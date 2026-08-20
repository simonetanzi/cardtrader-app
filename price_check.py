from datetime import datetime

import requests

from availability import (
    get_product_id,
    product_filter_failure_reason,
    verify_product_available_through_cart,
)
from cardtrader_client import CardTraderError, fetch_marketplace_products


def is_offer_level_cart_add_error(error):
    return (
        error.path == "/cart/add"
        and error.status_code == 422
        and error.error_code == "validation_error"
    )


def money_from_cents(cents):
    if cents is None:
        return ""
    return f"EUR {cents / 100:.2f}"


def seller_name(product):
    return (product.get("user", {}) or {}).get("username", "Unknown seller")


def product_condition(product):
    return (product.get("properties_hash", {}) or {}).get("condition", "")


def product_language(product):
    return (product.get("properties_hash", {}) or {}).get("mtg_language", "")


def run_price_check(items):
    results = []
    api_error = None
    total_offers = 0
    total_cards = 0

    for item in items:
        item_data = item.to_check_dict()
        if item_data.get("max_price_cents") is None:
            results.append({
                "item": item,
                "skipped": True,
                "message": "No target price set.",
                "offers": [],
                "offers_count": 0,
                "cards_count": 0,
                "lowest_offer": None,
            })
            continue

        candidates = []
        seen_product_ids = set()
        try:
            for language in item_data["allowed_languages"]:
                products = fetch_marketplace_products(item.blueprint_id, language)
                for product in products:
                    if product_filter_failure_reason(product, item_data) is not None:
                        continue
                    product_id = get_product_id(product)
                    if product_id in seen_product_ids:
                        continue
                    seen_product_ids.add(product_id)
                    candidates.append(product)

            verified_offers = []
            for product in candidates:
                try:
                    verified_product, error = verify_product_available_through_cart(product, item_data)
                except CardTraderError as exc:
                    if is_offer_level_cart_add_error(exc):
                        continue
                    raise
                if verified_product is not None:
                    verified_offers.append(verified_product)

        except (CardTraderError, requests.RequestException) as exc:
            api_error = str(exc)
            results.append({
                "item": item,
                "skipped": True,
                "message": api_error,
                "offers": [],
                "offers_count": 0,
                "cards_count": 0,
                "lowest_offer": None,
            })
            continue

        verified_offers.sort(key=lambda product: product.get("price_cents", 999999999))
        offers_count = len(verified_offers)
        cards_count = sum(product.get("quantity", 0) or 0 for product in verified_offers)
        total_offers += offers_count
        total_cards += cards_count
        results.append({
            "item": item,
            "skipped": False,
            "message": "",
            "offers": verified_offers,
            "offers_count": offers_count,
            "cards_count": cards_count,
            "lowest_offer": verified_offers[0] if verified_offers else None,
        })

    results.sort(
        key=lambda result: (
            len(result.get("offers", [])),
            result.get("lowest_offer", {}).get("price_cents", 999999999)
            if result.get("lowest_offer") else 999999999,
        ),
        reverse=True,
    )

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "api_error": api_error,
        "total_offers": total_offers,
        "total_cards": total_cards,
        "results": results,
    }
