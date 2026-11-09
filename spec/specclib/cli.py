"""std-uritemplate spec compiler.

Commands:
  parse            show the functions and targets declared in the spec
  build --target X generate target X from the spec with --backend, gate it on the conformance suite, write the lock
  check            verify generated files match the spec and the lock (no LLM call)
  tck --target X   run the conformance suite through <harness>/test.sh (reentrant, parallel)

Exit codes: 0 ok, 1 verdict failed (check problems, conformance failures, build gave up), 2 cannot run.
"""
import argparse
import os
import sys

from .build import build
from .check import verify
from .conformance import format_failures, run_tck
from .lock import load_lock
from .project import Project, SpecError
from .spec import load_spec


def cmd_parse(project, args):
    spec = load_spec(project)
    print("spec sha256: %s" % spec.sha)
    print("\ntypes (%d):" % len(spec.types))
    for name, _ in spec.types:
        print("  %s" % name)
    print("\nfunctions (%d):" % len(spec.fns))
    for name, sig, _ in spec.fns:
        print("  %s" % sig)
    print("\ntargets (%d):" % len(spec.targets))
    for name, t in spec.targets.items():
        m = t["meta"]
        print("  %-8s generated=%-5s file=%s" % (name, m["generated"], m["file"]))
    return 0


def cmd_tck(project, args):
    spec = load_spec(project)
    if args.target not in spec.targets:
        raise SpecError("unknown target %s" % args.target)
    meta = spec.targets[args.target]["meta"]
    total, failures = run_tck(project, meta["harness"], jobs=args.jobs)
    print("%s: %d/%d conformance cases passed" % (args.target, total - len(failures), total))
    if failures:
        print(format_failures(failures, limit=args.limit))
        return 1
    return 0


def cmd_build(project, args):
    return build(project, load_spec(project), args)


def cmd_check(project, args):
    spec = load_spec(project)
    problems = verify(project, spec, load_lock(project))
    if problems:
        print("check: FAILED")
        for p in problems:
            print("  - " + p)
        return 1
    n = sum(1 for t in spec.targets.values() if t["meta"]["generated"])
    print("check: OK (%d generated target(s) match the spec and the lock)" % n)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="specc.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", help="path to the <name>.spec.md file (default: the one next to the tool directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("parse").set_defaults(fn=cmd_parse)
    b = sub.add_parser("build")
    b.add_argument("--target", required=True)
    b.add_argument("--backend", default=os.environ.get("SPECC_BACKEND"),
                   help="shell command that reads the user prompt on stdin, the system prompt from "
                        "$SPECC_SYSTEM_PROMPT and $SPECC_MODEL, and prints the answer (default: $SPECC_BACKEND)")
    b.add_argument("--model", default=os.environ.get("SPECC_MODEL"), help="passed to the backend as $SPECC_MODEL")
    b.add_argument("--max-attempts", type=int, default=2)
    b.add_argument("--jobs", type=int, default=8)
    b.add_argument("--force", action="store_true")
    b.add_argument("--verbose", action="store_true")
    b.set_defaults(fn=cmd_build)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    t = sub.add_parser("tck")
    t.add_argument("--target", required=True)
    t.add_argument("--jobs", type=int, default=8)
    t.add_argument("--limit", type=int, default=12)
    t.set_defaults(fn=cmd_tck)
    args = ap.parse_args(argv)
    if args.cmd == "build" and not args.backend:
        ap.error("build needs --backend or $SPECC_BACKEND, e.g. --backend spec/backends/openai_sdk.py")
    try:
        return args.fn(Project(args.spec), args)
    except SpecError as e:
        print("specc: %s" % e, file=sys.stderr)
        return 2
