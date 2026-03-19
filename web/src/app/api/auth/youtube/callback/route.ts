import { createClient } from '@/utils/supabase/server';
import { encrypt, decrypt } from '@/utils/crypto';
import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  if (error) {
    return NextResponse.redirect(new URL(`/settings?error=${error}`, request.url));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/settings?error=no_code', request.url));
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // 1. Fetch the user's Client ID and Secret to perform the exchange
  const { data: config, error: configError } = await supabase
    .from('user_configs')
    .select('youtube_client_id, youtube_client_secret')
    .eq('user_id', user.id)
    .single();

  if (configError || !config?.youtube_client_id || !config?.youtube_client_secret) {
    return NextResponse.redirect(new URL('/settings?error=missing_keys', request.url));
  }

  const clientId = decrypt(config.youtube_client_id);
  const clientSecret = decrypt(config.youtube_client_secret);
  const redirectUri = `${new URL(request.url).origin}/api/auth/youtube/callback`;

  try {
    // 2. Exchange code for tokens
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    });

    const tokenData = await tokenRes.json();

    if (!tokenRes.ok) {
      console.error('[OAuth Callback] Token Exchange Error:', tokenData);
      return NextResponse.redirect(new URL(`/settings?error=${tokenData.error}`, request.url));
    }

    const { refresh_token } = tokenData;

    if (!refresh_token) {
       // Note: Google only sends refresh_token on the FIRST consent. 
       // If the user already linked once, we might not get it unless we used prompt=consent.
       return NextResponse.redirect(new URL('/settings?error=no_refresh_token', request.url));
    }

    // 3. Encrypt and save the refresh token
    const { error: updateError } = await supabase
      .from('user_configs')
      .update({
        youtube_refresh_token: encrypt(refresh_token),
        updated_at: new Date().toISOString()
      })
      .eq('user_id', user.id);

    if (updateError) throw updateError;

    return NextResponse.redirect(new URL('/settings?success=youtube_connected', request.url));
  } catch (err: any) {
    console.error('[OAuth Callback] Exception:', err);
    return NextResponse.redirect(new URL(`/settings?error=exception`, request.url));
  }
}
