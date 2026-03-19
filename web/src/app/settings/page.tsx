'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import { createClient } from '@/utils/supabase/client'
import { 
  Settings, 
  Github, 
  Youtube, 
  Save, 
  ArrowLeft, 
  ShieldCheck, 
  Globe, 
  Zap,
  CheckCircle2,
  AlertCircle
} from 'lucide-react'

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [config, setConfig] = useState({
    github_token: '',
    github_repo: '',
    youtube_api_key: '',
    default_vibe: 'suspense'
  })
  
  const supabase = createClient()

  useEffect(() => {
    async function fetchConfig() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        const { data, error } = await supabase
          .from('user_configs')
          .select('*')
          .eq('user_id', user.id)
          .single()
        
        if (data) {
          setConfig({
            github_token: data.github_token || '',
            github_repo: data.github_repo || '',
            youtube_api_key: data.youtube_api_key || '',
            default_vibe: data.default_vibe || 'suspense'
          })
        }
      }
      setLoading(false)
    }
    fetchConfig()
  }, [supabase])

  async function handleSave() {
    setSaving(true)
    setMessage(null)
    try {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) throw new Error('Not authenticated')

      const { error } = await supabase
        .from('user_configs')
        .upsert({
          user_id: user.id,
          ...config,
          updated_at: new Date().toISOString()
        })

      if (error) throw error
      setMessage({ type: 'success', text: 'Settings updated successfully! 🚀' })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-[#0a0a0c] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] p-8">
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
          <button 
            onClick={handleSave}
            disabled={saving}
            className="btn-primary px-8 py-3 flex items-center gap-2 disabled:opacity-50"
          >
            <Save size={20} />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </header>

        {message && (
          <div className={`p-4 rounded-xl flex items-center gap-3 border ${
            message.type === 'success' 
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {message.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* GitHub Integration */}
          <section className="glass-card p-8 space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-white/5 rounded-2xl border border-white/5">
                <Github className="text-white" />
              </div>
              <div>
                <h3 className="font-bold">GitHub Actions</h3>
                <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold">Cloud Rendering</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400">Personal Access Token</label>
                <input 
                  type="password"
                  value={config.github_token}
                  onChange={(e) => setConfig({ ...config, github_token: e.target.value })}
                  placeholder="ghp_xxxxxxxxxxxx"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:border-[#00e5ff]/50 outline-none transition-all"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400">Repository (owner/repo)</label>
                <input 
                  type="text"
                  value={config.github_repo}
                  onChange={(e) => setConfig({ ...config, github_repo: e.target.value })}
                  placeholder="username/shorts-generator"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:border-[#00e5ff]/50 outline-none transition-all"
                />
              </div>
            </div>
          </section>

          {/* YouTube Integration */}
          <section className="glass-card p-8 space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-white/5 rounded-2xl border border-white/5 text-red-500">
                <Youtube />
              </div>
              <div>
                <h3 className="font-bold">Social Automation</h3>
                <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold">Direct Publishing</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400">YouTube Data API Key</label>
                <input 
                  type="password"
                  value={config.youtube_api_key}
                  onChange={(e) => setConfig({ ...config, youtube_api_key: e.target.value })}
                  placeholder="AIzaSyXXXXXXXXXXXXXXXXX"
                  className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-sm focus:border-red-500/50 outline-none transition-all"
                />
              </div>
              <div className="p-4 bg-orange-500/5 border border-orange-500/10 rounded-xl">
                <p className="text-xs text-orange-400 flex items-center gap-2">
                  <ShieldCheck size={14} />
                  OAuth2 authentication is managed in Profile.
                </p>
              </div>
            </div>
          </section>

          {/* Engine Preferences */}
          <section className="md:col-span-2 glass-card p-8">
            <h3 className="font-bold mb-6 flex items-center gap-2">
              <Zap className="text-[#00e5ff]" size={20} />
              Default Engine Preferences
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {['suspense', 'spooky', 'cinematic', 'upbeat'].map((v) => (
                <button
                  key={v}
                  onClick={() => setConfig({ ...config, default_vibe: v })}
                  className={`px-4 py-3 rounded-xl border text-sm font-medium capitalize transition-all ${
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
