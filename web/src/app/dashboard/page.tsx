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
  LogOut,
  Trash2
} from 'lucide-react';
import { createClient } from '@/utils/supabase/client';
import { logout } from '../login/actions';

export default function Dashboard() {
  const [isTriggering, setIsTriggering] = useState(false);
  const [customScript, setCustomScript] = useState('');
  const [vibe, setVibe] = useState('suspense');
  const [videoLogs, setVideoLogs] = useState<any[]>([]);
  const [user, setUser] = useState<any>(null);
  const [userConfig, setUserConfig] = useState<any>(null);
  const [selectedMode, setSelectedMode] = useState('AUTO');
  const [selectedCategory, setSelectedCategory] = useState('random');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [thumbnailUrls, setThumbnailUrls] = useState<Record<string, string>>({});

  const modes = [
    { id: 'AUTO', label: 'Magic Auto', icon: <Sparkles size={16} />, color: 'text-purple-400' },
    { id: 'FACTS', label: 'Facts Mode', icon: <Eye size={16} />, color: 'text-cyan-400' },
    { id: 'STORY', label: 'Story Mode', icon: <Video size={16} />, color: 'text-orange-400' },
    { id: 'WYR', label: 'Would You Rather', icon: <Zap size={16} />, color: 'text-emerald-400' },
    { id: 'REDDIT', label: 'Reddit Stories', icon: <ArrowRight size={16} />, color: 'text-red-400' },
    { id: 'TRIVIA', label: 'Genius Trivia', icon: <PlusCircle size={16} />, color: 'text-yellow-400' },
    { id: 'QUOTE', label: 'Daily Quotes', icon: <Clock size={16} />, color: 'text-pink-400' },
    { id: 'ODD_ONE_OUT', label: 'Spot the Odd', icon: <Users size={16} />, color: 'text-indigo-400' },
    { id: 'NEWS', label: '😂 Funny News', icon: <TrendingUp size={16} />, color: 'text-green-400' },
    { id: 'NEWS_SERIOUS', label: '📰 Serious News', icon: <TrendingUp size={16} />, color: 'text-blue-400' },
  ];
  const supabase = createClient();

  useEffect(() => {
    async function init() {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
      
      if (user) {
        const { data: logs } = await supabase
          .from('video_logs')
          .select('*')
          .eq('user_id', user.id)
          .order('created_at', { ascending: false });
        if (logs) setVideoLogs(logs);

        const { data: config } = await supabase.from('user_configs').select('*').single();
        if (config) setUserConfig(config);
      }
    }
    init();
  }, [supabase]);

  useEffect(() => {
    if (!user) return;

    async function fetchLogs() {
      const { data } = await supabase
        .from('video_logs')
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false });
      if (data) setVideoLogs(data);

      // Also refresh user_configs to get updated generations_used
      const { data: config } = await supabase.from('user_configs').select('*').single();
      if (config) setUserConfig(config);
    }

    // Fetch thumbnails for logs that have them
    const logsWithThumbs = videoLogs.filter(log => log.thumbnail_path && !thumbnailUrls[log.id]);
    if (logsWithThumbs.length > 0) {
      logsWithThumbs.forEach(async (log) => {
        try {
          const res = await fetch('/api/video/signed-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ storage_path: log.thumbnail_path })
          });
          const json = await res.json();
          if (json.signedUrl) {
            setThumbnailUrls(prev => ({ ...prev, [log.id]: json.signedUrl }));
          }
        } catch (e) {
          console.error('Thumbnail fetch error:', e);
        }
      });
    }

    // Smart Polling Logic
    const hasProcessing = videoLogs.some(log => !['Published', 'Failed'].includes(log.status));
    const interval = setInterval(fetchLogs, hasProcessing ? 5000 : 15000);
    
    return () => clearInterval(interval);
  }, [user, supabase, videoLogs.length, videoLogs.some(log => log.status === 'Processing'), Object.keys(thumbnailUrls).length]);

  async function triggerGeneration(mode = 'AUTO', category = 'random', script = '') {
    const generationsUsed = userConfig?.generations_used || 0;
    const maxVideos = userConfig?.max_videos || 3;

    if (userConfig?.plan === 'free' && generationsUsed >= maxVideos) {
      alert(`❌ Usage limit reached! You have used all ${maxVideos} generations in your free plan. Upgrade to Pro for unlimited!`);
      return;
    }
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
        // Immediately fetch logs to show the "Processing" row
        const { data: updatedLogs } = await supabase
          .from('video_logs')
          .select('*')
          .eq('user_id', user.id)
          .order('created_at', { ascending: false });
        if (updatedLogs) setVideoLogs(updatedLogs);
      }
      else alert(`❌ Failed: ${data.error}`);
    } catch (err) {
      alert('❌ Error connecting to bridge.');
    } finally {
      setIsTriggering(false);
    }
  }

  async function deleteVideo(videoId: string) {
    if (!confirm('Are you sure you want to delete this video log?')) return;
    try {
      const res = await fetch(`/api/video/${videoId}`, { method: 'DELETE' });
      if (res.ok) {
        setVideoLogs(prev => prev.filter(v => v.id !== videoId));
      } else {
        const data = await res.json();
        alert(`❌ Failed to delete: ${data.error}`);
      }
    } catch (err) {
      alert('❌ Error deleting video.');
    }
  }

  const niches = ["Science", "Space", "Anime Lore", "Cooking Hacks", "History", "Animal Facts"];

  return (
    <div className="flex h-screen bg-[#0a0a0c] text-[#f0f0f5] overflow-hidden relative">
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-300"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:relative lg:flex lg:w-72
        w-80 h-full glass-card m-0 lg:m-4 lg:mr-0 
        flex-col p-6 space-y-8 z-50 transition-transform duration-300
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-xl flex items-center justify-center shadow-lg shadow-purple-500/20">
              <Sparkles className="text-white w-6 h-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight premium-gradient">ShortsFlow</h1>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-zinc-500 hover:text-white">
            <PlusCircle className="rotate-45" size={24} />
          </button>
        </div>

        <nav className="flex-1 space-y-2">
          <Link href="/dashboard" onClick={() => setSidebarOpen(false)}>
            <NavItem icon={<LayoutDashboard size={20} />} label="Dashboard" active />
          </Link>
          <div className="opacity-50 cursor-not-allowed">
            <NavItem icon={<Youtube size={20} />} label="Channels (Soon)" inactive />
          </div>
          <Link href="/analytics" onClick={() => setSidebarOpen(false)}>
            <NavItem icon={<BarChart3 size={20} />} label="Analytics" />
          </Link>
          <Link href="/settings" onClick={() => setSidebarOpen(false)}>
            <NavItem icon={<Settings size={20} />} label="Settings" />
          </Link>
          <div onClick={() => logout()} className="flex items-center space-x-3 px-4 py-3 rounded-xl cursor-pointer transition-all duration-200 text-zinc-500 hover:text-red-400 hover:bg-red-500/5 mt-auto">
            <LogOut size={20} />
            <span className="text-sm">Log Out</span>
          </div>
        </nav>

        <div className="p-4 bg-white/5 rounded-2xl border border-white/10 relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-[#9d4edd] to-[#00e5ff]" />
          <p className="text-[10px] text-zinc-500 mb-1 uppercase tracking-widest font-bold">Current Plan</p>
          <div className="flex justify-between items-end mb-3">
            <p className="font-extrabold text-sm capitalize">{userConfig?.plan || 'Free'}</p>
              {userConfig?.plan === 'free' && (
                <div className="text-sm font-medium text-slate-400">
                  {userConfig?.generations_used || 0} / {userConfig?.max_videos || 3} generations used
                </div>
              )}
          </div>
          <div className="w-full bg-zinc-800 h-1.5 rounded-full mb-4 overflow-hidden">
            <div 
              className="bg-gradient-to-r from-[#9d4edd] to-[#00e5ff] h-full transition-all duration-1000" 
              style={{ width: `${Math.min((videoLogs.length / (userConfig?.max_videos || 3)) * 100, 100)}%` }}
            />
          </div>
          <Link href="/pricing" className="block w-full py-2 bg-gradient-to-r from-[#9d4edd]/20 to-[#00e5ff]/20 hover:from-[#9d4edd]/30 hover:to-[#00e5ff]/30 text-center text-[10px] font-bold rounded-lg border border-white/5 transition-all">
            UPGRADE NOW
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-8 overflow-y-auto">
        <header className="flex flex-col md:flex-row md:justify-between md:items-center gap-6 mb-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 bg-white/5 border border-white/10 rounded-lg"
              >
                <LayoutDashboard size={20} className="text-[#00e5ff]" />
              </button>
              <div>
                <h2 className="text-xl md:text-3xl font-bold">Welcome back, {user?.email?.split('@')[0] || 'Manager'} 👋</h2>
                <p className="text-xs md:text-sm text-zinc-500 mt-1">Performing 24% better this week.</p>
              </div>
            </div>
          </div>

          {/* YouTube Connection Warning */}
          {!userConfig?.youtube_refresh_token && !isTriggering && (
            <div className="flex-1 md:max-w-md bg-orange-500/10 border border-orange-500/20 rounded-2xl p-4 flex items-center gap-4 animate-pulse">
              <div className="p-2 bg-orange-500/20 rounded-lg">
                <Youtube size={20} className="text-orange-400" />
              </div>
              <div className="flex-1">
                <p className="text-xs font-bold text-orange-400 uppercase tracking-wider">Channel Not Connected</p>
                <p className="text-[10px] text-zinc-400 mt-0.5">Connect your YouTube channel in settings to enable auto-posting.</p>
              </div>
              <Link href="/settings" className="px-3 py-1.5 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 text-[10px] font-bold rounded-lg transition-colors border border-orange-500/20">
                FIX NOW
              </Link>
            </div>
          )}
          
          <button 
            onClick={() => triggerGeneration(selectedMode, selectedCategory)}
            disabled={isTriggering}
            className="w-full md:w-auto btn-primary flex items-center justify-center gap-2 disabled:opacity-50 py-4 md:py-3"
          >
            <Youtube size={20} />
            <span className="text-sm font-bold truncate">
              {isTriggering ? 'Triggering...' : `Trigger ${selectedMode} (${selectedCategory.replace('_', ' ')})`}
            </span>
          </button>
        </header>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 mb-10">
          <StatCard 
            icon={<TrendingUp className="text-emerald-400" />} 
            label="Total Views" 
            value={videoLogs.reduce((acc, log) => acc + (log.views || 0), 0).toLocaleString()} 
            growth="+0% this week" 
          />
          <CheckCard 
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
                <div key={vid.id} className="group relative bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden hover:border-zinc-700 transition-all">
                  <button 
                    onClick={(e) => { e.stopPropagation(); deleteVideo(vid.id); }}
                    className="absolute top-2 right-2 p-1.5 bg-red-500/10 text-red-500 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500 hover:text-white z-10"
                  >
                    <Trash2 size={14} />
                  </button>
                  <div 
                        onClick={async () => {
                      if (vid.storage_path) {
                        const res = await fetch('/api/video/signed-url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ storage_path: vid.storage_path }) });
                        const json = await res.json();
                        console.log('[Dashboard] Signed URL response:', json);
                        if (json.signedUrl) {
                          window.open(json.signedUrl, '_blank');
                        } else {
                          console.error('[Dashboard] Failed to get signed URL:', json.error);
                          alert(`Failed to get download link: ${json.error || 'Unknown error'}`);
                        }
                      } else if (vid.download_url) {
                        window.open(vid.download_url, '_blank');
                      }
                    }} 
                    className="flex w-full gap-4 p-4 cursor-pointer"
                  >
                    <div className={`w-24 h-32 bg-zinc-800 rounded-lg overflow-hidden relative flex-shrink-0 ${vid.status === 'Processing' ? 'animate-pulse' : ''}`}>
                      {thumbnailUrls[vid.id] ? (
                        <img 
                          src={thumbnailUrls[vid.id]} 
                          alt={vid.title} 
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-2 flex-col justify-center items-center">
                          { !['Published', 'Failed'].includes(vid.status) ? (
                            <div className="flex flex-col items-center gap-1 group-hover:scale-110 transition-transform">
                              <div className="w-8 h-8 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
                              <span className="text-[10px] font-medium text-[#00e5ff] animate-pulse">
                                {vid.status || 'Processing...'}
                              </span>
                            </div>
                          ) : (
                            <PlayCircle className="text-white opacity-0 group-hover:opacity-100 transition-opacity w-8 h-8" />
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col justify-between py-1 flex-1 min-w-0">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          vid.mode === 'STORY' ? 'bg-orange-500/20 text-orange-400' : 
                          vid.mode === 'FIND_IT' ? 'bg-red-500/20 text-red-400' :
                          'bg-cyan-500/20 text-cyan-400'
                        }`}>
                          {vid.mode}
                        </span>
                        {vid.status === 'Processing' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-500 animate-pulse border border-yellow-500/30">
                            Processing...
                          </span>
                        )}
                      </div>
                      <h4 className="font-semibold text-sm line-clamp-1">{vid.title}</h4>
                        {vid.status === 'Published' && (
                          <button 
                                      onClick={async (e) => {
                              e.stopPropagation();
                              if (vid.storage_path) {
                                const res = await fetch('/api/video/signed-url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ storage_path: vid.storage_path }) });
                                const json = await res.json();
                                console.log('[Dashboard] Signed URL response:', json);
                                if (json.signedUrl) {
                                  window.open(json.signedUrl, '_blank');
                                } else {
                                  console.error('[Dashboard] Failed to get signed URL:', json.error);
                                  alert(`Failed to get download link: ${json.error || 'Unknown error'}`);
                                }
                              } else if (vid.download_url) {
                                window.open(vid.download_url, '_blank');
                              }
                            }}
                            className="p-1 px-3 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 rounded-lg text-[10px] font-medium transition-colors flex items-center gap-1.5"
                          >
                            <Download className="w-3 h-3" />
                            Download MP4
                          </button>
                        )}
                    </div>
                    <p className="text-xs text-zinc-500 mt-2 truncate">
                      {vid.status === 'Processing' ? 'Rendering AI media...' : `${vid.views || 0} views • ${vid.created_at ? new Date(vid.created_at).toLocaleDateString() : 'Just now'}`}
                    </p>
                  </div>
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
            <h3 className="text-xl font-bold">Generation Config</h3>
            <div className="glass-card p-6 space-y-6">
              
              {/* Mode Selection */}
              <div className="space-y-3">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Select Mode</p>
                <div className="grid grid-cols-2 gap-2">
                  {modes.map(m => (
                    <button 
                      key={m.id} 
                      onClick={() => setSelectedMode(m.id)}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border transition-all ${
                        selectedMode === m.id 
                          ? 'bg-white/10 border-white/20 text-white' 
                          : 'bg-white/5 border-white/5 text-zinc-500 hover:border-white/10'
                      }`}
                    >
                      <span className={m.color}>{m.icon}</span>
                      <span className="text-[10px] font-bold uppercase truncate">{m.label.split(' ')[0]}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Niche Selection */}
              <div className="space-y-3">
                <p className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Select Category</p>
                <div className="flex flex-wrap gap-2">
                  {niches.map(n => {
                    const norm_n = n.toLowerCase().replace(' ', '_');
                    return (
                      <button 
                        key={n} 
                        onClick={() => setSelectedCategory(norm_n)}
                        className={`px-3 py-1.5 border rounded-lg text-xs transition-colors ${
                          selectedCategory === norm_n 
                            ? 'bg-[#00e5ff]/10 border-[#00e5ff] text-[#00e5ff]' 
                            : 'bg-white/5 border-white/10 text-zinc-400 hover:border-white/20'
                        }`}
                      >
                        {n}
                      </button>
                    );
                  })}
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
    <div className="glass-card p-4 md:p-6 flex items-center justify-between">
      <div className="space-y-1 overflow-hidden">
        <p className="text-[10px] md:text-xs text-zinc-500 uppercase tracking-widest font-bold truncate">{label}</p>
        <p className="text-2xl md:text-3xl font-bold truncate">{value}</p>
        <span className="text-[10px] md:text-xs text-emerald-400 font-medium truncate inline-block">{growth}</span>
      </div>
      <div className="p-2 md:p-3 bg-white/5 rounded-2xl border border-white/5 flex-shrink-0 text-[#00e5ff]">
        {icon}
      </div>
    </div>
  );
}

function CheckCard({ icon, label, value, growth }: { icon: React.ReactNode, label: string, value: string, growth: string }) {
    return (
      <div className="glass-card p-4 md:p-6 flex items-center justify-between">
        <div className="space-y-1 overflow-hidden">
          <p className="text-[10px] md:text-xs text-zinc-500 uppercase tracking-widest font-bold truncate">{label}</p>
          <p className="text-2xl md:text-3xl font-bold truncate">{value}</p>
          <span className="text-[10px] md:text-xs text-blue-400 font-medium truncate inline-block">{growth}</span>
        </div>
        <div className="p-2 md:p-3 bg-white/5 rounded-2xl border border-white/5 flex-shrink-0 text-[#00e5ff]">
          {icon}
        </div>
      </div>
    );
  }
