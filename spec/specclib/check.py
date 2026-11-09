import os

from .spec import header_lines, sha256

def header_current(project, spec, target, meta, out_path):
    if not os.path.exists(out_path):
        return False
    with open(out_path, encoding="utf-8") as f:
        return f.read().startswith("\n".join(header_lines(project, spec, target, meta)))


def verify(project, spec, lock):
    """Static consistency of generated files against spec and lock; returns a list of problems."""
    problems = []
    if lock.get("spec_sha256") != spec.sha:
        problems.append("spec changed since the lock was written (run build for every generated target)")
    for target, t in spec.targets.items():
        meta = t["meta"]
        if not meta["generated"]:
            continue
        entry = lock["targets"].get(target)
        path = project.path(meta["file"])
        if not entry:
            problems.append("%s: no lock entry" % target)
            continue
        if not os.path.exists(path):
            problems.append("%s: %s missing" % (target, meta["file"]))
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        expected_header = "\n".join(header_lines(project, spec, target, meta))
        if not content.startswith(expected_header):
            problems.append("%s: header missing or stale spec hash" % target)
        if sha256(content) != entry["output_sha256"]:
            problems.append("%s: file content differs from the lock (hand edit?)" % target)
        if entry["chunk_hashes"] != spec.chunk_hashes():
            problems.append("%s: spec chunks changed since generation" % target)
        problems.extend("%s: %s" % (target, p) for p in check_markers(spec, meta, content))
        for needle in meta["forbid"]:
            if any(line.strip().startswith(needle) for line in content.splitlines()):
                problems.append("%s: forbidden line '%s'" % (target, needle))
    return problems


def markers(spec, meta):
    c = meta["comment"]
    return ["%s spec: type %s" % (c, n) for n, _ in spec.types] + ["%s spec: fn %s" % (c, n) for n, _, _ in spec.fns]


def check_markers(spec, meta, content):
    """Every marker exactly once; fn markers in spec order (types sit where the idiom wants them)."""
    expected = markers(spec, meta)
    found = [line.strip() for line in content.splitlines() if line.strip() in set(expected)]
    problems = []
    for m in expected:
        count = found.count(m)
        if count != 1:
            problems.append("marker '%s' found %d times" % (m, count))
    fn_prefix = "%s spec: fn " % meta["comment"]
    if not problems and [m for m in found if m.startswith(fn_prefix)] != [m for m in expected if m.startswith(fn_prefix)]:
        problems.append("fn markers are not in spec order")
    return problems
