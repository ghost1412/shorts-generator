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
    const { video_id, title, mode, status, download_url, user_id } = payload;

    // Security Check: You should add a secret token/signature check here from GitHub
    // to ensure only your GitHub Actions can call this endpoint.
    
    const { data, error } = await supabaseAdmin
      .from('video_logs')
      .upsert({
        id: video_id, // Use the ID passed from the generator
        user_id: user_id,
        title: title,
        mode: mode,
        status: status || 'Published',
        download_url: download_url,
        created_at: new Date().toISOString(),
      });

    if (error) throw error;

    return NextResponse.json({ success: true, data });
  } catch (err: any) {
    console.error('Webhook Error:', err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
