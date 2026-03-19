'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { createClient } from '@/utils/supabase/client'
import { saveUserSettings, deleteYouTubeAuth, getYouTubeAuthUrl } from './actions'
import { 
  Settings, 
  Youtube, 
  Save, 
  ArrowLeft, 
  ArrowRight,
  Zap,
  CheckCircle2,
  AlertCircle,
  Trash2
} from 'lucide-react'


export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [advancedMode, setAdvancedMode] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [config, setConfig] = useState({
    youtube_client_id: '',
    youtube_client_secret: '',
    youtube_refresh_token: '',
    default_vibe: 'suspense'
  })
  
  const supabase = createClient()

  useEffect(() => {
    // Check for callback status in URL
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      if (params.get('success') === 'youtube_connected') {
        setMessage({ type: 'success', text: 'YouTube account linked successfully! 🎥✨' });
        window.history.replaceState({}, '', window.location.pathname);
      } else if (params.get('error')) {
        setMessage({ type: 'error', text: `Failed to link: ${params.get('error')}` });
        window.history.replaceState({}, '', window.location.pathname);
      }
    }

    async function fetchConfig() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        const { data, error } = await supabase
          .from('user_configs')
          .select('*')
          .eq('user_id', user.id)
          .single()
        
        if (data) {
          setConfig(prev => ({
            ...prev,
            youtube_client_id: data.youtube_client_id || '',
            youtube_client_secret: data.youtube_client_secret || '',
            youtube_refresh_token: data.youtube_refresh_token || '',
            default_vibe: data.default_vibe || 'suspense'
          }))
        }
      }
      setLoading(false)
    }
    fetchConfig()
  }, [supabase])

  async function handleSave() {
    console.log('[Settings] Save clicked');
    setSaving(true)
    setMessage(null)
    try {
      await saveUserSettings(config)
      setMessage({ type: 'success', text: 'Settings updated successfully (Encrypted)! 🔒' })
    } catch (err: any) {
      console.error('[Settings] Save error:', err);
      setMessage({ type: 'error', text: err.message || 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  async function handleDisconnect() {
    console.log('[Settings] Disconnect clicked');
    if (!confirm('Are you sure you want to disconnect YouTube? This will wipe your credentials.')) return
    
    setDisconnecting(true)
    setMessage(null)
    try {
      await deleteYouTubeAuth()
      setConfig({
        youtube_client_id: '',
        youtube_client_secret: '',
        youtube_refresh_token: '',
        default_vibe: config.default_vibe
      })
      setMessage({ type: 'success', text: 'YouTube account disconnected and wiped. 🗑️' })
    } catch (err: any) {
      console.error('[Settings] Disconnect error:', err);
      setMessage({ type: 'error', text: err.message || 'Failed to disconnect' })
    } finally {
      setDisconnecting(false)
    }
  }

  function handleConnect() {
    window.location.href = '/oauth/consent';
  }

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] p-8 bg-gradient-to-b from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="p-2 hover:bg-white/5 rounded-xl transition-colors">
              <ArrowLeft size={24} className="text-zinc-500" />
            </Link>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Settings className="text-[#9d4edd]" />
                System Settings
              </h1>
              <p className="text-zinc-500">Configure your automation engine & integrations.</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setAdvancedMode(!advancedMode)}
              className={`text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded-full transition-all border ${
                advancedMode 
                  ? 'bg-[#00e5ff]/10 border-[#00e5ff]/30 text-[#00e5ff]' 
                  : 'bg-white/5 border-white/10 text-zinc-500 hover:text-white'
              }`}
            >
              {advancedMode ? 'Hide Details' : 'Show Details'}
            </button>
            <button 
              onClick={handleSave}
              disabled={saving}
              className="bg-white text-black px-8 py-3 rounded-2xl font-bold flex items-center gap-2 hover:bg-zinc-200 transition-all disabled:opacity-50"
            >
              <Save size={20} />
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </header>

        {message && (
          <div className={`p-4 rounded-xl flex items-center gap-3 border animate-in fade-in slide-in-from-top-2 ${
            message.type === 'success' 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {message.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* YouTube Integration */}
          <section className="glass-card p-8 space-y-6">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-white/5 rounded-2xl border border-white/5 text-red-500">
                  <Youtube />
                </div>
                <div>
                  <h3 className="font-bold">Social Automation</h3>
                  <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold">Direct Publishing</p>
                </div>
              </div>
              <Link href="/settings/guide" className="text-[10px] text-[#00e5ff] hover:underline flex items-center gap-1 font-bold">
                Setup Guide <ArrowRight size={10} />
              </Link>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-400">YouTube Client ID</label>
                <input 
                  type="password"
                  value={config.youtube_client_id}
                  onChange={(e) => setConfig({ ...config, youtube_client_id: e.target.value })}
                  placeholder="xxxxxxxx.apps.googleusercontent.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-xs focus:border-[#00e5ff]/50 outline-none transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-400">YouTube Client Secret</label>
                <input 
                  type="password"
                  value={config.youtube_client_secret}
                  onChange={(e) => setConfig({ ...config, youtube_client_secret: e.target.value })}
                  placeholder="GOCSPX-xxxxxxxxxxxx"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-xs focus:border-[#00e5ff]/50 outline-none transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-400">YouTube Refresh Token</label>
                <input 
                  type="password"
                  value={config.youtube_refresh_token}
                  onChange={(e) => setConfig({ ...config, youtube_refresh_token: e.target.value })}
                  placeholder="1//xxxxxxxxxxxxxxxxxxxx"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-xs focus:border-[#00e5ff]/50 outline-none transition-all"
                />
              </div>
            </div>

            <div className="flex gap-4 pt-2">
              <button 
                onClick={handleSave}
                disabled={saving}
                className="flex-1 bg-white text-black h-12 rounded-2xl font-bold flex items-center justify-center gap-2 hover:bg-zinc-200 transition-all disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save YouTube Auth'}
              </button>
              
              <button 
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="px-6 border border-red-500/20 bg-red-500/5 text-red-500 rounded-2xl font-bold flex items-center justify-center gap-2 hover:bg-red-500/10 transition-all disabled:opacity-50"
              >
                <Trash2 size={18} />
                {disconnecting ? '...' : 'Disconnect'}
              </button>
            </div>

            <button 
              onClick={handleConnect}
              disabled={connecting}
              className="w-full h-14 bg-gradient-to-r from-red-600 to-red-500 text-white rounded-2xl font-bold flex items-center justify-center gap-3 hover:from-red-500 hover:to-red-400 transition-all shadow-lg shadow-red-500/20 group disabled:opacity-50"
            >
              <Youtube className="group-hover:scale-110 transition-transform" />
              {connecting ? 'Redirecting to Google...' : 'Connect YouTube Channel'}
            </button>
          </section>

          {/* Engine Preferences */}
          <section className="glass-card p-8 flex flex-col justify-center">
            <h3 className="font-bold mb-6 flex items-center gap-2">
              <Zap className="text-[#00e5ff]" size={20} />
              Default Engine Vibe
            </h3>
            <div className="grid grid-cols-2 gap-4">
              {['suspense', 'spooky', 'cinematic', 'upbeat'].map((v) => (
                <button
                  key={v}
                  onClick={() => setConfig({ ...config, default_vibe: v })}
                  className={`px-4 py-4 rounded-xl border text-sm font-medium capitalize transition-all ${
                    config.default_vibe === v 
                      ? 'bg-[#00e5ff]/10 border-[#00e5ff]/50 text-[#00e5ff]' 
                      : 'bg-white/5 border-white/10 text-zinc-500 hover:bg-white/10'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </section>
        </div>

        <footer className="pt-10 flex items-center justify-between text-zinc-600 text-xs border-t border-white/5">
          <div className="flex gap-4">
            <Link href="#" className="hover:text-white">Terms of Use</Link>
            <Link href="#" className="hover:text-white">Privacy Policy</Link>
          </div>
          <p>Product ID: ShortsFlow-V2-Production</p>
        </footer>
      </div>
    </div>
  )
}
