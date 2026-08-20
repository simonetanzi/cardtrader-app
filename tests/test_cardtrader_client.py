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
    def __init__(self, status_code=200, headers=None, json_data=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.json_data = {} if json_data is None else json_data

    def json(self):
        return self.json_data


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


def test_upstream_error_body_is_not_exposed(app_context, monkeypatch):
    monkeypatch.setattr(
        cardtrader_client.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(
            500,
            text="private upstream diagnostic that must not reach a visitor",
        ),
    )

    with pytest.raises(CardTraderError) as raised:
        request_cardtrader("GET", "/cart")

    assert "private upstream diagnostic" not in str(raised.value)
    assert str(raised.value) == "CardTrader could not complete the request (status 500)."


def test_validation_error_keeps_only_structured_classification(app_context, monkeypatch):
    monkeypatch.setattr(
        cardtrader_client.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(
            422,
            json_data={"error_code": "validation_error", "errors": {"private": "detail"}},
            text='{"error_code":"validation_error","errors":{"private":"detail"}}',
        ),
    )

    with pytest.raises(CardTraderError) as raised:
        request_cardtrader("POST", "/cart/add")

    assert raised.value.path == "/cart/add"
    assert raised.value.status_code == 422
    assert raised.value.error_code == "validation_error"
    assert "private" not in str(raised.value)
