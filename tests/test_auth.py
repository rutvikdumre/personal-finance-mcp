import asyncio
import os
import subprocess
import sys

import pytest
from starlette.testclient import TestClient

import server

GOOD = "x" * 40
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_token_means_no_auth(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    assert server.build_auth() is None


def test_short_token_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "too-short")
    with pytest.raises(ValueError):
        server.build_auth()


def test_verifier_accepts_only_exact_token():
    v = server.BearerTokenVerifier(GOOD)
    assert asyncio.run(v.verify_token(GOOD)) is not None
    assert asyncio.run(v.verify_token(GOOD + "y")) is None
    assert asyncio.run(v.verify_token("")) is None


@pytest.mark.parametrize("host,expected", [
    ("127.0.0.1", True), ("localhost", True), ("::1", True),
    ("0.0.0.0", False), ("192.168.1.5", False), ("example.com", False),
])
def test_is_loopback(host, expected):
    assert server.is_loopback(host) is expected


def test_refuses_public_bind_without_token():
    env = {k: v for k, v in os.environ.items() if k != "MCP_AUTH_TOKEN"}
    env.update(HOST="0.0.0.0", PORT="8799", PLAID_CLIENT_ID="x", PLAID_SECRET="x")
    # main() loads a local .env, which never overrides existing vars, so an
    # explicit empty token guarantees "no auth" even if .env sets one.
    env["MCP_AUTH_TOKEN"] = ""
    result = subprocess.run(
        [sys.executable, "-c", "import server; server.main()"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert "Refusing to listen" in result.stderr


def test_http_requires_bearer_token():
    server.mcp.auth = server.BearerTokenVerifier(GOOD)
    try:
        app = server.mcp.http_app(path="/mcp")
        with TestClient(app) as client:
            assert client.get("/health").text == "ok"
            body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
            headers = {"accept": "application/json, text/event-stream"}
            assert client.post("/mcp", json=body, headers=headers).status_code == 401
            bad = {**headers, "authorization": "Bearer wrong"}
            assert client.post("/mcp", json=body, headers=bad).status_code == 401
            good = {**headers, "authorization": f"Bearer {GOOD}"}
            assert client.post("/mcp", json=body, headers=good).status_code != 401
    finally:
        server.mcp.auth = None
