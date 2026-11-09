import json
import os


def load_lock(project):
    if not os.path.exists(project.lock_path):
        return {"targets": {}}
    with open(project.lock_path, encoding="utf-8") as f:
        return json.load(f)


def save_lock(project, lock):
    with open(project.lock_path, "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")
