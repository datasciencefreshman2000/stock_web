alter table capital_movements
  add column if not exists to_amount numeric,
  add column if not exists to_currency text;
