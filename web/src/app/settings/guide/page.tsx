import React from 'react'
import Link from 'next/link'
import { ArrowLeft, ExternalLink, Key, Shield, Youtube } from 'lucide-react'

export default function YouTubeGuidePage() {
  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] py-20 px-6">
      <div className="max-w-3xl mx-auto space-y-12">
        <Link href="/settings" className="inline-flex items-center space-x-2 text-zinc-500 hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Settings</span>
        </Link>

        <div className="space-y-4">
          <h1 className="text-4xl font-extrabold premium-gradient">YouTube API Setup Guide</h1>
          <p className="text-zinc-400">
            Follow these 3 steps to connect your channel to ShortsFlow. This ensures 100% privacy and uses your own free Google API quota.
          </p>
        </div>

        <div className="space-y-12">
          {/* Step 1 */}
          <section className="space-y-4 border-l-2 border-[#00e5ff]/30 pl-6 relative">
            <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-[#00e5ff] shadow-[0_0_10px_#00e5ff]" />
            <h2 className="text-xl font-bold flex items-center gap-2">
              <span className="text-[#00e5ff]">01.</span> Create a Google Cloud Project
            </h2>
            <p className="text-sm text-zinc-400">
              Go to the <a href="https://console.cloud.google.com/" target="_blank" className="text-[#00e5ff] hover:underline inline-flex items-center gap-1">Google Cloud Console <ExternalLink className="w-3 h-3"/></a> and create a new project named "ShortsFlow". 
            </p>
            <ul className="list-disc list-inside text-sm text-zinc-500 space-y-1 ml-4">
              <li>Enable the **YouTube Data API v3**.</li>
              <li>Enable the **YouTube Analytics API**.</li>
              <li>Configure the **OAuth Consent Screen** (User Type: External).</li>
            </ul>
          </section>

          {/* Step 2 */}
          <section className="space-y-4 border-l-2 border-[#9d4edd]/30 pl-6 relative">
            <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-[#9d4edd] shadow-[0_0_10px_#9d4edd]" />
            <h2 className="text-xl font-bold flex items-center gap-2">
              <span className="text-[#9d4edd]">02.</span> Generate OAuth Credentials
            </h2>
            <p className="text-sm text-zinc-400">
              Go to **Credentials &gt; Create Credentials &gt; OAuth Client ID**.
            </p>
            <ul className="list-disc list-inside text-sm text-zinc-500 space-y-1 ml-4">
              <li>Application Type: **Web Application**.</li>
              <li>Authorized Redirect URI: <code className="bg-white/5 px-2 py-0.5 rounded text-[#00e5ff]">http://localhost:3000/api/auth/youtube/callback</code></li>
              <li>Copy your **Client ID** and **Client Secret**.</li>
            </ul>
          </section>

          {/* Step 3 */}
          <section className="space-y-4 border-l-2 border-emerald-500/30 pl-6 relative">
            <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-emerald-500 shadow-[0_0_10px_emerald]" />
            <h2 className="text-xl font-bold flex items-center gap-2">
              <span className="text-emerald-500">03.</span> One-Click Connection
            </h2>
            <p className="text-sm text-zinc-400">
              No more manual tokens! Simply:
            </p>
            <ul className="list-disc list-inside text-sm text-zinc-500 space-y-1 ml-4">
              <li>Enter your **Client ID** & **Secret** in Settings.</li>
              <li>Click **"Save YouTube Auth"**.</li>
              <li>Click the big red **"Connect YouTube Channel"** button.</li>
              <li>Approve the consent screen and you are DONE! 🚀</li>
            </ul>
          </section>
        </div>

        <div className="bg-white/5 border border-white/10 p-8 rounded-3xl space-y-6">
          <div className="flex items-center gap-4">
            <Shield className="w-8 h-8 text-[#00e5ff]" />
            <div>
              <h3 className="font-bold">Security Note</h3>
              <p className="text-xs text-zinc-500">We encrypt your secrets and only use them when you trigger a generation job.</p>
            </div>
          </div>
          <Link href="/settings" className="w-full btn-primary py-3 rounded-xl flex items-center justify-center gap-2">
            <Key className="w-4 h-4" />
            Enter My Keys Now
          </Link>
        </div>
      </div>
    </div>
  )
}
