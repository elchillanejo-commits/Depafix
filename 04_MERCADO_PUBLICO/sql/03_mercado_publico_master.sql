-- ============================================
-- MIGRACIÓN 03: SCRAPER ORIGINAL
-- ============================================

INSERT INTO migrations_log (migration_name, status) 
VALUES ('03_mercado_publico_master', 'success')
ON CONFLICT (migration_name) DO NOTHING;
