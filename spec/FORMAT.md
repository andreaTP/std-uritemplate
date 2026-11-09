# specc spec format, version 1

This document defines what `spec/specc.py` reads and writes, so that a spec for another
library can be written and driven by the same tool. The tool has no knowledge of
std-uritemplate; everything it needs is declared in the spec file.

## Scope

- One spec file, `<name>.spec.md`, at the root of the project. The tool's default is the
  single `*.spec.md` in the directory above `spec/`; `--spec PATH` overrides it.
- A sibling lock file, `<name>.lock.json`, written by `build` and `relock`, read by `check`.
- The tool directory, `spec/`, holds the entry point, `specclib/`, `prompts/generate.md`,
  `backends/` and `tests/`. Paths in the spec are relative to the project root.

## Document structure

A free preamble, then exactly five level-two sections whose heading starts with a letter
and a dot, in order:

| Section | Heading starts with | What the tool does with it |
|---|---|---|
| A | `## A.` | sent to the model; hashed as one chunk, `section A` |
| B | `## B.` | sent; each `### type X` is a chunk `type X`; the intro and the other `###` subsections are one chunk `section B` |
| C | `## C.` | sent; every `###` must be `### fn ...`; each is a chunk `fn x`, in this order |
| D | `## D.` | every `###` must be `### target lang`; one target is sent to the model per build |
| E | `## E.` | not sent; holds the `conformance` block and the project's decisions |

Section titles after the letter are free. Anything before `## A.` is ignored by the tool.

## Heading grammar

- `### type Name`: a data type the generated file must define, marked `spec: type Name`.
- `### fn name(params) -> ret`: a function. The name is the text up to the first `(`; it
  must be unique; the rest of the signature is free-form and only informs the model.
- `### target lang`: `lang` is the value of `--target` and the key in the lock.

## Fenced blocks

`pseudo` (inside a `### fn`): the algorithm. Opaque to the tool, verbatim to the model,
part of the chunk hash.

`target` (first thing inside a `### target`, exactly one): `key: value` lines.

| Key | Required | Meaning |
|---|---|---|
| `file` | yes | the generated file, relative to the root |
| `harness` | yes | directory holding `init.sh` and `test.sh` (see Harness contract) |
| `generated` | yes | `true` or `false`; `false` targets are documented but not built or checked |
| `comment` | yes | the line-comment leader used for the header and the markers |
| `forbid` | no, repeatable | the generated file must have no line starting with this text (after trimming) |

Values may be double-quoted to keep leading or trailing spaces (`forbid: "from re "`).
The lines after the block are the target notes: prose for the model, sent verbatim.

`conformance` (in section E, exactly one): repeatable `fixtures:` lines naming fixture
files, relative to the root, glob patterns allowed, at least one.

## Chunks, normalisation and hashes

A chunk's hash is the SHA-256 of its text after `normalize`: strip the whole text, then
strip trailing whitespace from every line. Indentation inside `pseudo` matters; trailing
spaces and surrounding blank lines do not. The lock records, per target:

| Field | Covers | A change means |
|---|---|---|
| `chunk_hashes` | `section A`, `section B`, every `type`, every `fn` | `build` regenerates with the changed keys listed in the prompt |
| `target_notes_sha256` | `### target` heading plus notes (not the `target` block) | regeneration |
| `prompt_template_sha256` | `spec/prompts/generate.md` | regeneration |
| `spec_sha256` (top level) | the whole file | only the header line changes: `build` refreshes it without a model call |

Editing a `target` block or the `conformance` block changes nothing the model sees, so
`build` refreshes headers only; `check` keeps passing after a `relock`.

## Generated file contract

The file starts with three header lines, built from the target's comment leader `c`:

```
c GENERATED FILE - DO NOT EDIT.
c Source: <name>.spec.md (sha256 <first 12 hex of spec_sha256>)
c Regenerate: python3 spec/specc.py build --target <lang>
```

