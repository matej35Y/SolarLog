-- ZojaLog — READ-ONLY catalog queries for the InsForge dashboard SQL editor.
-- Paste and run ONE statement at a time. Each returns fewer than ~20 rows and touches only catalog
-- views (plus two COUNT(*) on small tables). No writes, no DDL. Safe for the free plan.
-- Purpose: verify the LIVE schema, keys, RLS policies and grants (docs R-S3, Q-01, Q-02, Q-09).

-- 1) Columns and types (does it match scripts/init_schema.sql? is there an unexpected `id`?)
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN ('hourly_prices', 'energy_generation')
ORDER BY table_name, ordinal_position;

-- 2) Primary keys / unique constraints
SELECT conrelid::regclass AS tbl, contype, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid IN ('public.hourly_prices'::regclass, 'public.energy_generation'::regclass);

-- 3) Row-level-security policies (are the write policies really role-less?)
SELECT tablename, policyname, cmd, roles, qual, with_check
FROM pg_policies
WHERE tablename IN ('hourly_prices', 'energy_generation');

-- 4) Table grants for client roles (can `anon` INSERT/UPDATE/DELETE?)
SELECT table_name, grantee, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND table_name IN ('hourly_prices', 'energy_generation')
  AND grantee IN ('anon', 'authenticated', 'PUBLIC', 'public');

-- 5) RLS enabled / forced?
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN ('hourly_prices', 'energy_generation');

-- 6) Row counts (two COUNT(*) on small tables)
SELECT (SELECT count(*) FROM public.energy_generation) AS energy_rows,
       (SELECT count(*) FROM public.hourly_prices)     AS price_rows;
