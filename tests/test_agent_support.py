"""Fixtures for read-only lookup and repository skill files; no model calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog
import check_skills
import query_catalog


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.data, self.evidence, _ = catalog.load()

    def test_all_profile_ids_available(self):
        result = query_catalog.query(self.data, self.evidence, list_profiles=True)
        self.assertEqual([p["id"] for p in self.data["profiles"]],
                         [p["id"] for p in result["profiles"]])
        self.assertFalse(result["verification"]["tools_executed"])

    def test_web_profile_keeps_both_tools_and_evidence(self):
        result = query_catalog.query(self.data, self.evidence, profile="typescript-web")
        roles = result["tools_by_role"]
        self.assertIn("knip", [t["id"] for t in roles["base"]])
        fallow = next(t for t in roles["optional"] if t["id"] == "fallow")
        self.assertEqual("MIT", fallow["license"])
        self.assertEqual("fallow-rs/fallow", fallow["license_evidence"]["repository"])
        self.assertEqual(["fallow"], result["profile"]["featured_optional"])
        self.assertTrue(all(t["status"] != "excluded" for group in roles.values() for t in group))

    def test_excluded_tool_is_not_disguised_as_recommendation(self):
        result = query_catalog.query(self.data, self.evidence, tool="gitnexus")
        self.assertEqual("excluded", result["tool"]["status"])

    def test_engine_exception_stays_visible(self):
        result = query_catalog.query(self.data, self.evidence, profile="unreal-cpp")
        self.assertTrue(any(t["status"] == "engine-exception" for t in result["tools_by_role"]["base"]))

    def test_unknown_selection_and_multiple_modes_rejected(self):
        for kwargs in ({"profile": "missing"}, {"tool": "missing"},
                       {"tool": "fallow", "list_profiles": True}, {}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query_catalog.query(self.data, self.evidence, **kwargs)

    def test_query_result_cannot_mutate_source(self):
        before = copy.deepcopy((self.data, self.evidence))
        result = query_catalog.query(self.data, self.evidence, profile="typescript-web")
        result["profile"]["base"].clear()
        result["tools_by_role"]["base"][0]["languages"].clear()
        self.assertEqual(before, (self.data, self.evidence))

    def test_cli_works_outside_repository_and_returns_utf8_json(self):
        script = catalog.ROOT / "scripts" / "query_catalog.py"
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(script), "--profile", "godot"],
                                    cwd=temp, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("godot", json.loads(result.stdout)["profile"]["id"])

    def test_cli_unknown_tool_is_nonzero_with_no_json(self):
        result = subprocess.run([sys.executable, str(catalog.ROOT / "scripts" / "query_catalog.py"),
                                 "--tool", "missing"], capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("Unknown tool", result.stderr)


class SkillTests(unittest.TestCase):
    def test_current_agent_files(self):
        self.assertEqual([], check_skills.check())

    def validate_text(self, text, name="example-skill"):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / name / "SKILL.md"
            path.parent.mkdir()
            path.write_text(text, encoding="utf-8")
            return check_skills.validate_skill(path)

    def test_valid_minimal_header(self):
        self.assertEqual([], self.validate_text(
            '---\nname: example-skill\ndescription: Read the catalog.\nlicense: MIT\n---\n# Read\n'))

    def test_missing_or_unclosed_header(self):
        for text in ("# No header\n", "---\nname: example-skill\n"):
            self.assertTrue(self.validate_text(text))

    def test_invalid_names_rejected(self):
        for name in ("Wrong-Name", "-start", "double--dash", "other-name", "x" * 65):
            self.assertTrue(self.validate_text(
                f"---\nname: {name}\ndescription: Test.\nlicense: MIT\n---\n# Body\n"))

    def test_description_and_license_required(self):
        for fields in ("name: example-skill\nlicense: MIT", "name: example-skill\ndescription: Test.",
                       "name: example-skill\ndescription: Test.\nlicense: Proprietary"):
            self.assertTrue(self.validate_text(f"---\n{fields}\n---\n# Body\n"))

    def test_unsupported_and_duplicate_fields_rejected(self):
        base = "name: example-skill\ndescription: Test.\nlicense: MIT\n"
        for extra in ("name: example-skill\n", "allowed-tools: all\n", "description: |\n"):
            self.assertTrue(self.validate_text(f"---\n{base}{extra}---\n# Body\n"))

    def test_missing_agent_documents_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            errors = check_skills.check(Path(temp))
            self.assertTrue(any("missing agent document" in e for e in errors))
            self.assertIn("no repository skills found", errors)

    def test_markdown_fences_are_paired(self):
        for path in catalog.ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            fences = [line for line in path.read_text(encoding="utf-8").splitlines()
                      if line.startswith("```")]
            with self.subTest(path=path.relative_to(catalog.ROOT)):
                self.assertEqual(0, len(fences) % 2)


if __name__ == "__main__":
    unittest.main()
