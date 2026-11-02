# personal-finance-mcp (local)

Read-only MCP server that lets Claude query my Chase and Amex accounts through
Plaid's free Trial plan (up to 10 connections). Runs locally, on `127.0.0.1` only.

Based on [JosueM1109/personal-finance-mcp](https://github.com/JosueM1109/personal-finance-mcp)
(MIT), vendored at upstream commit `33e0343` after a code review. The original
README is in [`docs/UPSTREAM_README.md`](docs/UPSTREAM_README.md).

## Changes from upstream

| File | Why |
|---|---|
| `run_local.py` | Upstream `server.py` binds `0.0.0.0` with no auth, which exposes every linked account to anyone on the same Wi-Fi. It also never loads `.env`. This launcher binds `127.0.0.1` and loads `.env`. **Always start the server with this file.** |
| `setup.py` | One-time setup: virtualenv, dependencies, Plaid keys (hidden input), bank linking with automatic token capture into `.env`, and Claude Code registration. |

Upstream files are unchanged.

## Setup

Needs Python 3.11+ and a Plaid account on the **Trial plan** (dashboard.plaid.com).
In Plaid, enable the **Transactions**, **Liabilities** and **Investments** products, then
copy your **Client ID** and **Production secret** from Build → Keys.

```bash
git clone https://github.com/rutvikdumre/personal-finance-mcp.git
cd personal-finance-mcp
python3 setup.py        # Windows: py setup.py
```

1. Paste the Client ID and Production secret when prompted.
2. A browser opens at `localhost:8765`. Link Chase, then Amex, then press Enter in the terminal.
3. Start the server (leave the terminal open):

   ```bash
   .venv/bin/python run_local.py            # macOS / Linux
   .venv\Scripts\python.exe run_local.py    # Windows
   ```

4. In Claude Code, run `claude mcp add --scope user --transport http personal-finance http://127.0.0.1:8000/mcp`.
   `setup.py` does this for you if the `claude` CLI is installed.
5. Ask Claude: *"list my accounts"*.

To link another bank or fix one that needs re-authentication, run `python3 setup.py` again.

## Tools (all read-only)

`list_accounts` · `get_balances` · `get_transactions` · `search_transactions` ·
`get_recurring_transactions` · `get_liabilities` · `get_investment_holdings` ·
`get_investment_transactions` · `get_institutions_status`

No tool can move money or change anything at a bank.

## Security

- `.env` holds the Plaid secret and the per-bank access tokens. It's gitignored
  and set to `chmod 600` on macOS/Linux. **Never commit it.**
- Keep this repo **private**.
- If a token leaks, revoke it in the Plaid dashboard and rotate the secret.
- Don't expose port 8000 to the internet without adding auth first (see
  `docs/DEPLOYMENT.md`). Remote access for claude.ai is a separate, later step.
