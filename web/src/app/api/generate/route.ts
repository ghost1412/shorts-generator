import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    let {
      mode,
      category,
      customScript,
      vibe,
      useComfy,
      useAiAudio
    } = body;

    // Defensive check: support snake_case from older/misc clients
    if (useComfy === undefined) useComfy = body.use_comfy;
    if (useAiAudio === undefined) useAiAudio = body.use_ai_audio;
    if (customScript === undefined) customScript = body.custom_script;
    const renderTarget = process.env.RENDER_TARGET || 'github';
    const videoId = crypto.randomUUID();

    // 0. Security & Plan Limit Check (Backend enforcement)
    const { data: userConfig, error: configError } = await supabase
      .from('user_configs')
      .select('plan, max_videos, github_token, github_repo, generations_used')
      .eq('user_id', user.id)
      .single();

    // 2. Plan Limits (Usage-based check)
    const generationsUsed = userConfig?.generations_used || 0;
    const maxVideos = userConfig?.max_videos || 3;
    const plan = userConfig?.plan || 'free';

    // 🟢 PRO RESTRICTION: Only 'pro' or 'enterprise' can use Advanced AI Models or Audio
    const isPro = userConfig?.plan?.toLowerCase() === 'pro' || userConfig?.plan?.toLowerCase() === 'enterprise';
    
    if ((useComfy || useAiAudio) && !isPro) {
      return NextResponse.json(
        { error: 'Pro plan required for Advanced AI Models' },
        { status: 403 }
      );
    }

    // 🟢 PRO RESILIENCE: If user IS Pro, but flags came in as false/missing, we AUTO-ENABLE them.
    // This fixes state-sync issues where the frontend might lag behind the DB status.
    if (isPro) {
      if (useComfy === undefined || useComfy === false || useComfy === "false") useComfy = true;
      if (useAiAudio === undefined || useAiAudio === false || useAiAudio === "false") useAiAudio = true;
      console.log(`[API] Pro user detected (${user.id}). Auto-enabling AI flags: Comfy=${useComfy}, Audio=${useAiAudio}`);
    }

    if (plan === 'free' && generationsUsed >= maxVideos) {
      return NextResponse.json({ 
        error: 'Usage limit reached', 
        details: `You have used all ${maxVideos} generations in your free plan. Upgrade to Pro for unlimited!` 
      }, { status: 403 });
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

      // 5. Update usage counter (Increment by 1)
      if (plan === 'free') {
        await supabase
          .from('user_configs')
          .update({ generations_used: generationsUsed + 1 })
          .eq('user_id', user.id);
      }

      return NextResponse.json({ 
        message: 'Generation triggered successfully', 
        video_id: videoId 
      });
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
            user_id: user.id,
            use_comfy: useComfy ? 'true' : 'false',
            use_ai_audio: useAiAudio ? 'true' : 'false'
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
