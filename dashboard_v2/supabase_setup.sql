-- Kalachandji's sales dashboard: storage for weekly files added from the dashboard.
-- Run once in Supabase: Dashboard > SQL Editor > New query > paste > Run.
-- Your existing Streamlit tables (sales, uploads) are not touched.

create extension if not exists pgcrypto with schema extensions;

-- 1) One row per weekly file added from the dashboard
create table if not exists public.kc_dashboard_weeks (
  id          text primary key,              -- e.g. w2026-10-16_2026-10-22
  file        text not null,
  uploaded_at timestamptz not null default now(),
  min_date    date not null,
  max_date    date not null,
  n           integer not null,
  packed      jsonb not null                 -- the parsed sales lines
);
alter table public.kc_dashboard_weeks enable row level security;
drop policy if exists "anyone can read dashboard weeks" on public.kc_dashboard_weeks;
create policy "anyone can read dashboard weeks" on public.kc_dashboard_weeks for select using (true);
-- No insert/update/delete policies: writes only happen through the PIN-checked functions below.

-- 2) The upload PIN, stored as a bcrypt hash and never readable from the web
create table if not exists public.kc_dashboard_settings (
  key   text primary key,
  value text not null
);
alter table public.kc_dashboard_settings enable row level security;   -- no policies = no web access

-- >>> CHANGE THE PIN on the next line before running (keep the quotes) <<<
insert into public.kc_dashboard_settings (key, value)
values ('upload_pin', extensions.crypt('CHANGE-ME-1234', extensions.gen_salt('bf')))
on conflict (key) do update set value = excluded.value;

-- 3) PIN-checked functions the dashboard calls
create or replace function public.kc_pin_ok(p_pin text) returns boolean
language plpgsql security definer set search_path = public, extensions as $$
declare h text;
begin
  select value into h from kc_dashboard_settings where key = 'upload_pin';
  if h is null or p_pin is null then return false; end if;
  return extensions.crypt(p_pin, h) = h;
end $$;

create or replace function public.kc_upload_week(p_pin text, p_id text, p_file text, p_min date, p_max date, p_n integer, p_packed jsonb)
returns text language plpgsql security definer set search_path = public, extensions as $$
begin
  if not kc_pin_ok(p_pin) then raise exception 'invalid_pin'; end if;
  if p_id !~ '^w[0-9-]+_[0-9-]+$' or p_n < 1 or p_n > 20000 then raise exception 'bad_file'; end if;
  insert into kc_dashboard_weeks (id, file, uploaded_at, min_date, max_date, n, packed)
  values (p_id, left(p_file, 200), now(), p_min, p_max, p_n, p_packed)
  on conflict (id) do update set file = excluded.file, uploaded_at = now(), min_date = excluded.min_date,
    max_date = excluded.max_date, n = excluded.n, packed = excluded.packed;
  return 'ok';
end $$;

create or replace function public.kc_delete_week(p_pin text, p_id text)
returns text language plpgsql security definer set search_path = public, extensions as $$
begin
  if not kc_pin_ok(p_pin) then raise exception 'invalid_pin'; end if;
  delete from kc_dashboard_weeks where id = p_id;
  return 'ok';
end $$;

-- The PIN check is only callable from inside the two functions above, never from the web.
revoke all on function public.kc_pin_ok(text) from public, anon, authenticated;
grant execute on function public.kc_upload_week(text, text, text, date, date, integer, jsonb) to anon, authenticated;
grant execute on function public.kc_delete_week(text, text) to anon, authenticated;

-- To change the PIN later, run:
-- update public.kc_dashboard_settings set value = extensions.crypt('NEW-PIN', extensions.gen_salt('bf')) where key = 'upload_pin';
