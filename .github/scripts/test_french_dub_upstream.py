import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "updater", Path(__file__).with_name("french-dub-upstream.py")
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

OLD = "a" * 40
NEW = "b" * 40
BASE = "c" * 40
HEAD = "d" * 40


class ReleaseUpdaterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "output"
        self.summary = Path(temporary.name) / "summary"
        env = patch.dict(os.environ, {
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "REVALIDATE": "false",
        })
        env.start()
        self.addCleanup(env.stop)
        self.calls = []
        self.current_version = "3.4.1"
        self.target_version = "3.5.0"
        self.prerelease = False
        self.prs = []
        self.refs = []
        self.statuses = []
        self.pr = {
            "number": 1, "state": "open", "head": {"sha": HEAD},
            "html_url": "https://github.com/libussa/seerr/pull/1",
        }

    def api(self, path, data=None, method=None):
        self.calls.append((path, data))
        if path.endswith("releases/latest"):
            return {"tag_name": "v3.5.0", "draft": False,
                    "prerelease": self.prerelease, "html_url": "https://github.com/seerr-team/seerr/releases/tag/v3.5.0"}
        if path.endswith("/commits/v3.5.0"):
            return {"sha": NEW}
        if "/contents/" in path:
            if "package.json" in path:
                text = json.dumps({"version": self.current_version if path.endswith(OLD) else self.target_version})
            else:
                text = NEW if path.endswith(HEAD) else OLD
            return {"content": base64.b64encode(text.encode()).decode()}
        if "/git/ref/heads/" in path:
            return {"object": {"sha": BASE}}
        if "/pulls?" in path:
            return self.prs
        if "/git/matching-refs/" in path:
            return self.refs
        if path.endswith("/git/commits/" + BASE):
            return {"tree": {"sha": "e" * 40}}
        if path.endswith("/git/trees"):
            return {"sha": "f" * 40}
        if path.endswith("/git/commits"):
            return {"sha": HEAD}
        if path.endswith("/git/refs"):
            return {"object": {"sha": HEAD}}
        if path.endswith("/pulls"):
            return self.pr
        if path.endswith("/status"):
            return {"statuses": self.statuses}
        self.fail(f"Unexpected API call {path}")

    def execute(self):
        with patch.object(updater, "api", side_effect=self.api), contextlib.redirect_stdout(io.StringIO()):
            updater.main()

    def mutations(self):
        return [(path, data) for path, data in self.calls if data is not None]

    def test_new_release_creates_pin_only_pr_and_requests_validation(self):
        self.execute()
        tree = next(data for path, data in self.mutations() if path.endswith("/git/trees"))
        self.assertEqual(tree["tree"], [{"path": updater.PIN, "mode": "100644", "type": "blob", "content": NEW + "\n"}])
        pr = next(data for path, data in self.mutations() if path.endswith("/pulls"))
        self.assertEqual(pr["base"], updater.BASE)
        self.assertIn("v3.5.0", pr["title"])
        self.assertIn("validate=true", self.output.read_text())

    def test_already_current_does_nothing(self):
        self.current_version = "3.5.0"
        self.execute()
        self.assertEqual(self.mutations(), [])
        self.assertNotIn("validate=true", self.output.read_text())

    def test_never_downgrades(self):
        self.current_version = "3.6.0"
        self.execute()
        self.assertEqual(self.mutations(), [])

    def test_existing_successful_pr_is_not_rebuilt_or_changed(self):
        self.prs = [self.pr]
        self.statuses = [{"context": updater.STATUS, "state": "success"}]
        self.execute()
        self.assertEqual(self.mutations(), [])
        self.assertNotIn("validate=true", self.output.read_text())

    def test_closed_pr_is_not_reopened(self):
        self.prs = [dict(self.pr, state="closed")]
        self.execute()
        self.assertEqual(self.mutations(), [])
        self.assertNotIn("validate=true", self.output.read_text())

    def test_manual_retry_rebuilds_failed_pr(self):
        self.prs = [self.pr]
        self.statuses = [{"context": updater.STATUS, "state": "failure"}]
        with patch.dict(os.environ, {"REVALIDATE": "true"}):
            self.execute()
        self.assertEqual(self.mutations(), [])
        self.assertIn("validate=true", self.output.read_text())

    def test_partial_run_reuses_branch_without_force_push(self):
        self.refs = [{"ref": "refs/heads/automation/french-dub-v3.5.0", "object": {"sha": HEAD}}]
        self.execute()
        self.assertEqual(len(self.mutations()), 1)
        self.assertTrue(self.mutations()[0][0].endswith("/pulls"))

    def test_rejects_prerelease(self):
        self.prerelease = True
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(self.mutations(), [])

    def test_rejects_version_mismatch(self):
        self.target_version = "3.4.1"
        with self.assertRaises(ValueError):
            self.execute()
        self.assertEqual(self.mutations(), [])


if __name__ == "__main__":
    unittest.main()
