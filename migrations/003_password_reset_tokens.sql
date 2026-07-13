CREATE TABLE IF NOT EXISTS app.password_reset_tokens (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  email text NOT NULL,
  token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS password_reset_tokens_email_idx
  ON app.password_reset_tokens (email, created_at DESC);

CREATE INDEX IF NOT EXISTS password_reset_tokens_hash_idx
  ON app.password_reset_tokens (token_hash);

ALTER TABLE app.password_reset_tokens ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'password_reset_tokens' AND policyname = 'Password reset tokens ownership'
  ) THEN
    CREATE POLICY "Password reset tokens ownership" ON app.password_reset_tokens
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

GRANT ALL ON app.password_reset_tokens TO service_role;
GRANT SELECT ON app.password_reset_tokens TO authenticated;
