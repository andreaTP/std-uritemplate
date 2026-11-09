"""A tiny synthetic project: a spec with one type and two functions, a Python 'toy' target and its harness."""
import json
import os
import stat
import tempfile
import unittest

from specclib.lock import save_lock
from specclib.project import Project
from specclib.spec import Spec, header_lines, normalize, sha256

MINI_SPEC = """# toy specification

## A. Design constraints

- Standard library only.

## B. Data model

### type Mode

`plain` or `shout`.

### Modes table

| mode | effect |
|---|---|
| shout | upper case |

## C. Algorithm

### fn greet(name: string) -> string

```pseudo
return "hello " + name
```

### fn shout(name: string) -> string

```pseudo
return upper(greet(name))
```

## D. Targets

Target blocks are read by the tool.

### target toy

```target
file: toy_impl.py
harness: toy
generated: true
comment: "#"
forbid: import re
forbid: "from re "
```

- Plain Python 3, no imports beyond `sys` and `json`.

## E. Conformance

```conformance
fixtures: fixtures/*.json
```
"""

MINI_FIXTURES = {
    "greetings": {
        "variables": {"name": "bob"},
        "testcases": [["{name}", "hello bob"], ["{name:shout}", ["HELLO BOB", "HELLO BOB!"]], ["{missing}", False]],
    }
}

MINI_IMPL_BODY = """import json
import sys

# spec: type Mode
MODES = ("plain", "shout")


# spec: fn greet
def greet(name):
    return "hello " + name


# spec: fn shout
def shout(name):
    return greet(name).upper()


template = open(sys.argv[1]).read().strip()
subs = json.load(open(sys.argv[2]))
var, _, mode = template[1:-1].partition(":")
if var not in subs:
    print("false")
else:
    print(shout(subs[var]) if mode == "shout" else greet(subs[var]))
"""


def make_project(tmpdir, spec_text=MINI_SPEC, impl_body=MINI_IMPL_BODY, fixtures=MINI_FIXTURES, with_lock=True):
    """Write the toy project under tmpdir and return (project, spec)."""
    spec_path = os.path.join(tmpdir, "toy.spec.md")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_text)
    project = Project(spec_path)
    spec = Spec(spec_text)
    os.makedirs(os.path.join(tmpdir, "fixtures"))
    with open(os.path.join(tmpdir, "fixtures", "cases.json"), "w", encoding="utf-8") as f:
        json.dump(fixtures, f)
    os.makedirs(os.path.join(tmpdir, "toy"))
    write_exec(os.path.join(tmpdir, "toy", "init.sh"), "#!/usr/bin/env bash\nexit 0\n")
    write_exec(os.path.join(tmpdir, "toy", "test.sh"),
               '#!/usr/bin/env bash\nexec python3 "$(dirname "$0")/../toy_impl.py" "$1" "$2"\n')
    if impl_body is not None:
        content = impl_text(project, spec, impl_body)
        with open(project.path("toy_impl.py"), "w", encoding="utf-8") as f:
            f.write(content)
        if with_lock:
            save_lock(project, make_lock(project, spec, "toy", content))
    return project, spec


def impl_text(project, spec, body, target="toy"):
    return "\n".join(header_lines(project, spec, target, spec.targets[target]["meta"])) + "\n" + body


def make_lock(project, spec, target, content):
    return {"spec_sha256": spec.sha, "targets": {target: {
        "file": spec.targets[target]["meta"]["file"],
        "output_sha256": sha256(content),
        "chunk_hashes": spec.chunk_hashes(),
        "target_notes_sha256": sha256(normalize(spec.targets[target]["prompt_section"])),
        "prompt_template_sha256": sha256(read(project.prompt_path)),
        "backend": {"command": "test", "model": "none"},
        "tck": {"cases": 3, "result": "pass"},
        "attempts": 1,
        "duration_ms": 0,
        "generated_at": "2026-01-01T00:00:00Z",
    }}}


def write_exec(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class ToyCase(unittest.TestCase):
    """A fresh toy project per test in self.project / self.spec / self.dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="specc-test-")
        self.dir = self._tmp.name
        self.project, self.spec = make_project(self.dir)

    def tearDown(self):
        self._tmp.cleanup()

    def impl(self):
        return read(self.project.path("toy_impl.py"))

    def set_impl(self, text):
        write(self.project.path("toy_impl.py"), text)

    def reload_spec(self, text):
        write(self.project.spec_path, text)
        self.spec = Spec(text)
        return self.spec


REAL = Project()  # the std-uritemplate spec next to the tool
