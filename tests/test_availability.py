import pytest

import availability
from availability import (
    cart_item_matches_watchlist_entry,
    product_filter_failure_reason,
    verify_product_available_through_cart,
)


def make_entry():
    return {
        "max_price_cents": 100,
        "allowed_languages": ["en"],
        "minimum_condition": "Moderately Played",
    }


def make_product(**overrides):
    product = {
        "id": 123,
        "quantity": 1,
        "price_cents": 99,
        "user": {"can_sell_via_hub": True},
        "properties_hash": {
            "condition": "Near Mint",
            "mtg_language": "en",
            "mtg_foil": False,
            "signed": False,
            "altered": False,
            "graded": False,
            "misprint": False,
        },
    }
    product.update(overrides)
    return product


def make_cart(product_id, quantity):
    return {
        "subcarts": [
            {
                "cart_items": [
                    {
                        "quantity": quantity,
                        "product": make_product(id=product_id),
                    }
                ]
            }
        ]
    }


def test_accepts_good_product():
    assert product_filter_failure_reason(make_product(), make_entry()) is None


def test_accepts_equal_price_because_target_is_inclusive():
    assert product_filter_failure_reason(make_product(price_cents=100), make_entry()) is None


def test_accepts_equal_cart_price_because_target_is_inclusive():
    cart_item = {
        "quantity": 1,
        "product": make_product(price_cents=100),
    }
    assert cart_item_matches_watchlist_entry(cart_item, make_entry()) is None


def test_rejects_price_above_target():
    reason = product_filter_failure_reason(make_product(price_cents=101), make_entry())
    assert "above target" in reason


def test_rejects_cart_price_above_target():
    cart_item = {
        "quantity": 1,
        "product": make_product(price_cents=101),
    }
    reason = cart_item_matches_watchlist_entry(cart_item, make_entry())
    assert "above target" in reason


def test_rejects_zero_quantity():
    reason = product_filter_failure_reason(make_product(quantity=0), make_entry())
    assert "quantity is 0" in reason


def test_rejects_non_ct_zero_candidate():
    reason = product_filter_failure_reason(make_product(user={"can_sell_via_hub": False}), make_entry())
    assert "CT Zero" in reason


def test_rejects_wrong_language():
    product = make_product(properties_hash={"condition": "Near Mint", "mtg_language": "it"})
    reason = product_filter_failure_reason(product, make_entry())
    assert "language" in reason


def test_cart_verification_reports_and_removes_only_the_added_quantity(monkeypatch):
    product = make_product(id=123, quantity=3)
    removed = []

    monkeypatch.setattr(availability, "fetch_cart", lambda: make_cart(123, 2))
    monkeypatch.setattr(
        availability,
        "add_product_to_cart",
        lambda product_id, quantity: make_cart(product_id, 5),
    )
    monkeypatch.setattr(
        availability,
        "remove_product_from_cart",
        lambda product_id, quantity: removed.append((product_id, quantity)),
    )

    verified, error = verify_product_available_through_cart(product, make_entry())

    assert error is None
    assert verified["quantity"] == 3
    assert verified["verified_quantity"] == 3
    assert verified["cart_verified"] is True
    assert removed == [(123, 3)]


def test_cart_verification_cleans_up_when_later_verification_fails(monkeypatch):
    product = make_product(id=123, quantity=2)
    removed = []
    verification_calls = 0

    monkeypatch.setattr(availability, "fetch_cart", lambda: make_cart(123, 0))
    monkeypatch.setattr(
        availability,
        "add_product_to_cart",
        lambda product_id, quantity: make_cart(product_id, quantity),
    )
    monkeypatch.setattr(
        availability,
        "remove_product_from_cart",
        lambda product_id, quantity: removed.append((product_id, quantity)),
    )

    def fail_after_cart_change(_cart, _product_id, _watchlist_entry):
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls == 2:
            raise RuntimeError("later verification failed")
        return 0

    monkeypatch.setattr(
        availability,
        "get_verified_cart_quantity",
        fail_after_cart_change,
    )

    with pytest.raises(RuntimeError, match="later verification failed"):
        verify_product_available_through_cart(product, make_entry())

    assert removed == [(123, 2)]
