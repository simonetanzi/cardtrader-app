import pytest

import cardtrader_client
from cardtrader_client import (
    CardTraderError,
    CardTraderRateLimiter,
    request_cardtrader,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeResponse:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return {}


def test_blocks_purchase_endpoint(app_context):
    with pytest.raises(CardTraderError):
        request_cardtrader("POST", "/cart/purchase")


def test_marketplace_requests_are_limited_to_ten_per_second(
    app_context, monkeypatch
):
    clock = FakeClock()
    limiter = CardTraderRateLimiter(clock.monotonic, clock.sleep)
    monkeypatch.setattr(cardtrader_client, "_rate_limiter", limiter)
    monkeypatch.setattr(
        cardtrader_client.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(),
    )

    for _ in range(11):
        request_cardtrader("GET", "/marketplace/products")

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] >= 1.0


def test_all_endpoints_share_the_global_request_limit(app_context, monkeypatch):
    clock = FakeClock()
    limiter = CardTraderRateLimiter(clock.monotonic, clock.sleep)
    monkeypatch.setattr(cardtrader_client, "_rate_limiter", limiter)
    monkeypatch.setattr(
        cardtrader_client.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(),
    )

    for _ in range(201):
        request_cardtrader("GET", "/cart")

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] >= 10.0


def test_rate_limited_request_respects_retry_after(app_context, monkeypatch):
    responses = iter(
        [FakeResponse(429, {"Retry-After": "2"}), FakeResponse(200)]
    )
    sleep_calls = []
    monkeypatch.setattr(
        cardtrader_client.requests,
        "request",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(cardtrader_client.time, "sleep", sleep_calls.append)

    assert request_cardtrader("GET", "/cart") == {}
    assert sleep_calls == [2.0]
