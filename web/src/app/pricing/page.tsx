'use client'

import React from 'react'
import Link from 'next/link'
import { Check, Sparkles, Zap, Trophy, ArrowRight } from 'lucide-react'

const tiers = [
  {
    name: 'Free',
    price: '$0',
    priceId: '', // No Stripe for free
    variantId: '', // No LS for free
    description: 'Perfect for starters and hobbyists.',
    features: [
      '3 Videos per month',
      'Standard AI Generation',
      'Basic Subtitles',
      'Community Support'
    ],
    cta: 'Continue Free',
    highlighted: false
  },
  {
    name: 'Pro',
    price: '$19',
    priceId: 'price_1QvExamplePro', // Placeholder
    variantId: '12345', // Placeholder for Lemon Squeezy Variant ID
    description: 'The viral secret weapon for creators.',
    features: [
      'Unlimited Videos',
      'Advanced Story Mode',
      'Premium Vibe Selection',
      'Viral Hook Optimization',
      'Direct YouTube Posting',
      'Priority Cloud Rendering'
    ],
    cta: 'Get Pro Access',
    highlighted: true
  },
  {
    name: 'Agency',
    price: '$49',
    priceId: 'price_1QvExampleAgency', // Placeholder
    variantId: '67890', // Placeholder for Lemon Squeezy Variant ID
    description: 'Build your automated empire at scale.',
    features: [
      'Managing Multi-Channels',
      'White-label Branding',
      'Custom Music Uploads',
      'Bulk Video Generation',
      'API Access',
      '24/7 Priority Support'
    ],
    cta: 'Get Agency Access',
    highlighted: false
  }
]

export default function PricingPage() {
  const [loading, setLoading] = React.useState<string | null>(null)

  const handleSubscription = async (tier: typeof tiers[0]) => {
    if (tier.name === 'Free') {
      window.location.href = '/dashboard'
      return
    }

    setLoading(tier.name)
    try {
      // 🟢 PREFERENCE: If variantId exists, we use Lemon Squeezy (Easier for India/Global MoR)
      // If only priceId exists, we use Stripe.
      const isLemonSqueezy = !!tier.variantId;
      const apiEndpoint = isLemonSqueezy ? '/api/lemon/checkout' : '/api/stripe/checkout';
      
      const res = await fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          priceId: tier.priceId,
          variantId: tier.variantId,
          planName: tier.name 
        })
      })

      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        throw new Error(data.error || 'Checkout failed')
      }
    } catch (err) {
      console.error('Subscription error:', err)
      alert('Failed to start checkout. Please try again.')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] py-20 px-6 bg-gradient-to-b from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-[#00e5ff]/10 rounded-full blur-[120px] -z-10" />

      <div className="max-w-6xl mx-auto text-center space-y-8">
        <div className="space-y-4">
          <Link href="/" className="inline-flex items-center space-x-2 text-zinc-500 hover:text-white transition-colors">
            <ArrowRight className="w-4 h-4 rotate-180" />
            <span className="text-sm">Back to Dashboard</span>
          </Link>
          <h1 className="text-3xl md:text-6xl font-extrabold tracking-tight premium-gradient px-4">
            Pick Your Growth Plan
          </h1>
          <p className="text-base md:text-xl text-zinc-400 max-w-2xl mx-auto px-4">
            Scale your reach with fully automated shorts. Choose the plan that fits your ambition.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 pt-12">
          {tiers.map((tier) => (
            <div 
              key={tier.name}
              className={`relative glass-card p-6 md:p-8 rounded-3xl border transition-all duration-500 hover:scale-[1.02] flex flex-col ${
                tier.highlighted 
                  ? 'border-[#00e5ff]/50 bg-[#00e5ff]/5 shadow-[0_0_40px_rgba(0,229,255,0.15)] ring-1 ring-[#00e5ff]/50' 
                  : 'border-white/10 bg-white/5'
              }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-gradient-to-r from-[#9d4edd] to-[#00e5ff] text-white text-[10px] font-bold uppercase tracking-widest px-4 py-1.5 rounded-full shadow-lg">
                  Most Popular
                </div>
              )}

              <div className="mb-8 text-left">
                <h3 className="text-2xl font-bold mb-2 flex items-center gap-2">
                  {tier.name === 'Pro' && <Zap className="w-5 h-5 text-[#00e5ff]" />}
                  {tier.name === 'Agency' && <Trophy className="w-5 h-5 text-amber-500" />}
                  {tier.name}
                </h3>
                <div className="flex items-baseline gap-1">
                  <span className="text-5xl font-extrabold tracking-tight">{tier.price}</span>
                  <span className="text-zinc-500 font-medium">/month</span>
                </div>
                <p className="mt-4 text-sm text-zinc-400 leading-relaxed italic border-l-2 border-white/10 pl-3">
                  "{tier.description}"
                </p>
              </div>

              <div className="flex-1 space-y-4 mb-8">
                {tier.features.map((feature) => (
                  <div key={feature} className="flex items-center gap-3 text-sm text-zinc-300">
                    <div className="flex-shrink-0 w-5 h-5 rounded-full bg-white/5 flex items-center justify-center border border-white/10">
                      <Check className="w-3 h-3 text-[#00e5ff]" />
                    </div>
                    <span>{feature}</span>
                  </div>
                ))}
              </div>

              <button 
                onClick={() => handleSubscription(tier)}
                disabled={loading !== null}
                className={`w-full py-4 rounded-xl font-bold transition-all flex items-center justify-center gap-2 group ${
                  tier.highlighted 
                    ? 'btn-primary' 
                    : 'bg-white/5 hover:bg-white/10 border border-white/10 text-white'
                } ${loading === tier.name ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {loading === tier.name ? 'Redirecting...' : tier.cta}
                {loading !== tier.name && <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />}
              </button>
            </div>
          ))}
        </div>

        <div className="pt-20 border-t border-white/10">
          <div className="flex flex-col items-center gap-4 text-zinc-500 text-sm">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              <span>Secure payments via Stripe or Lemon Squeezy (MoR)</span>
            </div>
            <p>Taxes handled automatically. Global compliance guaranteed. Cancel anytime.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
