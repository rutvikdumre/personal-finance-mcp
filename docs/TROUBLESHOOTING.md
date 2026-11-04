# Troubleshooting

## Tool returns an empty list despite real data

That Item's Plaid products don't include the one the tool needs. `get_liabilities` requires the `liabilities` product to have been enabled at Link time; `get_investment_holdings` requires `investments`. If you linked the bank before enabling the product in the Plaid dashboard, you need to **unlink and re-link** that bank with all three products active. The tool will surface `PRODUCTS_NOT_SUPPORTED` in `warnings` when this happens.

## Deployment boots but tools crash on startup

Missing env var. Check deployment logs. `PLAID_CLIENT_ID` and `PLAID_SECRET` are required. The server imports fine with zero `PLAID_TOKEN_*` vars (you'd just get empty responses), but the Plaid credentials must be present.

## First MCP call after idle takes 20–60 seconds

Your host put the service to sleep while idle (Render's free plan does this after 15 minutes). The first call wakes it up; later calls are fast (the 5-minute health cache also warms up after the first call). Not a bug.

## `get_institutions_status()` shows `re_auth_required`

Plaid's `ITEM_LOGIN_REQUIRED`. The bank's session with Plaid has expired (password changed, MFA token rotated, bank forced a re-auth). Follow the update-mode flow in [DEPLOYMENT.md](DEPLOYMENT.md#when-a-bank-needs-you-to-log-in-again-item_login_required).

## Plaid Link shows a bank as "unsupported" (common with Amex)

Plaid Link filters institutions by the `products` array on the Link token. If `investments` is required, any bank without brokerage (Amex, most retail banks) is hidden. `link_helper.py` requests only `transactions` as required and puts `liabilities` + `investments` in `optional_products`, so all banks are reachable and each Item is initialized with whatever products it actually supports. If a bank still shows as unsupported, it's usually the `INSTITUTION_REGISTRATION_REQUIRED` issue below.

## Link flow errors with `INSTITUTION_REGISTRATION_REQUIRED`

OAuth institutions (Amex, Chase, Wells Fargo, Capital One, BoA, Citi, Schwab, PNC, etc.) require per-institution registration in the Plaid dashboard before you can create Items. Go to https://dashboard.plaid.com/activity/status/oauth-institutions, find the bank, and register. Most are one-click auto-registrations that take a few hours (up to 24). Schwab and PNC have extra questions. Non-OAuth banks (smaller banks, most credit unions, fintechs like Ally / SoFi / Marcus) don't need this.

While you wait, you can develop against sandbox: flip `.env` to `PLAID_ENV=sandbox` and use credentials `user_good` / `pass_good` in Plaid Link.

## `fastmcp inspect server.py:mcp` fails, or import error after `pip install`

Plaid SDK version mismatch. Check the installed versions with `.venv/bin/pip show plaid-python fastmcp`. They should match the ranges in `requirements.txt` (plaid-python 39.x, fastmcp 3.x). If not, run `pip install -r requirements.txt --force-reinstall`.

## Server exits with "Refusing to listen on 0.0.0.0 without authentication"

Working as intended. The server is set to accept connections from other machines (the Docker image does this), so it needs `MCP_AUTH_TOKEN`. Set it to 32+ random characters, or set `HOST=127.0.0.1` to stay local.

## Client gets `401 Unauthorized`

The client isn't sending the token, or it doesn't match `MCP_AUTH_TOKEN` exactly. The header must be `Authorization: Bearer <token>`. Check for trailing spaces or line breaks when copying the token from your host's dashboard.
