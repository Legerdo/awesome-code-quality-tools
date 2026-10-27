"""Positive and negative fixtures for the catalog policy, not third-party analyzers."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.data, self.evidence, self.policy = catalog.load()

    def tool(self, ident):
        return next(t for t in self.data["tools"] if t["id"] == ident)

    def errors(self):
        return catalog.validate(self.data, self.evidence, self.policy)

    def assert_rejected(self, text):
        self.assertTrue(any(text in error for error in self.errors()), self.errors())

    def test_current_catalog_is_valid(self):
        self.assertEqual([], self.errors())

    def test_duplicate_tool_id_rejected(self):
        self.data["tools"].append(copy.deepcopy(self.data["tools"][0]))
        self.assert_rejected("duplicate tool id")

    def test_gpl_cannot_enter_permissive_catalog(self):
        self.tool("serena")["status"] = "permissive"
        self.assert_rejected("non-permissive license")

    def test_unlisted_engine_exception_rejected(self):
        self.tool("serena")["status"] = "engine-exception"
        self.assert_rejected("unapproved engine exception")

    def test_excluded_tool_cannot_enter_profile(self):
        self.data["profiles"][0]["optional"].append("serena")
        self.assert_rejected("excluded tool in profile")

    def test_unknown_profile_reference_rejected(self):
        self.data["profiles"][0]["base"].append("not-a-tool")
        self.assert_rejected("unknown profile tool")

    def test_gdscript_not_claimed_for_codegraph(self):
        next(p for p in self.data["profiles"] if p["id"] == "godot")["navigation"] = ["codegraph"]
        self.assert_rejected("language mismatch")

    def test_missing_license_evidence_rejected(self):
        self.evidence = [e for e in self.evidence if e["id"] != "codegraph"]
        self.assert_rejected("missing repository license evidence")

    def test_false_execution_claim_rejected(self):
        self.data["verification"]["tools_executed"] = True
        self.assert_rejected("unsupported verification claim")

    def test_license_evidence_mismatch_rejected(self):
        self.tool("codegraph")["license"] = "BSD-3-Clause"
        self.assert_rejected("license evidence mismatch")

    def test_ambiguous_detection_needs_manual_note(self):
        entry = next(e for e in self.evidence if e["id"] == "lizard")
        entry.pop("review_note", None)
        self.assert_rejected("manual license note required")

    def test_insecure_source_url_rejected(self):
        self.tool("codegraph")["sources"] = ["http://example.com"]
        self.assert_rejected("invalid source URL")

    def test_excluded_tools_are_not_in_readme(self):
        readme = catalog.render(self.data, self.evidence)["README.md"]
        self.assertNotIn("[Serena]", readme)
        self.assertNotIn("[GitNexus]", readme)
        self.assertIn("[CodeGraph]", readme)

    def test_generated_files_are_current(self):
        for name, expected in catalog.render(self.data, self.evidence).items():
            with self.subTest(name=name):
                self.assertEqual(expected, (catalog.ROOT / name).read_text(encoding="utf-8"))

    def test_internal_links_exist(self):
        self.assertEqual([], catalog.check_internal_links(catalog.ROOT))

    def test_broken_link_and_anchor_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("[a](missing.md) [b](README.md#absent)", encoding="utf-8")
            errors = catalog.check_internal_links(root)
            self.assertEqual(2, len(errors))

    def test_markdown_table_pipe_escaped(self):
        self.assertIn(r"a\|b", catalog.table(["x"], [["a|b"]]))


if __name__ == "__main__":
    unittest.main()
