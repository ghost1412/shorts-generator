'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { Sparkles, Mail, Lock, ArrowRight, User, ShieldCheck } from 'lucide-react'

export default function SignupPage() {
  const [loading, setLoading] = useState(false)

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] flex flex-col justify-center items-center p-6 bg-gradient-to-tr from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      {/* Background Orbs */}
      <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10" />

      <div className="w-full max-w-md space-y-8">
        {/* Logo Section */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center space-x-3 group">
            <div className="w-12 h-12 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="text-white w-7 h-7" />
            </div>
            <h1 className="text-3xl font-bold tracking-tight premium-gradient">ShortsFlow</h1>
          </Link>
          <h2 className="mt-6 text-2xl font-bold tracking-tight text-white">Start Your Empire</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Automate your content, scale your reach, and win.
          </p>
        </div>

        {/* Auth Card */}
        <div className="glass-card p-8 space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-400 ml-1">Full Name</label>
              <div className="relative group">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-[#9d4edd] transition-colors" />
                <input 
                  type="text" 
                  placeholder="John Doe"
                  className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-[#9d4edd]/50 focus:ring-1 focus:ring-[#9d4edd]/50 transition-all placeholder:text-zinc-600"
                />
              </div>
            </div>

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
              <label className="text-sm font-medium text-zinc-400 ml-1">Password</label>
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

          <div className="flex items-start space-x-2 ml-1">
            <input type="checkbox" className="mt-1 w-4 h-4 rounded border-white/10 bg-white/5 text-[#9d4edd] focus:ring-[#9d4edd]" />
            <span className="text-xs text-zinc-500">
              I agree to the <Link href="#" className="underline">Terms of Service</Link> and <Link href="#" className="underline">Privacy Policy</Link>.
            </span>
          </div>

          <button 
            className="w-full btn-primary py-4 text-lg flex items-center justify-center gap-2 group"
            onClick={() => setLoading(true)}
          >
            {loading ? 'Processing...' : 'Create Account'}
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>

          <div className="flex items-center justify-center gap-2 py-2 px-4 bg-emerald-500/5 border border-emerald-500/10 rounded-lg">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span className="text-[10px] text-emerald-500 font-bold uppercase tracking-widest">Secure 256-bit Encryption</span>
          </div>
        </div>

        <p className="text-center text-sm text-zinc-400">
          Already have an empire?{' '}
          <Link href="/login" className="text-[#9d4edd] font-semibold hover:underline">Log in</Link>
        </p>
      </div>
    </div>
  )
}
