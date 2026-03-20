-- Existing tables and policies
CREATE TABLE IF NOT EXISTS video_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    mode TEXT, -- FACTS, STORY, WYR, REDDIT, TRIVIA, QUOTE, ODD_ONE_OUT, FIND_IT
    status TEXT DEFAULT 'Pending',
    views INTEGER DEFAULT 0,
    retention_rate FLOAT DEFAULT 0, -- Percentage (0-100)
    engagement_score INTEGER DEFAULT 0, -- Likes + Comments + Shares
    download_url TEXT,
    youtube_video_id TEXT,
    storage_path TEXT, -- Persistent path for fresh Signed URLs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE video_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own video logs" ON video_logs;
CREATE POLICY "Users can manage their own video logs"
ON video_logs
FOR ALL
USING (auth.uid() = user_id);

-- New user configuration table
CREATE TABLE IF NOT EXISTS user_configs (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    youtube_client_id TEXT,
    youtube_client_secret TEXT,
    youtube_refresh_token TEXT,
    default_vibe TEXT DEFAULT 'suspense',
    plan TEXT DEFAULT 'free',
    max_videos INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE user_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can manage their own configurations" ON user_configs;
CREATE POLICY "Users can manage their own configurations"
ON user_configs
FOR ALL
USING (auth.uid() = user_id);
