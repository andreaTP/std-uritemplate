import hashlib
import os

from .project import SpecError


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text):
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


class Spec:
    def __init__(self, text):
        self.text = text
        self.sha = sha256(text)
        self.sections = {}  # "A".."E" -> text (including heading)
        self.types = []  # [(name, text)]
        self.fns = []  # [(name, signature, text)]
        self.targets = {}  # name -> {"meta": {...}, "notes": text, "section": text}
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
            meta, notes = self._parse_target(body, name)
            self.targets[name] = {"meta": meta, "notes": notes, "section": body}

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
    def _parse_target(body, name):
        meta = {}
        notes = []
        in_block = False
        for line in body.splitlines()[1:]:
            if line.strip() == "```target":
                in_block = True
                continue
            if in_block and line.strip() == "```":
                in_block = False
                continue
            if in_block:
                k, _, v = line.partition(":")
                v = v.strip().strip('"')
                meta[k.strip()] = {"true": True, "false": False}.get(v, v)
            else:
                notes.append(line)
        for k in ("file", "harness", "generated", "comment"):
            if k not in meta:
                raise SpecError("spec: target %s is missing '%s'" % (name, k))
        return meta, "\n".join(notes).strip()

    def chunk_hashes(self):
        hashes = {"type " + n: sha256(normalize(t)) for n, t in self.types}
        hashes.update({"fn " + n: sha256(normalize(t)) for n, _, t in self.fns})
        hashes["section A"] = sha256(normalize(self.sections["A"]))
        return hashes

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
