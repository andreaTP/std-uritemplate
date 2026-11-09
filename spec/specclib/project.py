import glob
import os

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SpecError(Exception):
    """The spec, lock or project layout is unusable; reported as exit code 2."""


class Project:
    def __init__(self, spec_path=None):
        if spec_path is None:
            found = sorted(glob.glob(os.path.join(os.path.dirname(TOOL_DIR), "*.spec.md")))
            if len(found) != 1:
                raise SpecError("expected exactly one *.spec.md next to the tool directory, found %d; use --spec" % len(found))
            spec_path = found[0]
        if not spec_path.endswith(".spec.md"):
            raise SpecError("spec file name must end with .spec.md: %s" % spec_path)
        self.spec_path = os.path.abspath(spec_path)
        if not os.path.isfile(self.spec_path):
            raise SpecError("spec file not found: %s" % self.spec_path)
        self.root = os.path.dirname(self.spec_path)
        self.lock_path = self.spec_path[: -len(".spec.md")] + ".lock.json"
        self.prompt_path = os.path.join(TOOL_DIR, "prompts", "generate.md")
        self.tool_rel = os.path.relpath(os.path.join(TOOL_DIR, "specc.py"), self.root)

    def path(self, rel):
        return os.path.join(self.root, rel)
