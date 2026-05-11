alter table cash_accounts add column if not exists category text default '現金';
alter table cash_accounts add column if not exists account text default '台股';
alter table cash_accounts drop constraint if exists cash_accounts_amount_check;

update cash_accounts set category = '現金' where category is null;
update cash_accounts set account = '台股' where account is null;

insert into cash_accounts (name, category, currency, amount)
select '新光現金', '現金', 'TWD', 0
where not exists (select 1 from cash_accounts where name = '新光現金');

insert into cash_accounts (name, category, currency, amount)
select '第一現金', '現金', 'TWD', 0
where not exists (select 1 from cash_accounts where name = '第一現金');

insert into cash_accounts (name, category, currency, amount)
select '郵局現金', '現金', 'TWD', 0
where not exists (select 1 from cash_accounts where name = '郵局現金');

insert into cash_accounts (name, category, currency, amount)
select '國泰現金', '現金', 'TWD', 13000
where not exists (select 1 from cash_accounts where name = '國泰現金');

insert into cash_accounts (name, category, currency, amount)
select '外面欠錢 (待收款)', '現金', 'TWD', 0
where not exists (select 1 from cash_accounts where name = '外面欠錢 (待收款)');

insert into cash_accounts (name, category, currency, amount)
select '緊急現金', '現金', 'TWD', 200
where not exists (select 1 from cash_accounts where name = '緊急現金');

insert into cash_accounts (name, category, currency, amount)
select '社團欠錢 (待收款)', '現金', 'TWD', 6000
where not exists (select 1 from cash_accounts where name = '社團欠錢 (待收款)');

insert into cash_accounts (name, category, currency, amount)
select '公司欠錢 (待收款)', '現金', 'TWD', 0
where not exists (select 1 from cash_accounts where name = '公司欠錢 (待收款)');

insert into cash_accounts (name, category, currency, amount)
select '信用卡欠錢', '負債', 'TWD', -1000
where not exists (select 1 from cash_accounts where name = '信用卡欠錢');

insert into cash_accounts (name, category, currency, amount)
select '身上現金', '現金', 'TWD', 500
where not exists (select 1 from cash_accounts where name = '身上現金');
