'use server'

import { createClient } from '@/utils/supabase/server';
import { decrypt } from '@/utils/crypto';
import crypto from 'crypto';

export async function syncYouTubeAnalytics() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  
  if (!user) throw new Error('Not authenticated');

  // 1. Get user credentials
  const { data: config, error: configError } = await supabase
    .from('user_configs')
    .select('youtube_client_id, youtube_client_secret, youtube_refresh_token')
    .eq('user_id', user.id)
    .single();

  if (configError || !config?.youtube_refresh_token) {
    throw new Error('YouTube account not connected. Please go to settings.');
  }

  // 2. Decrypt secrets
  const clientId = decrypt(config.youtube_client_id);
  const clientSecret = decrypt(config.youtube_client_secret);
  const refreshToken = decrypt(config.youtube_refresh_token);

  // 3. Get Access Token
  const keyFingerprint = crypto.createHash('sha256').update(process.env.ENCRYPTION_KEY || 'shortsflow-placeholder-master-key-32chars').digest('hex').substring(0, 8);
  const d = {
    idLen: clientId?.length,
    idPre: `${clientId?.substring(0, 4)}...${clientId?.slice(-4)}`,
    secLen: clientSecret?.length,
    secPre: `${clientSecret?.substring(0, 4)}...${clientSecret?.slice(-4)}`,
    tokenLen: refreshToken?.length,
    tokenPre: `${refreshToken?.substring(0, 4)}...${refreshToken?.slice(-4)}`,
    isEnc: config.youtube_refresh_token?.includes(':'),
    finger: keyFingerprint
  };

  const params = new URLSearchParams({
    client_id: (clientId || '').trim(),
    client_secret: (clientSecret || '').trim(),
    refresh_token: (refreshToken || '').trim(),
    grant_type: 'refresh_token',
  });

  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    body: params, // Fetch automatically sets application/x-www-form-urlencoded
  });

  const tokenData = await tokenRes.json();
  if (!tokenRes.ok) {
    console.error('[Sync] Google Token Error:', tokenData);
    const diag = `(ID: ${d.idLen} [${d.idPre}], Sec: ${d.secLen} [${d.secPre}], Tok: ${d.tokenLen} [${d.tokenPre}], Enc: ${d.isEnc})`;
    const errorBody = JSON.stringify(tokenData);
    throw new Error(`Failed to refresh token (${tokenRes.status}): ${errorBody} ${diag}`);
  }
  const accessToken = tokenData.access_token;

  // 4. Fetch Video Logs that have a youtube_video_id
  const { data: logs, error: logsError } = await supabase
    .from('video_logs')
    .select('id, youtube_video_id')
    .not('youtube_video_id', 'is', null);

  if (logsError) throw logsError;
  if (!logs || logs.length === 0) return { success: true, updated: 0 };

  // 5. Fetch Analytics for each video (or batch if many)
  // For simplicity and to avoid complex batching logic, we'll fetch a report for the last 30 days
  // and filter by the video IDs we have.
  const videoIds = logs.map(l => l.youtube_video_id).join(',');
  const analyticsUrl = `https://youtubeanalytics.googleapis.com/v2/reports?` + new URLSearchParams({
    ids: 'channel==MINE',
    startDate: '2024-01-01', // Should ideally be calculated
    endDate: new Date().toISOString().split('T')[0],
    metrics: 'views,averageViewPercentage,likes,comments',
    dimensions: 'video',
    filters: `video==${videoIds}`,
  });

  const analyticsRes = await fetch(analyticsUrl, {
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });

  const analyticsData = await analyticsRes.json();
  if (!analyticsRes.ok) {
     // If no data found for some reason, just return gracefully
     if (analyticsRes.status === 403) throw new Error('Insufficient permissions. ensure your Google App has Analytics API enabled.');
     return { success: true, updated: 0 };
  }

  // 6. Update database with real results
  const rows = analyticsData.rows || [];
  let updatedCount = 0;

  for (const row of rows) {
    const [ytId, views, avgRetention, likes, comments] = row;
    const log = logs.find(l => l.youtube_video_id === ytId);
    if (log) {
      const { error: updateError } = await supabase
        .from('video_logs')
        .update({
          views: views,
          retention_rate: Math.round(avgRetention),
          engagement_score: likes + comments,
        })
        .eq('id', log.id);
      
      if (!updateError) updatedCount++;
    }
  }

  return { success: true, updated: updatedCount };
}
