create table if not exists account_daily_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_date date not null,
  account text not null,
  currency text not null default 'TWD',
  account_total numeric not null default 0,
  account_total_twd numeric not null default 0,
  market_value numeric not null default 0,
  market_value_twd numeric not null default 0,
  cash numeric not null default 0,
  cash_twd numeric not null default 0,
  invested numeric not null default 0,
  invested_twd numeric not null default 0,
  realized_pnl numeric not null default 0,
  realized_pnl_twd numeric not null default 0,
  unrealized_pnl numeric not null default 0,
  unrealized_pnl_twd numeric not null default 0,
  allocation jsonb not null default '{}'::jsonb,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (snapshot_date, account)
);

create index if not exists idx_account_daily_snapshots_date
  on account_daily_snapshots(snapshot_date desc);

create index if not exists idx_account_daily_snapshots_account_date
  on account_daily_snapshots(account, snapshot_date desc);
