alter table manual_values drop constraint if exists manual_values_key_check;

insert into manual_values (key, value)
values
  ('morgan_cost', 74000),
  ('nomura_cost', 47500),
  ('crypto_cost', 68785)
on conflict (key) do nothing;

create table if not exists price_cache (
  symbol text primary key,
  ticker text not null,
  account text,
  price numeric,
  currency text,
  fetched_at timestamptz default now(),
  source text default 'finnhub'
);
