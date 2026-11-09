import os

from .spec import header_lines, sha256

FORBIDDEN_IMPORTS = {
    "python": ["import re", "from re ", "import urllib", "from urllib"],
    "java": ["import java.util.regex", "import java.net.URLEncoder", "import java.net.URLDecoder"],
    "csharp": ["using System.Text.RegularExpressions"],
}


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
    return problems
