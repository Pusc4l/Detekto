-- DETEKTO :: Fase 5 — jalankan SEKALI di Supabase SQL Editor (opsional; tanpa ini sistem memakai SQLite lokal).
-- Bobot disimpan per-instance (instance_id) agar bobot satu pengguna tidak menimpa pengguna lain.
create table if not exists public.ml_model_state (
    instance_id text primary key,
    version     integer      not null,
    n_samples   integer      not null,
    payload     jsonb        not null,
    updated_at  timestamptz  not null default now()
);
alter table public.ml_model_state enable row level security;
-- Gunakan SERVICE ROLE key lokal di backend/.env (SUPABASE_KEY) HANYA di perangkat Anda sendiri. Jangan pernah menaruhnya di frontend.

-- Fase 6: Global Hive-Mind (payload < 5 KB per baris; HANYA hash username, bukan username asli).
create table if not exists public.hive_verdicts (
    username_hash      text        not null,
    platform           text        not null,
    verdict_score      real        not null check (verdict_score >= 0 and verdict_score <= 100),
    buzzer_type        text        not null check (buzzer_type in ('A', 'B', 'C')),
    relationship_edges jsonb       not null default '[]'::jsonb,
    ml_weights_version integer     not null default 0,
    created_at         timestamptz not null default now(),
    primary key (username_hash, platform)
);
alter table public.hive_verdicts enable row level security;
