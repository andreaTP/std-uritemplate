# Spec-driven implementations (prototype)

`std-uritemplate.spec.md` is the only hand-edited source for targets marked
`generated: true`. The implementations are derived from it, committed, and pinned.
This directory holds the tool that does it.

## The model

Three layers, all required, each cheap to check:

1. **Behavioural.** A generated file is accepted only if the whole conformance
   suite passes through the target's own `<harness>/test.sh`. The fixtures are the
   type checker.
2. **Structural.** The spec declares the function set. Every generated file
   carries one `spec: fn <name>` marker per function and a header naming the spec
   hash. `check` verifies both without any model call.
3. **Reproducibility by pinning.** `std-uritemplate.lock.json` records the spec
   hash, per-chunk hashes, the target notes hash, the prompt template hash, the
   backend and model, and the output hash. Generation is an explicit developer
   action; CI only ever runs `check` and the conformance suite. Bitwise
   reproduction across model versions is not a goal, the same way nobody expects
   it across compiler versions.

## Commands

```
python3 spec/specc.py parse                 # list types, functions, targets
python3 spec/specc.py tck --target python   # conformance suite, parallel, private scratch files
python3 spec/specc.py build --target python # regenerate if the spec changed, gate, update lock
python3 spec/specc.py check                 # no LLM: headers, hashes, markers, forbidden imports
```

`build` uses the `claude` CLI (`claude -p`) as the generation backend, so it needs
an authenticated Claude Code install and nothing else. `--model` pins the model
(default `claude-opus-5-5`), `--max-attempts` bounds the fix-up loop,
`--force` regenerates even when nothing changed.

`tck` exists because `tests/test.sh` keeps its scratch files in `tests/` and is not
reentrant; the tool writes to a private temp dir and runs cases in parallel.
`tests/test.sh <lang>` stays the official gate.

## Fixing a bug

Never edit a generated file. The loop is:

1. Add a failing case to `uritemplate-test-additional/edge-cases.json`. That is
   the bug report, and it is language independent.
2. Run the suite. If generated targets disagree with each other, the spec was
   ambiguous: fix the prose or the `pseudo` block in section C. If the spec was
   clear and one target deviated, add a bullet to that target's notes in section D.
3. `python3 spec/specc.py build --target <lang>` for each affected target. Only
   targets whose chunk hashes changed regenerate; the current file is passed as an
   anchor so the diff stays small.
4. Review the diff, then commit the spec, the fixture, the outputs and the lock
   together.

The escape hatch is always in the spec (section D notes), never in the output.
`check` fails on a hand-edited file, so the rule enforces itself.

## Adding a generated target

Add a `### target <lang>` section with a `target` block (`file`, `harness`,
`generated: true`, `comment`) and idiom notes, write the harness glue
(`<lang>/init.sh`, `<lang>/test.sh` following `Contributing.md`), then `build`.
