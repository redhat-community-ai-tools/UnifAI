"""Self-test of fork/ci/slsa_provenance.py. Run: python3 fork/ci/test_slsa_provenance.py"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import slsa_provenance as s  # noqa: E402

ENV = {
    "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "startxfr/UnifAI",
    "GITHUB_REF": "refs/heads/devel", "GITHUB_SHA": "1bb72a84d" + "0" * 31,
    "GITHUB_WORKFLOW_REF": "startxfr/UnifAI/.github/workflows/publish-images.yml@refs/heads/devel",
    "GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_EVENT_NAME": "push",
    "RUNNER_ENVIRONMENT": "github-hosted",
}


class Provenance(unittest.TestCase):
    def test_it_names_the_workflow_the_commit_and_the_run(self):
        p = s.predicate(ENV, "ui")
        bd = p["buildDefinition"]
        self.assertEqual(bd["buildType"], s.BUILD_TYPE)
        self.assertEqual(bd["externalParameters"]["workflow"],
                         {"ref": "refs/heads/devel", "repository": "https://github.com/startxfr/UnifAI",
                          "path": ".github/workflows/publish-images.yml"})
        self.assertEqual(bd["externalParameters"]["component"], "ui")
        self.assertEqual(bd["resolvedDependencies"][0]["digest"]["gitCommit"], ENV["GITHUB_SHA"])
        self.assertEqual(p["runDetails"]["builder"]["id"],
                         "https://github.com/startxfr/UnifAI/.github/workflows/publish-images.yml@refs/heads/devel")
        self.assertTrue(p["runDetails"]["metadata"]["invocationId"].endswith("/runs/123456/attempts/2"))

    def test_outside_github_actions_it_refuses(self):
        with self.assertRaises(SystemExit):
            s.predicate({}, "ui")


if __name__ == "__main__":
    unittest.main()
