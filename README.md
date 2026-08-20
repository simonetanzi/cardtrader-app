# CardTrader App

Hosted CardTrader watchlist and availability-checking tool with private user accounts and an optional restricted public demo.

The app keeps the CardTrader API token on the server. Browser clients never receive the token. The CardTrader client is intentionally limited to:

- `GET /marketplace/products`
- `GET /cart`
- `POST /cart/add`
- `POST /cart/remove`

There is no purchase endpoint in this app.

## Local setup

```powershell
cd C:\Users\serpe\Documents\dev\python\Cardtrader_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set environment variables in PowerShell:

```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:CARDTRADER_API_TOKEN="replace-with-cardtrader-token"
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="replace-with-a-real-password"
$env:USER_USERNAME="friend"
$env:USER_PASSWORD="replace-with-a-real-password"
$env:ENABLE_GUEST_ACCOUNT="true"
$env:GUEST_USERNAME="guest"
```

Initialize the database and create the first user:

```powershell
flask --app app init-db
```

The `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables bootstrap the owner/admin account. `USER_USERNAME` and `USER_PASSWORD` can bootstrap one normal customer account.

When `ENABLE_GUEST_ACCOUNT=true`, the app also creates a passwordless shared guest account and shows a **Continue as guest** button on the login page. Guest visitors share one communal watchlist: they can search, add or remove cards, adjust card criteria, and run live price checks with the server-side `CARDTRADER_API_TOKEN`. They cannot create separate watchlists, rename or delete the shared list, change credentials, view the token, or save their own token. Changes made by one guest are visible to every other guest. Use a dedicated, payment-free CardTrader account for the public demo because availability checks temporarily add and remove cart items.

Run locally on this PC only:

```powershell
flask --app app run --host 127.0.0.1 --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

## LAN test

Run the app so another device on your LAN can reach it:

```powershell
flask --app app run --host 0.0.0.0 --port 5000
```

Find the host PC local IP:

```powershell
ipconfig
```

Open this from another PC on the same network:

```text
http://HOST_PC_LOCAL_IP:5000
```

Windows Firewall may ask you to allow Python on private networks.

## Hosting notes

For Render or Railway, use:

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app
```

Set environment variables in the hosting dashboard:

- `SECRET_KEY`
- `CARDTRADER_API_TOKEN`
- `DATABASE_URL`
- `ADMIN_USERNAME` and `ADMIN_PASSWORD` to bootstrap the owner/admin account
- `USER_USERNAME` and `USER_PASSWORD` to bootstrap one normal customer account
- `ENABLE_GUEST_ACCOUNT=true` and optionally `GUEST_USERNAME` to expose the restricted public demo
- `SESSION_COOKIE_SECURE=true` when HTTPS is active

For production, prefer PostgreSQL through the hosting provider. SQLite is fine for local and LAN testing.

The bundled blueprint catalog is stored as `data/blueprints.sqlite`. For this MVP it contains only Magic: the Gathering cards, which keeps searches fast and memory usage low on small hosting plans.

## Before making the GitHub repository public

1. Confirm `.env`, `app.db`, logs, and virtual environments are ignored and are not present anywhere in Git history.
2. Rotate the CardTrader token, Flask secret key, database password, and account passwords if any were ever committed or pasted into repository files.
3. Keep production secrets only in the hosting provider's environment-variable settings.
4. Enable GitHub secret scanning and dependency alerts after changing repository visibility.
5. Review the bundled catalog/database for data you are permitted to redistribute.

Changing the GitHub repository visibility is intentionally a separate manual step after this review; making the code public does not automatically deploy the guest demo.

## Tests

```powershell
pytest
```
