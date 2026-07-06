-- ============================================================
-- BrickBit · Esquema de cuentas (Supabase)
-- Ejecuta TODO esto en Supabase → SQL Editor → New query → Run
-- Crea las tablas de "análisis guardados" y "zonas favoritas",
-- y la seguridad por usuario (Row Level Security).
-- ============================================================

-- 1) Análisis guardados ---------------------------------------
create table if not exists public.saved_analyses (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  zona        text not null,
  horizonte   int  not null default 5,
  inputs      jsonb not null default '{}'::jsonb,   -- todos los supuestos del analizador
  resumen     jsonb not null default '{}'::jsonb,   -- TIR/ROI/etc. para mostrar sin recalcular
  nota        text,
  created_at  timestamptz not null default now()
);

-- 2) Zonas favoritas ------------------------------------------
create table if not exists public.favorite_zones (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  zona        text not null,
  created_at  timestamptz not null default now(),
  unique (user_id, zona)                            -- una zona no se repite por usuario
);

-- 3) Seguridad por usuario (RLS) ------------------------------
-- Sin esto, la llave pública dejaría ver todo. CON esto, cada
-- quien ve y edita ÚNICAMENTE sus propios registros.
alter table public.saved_analyses  enable row level security;
alter table public.favorite_zones  enable row level security;

-- Análisis: políticas
drop policy if exists "analyses_select_own" on public.saved_analyses;
drop policy if exists "analyses_insert_own" on public.saved_analyses;
drop policy if exists "analyses_update_own" on public.saved_analyses;
drop policy if exists "analyses_delete_own" on public.saved_analyses;
create policy "analyses_select_own" on public.saved_analyses for select using (auth.uid() = user_id);
create policy "analyses_insert_own" on public.saved_analyses for insert with check (auth.uid() = user_id);
create policy "analyses_update_own" on public.saved_analyses for update using (auth.uid() = user_id);
create policy "analyses_delete_own" on public.saved_analyses for delete using (auth.uid() = user_id);

-- Favoritos: políticas
drop policy if exists "favs_select_own" on public.favorite_zones;
drop policy if exists "favs_insert_own" on public.favorite_zones;
drop policy if exists "favs_delete_own" on public.favorite_zones;
create policy "favs_select_own" on public.favorite_zones for select using (auth.uid() = user_id);
create policy "favs_insert_own" on public.favorite_zones for insert with check (auth.uid() = user_id);
create policy "favs_delete_own" on public.favorite_zones for delete using (auth.uid() = user_id);

-- Índices útiles
create index if not exists idx_analyses_user on public.saved_analyses(user_id, created_at desc);
create index if not exists idx_favs_user     on public.favorite_zones(user_id, created_at desc);

-- ============================================================
-- ALERTAS POR ZONA  (base lista para notificaciones por correo)
-- Un proceso programado (Edge Function / cron) leerá esta tabla,
-- comparará contra el pronóstico nuevo y enviará el correo.
-- ============================================================
create table if not exists public.zone_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  zona text not null,
  horizonte int not null default 5,
  umbral_pct numeric not null default 5,
  activa boolean not null default true,
  ultimo_valor numeric,                       -- pronóstico de referencia (lo llena el job)
  notificado_en timestamptz,                  -- última notificación enviada
  created_at timestamptz not null default now(),
  unique(user_id, zona)
);
alter table public.zone_alerts enable row level security;
create policy "alerts_select_own" on public.zone_alerts for select using (auth.uid() = user_id);
create policy "alerts_insert_own" on public.zone_alerts for insert with check (auth.uid() = user_id);
create policy "alerts_update_own" on public.zone_alerts for update using (auth.uid() = user_id);
create policy "alerts_delete_own" on public.zone_alerts for delete using (auth.uid() = user_id);
create index if not exists zone_alerts_user_idx on public.zone_alerts(user_id);
create index if not exists zone_alerts_activa_idx on public.zone_alerts(activa) where activa = true;
