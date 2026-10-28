from pathlib import Path
import sys
import json
import time
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.core import data


def test_adjusted_open_and_close_use_same_basis():
    source=pd.DataFrame({'open':[100.], 'high':[110.], 'low':[90.], 'close':[100.], 'adj_close':[50.]})
    result=data.adjust_ohlc(source)
    assert result.iloc[0]['open']==50
    assert result.iloc[0]['close']==50
    assert result.iloc[0]['high']==55


def test_subset_cache_is_not_reused_as_full_universe(tmp_path,monkeypatch):
    cache=tmp_path/'prices.parquet'; meta=tmp_path/'prices.meta.json'
    cache.write_text('placeholder')
    monkeypatch.setattr(data,'CACHE',cache);monkeypatch.setattr(data,'CACHE_META',meta)
    meta.write_text(json.dumps({'saved_at':time.time(),'scope':'subset','symbols':['TW:2330'],'price_basis':'adjusted_ohlc_v1'}))
    assert data.load_from_cache() is None
    assert data.load_from_cache(['TW:9999']) is None


def test_invalid_adjusted_price_cannot_enter_backtest():
    with pytest.raises(ValueError): data.adjust_ohlc(pd.DataFrame({'open':[10],'close':[10],'adj_close':[None]}))
