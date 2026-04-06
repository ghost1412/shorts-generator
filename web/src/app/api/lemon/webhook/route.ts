import { NextResponse } from 'next/server';
import crypto from 'crypto';
import { createClient } from '@supabase/supabase-js';

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Supabase admin credentials missing');
  return createClient(url, key);
}

export async function POST(request: Request) {
  const body = await request.text();
  const signature = request.headers.get('x-signature') as string;
  const secret = process.env.LEMON_SQUEEZY_WEBHOOK_SECRET;

  if (!secret || !signature) {
    return NextResponse.json({ error: 'Webhook configuration missing' }, { status: 400 });
  }

  // Verify signature
  const hmac = crypto.createHmac('sha256', secret);
  const digest = hmac.update(body).digest('hex');
  if (digest !== signature) {
    console.error('Invalid signature');
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
  }

  const payload = JSON.parse(body);
  const eventName = payload.meta.event_name;
  const customData = payload.meta.custom_data;

  console.log(`[Lemon Squeezy Webhook] Received ${eventName}`);

  if (eventName === 'order_created' || eventName === 'subscription_created' || eventName === 'subscription_updated') {
    const userId = customData?.user_id;
    const planName = customData?.plan_name || 'pro';
    
    if (userId) {
      console.log(`✅ Payment received for user ${userId}. Upgrading to ${planName}.`);
      
      const maxVideos = planName.toLowerCase() === 'agency' ? 500 : 100;

      const supabaseAdmin = getSupabaseAdmin();
      const { error } = await supabaseAdmin
        .from('user_configs')
        .update({
          plan: planName.toLowerCase(),
          max_videos: maxVideos,
          updated_at: new Date().toISOString()
        })
        .eq('user_id', userId);

      if (error) {
        console.error('Error updating user plan:', error.message);
      }
    }
  } else if (eventName === 'subscription_cancelled' || eventName === 'subscription_expired') {
    const userId = customData?.user_id;

    if (userId) {
      console.log(`❌ Subscription ended for user ${userId}. Downgrading to free.`);
      
      const supabaseAdmin = getSupabaseAdmin();
      await supabaseAdmin
        .from('user_configs')
        .update({
          plan: 'free',
          max_videos: 3, // Standard free tier limit
          updated_at: new Date().toISOString()
        })
        .eq('user_id', userId);
    }
  }

  return NextResponse.json({ received: true });
}
