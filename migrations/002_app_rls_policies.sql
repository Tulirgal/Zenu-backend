DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'profiles' AND policyname = 'Profiles select self'
  ) THEN
    CREATE POLICY "Profiles select self" ON app.profiles
      FOR SELECT
      USING (auth.uid() = id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'profiles' AND policyname = 'Profiles upsert self'
  ) THEN
    CREATE POLICY "Profiles upsert self" ON app.profiles
      FOR ALL
      USING (auth.uid() = id)
      WITH CHECK (auth.uid() = id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'journal_entries' AND policyname = 'Journal entries ownership'
  ) THEN
    CREATE POLICY "Journal entries ownership" ON app.journal_entries
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'breathing_sessions' AND policyname = 'Breathing sessions ownership'
  ) THEN
    CREATE POLICY "Breathing sessions ownership" ON app.breathing_sessions
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'activity_logs' AND policyname = 'Activity logs ownership'
  ) THEN
    CREATE POLICY "Activity logs ownership" ON app.activity_logs
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'mood_logs' AND policyname = 'Mood logs ownership'
  ) THEN
    CREATE POLICY "Mood logs ownership" ON app.mood_logs
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'chat_conversations' AND policyname = 'Chat conversations ownership'
  ) THEN
    CREATE POLICY "Chat conversations ownership" ON app.chat_conversations
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'chat_messages' AND policyname = 'Chat messages ownership'
  ) THEN
    CREATE POLICY "Chat messages ownership" ON app.chat_messages
      FOR ALL
      USING (
        EXISTS (
          SELECT 1
          FROM app.chat_conversations c
          WHERE c.id = conversation_id
            AND c.user_id = auth.uid()
        )
      )
      WITH CHECK (
        EXISTS (
          SELECT 1
          FROM app.chat_conversations c
          WHERE c.id = conversation_id
            AND c.user_id = auth.uid()
        )
      );
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'pss_assessments' AND policyname = 'PSS assessments ownership'
  ) THEN
    CREATE POLICY "PSS assessments ownership" ON app.pss_assessments
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'meditation_sessions' AND policyname = 'Meditation sessions ownership'
  ) THEN
    CREATE POLICY "Meditation sessions ownership" ON app.meditation_sessions
      FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'modules' AND policyname = 'Modules allow read'
  ) THEN
    CREATE POLICY "Modules allow read" ON app.modules
      FOR SELECT
      USING (true);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'daily_focus' AND policyname = 'Daily focus allow read'
  ) THEN
    CREATE POLICY "Daily focus allow read" ON app.daily_focus
      FOR SELECT
      USING (true);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'breathing_patterns' AND policyname = 'Breathing patterns allow read'
  ) THEN
    CREATE POLICY "Breathing patterns allow read" ON app.breathing_patterns
      FOR SELECT
      USING (true);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'app' AND tablename = 'meditations' AND policyname = 'Meditations allow read'
  ) THEN
    CREATE POLICY "Meditations allow read" ON app.meditations
      FOR SELECT
      USING (true);
  END IF;
END;
$$;
