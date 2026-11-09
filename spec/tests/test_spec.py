import json
import unittest

from specclib.project import SpecError
from specclib.spec import Spec, load_spec, normalize

from . import support


class RealSpecTest(unittest.TestCase):
    def test_declarations(self):
        spec = load_spec(support.REAL)
        self.assertEqual([n for n, _ in spec.types], ["Operator", "SubstitutionType"])
        self.assertEqual(len(spec.fns), 25)
        self.assertEqual(spec.fns[0][0], "expand")
        self.assertEqual(spec.fns[-1][0], "pctEncode")
        self.assertEqual(sorted(spec.targets), ["csharp", "java", "python"])
        self.assertEqual(len(spec.conformance["fixtures"]), 5)

    def test_lock_matches_spec(self):
        """Fails when the spec changed and nobody ran build or relock."""
        spec = load_spec(support.REAL)
        with open(support.REAL.lock_path, encoding="utf-8") as f:
            lock = json.load(f)
        self.assertEqual(lock["spec_sha256"], spec.sha)
        for target, entry in lock["targets"].items():
            self.assertEqual(entry["chunk_hashes"], spec.chunk_hashes(), target)


class MiniSpecTest(unittest.TestCase):
    def test_parse(self):
        spec = Spec(support.MINI_SPEC)
        self.assertEqual([n for n, _ in spec.types], ["Mode"])
        self.assertEqual([(n, sig) for n, sig, _ in spec.fns],
                         [("greet", "greet(name: string) -> string"), ("shout", "shout(name: string) -> string")])
        meta = spec.targets["toy"]["meta"]
        self.assertEqual(meta["file"], "toy_impl.py")
        self.assertIs(meta["generated"], True)
        self.assertEqual(meta["comment"], "#")
        self.assertEqual(meta["forbid"], ["import re", "from re "])
        self.assertEqual(spec.conformance["fixtures"], ["fixtures/*.json"])

    def test_prompt_section_has_no_target_block(self):
        section = Spec(support.MINI_SPEC).targets["toy"]["prompt_section"]
        self.assertTrue(section.startswith("### target toy\n\n- Plain Python 3"))
        self.assertNotIn("```target", section)
        self.assertNotIn("forbid", section)

    def test_chunk_hashes(self):
        hashes = Spec(support.MINI_SPEC).chunk_hashes()
        self.assertEqual(sorted(hashes), ["fn greet", "fn shout", "section A", "section B", "type Mode"])

    def test_normalize_ignores_trailing_whitespace_only(self):
        self.assertEqual(normalize("a  \nb\n"), normalize("\na\nb"))
        self.assertNotEqual(normalize("a\n  b"), normalize("a\nb"))

    def test_whitespace_edit_does_not_change_hashes(self):
        a = Spec(support.MINI_SPEC).chunk_hashes()
        b = Spec(support.MINI_SPEC.replace('return "hello " + name\n', 'return "hello " + name   \n')).chunk_hashes()
        self.assertEqual(a, b)

    def test_section_b_prose_is_hashed_apart_from_types(self):
        a = Spec(support.MINI_SPEC).chunk_hashes()
        b = Spec(support.MINI_SPEC.replace("| shout | upper case |", "| shout | UPPER case |")).chunk_hashes()
        self.assertNotEqual(a["section B"], b["section B"])
        self.assertEqual(a["type Mode"], b["type Mode"])

    def test_missing_section(self):
        with self.assertRaisesRegex(SpecError, "missing section E"):
            Spec(support.MINI_SPEC.split("## E.")[0])

    def test_duplicate_fn(self):
        text = support.MINI_SPEC.replace("### fn shout(name: string) -> string", "### fn greet(x: string) -> string")
        with self.assertRaisesRegex(SpecError, "duplicate fn greet"):
            Spec(text)

    def test_unexpected_heading_in_c(self):
        with self.assertRaisesRegex(SpecError, "unexpected heading in section C"):
            Spec(support.MINI_SPEC.replace("### fn shout", "### helper shout"))

    def test_unexpected_heading_in_d(self):
        with self.assertRaisesRegex(SpecError, "unexpected heading in section D"):
            Spec(support.MINI_SPEC.replace("### target toy", "### toy"))

    def test_missing_target_key(self):
        with self.assertRaisesRegex(SpecError, "target toy is missing 'harness'"):
            Spec(support.MINI_SPEC.replace("harness: toy\n", ""))

    def test_bad_kv_line(self):
        with self.assertRaisesRegex(SpecError, "not a key: value line"):
            Spec(support.MINI_SPEC.replace("harness: toy\n", "harness toy\n"))

    def test_two_target_blocks(self):
        with self.assertRaisesRegex(SpecError, "more than one target block"):
            Spec(support.MINI_SPEC.replace("- Plain Python 3", "```target\nfile: x\n```\n- Plain Python 3"))

    def test_no_fixtures(self):
        with self.assertRaisesRegex(SpecError, "at least one 'fixtures:'"):
            Spec(support.MINI_SPEC.replace("fixtures: fixtures/*.json\n", ""))

    def test_generated_false_is_parsed(self):
        spec = Spec(support.MINI_SPEC.replace("generated: true", "generated: false"))
        self.assertIs(spec.targets["toy"]["meta"]["generated"], False)
