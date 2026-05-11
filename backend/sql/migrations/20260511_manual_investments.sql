create table if not exists manual_investments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  asset_type text not null default '其他',
  cost numeric not null default 0,
  value numeric not null default 0,
  currency text not null default 'TWD',
  updated_at timestamptz default now(),
  created_at timestamptz default now()
);

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
