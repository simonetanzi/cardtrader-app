from availability import cart_item_matches_watchlist_entry, product_filter_failure_reason


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
