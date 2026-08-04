from services.fees import calc_tw_fee, calc_tw_tax


def test_fee_uses_broker_discount_and_truncates():
    # 100 * 1000 * 0.001425 * 0.6 = 85.5 → 無條件捨去
    assert calc_tw_fee(100, 1000) == 85


def test_fee_has_minimum_of_one():
    assert calc_tw_fee(10, 1) == 1
    assert calc_tw_fee(0.01, 1) == 1


def test_general_stock_tax_is_three_permille():
    assert calc_tw_tax(100, 1000, "2330", is_etf=False) == 300


def test_etf_tax_is_one_permille():
    assert calc_tw_tax(100, 1000, "0050", is_etf=True) == 100


def test_etf_flag_falls_back_to_builtin_list():
    # 未傳 is_etf 時退回硬編清單，0050 應視為 ETF
    assert calc_tw_tax(100, 1000, "0050") == 100
    assert calc_tw_tax(100, 1000, "2330") == 300
