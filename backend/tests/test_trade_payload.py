import pytest

from routers.trades import prepare_trade_payload


def test_tw_sell_total_subtracts_fee_and_tax():
    payload = prepare_trade_payload(
        {
            "account": "台股",
            "ticker": "2330",
            "date": "2026-08-05",
            "buy_qty": None,
            "sell_qty": 1000,
            "price": 100,
            "fee": 0,
            "note": "",
        }
    )

    assert payload["fee"] == 85
    assert payload["total"] == pytest.approx(100000 - 85 - 300)
