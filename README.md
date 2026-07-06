# CardTrader App

Clean hosted-MVP version of the CardTrader watchlist and availability-checking tool.

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
```

Initialize the database and create the first user:

```powershell
flask --app app init-db
```

The `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables bootstrap the owner/admin account. Customer accounts should be created from the admin-only Users page after logging in.

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
- `SESSION_COOKIE_SECURE=true` when HTTPS is active

For production, prefer PostgreSQL through the hosting provider. SQLite is fine for local and LAN testing.

The bundled blueprint catalog is stored as `data/blueprints.sqlite`. For this MVP it contains only Magic: the Gathering cards, which keeps searches fast and memory usage low on small hosting plans.

## Tests

```powershell
pytest
```
