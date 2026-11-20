-- Run this ONCE in Supabase: SQL Editor > New query > paste > Run
create table if not exists po_lines (
  key text primary key, po text, asin text, order_date date,
  status text, requested numeric, accepted numeric, title text);
create index if not exists po_lines_asin_idx on po_lines(asin);

create table if not exists reports (
  id text primary key, kind text, mk text, rng text, filename text,
  uploaded_by text, uploaded_at timestamptz default now(), data jsonb);

create table if not exists notes (
  asin text primary key, status text, note text,
  updated_by text, updated_at timestamptz default now());

create table if not exists app_log (
  id bigint generated always as identity primary key,
  at timestamptz default now(), user_name text, msg text);

alter table po_lines enable row level security;
alter table reports enable row level security;
alter table notes enable row level security;
alter table app_log enable row level security;
