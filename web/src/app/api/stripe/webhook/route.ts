import { NextResponse } from 'next/server';
import { headers } from 'next/headers';
import Stripe from 'stripe';
import { createClient } from '@supabase/supabase-js';

function getStripe() {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error('STRIPE_SECRET_KEY is missing');
  return new Stripe(key, {
    apiVersion: '2024-12-18.acacia' as any,
  });
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Supabase admin credentials missing');
  return createClient(url, key);
}

export async function POST(request: Request) {
  const body = await request.text();
  const signature = (await headers()).get('stripe-signature') as string;

  let event: Stripe.Event;

  try {
    const stripe = getStripe();
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err: any) {
    console.error(`❌ Webhook signature verification failed: ${err.message}`);
    return NextResponse.json({ error: `Webhook Error: ${err.message}` }, { status: 400 });
  }

  // Handle the event
  switch (event.type) {
    case 'checkout.session.completed':
      const session = event.data.object as Stripe.Checkout.Session;
      const userId = session.metadata?.userId;
      const planName = session.metadata?.planName || 'pro';

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
      break;
    
    case 'customer.subscription.deleted':
      const subscription = event.data.object as Stripe.Subscription;
      const subUserId = subscription.metadata?.userId;

      if (subUserId) {
        console.log(`❌ Subscription cancelled for user ${subUserId}. Downgrading to free.`);
        
        const supabaseAdmin = getSupabaseAdmin();
        await supabaseAdmin
          .from('user_configs')
          .update({
            plan: 'free',
            max_videos: 3,
            updated_at: new Date().toISOString()
          })
          .eq('user_id', subUserId);
      }
      break;

    default:
      console.log(`Unhandled event type ${event.type}`);
  }

  return NextResponse.json({ received: true });
}
