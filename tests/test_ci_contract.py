import pathlib
import unittest
import yaml


class CIWorkflowContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root_dir = pathlib.Path(__file__).resolve().parent.parent
        self.workflow_path = self.root_dir / ".github" / "workflows" / "contract-tests.yml"

    def test_contract_tests_workflow_has_optimizations(self) -> None:
        self.assertTrue(self.workflow_path.exists())
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertIn("concurrency", data)
        self.assertTrue(data["concurrency"].get("cancel-in-progress"))

        push_triggers = data.get("on", {}).get("push", {})
        self.assertIn("paths-ignore", push_triggers)
        self.assertIn("presentation/**", push_triggers["paths-ignore"])

        steps = data["jobs"]["contract-tests"]["steps"]
        cache_steps = [s for s in steps if s.get("name") == "Cache Playwright Browsers"]
        self.assertEqual(len(cache_steps), 1)
        self.assertIn("actions/cache", cache_steps[0].get("uses", ""))


if __name__ == "__main__":
    unittest.main()
