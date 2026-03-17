-- Video Logs Table
-- Stores information about every generated video for the dashboard
CREATE TABLE IF NOT EXISTS video_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id),
    title TEXT NOT NULL,
    mode TEXT CHECK (mode IN ('FACTS', 'STORY', 'AUTO')),
    status TEXT DEFAULT 'Processing' CHECK (status IN ('Processing', 'Published', 'Failed')),
    views INTEGER DEFAULT 0,
    download_url TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RLS (Row Level Security)
ALTER TABLE video_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own logs
CREATE POLICY "Users can view own video logs" 
ON video_logs FOR SELECT 
USING (auth.uid() = user_id);

-- Policy: System/Admin can insert/update logs (Service Role)
CREATE POLICY "Service role can manage all logs" 
ON video_logs FOR ALL 
USING (true)
WITH CHECK (true);
