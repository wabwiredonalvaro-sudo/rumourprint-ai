-- RUMOURPRINT AI — community review moderation
-- Apply in the Supabase SQL Editor after creating your own project.
-- All public API access is denied. Only the server-side Streamlit integration
-- should hold the service-role credential. No visitor can publish directly.

create extension if not exists pgcrypto;

create table if not exists public.rumourprint_reviews (
  id uuid primary key default gen_random_uuid(),
  claim_hash text not null check (claim_hash ~ '^[a-f0-9]{64}$'),
  reviewer_role text not null default 'Reader'
    check (reviewer_role in ('Reader', 'Journalist (self-described)')),
  review_text text not null check (char_length(review_text) between 35 and 700),
  source_url text,
  origin text not null default 'RUMOURPRINT',
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  approved_at timestamptz,
  moderator_notes text
);

create index if not exists rumourprint_reviews_lookup
  on public.rumourprint_reviews (claim_hash, status, created_at desc);

alter table public.rumourprint_reviews enable row level security;

revoke all on public.rumourprint_reviews from anon, authenticated;
-- Moderators review entries in Supabase Table Editor, changing 'pending' to
-- 'approved' only after reading the linked public source and checking privacy.
-- No public access policies should be created for this table.
