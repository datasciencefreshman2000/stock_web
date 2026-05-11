alter table cash_accounts add column if not exists account text default '台股';
alter table cash_accounts add column if not exists category text default '現金';
alter table cash_accounts drop constraint if exists cash_accounts_currency_check;
alter table cash_accounts drop constraint if exists cash_accounts_amount_check;

update cash_accounts set account = '台股' where account is null;
update cash_accounts set category = '現金' where category is null;

alter table manual_values drop constraint if exists manual_values_key_check;

insert into manual_values (key, value)
values
  ('invested_台股', 0),
  ('invested_美股', 0),
  ('invested_爸媽美股', 0),
  ('invested_x', 0)
on conflict (key) do nothing;
