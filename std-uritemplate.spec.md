# std-uritemplate specification

This file is the single source of truth for every std-uritemplate implementation.
It is a literate specification: prose explains intent, `pseudo` blocks define the
algorithm, `target` sections carry the language-specific knowledge, and the
conformance fixtures decide what is correct. Implementations marked
`generated: true` are produced from this file by `spec/specc.py` and must not be
edited by hand: fix the spec, add a fixture, regenerate.

The library implements RFC 6570 (URI Template) Level 4 expansion.

## A. Design constraints

These apply to every target and the generator must honour them.

- Zero dependencies: only the language's standard library.
- No regular expressions, anywhere.
- No options, no configuration, no builder: one public function
  `expand(template, substitutions) -> string`.
- Substitution values are: `null`/absent, strings, booleans, integers, floating
  point numbers, lists of those primitives, maps from string to those primitives.
  Anything else is an error. Nested lists or maps are an error.
- Invalid templates and invalid values raise the target's conventional
  invalid-argument error. Nothing is silently skipped. Error messages are not part
  of the contract but should include the 0-based column where known.
- Portable and readable first: the same function set, in the same order, with the
  same control flow in every target. Performance only matters until it hurts
  readability.
- Strings are processed as sequences of Unicode code points, never UTF-16 code
  units or bytes, except when percent-encoding, where the UTF-8 bytes of a code
  point are emitted as uppercase `%XX` triplets.

## B. Data model

### type Operator

The expression operator, decided by the first character after `{`. `NO_OP` is
simple string expansion (`{var}`).

| Operator        | Char |
|-----------------|------|
| `NO_OP`         | none |
| `PLUS`          | `+`  |
| `HASH`          | `#`  |
| `DOT`           | `.`  |
| `SLASH`         | `/`  |
| `SEMICOLON`     | `;`  |
| `QUESTION_MARK` | `?`  |
| `AMP`           | `&`  |

### type SubstitutionType

| Value    | Meaning                                  |
|----------|------------------------------------------|
| `EMPTY`  | variable absent or `null`                |
| `STRING` | a primitive (string, boolean, number)    |
| `LIST`   | a list of primitives                     |
| `MAP`    | a map from string to primitives          |

### Operator table

From RFC 6570 Appendix A. `first` is emitted before the first expanded variable of
an expression, `sep` between variables and between exploded items, `named` means
the variable name is emitted as `name=value`, `ifemp` is what follows the name when
the value is the empty string, `allow` is the set of characters left unencoded
(`U` = unreserved only, `U+R` = unreserved and reserved).

| Operator        | first | sep | named | ifemp | allow |
|-----------------|-------|-----|-------|-------|-------|
| `NO_OP`         | ``    | `,` | false | ``    | U     |
| `PLUS`          | ``    | `,` | false | ``    | U+R   |
| `HASH`          | `#`   | `,` | false | ``    | U+R   |
| `DOT`           | `.`   | `.` | false | ``    | U     |
| `SLASH`         | `/`   | `/` | false | ``    | U     |
| `SEMICOLON`     | `;`   | `;` | true  | ``    | U     |
| `QUESTION_MARK` | `?`   | `&` | true  | `=`   | U     |
| `AMP`           | `&`   | `&` | true  | `=`   | U     |

### Character classes

- unreserved: `ALPHA / DIGIT / "-" / "." / "_" / "~"`
- reserved: `":" / "/" / "?" / "#" / "[" / "]" / "@" / "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="`
- varchar (allowed in a variable name): `ALPHA / DIGIT / "_" / pct-encoded`, and
  `.` as a separator between varchars.

### Scanner state

`expandImpl` is a single left-to-right pass over the template with this state:

| Name            | Type            | Meaning                                                   |
|-----------------|-----------------|-----------------------------------------------------------|
| `result`        | string builder  | output                                                    |
| `token`         | string builder or `null` | `null` outside an expression; the variable name being read inside one |
| `operator`      | Operator or `null` | `null` until the first character of the expression decides it |
| `composite`     | bool            | `*` explode modifier seen for the current variable         |
| `maxCharBuffer` | string builder or `null` | `null` until `:` is seen, then the digits of the prefix length |
| `firstToken`    | bool            | no variable of the current expression has produced output yet |

## C. Algorithm

