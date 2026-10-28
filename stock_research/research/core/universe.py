"""股票池建構與診斷。

核心原則：**股票池要配合你的問題，不是有什麼就用什麼。**

  「這個訊號本身有沒有用？」        → 需要寬廣、無偏的池
  「這個訊號在我會買的股票上有用嗎？」→ 用你自己的持股池才對

兩者都合理，但結論不能互相推論。
"""

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ============================================================ 有效分散檔數


def effective_holdings(weights) -> float:
    """有效分散檔數 = 1 / Σw²（Herfindahl 指數的倒數）。

    實測：0050 名目持有 50 檔，但台積電權重 57–61%，
    有效分散檔數只有 **2.7–3.0 檔**。

    也就是說「買 0050 = 分散投資 50 檔」是錯覺，
    它比較接近「買 3 檔股票，其中一檔佔六成」。
    """
    w = np.asarray(list(weights), dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if len(w) == 0:
        return 0.0
    w = w / w.sum()
    return float(1.0 / np.sum(w ** 2))


def concentration_report(weights: dict[str, float]) -> str:
    items = sorted(weights.items(), key=lambda kv: -kv[1])
    total = sum(weights.values())
    lines = [
        f"名目檔數        {len(weights)}",
        f"最大單一權重    {items[0][1]/total:.1%}  ({items[0][0]})",
        f"前十大合計      {sum(v for _, v in items[:10])/total:.1%}",
        f"有效分散檔數    {effective_holdings(weights.values()):.2f}",
    ]
    return "\n".join(lines)


# ============================================================ 池的建構


@dataclass(frozen=True)
class UniverseConfig:
    """股票池篩選條件。全部都是 point-in-time 可觀測的量。"""

    min_history_days: int = 250      # 至少上市滿一年，避免新股的異常波動
    min_avg_turnover: float = 1e7    # 近 60 日平均成交金額下限（元）
    turnover_window: int = 60
    max_symbols: int | None = None   # 只留成交金額前 N 名


def build_universe(df: pd.DataFrame, config: UniverseConfig | None = None) -> pd.DataFrame:
    """依「當下可觀測的條件」逐日建立股票池。

    關鍵：篩選條件只能用**當天以前**的資料。
    絕對不能用「這檔股票後來變得很大」這種未來資訊。

    參數
    ----
    df : 需含 symbol, date, close, volume

    回傳
    ----
    在 df 上新增 in_universe 欄位（布林）
    """
    config = config or UniverseConfig()
    out = []

    for symbol, g in df.groupby("symbol", sort=False):
        g = g.sort_values("date").copy()
        g["days_listed"] = np.arange(len(g))
        turnover = g["close"] * g["volume"]
        # 用 shift(1) 確保只用到「昨天以前」的資訊
        g["avg_turnover"] = turnover.rolling(config.turnover_window).mean().shift(1)
        g["in_universe"] = (
            (g["days_listed"] >= config.min_history_days)
            & (g["avg_turnover"] >= config.min_avg_turnover)
        )
        out.append(g)

    result = pd.concat(out, ignore_index=True)

    if config.max_symbols:
        # 每天只留成交金額前 N 名（用排名而非 apply，避免 pandas 的分組欄位警告）
        rank = (
            result["avg_turnover"]
            .where(result["in_universe"])
            .groupby(result["date"])
            .rank(ascending=False, method="first")
        )
        result["in_universe"] = result["in_universe"] & (rank <= config.max_symbols)

    return result.reset_index(drop=True)


# ============================================================ 偏誤診斷


@dataclass
class UniverseDiagnostics:
    n_symbols: int
    n_rows: int
    date_range: tuple
    symbols_alive_at_end: int
    survivorship_ratio: float
    median_history_days: float
    turnover_p10: float
    warnings: list[str]

    def report(self) -> str:
        lines = [
            f"標的數              {self.n_symbols}",
            f"資料列數            {self.n_rows:,}",
            f"期間                {self.date_range[0]:%Y-%m-%d} ~ {self.date_range[1]:%Y-%m-%d}",
            f"期末仍有資料的標的  {self.symbols_alive_at_end} / {self.n_symbols}"
            f"  ({self.survivorship_ratio:.0%})",
            f"歷史長度中位數      {self.median_history_days:.0f} 天",
            f"成交金額 10 百分位  {self.turnover_p10:,.0f} 元",
        ]
        if self.warnings:
            lines.append("\n⚠ 警告：")
            lines += [f"   - {w}" for w in self.warnings]
        return "\n".join(lines)


def diagnose(df: pd.DataFrame) -> UniverseDiagnostics:
    """檢查股票池有沒有明顯的偏誤問題。跑回測前先跑這個。"""
    last_date = df["date"].max()
    per_symbol = df.groupby("symbol")["date"]
    alive = (per_symbol.max() >= last_date - pd.Timedelta(days=10)).sum()
    n = df["symbol"].nunique()
    ratio = alive / n if n else 0.0

    turnover = (df["close"] * df["volume"])
    warnings: list[str] = []

    if ratio > 0.98:
        warnings.append(
            "幾乎所有標的到期末都還存在 —— 極可能有倖存者偏誤。"
            "真實市場 16 年間通常有 5–15% 的標的下市。"
            "回測結果會系統性高估（模擬顯示約每年 1–3%）。"
        )
    if n < 30:
        warnings.append(f"標的數只有 {n} 檔，橫斷面策略的統計檢定力會很弱。")
    if df.groupby("symbol").size().median() < 500:
        warnings.append("多數標的歷史不足兩年，動能類研究（需 12 個月形成期）會樣本不足。")
    q10 = float(turnover.quantile(0.10))
    if q10 < 5e6:
        warnings.append(
            f"最低 10% 的標的日成交金額僅 {q10:,.0f} 元，"
            "回測假設能買到的量要設上限，否則會高估。"
        )

    return UniverseDiagnostics(
        n_symbols=n,
        n_rows=len(df),
        date_range=(df["date"].min(), last_date),
        symbols_alive_at_end=int(alive),
        survivorship_ratio=float(ratio),
        median_history_days=float(df.groupby("symbol").size().median()),
        turnover_p10=q10,
        warnings=warnings,
    )


# ============================================================ 預設股票池


#: 你歷史上交易過的台股。貼近實用，但有強烈選擇偏誤——
#: 這些是「你挑過的股票」，不是市場的隨機樣本。
#: 適合回答「這訊號在我會買的股票上有沒有用」，
#: 不適合回答「這訊號本身有沒有用」。
MY_HOLDINGS = [
    "0050", "00981A", "1303", "1514", "1519", "1802", "2303", "2308", "2317",
    "2330", "2337", "2344", "2368", "2371", "2382", "2383", "2408", "2449",
    "2454", "2455", "3017", "3037", "3081", "3189", "3264", "3324", "3555",
    "3661", "3665", "3706", "3711", "4958", "4971", "6442", "6869", "6919",
    "7871", "8046", "8299",
]

#: 大盤 benchmark。算相對強度與對照組時用。
BENCHMARK = "0050"


def to_symbols(tickers: list[str]) -> list[str]:
    """台股代號加上 TW: 前綴，與 price_history 表一致。"""
    return [f"TW:{t.strip().upper()}" for t in tickers]


# ============================================================ 主題型股票池


#: 你實際交易過的標的中文名稱。
NAMES: dict[str, str] = {
    "0050": "元大台灣50", "00981A": "統一台股增長主動",
    "1303": "南亞", "1514": "亞力", "1519": "華城", "1802": "台玻",
    "2303": "聯電", "2308": "台達電", "2317": "鴻海", "2330": "台積電",
    "2337": "旺宏", "2344": "華邦電", "2368": "金像電", "2371": "大同",
    "2382": "廣達", "2383": "台光電", "2408": "南亞科", "2449": "京元電子",
    "2454": "聯發科", "2455": "全新", "3017": "奇鋐", "3037": "欣興",
    "3081": "聯亞", "3189": "景碩", "3264": "欣銓", "3324": "雙鴻",
    "3555": "重鵬", "3661": "世芯-KY", "3665": "貿聯-KY", "3706": "神達",
    "3711": "日月光投控", "4958": "臻鼎-KY", "4971": "IET-KY 英特磊",
    "6442": "光聖", "6869": "雲豹能源", "6919": "康霈*", "7871": "安立璽榮-KY",
    "8046": "南電", "8299": "群聯",
}

#: 主題分組（全部來自你自己交易過的標的）。
#: **這些分組是「假設」不是事實** —— 用 validate_theme() 驗證後再用。
#: 每組後面的註解是「你相信它們一起漲跌的原因」，說不出機制的分組不該存在。
THEMES: dict[str, list[str]] = {
    # ★ 首選：驅動因子最明確、歷史最長、你交易最活躍
    "記憶體": ["2337", "2344", "2408"],          # DRAM/NAND 現貨報價循環
    # ★ 次選：市場公認的「載板三雄」，ABF 載板供需
    "ABF載板": ["3037", "3189", "8046"],         # AI/HPC 晶片對高階載板的需求
    # ⚠ 教學用：很可能驗證失敗（AI 用電題材是 2023 後才有）
    "重電": ["1514", "1519", "2371"],            # 台電電網強韌計畫 + AI 資料中心用電
    "化合物半導體": ["2455", "3081", "4971"],      # 砷化鎵/磷化銦磊晶，光通訊需求
    "PCB材料": ["2368", "2383", "4958"],          # CCL 與一般 PCB，層次不同
    # 只有 2 檔，樣本數是硬傷，但你要求納入
    "散熱": ["3017", "3324"],                     # 伺服器散熱需求
    "半導體測試": ["2449", "3264"],                # 晶圓/成品測試產能
    "晶圓代工": ["2330", "2303"],
}

#: 想過但沒納入的分組，保留理由供日後參考。
CANDIDATE_THEMES: dict[str, tuple[list[str], str]] = {
    "AI伺服器": (["2317", "2382", "3706"],
                 "鴻海營收 6 兆、神達不到千億，AI 伺服器佔各自營收比例差太多，主題純度低"),
}

#: 無法歸入任何主題的標的。單獨分析可以，但樣本數會是硬傷。
UNGROUPED: dict[str, str] = {
    "2454": "IC設計龍頭，台股沒有可比對象",
    "3711": "封測龍頭，規模與 2449/3264 差太多",
    "3661": "ASIC 設計，獨立性高",
    "3665": "連接線束",
    "3555": "電子通路商，非製造業",
    "6442": "光通訊，可考慮併入化合物半導體",
    "2308": "電源+散熱+車用，業務太多元，無法歸入單一主題",
    "8299": "記憶體『控制IC』，驅動因子與記憶體本身不同（設計 vs 報價循環）",
    "2317": "AI伺服器組裝，業務多元度太高（見 CANDIDATE_THEMES）",
    "2382": "AI伺服器，與鴻海/神達規模差異大",
    "3706": "AI伺服器，規模最小",
    "6869": "綠能",
    "1303": "塑化", "1802": "玻璃",
    "7871": "生技（無獲利）", "6919": "生技（無獲利）",
    "0050": "ETF，當 benchmark 用",
    "00981A": "主動型 ETF，成立時間短",
}


@dataclass
class ThemeValidation:
    """主題的內聚度診斷。"""

    theme: str
    members: list[str]
    n_days: int
    raw_pairwise_corr: float          # 原始配對相關（含市場因子）
    residual_pairwise_corr: float     # 剝掉市場因子後的殘差相關 ← 真正的判準
    control_corr: float               # 對照組：不同主題配對的殘差相關
    z_score: float
    first_pc_explained: float
    weakest_member: str | None
    verdict: str

    def report(self) -> str:
        lines = [
            f"主題：{self.theme}（{', '.join(self.members)}）",
            f"  共同交易日數        {self.n_days:,}",
            f"  原始配對相關        {self.raw_pairwise_corr:+.3f}（含市場因子，參考用）",
            f"  殘差配對相關        {self.residual_pairwise_corr:+.3f} ← 判準",
            f"  對照組基準          {self.control_corr:+.3f}",
            f"  z 值                {self.z_score:.2f}",
            f"  第一主成分解釋度    {self.first_pc_explained:.1%}",
        ]
        if self.weakest_member:
            lines.append(f"  最不合群的成員      {self.weakest_member}")
        lines.append(f"  判定：{self.verdict}")
        return "\n".join(lines)


def market_residuals(returns: pd.DataFrame, market: pd.Series) -> pd.DataFrame:
    """剝掉市場因子：對每檔股票跑 r_i = a + b·m + e_i，回傳殘差 e_i。"""
    out = {}
    for col in returns.columns:
        pair = pd.concat([returns[col], market], axis=1).dropna()
        pair.columns = ["y", "x"]
        if len(pair) < 60 or pair["x"].var() == 0:
            continue
        beta = np.cov(pair["y"], pair["x"])[0, 1] / np.var(pair["x"])
        out[col] = pair["y"] - beta * pair["x"]
    return pd.DataFrame(out)


def _mean_pair_corr(cols: list[str], frame: pd.DataFrame) -> float:
    cols = [c for c in cols if c in frame.columns]
    if len(cols) < 2:
        return float("nan")
    m = frame[cols].corr().to_numpy()
    return float(m[np.triu_indices_from(m, k=1)].mean())


def validate_theme(
    prices: pd.DataFrame,
    members: list[str],
    market: pd.Series | None = None,
    theme_name: str = "",
    control_members: list[list[str]] | None = None,
) -> ThemeValidation:
    """檢查一組股票是不是真的構成「主題」。

    **方法論重點（這裡踩過一次坑）：**

    直覺做法是比較「組內配對相關」與「與大盤的相關」，但**這不是蘋果比蘋果**——
    單一股票與「多檔平均」的相關，會因為平均消掉了個別雜訊而系統性偏高。
    用這個比法，所有主題都會被誤判為不成立。

    正確做法：
      1. 先對每檔股票剝掉市場因子（回歸取殘差）
      2. 算組內殘差的配對相關
      3. 跟「不同主題的配對」比較 —— 這才是同一個尺度的對照組

    參數
    ----
    prices          : 寬表，index=date、columns=symbol、值為還原收盤價
    members         : 要檢驗的成員
    market          : 市場代理序列。建議用等權重平均而非 0050
                      （0050 有 60% 是台積電，會扭曲個股的市場相關）
    control_members : 對照組分群。預設用 prices 裡所有非成員的股票兩兩配對
    """
    cols = [m for m in members if m in prices.columns]
    if len(cols) < 2:
        raise ValueError(f"至少要 2 檔才能檢驗主題，目前只有 {cols}")

    rets = prices.pct_change(fill_method=None)
    if market is None:
        market_ret = rets[[c for c in rets.columns]].mean(axis=1)
    else:
        market_ret = market.reindex(rets.index).pct_change(fill_method=None)

    res = market_residuals(rets.dropna(axis=1, how="all"), market_ret).dropna()
    raw = _mean_pair_corr(cols, rets.dropna())
    resid = _mean_pair_corr(cols, res)

    # 對照組：不同群組之間的配對
    if control_members is None:
        groups = [cols] + [[c] for c in res.columns if c not in cols]
    else:
        groups = control_members
    group_of = {c: i for i, g in enumerate(groups) for c in g}
    control = [
        res[a].corr(res[b])
        for a, b in itertools.combinations(res.columns, 2)
        if group_of.get(a, -1) != group_of.get(b, -2)
    ]
    base = float(np.mean(control)) if control else 0.0
    sd = float(np.std(control)) if len(control) > 1 else 1.0
    z = (resid - base) / sd if sd > 0 else float("nan")

    sub = rets[cols].dropna()
    zz = (sub - sub.mean()) / sub.std()
    ev = np.linalg.eigvalsh(np.cov(zz.T.values))[::-1]
    pc1 = float(ev[0] / ev.sum())

    weakest = None
    if len(cols) > 2 and not res.empty:
        rc = res[[c for c in cols if c in res.columns]].corr()
        avg = {c: float(rc[c].drop(c).mean()) for c in rc.columns}
        cand = min(avg, key=avg.get)
        if avg[cand] < resid - 0.05:
            weakest = cand

    if not np.isfinite(z):
        verdict = "資料不足，無法判定"
    elif z > 4:
        verdict = "✅ 主題明確成立"
    elif z > 2:
        verdict = "✅ 主題成立（強度中等）"
    elif z > 1:
        verdict = "⚠ 偏弱，共同驅動因子不明顯"
    else:
        verdict = "❌ 不成立 —— 剝掉市場因子後沒有共同性，這個「主題」只是個故事"

    if pc1 > 0.65 and z > 2:
        verdict += "；但高度同質（PC1 > 65%），分散效果接近於零"

    return ThemeValidation(
        theme=theme_name or "未命名",
        members=cols,
        n_days=len(res),
        raw_pairwise_corr=raw,
        residual_pairwise_corr=resid,
        control_corr=base,
        z_score=z,
        first_pc_explained=pc1,
        weakest_member=weakest,
        verdict=verdict,
    )


def to_wide(df: pd.DataFrame, value: str = "close") -> pd.DataFrame:
    """長表轉寬表：index=date, columns=symbol。"""
    return df.pivot_table(index="date", columns="symbol", values=value)
