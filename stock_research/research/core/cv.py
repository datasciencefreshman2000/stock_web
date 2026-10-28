"""時序交叉驗證：purge 與 embargo。

為什麼需要：標籤 horizon = 20 天時，相鄰兩天的標籤有 19/20 內容重疊。
隨機 K-fold 會把幾乎相同的樣本同時放進訓練與測試集，模型等於看過答案。

實測（見 docs/backtest_methodology.md）：
在特徵與價格完全無關的資料上，隨機 K-fold 憑空生出 +1.5% 的假預測力。
"""

from dataclasses import dataclass

import numpy as np


def effective_sample_size(n_rows: int, horizon: int) -> int:
    """有效獨立樣本數的粗估。

    2,000 天資料 + 20 天標籤 → 約 100 個獨立觀測，不是 2,000 個。
    這個數字決定你的模型能有多複雜。
    """
    return max(int(n_rows / max(horizon, 1)), 1)


@dataclass(frozen=True)
class PurgedSplit:
    train: np.ndarray
    test: np.ndarray


def purged_walk_forward(
    n_samples: int,
    n_splits: int = 5,
    horizon: int = 20,
    embargo: int = 5,
    expanding: bool = True,
) -> list[PurgedSplit]:
    """往前滾動的時序切分，訓練集尾端做 purge，測試集後方留 embargo。

    參數
    ----
    horizon  : 標籤往前看幾天。訓練集要刪掉最後 horizon 筆，
               因為它們的標籤仍與測試期重疊。
    embargo  : 測試期結束後再空幾天才恢復使用，處理序列相關的殘留。
    expanding: True 為擴張窗（用到目前為止全部歷史），
               False 為滾動窗（只用固定長度的近期資料）。
    """
    if n_splits < 2:
        raise ValueError("n_splits 至少要 2")

    folds = np.array_split(np.arange(n_samples), n_splits)
    splits: list[PurgedSplit] = []

    for i in range(1, n_splits):
        test = folds[i]
        if expanding:
            train = np.concatenate(folds[:i])
        else:
            train = folds[i - 1]

        # purge：刪掉標籤仍會延伸到測試期的訓練樣本
        train = train[train < test[0] - horizon]

        # embargo：測試期之後的一小段也不能用（若訓練集含未來段落）
        if embargo > 0:
            forbidden = np.arange(test[-1] + 1, min(test[-1] + 1 + embargo, n_samples))
            train = np.setdiff1d(train, forbidden, assume_unique=False)

        if len(train) == 0 or len(test) == 0:
            continue
        splits.append(PurgedSplit(train=train, test=test))

    return splits


def train_test_by_date(dates, split_date) -> tuple[np.ndarray, np.ndarray]:
    """依日期切樣本內／樣本外。

    **樣本外只能驗證一次。**
    如果你因為樣本外結果不好而回頭調參，這道防線就失效了，
    跟樣本內沒有任何差別。
    """
    import pandas as pd

    dates = pd.to_datetime(pd.Series(list(dates))).to_numpy()
    cutoff = np.datetime64(pd.Timestamp(split_date))
    in_sample = np.where(dates < cutoff)[0]
    out_sample = np.where(dates >= cutoff)[0]
    return in_sample, out_sample
