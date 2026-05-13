create table if not exists capital_movement_options (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  label text not null,
  created_at timestamptz default now(),
  unique (category, label)
);

insert into capital_movement_options (category, label)
values
  ('income_source', '宇統資訊'),
  ('income_source', '陽明高中'),
  ('income_source', '實驗小學'),
  ('income_source', '接案')
on conflict (category, label) do nothing;
