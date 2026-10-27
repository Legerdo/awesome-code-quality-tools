"""Read catalog entries as JSON. Never install tools, run analyzers, or access the network."""
from __future__ import annotations

import argparse
import copy
import json
import sys

import catalog


def query(data: dict, evidence: list, *, profile: str | None = None,
          tool: str | None = None, list_profiles: bool = False) -> dict:
    """Return a self-contained selection without mutating the catalog."""
    if sum((profile is not None, tool is not None, list_profiles)) != 1:
        raise ValueError("Choose exactly one of --list-profiles, --profile, or --tool")
    result = {
        "repository": data["repository"],
        "reviewed_on": data["reviewed_on"],
        "source": "data/catalog.json",
        "verification": copy.deepcopy(data["verification"]),
        "scope": "catalog lookup only; no analyzers executed",
    }
    tools = {entry["id"]: entry for entry in data["tools"]}
    licenses = {entry["id"]: entry for entry in evidence}

    def entry(ident: str) -> dict:
        item = copy.deepcopy(tools[ident])
        item["license_evidence"] = copy.deepcopy(licenses.get(ident))
        return item

    if list_profiles:
        result["profiles"] = [
            {key: copy.deepcopy(p[key]) for key in ("id", "name", "languages")}
            for p in data["profiles"]
        ]
    elif tool is not None:
        if tool not in tools:
            raise ValueError(f"Unknown tool: {tool}")
        result["tool"] = entry(tool)
    else:
        selected = next((p for p in data["profiles"] if p["id"] == profile), None)
        if selected is None:
            raise ValueError(f"Unknown profile: {profile}")
        result["profile"] = copy.deepcopy(selected)
        result["tools_by_role"] = {
            role: [entry(ident) for ident in selected.get(role, [])]
            for role in ("base", "optional", "navigation")
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list-profiles", action="store_true", help="List available profile IDs")
    mode.add_argument("--profile", help="Return a profile with its tools and license evidence")
    mode.add_argument("--tool", help="Return one tool, including an excluded tool if requested")
    args = parser.parse_args(argv)
    try:
        data, evidence, policy = catalog.load()
        errors = catalog.validate(data, evidence, policy)
        if errors:
            raise ValueError("\n".join(errors))
        result = query(data, evidence, profile=args.profile, tool=args.tool,
                       list_profiles=args.list_profiles)
        # JSON stays readable when PowerShell pipes it to another process.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
