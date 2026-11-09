import os

from specclib.check import verify
from specclib.lock import load_lock

from . import support


class CheckTest(support.ToyCase):
    def problems(self):
        return verify(self.project, self.spec, load_lock(self.project))

    def test_clean(self):
        self.assertEqual(self.problems(), [])

    def test_hand_edit(self):
        self.set_impl(self.impl().replace('"hello "', '"hi "'))
        self.assertEqual(self.problems(), ["toy: file content differs from the lock (hand edit?)"])

    def test_marker_missing(self):
        self.set_impl(self.impl().replace("# spec: fn shout\n", ""))
        self.assertIn("toy: marker '# spec: fn shout' found 0 times", self.problems())

    def test_marker_duplicated(self):
        self.set_impl(self.impl().replace("# spec: fn shout\n", "# spec: fn shout\n# spec: fn shout\n"))
        self.assertIn("toy: marker '# spec: fn shout' found 2 times", self.problems())

    def test_fn_markers_out_of_order(self):
        text = self.impl().replace("# spec: fn greet", "# spec: fn TMP").replace("# spec: fn shout", "# spec: fn greet").replace("# spec: fn TMP", "# spec: fn shout")
        self.set_impl(text)
        self.assertIn("toy: fn markers are not in spec order", self.problems())

    def test_type_marker_may_move(self):
        text = self.impl().replace("# spec: type Mode\n", "") + "# spec: type Mode\n"
        self.set_impl(text)
        self.assertEqual([p for p in self.problems() if "marker" in p], [])

    def test_stale_header(self):
        self.set_impl(self.impl().replace("(sha256 ", "(sha256 0"))
        self.assertIn("toy: header missing or stale spec hash", self.problems())

    def test_forbidden_line(self):
        self.set_impl(self.impl().replace("import sys\n", "import sys\nimport re\n"))
        self.assertIn("toy: forbidden line 'import re'", self.problems())

    def test_spec_changed(self):
        self.reload_spec(support.MINI_SPEC.replace("- Standard library only.", "- Standard library only, really."))
        p = self.problems()
        self.assertIn("spec changed since the lock was written (run build for every generated target)", p)
        self.assertIn("toy: spec chunks changed since generation", p)

    def test_missing_lock_entry(self):
        os.unlink(self.project.lock_path)
        self.assertIn("toy: no lock entry", self.problems())

    def test_missing_file(self):
        os.unlink(self.project.path("toy_impl.py"))
        self.assertIn("toy: toy_impl.py missing", self.problems())

    def test_not_generated_is_ignored(self):
        self.reload_spec(support.MINI_SPEC.replace("generated: true", "generated: false"))
        os.unlink(self.project.path("toy_impl.py"))
        self.assertEqual([p for p in self.problems() if p.startswith("toy:")], [])
