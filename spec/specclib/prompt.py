from .spec import header_lines


def load_prompt_template(project):
    with open(project.prompt_path, encoding="utf-8") as f:
        text = f.read()
    _, system_and_user = text.split("## system", 1)
    system, user = system_and_user.split("## user", 1)
    return text, system.strip(), user.strip()


def render_prompt(project, user_tpl, spec, target, meta, changes, anchor, failures):
    header = "\n".join(header_lines(project, spec, target, meta))
    repl = {
        "{{TARGET}}": target,
        "{{HEADER}}": header,
        "{{SPEC_CORE}}": spec.core_text(),
        "{{TARGET_SECTION}}": spec.targets[target]["section"],
        "{{CHANGES}}": changes,
        "{{ANCHOR}}": anchor,
        "{{FAILURES}}": failures,
    }
    out = user_tpl
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def extract_code_block(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("```"):
            if start is None:
                start = i
            else:
                return "\n".join(lines[start + 1:i]).rstrip() + "\n"
    return text.strip() + "\n"
