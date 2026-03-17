import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { mode, category, customScript, vibe } = await request.json();
    const renderTarget = process.env.RENDER_TARGET || 'server'; // Default to server for local dev
    const videoId = crypto.randomUUID();

    // 1. Create the 'Processing' entry in the DB immediately
    // This ensures the user sees something in their list even if they leave
    await supabase.from('video_logs').insert({
      id: videoId,
      user_id: user.id,
      title: customScript?.substring(0, 30) || `${category} Video`,
      mode: mode === 'AUTO' ? 'FACTS' : mode, // Fallback for log display
      status: 'Processing',
      created_at: new Date().toISOString()
    });

    if (renderTarget === 'server') {
      // 1. DEDICATED SERVER RENDERING (Local or VPS)
      const serverUrl = process.env.SERVER_RENDER_URL || 'http://localhost:5000/render';
      
      console.log(`🚀 Forwarding render request to dedicated server: ${serverUrl}`);
      
      const res = await fetch(serverUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          category,
          customScript,
          vibe,
          userId: user.id,
          video_id: videoId // Sync with DB
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        return NextResponse.json({ error: errorData.message || 'Server render failed' }, { status: 500 });
      }

      return NextResponse.json({ message: 'Render started on dedicated server' });

    } else {
      // 2. GITHUB ACTIONS RENDERING (Default Cloud)
      const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
      const GITHUB_REPO = process.env.GITHUB_REPO; // e.g., "username/repo"

      if (!GITHUB_TOKEN || !GITHUB_REPO) {
        return NextResponse.json({ error: 'GitHub configuration missing for cloud rendering' }, { status: 500 });
      }

      const [owner, repo] = GITHUB_REPO.split('/');

      const res = await fetch(
        `https://api.github.com/repos/${owner}/${repo}/actions/workflows/daily_generate.yml/dispatches`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${GITHUB_TOKEN}`,
            Accept: 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
          },
          body: JSON.stringify({
            ref: 'main',
            inputs: {
              mode,
              category,
              script: customScript,
              vibe,
              video_id: videoId,
              user_id: user.id
            },
          }),
        }
      );

      if (!res.ok) {
        return NextResponse.json({ error: 'GitHub Action trigger failed' }, { status: 500 });
      }

      return NextResponse.json({ message: 'Cloud render triggered on GitHub Actions' });
    }

  } catch (error: any) {
    console.error('Error in generate route:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
