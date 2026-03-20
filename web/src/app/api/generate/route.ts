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
    const renderTarget = process.env.RENDER_TARGET || 'github'; 
    const videoId = crypto.randomUUID();

    // 0. Security & Plan Limit Check (Backend enforcement)
    const { data: userConfig, error: configError } = await supabase
      .from('user_configs')
      .select('plan, max_videos, github_token, github_repo')
      .eq('user_id', user.id)
      .single();

    const plan = userConfig?.plan || 'free';
    const maxVideos = userConfig?.max_videos || 3;

    if (plan === 'free') {
      const { count } = await supabase
        .from('video_logs')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', user.id);
      
      if (count !== null && count >= maxVideos) {
        return NextResponse.json({ 
          error: 'Video limit reached for Free plan. Please upgrade to Pro for unlimited generation.' 
        }, { status: 403 });
      }
    }

    // 1. Create the 'Processing' entry in the DB immediately
    const { error: insertError } = await supabase.from('video_logs').insert({
      id: videoId,
      user_id: user.id,
      title: customScript?.substring(0, 30) || `${category} Video`,
      mode: mode === 'AUTO' ? 'FACTS' : mode, 
      status: 'Processing',
      created_at: new Date().toISOString()
    });

    if (insertError) {
      console.error('DB Insert Error:', insertError);
      return NextResponse.json({ error: 'Failed to create video log' }, { status: 500 });
    }

    if (renderTarget === 'server') {
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
          video_id: videoId 
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        return NextResponse.json({ error: errorData.message || 'Server render failed' }, { status: 500 });
      }

      return NextResponse.json({ message: 'Render started on dedicated server' });
    }

    // 2. GITHUB ACTIONS RENDERING (Default Cloud)
    let GITHUB_TOKEN = process.env.GITHUB_TOKEN;
    let GITHUB_REPO = process.env.GITHUB_REPO;

    if (!GITHUB_TOKEN || !GITHUB_REPO) {
      return NextResponse.json({ error: 'GitHub configuration missing for cloud rendering' }, { status: 500 });
    }

    const [owner, repo] = GITHUB_REPO.split('/');

    const githubRes = await fetch(
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
            custom_script: customScript,
            vibe,
            video_id: videoId,
            user_id: user.id
          },
        }),
      }
    );

    if (!githubRes.ok) {
      const errorText = await githubRes.text();
      console.error('GitHub API Error:', errorText);
      return NextResponse.json({ error: 'GitHub Action trigger failed' }, { status: 500 });
    }

    return NextResponse.json({ message: 'Cloud render triggered on GitHub Actions' });

  } catch (error: any) {
    console.error('Error in generate route:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
