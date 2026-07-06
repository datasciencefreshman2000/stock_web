create index if not exists idx_trades_account_date_created
  on trades(account, date desc, created_at desc);

create index if not exists idx_trades_account_ticker_date_created
  on trades(account, ticker, date desc, created_at desc);

create index if not exists idx_price_cache_fetched_at
  on price_cache(fetched_at desc);
