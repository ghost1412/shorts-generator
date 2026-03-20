'use server'

import { createClient } from '@/utils/supabase/server';
import { decrypt } from '@/utils/crypto';
import crypto from 'crypto';

export async function syncYouTubeAnalytics() {
  try {
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

    // 2. Decrypt secrets (Safe decrypt handles non-encrypted values)
    const clientId = decrypt(config.youtube_client_id);
    const clientSecret = decrypt(config.youtube_client_secret);
    const refreshToken = decrypt(config.youtube_refresh_token);

    if (!clientId || !clientSecret || !refreshToken) {
      throw new Error('YouTube credentials are empty or corrupted. Re-connect in settings.');
    }

    // 3. Get Access Token
    const params = new URLSearchParams({
      client_id: clientId.trim(),
      client_secret: clientSecret.trim(),
      refresh_token: refreshToken.trim(),
      grant_type: 'refresh_token',
    });

    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      body: params,
    });

    const tokenData = await tokenRes.json();
    if (!tokenRes.ok) {
      console.error('[Sync] Google Token Error:', tokenData);
      throw new Error(`Google Auth failed: ${JSON.stringify(tokenData)}`);
    }
    const accessToken = tokenData.access_token;

    // 4. Fetch Video Logs (only this user's videos)
    const { data: logs, error: logsError } = await supabase
      .from('video_logs')
      .select('id, youtube_video_id')
      .eq('user_id', user.id)
      .not('youtube_video_id', 'is', null);

    if (logsError) throw logsError;
    if (!logs || logs.length === 0) return { success: true, updated: 0 };

    // 5. Fetch Analytics
    const videoIds = logs.map(l => l.youtube_video_id?.trim()).filter(id => !!id).join(',');
    if (!videoIds) {
        console.log('[Sync] No video IDs found to sync.');
        return { success: true, updated: 0 };
    }

    const analyticsUrl = `https://youtubeanalytics.googleapis.com/v2/reports?` + new URLSearchParams({
      ids: 'channel==MINE',
      startDate: '2024-01-01',
      endDate: new Date().toISOString().split('T')[0],
      metrics: 'views,averageViewPercentage,likes,comments',
      dimensions: 'video',
      filters: `video==${videoIds}`,
    });

    console.log('[Sync] Requesting Google Analytics:', analyticsUrl);

    const analyticsRes = await fetch(analyticsUrl, {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });

    const analyticsData = await analyticsRes.json();
    console.log('[Sync] Raw Google Response:', JSON.stringify(analyticsData));

    if (!analyticsRes.ok) {
        const errReason = analyticsData?.error?.message || JSON.stringify(analyticsData);
        console.error('[Sync] Google Analytics API Error:', analyticsData);
        if (analyticsRes.status === 403) {
          throw new Error(`Analytics API permission denied: ${errReason}. Make sure the YouTube Analytics API is enabled in Google Cloud, and re-connect your YouTube account in settings to refresh permissions.`);
        }
        throw new Error(`Analytics API returned ${analyticsRes.status}: ${errReason}`);
    }

    // 6. Update database
    const rows = analyticsData.rows || [];
    console.log(`[Sync] Found ${rows.length} rows in Google reports.`);
    let updatedCount = 0;

    for (const row of rows) {
      // Row format: [ytId, views, avgRetention, likes, comments]
      if (!row || row.length < 2) continue;
      
      const [ytId, views, avgRetention, likes, comments] = row;
      console.log(`[Sync] Comparing Google ID "${ytId}" with local logs...`);
      const log = logs.find(l => l.youtube_video_id?.trim() === ytId);
      
      if (log) {
        // Defensive values
        const dViews = parseInt(views) || 0;
        const dRet = Math.round(parseFloat(avgRetention) || 0);
        const dEng = (parseInt(likes) || 0) + (parseInt(comments) || 0);

        const { error: updateError } = await supabase
          .from('video_logs')
          .update({
            views: dViews,
            retention_rate: dRet,
            engagement_score: dEng,
          })
          .eq('id', log.id);
        
        if (!updateError) updatedCount++;
      }
    }

    return { success: true, updated: updatedCount };
  } catch (err: any) {
    console.error('[Sync Action Error]:', err);
    // Return error message instead of throwing to avoid RSC crash
    return { success: false, error: err.message || 'An unexpected error occurred during sync.' };
  }
}
