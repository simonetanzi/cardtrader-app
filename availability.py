from catalog import CONDITION_RANK, DEFAULT_LANGUAGES, DEFAULT_MINIMUM_CONDITION
from cardtrader_client import add_product_to_cart, fetch_cart, remove_product_from_cart


def condition_is_good_enough(product_condition, minimum_condition):
    product_rank = CONDITION_RANK.get(product_condition)
    minimum_rank = CONDITION_RANK.get(minimum_condition)
    if product_rank is None or minimum_rank is None:
        return False
    return product_rank <= minimum_rank


def product_filter_failure_reason(product, watchlist_entry):
    quantity = product.get("quantity", 0) or 0
    if quantity <= 0:
        return f"Rejected: quantity is {quantity}."

    max_price_cents = watchlist_entry.get("max_price_cents")
    if max_price_cents is None:
        return "Rejected: watchlist entry has no target price."

    price_cents = product.get("price_cents")
    if price_cents is None:
        return "Rejected: product has no price_cents."
    if price_cents > max_price_cents:
        return f"Rejected: price {price_cents} is above target {max_price_cents}."

    user = product.get("user", {}) or {}
    if not user.get("can_sell_via_hub"):
        return "Rejected: seller cannot sell via hub / CT Zero."

    properties = product.get("properties_hash", {}) or {}
    minimum_condition = watchlist_entry.get("minimum_condition", DEFAULT_MINIMUM_CONDITION)
    if not condition_is_good_enough(properties.get("condition"), minimum_condition):
        return "Rejected: condition is not good enough."

    allowed_languages = watchlist_entry.get("allowed_languages", DEFAULT_LANGUAGES)
    if properties.get("mtg_language") not in allowed_languages:
        return "Rejected: product language is not allowed."

    for flag in ("mtg_foil", "signed", "altered", "graded", "misprint"):
        if properties.get(flag) is True:
            return f"Rejected: product is {flag}."

    return None


def get_product_id(product):
    return product.get("id")


def get_cart_items_for_product(cart, product_id):
    if not isinstance(cart, dict):
        return []

    wanted_id = str(product_id)
    matching_items = []
    for subcart in cart.get("subcarts", []) or []:
        for cart_item in subcart.get("cart_items", []) or []:
            product = cart_item.get("product", {}) or {}
            if str(product.get("id")) == wanted_id:
                matching_items.append(cart_item)
    return matching_items


def cart_item_matches_watchlist_entry(cart_item, watchlist_entry):
    if not isinstance(cart_item, dict):
        return "Rejected cart item: invalid item."

    product = cart_item.get("product", {}) or {}
    quantity = cart_item.get("quantity", 0) or 0
    if quantity <= 0:
        return f"Rejected cart item: quantity is {quantity}."

    max_price_cents = watchlist_entry.get("max_price_cents")
    price_cents = product.get("price_cents")
    if price_cents is not None and max_price_cents is not None and price_cents > max_price_cents:
        return "Rejected cart item: price is above target."

    properties = product.get("properties_hash", {}) or {}
    cart_condition = properties.get("condition")
    minimum_condition = watchlist_entry.get("minimum_condition", DEFAULT_MINIMUM_CONDITION)
    if cart_condition is not None and not condition_is_good_enough(cart_condition, minimum_condition):
        return "Rejected cart item: condition is not good enough."

    cart_language = properties.get("mtg_language")
    allowed_languages = watchlist_entry.get("allowed_languages", DEFAULT_LANGUAGES)
    if cart_language is not None and cart_language not in allowed_languages:
        return "Rejected cart item: language is not allowed."

    for flag in ("mtg_foil", "signed", "altered", "graded", "misprint"):
        if properties.get(flag) is True:
            return f"Rejected cart item: product is {flag}."

    user = product.get("user", {}) or {}
    if "can_sell_via_hub" in user and not user.get("can_sell_via_hub"):
        return "Rejected cart item: seller cannot sell via hub."

    return None


def get_verified_cart_quantity(cart, product_id, watchlist_entry):
    total = 0
    for cart_item in get_cart_items_for_product(cart, product_id):
        if cart_item_matches_watchlist_entry(cart_item, watchlist_entry) is None:
            total += cart_item.get("quantity", 0) or 0
    return total


def make_verified_product_copy(product, verified_quantity):
    verified_product = dict(product)
    verified_product["quantity"] = verified_quantity
    verified_product["verified_quantity"] = verified_quantity
    verified_product["cart_verified"] = True
    return verified_product


def verify_product_available_through_cart(product, watchlist_entry):
    product_id = get_product_id(product)
    if product_id is None:
        return None, "Marketplace product has no product ID."

    requested_quantity = product.get("quantity", 0) or 0
    if requested_quantity <= 0:
        return None, "Marketplace product has no positive quantity."

    added_quantity = 0
    try:
        cart_before = fetch_cart()
        simple_before = sum(
            item.get("quantity", 0) or 0
            for item in get_cart_items_for_product(cart_before, product_id)
        )
        verified_before = get_verified_cart_quantity(cart_before, product_id, watchlist_entry)

        cart_after_add = add_product_to_cart(product_id, requested_quantity)
        simple_after = sum(
            item.get("quantity", 0) or 0
            for item in get_cart_items_for_product(cart_after_add, product_id)
        )
        added_quantity = max(0, simple_after - simple_before)
        verified_after = get_verified_cart_quantity(cart_after_add, product_id, watchlist_entry)
        verified_quantity = max(0, verified_after - verified_before)

        if verified_quantity <= 0:
            return None, "Product did not pass cart verification."
        return make_verified_product_copy(product, verified_quantity), None
    finally:
        if added_quantity > 0:
            remove_product_from_cart(product_id, added_quantity)
