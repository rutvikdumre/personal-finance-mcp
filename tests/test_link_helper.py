import os
import subprocess
import sys

from fastapi.testclient import TestClient

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_horizon_guard_blocks_import():
    # Run a fresh subprocess with HORIZON set; importing link_helper must sys.exit.
    result = subprocess.run(
        [sys.executable, "-c", "import link_helper"],
        env={**os.environ, "HORIZON": "1"},
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode != 0
    assert "local-only tool" in (result.stderr + result.stdout)


def test_index_returns_html(fake_env_tokens):
    # Import inside the test so fake_env_tokens env is active before build_api() runs.
    # NOTE: link_helper.build_api() is called at import time, but we're using
    # fake env vars which produce a valid (if useless) PlaidApi instance.
    import importlib
    import link_helper
    importlib.reload(link_helper)
    client = TestClient(link_helper.app, base_url="http://localhost")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Plaid" in resp.text
    assert "Link a bank" in resp.text


class _Resp:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


def _helper_with_fake_api(fake_env_tokens):
    import importlib
    from unittest.mock import MagicMock

    import link_helper
    importlib.reload(link_helper)
    api = MagicMock()
    link_helper.api = api
    return link_helper, api


def test_connected_lists_banks_with_logo_and_accounts(fake_env_tokens):
    link_helper, api = _helper_with_fake_api(fake_env_tokens)

    def item_get(req):
        if req.access_token == "access-prod-fake-chase":
            return _Resp({"item": {"institution_id": "ins_3"}})
        return _Resp({"item": {"institution_id": "ins_12",
                                "error": {"error_code": "ITEM_LOGIN_REQUIRED"}}})

    def institution(req):
        names = {"ins_3": ("Chase", "aGVsbG8=", "#117aca"), "ins_12": ("Fidelity", None, "#4a8a2a")}
        name, logo, color = names[req.institution_id]
        return _Resp({"institution": {"name": name, "logo": logo, "primary_color": color}})

    api.item_get.side_effect = item_get
    api.institutions_get_by_id.side_effect = institution
    api.accounts_get.return_value = _Resp({"accounts": [
        {"name": "Checking", "mask": "1234", "subtype": "checking", "type": "depository"},
        {"name": "Freedom", "mask": "9876", "subtype": "credit card", "type": "credit"},
    ]})

    client = TestClient(link_helper.app, base_url="http://localhost")
    resp = client.get("/connected")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2

    chase, fidelity = data["banks"]
    assert chase["name"] == "Chase"
    assert chase["logo"] == "aGVsbG8="
    assert chase["color"] == "#117aca"
    assert chase["status"] == "connected"
    assert [a["mask"] for a in chase["accounts"]] == ["1234", "9876"]

    assert fidelity["name"] == "Fidelity"
    assert fidelity["status"] == "needs_login"
    assert fidelity["accounts"] == []

    # Access tokens must never reach the browser.
    assert "access-prod" not in resp.text


def test_connected_includes_banks_linked_this_session(fake_env_tokens, monkeypatch):
    monkeypatch.delenv("PLAID_TOKEN_CHASE")
    monkeypatch.delenv("PLAID_TOKEN_FIDELITY")
    link_helper, api = _helper_with_fake_api(fake_env_tokens)
    api.item_public_token_exchange.return_value = _Resp(
        {"access_token": "access-prod-new", "item_id": "item-1"})
    api.item_get.return_value = _Resp({"item": {"institution_id": "ins_10"}})
    api.institutions_get_by_id.return_value = _Resp(
        {"institution": {"name": "American Express", "logo": None, "primary_color": "#016fd0"}})
    api.accounts_get.return_value = _Resp({"accounts": []})

    client = TestClient(link_helper.app, base_url="http://localhost")
    assert client.get("/connected").json()["count"] == 0
    assert client.post("/exchange", json={"public_token": "public-x"}).json()["env_key"] ==         "PLAID_TOKEN_AMERICANEXPRESS"
    banks = client.get("/connected").json()["banks"]
    assert [b["name"] for b in banks] == ["American Express"]


def test_rejects_non_local_host(fake_env_tokens):
    link_helper, _ = _helper_with_fake_api(fake_env_tokens)
    client = TestClient(link_helper.app, base_url="http://evil.example")
    assert client.get("/connected").status_code == 400
