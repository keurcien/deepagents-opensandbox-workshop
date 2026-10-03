"""Host-side setup tests. No real credentials, network or Docker required."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

SOLUTIONS = Path(__file__).resolve().parents[1] / "solutions"
with patch.object(sys, "path", [str(SOLUTIONS), *sys.path]):
    spec = importlib.util.spec_from_file_location("vault_bonus", SOLUTIONS / "13_deep_agent_credential_vault.py")
    bonus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bonus)


class CredentialVaultTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sandbox = SimpleNamespace(
            id="test-sandbox", credential_vault=SimpleNamespace(create=AsyncMock(), delete=AsyncMock()), destroy=AsyncMock(),
        )
        self.create = AsyncMock(return_value=self.sandbox)
        self.patch = patch.object(bonus.Sandbox, "create", self.create)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.kwargs = dict(host="api.github.com", path="/user", server="localhost:17431")

    async def test_provisions_before_yield_and_keeps_secret_out_of_sandbox_config(self):
        async with bonus.credential_backend("synthetic-test-token", **self.kwargs) as backend:
            self.assertIs(backend.sandbox, self.sandbox)
            self.sandbox.credential_vault.create.assert_awaited_once()
            self.sandbox.destroy.assert_not_awaited()
            options = self.create.call_args.kwargs
            self.assertNotIn("synthetic-test-token", repr(self.create.call_args))
            self.assertNotIn("env", options)
            self.assertNotIn("volumes", options)
            self.assertTrue(options["credential_proxy"].enabled)
            policy = options["network_policy"]
            self.assertEqual(policy.default_action, "deny")
            self.assertEqual([(r.action, r.target) for r in policy.egress], [("allow", "api.github.com")])
            self.assertEqual(options["connection_config"].domain, "localhost:17431")
            vault = self.sandbox.credential_vault.create.call_args.kwargs
            self.assertEqual(vault["credentials"][0].source.value, "synthetic-test-token")
            binding = vault["bindings"][0]
            self.assertEqual(binding.match.hosts, ["api.github.com"])
            self.assertEqual(binding.match.methods, ["GET"])
            self.assertEqual(binding.match.paths, ["/user"])
            self.assertEqual(binding.match.schemes, ["https"])
        self.sandbox.destroy.assert_awaited_once()

    async def test_vault_failure_cleans_up_without_handing_sandbox_to_agent(self):
        self.sandbox.credential_vault.create.side_effect = RuntimeError("vault unavailable")
        with self.assertRaisesRegex(RuntimeError, "vault unavailable"):
            async with bonus.credential_backend("synthetic", **self.kwargs):
                self.fail("The backend must not be yielded before credentials are provisioned")
        self.sandbox.destroy.assert_awaited_once()

    async def test_agent_failure_cleans_up(self):
        with self.assertRaisesRegex(RuntimeError, "agent failed"):
            async with bonus.credential_backend("synthetic", **self.kwargs):
                raise RuntimeError("agent failed")
        self.sandbox.destroy.assert_awaited_once()

    async def test_blank_token_does_not_create_sandbox(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            async with bonus.credential_backend("  ", **self.kwargs):
                self.fail("Empty token must not create a backend")
        self.create.assert_not_awaited()

    async def test_smoke_needs_no_host_secrets_or_model(self):
        backend = SimpleNamespace(
            sandbox=self.sandbox,
            aexecute=AsyncMock(return_value=SimpleNamespace(exit_code=0, output="ok")),
        )
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(bonus, "OpenSandboxBackend", return_value=backend),
            patch.object(bonus, "ChatOpenAI") as model,
        ):
            await bonus.main(smoke_test=True, server="localhost:17431")
            model.assert_not_called()
            self.assertEqual(backend.aexecute.await_count, 2)
            self.sandbox.credential_vault.delete.assert_awaited_once()
            command = backend.aexecute.call_args_list[0].args[0]
            self.assertNotIn("volcamp-synthetic-smoke-token", command)
            self.assertNotIn("Authorization", command)
            self.assertIn("https://httpbin.org/bearer", command)
            binding = self.sandbox.credential_vault.create.call_args.kwargs["bindings"][0]
            self.assertEqual(binding.match.hosts, ["httpbin.org"])
            self.assertEqual(binding.match.paths, ["/bearer"])
        self.sandbox.destroy.assert_awaited_once()
