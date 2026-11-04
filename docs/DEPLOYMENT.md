# Deployment

The server runs anywhere that can run Python 3.11+ or a Docker container. Pick one:

| Option | Reachable from | Auth needed |
|---|---|---|
| [Local](#local) | This computer only | No |
| [Docker](#docker) | Wherever you expose it | Yes, if exposed |
| [Render / Koyeb / Railway](#one-click-hosts) | Anywhere | Yes (enforced) |
| [Other hosts](#other-hosts) | Anywhere | Yes (enforced) |

## How auth works

- `HOST` defaults to `127.0.0.1`. Nothing else on your network can connect.
- If `HOST` is anything else (the Docker image uses `0.0.0.0`), the server **refuses to start** unless `MCP_AUTH_TOKEN` is set to 32+ characters.
- With `MCP_AUTH_TOKEN` set, every request to `/mcp` must include `Authorization: Bearer <token>`. Wrong or missing tokens get `401`.
- `GET /health` is unauthenticated and returns `ok` for host health checks. It returns no data.

Generate a token:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `PLAID_CLIENT_ID` | Yes | Plaid dashboard → Developers → Keys |
| `PLAID_SECRET` | Yes | Production secret (or Sandbox secret with `PLAID_ENV=sandbox`) |
| `PLAID_ENV` | No | `production` (default) or `sandbox` |
| `PLAID_TOKEN_<BANK>` | One per bank | Written to `.env` by `setup.py`. Any name after the prefix works. |
| `MCP_AUTH_TOKEN` | When not on localhost | 32+ random characters |
| `HOST` | No | Default `127.0.0.1`; the Docker image sets `0.0.0.0` |
| `PORT` | No | Default `8000`. Most hosts set this automatically. |

## Local

```bash
python3 setup.py                   # once: keys, bank linking, Claude Code registration
.venv/bin/python server.py         # Windows: .venv\Scripts\python.exe server.py
```

Connect your client to `http://127.0.0.1:8000/mcp`. `run_local.py` still works too and does the same thing.

## Docker

```bash
docker build -t personal-finance-mcp .
docker run --rm -p 8000:8000 --env-file .env -e MCP_AUTH_TOKEN=<token> personal-finance-mcp
```

The image runs as a non-root user and contains only `server.py` and `plaid_client.py`. The bank-linking tool is never included.

## One-click hosts

Link your banks on your own machine first (`python3 setup.py`), then copy the variables from `.env` into the host.

### Render

1. Click **Deploy to Render** in the README. It reads [`render.yaml`](../render.yaml).
2. Enter `PLAID_CLIENT_ID` and `PLAID_SECRET` when asked. Render generates `MCP_AUTH_TOKEN` itself.
3. After the first deploy, open the service → **Environment**, add each `PLAID_TOKEN_*` line, and copy the generated `MCP_AUTH_TOKEN`.
4. Your endpoint is `https://<service>.onrender.com/mcp`.

On the free plan the service sleeps after 15 minutes without traffic. The first request after that takes about a minute while it wakes up.

### Koyeb

1. Click **Deploy to Koyeb** in the README.
2. Fill in `PLAID_CLIENT_ID`, `PLAID_SECRET` and `MCP_AUTH_TOKEN`, and add each `PLAID_TOKEN_*` variable.
3. Your endpoint is `https://<app>.koyeb.app/mcp`.

### Railway

1. New Project → **Deploy from GitHub repo** → pick your fork. Railway reads [`railway.json`](../railway.json) and builds the Dockerfile.
2. Under **Variables**, add every variable from the table above, including `MCP_AUTH_TOKEN`.
3. Under **Settings → Networking**, generate a domain. Your endpoint is `https://<domain>/mcp`.

Maintainers: to get a Railway deploy button, publish a template from this repo in your Railway account, then put its URL in the commented-out button in the README.

## Other hosts

Fly.io, AWS App Runner or ECS, Google Cloud Run, Azure Container Apps, a VPS, a Raspberry Pi: build the Dockerfile and set the variables above. Use HTTPS, since the bearer token travels in a header.

On a private network such as Tailscale, still set `MCP_AUTH_TOKEN`. It costs nothing.

## Adding a bank

1. On your machine, run `python3 setup.py`. It keeps your existing keys and opens the bank-linking page.
2. Copy the new `PLAID_TOKEN_<BANK>=...` line from `.env` into your host's variables.
3. The host restarts with the new variable. No code change needed.

## When a bank needs you to log in again (`ITEM_LOGIN_REQUIRED`)

Banks sometimes expire Plaid's access, for example after a password change. `get_institutions_status` then shows `re_auth_required` for that bank.

The simplest fix is to link the bank again with `setup.py` and replace the old `PLAID_TOKEN_` value on your host.

To keep the same token instead, use Plaid's update mode:

```bash
.venv/bin/python -m uvicorn link_helper:app --host 127.0.0.1 --port 8765
curl -X POST http://127.0.0.1:8765/create-link-token \
  -H "content-type: application/json" \
  -d '{"update_access_token": "<the PLAID_TOKEN_ value for that bank>"}'
```

Open the returned `link_token` with Plaid Link (for example by editing `INDEX_HTML` in `link_helper.py` to use it) and log in. The token doesn't change, so your deployment needs no update.
