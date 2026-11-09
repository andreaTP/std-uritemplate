import contextlib
import io
import json
import os
from unittest import mock

from specclib import cli
from specclib.lock import load_lock
from specclib.spec import Spec

from . import support

REPLAY = "spec/backends/replay.sh"


def replay_backend(project):
    return "%s %s" % (os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), REPLAY), project.path("toy_impl.py"))


class BuildTest(support.ToyCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(["--spec", self.project.spec_path] + list(argv))
        return code, out.getvalue()

    def test_up_to_date(self):
        code, out = self.run_cli("build", "--target", "toy", "--backend", "false")
        self.assertEqual(code, 0)
        self.assertIn("up to date", out)

    def test_force_with_replay(self):
        before = self.impl()
        code, out = self.run_cli("build", "--target", "toy", "--force", "--backend", replay_backend(self.project), "--model", "m1")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.impl(), before)
        entry = load_lock(self.project)["targets"]["toy"]
        self.assertEqual(entry["backend"], {"command": replay_backend(self.project), "model": "m1"})
        self.assertEqual(entry["attempts"], 1)
        self.assertEqual(entry["tck"], {"cases": 3, "result": "pass"})

    def test_retry_feeds_failures_back(self):
        good = self.impl()
        bad = good.replace('"hello "', '"hi "')
        prompts = []

        def fake(project, system, user, backend, model, verbose=False):
            prompts.append(user)
            return ("```\n%s```\n" % (bad if len(prompts) == 1 else good)), 5

        with mock.patch("specclib.build.generate", fake):
            code, out = self.run_cli("build", "--target", "toy", "--force", "--backend", "fake")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(prompts), 2)
        self.assertIn("template: {name}", prompts[1])
        self.assertIn("got: hi bob", prompts[1])
        self.assertIn("previous attempt failed conformance", prompts[1])
        self.assertEqual(load_lock(self.project)["targets"]["toy"]["attempts"], 2)
        self.assertEqual(load_lock(self.project)["targets"]["toy"]["duration_ms"], 10)

    def test_gives_up(self):
        bad = self.impl().replace('"hello "', '"hi "')
        with mock.patch("specclib.build.generate", lambda *a, **k: ("```\n%s```\n" % bad, 1)):
            code, out = self.run_cli("build", "--target", "toy", "--force", "--backend", "fake", "--max-attempts", "1")
        self.assertEqual(code, 1)
        self.assertIn("giving up after 1 attempts", out)
        self.assertEqual(self.impl(), bad)

    def test_header_prepended_when_missing(self):
        body = support.MINI_IMPL_BODY
        with mock.patch("specclib.build.generate", lambda *a, **k: ("```python\n%s```\n" % body, 1)):
            code, out = self.run_cli("build", "--target", "toy", "--force", "--backend", "fake")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.impl(), support.impl_text(self.project, self.spec, body))

    def test_spec_change_in_chunk_regenerates(self):
        spec = self.reload_spec(support.MINI_SPEC.replace('return "hello " + name', 'return "hello, " + name'))
        prompts = []

        def fake(project, system, user, backend, model, verbose=False):
            prompts.append(user)
            return "```\n%s```\n" % support.impl_text(project, spec, support.MINI_IMPL_BODY), 1

        with mock.patch("specclib.build.generate", fake):
            code, out = self.run_cli("build", "--target", "toy", "--backend", "fake")
        self.assertEqual(code, 0, out)
        self.assertIn("- fn greet", prompts[0])
        self.assertNotIn("- fn shout", prompts[0])
        self.assertEqual(load_lock(self.project)["spec_sha256"], spec.sha)

    def test_refresh_header_without_backend(self):
        old_backend = load_lock(self.project)["targets"]["toy"]["backend"]
        spec = self.reload_spec(support.MINI_SPEC.replace("- Plain Python 3", "- Plain Python 3, please"))
        code, out = self.run_cli("build", "--target", "toy", "--backend", "false")
        # target notes changed: that is a regeneration, so the backend ('false') fails
        self.assertEqual(code, 2)
        spec = self.reload_spec(support.MINI_SPEC.replace("Target blocks are read", "Target blocks are parsed"))
        code, out = self.run_cli("build", "--target", "toy", "--backend", "false")
        self.assertEqual(code, 0, out)
        self.assertIn("refreshed the header", out)
        lock = load_lock(self.project)
        self.assertEqual(lock["spec_sha256"], spec.sha)
        self.assertEqual(lock["targets"]["toy"]["backend"], old_backend)
        self.assertTrue(self.impl().startswith("# GENERATED FILE - DO NOT EDIT.\n# Source: toy.spec.md (sha256 %s)" % spec.sha[:12]))
        code, out = self.run_cli("check")
        self.assertEqual(code, 0, out)

    def test_lock_reread_before_write(self):
        def fake(project, system, user, backend, model, verbose=False):
            lock = load_lock(project)
            lock["targets"]["other"] = {"file": "x"}
            with open(project.lock_path, "w") as f:
                json.dump(lock, f)
            return "```\n%s```\n" % self.impl(), 1

        with mock.patch("specclib.build.generate", fake):
            code, out = self.run_cli("build", "--target", "toy", "--force", "--backend", "fake")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(load_lock(self.project)["targets"]), ["other", "toy"])

    def test_dry_run_writes_nothing(self):
        before = (self.impl(), support.read(self.project.lock_path))
        with mock.patch("specclib.build.generate", side_effect=AssertionError("must not be called")):
            code, out = self.run_cli("build", "--target", "toy", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("=== system ===", out)
        self.assertIn("### target toy", out)
        self.assertIn(support.MINI_IMPL_BODY.splitlines()[0], out)  # the anchor
        self.assertEqual((self.impl(), support.read(self.project.lock_path)), before)

    def test_check_tck(self):
        code, out = self.run_cli("check", "--tck")
        self.assertEqual(code, 0, out)
        self.assertIn("toy: 3/3 conformance cases passed", out)

    def test_unknown_target(self):
        code, out = self.run_cli("tck", "--target", "nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown target nope", out)


class RelockTest(support.ToyCase):
    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(["--spec", self.project.spec_path] + list(argv))
        return code, out.getvalue()

    def test_relock_after_notes_change(self):
        spec = self.reload_spec(support.MINI_SPEC.replace("- Plain Python 3", "- Plain Python 3, please"))
        code, out = self.run_cli("check")
        self.assertEqual(code, 1)
        code, out = self.run_cli("relock", "--target", "toy")
        self.assertEqual(code, 0, out)
        entry = load_lock(self.project)["targets"]["toy"]
        self.assertEqual(entry["backend"], {"command": "test", "model": "none"})
        self.assertEqual(entry["tck"]["cases"], 3)
        self.assertIn("verified_at", entry["tck"])
        self.assertEqual(entry["chunk_hashes"], spec.chunk_hashes())
        code, out = self.run_cli("check")
        self.assertEqual(code, 0, out)

    def test_relock_accepts_new_chunk_keys(self):
        lock = load_lock(self.project)
        del lock["targets"]["toy"]["chunk_hashes"]["section B"]
        support.write(self.project.lock_path, json.dumps(lock))
        code, out = self.run_cli("relock", "--target", "toy")
        self.assertEqual(code, 0, out)

    def test_relock_refuses_chunk_change(self):
        self.reload_spec(support.MINI_SPEC.replace('return "hello " + name', 'return "hello, " + name'))
        code, out = self.run_cli("relock", "--target", "toy")
        self.assertEqual(code, 1)
        self.assertIn("spec chunks changed (fn greet)", out)

    def test_relock_refuses_hand_edit(self):
        self.set_impl(self.impl() + "\n# extra\n")
        code, out = self.run_cli("relock", "--target", "toy")
        self.assertEqual(code, 1)
        self.assertIn("differs from the locked output", out)

    def test_relock_refuses_failing_suite(self):
        support.write(self.project.path("fixtures/cases.json"), json.dumps({"g": {"variables": {"name": "x"}, "testcases": [["{name}", "nope"]]}}))
        code, out = self.run_cli("relock", "--target", "toy")
        self.assertEqual(code, 1)
        self.assertIn("0/1 cases passed", out)
