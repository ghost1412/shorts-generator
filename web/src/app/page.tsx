'use client'

import React from 'react'
import Link from 'next/link'
import { Sparkles, Youtube, Zap, Shield, ArrowRight, Play, CheckCircle2 } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] selection:bg-[#00e5ff]/30 relative overflow-x-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 glass-card !rounded-none border-b border-white/5 px-6 py-4 flex justify-between items-center backdrop-blur-xl">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 md:w-10 md:h-10 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-lg md:rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Sparkles className="text-white w-5 h-5 md:w-6 md:h-6" />
          </div>
          <span className="text-xl md:text-2xl font-bold tracking-tight premium-gradient">ShortsFlow</span>
        </div>
        <div className="flex items-center space-x-4 md:space-x-8 text-sm font-medium text-zinc-400">
          <Link href="#features" className="hidden md:block hover:text-white transition-colors">Features</Link>
          <Link href="/pricing" className="hidden md:block hover:text-white transition-colors">Pricing</Link>
          <Link href="/login" className="px-3 md:px-5 py-2 hover:bg-white/5 rounded-lg transition-all">Login</Link>
          <Link href="/signup" className="btn-primary px-4 md:px-6 py-2">Get Started</Link>
        </div>
      </nav>

      <main>
        {/* Hero Section */}
        <section className="relative pt-32 pb-20 px-6">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10 animate-pulse" />
          
          <div className="max-w-6xl mx-auto text-center space-y-8 relative z-10">
            <div className="inline-flex items-center space-x-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full text-xs font-medium text-[#00e5ff] mb-4">
              <Zap className="w-3 h-3" />
              <span>Version 2.0 is now live</span>
            </div>
            
            <h1 className="text-4xl md:text-8xl font-black tracking-tight leading-[1.2] md:leading-[1.1]">
              Automate Your <br />
              <span className="premium-gradient">Shorts Empire</span>
            </h1>
            
            <p className="text-base md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed px-4">
              The world's first AI-powered engine that creates, edits, and schedules viral shorts while you sleep. No more manual editing. Just pure growth.
            </p>

            <div className="flex flex-col md:flex-row items-center justify-center gap-4 pt-4">
              <Link href="/signup" className="btn-primary px-8 py-4 text-lg flex items-center gap-2 group w-full md:w-auto">
                Start Creating Free
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
              <button className="px-8 py-4 bg-white/5 border border-white/10 rounded-2xl font-bold flex items-center gap-2 hover:bg-white/10 transition-all w-full md:w-auto justify-center">
                <Play className="w-5 h-5" />
                Watch Demo
              </button>
            </div>

            <div className="pt-12 flex flex-wrap items-center justify-center gap-6 md:gap-8 opacity-40 grayscale hover:grayscale-0 transition-all">
              <span className="text-[10px] md:text-sm font-bold tracking-widest uppercase w-full md:w-auto">Trusted by</span>
              <Youtube className="w-6 h-6 md:w-8 md:h-8" />
              <div className="font-bold text-lg md:text-xl italic uppercase">IG Reels</div>
              <div className="font-bold text-lg md:text-xl uppercase tracking-tighter">TikTok</div>
            </div>
          </div>
        </section>

        {/* Features Grid */}
        <section id="features" className="py-20 px-6 bg-[#0c0c0e]">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-16 space-y-4">
              <h2 className="text-4xl font-bold">Everything you need to go viral</h2>
              <p className="text-zinc-500">Built for creators who want to scale without the burnout.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <FeatureCard 
                icon={<Zap className="text-yellow-400" />}
                title="Instant Generation"
                desc="Turn a niche topic into a fully edited 4K short in under 60 seconds."
              />
              <FeatureCard 
                icon={<Sparkles className="text-purple-400" />}
                title="AI Viral Hooks"
                desc="Our engine uses psychology to write scripts that maximize retention."
              />
              <FeatureCard 
                icon={<Shield className="text-emerald-400" />}
                title="Auto-Pilot Mode"
                desc="Schedule weeks of content in advance and let our server handle the rest."
              />
            </div>
          </div>
        </section>

        {/* Call to Action */}
        <section className="py-20 px-6">
          <div className="max-w-4xl mx-auto glass-card p-8 md:p-12 text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#00e5ff]/10 rounded-full blur-3xl -z-10" />
            <h2 className="text-2xl md:text-4xl font-bold mb-6">Ready to dominate the algorithm?</h2>
            <p className="text-zinc-400 mb-10 text-base md:text-lg">Join 2,500+ creators who are saving 20+ hours every week.</p>
            <Link href="/signup" className="btn-primary px-8 md:px-10 py-4 text-base md:text-lg inline-flex items-center gap-2 w-full md:w-auto justify-center">
              Get Started Now
              <CheckCircle2 className="w-5 h-5" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="py-10 border-t border-white/5 text-center text-zinc-500 text-sm">
        <p>&copy; 2026 ShortsFlow. All rights reserved.</p>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="glass-card p-8 space-y-4 hover:border-white/20 transition-all group">
      <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-xl font-bold">{title}</h3>
      <p className="text-zinc-500 leading-relaxed text-sm">{desc}</p>
    </div>
  )
}
