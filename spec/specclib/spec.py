import hashlib
import os

from .project import SpecError


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text):
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


REPEATABLE_KEYS = ("forbid", "fixtures")
TARGET_KEYS = ("file", "harness", "generated", "comment")


class Spec:
    def __init__(self, text):
        self.text = text
        self.sha = sha256(text)
        self.sections = {}  # "A".."E" -> text (including heading)
        self.types = []  # [(name, text)]
        self.fns = []  # [(name, signature, text)]
        self.targets = {}  # name -> {"meta": {...}, "notes": text, "prompt_section": text}
        self.conformance = {}  # the conformance block of section E
        self._parse()

    def _parse(self):
        current = None
        buf = []
        for line in self.text.splitlines():
            if line.startswith("## "):
                if current:
                    self.sections[current] = "\n".join(buf)
                current = line[3:4]
                buf = [line]
            elif current:
                buf.append(line)
        if current:
            self.sections[current] = "\n".join(buf)
        for key in "ABCDE":
            if key not in self.sections:
                raise SpecError("spec: missing section %s" % key)
        self.types = [(h[len("### type "):].strip(), body) for h, body in self._subsections("B") if h.startswith("### type ")]
        for h, body in self._subsections("C"):
            if not h.startswith("### fn "):
                raise SpecError("spec: unexpected heading in section C: %s" % h)
            sig = h[len("### fn "):].strip()
            name = sig.split("(", 1)[0]
            if any(n == name for n, _, _ in self.fns):
                raise SpecError("spec: duplicate fn %s" % name)
            self.fns.append((name, sig, body))
        for h, body in self._subsections("D"):
            if not h.startswith("### target "):
                raise SpecError("spec: unexpected heading in section D: %s" % h)
            name = h[len("### target "):].strip()
            meta, notes = self._parse_kv_block(body.splitlines()[1:], "target", "target %s" % name)
            for k in TARGET_KEYS:
                if k not in meta:
                    raise SpecError("spec: target %s is missing '%s'" % (name, k))
            notes = "\n".join(notes).strip()
            self.targets[name] = {"meta": meta, "notes": notes, "prompt_section": h + "\n\n" + notes}
        self.conformance, _ = self._parse_kv_block(self.sections["E"].splitlines(), "conformance", "section E")
        if not self.conformance.get("fixtures"):
            raise SpecError("spec: section E needs a conformance block with at least one 'fixtures:' line")

    def _subsections(self, key):
        out = []
        heading = None
        buf = []
        for line in self.sections[key].splitlines():
            if line.startswith("### "):
                if heading:
                    out.append((heading, "\n".join(buf)))
                heading = line
                buf = [line]
            elif heading:
                buf.append(line)
        if heading:
            out.append((heading, "\n".join(buf)))
        return out

    @staticmethod
    def _parse_kv_block(lines, fence, where):
        """Read the one ```<fence> block of key: value lines; returns (meta, the other lines)."""
        meta = {k: [] for k in REPEATABLE_KEYS}
        rest = []
        in_block = False
        seen = False
        for line in lines:
            if line.strip() == "```" + fence:
                if seen:
                    raise SpecError("spec: %s has more than one %s block" % (where, fence))
                in_block = seen = True
                continue
            if in_block and line.strip() == "```":
                in_block = False
                continue
            if not in_block:
                rest.append(line)
                continue
            k, sep, v = line.partition(":")
            if not sep or not k.strip():
                raise SpecError("spec: %s: not a key: value line in the %s block: %r" % (where, fence, line))
            k = k.strip()
            v = v.strip().strip('"')
            if k in REPEATABLE_KEYS:
                meta[k].append(v)
            else:
                meta[k] = {"true": True, "false": False}.get(v, v)
        if in_block:
            raise SpecError("spec: %s: unterminated %s block" % (where, fence))
        return meta, rest

    def chunk_hashes(self):
        hashes = {"type " + n: sha256(normalize(t)) for n, t in self.types}
        hashes.update({"fn " + n: sha256(normalize(t)) for n, _, t in self.fns})
        hashes["section A"] = sha256(normalize(self.sections["A"]))
        b_prose = [body for h, body in self._subsections("B") if not h.startswith("### type ")]
        hashes["section B"] = sha256(normalize("\n".join([self._intro("B")] + b_prose)))
        return hashes

    def _intro(self, key):
        lines = []
        for line in self.sections[key].splitlines():
            if line.startswith("### "):
                break
            lines.append(line)
        return "\n".join(lines)

    def core_text(self):
        return "\n\n".join(self.sections[k] for k in "ABC")


def load_spec(project):
    with open(project.spec_path, encoding="utf-8") as f:
        return Spec(f.read())


def header_lines(project, spec, target, meta):
    c = meta["comment"]
    return [
        "%s GENERATED FILE - DO NOT EDIT." % c,
        "%s Source: %s (sha256 %s)" % (c, os.path.basename(project.spec_path), spec.sha[:12]),
        "%s Regenerate: python3 %s build --target %s" % (c, project.tool_rel, target),
    ]
