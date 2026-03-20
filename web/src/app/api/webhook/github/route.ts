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
    console.log(`[Webhook] Received update for ${video_id}: status=${status}, path=${storage_path}, user=${user_id}`);

    const finalStatus = status || 'Published';

    // Direct UPDATE (not upsert) - row already created by /api/generate
    const { data: updateResult, error: updateError } = await supabaseAdmin
      .from('video_logs')
      .update({
        status: finalStatus,
        ...(title && { title }),
        ...(mode && { mode }),
        ...(download_url && { download_url }),
        ...(storage_path && { storage_path }),
        ...(youtube_video_id && { youtube_video_id }),
      })
      .eq('id', video_id)
      .select();

    if (updateError) {
      console.error('[Webhook] Update failed:', updateError);
      throw updateError;
    }
    console.log(`[Webhook] Updated rows:`, updateResult?.length ?? 0);

    // If success, also increment the generations_used counter in user_configs
    if (finalStatus === 'Published' && user_id) {
      const { data: config, error: configError } = await supabaseAdmin
        .from('user_configs')
        .select('generations_used')
        .eq('user_id', user_id)
        .single();

      if (configError) {
        console.error('[Webhook] Failed to fetch user_configs:', configError);
      } else if (config) {
        const { error: counterError } = await supabaseAdmin
          .from('user_configs')
          .update({ generations_used: (config.generations_used || 0) + 1 })
          .eq('user_id', user_id);
        if (counterError) console.error('[Webhook] Counter update failed:', counterError);
        else console.log('[Webhook] generations_used incremented to', (config.generations_used || 0) + 1);
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
