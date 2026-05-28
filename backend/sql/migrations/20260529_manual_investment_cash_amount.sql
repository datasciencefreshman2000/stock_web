alter table manual_investments
  add column if not exists cash_amount numeric not null default 0;
