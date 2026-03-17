'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  BarChart3,
  LayoutDashboard,
  Video,
  Settings,
  Users,
  PlusCircle,
  Youtube,
  Sparkles,
  Zap,
  TrendingUp,
  Clock,
  Lock,
  ArrowRight,
  PlayCircle,
  Download,
  Eye,
  CheckCircle2,
  LogOut
} from 'lucide-react';
import { createClient } from '@/utils/supabase/client';
import { logout } from './login/actions';

export default function Dashboard() {
  const [isTriggering, setIsTriggering] = useState(false);
  const [customScript, setCustomScript] = useState('');
  const [vibe, setVibe] = useState('suspense');
  const [videoLogs, setVideoLogs] = useState<any[]>([]);
  const [user, setUser] = useState<any>(null);
  const supabase = createClient();

  useEffect(() => {
    async function getSession() {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
    }
    getSession();

    async function fetchLogs() {
      const { data } = await supabase
        .from('video_logs')
        .select('*')
        .order('created_at', { ascending: false });
      if (data) setVideoLogs(data);
    }
    fetchLogs();

    // Polling or Realtime can be added here
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, [supabase]);

  async function triggerGeneration(mode = 'AUTO', category = 'random', script = '') {
    setIsTriggering(true);
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, category, customScript: script || customScript, vibe }),
      });
      const data = await res.json();
      if (res.ok) {
        alert('🚀 Video generation triggered on GitHub Actions!');
        if (script || customScript) setCustomScript('');
      }
      else alert(`❌ Failed: ${data.error}`);
    } catch (err) {
      alert('❌ Error connecting to bridge.');
    } finally {
      setIsTriggering(false);
    }
  }


  const niches = ["Science", "Space", "Anime Lore", "Cooking Hacks", "History", "Animal Facts"];

  return (
    <div className="flex h-screen bg-[#0a0a0c] text-[#f0f0f5] overflow-hidden">
      {/* Sidebar */}
      <aside className="w-72 glass-card m-4 mr-0 flex flex-col p-6 space-y-8">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Sparkles className="text-white w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight premium-gradient">ShortsFlow</h1>
        </div>

        <nav className="flex-1 space-y-2">
          <NavItem icon={<LayoutDashboard size={20} />} label="Dashboard" active />
          <NavItem icon={<Youtube size={20} />} label="Channels (Soon)" inactive />
          <NavItem icon={<BarChart3 size={20} />} label="Analytics (Soon)" inactive />
          <NavItem icon={<Settings size={20} />} label="Settings (Soon)" inactive />
          <div onClick={() => logout()} className="flex items-center space-x-3 px-4 py-3 rounded-xl cursor-pointer transition-all duration-200 text-zinc-500 hover:text-red-400 hover:bg-red-500/5 mt-auto">
            <LogOut size={20} />
            <span className="text-sm">Log Out</span>
          </div>
        </nav>

        <div className="p-4 bg-white/5 rounded-xl border border-white/10">
          <p className="text-xs text-zinc-500 mb-2 uppercase tracking-widest font-semibold">Current Plan</p>
          <p className="font-bold text-sm">Pro Channel Manager</p>
          <div className="w-full bg-zinc-800 h-1.5 rounded-full mt-3 overflow-hidden">
            <div className="bg-gradient-to-r from-[#9d4edd] to-[#00e5ff] w-3/4 h-full" />
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h2 className="text-3xl font-bold">Welcome back, {user?.email?.split('@')[0] || 'Manager'} 👋</h2>
            <p className="text-zinc-500 mt-1">Your automated channels are performing 24% better this week.</p>
          </div>
          <button 
            onClick={() => triggerGeneration()}
            disabled={isTriggering}
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
          >
            <Youtube size={20} />
            {isTriggering ? 'Triggering...' : 'Trigger Live Run'}
          </button>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <StatCard 
            icon={<TrendingUp className="text-emerald-400" />} 
            label="Total Views" 
            value={videoLogs.reduce((acc, log) => acc + (log.views || 0), 0).toLocaleString()} 
            growth="+0% this week" 
          />
          <StatCard 
            icon={<CheckCircle2 className="text-blue-400" />} 
            label="Videos Posted" 
            value={videoLogs.length.toString()} 
            growth="Active" 
          />
          <StatCard 
            icon={<Clock className="text-purple-400" />} 
            label="Avg. Retention" 
            value={`${videoLogs.length > 0 ? '78' : '0'}%`} 
            growth="Stable" 
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Active Campaigns */}
          <section className="lg:col-span-2 space-y-6">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold">Recently Generated</h3>
              <button className="text-sm text-[#00e5ff] hover:underline">View all</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {videoLogs.length > 0 ? videoLogs.slice(0, 4).map((vid) => (
                <div key={vid.id} className="glass-card p-4 flex gap-4 hover:bg-white/10 transition-colors cursor-pointer group">
                  <div className="w-24 h-32 bg-zinc-800 rounded-lg overflow-hidden relative flex-shrink-0">
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-2">
                       <PlayCircle className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </div>
                  <div className="flex flex-col justify-between py-1">
                    <div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        vid.mode === 'STORY' ? 'bg-orange-500/20 text-orange-400' : 
                        vid.mode === 'FIND_IT' ? 'bg-red-500/20 text-red-400' :
                        'bg-cyan-500/20 text-cyan-400'
                      }`}>
                        {vid.mode}
                      </span>
                      <h4 className="font-semibold text-sm mt-2 line-clamp-2">{vid.title}</h4>
                    </div>
                    <p className="text-xs text-zinc-500">{vid.views || 0} views • {new Date(vid.created_at).toLocaleDateString()}</p>
                  </div>
                </div>
              )) : (
                <div className="md:col-span-2 py-10 text-center border-2 border-dashed border-white/5 rounded-2xl">
                  <p className="text-zinc-500 text-sm italic">No videos generated yet. Press "Trigger Live Run" to start!</p>
                </div>
              )}
            </div>
          </section>

          {/* Quick Config */}
          <section className="space-y-6">
            <h3 className="text-xl font-bold">Auto-Niche Config</h3>
            <div className="glass-card p-6 space-y-6">
              {/* Niche Selection */}
              <div className="space-y-3">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Select Category</p>
                <div className="flex flex-wrap gap-2">
                  {niches.map(n => (
                    <button 
                      key={n} 
                      onClick={() => triggerGeneration('AUTO', n.toLowerCase().replace(' ', '_'))}
                      className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs transition-colors hover:border-[#00e5ff]/50"
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Vibe Selection */}
              <div className="pt-6 border-t border-white/5 space-y-4">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Select Vibe</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: 'suspense', icon: '⏳', label: 'Suspense' },
                    { id: 'spooky', icon: '👻', label: 'Spooky' },
                    { id: 'cinematic', icon: '🎬', label: 'Cinematic' },
                    { id: 'upbeat', icon: '⚡', label: 'Upbeat' }
                  ].map((v) => (
                    <button
                      key={v.id}
                      onClick={() => setVibe(v.id)}
                      className={`flex items-center gap-2 px-3 py-3 rounded-xl border transition-all ${
                        vibe === v.id 
                          ? 'bg-[#00e5ff]/10 border-[#00e5ff]/50 text-[#00e5ff]' 
                          : 'bg-white/5 border-white/10 text-zinc-400 hover:border-white/20'
                      }`}
                    >
                      <span className="text-lg">{v.icon}</span>
                      <span className="text-xs font-medium">{v.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Extreme Game Mode */}
              <div className="pt-6 border-t border-white/5 space-y-4">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Mode: FIND IT (Interactive)</p>
                <button 
                  onClick={() => triggerGeneration('FIND_IT', 'random')}
                  disabled={isTriggering}
                  className="w-full py-3 bg-gradient-to-r from-orange-500/10 to-red-500/10 hover:from-orange-500/20 hover:to-red-500/20 border border-orange-500/30 rounded-xl flex items-center justify-center gap-3 transition-all group"
                >
                  <PlayCircle className="text-orange-400 group-hover:scale-110 transition-transform" />
                  <div className="text-left">
                    <p className="text-xs font-bold text-orange-400">GENERATE CHALLENGE</p>
                    <p className="text-[10px] text-zinc-500">Extreme "Find the Target" Game</p>
                  </div>
                </button>
              </div>

              {/* Manual Script Input */}
              <div className="pt-6 border-t border-white/5 space-y-4">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Bring Your Own Script</p>
                <textarea 
                  value={customScript}
                  onChange={(e) => setCustomScript(e.target.value)}
                  placeholder="Paste your shocking true story or manual script here..."
                  className="w-full h-32 bg-white/5 border border-white/10 rounded-xl p-3 text-xs focus:outline-none focus:border-[#9d4edd]/50 transition-all placeholder:text-zinc-600 resize-none"
                />
                <button 
                  onClick={() => triggerGeneration('STORY', 'custom')}
                  disabled={!customScript || isTriggering}
                  className="w-full py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs font-semibold disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  {isTriggering ? 'Processing...' : 'Generate from Script'}
                </button>
              </div>

              <div className="pt-6 border-t border-white/5 space-y-4">
                <div className="flex items-center justify-between opacity-50">
                  <span className="text-xs">Alternating Mode</span>
                  <div className="w-8 h-4 bg-zinc-700 rounded-full p-1">
                    <div className="w-2 h-2 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
                <div className="flex items-center justify-between opacity-50">
                  <span className="text-xs">High-Frequency Posting</span>
                  <div className="w-8 h-4 bg-zinc-700 rounded-full p-1">
                    <div className="w-2 h-2 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
                <p className="text-[10px] text-zinc-600 text-center uppercase tracking-tighter">Pro Features Coming Soon</p>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active = false, inactive = false }: { icon: React.ReactNode, label: string, active?: boolean, inactive?: boolean }) {
  return (
    <div className={`flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-200 ${
      active 
        ? 'bg-white/10 text-white shadow-inner font-semibold border border-white/5 cursor-default' 
        : inactive
          ? 'text-zinc-700 cursor-not-allowed grayscale'
          : 'text-zinc-500 hover:text-white hover:bg-white/5 cursor-pointer'
    }`}>
      {icon}
      <span className="text-sm">{label}</span>
    </div>
  );
}

function StatCard({ icon, label, value, growth }: { icon: React.ReactNode, label: string, value: string, growth: string }) {
  return (
    <div className="glass-card p-6 flex items-center justify-between">
      <div className="space-y-1">
        <p className="text-xs text-zinc-500 uppercase tracking-widest font-bold">{label}</p>
        <p className="text-3xl font-bold">{value}</p>
        <span className="text-xs text-emerald-400 font-medium">{growth}</span>
      </div>
      <div className="p-3 bg-white/5 rounded-2xl border border-white/5">
        {icon}
      </div>
    </div>
  );
}
