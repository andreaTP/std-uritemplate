import concurrent.futures
import json
import os
import subprocess
import tempfile

from .project import SpecError

FIXTURE_DIRS = ["uritemplate-test", "uritemplate-test-additional"]


def load_cases(project):
    cases = []
    for d in FIXTURE_DIRS:
        full = project.path(d)
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
        raise SpecError("no fixtures found; run: git submodule update --init")
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


def run_tck(project, harness, cases=None, jobs=8):
    harness_dir = project.path(harness)
    cases = cases or load_cases(project)
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
