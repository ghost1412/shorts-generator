'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  BarChart3, 
  TrendingUp, 
  PlayCircle, 
  Clock, 
  ArrowLeft, 
  Filter,
  Download,
  Calendar,
  Sparkles,
  RefreshCcw,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { createClient } from '@/utils/supabase/client';
import { syncYouTubeAnalytics } from './actions';

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalViews: 0,
    totalVideos: 0,
    avgRetention: 0,
    viralRate: 0,
    topMode: 'N/A',
    weeklyViews: [0,0,0,0,0,0,0,0,0,0,0,0] as number[],
    modeDistribution: { FACTS: 0, STORY: 0, FIND_IT: 0 } as Record<string,number>
  });
  const [recentLogs, setRecentLogs] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  
  const supabase = createClient();

  useEffect(() => {
    async function fetchData() {
      const { data: logs } = await supabase
        .from('video_logs')
        .select('*')
        .order('created_at', { ascending: false });

      if (logs) {
        const totalViews = logs.reduce((acc, log) => acc + (log.views || 0), 0);
        const modeDistribution = logs.reduce((acc: any, log) => {
          acc[log.mode] = (acc[log.mode] || 0) + 1;
          return acc;
        }, { FACTS: 0, STORY: 0, FIND_IT: 0 });

        // Real average retention
        const retained = logs.filter(l => l.retention_rate > 0);
        const avgRet = retained.length > 0
          ? Math.round(retained.reduce((acc, l) => acc + l.retention_rate, 0) / retained.length)
          : 0;

        // Viral rate: % of videos with views > 10,000
        const viralVideos = logs.filter(l => (l.views || 0) > 10000).length;
        const viralRate = logs.length > 0 ? Math.round((viralVideos / logs.length) * 100) : 0;

        // Top mode by count
        const topMode = Object.entries(modeDistribution).sort((a, b) => (b[1] as number) - (a[1] as number))[0]?.[0] || 'N/A';

        // Weekly views chart — last 12 weeks
        const now = Date.now();
        const WEEK = 7 * 24 * 60 * 60 * 1000;
        const weeklyViews = Array(12).fill(0).map((_, i) => {
          const start = now - (11 - i + 1) * WEEK;
          const end = now - (11 - i) * WEEK;
          return logs
            .filter(l => { const t = new Date(l.created_at).getTime(); return t >= start && t < end; })
            .reduce((acc, l) => acc + (l.views || 0), 0);
        });
        const maxWeekly = Math.max(...weeklyViews, 1);
        const weeklyNorm = weeklyViews.map(v => Math.round((v / maxWeekly) * 100));

        setStats({
          totalViews,
          totalVideos: logs.length,
          avgRetention: avgRet,
          viralRate,
          topMode,
          weeklyViews: weeklyNorm,
          modeDistribution
        });
        setRecentLogs(logs.slice(0, 5));
      }
      setLoading(false);
    }
    fetchData();
  }, [supabase]);

  async function handleSync() {
    setSyncing(true);
    setMessage(null);
    try {
      const result = await syncYouTubeAnalytics();
      if (result.success) {
        setMessage({ type: 'success', text: `Successfully synced ${result.updated} videos! 🚀` });
        // Re-fetch data
        const { data: logs } = await supabase
          .from('video_logs')
          .select('*')
          .order('created_at', { ascending: false });
        
        if (logs) {
          const totalViews = logs.reduce((acc, log) => acc + (log.views || 0), 0);
          const modeDistribution = logs.reduce((acc: any, log) => {
            acc[log.mode] = (acc[log.mode] || 0) + 1;
            return acc;
          }, { FACTS: 0, STORY: 0, FIND_IT: 0 });

          const retained = logs.filter(l => l.retention_rate > 0);
          const avgRet = retained.length > 0
            ? Math.round(retained.reduce((acc, l) => acc + l.retention_rate, 0) / retained.length)
            : 0;

          const viralVideos = logs.filter(l => (l.views || 0) > 10000).length;
          const viralRate = logs.length > 0 ? Math.round((viralVideos / logs.length) * 100) : 0;
          const topMode = Object.entries(modeDistribution).sort((a, b) => (b[1] as number) - (a[1] as number))[0]?.[0] || 'N/A';

          const now = Date.now();
          const WEEK = 7 * 24 * 60 * 60 * 1000;
          const weeklyViews = Array(12).fill(0).map((_, i) => {
            const start = now - (11 - i + 1) * WEEK;
            const end = now - (11 - i) * WEEK;
            return logs
              .filter(l => { const t = new Date(l.created_at).getTime(); return t >= start && t < end; })
              .reduce((acc, l) => acc + (l.views || 0), 0);
          });
          const maxWeekly = Math.max(...weeklyViews, 1);
          const weeklyNorm = weeklyViews.map(v => Math.round((v / maxWeekly) * 100));

          setStats({
            totalViews,
            totalVideos: logs.length,
            avgRetention: avgRet,
            viralRate,
            topMode,
            weeklyViews: weeklyNorm,
            modeDistribution
          });
          setRecentLogs(logs.slice(0, 5));
        }
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Sync failed' });
    } finally {
      setSyncing(false);
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] p-8">
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Header */}
        <header className="flex justify-between items-end">
          <div className="space-y-4">
            <Link href="/dashboard" className="inline-flex items-center gap-2 text-zinc-500 hover:text-white transition-colors text-sm font-medium">
              <ArrowLeft size={16} />
              Back to Dashboard
            </Link>
            <h1 className="text-4xl font-bold flex items-center gap-3">
              <BarChart3 className="text-[#00e5ff]" size={32} />
              Performance Analytics
            </h1>
          </div>
          <div className="flex gap-3">
            <button className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-semibold flex items-center gap-2 hover:bg-white/10 transition-all">
              <Calendar size={14} />
              Last 30 Days
            </button>
            <button 
              onClick={handleSync}
              disabled={syncing}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${
                syncing 
                ? 'bg-zinc-800 text-zinc-500 animate-pulse' 
                : 'bg-[#00e5ff]/10 border border-[#00e5ff]/20 text-[#00e5ff] hover:bg-[#00e5ff]/20 cursor-pointer'
              }`}
            >
              <RefreshCcw size={14} className={syncing ? 'animate-spin' : ''} />
              {syncing ? 'Syncing...' : 'Sync Data'}
            </button>
            <button className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-xs font-semibold flex items-center gap-2 hover:bg-white/10 transition-all">
              <Download size={14} />
              Export Report
            </button>
          </div>
        </header>

        {message && (
          <div className={`p-4 rounded-xl flex items-center gap-3 border animate-in fade-in slide-in-from-top-2 ${
            message.type === 'success' 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {message.type === 'success' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        {/* Hero Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <AnalyticsStatCard 
            label="Total Views" 
            value={stats.totalViews.toLocaleString()} 
            growth={stats.totalVideos > 0 ? `${stats.totalVideos} videos` : 'No data'}
            icon={<TrendingUp className="text-emerald-400" />} 
          />
          <AnalyticsStatCard 
            label="Content Output" 
            value={stats.totalVideos.toString()} 
            growth={stats.totalVideos > 0 ? `${stats.totalVideos} total` : 'No videos yet'}
            icon={<PlayCircle className="text-blue-400" />} 
          />
          <AnalyticsStatCard 
            label="Avg. Retention" 
            value={`${stats.avgRetention}%`} 
            growth={stats.avgRetention > 0 ? 'From synced data' : 'Sync to update'}
            icon={<Clock className="text-purple-400" />} 
          />
          <AnalyticsStatCard 
            label="Viral Rate" 
            value={`${stats.viralRate}%`} 
            growth={stats.totalVideos > 0 ? `${stats.totalVideos > 0 ? 'Videos >10K views' : 'No data'}` : 'No data'}
            icon={<Sparkles className="text-yellow-400" />} 
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Chart Section (CSS Mockup) */}
          <section className="lg:col-span-2 glass-card p-8 space-y-8">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold">Views Over Time</h3>
              <div className="flex items-center gap-4 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">
                <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-[#00e5ff]" /> This Month</div>
                <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-white/10" /> Last Month</div>
              </div>
            </div>
            
            <div className="h-64 flex items-end justify-between gap-4 pt-4">
              {stats.weeklyViews.map((h, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-2 group">
                  <div className="w-full relative bg-white/5 rounded-t-lg overflow-hidden h-full">
                    <div 
                      className="absolute bottom-0 w-full bg-gradient-to-t from-[#00e5ff]/40 to-[#00e5ff] transition-all duration-1000 group-hover:brightness-125" 
                      style={{ height: `${h || 2}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-zinc-600 font-bold">W{i+1}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Mode Distribution */}
          <section className="glass-card p-8 flex flex-col justify-between">
            <h3 className="text-xl font-bold mb-6">Mode Distribution</h3>
            <div className="space-y-6">
              <DistributionRow label="Facts Mode" count={stats.modeDistribution.FACTS} total={stats.totalVideos} color="bg-cyan-400" />
              <DistributionRow label="Story Mode" count={stats.modeDistribution.STORY} total={stats.totalVideos} color="bg-orange-400" />
              <DistributionRow label="Interactive" count={stats.modeDistribution.FIND_IT} total={stats.totalVideos} color="bg-red-400" />
            </div>
              <div className="mt-8 p-4 bg-white/5 rounded-2xl border border-white/5 text-center">
                <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold mb-1">Top Performing</p>
                <p className="font-bold text-[#00e5ff]">
                  {stats.topMode !== 'N/A' ? `${stats.topMode} MODE` : 'No data yet'}
                </p>
              </div>
          </section>
        </div>

        {/* Recent Videos Table */}
        <section className="glass-card overflow-hidden">
          <div className="p-8 border-b border-white/5 flex justify-between items-center">
            <h3 className="text-xl font-bold">Top Content Performance</h3>
            <button className="text-xs font-bold text-zinc-500 hover:text-white transition-colors flex items-center gap-2">
              <Filter size={14} />
              Filter by Mode
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold border-b border-white/5">
                  <th className="px-8 py-4">Video Title</th>
                  <th className="px-8 py-4">Mode</th>
                  <th className="px-8 py-4">Views</th>
                  <th className="px-8 py-4">Status</th>
                  <th className="px-8 py-4">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recentLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-8 py-6 font-medium text-sm max-w-xs truncate">{log.title}</td>
                    <td className="px-8 py-6">
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        log.mode === 'STORY' ? 'bg-orange-500/20 text-orange-400' : 
                        log.mode === 'FIND_IT' ? 'bg-red-500/20 text-red-400' :
                        'bg-cyan-500/20 text-cyan-400'
                      }`}>
                        {log.mode}
                      </span>
                    </td>
                    <td className="px-8 py-6 font-bold text-sm">{(log.views || 0).toLocaleString()}</td>
                    <td className="px-8 py-6">
                       <span className={`flex items-center gap-1.5 text-xs ${
                        log.status === 'Published' ? 'text-emerald-400' : 
                        log.status === 'Failed' ? 'text-red-400' : 'text-blue-400'
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          log.status === 'Published' ? 'bg-emerald-400 animate-pulse' : 
                          log.status === 'Failed' ? 'bg-red-400' : 'bg-blue-400 animate-spin'
                        }`} />
                        {log.status}
                      </span>
                    </td>
                    <td className="px-8 py-6 text-xs text-zinc-500">{new Date(log.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function AnalyticsStatCard({ label, value, growth, icon }: { label: string, value: string, growth: string, icon: React.ReactNode }) {
  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex justify-between items-start">
        <div className="p-3 bg-white/5 rounded-2xl border border-white/5">
          {icon}
        </div>
        <span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-full">{growth}</span>
      </div>
      <div>
        <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold mb-1">{label}</p>
        <p className="text-3xl font-bold">{value}</p>
      </div>
    </div>
  );
}

function DistributionRow({ label, count, total, color }: { label: string, count: number, total: number, color: string }) {
  const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-xs font-bold">
        <span>{label}</span>
        <span className="text-zinc-500">{percentage}%</span>
      </div>
      <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-1000`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
