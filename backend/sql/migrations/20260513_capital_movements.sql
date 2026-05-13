create table if not exists capital_movements (
  id uuid primary key default gen_random_uuid(),
  movement_date date not null,
  from_bucket text,
  to_bucket text not null,
  amount numeric not null check (amount > 0),
  currency text not null default 'TWD',
  to_amount numeric,
  to_currency text,
  note text default '',
  created_at timestamptz default now()
);

create index if not exists idx_capital_movements_date on capital_movements(movement_date desc);
