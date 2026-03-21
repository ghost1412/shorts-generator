# 🚀 Shorts Generator Setup Guide

This guide covers the essential steps to configure your video generator and connect your YouTube channel.

## 1. Vercel Environment Variables
Add these to your project in **Vercel → Settings → Environment Variables**:

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_SITE_URL` | Your app domain | `https://shorts-generator-projects.vercel.app` |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin key for DB writes | (From Supabase Dashboard) |
| `ENCRYPTION_KEY` | 32-character key for secrets | `a-random-32-char-string-here...` |

---

## 2. Google Cloud Console (YouTube API)
To enable YouTube uploads and analytics:

1.  Go to [Google Cloud Console](https://console.cloud.google.com/).
2.  Select your project and go to **APIs & Services → Credentials**.
3.  Edit your **OAuth 2.0 Client ID**.
4.  Add these to **Authorized redirect URIs**:
    *   `https://shorts-generator-projects.vercel.app/api/auth/youtube/callback`
    *   `http://localhost:3000/api/auth/youtube/callback` (for local testing)

---

## 3. Supabase Database Update
Run this command in your **Supabase SQL Editor** to support the latest features:

```sql
-- Add support for video thumbnails
ALTER TABLE video_logs ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;

-- Add permanent usage tracking
ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS generations_used INTEGER DEFAULT 0;
```

---

## 4. GitHub Actions Secrets
Ensure these are set in **GitHub Repository → Settings → Secrets and variables → Actions**:
*   `SUPABASE_URL`
*   `SUPABASE_SERVICE_ROLE_KEY`
*   `USER_ID` (Your Supabase User ID)
