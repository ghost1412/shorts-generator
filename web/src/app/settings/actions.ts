'use server'

import { createClient } from '@/utils/supabase/server';
import { encrypt, decrypt } from '@/utils/crypto';
import crypto from 'crypto';

export async function saveUserSettings(config: any) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('Not authenticated');
  }

  console.log(`[Action] Saving settings for user ${user.id}...`);
  const keyFingerprint = crypto.createHash('sha256').update(process.env.ENCRYPTION_KEY || 'shortsflow-placeholder-master-key-32chars').digest('hex').substring(0, 8);
  console.log(`[Action] Key Fingerprint: ${keyFingerprint}`);

  // Encrypt sensitive fields (trim then encrypt)
  const encryptedConfig = {
    user_id: user.id,
    youtube_client_id: encrypt(config.youtube_client_id?.trim()), 
    youtube_client_secret: encrypt(config.youtube_client_secret?.trim()),
    youtube_refresh_token: encrypt(config.youtube_refresh_token?.trim()),
    pinterest_access_token: encrypt(config.pinterest_access_token?.trim()),
    pinterest_board_id: encrypt(config.pinterest_board_id?.trim()),
    default_vibe: config.default_vibe,
    updated_at: new Date().toISOString()
  };

  console.log(`[Action] Secret starts with hex: ${encryptedConfig.youtube_client_secret.substring(0, 8)}...`);

  const { error } = await supabase
    .from('user_configs')
    .upsert(encryptedConfig);

  if (error) {
    console.error('Supabase Upsert Error:', error);
    throw new Error(`Supabase Error: ${error.message} (Code: ${error.code})`);
  }
  
  return { success: true };
}

export async function deleteYouTubeAuth() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) {
    throw new Error('Not authenticated');
  }

  const { error } = await supabase
    .from('user_configs')
    .upsert({
      user_id: user.id,
      youtube_client_id: '',
      youtube_client_secret: '',
      youtube_refresh_token: '',
      updated_at: new Date().toISOString()
    });

  if (error) throw error;
  
  return { success: true };
}

export async function getYouTubeAuthUrl() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const { data: config, error: configError } = await supabase
    .from('user_configs')
    .select('youtube_client_id')
    .eq('user_id', user.id)
    .single();

  if (configError || !config?.youtube_client_id) {
    throw new Error('Please enter and save your Client ID first.');
  }

  const clientId = decrypt(config.youtube_client_id);
  const redirectUri = `${process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'}/api/auth/youtube/callback`;
  
  const scopes = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/yt-analytics.readonly',
    'https://www.googleapis.com/auth/youtube.readonly'
  ];

  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.searchParams.set('client_id', clientId);
  url.searchParams.set('redirect_uri', redirectUri);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('scope', scopes.join(' '));
  url.searchParams.set('access_type', 'offline');
  url.searchParams.set('prompt', 'consent'); // Always prompt to ensure we get a refresh token

  return url.toString();
}
