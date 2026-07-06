import requests
from flask import current_app, has_request_context
from flask_login import current_user


class CardTraderError(RuntimeError):
    pass


def get_headers():
    token = ""

    if has_request_context() and current_user.is_authenticated:
        token = (current_user.cardtrader_api_token or "").strip()

    if not token:
        token = current_app.config["CARDTRADER_API_TOKEN"]

    if not token:
        raise CardTraderError("CardTrader API token is missing for this user.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def request_cardtrader(method, path, **kwargs):
    allowed_paths = {
        "/marketplace/products",
        "/cart",
        "/cart/add",
        "/cart/remove",
    }
    if path not in allowed_paths:
        raise CardTraderError(f"Blocked unsafe CardTrader endpoint: {path}")

    url = f"{current_app.config['CARDTRADER_BASE_URL']}{path}"
    response = requests.request(
        method,
        url,
        headers=get_headers(),
        timeout=30,
        **kwargs,
    )

    if response.status_code == 401:
        raise CardTraderError("CardTrader rejected the API token.")
    if response.status_code == 403:
        raise CardTraderError("CardTrader refused access for this API token.")
    if response.status_code not in (200, 201):
        preview = response.text[:300]
        raise CardTraderError(
            f"CardTrader {path} failed with status {response.status_code}: {preview}"
        )

    return response.json()


def fetch_marketplace_products(blueprint_id, language_code):
    data = request_cardtrader(
        "GET",
        "/marketplace/products",
        params={
            "blueprint_id": blueprint_id,
            "language": language_code,
        },
    )
    return data.get(str(blueprint_id), [])


def fetch_cart():
    return request_cardtrader("GET", "/cart")


def add_product_to_cart(product_id, quantity):
    return request_cardtrader(
        "POST",
        "/cart/add",
        json={
            "product_id": product_id,
            "quantity": quantity,
            "via_cardtrader_zero": True,
        },
    )


def remove_product_from_cart(product_id, quantity):
    if quantity <= 0:
        return None
    return request_cardtrader(
        "POST",
        "/cart/remove",
        json={
            "product_id": product_id,
            "quantity": quantity,
        },
    )
