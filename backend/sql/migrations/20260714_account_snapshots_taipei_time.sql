alter table account_snapshots
  add column if not exists snapshot_date_taipei date;

alter table account_snapshots
  add column if not exists snapshot_hour_taipei smallint;

update account_snapshots
set
  snapshot_date_taipei = (snapshot_at at time zone 'Asia/Taipei')::date,
  snapshot_hour_taipei = extract(hour from snapshot_at at time zone 'Asia/Taipei')::smallint
where snapshot_date_taipei is null
   or snapshot_hour_taipei is null;

alter table account_snapshots
  alter column snapshot_date_taipei set not null;

alter table account_snapshots
  alter column snapshot_hour_taipei set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'account_snapshots_snapshot_hour_taipei_check'
  ) then
    alter table account_snapshots
      add constraint account_snapshots_snapshot_hour_taipei_check
      check (snapshot_hour_taipei between 0 and 23);
  end if;
end $$;

create index if not exists idx_account_snapshots_date_taipei
  on account_snapshots(snapshot_date_taipei desc);
