import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { createClient as createUserClient } from '@/utils/supabase/server';

export async function POST(request: Request) {
  try {
    // Verify the user is authenticated
    const supabase = await createUserClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();
    
    if (authError || !user) {
      console.error('[SignedURL API] Auth failed:', authError);
      return NextResponse.json({ error: 'Unauthorized', details: authError?.message }, { status: 401 });
    }

    const { storage_path } = await request.json();
    console.log(`[SignedURL API] Request for path: ${storage_path} by user: ${user.id}`);

    if (!storage_path) {
      return NextResponse.json({ error: 'storage_path is required' }, { status: 400 });
    }

    // Use service role to generate signed URL (server-side only)
    if (!process.env.SUPABASE_SERVICE_ROLE_KEY) {
      console.error('[SignedURL API] SUPABASE_SERVICE_ROLE_KEY is missing from environment variables!');
      return NextResponse.json({ error: 'Server misconfiguration: Service key missing' }, { status: 500 });
    }

    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );

    const { data, error } = await supabaseAdmin.storage
      .from('videos')
      .createSignedUrl(storage_path, 3600); // 1 hour expiry

    if (error) {
      console.error('[SignedURL API] Supabase storage error:', error);
      return NextResponse.json({ error: 'Failed to generate download link', details: error.message }, { status: 500 });
    }

    if (!data?.signedUrl) {
      console.error('[SignedURL API] No signedUrl in response');
      return NextResponse.json({ error: 'No signed URL generated' }, { status: 500 });
    }

    console.log('[SignedURL API] Successfully generated URL');
    return NextResponse.json({ signedUrl: data.signedUrl });
  } catch (err: any) {
    console.error('[SignedURL API] Unexpected error:', err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
