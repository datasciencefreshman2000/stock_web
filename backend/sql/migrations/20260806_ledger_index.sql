-- 記帳紀錄頁的排序索引
--
-- list_capital_movements() 是 order by movement_date desc, created_at desc，
-- 但既有索引只有 movement_date 單欄，同一天有多筆時仍要排序。
-- 記帳是同一天連續好幾筆的情境，這個複合索引才對得上實際查詢。

create index if not exists idx_capital_movements_date_created
  on capital_movements(movement_date desc, created_at desc);

-- 資金移動每次都要用 (名稱, 幣別) 找現金列
create index if not exists idx_cash_accounts_name_currency
  on cash_accounts(name, currency);
