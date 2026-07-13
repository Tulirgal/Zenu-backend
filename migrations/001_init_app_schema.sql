CREATE SCHEMA IF NOT EXISTS app;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS app.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  username text UNIQUE,
  full_name text,
  avatar_url text,
  bio text,
  preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT profiles_preferences_object CHECK (jsonb_typeof(preferences) = 'object')
);

CREATE TABLE IF NOT EXISTS app.modules (
  id text PRIMARY KEY,
  title text NOT NULL,
  description text,
  icon text,
  position integer,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.daily_focus (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  description text,
  cta text NOT NULL,
  duration_seconds integer NOT NULL CHECK (duration_seconds > 0),
  module_id text REFERENCES app.modules (id),
  starts_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  ends_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.breathing_patterns (
  id text PRIMARY KEY,
  name text NOT NULL,
  description text,
  difficulty text,
  steps integer[] NOT NULL DEFAULT '{}'::int4[],
  default_minutes integer NOT NULL DEFAULT 5 CHECK (default_minutes > 0),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.breathing_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  pattern text NOT NULL REFERENCES app.breathing_patterns (id),
  duration_seconds integer NOT NULL CHECK (duration_seconds > 0),
  rating integer CHECK (rating BETWEEN 1 AND 5),
  notes text,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.meditations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  duration_minutes integer NOT NULL CHECK (duration_minutes > 0),
  category text NOT NULL,
  image_url text,
  audio_url text,
  description text,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.meditation_sessions (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  meditation_id uuid NOT NULL REFERENCES app.meditations (id),
  duration_seconds integer NOT NULL CHECK (duration_seconds > 0),
  completed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.journal_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  mood text,
  title text,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.mood_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  mood text NOT NULL,
  intensity integer CHECK (intensity BETWEEN 1 AND 10),
  note text,
  logged_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.activity_logs (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  module text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
  CONSTRAINT activity_logs_payload_object CHECK (jsonb_typeof(payload) = 'object')
);

CREATE TABLE IF NOT EXISTS app.chat_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  title text,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.chat_messages (
  id bigserial PRIMARY KEY,
  conversation_id uuid NOT NULL REFERENCES app.chat_conversations (id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS app.pss_assessments (
  id bigserial PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  scores integer[] NOT NULL,
  average_score numeric(5, 2) NOT NULL,
  flagged boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS modules_position_idx ON app.modules (position);
CREATE INDEX IF NOT EXISTS daily_focus_window_idx ON app.daily_focus (starts_at DESC, ends_at);
CREATE INDEX IF NOT EXISTS breathing_sessions_user_idx ON app.breathing_sessions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS meditation_sessions_user_idx ON app.meditation_sessions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS journal_entries_user_idx ON app.journal_entries (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS activity_logs_user_idx ON app.activity_logs (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS mood_logs_user_idx ON app.mood_logs (user_id, logged_at DESC);
CREATE INDEX IF NOT EXISTS chat_conversations_user_idx ON app.chat_conversations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS chat_messages_conversation_idx ON app.chat_messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS pss_assessments_user_idx ON app.pss_assessments (user_id, created_at DESC);

ALTER TABLE app.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.breathing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.mood_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.pss_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.meditation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.daily_focus ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.breathing_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.meditations ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA app TO authenticated, anon, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA app TO service_role;
