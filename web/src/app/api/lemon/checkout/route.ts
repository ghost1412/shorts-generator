import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export async function POST(request: Request) {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { variantId, planName } = await request.json();

    if (!variantId) {
      return NextResponse.json({ error: 'Variant ID is required' }, { status: 400 });
    }

    const apiKey = process.env.LEMON_SQUEEZY_API_KEY;
    const storeId = process.env.LEMON_SQUEEZY_STORE_ID;

    if (!apiKey || !storeId) {
      return NextResponse.json({ error: 'Lemon Squeezy configuration missing' }, { status: 500 });
    }

    // Create a checkout session using Lemon Squeezy API
    // Documentation: https://docs.lemonsqueezy.com/api/checkouts#create-a-checkout
    const response = await fetch('https://api.lemonsqueezy.com/v1/checkouts', {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.api+json',
        'Content-Type': 'application/vnd.api+json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        data: {
          type: 'checkouts',
          attributes: {
            checkout_data: {
              email: user.email,
              custom: {
                user_id: user.id,
                plan_name: planName,
              },
            },
            product_options: {
              redirect_url: `${process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'}/dashboard`,
            },
          },
          relationships: {
            store: {
              data: {
                type: 'stores',
                id: storeId.toString(),
              },
            },
            variant: {
              data: {
                type: 'variants',
                id: variantId.toString(),
              },
            },
          },
        },
      }),
    });

    const data = await response.json();
    
    if (!response.ok) {
      console.error('Lemon Squeezy Error:', data);
      return NextResponse.json({ error: data.errors?.[0]?.detail || 'Checkout creation failed' }, { status: response.status });
    }

    return NextResponse.json({ 
      url: data.data.attributes.url 
    });
  } catch (error: any) {
    console.error('Lemon Squeezy Checkout Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
