import datetime
import os
import subprocess

from .project import SpecError


def generate(project, system_prompt, user_prompt, backend, model, verbose=False):
    """Run the backend: system prompt in $SPECC_SYSTEM_PROMPT, user prompt on stdin, answer on stdout."""
    env = dict(os.environ, SPECC_SYSTEM_PROMPT=system_prompt, SPECC_MODEL=model or "")
    if verbose:
        print("  calling: %s (prompt %d chars)" % (backend, len(user_prompt)))
    started = datetime.datetime.now()
    proc = subprocess.run(backend, shell=True, input=user_prompt, capture_output=True, text=True, cwd=project.root, env=env)
    if proc.returncode != 0:
        raise SpecError("backend failed (%d):\n%s" % (proc.returncode, proc.stderr[-2000:]))
    duration_ms = int((datetime.datetime.now() - started).total_seconds() * 1000)
    return proc.stdout, duration_ms
