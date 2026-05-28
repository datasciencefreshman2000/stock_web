create extension if not exists "pgcrypto";

create table if not exists trades (
  id uuid primary key default gen_random_uuid(),
  account text not null check (account in ('台股', '美股', '爸媽美股', 'x')),
  ticker text not null,
  date date,
  buy_qty numeric,
  sell_qty numeric,
  price numeric not null check (price > 0),
  fee numeric default 0,
  total numeric,
  note text default '',
  created_at timestamptz default now(),
  check (
    (coalesce(buy_qty, 0) > 0 and coalesce(sell_qty, 0) = 0)
    or
    (coalesce(sell_qty, 0) > 0 and coalesce(buy_qty, 0) = 0)
  )
);

create index if not exists idx_trades_account_date on trades(account, date);
create index if not exists idx_trades_account_ticker on trades(account, ticker);

create table if not exists manual_values (
  key text primary key,
  value numeric not null check (value >= 0),
  updated_at timestamptz default now()
);

create table if not exists price_cache (
  symbol text primary key,
  ticker text not null,
  account text,
  price numeric,
  currency text,
  fetched_at timestamptz default now(),
  source text default 'finnhub'
);

create table if not exists cash_accounts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  account text default '台股',
  category text default '現金',
  currency text default 'TWD',
  amount numeric default 0,
  updated_at timestamptz default now()
);

create table if not exists manual_investments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  asset_type text not null default '其他',
  cost numeric not null default 0,
  cash_amount numeric not null default 0,
  value numeric not null default 0,
  currency text not null default 'TWD',
  updated_at timestamptz default now(),
  created_at timestamptz default now()
);

insert into manual_values (key, value)
values
  ('morgan_cost', 74000),
  ('morgan_value', 65000),
  ('nomura_cost', 47500),
  ('nomura_value', 26000),
  ('crypto_cost', 68785),
  ('crypto_value', 17039.97)
on conflict (key) do nothing;

insert into manual_investments (name, asset_type, cost, value, currency)
select
  '摩根新興科技',
  '其他',
  coalesce((select value from manual_values where key = 'morgan_cost'), 74000),
  coalesce((select value from manual_values where key = 'morgan_value'), 0),
  'TWD'
where not exists (select 1 from manual_investments where name = '摩根新興科技');

insert into manual_investments (name, asset_type, cost, value, currency)
select
  '野村高科技',
  '其他',
  coalesce((select value from manual_values where key = 'nomura_cost'), 47500),
  coalesce((select value from manual_values where key = 'nomura_value'), 0),
  'TWD'
where not exists (select 1 from manual_investments where name = '野村高科技');

insert into manual_investments (name, asset_type, cost, value, currency)
select
  '加密貨幣',
  '其他',
  coalesce((select value from manual_values where key = 'crypto_cost'), 68785),
  coalesce((select value from manual_values where key = 'crypto_value'), 0),
  'TWD'
where not exists (select 1 from manual_investments where name = '加密貨幣');
