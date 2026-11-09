import unittest

from specclib.prompt import extract_code_block, load_prompt_template, render_prompt
from specclib.spec import Spec

from . import support


class ExtractTest(unittest.TestCase):
    def test_fenced_with_language(self):
        self.assertEqual(extract_code_block("```python\nx = 1\n```\n"), "x = 1\n")

    def test_prose_around(self):
        self.assertEqual(extract_code_block("Here:\n```\nx = 1\n\n```\nDone."), "x = 1\n")

    def test_raw(self):
        self.assertEqual(extract_code_block("x = 1\n\n"), "x = 1\n")

    def test_inner_fence_closes_the_block(self):
        # The first two fences delimit the block; an inner fence is the model's problem.
        self.assertEqual(extract_code_block("```\na\n```\nb\n```\n"), "a\n")


class RenderTest(unittest.TestCase):
    def test_all_placeholders_replaced(self):
        project, spec = None, Spec(support.MINI_SPEC)
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            project, spec = support.make_project(d, impl_body=None)
            _, system, user = load_prompt_template(project)
            out = render_prompt(project, user, spec, "toy", spec.targets["toy"]["meta"], "- none", "(none)", "(none)")
        self.assertNotIn("{{", out)
        self.assertIn("### target toy", out)
        self.assertNotIn("```target", out)
        self.assertIn("## C. Algorithm", out)
        self.assertNotIn("## D. Targets", out)
        self.assertIn("Regenerate: python3", out)
        self.assertTrue(system.startswith("You translate"))
