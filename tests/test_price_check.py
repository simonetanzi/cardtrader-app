from cardtrader_client import CardTraderError
from price_check import run_price_check


class FakeWatchlistItem:
    id = 1
    blueprint_id = 6
    name = "Fury"
    version = None
    game_id = 1
    expansion_name = "Commander: Lorwyn Eclipsed"
    collector_number = "123"
    image_url = None
    max_price_cents = 200
    minimum_condition = "Moderately Played"

    def to_check_dict(self):
        return {
            "id": self.id,
            "blueprint_id": self.blueprint_id,
            "name": self.name,
            "version": self.version,
            "game_id": self.game_id,
            "expansion_name": self.expansion_name,
            "collector_number": self.collector_number,
            "image_url": self.image_url,
            "max_price_cents": self.max_price_cents,
            "allowed_languages": ["en"],
            "minimum_condition": self.minimum_condition,
        }


def make_product(product_id, quantity=1):
    return {
        "id": product_id,
        "quantity": quantity,
        "price_cents": 150,
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


def test_stale_cart_add_error_rejects_only_that_offer(monkeypatch):
    products = [make_product(101), make_product(202, quantity=2)]

    def fake_verify(product, _item_data):
        if product["id"] == 101:
            raise CardTraderError(
                "CardTrader could not complete the request (status 422).",
                path="/cart/add",
                status_code=422,
                error_code="validation_error",
            )
        return dict(product, cart_verified=True, verified_quantity=product["quantity"]), None

    monkeypatch.setattr("price_check.fetch_marketplace_products", lambda *_args: products)
    monkeypatch.setattr("price_check.verify_product_available_through_cart", fake_verify)

    report = run_price_check([FakeWatchlistItem()])
    result = report["results"][0]

    assert report["api_error"] is None
    assert result["skipped"] is False
    assert result["offers_count"] == 1
    assert result["cards_count"] == 2
    assert result["offers"][0]["id"] == 202


def test_non_offer_level_cardtrader_error_still_skips_card(monkeypatch):
    product = make_product(101)

    monkeypatch.setattr("price_check.fetch_marketplace_products", lambda *_args: [product])
    monkeypatch.setattr(
        "price_check.verify_product_available_through_cart",
        lambda *_args: (_ for _ in ()).throw(CardTraderError("CardTrader rejected the API token.")),
    )

    report = run_price_check([FakeWatchlistItem()])
    result = report["results"][0]

    assert report["api_error"] == "CardTrader rejected the API token."
    assert result["skipped"] is True
    assert result["offers_count"] == 0
