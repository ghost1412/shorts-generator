'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { Sparkles, Mail, Lock, ArrowRight, Github, Chrome } from 'lucide-react'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] flex flex-col justify-center items-center p-6 bg-gradient-to-br from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-[120px] -z-10" />

      <div className="w-full max-w-md space-y-8">
        {/* Logo Section */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center space-x-3 group">
            <div className="w-12 h-12 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="text-white w-7 h-7" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight premium-gradient">ShortsFlow</h1>
          </Link>
          <h2 className="mt-6 text-2xl font-bold tracking-tight text-white">Welcome Back</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Log in to manage your automated video empire.
          </p>
        </div>

        {/* Auth Card */}
        <div className="glass-card p-8 space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-400 ml-1">Email Address</label>
              <div className="relative group">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-[#00e5ff] transition-colors" />
                <input 
                  type="email" 
                  placeholder="name@company.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-[#00e5ff]/50 focus:ring-1 focus:ring-[#00e5ff]/50 transition-all placeholder:text-zinc-600"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center ml-1">
                <label className="text-sm font-medium text-zinc-400">Password</label>
                <Link href="#" className="text-xs text-[#00e5ff] hover:underline">Forgot password?</Link>
              </div>
              <div className="relative group">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-[#9d4edd] transition-colors" />
                <input 
                  type="password" 
                  placeholder="••••••••"
                  className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-[#9d4edd]/50 focus:ring-1 focus:ring-[#9d4edd]/50 transition-all placeholder:text-zinc-600"
                />
              </div>
            </div>
          </div>

          <button 
            className="w-full btn-primary py-4 text-lg flex items-center justify-center gap-2 group"
            onClick={() => setLoading(true)}
          >
            {loading ? 'Authenticating...' : 'Launch Dashboard'}
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10"></div>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#0a0a0c] px-2 text-zinc-500 font-medium">Or continue with</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <button className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors">
              <Chrome className="w-5 h-5" />
              <span className="text-sm">Google</span>
            </button>
            <button className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors">
              <Github className="w-5 h-5" />
              <span className="text-sm">GitHub</span>
            </button>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-400">
          New to the flow?{' '}
          <Link href="/signup" className="text-[#00e5ff] font-semibold hover:underline">Create an account</Link>
        </p>
      </div>
    </div>
  )
}
