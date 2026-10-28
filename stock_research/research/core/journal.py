"""研究日誌：強迫記錄「你到底試了幾個變體」。

這是整個專案裡最不起眼、但最重要的一個檔案。

沒有這個記錄，你半年後回頭看只會記得「我試了 RSI，效果不錯」，
不會記得「我試了 RSI 的 9/14/21 三種週期、三種門檻、兩種持有期，
一共 18 個組合，然後挑了最好的那個」。

而這 18 這個數字，決定了你的結果要多好才算數。
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

JOURNAL_DIR = Path(__file__).resolve().parents[2] / "journal"


@dataclass
class Variant:
    """一次參數嘗試。每呼叫一次 record() 就算一個變體。"""

    params: dict
    metric_name: str
    metric_value: float
    n_obs: int
    note: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ResearchLog:
    """一個研究題目的完整記錄。

    用法：

        log = ResearchLog(study="01_short_term_reversal",
                          hypothesis="連續下跌後有均值回歸傾向",
                          mechanism="短期賣壓造成流動性折價")
        log.record({"lookback": 5, "horizon": 20}, "net_return", 0.012, n_obs=3200)
        ...
        log.save()
        print(log.variants_tested)   # ← 拿這個去做 null 分布檢定
    """

    study: str
    hypothesis: str
    mechanism: str
    falsification: str = ""
    in_sample_end: str = ""
    variants: list[Variant] = field(default_factory=list)
    out_of_sample_used: bool = False
    notes: list[str] = field(default_factory=list)

    def record(self, params: dict, metric_name: str, metric_value: float,
               n_obs: int, note: str = "") -> Variant:
        v = Variant(params=dict(params), metric_name=metric_name,
                    metric_value=float(metric_value), n_obs=int(n_obs), note=note)
        self.variants.append(v)
        return v

    @property
    def variants_tested(self) -> int:
        return len(self.variants)

    def best(self, maximize: bool = True) -> Variant | None:
        if not self.variants:
            return None
        return (max if maximize else min)(self.variants, key=lambda v: v.metric_value)

    def mark_out_of_sample_used(self) -> None:
        """樣本外只能用一次。用過就標記起來。

        如果你發現這個旗標已經是 True 又想再跑一次——停下來想想。
        再跑一次，你的樣本外就跟樣本內沒兩樣了。
        """
        if self.out_of_sample_used:
            raise RuntimeError(
                "這個研究的樣本外已經用過一次了。\n"
                "再驗證一次會讓樣本外失效——那等於沒有樣本外。\n"
                "如果你真的要重來，請開一個新的 study 名稱，"
                "並且誠實地把先前的變體數一起算進去。"
            )
        self.out_of_sample_used = True

    def save(self, directory: Path | None = None) -> Path:
        directory = directory or JOURNAL_DIR
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.study}.json"
        payload = asdict(self)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, study: str, directory: Path | None = None) -> "ResearchLog":
        directory = directory or JOURNAL_DIR
        path = directory / f"{study}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        variants = [Variant(**v) for v in data.pop("variants", [])]
        return cls(**data, variants=variants)

    def summary(self) -> str:
        best = self.best()
        lines = [
            f"研究：{self.study}",
            f"假設：{self.hypothesis}",
            f"機制：{self.mechanism}",
            f"可否證：{self.falsification}",
            f"樣本內結束於：{self.in_sample_end or '未設定'}",
            f"試過的變體數：{self.variants_tested}",
        ]
        if best:
            lines.append(f"最佳結果：{best.metric_name} = {best.metric_value:.4f}  {best.params}")
        lines.append(f"樣本外是否已使用：{'是' if self.out_of_sample_used else '否'}")
        return "\n".join(lines)
