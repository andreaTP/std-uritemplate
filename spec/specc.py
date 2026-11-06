#!/usr/bin/env python3
"""std-uritemplate spec compiler (prototype).

Commands:
  parse            show the functions and targets declared in the spec
  build --target X generate target X from the spec, gate it on the conformance suite, write the lock
  check            verify generated files match the spec and the lock (no LLM call)
  tck --target X   run the conformance suite through <harness>/test.sh (reentrant, parallel)
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(ROOT, "std-uritemplate.spec.md")
LOCK_PATH = os.path.join(ROOT, "std-uritemplate.lock.json")
PROMPT_PATH = os.path.join(ROOT, "spec", "prompts", "generate.md")
FIXTURE_DIRS = ["uritemplate-test", "uritemplate-test-additional"]
DEFAULT_MODEL = "claude-opus-5-5"
FORBIDDEN_IMPORTS = {
    "python": ["import re", "from re ", "import urllib", "from urllib"],
    "java": ["import java.util.regex", "import java.net.URLEncoder", "import java.net.URLDecoder"],
    "csharp": ["using System.Text.RegularExpressions"],
}


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text):
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


class Spec:
    def __init__(self, text):
        self.text = text
        self.sha = sha256(text)
        self.sections = {}  # "A".."E" -> text (including heading)
        self.types = []  # [(name, text)]
        self.fns = []  # [(name, signature, text)]
        self.targets = {}  # name -> {"meta": {...}, "notes": text, "section": text}
        self._parse()

    def _parse(self):
        current = None
        buf = []
        for line in self.text.splitlines():
            if line.startswith("## "):
                if current:
                    self.sections[current] = "\n".join(buf)
                current = line[3:4]
                buf = [line]
            elif current:
                buf.append(line)
        if current:
            self.sections[current] = "\n".join(buf)
        for key in "ABCDE":
            if key not in self.sections:
                raise SystemExit("spec: missing section %s" % key)
        self.types = [(h[len("### type "):].strip(), body) for h, body in self._subsections("B") if h.startswith("### type ")]
        for h, body in self._subsections("C"):
            if not h.startswith("### fn "):
                raise SystemExit("spec: unexpected heading in section C: %s" % h)
            sig = h[len("### fn "):].strip()
            name = sig.split("(", 1)[0]
            if any(n == name for n, _, _ in self.fns):
                raise SystemExit("spec: duplicate fn %s" % name)
            self.fns.append((name, sig, body))
        for h, body in self._subsections("D"):
            if not h.startswith("### target "):
                raise SystemExit("spec: unexpected heading in section D: %s" % h)
            name = h[len("### target "):].strip()
            meta, notes = self._parse_target(body, name)
            self.targets[name] = {"meta": meta, "notes": notes, "section": body}

    def _subsections(self, key):
        out = []
        heading = None
        buf = []
        for line in self.sections[key].splitlines():
            if line.startswith("### "):
                if heading:
                    out.append((heading, "\n".join(buf)))
                heading = line
                buf = [line]
            elif heading:
                buf.append(line)
        if heading:
            out.append((heading, "\n".join(buf)))
        return out

    @staticmethod
    def _parse_target(body, name):
        meta = {}
        notes = []
        in_block = False
        for line in body.splitlines()[1:]:
            if line.strip() == "```target":
                in_block = True
                continue
            if in_block and line.strip() == "```":
                in_block = False
                continue
            if in_block:
                k, _, v = line.partition(":")
                v = v.strip().strip('"')
                meta[k.strip()] = {"true": True, "false": False}.get(v, v)
            else:
                notes.append(line)
        for k in ("file", "harness", "generated", "comment"):
            if k not in meta:
                raise SystemExit("spec: target %s is missing '%s'" % (name, k))
        return meta, "\n".join(notes).strip()

    def chunk_hashes(self):
        hashes = {"type " + n: sha256(normalize(t)) for n, t in self.types}
        hashes.update({"fn " + n: sha256(normalize(t)) for n, _, t in self.fns})
        hashes["section A"] = sha256(normalize(self.sections["A"]))
        return hashes

    def core_text(self):
        return "\n\n".join(self.sections[k] for k in "ABC")


def load_spec():
    with open(SPEC_PATH, encoding="utf-8") as f:
        return Spec(f.read())


def load_lock():
    if not os.path.exists(LOCK_PATH):
        return {"targets": {}}
    with open(LOCK_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_lock(lock):
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")


def header_lines(spec, target, meta):
    c = meta["comment"]
    return [
        "%s GENERATED FILE - DO NOT EDIT." % c,
        "%s Source: std-uritemplate.spec.md (sha256 %s)" % (c, spec.sha[:12]),
        "%s Regenerate: python3 spec/specc.py build --target %s" % (c, target),
    ]


# ---------------------------------------------------------------- conformance


def load_cases():
    cases = []
    for d in FIXTURE_DIRS:
        full = os.path.join(ROOT, d)
        for fname in sorted(os.listdir(full)):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(full, fname), encoding="utf-8") as f:
                data = json.load(f)
            for group, body in data.items():
                variables = body["variables"]
                for template, expected in body["testcases"]:
                    if isinstance(expected, list):
                        acceptable = expected
                    elif expected is False:
                        acceptable = ["false"]
                    else:
                        acceptable = [expected]
                    cases.append({"file": fname, "group": group, "template": template, "variables": variables, "expected": acceptable})
    if not cases:
        raise SystemExit("no fixtures found; run: git submodule update --init")
    return cases


def run_case(harness_dir, case, scratch):
    fd, tpath = tempfile.mkstemp(dir=scratch, suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(case["template"] + "\n")
    fd, spath = tempfile.mkstemp(dir=scratch, suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(case["variables"], f, ensure_ascii=False)
    try:
        proc = subprocess.run([os.path.join(harness_dir, "test.sh"), tpath, spath], capture_output=True, text=True)
        got = proc.stdout.rstrip("\n")
        ok = got in case["expected"]
        return ok, got, proc.stderr.strip()
    finally:
        os.unlink(tpath)
        os.unlink(spath)


def run_tck(harness, cases=None, jobs=8, verbose=False):
    harness_dir = os.path.join(ROOT, harness)
    cases = cases or load_cases()
    init = subprocess.run(["bash", os.path.join(harness_dir, "init.sh")], capture_output=True, text=True)
    if init.returncode != 0:
        log = (init.stdout + init.stderr).strip().splitlines()
        errors = [line for line in log if "error" in line.lower()] or log
        return 0, [{"file": "init.sh", "group": "build", "template": "(build failed)", "variables": {},
                    "expected": ["a successful build"], "got": "exit %d" % init.returncode,
                    "stderr": "\n".join(errors[-15:])}]
    scratch = tempfile.mkdtemp(prefix="specc-tck-")
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_case, harness_dir, c, scratch): c for c in cases}
        for fut in concurrent.futures.as_completed(futures):
            case = futures[fut]
            ok, got, err = fut.result()
            if not ok:
                failures.append(dict(case, got=got, stderr=err))
    os.rmdir(scratch)
    failures.sort(key=lambda c: (c["file"], c["group"], c["template"]))
    return len(cases), failures


def format_failures(failures, limit=12):
    out = []
    for f in failures[:limit]:
        out.append("- template: %s\n  variables: %s\n  expected one of: %s\n  got: %s" % (
            f["template"], json.dumps(f["variables"], ensure_ascii=False), json.dumps(f["expected"], ensure_ascii=False), f["got"]))
        if f["stderr"]:
            out.append("  stderr: " + f["stderr"] if f["file"] == "init.sh" else "  stderr: " + f["stderr"].splitlines()[-1])
    if len(failures) > limit:
        out.append("- ... and %d more" % (len(failures) - limit))
    return "\n".join(out)


# ------------------------------------------------------------------- backend


def claude_cli_version():
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def generate_with_claude_cli(system_prompt, user_prompt, args):
    cmd = ["claude", "-p", "--model", args.model, "--output-format", "json", "--no-session-persistence", "--tools", "", "--system-prompt", system_prompt]
    if args.verbose:
        print("  calling: %s (prompt %d chars)" % (" ".join(cmd[:6]), len(user_prompt)))
    proc = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit("claude CLI failed (%d):\n%s" % (proc.returncode, proc.stderr[-2000:]))
    data = json.loads(proc.stdout)
    if data.get("is_error"):
        raise SystemExit("claude CLI returned an error: %s" % data.get("result"))
    usage = {"cost_usd": data.get("total_cost_usd"), "duration_ms": data.get("duration_api_ms")}
    return data["result"], usage, {"name": "claude-cli", "version": claude_cli_version(), "model": args.model}


def generate_with_command(system_prompt, user_prompt, args):
    """Any program: system prompt in $SPECC_SYSTEM_PROMPT, user prompt on stdin, answer on stdout."""
    if not args.backend_command:
        raise SystemExit("--backend command needs --backend-command")
    env = dict(os.environ, SPECC_SYSTEM_PROMPT=system_prompt, SPECC_MODEL=args.model or "")
    if args.verbose:
        print("  calling: %s (prompt %d chars)" % (args.backend_command, len(user_prompt)))
    started = datetime.datetime.now()
    proc = subprocess.run(args.backend_command, shell=True, input=user_prompt, capture_output=True, text=True, cwd=ROOT, env=env)
    if proc.returncode != 0:
        raise SystemExit("backend command failed (%d):\n%s" % (proc.returncode, proc.stderr[-2000:]))
    usage = {"cost_usd": None, "duration_ms": int((datetime.datetime.now() - started).total_seconds() * 1000)}
    return proc.stdout, usage, {"name": "command", "command": args.backend_command, "model": args.model or ""}


BACKENDS = {"claude-cli": generate_with_claude_cli, "command": generate_with_command}


def extract_code_block(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("```"):
            if start is None:
                start = i
            else:
                return "\n".join(lines[start + 1:i]).rstrip() + "\n"
    return text.strip() + "\n"


def load_prompt_template():
    with open(PROMPT_PATH, encoding="utf-8") as f:
        text = f.read()
    _, system_and_user = text.split("## system", 1)
    system, user = system_and_user.split("## user", 1)
    return text, system.strip(), user.strip()


def render_prompt(user_tpl, spec, target, meta, changes, anchor, failures):
    header = "\n".join(header_lines(spec, target, meta))
    repl = {
        "{{TARGET}}": target,
        "{{HEADER}}": header,
        "{{SPEC_CORE}}": spec.core_text(),
        "{{TARGET_SECTION}}": spec.targets[target]["section"],
        "{{CHANGES}}": changes,
        "{{ANCHOR}}": anchor,
        "{{FAILURES}}": failures,
    }
    out = user_tpl
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


# ------------------------------------------------------------------ commands


def cmd_parse(args):
    spec = load_spec()
    print("spec sha256: %s" % spec.sha)
    print("\ntypes (%d):" % len(spec.types))
    for name, _ in spec.types:
        print("  %s" % name)
    print("\nfunctions (%d):" % len(spec.fns))
    for name, sig, _ in spec.fns:
        print("  %s" % sig)
    print("\ntargets (%d):" % len(spec.targets))
    for name, t in spec.targets.items():
        m = t["meta"]
        print("  %-8s generated=%-5s file=%s" % (name, m["generated"], m["file"]))
    return 0


def cmd_tck(args):
    spec = load_spec()
    meta = spec.targets[args.target]["meta"]
    total, failures = run_tck(meta["harness"], jobs=args.jobs, verbose=args.verbose)
    print("%s: %d/%d conformance cases passed" % (args.target, total - len(failures), total))
    if failures:
        print(format_failures(failures, limit=args.limit))
        return 1
    return 0


def cmd_build(args):
    spec = load_spec()
    target = args.target
    if target not in spec.targets:
        raise SystemExit("unknown target %s" % target)
    meta = spec.targets[target]["meta"]
    if not meta["generated"]:
        raise SystemExit("target %s is not marked generated: true" % target)
    out_path = os.path.join(ROOT, meta["file"])
    lock = load_lock()
    prompt_text, system_tpl, user_tpl = load_prompt_template()
    hashes = spec.chunk_hashes()
    notes_sha = sha256(normalize(spec.targets[target]["section"]))
    prev = lock["targets"].get(target)

    changed = []
    if prev:
        for k, v in hashes.items():
            if prev["chunk_hashes"].get(k) != v:
                changed.append(k)
        if prev["target_notes_sha256"] != notes_sha:
            changed.append("target notes")
        if prev["prompt_template_sha256"] != sha256(prompt_text):
            changed.append("prompt template")
        if not changed and not args.force:
            if lock.get("spec_sha256") != spec.sha or not header_current(spec, target, meta, out_path):
                return refresh_header(spec, target, meta, lock, out_path)
            print("%s: up to date (no spec change since last build); use --force to regenerate" % target)
            return 0
        changes = "\n".join("- " + c for c in changed) if changed else "- none (forced regeneration)"
    else:
        changes = "- first generation from the spec; the anchor is the hand-written implementation"

    anchor = ""
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            anchor = f.read()
        if prev and sha256(anchor) != prev["output_sha256"]:
            print("warning: %s differs from the lock (hand-edited?); using it as anchor anyway" % meta["file"])
    anchor_block = "```\n%s```" % anchor if anchor else "(none)"

    cases = load_cases()
    failures_text = "(none)"
    stats = []
    for attempt in range(1, args.max_attempts + 1):
        print("[%s] attempt %d/%d: generating with %s %s ..." % (target, attempt, args.max_attempts, args.backend, args.model or ""))
        user_prompt = render_prompt(user_tpl, spec, target, meta, changes, anchor_block, failures_text)
        result, usage, backend_info = BACKENDS[args.backend](system_tpl, user_prompt, args)
        stats.append(usage)
        code = extract_code_block(result)
        expected_header = "\n".join(header_lines(spec, target, meta))
        if not code.startswith(expected_header):
            code = expected_header + "\n" + code
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(code)
        print("[%s] wrote %s (%d lines, $%.3f); running conformance suite ..." % (target, meta["file"], code.count("\n"), usage["cost_usd"] or 0))
        total, failures = run_tck(meta["harness"], cases=cases, jobs=args.jobs, verbose=args.verbose)
        print("[%s] %d/%d cases passed" % (target, total - len(failures), total))
        if not failures:
            lock = load_lock()  # another build may have written it meanwhile
            lock["spec_sha256"] = spec.sha
            lock["targets"][target] = {
                "file": meta["file"],
                "output_sha256": sha256(code),
                "chunk_hashes": hashes,
                "target_notes_sha256": notes_sha,
                "prompt_template_sha256": sha256(prompt_text),
                "backend": backend_info,
                "tck": {"cases": total, "result": "pass"},
                "attempts": attempt,
                "cost_usd": round(sum(s["cost_usd"] or 0 for s in stats), 4) if any(s["cost_usd"] is not None for s in stats) else None,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            save_lock(lock)
            print("[%s] lock updated; total cost $%.3f over %d attempt(s)" % (target, lock["targets"][target]["cost_usd"] or 0, attempt))
            return 0
        print(format_failures(failures))
        failures_text = format_failures(failures)
        with open(out_path, encoding="utf-8") as f:
            anchor_block = "```\n%s```" % f.read()
        changes = "- previous attempt failed conformance; fix the listed cases"
    print("[%s] giving up after %d attempts; the last output is left in %s" % (target, args.max_attempts, meta["file"]))
    return 1


def header_current(spec, target, meta, out_path):
    if not os.path.exists(out_path):
        return False
    with open(out_path, encoding="utf-8") as f:
        return f.read().startswith("\n".join(header_lines(spec, target, meta)))


def refresh_header(spec, target, meta, lock, out_path):
    # The spec changed outside this target's chunks: only the header hash is stale.
    with open(out_path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    header = header_lines(spec, target, meta)
    code = "\n".join(header + lines[len(header):])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    lock["spec_sha256"] = spec.sha
    lock["targets"][target]["output_sha256"] = sha256(code)
    save_lock(lock)
    print("%s: no chunk changed; refreshed the header hash without regenerating" % target)
    return 0


def cmd_check(args):
    spec = load_spec()
    lock = load_lock()
    problems = []
    if lock.get("spec_sha256") != spec.sha:
        problems.append("spec changed since the lock was written (run build for every generated target)")
    for target, t in spec.targets.items():
        meta = t["meta"]
        if not meta["generated"]:
            continue
        entry = lock["targets"].get(target)
        path = os.path.join(ROOT, meta["file"])
        if not entry:
            problems.append("%s: no lock entry" % target)
            continue
        if not os.path.exists(path):
            problems.append("%s: %s missing" % (target, meta["file"]))
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        expected_header = "\n".join(header_lines(spec, target, meta))
        if not content.startswith(expected_header):
            problems.append("%s: header missing or stale spec hash" % target)
        if sha256(content) != entry["output_sha256"]:
            problems.append("%s: file content differs from the lock (hand edit?)" % target)
        if entry["chunk_hashes"] != spec.chunk_hashes():
            problems.append("%s: spec chunks changed since generation" % target)
        c = meta["comment"]
        for kind, names in (("type", [n for n, _ in spec.types]), ("fn", [n for n, _, _ in spec.fns])):
            for name in names:
                marker = "%s spec: %s %s" % (c, kind, name)
                count = sum(1 for line in content.splitlines() if line.strip() == marker)
                if count != 1:
                    problems.append("%s: marker '%s' found %d times" % (target, marker, count))
        for needle in FORBIDDEN_IMPORTS.get(target, []):
            if any(line.strip().startswith(needle) for line in content.splitlines()):
                problems.append("%s: forbidden import '%s'" % (target, needle))
    if problems:
        print("check: FAILED")
        for p in problems:
            print("  - " + p)
        return 1
    n = sum(1 for t in spec.targets.values() if t["meta"]["generated"])
    print("check: OK (%d generated target(s) match the spec and the lock)" % n)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("parse").set_defaults(fn=cmd_parse)
    b = sub.add_parser("build")
    b.add_argument("--target", required=True)
    b.add_argument("--backend", choices=sorted(BACKENDS), default="claude-cli")
    b.add_argument("--backend-command", help="for --backend command: shell command that reads the user prompt on stdin, "
                   "the system prompt from $SPECC_SYSTEM_PROMPT and $SPECC_MODEL, and prints the answer")
    b.add_argument("--model", default=None, help="model name passed to the backend (default for claude-cli: %s)" % DEFAULT_MODEL)
    b.add_argument("--max-attempts", type=int, default=2)
    b.add_argument("--jobs", type=int, default=8)
    b.add_argument("--force", action="store_true")
    b.add_argument("--verbose", action="store_true")
    b.set_defaults(fn=cmd_build)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    t = sub.add_parser("tck")
    t.add_argument("--target", required=True)
    t.add_argument("--jobs", type=int, default=8)
    t.add_argument("--limit", type=int, default=12)
    t.add_argument("--verbose", action="store_true")
    t.set_defaults(fn=cmd_tck)
    args = ap.parse_args()
    if args.cmd == "build" and args.backend == "claude-cli" and not args.model:
        args.model = DEFAULT_MODEL
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
