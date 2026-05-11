create table if not exists summary_cache (
  cache_key text primary key,
  payload jsonb not null,
  updated_at timestamptz default now()
);
