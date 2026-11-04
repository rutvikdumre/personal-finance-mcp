import os

import dotenv
import pytest
from unittest.mock import MagicMock

# Keep tests hermetic: never load the developer's real .env (it holds live
# Plaid tokens). Modules do `from dotenv import load_dotenv`, so patching the
# module attribute before they're imported is enough.
dotenv.load_dotenv = lambda *args, **kwargs: False

# Strip any real Plaid / auth settings inherited from the shell.
for _key in list(os.environ):
    if _key.startswith("PLAID_") or _key in ("MCP_AUTH_TOKEN", "HOST"):
        del os.environ[_key]


@pytest.fixture
def fake_env_tokens(monkeypatch):
    monkeypatch.setenv("PLAID_TOKEN_CHASE", "access-prod-fake-chase")
    monkeypatch.setenv("PLAID_TOKEN_FIDELITY", "access-prod-fake-fidelity")
    monkeypatch.setenv("PLAID_CLIENT_ID", "client-id-fake")
    monkeypatch.setenv("PLAID_SECRET", "secret-fake")
    monkeypatch.setenv("PLAID_ENV", "sandbox")


@pytest.fixture
def mock_plaid_api():
    return MagicMock()