Immediately before each type definition there is a line `c spec: type Name`, immediately
before each function `c spec: fn name`, with the spec's name as written. `check` requires
every marker exactly once, the `fn` markers in spec order (types may sit where the
language's idiom wants them), no forbidden line, and the file's SHA-256 equal to the
lock's `output_sha256`.

## Lock schema

```json
{
  "spec_sha256": "...",
  "targets": {
    "<lang>": {
      "file": "...",
      "output_sha256": "...",
      "chunk_hashes": {"section A": "...", "section B": "...", "type X": "...", "fn x": "..."},
      "target_notes_sha256": "...",
      "prompt_template_sha256": "...",
      "backend": {"command": "...", "model": "..."},
      "tck": {"cases": 446, "result": "pass", "verified_at": "..."},
      "attempts": 1,
      "duration_ms": 12345,
      "generated_at": "2026-11-06T15:21:29Z"
    }
  }
}
```

`check` compares `spec_sha256`, `output_sha256` and `chunk_hashes`; `build` also compares
`target_notes_sha256` and `prompt_template_sha256` to decide whether to regenerate. The
rest is provenance. `tck.verified_at` is set by `relock`; `cost_usd` may appear in old
entries. Fields are additive: unknown keys are kept.

## Backend contract

`build` runs the `--backend` (or `$SPECC_BACKEND`) command through the shell, with the
project root as working directory:

- the user prompt on standard input;
- the system prompt in `$SPECC_SYSTEM_PROMPT`;
- the `--model` (or `$SPECC_MODEL`) value in `$SPECC_MODEL`, possibly empty;
- the answer on standard output: one fenced code block, or raw code. The tool takes the
  text between the first two lines starting with three backticks; with no fence it takes
  everything. If the answer lacks the header lines, the tool prepends them.
- a non-zero exit code aborts the build (exit code 2) with the command's stderr.

`spec/backends/openai_sdk.py` is the stock backend; `spec/backends/replay.sh FILE`
answers with the content of FILE, to exercise the pipeline without a model.
`build --dry-run` prints both prompts and stops, which is the first thing to try when
wiring a new backend.

## Harness contract

For a target with `harness: dir`:

- `dir/init.sh`, run with `bash` once per attempt, builds whatever the target needs.
  Non-zero exit is reported as a build failure and fed back to the model.
- `dir/test.sh TEMPLATE_FILE SUBSTITUTIONS_FILE`, executable, prints the expansion of the
  template in the first file with the JSON object in the second, or the word `false` when
  the expansion must fail. Only standard output is compared, after trailing newlines are
  removed. It must be safe to run many instances in parallel; the tool gives each case its
  own temporary files.

Fixture files are JSON objects: each key is a group with `variables` (an object) and
`testcases`, a list of `[template, expected]` pairs. `expected` is a string, a list of
acceptable strings, or `false`.

## Prompt template

`spec/prompts/generate.md` has a `## system` part and a `## user` part. The user part is
rendered with `{{TARGET}}`, `{{HEADER}}`, `{{SPEC_CORE}}` (sections A, B, C), `{{TARGET_SECTION}}`
(the target heading and notes), `{{CHANGES}}` (the chunk keys that changed since the last
build), `{{ANCHOR}}` (the current content of the output file) and `{{FAILURES}}` (the
failing cases of the previous attempt).

## Writing a spec for another library

1. Write the five sections. Keep section A short and absolute; put every algorithmic
   decision in a `pseudo` block; keep prose for intent.
2. Write the fixtures and the `conformance` block, then a harness per target: `init.sh`,
   `test.sh` and whatever wrapper turns two files into one line of output.
3. Write one `### target` section per language: the `target` block, then notes about
   naming, errors, the standard-library calls that are allowed, and how the harness's
   native values map to the spec's types.
4. `python3 spec/specc.py --spec my.spec.md parse`, then `build --target X --dry-run` to
   read the prompt, then `build` with a backend. Commit the spec, the output and the lock
   together.

## Commands and exit codes

| Command | Model call | Writes |
|---|---|---|
| `parse [--json]` | no | nothing |
| `check [--tck [--target X]]` | no | nothing |
| `tck --target X` | no | nothing |
| `build --target X [--force] [--dry-run]` | yes (not with `--dry-run`) | the output file and the lock |
| `relock --target X` | no | the header line and the lock |

Exit codes: 0 success; 1 a verdict failed (check problems, conformance failures, build gave
up, relock refused); 2 the tool could not run (usage, unreadable spec, backend error,
missing fixtures).
