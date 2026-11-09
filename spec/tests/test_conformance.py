from specclib.conformance import format_failures, load_cases, run_tck
from specclib.project import SpecError

from . import support


class ConformanceTest(support.ToyCase):
    def test_load_cases(self):
        cases = load_cases(self.project, self.spec)
        self.assertEqual([c["expected"] for c in cases], [["hello bob"], ["HELLO BOB", "HELLO BOB!"], ["false"]])
        self.assertEqual(cases[0]["file"], "fixtures/cases.json")

    def test_missing_fixture(self):
        self.reload_spec(support.MINI_SPEC.replace("fixtures/*.json", "nowhere/*.json"))
        with self.assertRaisesRegex(SpecError, "fixture not found"):
            load_cases(self.project, self.spec)

    def test_pass(self):
        total, failures = run_tck(self.project, "toy", load_cases(self.project, self.spec))
        self.assertEqual((total, failures), (3, []))

    def test_failure_reports_got(self):
        self.set_impl(self.impl().replace('"hello "', '"hi "'))
        total, failures = run_tck(self.project, "toy", load_cases(self.project, self.spec))
        self.assertEqual(total, 3)
        self.assertEqual([(f["template"], f["got"]) for f in failures], [("{name:shout}", "HI BOB"), ("{name}", "hi bob")])
        text = format_failures(failures)
        self.assertIn("template: {name}", text)
        self.assertIn("got: hi bob", text)

    def test_init_failure(self):
        support.write_exec(self.project.path("toy/init.sh"), "#!/usr/bin/env bash\necho 'error: no compiler' >&2\nexit 3\n")
        total, failures = run_tck(self.project, "toy", load_cases(self.project, self.spec))
        self.assertEqual(total, 0)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["got"], "exit 3")
        self.assertIn("error: no compiler", format_failures(failures))

    def test_format_limit(self):
        failures = [{"template": "{%d}" % i, "variables": {}, "expected": ["x"], "got": "y", "stderr": "", "file": "f"} for i in range(5)]
        self.assertTrue(format_failures(failures, limit=2).endswith("- ... and 3 more"))
