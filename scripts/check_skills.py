"""Check this repository's simple Agent Skills headers and agent entry points.

This is not a general YAML parser or a model-behavior evaluation. The repository
uses only single-line string fields from https://agentskills.io/specification.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FIELDS = {"name", "description", "license", "compatibility"}
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
MAX_SKILL_LINES = 500  # Local limit based on the specification's recommendation.
REQUIRED_DOCS = (
    "AGENTS.md", "CLAUDE.md", "docs/AGENT-GUIDE.md", "docs/WRITING.md",
    "docs/templates/QUALITY-CHECK.md",
)


def validate_skill(path: Path) -> list[str]:
    errors = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return [f"missing frontmatter: {path}"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return [f"unclosed frontmatter: {path}"]
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, raw = line.partition(":")
        if not separator or key not in ALLOWED_FIELDS or key in fields:
            errors.append(f"unsupported or duplicate header field: {path}: {key}")
            continue
        value = raw.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                errors.append(f"invalid quoted string: {path}: {key}")
                continue
        elif not value or value[0] in "'[{>&*!|" or ": " in value or " #" in value:
            errors.append(f"header must use a plain or JSON-quoted string: {path}: {key}")
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"empty or non-string field: {path}: {key}")
            continue
        fields[key] = value
    name = fields.get("name", "")
    if (not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or len(name) > MAX_NAME_LENGTH or name != path.parent.name):
        errors.append(f"invalid or mismatched skill name: {path}")
    if not 1 <= len(fields.get("description", "")) <= MAX_DESCRIPTION_LENGTH:
        errors.append(f"invalid skill description: {path}")
    if fields.get("license") != "MIT":
        errors.append(f"skill must declare the repository license: {path}")
    if "compatibility" in fields and len(fields["compatibility"]) > MAX_COMPATIBILITY_LENGTH:
        errors.append(f"compatibility too long: {path}")
    if len(lines) > MAX_SKILL_LINES:
        errors.append(f"skill exceeds local line limit: {path}")
    if not any(line.startswith("# ") for line in lines[end + 1:]):
        errors.append(f"missing skill instructions: {path}")
    return errors


def check(root: Path = ROOT) -> list[str]:
    errors = []
    for relative in REQUIRED_DOCS:
        if not (root / relative).is_file():
            errors.append(f"missing agent document: {relative}")
    skills = sorted((root / ".agents" / "skills").glob("*/SKILL.md"))
    if not skills:
        errors.append("no repository skills found")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8") if (root / "AGENTS.md").is_file() else ""
    for path in skills:
        errors.extend(validate_skill(path))
        if path.relative_to(root).as_posix() not in agents:
            errors.append(f"skill missing from AGENTS.md: {path.parent.name}")
    claude = root / "CLAUDE.md"
    if claude.is_file() and "@AGENTS.md" not in claude.read_text(encoding="utf-8").splitlines():
        errors.append("CLAUDE.md must import AGENTS.md")
    return errors


def main() -> int:
    try:
        errors = check()
        if errors:
            print("\n".join(f"FAIL: {error}" for error in errors), file=sys.stderr)
            return 1
        count = len(list((ROOT / ".agents" / "skills").glob("*/SKILL.md")))
        print(f"PASS: {count} skill headers and agent documents")
        print("Scope: file structure only; agent discovery and behavior were not tested.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
