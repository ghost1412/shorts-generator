'use client'

import React from 'react'
import Link from 'next/link'
import { createClient } from '@/utils/supabase/client'
import { Sparkles, Youtube, Zap, Shield, ArrowRight, Play, CheckCircle2, Eye, Video, Clock, TrendingUp, PlusCircle, Users } from 'lucide-react'

export default function LandingPage() {
  const [applied, setApplied] = React.useState(false)
  const [isApplying, setIsApplying] = React.useState(false)
  const [extracting, setExtracting] = React.useState(false)
  const [extractPhase, setExtractPhase] = React.useState('idle') // idle, scanning, splitting, done
  const [user, setUser] = React.useState<any>(null)
  const supabase = createClient()
  
  React.useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [])
  
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
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10 animate-pulse pointer-events-none" />
          
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

            <div className="space-y-12">
              {[
                { 
                  title: 'AI Templates', 
                  modes: [
                    { id: 'AUTO', label: 'Magic Auto', icon: <Sparkles size={32} />, color: 'text-purple-400', desc: 'Predictive trend analysis.' },
                    { id: 'FACTS', label: 'Facts', icon: <Eye size={32} />, color: 'text-cyan-400', desc: 'Educational viral facts.' },
                    { id: 'STORY', label: 'Story', icon: <Video size={32} />, color: 'text-orange-400', desc: 'Narrative retention loops.' },
                    { id: 'REDDIT', label: 'Reddit', icon: <ArrowRight size={32} />, color: 'text-red-400', desc: 'Subreddit viral stories.' },
                    { id: 'QUOTE', label: 'Quotes', icon: <Clock size={32} />, color: 'text-pink-400', desc: 'Daily motivational clips.' },
                    { id: 'TREND', label: 'Viral Trends', icon: <TrendingUp size={32} />, color: 'text-yellow-300', desc: 'Algorithm-focused trends.' },
                  ] 
                },
                { 
                  title: 'Interactive Games', 
                  modes: [
                    { id: 'WYR', label: 'Would You Rather', icon: <Zap size={32} />, color: 'text-emerald-400', desc: 'Psychology-based games.' },
                    { id: 'TRIVIA', label: 'Trivia', icon: <PlusCircle size={32} />, color: 'text-yellow-400', desc: 'Genius-level trivia.' },
                    { id: 'ODD_ONE_OUT', label: 'Odd One Out', icon: <Users size={32} />, color: 'text-indigo-400', desc: 'Visual attention tests.' },
                    { id: 'CHALLENGE', label: 'Breathing', icon: <Sparkles size={32} />, color: 'text-rose-400', desc: 'Interactive viral challenges.' },
                  ] 
                },
                { 
                  title: 'Reporter News', 
                  modes: [
                    { id: 'NEWS', label: 'Funny News', icon: <TrendingUp size={32} />, color: 'text-green-400', desc: 'Satirical entertainment news.' },
                    { id: 'NEWS_SERIOUS', label: 'Serious News', icon: <TrendingUp size={32} />, color: 'text-blue-400', desc: 'Global headlines & reports.' },
                  ] 
                }
              ].map(cat => (
                <div key={cat.title} className="space-y-8">
                  <h3 className="text-[10px] font-black text-zinc-600 uppercase tracking-[0.4em]">{cat.title}</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
                    {cat.modes.map(m => (
                      <div key={m.id} className="glass-card p-6 flex flex-col items-center gap-4 hover:border-white/20 hover:scale-105 transition-all group cursor-pointer">
                        <div className={`p-5 bg-white/5 rounded-2xl ${m.color} group-hover:scale-110 transition-transform shadow-lg shadow-black/20`}>
                          {m.icon}
                        </div>
                        <div className="text-center space-y-1.5">
                          <p className="text-xs font-black uppercase tracking-widest text-white leading-none">{m.label}</p>
                          <p className="text-[10px] text-zinc-500 leading-tight font-medium px-2">{m.desc}</p>
                        </div>
                        <Link href="/login" className="mt-1 text-[10px] font-black text-[#00e5ff] hover:text-white transition-colors uppercase tracking-widest border border-[#00e5ff]/20 px-4 py-1.5 rounded-full hover:bg-[#00e5ff]/10">Try Demo</Link>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-12" id="beta">
              <div className="glass-card p-8 md:p-16 relative overflow-hidden bg-gradient-to-br from-[#9d4edd]/5 to-[#00e5ff]/5 border-[#00e5ff]/20">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[#00e5ff] to-transparent animate-pulse" />
                
                <div className="grid lg:grid-cols-2 gap-12 items-center">
                  <div className="space-y-8 text-left relative z-10">
                    <div className="inline-flex items-center space-x-2 px-3 py-1 bg-[#00e5ff]/10 border border-[#00e5ff]/20 rounded-full text-[10px] font-black text-[#00e5ff] uppercase tracking-widest">
                      <Zap className="w-3 h-3" />
                      <span>Closed Beta Access</span>
                    </div>
                    <h3 className="text-3xl md:text-5xl font-black italic uppercase tracking-tighter leading-none">
                      Long-form <br />
                      <span className="text-[#00e5ff]">to Viral Clips</span>
                    </h3>
                    <p className="text-zinc-400 max-w-md text-sm leading-relaxed">
                      Our new Audio-Visual Hybrid engine scans your 4-hour live streams in minutes, identifying every viral moment using pitch, energy, and speech-rate analysis.
                    </p>
                    
                    {applied ? (
                      <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl inline-block animate-in zoom-in-95 duration-500">
                        <p className="text-emerald-400 font-black uppercase text-xs tracking-widest">
                          ✨ Application Received! We'll reach out to your email soon.
                        </p>
                      </div>
                    ) : !user ? (
                      <div className="space-y-4">
                        <p className="text-zinc-500 text-xs italic">Log in to claim your spot in the queue.</p>
                        <Link 
                          href="/login"
                          className="inline-flex px-8 py-3 bg-white text-black font-black rounded-xl hover:bg-zinc-200 transition-all uppercase text-[10px] tracking-widest cursor-pointer"
                        >
                          Login to Join Beta
                        </Link>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="p-4 bg-white/5 border border-white/10 rounded-xl max-w-sm">
                          <p className="text-[10px] text-zinc-500 uppercase font-bold mb-1">Applying as</p>
                          <p className="text-sm font-bold text-white">{user.email}</p>
                        </div>
                        <button 
                          onClick={async () => {
                            setIsApplying(true);
                            try {
                              await supabase.from('beta_applications').insert({ 
                                user_id: user.id,
                                email: user.email 
                              });
                              console.log('Beta application for:', user.email);
                            } catch (err) {
                               console.error('Waitlist error:', err);
                            }
                            setTimeout(() => {
                              setIsApplying(false);
                              setApplied(true);
                            }, 800);
                          }}
                          disabled={isApplying}
                          className="px-10 py-4 bg-gradient-to-r from-[#9d4edd] to-[#00e5ff] text-white font-black rounded-xl hover:scale-105 transition-all shadow-lg shadow-purple-500/20 uppercase text-[10px] tracking-widest cursor-pointer disabled:opacity-50"
                        >
                          {isApplying ? 'Processing...' : 'Claim My Beta Spot'}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* High-Fidelity VFX Area */}
                  <div className="relative h-[300px] flex items-center justify-center bg-black/40 rounded-3xl border border-white/5 overflow-hidden group">
                    {!extracting ? (
                      <button 
                        onClick={() => {
                          setExtracting(true);
                          setExtractPhase('scanning');
                          setTimeout(() => setExtractPhase('splitting'), 3000);
                          setTimeout(() => setExtractPhase('done'), 4500);
                        }}
                        className="flex flex-col items-center gap-4 group cursor-pointer"
                      >
                        <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center border border-white/10 group-hover:scale-110 group-hover:bg-[#00e5ff]/10 group-hover:border-[#00e5ff]/30 transition-all duration-500">
                          <Play className="w-8 h-8 text-zinc-500 group-hover:text-[#00e5ff]" />
                        </div>
                        <p className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest group-hover:text-white transition-colors">Click to Demo Extraction</p>
                      </button>
                    ) : (
                      <div className="relative w-full h-full flex items-center justify-center">
                        {/* The "Neural Pulse" Ring */}
                        {extractPhase === 'scanning' && (
                          <div className="absolute w-40 h-40 border-2 border-[#00e5ff]/30 rounded-full animate-pulse-ring" />
                        )}

                        {/* Main Video Icon */}
                        <div className={`relative z-20 transition-all duration-700 ${extractPhase !== 'scanning' ? 'scale-0 opacity-0' : 'scale-100 opacity-100'}`}>
                          <div className="w-48 h-28 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-2xl border border-white/20 flex items-center justify-center shadow-2xl backdrop-blur-md">
                            <Video className="w-12 h-12 text-[#00e5ff] animate-pulse" />
                            <div className="animate-scan" />
                          </div>
                        </div>

                        {/* Splitting Assets (Shorts) */}
                        {(extractPhase === 'splitting' || extractPhase === 'done') && (
                          <>
                            <div className="absolute z-30 animate-split-1">
                              <div className="w-16 h-28 bg-white/10 rounded-lg border border-white/20 flex flex-col items-center justify-center gap-2 backdrop-blur-xl">
                                <Sparkles className="w-4 h-4 text-purple-400" />
                                <span className="text-[6px] font-black text-white uppercase tracking-tighter">Viral #1</span>
                              </div>
                            </div>
                            <div className="absolute z-30 animate-split-2">
                              <div className="w-16 h-28 bg-white/10 rounded-lg border border-white/20 flex flex-col items-center justify-center gap-2 backdrop-blur-xl">
                                <Zap className="w-4 h-4 text-amber-400" />
                                <span className="text-[6px] font-black text-white uppercase tracking-tighter">Viral #2</span>
                              </div>
                            </div>
                            <div className="absolute z-30 animate-split-3">
                              <div className="w-16 h-28 bg-white/10 rounded-lg border border-white/20 flex flex-col items-center justify-center gap-2 backdrop-blur-xl">
                                <Eye className="w-4 h-4 text-cyan-400" />
                                <span className="text-[6px] font-black text-white uppercase tracking-tighter">Viral #3</span>
                              </div>
                            </div>
                            <div className="absolute z-30 animate-split-4">
                              <div className="w-16 h-28 bg-white/10 rounded-lg border border-white/20 flex flex-col items-center justify-center gap-2 backdrop-blur-xl">
                                <TrendingUp className="w-4 h-4 text-emerald-400" />
                                <span className="text-[6px] font-black text-white uppercase tracking-tighter">Viral #4</span>
                              </div>
                            </div>
                            
                            {/* The Narrative Reel (Horizontal) */}
                            <div className="absolute z-20 animate-split-hl">
                              <div className="w-40 h-24 bg-[#00e5ff]/5 rounded-xl border border-[#00e5ff]/30 flex flex-col items-center justify-center gap-3 shadow-[0_0_30px_rgba(0,229,255,0.1)]">
                                <Video className="w-6 h-6 text-[#00e5ff]" />
                                <span className="text-[8px] font-black text-white uppercase tracking-[0.2em]">Narrative Reel</span>
                              </div>
                            </div>
                          </>
                        )}

                        {extractPhase === 'done' && (
                          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-[8px] font-black text-[#00e5ff] uppercase tracking-[0.4em] animate-in fade-in slide-in-from-bottom-2 duration-1000">
                            Extraction Complete
                          </div>
                        )}
                        
                        {/* Reset button inside VFX area */}
                        {extractPhase === 'done' && (
                          <button 
                            onClick={() => setExtracting(false)}
                            className="absolute top-4 right-4 p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
                          >
                            <ArrowRight className="w-3 h-3 rotate-180" />
                          </button>
                        )}
                      </div>
                    )}
                    
                    {/* Background Grid for VFX field */}
                    <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none" />
                  </div>
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
