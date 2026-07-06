import pytest

from cardtrader_client import CardTraderError, request_cardtrader


def test_blocks_purchase_endpoint(app_context):
    with pytest.raises(CardTraderError):
        request_cardtrader("POST", "/cart/purchase")
