import time
from collections import deque
from threading import Lock

import requests
from flask import current_app, has_request_context
from flask_login import current_user


class CardTraderError(RuntimeError):
    pass


class CardTraderRateLimiter:
    """Thread-safe rolling-window limiter for CardTrader API requests."""

    GLOBAL_LIMIT = (200, 10.0)
    MARKETPLACE_LIMIT = (10, 1.0)
    CLOCK_SAFETY_MARGIN = 0.001

    def __init__(self, clock=time.monotonic, sleeper=time.sleep):
        self._clock = clock
        self._sleep = sleeper
        self._lock = Lock()
        self._request_times = {
            "global": deque(),
            "marketplace": deque(),
        }

    def acquire(self, path):
        rules = [("global", *self.GLOBAL_LIMIT)]
        if path == "/marketplace/products":
            rules.append(("marketplace", *self.MARKETPLACE_LIMIT))

        # Keep the lock while waiting so concurrent Flask threads cannot reserve
        # the same slot. The timestamp is recorded immediately before dispatch.
        with self._lock:
            while True:
                now = self._clock()
                waits = []

                for name, limit, window_seconds in rules:
                    timestamps = self._request_times[name]
                    while timestamps and now - timestamps[0] >= window_seconds:
                        timestamps.popleft()
                    if len(timestamps) >= limit:
                        waits.append(window_seconds - (now - timestamps[0]))

                if not waits:
                    for name, _limit, _window_seconds in rules:
                        self._request_times[name].append(now)
                    return

                self._sleep(max(waits) + self.CLOCK_SAFETY_MARGIN)


_rate_limiter = CardTraderRateLimiter()


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
    max_rate_limit_retries = current_app.config.get(
        "CARDTRADER_MAX_RATE_LIMIT_RETRIES", 2
    )

    for attempt in range(max_rate_limit_retries + 1):
        _rate_limiter.acquire(path)
        response = requests.request(
            method,
            url,
            headers=get_headers(),
            timeout=30,
            **kwargs,
        )

        if response.status_code != 429 or attempt == max_rate_limit_retries:
            break

        retry_after = response.headers.get("Retry-After", "1")
        try:
            retry_delay = max(0.0, float(retry_after))
        except (TypeError, ValueError):
            retry_delay = 1.0
        time.sleep(retry_delay)

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
