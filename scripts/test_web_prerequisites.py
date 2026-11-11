import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("check-web-prerequisites.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def consumer(module="library", environment="production"):
    repository = "https://github.com/aetheric-forge/" + ("adr-campus" if module == "decisions" else module)
    artifact = {
        "Version": 1, "Module": module, "InstitutionId": module,
        "Environment": environment, "PlanId": "a" * 64,
        "DeploymentId": hashlib.sha256(json.dumps([repository, module, environment], separators=(",", ":")).encode()).hexdigest(),
        "Settings": {module.capitalize() + ":Enabled": "true", "Private:Password": "sensitive-fixture-value"},
    }
    return artifact


def secret(artifact):
    return {"data": {"configuration.json": base64.b64encode(json.dumps(artifact).encode()).decode()}}


class PrerequisiteTests(unittest.TestCase):
    def test_matching_identity_is_accepted(self):
        self.assertIsNone(gate.check_consumer(secret(consumer()), "library", "production", None))

    def test_empty_placeholder_requires_provisioning(self):
        self.assertIn("rerun provisioning", gate.check_consumer({}, "library", "production", None))

    def test_wrong_environment_or_deployment_is_rejected(self):
        self.assertIsNotNone(gate.check_consumer(secret(consumer(environment="dev")), "library", "production", None))
        artifact = consumer()
        artifact["DeploymentId"] = "b" * 64
        self.assertIsNotNone(gate.check_consumer(secret(artifact), "library", "production", None))

    def test_decisions_requires_matching_owner(self):
        artifact = consumer("decisions")
        artifact["Settings"].update({"Decisions:Owner:DeploymentId": "c" * 64, "Decisions:Owner:Environment": "production"})
        self.assertIsNotNone(gate.check_consumer(secret(artifact), "decisions", "production", "d" * 64))
        self.assertIsNone(gate.check_consumer(secret(artifact), "decisions", "production", "c" * 64))

    def test_missing_namespace_state_blocks_web(self):
        issues = gate.inspect([], "production")
        self.assertTrue(any("PVC missing" in x for x in issues))
        self.assertTrue(any("scoped credential missing" in x for x in issues))
        self.assertTrue(any("rerun provisioning" in x for x in issues))

    def test_malformed_secret_never_appears_in_diagnostics(self):
        artifact = consumer()
        artifact["Settings"] = {"Library:Enabled": {"Password": "sensitive-fixture-value"}}
        output = gate.check_consumer(secret(artifact), "library", "production", None)
        self.assertIsNotNone(output)
        self.assertNotIn("sensitive-fixture-value", output)

    def test_kubectl_error_does_not_echo_sensitive_stderr(self):
        import subprocess
        output = io.StringIO()
        error = subprocess.CalledProcessError(1, ["kubectl"], stderr="sensitive-fixture-value")
        with patch("sys.argv", ["gate"]), patch.object(gate.subprocess, "run", side_effect=error), contextlib.redirect_stdout(output):
            self.assertEqual(2, gate.main())
        self.assertNotIn("sensitive-fixture-value", output.getvalue())


if __name__ == "__main__":
    unittest.main()
