-- Shared DENUE reference data must be written by trusted ingestion only.
-- Public reads remain available through denue_read_all.
drop policy if exists denue_write_auth_ins on public.zone_denue;
drop policy if exists denue_write_auth_upd on public.zone_denue;
revoke insert, update, delete, truncate, references, trigger on public.zone_denue from anon, authenticated;
