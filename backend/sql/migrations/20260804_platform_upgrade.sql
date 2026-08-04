-- 20260804 platform upgrade
-- A2: fx_rates（匯率不再只存在記憶體）
-- A4: fifo_checkpoints（FIFO 增量結算）+ trades.updated_at
-- A5: tickers / corporate_actions / price_history

-- ---------------------------------------------------------------
-- A5-1. tickers：標的主檔（取代硬編的 OTC_LIST / ETF_LIST / 記憶體公司名稱快取）
-- ---------------------------------------------------------------
create table if not exists tickers (
  symbol      text primary key,          -- 'TW:2330' / 'NVDA'
  ticker      text not null,
  name        text,
  market      text,                      -- 'TWSE' | 'TPEX' | 'US'
  is_etf      boolean not null default false,
  currency    text not null default 'TWD',
  sector      text,
  meta        jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

create index if not exists idx_tickers_ticker on tickers(ticker);

-- 從既有常數種入台股 ETF（賣出稅率 0.1%）
insert into tickers (symbol, ticker, name, market, is_etf, currency)
values
  ('TW:0050',   '0050',   '元大台灣50',   'TWSE', true, 'TWD'),
  ('TW:00981A', '00981A', '主動統一台股', 'TPEX', true, 'TWD')
on conflict (symbol) do nothing;


-- ---------------------------------------------------------------
-- A5-2. corporate_actions：分割與配息
-- 原則：永遠不改寫 trades 原始紀錄，只在 FIFO 計算時套用調整
-- ---------------------------------------------------------------
create table if not exists corporate_actions (
  id          uuid primary key default gen_random_uuid(),
  symbol      text not null,
  ticker      text not null,
  action_type text not null check (action_type in ('split', 'reverse_split', 'cash_dividend', 'stock_dividend')),
  ex_date     date not null,
  ratio       numeric,                   -- split: 1 股變 N 股（N=4 表示 1:4 分割）
  amount      numeric,                   -- cash_dividend: 每股金額
  currency    text,
  source      text default 'manual',
  note        text default '',
  created_at  timestamptz not null default now(),
  unique (symbol, action_type, ex_date)
);

create index if not exists idx_corporate_actions_symbol_date
  on corporate_actions(symbol, ex_date);

-- 分割類（含配股）必須有 ratio；現金股利必須有 amount
alter table corporate_actions drop constraint if exists corporate_actions_payload_check;
alter table corporate_actions add constraint corporate_actions_payload_check check (
  (action_type in ('split', 'reverse_split', 'stock_dividend') and ratio is not null and ratio > 0)
  or
  (action_type = 'cash_dividend' and amount is not null)
);


-- ---------------------------------------------------------------
-- A5-3. price_history：日線 OHLCV（技術分析與回測的基礎）
-- ---------------------------------------------------------------
create table if not exists price_history (
  symbol     text not null,
  date       date not null,
  open       numeric,
  high       numeric,
  low        numeric,
  close      numeric,
  adj_close  numeric,
  volume     numeric,
  source     text default 'fugle',
  created_at timestamptz not null default now(),
  primary key (symbol, date)
);

create index if not exists idx_price_history_symbol_date
  on price_history(symbol, date desc);


-- ---------------------------------------------------------------
-- A2. fx_rates：匯率落地，serverless 冷啟動後不再遺失
-- ---------------------------------------------------------------
create table if not exists fx_rates (
  pair       text primary key,           -- 'USD/TWD'
  rate       numeric not null,
  source     text,
  fetched_at timestamptz not null default now()
);


-- ---------------------------------------------------------------
-- A4-1. trades.updated_at：偵測「近 12 小時是否有異動」需要它
-- ---------------------------------------------------------------
alter table trades add column if not exists updated_at timestamptz default now();

update trades set updated_at = coalesce(updated_at, created_at, now())
where updated_at is null;

create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_trades_updated_at on trades;
create trigger trg_trades_updated_at
  before update on trades
  for each row execute function set_updated_at();

create index if not exists idx_trades_updated_at on trades(updated_at desc);


-- ---------------------------------------------------------------
-- A4-2. fifo_checkpoints：FIFO 增量結算
-- 每個 checkpoint 存「截至 as_of_date 收盤為止」的 FIFO 狀態，
-- 之後只需套用 date > as_of_date 的交易。
-- ---------------------------------------------------------------
create table if not exists fifo_checkpoints (
  account                text not null,
  ticker                 text not null,
  as_of_date             date not null,
  lots                   jsonb not null default '[]'::jsonb,
  total_cost             numeric not null default 0,
  realized_pnl           numeric not null default 0,
  total_fee              numeric not null default 0,
  total_tax              numeric not null default 0,
  unmatched_sell_balance numeric not null default 0,
  unmatched_sell_qty     numeric not null default 0,
  unmatched_sell_value   numeric not null default 0,
  trade_count            integer not null default 0,   -- 用來偵測 checkpoint 是否失效
  created_at             timestamptz not null default now(),
  primary key (account, ticker, as_of_date)
);

create index if not exists idx_fifo_checkpoints_lookup
  on fifo_checkpoints(account, ticker, as_of_date desc);


-- ---------------------------------------------------------------
-- A4-3. job_runs：記錄排程執行狀況，取代不可靠的記憶體狀態機
-- ---------------------------------------------------------------
create table if not exists job_runs (
  job_name    text primary key,
  last_run_at timestamptz,
  last_ok_at  timestamptz,
  last_error  text,
  payload     jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);