Every target defines exactly these functions, in this order, with these names
(adapted to the target's naming convention). Only `expand` is public.

### fn expand(template: string, substitutions: map<string, any>) -> string

The public entry point. It only delegates.

```pseudo
return expandImpl(template, substitutions)
```

### fn expandImpl(template: string, substitutions: map<string, any>) -> string

The scanner. Literal text outside `{...}` is copied verbatim except that code
points above `0x7F` are percent-encoded. A literal comma outside an expression is
ordinary literal text. Inside an expression, the first character selects the
operator, `,` ends a variable, `:` starts the prefix length, `*` marks explode, and
`}` ends the expression.

```pseudo
result = new string builder
token = null
operator = null
composite = false
maxCharBuffer = null
firstToken = true

for i, c in codePointsWithIndex(template):
  if c == '{':
    if token != null: raise error("Nested expression at col:" + i)
    token = new string builder
    firstToken = true
  elif c == '}':
    if token == null: raise error("Unexpected '}' at col:" + i)
    if maxCharBuffer != null and length(maxCharBuffer) == 0:
      raise error("Empty prefix modifier at col:" + i)
    expanded = expandToken(operator, toString(token), composite, getMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i)
    if expanded and firstToken: firstToken = false
    token = null
    operator = null
    composite = false
    maxCharBuffer = null
  elif c == ',' and token != null:
    if maxCharBuffer != null and length(maxCharBuffer) == 0:
      raise error("Empty prefix modifier at col:" + i)
    expanded = expandToken(operator, toString(token), composite, getMaxChar(maxCharBuffer, i), firstToken, substitutions, result, i)
    if expanded and firstToken: firstToken = false
    token = new string builder
    composite = false
    maxCharBuffer = null
  elif token != null:
    if operator == null:
      operator = getOperator(c, token, i)
    elif maxCharBuffer != null:
      if isDigit(c): append(maxCharBuffer, c)
      else: raise error("Illegal character in prefix modifier at col:" + i)
    elif c == ':':
      maxCharBuffer = new string builder
    elif c == '*':
      composite = true
    else:
      validateVarchar(c, i)
      append(token, c)
  else:
    if c > 0x7F: pctEncode(c, result)
    else: append(result, c)

if token != null: raise error("Unterminated expression")
return toString(result)
```

### fn getOperator(c: codepoint, token: string builder, col: int) -> Operator

Called for the first character of an expression. An operator character selects the
operator; anything else is the first character of the variable name, so it is
validated and appended to `token`, and the operator is `NO_OP`.

```pseudo
if c == '+': return PLUS
if c == '#': return HASH
if c == '.': return DOT
if c == '/': return SLASH
if c == ';': return SEMICOLON
if c == '?': return QUESTION_MARK
if c == '&': return AMP
validateVarchar(c, col)
append(token, c)
return NO_OP
```

### fn validateVarchar(c: codepoint, col: int) -> void

A character inside a variable name must be a varchar or a `.`. Percent-encoded
triplets are checked later by `checkVarname`, so `%` is accepted here.

```pseudo
if isAlpha(c) or isDigit(c) or c == '_' or c == '%' or c == '.': return
raise error("Illegal character in variable name at col:" + col)
```

### fn checkVarname(token: string, col: int) -> void

Dots may only separate varchars, and every `%` must start a valid triplet.

```pseudo
if startsWith(token, '.') or endsWith(token, '.'):
  raise error("Variable name cannot start or end with a dot at col:" + col)
if contains(token, ".."):
  raise error("Variable name cannot contain consecutive dots at col:" + col)
i = 0
while i < length(token):
  if token[i] == '%':
    if i + 2 >= length(token) or not isHexDigit(token[i+1]) or not isHexDigit(token[i+2]):
      raise error("Invalid percent-encoding in variable name at col:" + col)
    i = i + 3
  else:
    i = i + 1
```

### fn isHexDigit(c: codepoint) -> bool

```pseudo
return ('0' <= c <= '9') or ('A' <= c <= 'F') or ('a' <= c <= 'f')
```

### fn getMaxChar(buffer: string builder or null, col: int) -> int

The prefix length. `-1` means no prefix modifier. The value must be 1 to 9999 with
no leading zero.

```pseudo
if buffer == null or length(buffer) == 0: return -1
value = toString(buffer)
if value[0] == '0': raise error("Leading zero not allowed in prefix modifier at col:" + col)
n = parseDecimalInteger(value)   # only digits can be present, see expandImpl
if n < 1 or n > 9999: raise error("Prefix modifier out of range (1-9999) at col:" + col)
return n
```

### fn expandToken(operator: Operator, token: string, composite: bool, maxChar: int, firstToken: bool, substitutions: map<string, any>, result: string builder, col: int) -> bool

Expands one variable of an expression. Returns `true` when something was written
to `result`, so the caller can decide whether the next variable needs a separator.
A `null`/absent variable or an empty list/map produces nothing at all, not even a
separator.

```pseudo
if length(token) == 0: raise error("Empty variable name at col:" + col)
checkVarname(token, col)
value = lookup(substitutions, token)      # null when absent
substType = getSubstitutionType(value, col)
if substType == EMPTY or isEmpty(substType, value): return false

if firstToken: addPrefix(operator, result)
else: addSeparator(operator, result)

if substType == STRING: addStringValue(operator, token, value, result, maxChar)
elif substType == LIST: addListValue(operator, token, value, result, maxChar, composite)
elif substType == MAP: addMapValue(operator, token, value, result, maxChar, composite)
return true
```

### fn getSubstitutionType(value: any, col: int) -> SubstitutionType

```pseudo
if value == null: return EMPTY
if isNativeType(value): return STRING
if isList(value): return LIST
if isMap(value): return MAP
raise error("Illegal value type for substitution at col:" + col)
```

### fn isEmpty(substType: SubstitutionType, value: any) -> bool

An empty string is not empty: `{?empty}` yields `?empty=`.

```pseudo
if value == null: return true
if substType == STRING: return false
if substType == LIST: return length(value) == 0
if substType == MAP: return length(value) == 0
return true
```

### fn isNativeType(value: any) -> bool

A primitive: string, boolean, integer or floating point number.

```pseudo
return isString(value) or isBoolean(value) or isInteger(value) or isFloat(value)
```

### fn isList(value: any) -> bool

```pseudo
return value is the target's list / array type
```

### fn isMap(value: any) -> bool

```pseudo
return value is the target's string-keyed map / dictionary type
```

### fn convertNativeTypes(value: any) -> string

Booleans become `true` / `false` (lowercase). Integers become their decimal
representation. Floating point numbers use the target's default decimal
representation (not part of the conformance contract). Called for list elements
and map keys and values too, so a non-primitive element is an error here.

```pseudo
if isString(value): return value
if isBoolean(value): return value ? "true" : "false"
if isInteger(value) or isFloat(value): return decimalString(value)
raise error("Illegal value type for substitution")
```

### fn addPrefix(op: Operator, result: string builder) -> void

Emits the `first` column of the operator table.

```pseudo
if op == HASH: append(result, '#')
elif op == DOT: append(result, '.')
elif op == SLASH: append(result, '/')
elif op == SEMICOLON: append(result, ';')
elif op == QUESTION_MARK: append(result, '?')
elif op == AMP: append(result, '&')
# NO_OP and PLUS emit nothing
```

### fn addSeparator(op: Operator, result: string builder) -> void

Emits the `sep` column of the operator table.

```pseudo
if op == DOT: append(result, '.')
elif op == SLASH: append(result, '/')
elif op == SEMICOLON: append(result, ';')
elif op == QUESTION_MARK or op == AMP: append(result, '&')
else: append(result, ',')   # NO_OP, PLUS and HASH all separate with a comma
```

### fn addStringValue(op: Operator, token: string, value: any, result: string builder, maxChar: int) -> void

```pseudo
addValue(op, token, value, result, maxChar)
```

### fn addListValue(op: Operator, token: string, value: list, result: string builder, maxChar: int, composite: bool) -> void

Without explode the items are joined by `,` after a single name (for named
operators). With explode every item is a full `name=value` (named) or value,
joined by the operator separator. The prefix modifier applies to every item.

```pseudo
first = true
for v in value:
  if first:
    addValue(op, token, v, result, maxChar)
    first = false
  elif composite:
    addSeparator(op, result)
    addValue(op, token, v, result, maxChar)
  else:
    append(result, ',')
    addValueElement(op, token, v, result, maxChar)
```

### fn addMapValue(op: Operator, token: string, value: map, result: string builder, maxChar: int, composite: bool) -> void

Without explode: `name=k1,v1,k2,v2` (or `k1,v1,k2,v2` for unnamed operators).
With explode: `k1=v1<sep>k2=v2`, the variable name is not used. Keys are visited in
the map's iteration order. A prefix modifier on a map is an error.

```pseudo
if maxChar != -1: raise error("Prefix modifier is not allowed on map values")
first = true
for k, v in entries(value):
  if composite:
    if not first: addSeparator(op, result)
    addValueElement(op, token, k, result, maxChar)
    append(result, '=')
  else:
    if first: addValue(op, token, k, result, maxChar)
    else:
      append(result, ',')
      addValueElement(op, token, k, result, maxChar)
    append(result, ',')
  addValueElement(op, token, v, result, maxChar)
  first = false
```

### fn addValue(op: Operator, token: string, value: any, result: string builder, maxChar: int) -> void

Emits one value as the first item of a variable: for named operators this is where
the name and `=` are written. `SEMICOLON` omits `=` when the value is empty
(`ifemp` column), `QUESTION_MARK` and `AMP` always write it. `PLUS` and `HASH`
allow reserved characters through (`allow` column).

```pseudo
if op == PLUS or op == HASH:
  addExpandedValue(null, value, result, maxChar, false)
elif op == QUESTION_MARK or op == AMP:
  append(result, token); append(result, '=')
  addExpandedValue(null, value, result, maxChar, true)
elif op == SEMICOLON:
  append(result, token)
  addExpandedValue("=", value, result, maxChar, true)
else:  # NO_OP, DOT, SLASH
  addExpandedValue(null, value, result, maxChar, true)
```

### fn addValueElement(op: Operator, token: string, value: any, result: string builder, maxChar: int) -> void

Emits a value that is not the first item of its variable (a later list item, or a
map key/value): never writes the name.

```pseudo
if op == PLUS or op == HASH:
  addExpandedValue(null, value, result, maxChar, false)
else:
  addExpandedValue(null, value, result, maxChar, true)
```

### fn addExpandedValue(prefix: string or null, value: any, result: string builder, maxChar: int, replaceReserved: bool) -> void

Converts `value` to a string, truncates it to `maxChar` code points when `maxChar`
is not `-1`, writes `prefix` (if any, and only if something follows), then writes
each code point:

- unreserved characters are copied;
- when `replaceReserved` is `false` (operators `+` and `#`), reserved characters
  are copied too, and a `%` followed by two hex digits (within the truncated
  value) is copied as an existing percent-encoded triplet;
- everything else, including space, `%` not starting a triplet, and every code
  point above `0x7F`, is percent-encoded.

```pseudo
s = codePoints(convertNativeTypes(value))
max = length(s) if maxChar == -1 else min(maxChar, length(s))
if max > 0 and prefix != null: append(result, prefix)
i = 0
while i < max:
  c = s[i]
  if isUnreserved(c):
    append(result, c)
  elif not replaceReserved and isReserved(c):
    append(result, c)
  elif not replaceReserved and c == '%' and i + 2 < max and isHexDigit(s[i+1]) and isHexDigit(s[i+2]):
    append(result, c); append(result, s[i+1]); append(result, s[i+2])
    i = i + 2
  else:
    pctEncode(c, result)
  i = i + 1
```

### fn isUnreserved(c: codepoint) -> bool

```pseudo
return isAlpha(c) or isDigit(c) or c == '-' or c == '.' or c == '_' or c == '~'
```

### fn isReserved(c: codepoint) -> bool

```pseudo
return c in ":/?#[]@!$&'()*+,;="
```

### fn pctEncode(c: codepoint, result: string builder) -> void

Appends the UTF-8 encoding of `c` as uppercase `%XX` triplets.

```pseudo
for b in utf8Bytes(c): append(result, '%' + twoUppercaseHexDigits(b))
```

## D. Targets

Each target section starts with a `target` block of `key: value` lines read by the
tool, followed by idiom notes passed verbatim to the generator. Only ported
implementations are listed; a target is added here when it is generated from this
file.

### target python

```target
file: python/stduritemplate/__init__.py
harness: python
generated: true
comment: "#"
```

- Must run on Python 3.8+: use `typing.Any`, `Dict`, `List`; no `match`, no `X | Y`
  unions, no walrus-free-only features. Only `from typing import ...` and
  `from enum import Enum` imports; never `import re`, never `urllib`.
- Module layout, in this order: `_Operator(Enum)`, `_SubstitutionType(Enum)`, then
  `class StdUriTemplate` with one `@staticmethod` per spec function. The public
  method is `expand`; every other method is private with a double underscore
  (`__expand_impl`, `__get_operator`, ...). Call them as
  `StdUriTemplate.__name(...)` inside the class.
- Python `str` already iterates code points; `ord(c)`, `chr(n)` convert.
- `result` and other string builders are `List[str]` joined with `"".join(...)`
  when returned. The `null` builder state is `None`.
- `pctEncode`: iterate `c.encode("utf-8")` and append `"%{:02X}".format(b)`.
- Errors are `ValueError`.
- `isNativeType`: `isinstance(value, (str, bool, int, float))`. Note `bool` is a
  subclass of `int`, so test `bool` before `int` in `convertNativeTypes`.
- `isList`: `isinstance(value, list)`; `isMap`: `isinstance(value, dict)`.
- Map iteration order is insertion order, use it as-is.
- Type hints on every method; no docstrings needed; keep lines under 100 chars.

## E. Conformance

The contract is the fixture set, run by `tests/test.sh <lang>` and by
`spec/specc.py build` through each target's `<harness>/test.sh`:

- `uritemplate-test/spec-examples.json`
- `uritemplate-test/spec-examples-by-section.json`
- `uritemplate-test/extended-tests.json`
- `uritemplate-test/negative-tests.json`
- `uritemplate-test-additional/edge-cases.json`

Decisions this spec makes explicitly, with the fixture that pins each:

- A literal comma outside an expression is copied verbatim
  (`edge-cases.json`, "Commas outside expressions").
- Prefix length is 1-9999, no leading zero, no empty prefix (`negative-tests.json`:
  `{var:0}`, `{var:01}`, `{var:10000}`, `{var:}`).
- Variable names: varchar with single dots, valid percent triplets
  (`negative-tests.json`: `{x.}`, `{x..y}`, `{%2x}`, `{default-graph-uri}`;
  `extended-tests.json`: `{?Stra%C3%9Fe}`).
- Prefix length counts code points (`extended-tests.json`: `{clef:1}` with a
  non-BMP character).
- Non-ASCII literal text outside expressions is percent-encoded
  (`spec-examples-by-section.json`, 2.1 Literals).
- A `%` in a value is copied only when it starts a valid triplet and the operator
  allows reserved characters (`spec-examples-by-section.json`: `{+half}`,
  `{+not_pct}`, `{+id}` with `admin%2F`).

Known divergences between the spec and hand-written targets, to be resolved when
those targets become generated. None is covered by a fixture yet; the test cases
listed are candidates for `edge-cases.json`:

- `~` and `*` in values: the spec keeps `~` unencoded and encodes `*` as `%2A`
  (RFC unreserved set). Java's `URLEncoder` does the opposite.
  Candidate: `{var}` with `var = "a~b*c"` → `a~b%2Ac`.
- Reserved expansion of ASCII characters that are neither unreserved nor reserved
  (`"`, `<`, `>`, `\`, `^`, `` ` ``, `{`, `|`, `}`): the spec percent-encodes them;
  Java and Python copy them. Candidate: `{+var}` with `var = "a<b"` → `a%3Cb`.
- Reserved expansion of non-ASCII characters outside the RFC 3987 `ucschar` and
  `iprivate` ranges: the spec percent-encodes every code point above `0x7F`; Java
  copies those. Candidate: `{+var}` with `var = "\u0085"` → `%C2%85`.
- Variable names are an allow-list (RFC 6570 section 2.3); the hand-written ports
  use a deny-list and accept `{@v}`, `{v@}`, `{(v)}`, `{v[0]}`, `{v'}`, `{v\}`,
  `{é}`, and Java restarts the expression on a nested `{` (`{a{b}`). All of these
  → `false`. Not yet reported upstream.
- Unsupported value types: always an error (Go currently skips the variable).
