-- Fix sequence permissions required by bigserial defaults when using service_role
-- Example failure: permission denied for sequence password_reset_tokens_id_seq

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO service_role;
