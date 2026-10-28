-- Additive upgrade. Existing user rows are retained; duplicate rows are archived.
begin;
alter table public.cash_accounts add column if not exists account text default '';
alter table public.cash_accounts add column if not exists category text default '現金';
alter table public.cash_accounts add column if not exists archived_at timestamptz;
alter table public.manual_investments add column if not exists cash_amount numeric not null default 0;
alter table public.fifo_checkpoints add column if not exists calculation_version integer not null default 1;
alter table public.capital_movements add column if not exists updated_at timestamptz not null default now();
alter table public.capital_movements add column if not exists affects_balance boolean not null default true;

create table if not exists public.app_state (
  id boolean primary key default true check(id),
  revision bigint not null default 0,
  updated_at timestamptz not null default now()
);
insert into public.app_state(id) values(true) on conflict do nothing;
create table if not exists public.app_operations (
  operation_id uuid primary key,
  action text not null,
  request jsonb not null,
  result jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists public.app_login_attempts(window_start timestamptz primary key, attempts integer not null);
create or replace function public.check_app_login_limit() returns boolean language plpgsql security invoker set search_path='' as $$
declare attempts_now integer;
begin
  delete from public.app_login_attempts where window_start<now()-interval '1 day';
  insert into public.app_login_attempts(window_start,attempts) values(date_trunc('minute',now()),1)
  on conflict(window_start) do update set attempts=public.app_login_attempts.attempts+1 returning attempts into attempts_now;
  return attempts_now<=10;
end $$;
create table if not exists public.balance_adjustments (
  id uuid primary key default gen_random_uuid(),
  operation_id uuid not null references public.app_operations(operation_id) deferrable initially deferred,
  kind text not null,
  record_key text not null,
  previous_value numeric not null,
  new_value numeric not null,
  reason text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.cash_account_merge_backup (
  id uuid primary key,
  original_row jsonb not null,
  backed_up_at timestamptz not null default now()
);
create index if not exists balance_adjustments_created_idx on public.balance_adjustments(created_at desc,id desc);
create index if not exists balance_adjustments_record_idx on public.balance_adjustments(kind,record_key,created_at desc);

-- Preserve all originals before consolidating duplicate display buckets.
insert into public.cash_account_merge_backup(id,original_row)
select c.id,to_jsonb(c) from public.cash_accounts c
join (select name,currency from public.cash_accounts where archived_at is null
      group by name,currency having count(*) > 1) d using(name,currency)
on conflict do nothing;
do $$
declare g record; keep_id uuid;
begin
  for g in select name,currency,sum(coalesce(amount,0)) as total
      from public.cash_accounts where archived_at is null group by name,currency having count(*) > 1
  loop
    select id into keep_id from public.cash_accounts where name=g.name and currency=g.currency and archived_at is null order by id limit 1;
    update public.cash_accounts set amount=g.total where id=keep_id;
    update public.cash_accounts set archived_at=now() where name=g.name and currency=g.currency and id<>keep_id and archived_at is null;
  end loop;
end $$;
create unique index if not exists cash_accounts_active_bucket on public.cash_accounts(name,currency) where archived_at is null;
-- Net contributed capital may be negative after withdrawing profits.
alter table public.manual_values drop constraint if exists manual_values_value_check;
alter table public.manual_values add constraint manual_values_value_check check(key like 'invested_%' or value>=0) not valid;

-- Every writer takes the same state lock BEFORE touching business rows.
create or replace function public.lock_app_write() returns trigger language plpgsql security invoker set search_path='' as $$
begin
  perform 1 from public.app_state where id for update;
  return null;
end $$;
create or replace function public.bump_app_revision() returns trigger language plpgsql security invoker set search_path='' as $$
begin
  update public.app_state set revision=revision+1,updated_at=clock_timestamp() where id;
  return null;
end $$;
create or replace function public.app_touch_row() returns trigger language plpgsql security invoker set search_path='' as $$
begin new.updated_at=clock_timestamp(); return new; end $$;
create or replace function public.invalidate_trade_checkpoints() returns trigger language plpgsql security invoker set search_path='' as $$
begin
  if tg_op <> 'INSERT' then
    delete from public.fifo_checkpoints where account=old.account and ticker=old.ticker and as_of_date>=coalesce(old.date,'0001-01-01'::date);
  end if;
  if tg_op <> 'DELETE' then
    delete from public.fifo_checkpoints where account=new.account and ticker=new.ticker and as_of_date>=coalesce(new.date,'0001-01-01'::date);
  end if;
  return null;
end $$;
create or replace function public.invalidate_action_checkpoints() returns trigger language plpgsql security invoker set search_path='' as $$
begin
  if tg_op <> 'INSERT' then
    delete from public.fifo_checkpoints where ticker=old.ticker and as_of_date>=old.ex_date;
  end if;
  if tg_op <> 'DELETE' then
    delete from public.fifo_checkpoints where ticker=new.ticker and as_of_date>=new.ex_date;
  end if;
  return null;
end $$;
do $$
declare t text;
begin
  foreach t in array array['trades','cash_accounts','manual_values','manual_investments','capital_movements','corporate_actions'] loop
    execute format('drop trigger if exists app_lock_write on public.%I',t);
    execute format('create trigger app_lock_write before insert or update or delete on public.%I for each statement execute function public.lock_app_write()',t);
    execute format('drop trigger if exists app_bump_revision on public.%I',t);
    execute format('create trigger app_bump_revision after insert or update or delete on public.%I for each statement execute function public.bump_app_revision()',t);
  end loop;
  foreach t in array array['trades','cash_accounts','manual_values','manual_investments','capital_movements'] loop
    execute format('drop trigger if exists app_touch_row on public.%I',t);
    execute format('create trigger app_touch_row before update on public.%I for each row execute function public.app_touch_row()',t);
  end loop;
end $$;
drop trigger if exists app_invalidate_fifo on public.trades;
create trigger app_invalidate_fifo after insert or update or delete on public.trades for each row execute function public.invalidate_trade_checkpoints();
drop trigger if exists app_invalidate_action_fifo on public.corporate_actions;
create trigger app_invalidate_action_fifo after insert or update or delete on public.corporate_actions for each row execute function public.invalidate_action_checkpoints();

create or replace function public.app_data_revision() returns bigint language sql stable security invoker set search_path='' as $$
  select revision from public.app_state where id;
$$;
create or replace function public.list_app_trades_page(p_account text,p_ticker text default null,p_start date default null,p_end date default null,p_before jsonb default null,p_limit integer default 100)
returns jsonb language sql stable security invoker set search_path='' as $$
  select coalesce(jsonb_agg(to_jsonb(q)),'[]'::jsonb) from (
    select t.* from public.trades t
    where (t.account=p_account or (p_account='__combined__' and t.account in ('台股','美股','爸媽美股')))
      and (p_ticker is null or t.ticker=upper(trim(p_ticker)))
      and (p_start is null or t.date>=p_start) and (p_end is null or t.date<=p_end)
      and (p_before is null or (coalesce(t.date,'0001-01-01'::date),t.created_at,t.id)<
         ((p_before->>'date')::date,(p_before->>'created_at')::timestamptz,(p_before->>'id')::uuid))
    order by coalesce(t.date,'0001-01-01'::date) desc,t.created_at desc,t.id desc limit least(greatest(p_limit,1),200)+1
  ) q;
$$;
create index if not exists idx_trades_cursor on public.trades(account,(coalesce(date,'0001-01-01'::date)) desc,created_at desc,id desc);

create or replace function public.publish_app_caches(p_revision bigint, p_payloads jsonb) returns text
language plpgsql security invoker set search_path='' as $$
declare stamp timestamptz:=clock_timestamp(); item record;
begin
  perform 1 from public.app_state where id for update;
  if (select revision from public.app_state where id) <> p_revision then return null; end if;
  if exists(select 1 from public.summary_cache c join jsonb_each(p_payloads) incoming on incoming.key=c.cache_key where
    (c.payload->>'calculation_started_at')::timestamptz>(incoming.value->>'calculation_started_at')::timestamptz) then return null; end if;
  for item in select * from jsonb_each(p_payloads) loop
    insert into public.summary_cache(cache_key,payload,updated_at)
    values(item.key,item.value || jsonb_build_object('data_revision',p_revision,'valuation_date',((now() at time zone 'Asia/Taipei')::date)::text),stamp)
    on conflict(cache_key) do update set payload=excluded.payload,updated_at=excluded.updated_at;
  end loop;
  return stamp::text;
end $$;
create or replace function public.read_app_cache(p_key text) returns jsonb language sql stable security invoker set search_path='' as $$
  select c.payload || jsonb_build_object('summary_cached',true,'summary_cached_at',c.updated_at)
  from public.summary_cache c, public.app_state s where s.id and c.cache_key=p_key
    and (c.payload->>'data_revision')::bigint=s.revision
    and c.payload->>'valuation_date'=((now() at time zone 'Asia/Taipei')::date)::text;
$$;
create or replace function public.read_app_caches(p_keys text[]) returns jsonb language sql stable security invoker set search_path='' as $$
  select coalesce(jsonb_object_agg(k,public.read_app_cache(k)) filter(where public.read_app_cache(k) is not null),'{}'::jsonb) from unnest(p_keys) k;
$$;
create or replace function public.write_fifo_checkpoints(p_revision bigint,p_rows jsonb) returns boolean language plpgsql security invoker set search_path='' as $$
declare item jsonb;
begin
  perform 1 from public.app_state where id for update;
  if p_revision<>(select revision from public.app_state where id) then return false; end if;
  for item in select value from jsonb_array_elements(p_rows) loop
    insert into public.fifo_checkpoints(account,ticker,as_of_date,lots,total_cost,realized_pnl,total_fee,total_tax,unmatched_sell_balance,unmatched_sell_qty,unmatched_sell_value,trade_count,calculation_version)
    values(item->>'account',item->>'ticker',(item->>'as_of_date')::date,item->'lots',(item->>'total_cost')::numeric,(item->>'realized_pnl')::numeric,(item->>'total_fee')::numeric,(item->>'total_tax')::numeric,(item->>'unmatched_sell_balance')::numeric,(item->>'unmatched_sell_qty')::numeric,(item->>'unmatched_sell_value')::numeric,(item->>'trade_count')::integer,2)
    on conflict(account,ticker,as_of_date) do update set lots=excluded.lots,total_cost=excluded.total_cost,realized_pnl=excluded.realized_pnl,total_fee=excluded.total_fee,total_tax=excluded.total_tax,unmatched_sell_balance=excluded.unmatched_sell_balance,unmatched_sell_qty=excluded.unmatched_sell_qty,unmatched_sell_value=excluded.unmatched_sell_value,trade_count=excluded.trade_count,calculation_version=2;
  end loop;
  return true;
end $$;

-- p_effects are supplied ONLY by the trusted API after a full cash calculation.
-- Revision checking makes that calculation valid at commit; service_role only.
create or replace function public.apply_app_operation(
  p_action text,p_payload jsonb,p_record_id uuid,p_operation_id uuid,
  p_expected_revision bigint default null,p_effects jsonb default '[]'::jsonb
) returns jsonb language plpgsql security invoker set search_path='' as $$
declare
  existing public.app_operations%rowtype; request_data jsonb; result_data jsonb;
  previous_data jsonb; row_data jsonb; item jsonb; effect jsonb;
  row_id uuid; old_amount numeric; new_amount numeric; delta numeric;
  bucket text; curr text; effect_kind text; k text; skipped_correction boolean:=false;
begin
  perform 1 from public.app_state where id for update;
  request_data=jsonb_build_object('payload',p_payload - 'operation_id','record_id',p_record_id);
  select * into existing from public.app_operations where operation_id=p_operation_id;
  if found then
    if existing.action<>p_action or existing.request<>request_data then raise exception using errcode='22023',message='重試識別碼與原操作不一致'; end if;
    return existing.result;
  end if;
  if p_expected_revision is not null and p_expected_revision<>(select revision from public.app_state where id) then
    raise exception using errcode='40001',message='帳務剛被其他操作更新，請重試';
  end if;
  if p_payload->>'currency' is not null and p_payload->>'currency' not in ('TWD','USD') then
    raise exception using errcode='22023',message='幣別只能為 TWD 或 USD';
  end if;
  if p_action like 'movement.%' then
    if p_action<>'movement.create' then
      select to_jsonb(m) into previous_data from public.capital_movements m where id=p_record_id for update;
      if previous_data is null then raise exception using errcode='P0002',message='記帳紀錄不存在'; end if;
    end if;
    if p_payload->>'expected_updated_at' is not null and (previous_data->>'updated_at')::timestamptz<>(p_payload->>'expected_updated_at')::timestamptz then
      raise exception using errcode='40001',message='記帳紀錄已修改';
    end if;
    if p_action<>'movement.delete' then
      if (p_payload->>'amount')::numeric<=0 or coalesce((p_payload->>'to_amount')::numeric,1)<=0 then raise exception using errcode='22023',message='金額必須大於零'; end if;
      curr=coalesce(p_payload->>'to_currency',p_payload->>'currency');
      if curr not in ('TWD','USD') or (curr<>p_payload->>'currency' and p_payload->>'to_amount' is null) then raise exception using errcode='22023',message='請填完整的換出與換入幣別及金額'; end if;
      if (p_payload->>'from_bucket' in ('美股','爸媽美股') and p_payload->>'currency'<>'USD')
        or (p_payload->>'from_bucket'='台股' and p_payload->>'currency'<>'TWD')
        or (p_payload->>'to_bucket' in ('美股','爸媽美股') and curr<>'USD')
        or (p_payload->>'to_bucket'='台股' and curr<>'TWD') then raise exception using errcode='22023',message='帳戶與幣別不一致'; end if;
    end if;
    for effect in select value from jsonb_array_elements(p_effects) loop
      bucket=effect->>'bucket'; curr=effect->>'currency'; effect_kind=effect->>'kind'; delta=(effect->>'delta')::numeric;
      if previous_data is not null and exists(select 1 from public.balance_adjustments a
        where a.created_at>(previous_data->>'created_at')::timestamptz and
          ((effect_kind='account' and a.kind='invested' and a.record_key='invested_'||bucket)
           or (effect_kind='cash' and a.kind='cash' and a.record_key in (select id::text from public.cash_accounts where name=bucket and currency=curr and archived_at is null)))) then
        skipped_correction=true;
        continue;
      end if;
      if effect_kind='account' then
        if delta<0 and (effect->>'available_cash' is null or (effect->>'available_cash')::numeric+delta < -0.000001) then raise exception using errcode='22023',message=bucket||' 可用現金不足，請先賣出持股或校正期初金額'; end if;
        k='invested_'||bucket;
        insert into public.manual_values(key,value) values(k,delta) on conflict(key) do update set value=public.manual_values.value+excluded.value;
      elsif effect_kind='cash' then
        if curr not in ('TWD','USD') then raise exception using errcode='22023',message='不支援的幣別'; end if;
        select id,amount into row_id,old_amount from public.cash_accounts where name=bucket and currency=curr and archived_at is null for update;
        if found then
          update public.cash_accounts set amount=coalesce(amount,0)+delta where id=row_id;
        else
          insert into public.cash_accounts(name,account,category,currency,amount) values(bucket,'',case when bucket like '%待還款%' or bucket='信用卡欠錢' then '負債' else '現金' end,curr,delta);
        end if;
      else raise exception using errcode='22023',message='未知帳戶類型'; end if;
    end loop;
    if p_action='movement.create' then
      insert into public.capital_movements(movement_date,from_bucket,to_bucket,amount,currency,to_amount,to_currency,note,affects_balance)
      values((p_payload->>'movement_date')::date,p_payload->>'from_bucket',p_payload->>'to_bucket',(p_payload->>'amount')::numeric,p_payload->>'currency',(p_payload->>'to_amount')::numeric,p_payload->>'to_currency',coalesce(p_payload->>'note',''),coalesce((p_payload->>'affects_balance')::boolean,true)) returning to_jsonb(capital_movements.*) into result_data;
    elsif p_action='movement.update' then
      update public.capital_movements set movement_date=(p_payload->>'movement_date')::date,from_bucket=p_payload->>'from_bucket',to_bucket=p_payload->>'to_bucket',amount=(p_payload->>'amount')::numeric,currency=p_payload->>'currency',to_amount=(p_payload->>'to_amount')::numeric,to_currency=p_payload->>'to_currency',note=coalesce(p_payload->>'note',''),affects_balance=coalesce((p_payload->>'affects_balance')::boolean,true) where id=p_record_id returning to_jsonb(capital_movements.*) into result_data;
    elsif p_action='movement.delete' then delete from public.capital_movements where id=p_record_id; result_data=previous_data;
    else raise exception using errcode='22023',message='未知的記帳操作'; end if;
  elsif p_action like 'trade.%' then
    if p_action<>'trade.create' then
      select to_jsonb(t) into previous_data from public.trades t where id=p_record_id for update;
      if previous_data is null then raise exception using errcode='P0002',message='交易不存在'; end if;
      if p_payload->>'expected_updated_at' is not null and (previous_data->>'updated_at')::timestamptz<>(p_payload->>'expected_updated_at')::timestamptz then raise exception using errcode='40001',message='交易已修改'; end if;
    end if;
    if p_action='trade.delete' then delete from public.trades where id=p_record_id; result_data=previous_data;
    elsif p_action in ('trade.create','trade.update') then
      if p_payload->>'account' not in ('台股','美股','爸媽美股') or trim(coalesce(p_payload->>'ticker',''))='' or (p_payload->>'fee')::numeric<0 then raise exception using errcode='22023',message='交易帳戶、代號或費用不正確'; end if;
      if p_action='trade.create' then
        insert into public.trades(account,ticker,date,buy_qty,sell_qty,price,fee,total,note)
        values(p_payload->>'account',upper(trim(p_payload->>'ticker')),(p_payload->>'date')::date,(p_payload->>'buy_qty')::numeric,(p_payload->>'sell_qty')::numeric,(p_payload->>'price')::numeric,(p_payload->>'fee')::numeric,(p_payload->>'total')::numeric,coalesce(p_payload->>'note','')) returning to_jsonb(trades.*) into result_data;
      else
        update public.trades set account=p_payload->>'account',ticker=upper(trim(p_payload->>'ticker')),date=(p_payload->>'date')::date,buy_qty=(p_payload->>'buy_qty')::numeric,sell_qty=(p_payload->>'sell_qty')::numeric,price=(p_payload->>'price')::numeric,fee=(p_payload->>'fee')::numeric,total=(p_payload->>'total')::numeric,note=coalesce(p_payload->>'note','') where id=p_record_id returning to_jsonb(trades.*) into result_data;
      end if;
    else raise exception using errcode='22023',message='未知交易操作'; end if;
  elsif p_action in ('cash.create','cash.update') then
    if p_action='cash.update' then
      select to_jsonb(c) into previous_data from public.cash_accounts c where id=p_record_id and archived_at is null for update;
      if previous_data is null then raise exception using errcode='P0002',message='現金帳戶不存在'; end if;
      if p_payload->>'expected_updated_at' is not null and (previous_data->>'updated_at')::timestamptz<>(p_payload->>'expected_updated_at')::timestamptz then raise exception using errcode='40001',message='餘額已更新，請重新讀取'; end if;
      if p_payload->>'currency' is not null and p_payload->>'currency'<>previous_data->>'currency' then raise exception using errcode='22023',message='校正餘額不能更換帳戶幣別，請使用換匯'; end if;
      update public.cash_accounts set amount=(p_payload->>'amount')::numeric where id=p_record_id returning to_jsonb(cash_accounts.*) into result_data;
      insert into public.balance_adjustments(operation_id,kind,record_key,previous_value,new_value,reason) values(p_operation_id,'cash',p_record_id::text,coalesce((previous_data->>'amount')::numeric,0),(p_payload->>'amount')::numeric,coalesce(p_payload->>'reason','餘額校正'));
    else
      insert into public.cash_accounts(name,account,category,currency,amount) values(trim(p_payload->>'name'),coalesce(p_payload->>'account',''),coalesce(p_payload->>'category','現金'),p_payload->>'currency',coalesce((p_payload->>'amount')::numeric,0)) returning to_jsonb(cash_accounts.*) into result_data;
    end if;
  elsif p_action='value.set' then
    k=p_payload->>'key'; new_amount=(p_payload->>'value')::numeric;
    if new_amount<0 and k not like 'invested_%' then raise exception using errcode='22023',message='金額不能小於零'; end if;
    select to_jsonb(v) into previous_data from public.manual_values v where key=k for update;
    old_amount=coalesce((previous_data->>'value')::numeric,0);
    if p_payload->>'expected_updated_at' is not null and (previous_data->>'updated_at')::timestamptz<>(p_payload->>'expected_updated_at')::timestamptz then raise exception using errcode='40001',message='投入金額已更新'; end if;
    insert into public.manual_values(key,value) values(k,new_amount) on conflict(key) do update set value=excluded.value returning to_jsonb(manual_values.*) into result_data;
    insert into public.balance_adjustments(operation_id,kind,record_key,previous_value,new_value,reason) values(p_operation_id,'invested',k,coalesce(old_amount,0),new_amount,coalesce(p_payload->>'reason','期初金額校正'));
  elsif p_action like 'investment.%' then
    result_data='[]'::jsonb;
    for item in select value from jsonb_array_elements(case when p_action='investment.bulk' then p_payload->'investments' else jsonb_build_array(p_payload || jsonb_build_object('id',p_record_id)) end) loop
      row_id=(item->>'id')::uuid;
      if p_action<>'investment.create' then
        select to_jsonb(i) into previous_data from public.manual_investments i where id=row_id for update;
        if previous_data is null then raise exception using errcode='P0002',message='投資項目已刪除'; end if;
        if item->>'expected_updated_at' is not null and (previous_data->>'updated_at')::timestamptz<>(item->>'expected_updated_at')::timestamptz then raise exception using errcode='40001',message='投資項目已更新'; end if;
      else previous_data='{}'::jsonb; end if;
      row_data=previous_data || item;
      if p_action='investment.delete' then delete from public.manual_investments where id=row_id;
      else
        if coalesce((row_data->>'cost')::numeric,0)<0 or coalesce((row_data->>'value')::numeric,0)<0 or coalesce((row_data->>'cash_amount')::numeric,0)<0 or trim(coalesce(row_data->>'name',''))='' or row_data->>'currency' not in ('TWD','USD') then raise exception using errcode='22023',message='投資項目名稱、幣別或金額不正確'; end if;
        if p_action='investment.create' then
          insert into public.manual_investments(name,asset_type,cost,value,cash_amount,currency) values(row_data->>'name',row_data->>'asset_type',(row_data->>'cost')::numeric,(row_data->>'value')::numeric,coalesce((row_data->>'cash_amount')::numeric,0),row_data->>'currency') returning to_jsonb(manual_investments.*) into row_data;
        else
          update public.manual_investments set name=row_data->>'name',asset_type=row_data->>'asset_type',cost=(row_data->>'cost')::numeric,value=(row_data->>'value')::numeric,cash_amount=coalesce((row_data->>'cash_amount')::numeric,0),currency=row_data->>'currency' where id=row_id returning to_jsonb(manual_investments.*) into row_data;
        end if;
      end if;
      result_data=result_data || jsonb_build_array(row_data);
    end loop;
    if p_action<>'investment.bulk' then result_data=result_data->0; end if;
  else raise exception using errcode='22023',message='不支援的帳務操作'; end if;
  if skipped_correction then result_data=result_data||jsonb_build_object('balance_effect_note','此紀錄已包含於後續餘額校正，相關帳戶保留校正後餘額。'); end if;
  insert into public.app_operations(operation_id,action,request,result) values(p_operation_id,p_action,request_data,coalesce(result_data,'{}'::jsonb));
  return result_data;
end $$;

-- Single-owner app: the API uses service_role. No public client needs these tables/RPCs.
do $$
declare t text; f record;
begin
  foreach t in array array['app_state','app_operations','app_login_attempts','balance_adjustments','cash_account_merge_backup','trades','manual_values','cash_accounts','manual_investments','summary_cache','price_cache','fx_rates','tickers','corporate_actions','price_history','fifo_checkpoints','job_runs','account_snapshots','capital_movements','capital_movement_options'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon,authenticated',t);
    execute format('grant all on public.%I to service_role',t);
  end loop;
  for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname in ('list_app_trades_page','check_app_login_limit','lock_app_write','bump_app_revision','app_touch_row','invalidate_trade_checkpoints','invalidate_action_checkpoints','app_data_revision','publish_app_caches','read_app_cache','read_app_caches','write_fifo_checkpoints','apply_app_operation') loop
    execute format('revoke all on function %s from public,anon,authenticated',f.signature);
    execute format('grant execute on function %s to service_role',f.signature);
  end loop;
end $$;
notify pgrst,'reload schema';
commit;
