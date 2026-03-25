'use client'

import React from 'react'
import Link from 'next/link'
import { Sparkles, Youtube, Zap, Shield, ArrowRight, Play, CheckCircle2, Eye, Video } from 'lucide-react'

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
              <span>Version 3.0: Hybrid Audio-Visual AI is here</span>
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
          </div>
        </section>

        {/* 🚀 NEW: Product Playground Showcase */}
        <section className="py-24 px-6 relative overflow-hidden">
          <div className="max-w-6xl mx-auto text-center space-y-16">
            <div className="space-y-4">
              <h2 className="text-3xl md:text-5xl font-black tracking-tighter">THE POWER BEHIND THE MAGIC</h2>
              <p className="text-zinc-500 max-w-xl mx-auto">Click any engine to see how it dominates the algorithm.</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {[
                { id: 'AUTO', label: 'Magic Auto', icon: <Sparkles size={24} />, color: 'text-purple-400', desc: 'AI analyzes trends and picks the best niche for you.' },
                { id: 'FACTS', label: 'Facts', icon: <Eye size={24} />, color: 'text-cyan-400', desc: 'Mind-blowing educational content that drives saves.' },
                { id: 'STORY', label: 'Story', icon: <Video size={24} />, color: 'text-orange-400', desc: 'Narrative-driven shorts with high retention loops.' },
                { id: 'WYR', label: 'Would You Rather', icon: <Zap size={24} />, color: 'text-emerald-400', desc: 'Interactive psychological games for engagement.' },
                { id: 'REDDIT', label: 'Reddit', icon: <ArrowRight size={24} />, color: 'text-red-400', desc: 'Auto-narrated viral stories from top subreddits.' },
                { id: 'EXTRACT', label: 'AI Extraction', icon: <Play size={24} />, color: 'text-pink-400', desc: 'Turn long streams into massive batches of viral shorts.' },
              ].map(m => (
                <div key={m.id} className="glass-card p-6 flex flex-col items-center gap-4 hover:border-white/20 hover:scale-105 transition-all group cursor-pointer">
                  <div className={`p-4 bg-white/5 rounded-2xl ${m.color} group-hover:scale-110 transition-transform`}>
                    {m.icon}
                  </div>
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-widest text-white">{m.label}</p>
                    <p className="text-[8px] text-zinc-500 mt-2 leading-relaxed">{m.desc}</p>
                  </div>
                  <Link href="/signup" className="mt-2 text-[8px] font-bold text-[#00e5ff] hover:underline uppercase tracking-tighter">Try this Mode →</Link>
                </div>
              ))}
            </div>

            <div className="pt-12">
              <div className="glass-card p-12 relative overflow-hidden bg-gradient-to-br from-[#9d4edd]/5 to-[#00e5ff]/5 border-[#00e5ff]/20">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#00e5ff] to-transparent animate-pulse" />
                <div className="space-y-6 relative z-10">
                  <h3 className="text-2xl font-black italic uppercase tracking-tighter">Long-form to Shorts: Now in Closed Beta</h3>
                  <p className="text-zinc-400 max-w-2xl mx-auto text-sm">
                    Our new Audio-Visual Hybrid engine scans your 4-hour live streams in minutes, identifying every viral moment using pitch, energy, and speech-rate analysis.
                  </p>
                  <Link href="/signup" className="inline-flex px-8 py-3 bg-white text-black font-black rounded-xl hover:bg-zinc-200 transition-all uppercase text-xs tracking-widest">
                    Apply for Beta Access
                  </Link>
                </div>
              </div>
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
