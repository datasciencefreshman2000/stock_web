-- Read-only verification. Run AFTER 20261028100854_reliable_ledger.sql.
-- One result set: the first row is the overall result; every status should be PASS.
with tables_expected(name) as (
  values ('app_state'),('app_operations'),('app_login_attempts'),
         ('balance_adjustments'),('cash_account_merge_backup')
), columns_expected(table_name,column_name) as (
  values ('cash_accounts','account'),('cash_accounts','category'),
         ('cash_accounts','archived_at'),('manual_investments','cash_amount'),
         ('fifo_checkpoints','calculation_version'),
         ('capital_movements','updated_at'),('capital_movements','affects_balance')
), functions_expected(signature) as (
  values ('public.check_app_login_limit()'),('public.lock_app_write()'),
    ('public.bump_app_revision()'),('public.app_touch_row()'),
    ('public.invalidate_trade_checkpoints()'),('public.invalidate_action_checkpoints()'),
    ('public.app_data_revision()'),
    ('public.list_app_trades_page(text,text,date,date,jsonb,integer)'),
    ('public.publish_app_caches(bigint,jsonb)'),('public.read_app_cache(text)'),
    ('public.read_app_caches(text[])'),('public.write_fifo_checkpoints(bigint,jsonb)'),
    ('public.apply_app_operation(text,jsonb,uuid,uuid,bigint,jsonb)')
), checks as (
  select 'table' as kind,name as item,to_regclass('public.'||name) is not null as ok
  from tables_expected
  union all
  select 'column',e.table_name||'.'||e.column_name,exists(
    select 1 from information_schema.columns c where c.table_schema='public'
      and c.table_name=e.table_name and c.column_name=e.column_name
  ) from columns_expected e
  union all
  select 'function',signature,to_regprocedure(signature) is not null from functions_expected
  union all
  select 'index','cash_accounts_active_bucket',exists(
    select 1 from pg_index where indexrelid=to_regclass('public.cash_accounts_active_bucket')
      and indisunique and indisvalid
  )
), permission_tables(name) as (
  values ('app_state'),('app_operations'),('app_login_attempts'),('balance_adjustments'),
    ('cash_account_merge_backup'),('cash_accounts'),('manual_values'),('trades'),('capital_movements')
), duplicates as (
  select name,currency,count(*) as active_rows from public.cash_accounts
  where archived_at is null group by name,currency having count(*)>1
), all_checks as (
  select kind,item,ok,
    case when ok then 'exists' else 'missing or invalid' end as detail from checks
  union all
  select 'table_permissions',t.name,
    c.oid is not null and c.relrowsecurity
      and not has_table_privilege('anon',c.oid,'SELECT,INSERT,UPDATE,DELETE')
      and not has_table_privilege('authenticated',c.oid,'SELECT,INSERT,UPDATE,DELETE')
      and has_table_privilege('service_role',c.oid,'SELECT'),
    'RLS enabled; backend access only'
  from permission_tables t left join pg_class c on c.oid=to_regclass('public.'||t.name)
  union all
  select 'function_permissions',e.signature,
    p.oid is not null and not p.prosecdef
      and not has_function_privilege('anon',p.oid,'EXECUTE')
      and not has_function_privilege('authenticated',p.oid,'EXECUTE')
      and has_function_privilege('service_role',p.oid,'EXECUTE'),
    'SECURITY INVOKER; backend execute only'
  from functions_expected e left join pg_proc p on p.oid=to_regprocedure(e.signature)
  union all
  select 'data','active_cash_duplicates',not exists(select 1 from duplicates),
    (select count(*)::text||' duplicate group(s)' from duplicates)
  union all
  select 'state','app_state',count(*)=1 and coalesce(bool_and(id and revision>=0),false),
    'rows='||count(*)::text||'; revision='||coalesce(max(revision)::text,'missing')
  from public.app_state
)
select kind,item,status,detail from (
  select 0 as sort_order,'summary' as kind,'overall' as item,
    case when bool_and(coalesce(ok,false)) then 'PASS' else 'FAIL' end as status,
    count(*)::text||' checks; '||count(*) filter(where not coalesce(ok,false))::text||' failed' as detail
  from all_checks
  union all
  select 1,kind,item,case when ok then 'PASS' else 'FAIL' end,detail from all_checks
) report order by sort_order,kind,item;
