'use client'

import React from 'react'
import Link from 'next/link'
import { Check, Sparkles, Zap, Trophy, ArrowRight } from 'lucide-react'

const tiers = [
  {
    name: 'Free',
    price: '$0',
    description: 'Perfect for starters and hobbyists.',
    features: [
      '3 Videos per month',
      'Standard AI Generation',
      'Basic Subtitles',
      'Community Support'
    ],
    cta: 'Start for Free',
    highlighted: false
  },
  {
    name: 'Pro',
    price: '$19',
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
    description: 'Build your automated empire at scale.',
    features: [
      'Managing Multi-Channels',
      'White-label Branding',
      'Custom Music Uploads',
      'Bulk Video Generation',
      'API Access',
      '24/7 Priority Support'
    ],
    cta: 'Contact Sales',
    highlighted: false
  }
]

export default function PricingPage() {
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
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight premium-gradient">
            Pick Your Growth Plan
          </h1>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto">
            Scale your reach with fully automated shorts. Choose the plan that fits your ambition.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 pt-12">
          {tiers.map((tier) => (
            <div 
              key={tier.name}
              className={`relative glass-card p-8 rounded-3xl border transition-all duration-500 hover:scale-[1.02] flex flex-col ${
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
                className={`w-full py-4 rounded-xl font-bold transition-all flex items-center justify-center gap-2 group ${
                  tier.highlighted 
                    ? 'btn-primary' 
                    : 'bg-white/5 hover:bg-white/10 border border-white/10 text-white'
                }`}
              >
                {tier.cta}
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          ))}
        </div>

        <div className="pt-20 border-t border-white/10">
          <div className="flex flex-col items-center gap-4 text-zinc-500 text-sm">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              <span>Secure payments powered by Stripe</span>
            </div>
            <p>Taxes may apply based on your location. Cancel anytime.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
