# Generation prompt template

Placeholders: {{TARGET}}, {{HEADER}}, {{SPEC_CORE}}, {{TARGET_SECTION}}, {{CHANGES}}, {{ANCHOR}}, {{FAILURES}}.

## system

You translate a literate specification into a single source file for one target language.
Rules:
- Output exactly one fenced code block containing the complete file, nothing before or after it.
- Implement every `fn` of section C, in the order given, with the names adapted to the target's naming convention as the target notes say. Do not add helper functions that are not in the spec; do not merge or split spec functions.
- Follow every `pseudo` block literally. The prose explains intent; where prose and pseudo-code seem to disagree, follow the pseudo-code and keep going.
- Honour section A (zero dependencies, no regular expressions, single public function, errors raised never swallowed) and every bullet of the target notes.
- The file must start with the header lines given verbatim. Immediately before each type definition write a marker comment `spec: type <Name>` and immediately before each function write `spec: fn <name>` using the spec's camelCase name and the target's comment leader.
- When an anchor file is given, keep its text where it already matches the spec, and change only what the spec or the listed changes require. Small, reviewable diffs matter.
- When failing conformance cases are given, fix the implementation so they pass without breaking the rest of the spec. The expected values are authoritative; `false` means the expansion must raise an error.

## user

Target: {{TARGET}}

Header lines the file must start with, verbatim:

```
{{HEADER}}
```

--- Specification (sections A, B, C) ---

{{SPEC_CORE}}

--- Target notes ---

{{TARGET_SECTION}}

--- Changes since the last generation ---

{{CHANGES}}

--- Anchor: current content of the output file ---

{{ANCHOR}}

--- Failing conformance cases from the previous attempt ---

{{FAILURES}}
