"""Local-only Plaid Link helper.

Run one-time per bank to obtain a long-lived access token. Never deploy.

Usage:
    cp .env.example .env            # fill PLAID_CLIENT_ID / PLAID_SECRET
    source .venv/bin/activate
    uvicorn link_helper:app --port 8765

Then open http://localhost:8765 in your browser, click "Link a bank",
complete the Plaid Link flow, and paste the printed env var line into
your local .env (setup.py does this for you) and your host's env vars.
The page also lists every connected bank, with its logo and accounts.

For re-auth (ITEM_LOGIN_REQUIRED):
    curl -X POST localhost:8765/create-link-token \\
      -H "content-type: application/json" \\
      -d '{"update_access_token": "access-prod-EXISTING"}'
    # then open the returned link_token in the browser widget
"""
from __future__ import annotations

import json
import os
import sys

# Defense-in-depth: this tool must never run on a deployed server.
# (The Docker image doesn't include it either.)
if os.environ.get("HORIZON") or os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT"):
    sys.exit("link_helper.py is a local-only tool. Run it on your own machine.")

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.institutions_get_by_id_request_options import InstitutionsGetByIdRequestOptions
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_update import LinkTokenCreateRequestUpdate
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products

from plaid_client import SecretStr, build_api, load_tokens

app = FastAPI(title="Personal Finance MCP — Link Helper")
# This page shows account details, so only answer requests addressed to this
# machine. Blocks DNS-rebinding tricks from other websites.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
api = build_api()

# Banks linked while this helper is running. Existing banks come from .env.
_session_tokens: dict[str, SecretStr] = {}
_institution_cache: dict[str, dict] = {}

_STATUS_LABELS = {
    "ITEM_LOGIN_REQUIRED": "needs_login",
    "PENDING_EXPIRATION": "needs_login",
    "PENDING_DISCONNECT": "needs_login",
}


class CreateReq(BaseModel):
    update_access_token: str | None = None


@app.post("/create-link-token")
def create_link_token(req: CreateReq) -> dict:
    if req.update_access_token:
        body = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id="personal-user"),
            client_name="Personal Finance MCP",
            country_codes=[CountryCode("US")],
            language="en",
            access_token=req.update_access_token,
            update=LinkTokenCreateRequestUpdate(account_selection_enabled=False),
        )
    else:
        body = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id="personal-user"),
            client_name="Personal Finance MCP",
            products=[Products("transactions")],
            optional_products=[
                Products("liabilities"),
                Products("investments"),
            ],
            country_codes=[CountryCode("US")],
            language="en",
        )
    return api.link_token_create(body).to_dict()


def institution_info(ins_id: str | None) -> dict:
    """Name, logo (base64 PNG or None) and brand color for an institution."""
    if not ins_id:
        return {"name": "Unknown bank", "logo": None, "color": None}
    if ins_id in _institution_cache:
        return _institution_cache[ins_id]
    try:
        ins = api.institutions_get_by_id(
            InstitutionsGetByIdRequest(
                institution_id=ins_id,
                country_codes=[CountryCode("US")],
                options=InstitutionsGetByIdRequestOptions(include_optional_metadata=True),
            )
        ).to_dict()["institution"]
        info = {
            "name": ins.get("name") or "Unknown bank",
            "logo": ins.get("logo"),
            "color": ins.get("primary_color"),
        }
    except Exception:
        # Not cached, so a temporary failure is retried on the next refresh.
        return {"name": "Unknown bank", "logo": None, "color": None}
    _institution_cache[ins_id] = info
    return info


def _describe_bank(env_key: str, token: SecretStr) -> dict:
    out: dict = {"env_key": f"PLAID_TOKEN_{env_key}", "status": "connected", "accounts": []}
    try:
        item = api.item_get(ItemGetRequest(access_token=token.reveal())).to_dict().get("item") or {}
    except ApiException:
        return {**out, "name": env_key.title(), "logo": None, "color": None, "status": "error"}

    out.update(institution_info(item.get("institution_id")))
    error = item.get("error") or {}
    if error:
        out["status"] = _STATUS_LABELS.get(error.get("error_code"), "error")
        return out

    try:
        resp = api.accounts_get(AccountsGetRequest(access_token=token.reveal())).to_dict()
        out["accounts"] = [
            {
                "name": a.get("name"),
                "mask": a.get("mask"),
                "subtype": str(a.get("subtype") or a.get("type") or ""),
            }
            for a in resp.get("accounts", [])
        ]
    except ApiException as e:
        code = ""
        try:
            code = json.loads(e.body or "{}").get("error_code", "")
        except (ValueError, TypeError, AttributeError):
            pass
        out["status"] = _STATUS_LABELS.get(code, "error")
    return out


