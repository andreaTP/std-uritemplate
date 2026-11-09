import datetime
import os

from .backend import generate
from .check import header_current
from .conformance import format_failures, load_cases, run_tck
from .lock import load_lock, save_lock
from .project import SpecError
from .prompt import extract_code_block, load_prompt_template, render_prompt
from .spec import header_lines, normalize, sha256


def build(project, spec, args):
    target = args.target
    if target not in spec.targets:
        raise SpecError("unknown target %s" % target)
    meta = spec.targets[target]["meta"]
    if not meta["generated"]:
        raise SpecError("target %s is not marked generated: true" % target)
    out_path = project.path(meta["file"])
    lock = load_lock(project)
    prompt_text, system_tpl, user_tpl = load_prompt_template(project)
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
            if lock.get("spec_sha256") != spec.sha or not header_current(project, spec, target, meta, out_path):
                return refresh_header(project, spec, target, meta, lock, out_path)
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

    cases = load_cases(project)
    failures_text = "(none)"
    stats = []
    for attempt in range(1, args.max_attempts + 1):
        print("[%s] attempt %d/%d: generating with: %s %s" % (target, attempt, args.max_attempts, args.backend, args.model or ""))
        user_prompt = render_prompt(project, user_tpl, spec, target, meta, changes, anchor_block, failures_text)
        result, duration_ms = generate(project, system_tpl, user_prompt, args.backend, args.model, args.verbose)
        stats.append(duration_ms)
        code = extract_code_block(result)
        expected_header = "\n".join(header_lines(project, spec, target, meta))
        if not code.startswith(expected_header):
            code = expected_header + "\n" + code
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(code)
        print("[%s] wrote %s (%d lines, %.1fs); running conformance suite ..." % (target, meta["file"], code.count("\n"), duration_ms / 1000))
        total, failures = run_tck(project, meta["harness"], cases=cases, jobs=args.jobs)
        print("[%s] %d/%d cases passed" % (target, total - len(failures), total))
        if not failures:
            lock = load_lock(project)  # another build may have written it meanwhile
            lock["spec_sha256"] = spec.sha
            lock["targets"][target] = {
                "file": meta["file"],
                "output_sha256": sha256(code),
                "chunk_hashes": hashes,
                "target_notes_sha256": notes_sha,
                "prompt_template_sha256": sha256(prompt_text),
                "backend": {"command": args.backend, "model": args.model or ""},
                "tck": {"cases": total, "result": "pass"},
                "attempts": attempt,
                "duration_ms": sum(stats),
                "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            save_lock(project, lock)
            print("[%s] lock updated after %d attempt(s)" % (target, attempt))
            return 0
        print(format_failures(failures))
        failures_text = format_failures(failures)
        with open(out_path, encoding="utf-8") as f:
            anchor_block = "```\n%s```" % f.read()
        changes = "- previous attempt failed conformance; fix the listed cases"
    print("[%s] giving up after %d attempts; the last output is left in %s" % (target, args.max_attempts, meta["file"]))
    return 1


def refresh_header(project, spec, target, meta, lock, out_path):
    # The spec changed outside this target's chunks: only the header hash is stale.
    with open(out_path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    header = header_lines(project, spec, target, meta)
    code = "\n".join(header + lines[len(header):])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    lock["spec_sha256"] = spec.sha
    lock["targets"][target]["output_sha256"] = sha256(code)
    save_lock(project, lock)
    print("%s: no chunk changed; refreshed the header hash without regenerating" % target)
    return 0
