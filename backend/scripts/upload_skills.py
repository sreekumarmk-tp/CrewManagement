"""
Upload custom Agent Skills (authored under backend/skills/<name>/SKILL.md) to your
Anthropic workspace via the Skills API, and cache their IDs to backend/skills.json.

Run after creating/editing a SKILL.md:

    cd backend
    python -m scripts.upload_skills

Idempotent: if a skill is already in skills.json it creates a NEW VERSION;
otherwise it creates the skill. Afterwards run:

    python -m scripts.update_agent_skills

so the agents that reference the skill (see registry._CUSTOM_SKILLS_BY_AGENT)
pick up the latest version on their next session.

Prerequisites: ANTHROPIC_API_KEY set, on an org with Skills + Managed Agents beta.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic  # noqa: E402
from config import settings  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(BACKEND_DIR, "skills")
SKILLS_CACHE = os.path.join(BACKEND_DIR, "skills.json")
BETAS = ["skills-2025-10-02"]

# logical key (cache/registry name) -> (folder under skills/ — MUST match the
# `name:` in that folder's SKILL.md, human display title)
SKILLS = {
    "maritime_comms": ("maritime-comms-templates", "Maritime Comms Templates / Style Guide"),
}


def _content_type(filename: str) -> str:
    if filename.endswith(".md"):
        return "text/markdown"
    if filename.endswith(".txt"):
        return "text/plain"
    if filename.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _load_files(directory: str):
    """All files under the skill directory, named relative to the directory's
    PARENT so each path is `<skill-folder>/<file>` — the API requires SKILL.md to
    sit exactly in a single top-level folder."""
    parent = os.path.dirname(directory)
    files = []
    for root, _dirs, names in os.walk(directory):
        for n in names:
            path = os.path.join(root, n)
            rel = os.path.relpath(path, parent)  # e.g. "maritime_comms/SKILL.md"
            with open(path, "rb") as f:
                files.append((rel, f.read(), _content_type(n)))
    return files


def main() -> None:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    cache = {}
    if os.path.exists(SKILLS_CACHE):
        with open(SKILLS_CACHE) as f:
            cache = json.load(f)

    for key, (subdir, title) in SKILLS.items():
        directory = os.path.join(SKILLS_DIR, subdir)
        if not os.path.isdir(directory):
            print(f"skip {key}: {directory} not found")
            continue
        files = _load_files(directory)

        existing = cache.get(key, {}).get("skill_id")
        if existing:
            resp = client.beta.skills.versions.create(existing, files=files, betas=BETAS)
            cache[key] = {"skill_id": existing, "version": getattr(resp, "version", None)}
            print(f"updated {key}: skill_id={existing} version={cache[key]['version']}")
        else:
            resp = client.beta.skills.create(display_title=title, files=files, betas=BETAS)
            cache[key] = {"skill_id": resp.id, "version": getattr(resp, "latest_version", None)}
            print(f"created {key}: skill_id={resp.id} version={cache[key]['version']}")

    with open(SKILLS_CACHE, "w") as f:
        json.dump(cache, f, indent=2)

    print("\n✅ skills.json updated:")
    print(json.dumps(cache, indent=2))
    print("\nNext: python -m scripts.update_agent_skills  (applies the skill to its agents)")


if __name__ == "__main__":
    main()
