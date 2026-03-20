import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase with Service Role Key for administrative access
const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const { video_id, title, mode, status, download_url, user_id, youtube_video_id, storage_path } = payload;
    console.log(`[Webhook] Received update for ${video_id}: status=${status}, path=${storage_path}`);

    const finalStatus = status || 'Published';

    // Build update object - no created_at on updates to avoid overwriting
    const updateData: Record<string, any> = {
      id: video_id,
      user_id: user_id,
      status: finalStatus,
    };
    if (title) updateData.title = title;
    if (mode) updateData.mode = mode;
    if (download_url) updateData.download_url = download_url;
    if (storage_path) updateData.storage_path = storage_path;
    if (youtube_video_id) updateData.youtube_video_id = youtube_video_id;

    const { error } = await supabaseAdmin
      .from('video_logs')
      .upsert(updateData, { onConflict: 'id', ignoreDuplicates: false });

    if (error) throw error;

    // If success, also increment the generations_used counter in user_configs
    if (finalStatus === 'Published' && user_id) {
      const { data: config } = await supabaseAdmin
        .from('user_configs')
        .select('generations_used, max_videos')
        .eq('user_id', user_id)
        .single();

      if (config) {
        await supabaseAdmin
          .from('user_configs')
          .update({ generations_used: (config.generations_used || 0) + 1 })
          .eq('user_id', user_id);
      }
    }

    return NextResponse.json({ success: true });
  } catch (err: any) {
    console.error('Webhook Error Details:', {
      message: err.message,
      code: err.code,
      details: err.details,
      hint: err.hint
    });
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