@app.get("/connected")
def connected() -> dict:
    """Every linked bank (from .env plus this session). Never returns tokens."""
    tokens = {**load_tokens(), **_session_tokens}
    banks = [_describe_bank(key, tok) for key, tok in sorted(tokens.items())]
    return {"count": len(banks), "banks": banks}


class ExchangeReq(BaseModel):
    public_token: str


@app.post("/exchange")
def exchange(req: ExchangeReq) -> dict:
    resp = api.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=req.public_token)
    ).to_dict()
    access_token = resp["access_token"]
    item_id = resp["item_id"]

    item = api.item_get(ItemGetRequest(access_token=access_token)).to_dict().get("item", {}) or {}
    ins_name = institution_info(item.get("institution_id"))["name"]
    if ins_name == "Unknown bank":
        ins_name = "UNKNOWN"

    env_suffix = "".join(ch for ch in ins_name.upper() if ch.isalnum())
    env_key = f"PLAID_TOKEN_{env_suffix}" if env_suffix else "PLAID_TOKEN_UNKNOWN"
    _session_tokens[env_key.removeprefix("PLAID_TOKEN_")] = SecretStr(access_token)

    print("=" * 60, flush=True)
    print(f"Institution: {ins_name}", flush=True)
    print(f"Item ID:     {item_id}", flush=True)
    print("Add this to your .env (local) and your host's env vars (cloud):", flush=True)
    print(f"  {env_key}={access_token}", flush=True)
    print("Do NOT commit this line.", flush=True)
    print("=" * 60, flush=True)

    return {"institution": ins_name, "item_id": item_id, "env_key": env_key}


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Personal Finance MCP · Link your banks</title>
<style>
  :root {
    --bg: #f6f7f9; --card: #fff; --text: #14161a; --muted: #5d6470; --line: #e3e6eb;
    --accent: #1f6feb; --ok: #1a7f37; --ok-bg: #e6f4ea; --warn: #9a6700; --warn-bg: #fff4d6;
    --err: #b42318; --err-bg: #fde8e7;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1115; --card: #171a20; --text: #e8eaed; --muted: #9aa1ad; --line: #2a2f38;
      --accent: #4c8dff; --ok: #4ac26b; --ok-bg: #12261a; --warn: #e3b341; --warn-bg: #2b2412;
      --err: #ff7b72; --err-bg: #2d1515;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 760px; margin: 0 auto; padding: 48px 20px 64px; }
  h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: -0.01em; }
  .sub { color: var(--muted); margin: 0 0 24px; }
  button.primary { background: var(--accent); color: #fff; border: 0; border-radius: 8px;
                   padding: 11px 20px; font: inherit; font-weight: 600; cursor: pointer; }
  button.primary:disabled { opacity: .6; cursor: progress; }
  .notice { margin-top: 14px; padding: 10px 14px; border-radius: 8px; font-size: 14px; display: none; }
  .notice.ok { display: block; background: var(--ok-bg); color: var(--ok); }
  .notice.err { display: block; background: var(--err-bg); color: var(--err); }
  .section-head { display: flex; align-items: baseline; justify-content: space-between;
                  margin: 40px 0 14px; }
  h2 { font-size: 18px; margin: 0; }
  .count { color: var(--muted); font-size: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px;
          border-top: 4px solid var(--brand, var(--line)); }
  .head { display: flex; align-items: center; gap: 12px; }
  .logo { width: 44px; height: 44px; border-radius: 10px; flex: none; object-fit: contain;
          background: #fff; border: 1px solid var(--line); }
  .initials { display: grid; place-items: center; color: #fff; font-weight: 700; font-size: 16px;
              background: var(--brand, #6b7280); border: 0; }
  .name { font-weight: 600; line-height: 1.25; }
  .pill { display: inline-block; margin-top: 3px; font-size: 12px; font-weight: 600;
          padding: 1px 8px; border-radius: 999px; }
  .pill.connected { background: var(--ok-bg); color: var(--ok); }
  .pill.needs_login { background: var(--warn-bg); color: var(--warn); }
  .pill.error { background: var(--err-bg); color: var(--err); }
  ul { list-style: none; margin: 14px 0 0; padding: 12px 0 0; border-top: 1px solid var(--line);
       font-size: 13px; color: var(--muted); }
  li { display: flex; justify-content: space-between; gap: 8px; padding: 2px 0; }
  li span:first-child { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .hint { margin: 12px 0 0; font-size: 13px; color: var(--muted); }
  .empty { background: var(--card); border: 1px dashed var(--line); border-radius: 12px;
           padding: 28px; text-align: center; color: var(--muted); }
  .skeleton { height: 120px; border-radius: 12px; background: var(--card); border: 1px solid var(--line);
              animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: .5; } }
  footer { margin-top: 40px; color: var(--muted); font-size: 13px; }
  code { font-size: 12px; }
</style>
</head>
<body>
<main>
  <h1>Link your banks</h1>
  <p class="sub">Connect each bank or card through Plaid. Access is read-only and keys stay on this computer.</p>
  <button id="link" class="primary">Link a bank</button>
  <div id="notice" class="notice" role="status"></div>

  <div class="section-head">
    <h2>Connected banks</h2>
    <span id="count" class="count"></span>
  </div>
  <div id="banks" class="grid" aria-live="polite">
    <div class="skeleton"></div><div class="skeleton"></div>
  </div>

  <footer>Finished? Go back to the terminal and press Enter.</footer>
</main>

<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<script>
  const STATUS_TEXT = { connected: 'Connected', needs_login: 'Needs login', error: 'Error' };
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const notice = (msg, kind) => {
    const n = document.getElementById('notice');
    n.textContent = msg; n.className = 'notice ' + kind;
  };

  function bankCard(b) {
    const card = el('div', 'card');
    if (b.color) card.style.setProperty('--brand', b.color);

    const head = el('div', 'head');
    if (b.logo) {
      const img = el('img', 'logo');
      img.src = 'data:image/png;base64,' + b.logo;
      img.alt = '';
      head.append(img);
    } else {
      const initials = b.name.split(/\\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
      head.append(el('div', 'logo initials', initials));
    }
    const title = el('div');
    title.append(el('div', 'name', b.name));
    title.append(el('span', 'pill ' + b.status, STATUS_TEXT[b.status] || b.status));
    head.append(title);
    card.append(head);

    if (b.status === 'needs_login') {
      card.append(el('p', 'hint', 'The bank asked for a fresh login. Click "Link a bank" and connect it again.'));
    } else if (b.status === 'error') {
      card.append(el('p', 'hint', 'Plaid returned an error for this bank. Check the terminal for details.'));
    }
    if (b.accounts.length) {
      const list = el('ul');
      for (const a of b.accounts) {
        const li = el('li');
        li.append(el('span', null, a.name));
        li.append(el('span', null, a.mask ? '··' + a.mask : a.subtype));
        list.append(li);
      }
      card.append(list);
    }
    return card;
  }

  async function loadBanks() {
    const box = document.getElementById('banks');
    try {
      const r = await fetch('/connected');
      const data = await r.json();
      const accounts = data.banks.reduce((n, b) => n + b.accounts.length, 0);
      document.getElementById('count').textContent = data.count
        ? `${data.count} ${data.count === 1 ? 'bank' : 'banks'} · ${accounts} ${accounts === 1 ? 'account' : 'accounts'}`
        : '';
      box.replaceChildren(...(data.count
        ? data.banks.map(bankCard)
        : [el('div', 'empty', 'No banks connected yet. Click "Link a bank" to add your first one.')]));
    } catch (e) {
      box.replaceChildren(el('div', 'empty', 'Could not load connected banks. Check the terminal for errors.'));
    }
  }

  document.getElementById('link').onclick = async () => {
    const btn = document.getElementById('link');
    btn.disabled = true;
    try {
      const r = await fetch('/create-link-token', {
        method: 'POST',
        headers: {'content-type': 'application/json'},
        body: JSON.stringify({}),
      });
      const data = await r.json();
      if (!data.link_token) { notice('Could not start Plaid Link: ' + JSON.stringify(data), 'err'); return; }
      Plaid.create({
        token: data.link_token,
        onSuccess: async (public_token) => {
          const ex = await fetch('/exchange', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify({public_token}),
          });
          const res = await ex.json();
          notice(`${res.institution} connected.`, 'ok');
          loadBanks();
        },
        onExit: (err) => { if (err) notice('Plaid Link closed: ' + (err.display_message || err.error_message || err.error_code), 'err'); },
      }).open();
    } finally {
      btn.disabled = false;
    }
  };

  loadBanks();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML
