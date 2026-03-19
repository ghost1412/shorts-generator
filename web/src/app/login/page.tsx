'use client'

import React, { useState, use } from 'react'
import Link from 'next/link'
import { Sparkles, Mail, Lock, ArrowRight, Github, Chrome } from 'lucide-react'
import { login, signInWithOAuth } from './actions'

export default function LoginPage({ 
  searchParams 
}: { 
  searchParams: Promise<{ error?: string }> 
}) {
  const resolvedParams = use(searchParams)
  const [loading, setLoading] = useState(false)

  const handleOAuthSignIn = async (provider: 'google' | 'github') => {
    setLoading(true)
    await signInWithOAuth(provider)
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] flex flex-col justify-center items-center p-6 bg-gradient-to-br from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      {/* Background Orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-[120px] -z-10" />

      <div className="w-full max-w-md space-y-8">
        {/* Logo Section */}
        <div className="text-center">
          <Link href="/" className="inline-flex items-center space-x-3 group">
            <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-br from-[#9d4edd] to-[#00e5ff] rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="text-white w-6 h-6 md:w-7 md:h-7" />
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight premium-gradient">ShortsFlow</h1>
          </Link>
          <h2 className="mt-6 text-xl md:text-2xl font-bold tracking-tight text-white">Welcome Back</h2>
          <p className="mt-2 text-xs md:text-sm text-zinc-400 px-4">
            Log in to manage your automated video empire.
          </p>
        </div>

        {/* Auth Card */}
        <div className="glass-card p-6 md:p-8 space-y-6">
          <form className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-zinc-400 ml-1">Email Address</label>
                <div className="relative group">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 group-focus-within:text-[#00e5ff] transition-colors" />
                  <input 
                    name="email"
                    type="email" 
                    required
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
                    name="password"
                    type="password" 
                    required
                    placeholder="••••••••"
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:border-[#9d4edd]/50 focus:ring-1 focus:ring-[#9d4edd]/50 transition-all placeholder:text-zinc-600"
                  />
                </div>
              </div>
            </div>

            {resolvedParams?.error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs p-3 rounded-lg text-center font-medium">
                {resolvedParams.error}
              </div>
            )}

            <button 
              formAction={async (formData) => {
                setLoading(true)
                await login(formData)
                setLoading(false)
              }}
              className="w-full btn-primary py-4 text-lg flex items-center justify-center gap-2 group disabled:opacity-50"
              disabled={loading}
            >
              {loading ? 'Authenticating...' : 'Launch Dashboard'}
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10"></div>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#0a0a0c] px-2 text-zinc-500 font-medium">Or continue with</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <button 
              onClick={() => handleOAuthSignIn('google')}
              disabled={loading}
              className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors disabled:opacity-50"
            >
              <Chrome className="w-5 h-5" />
              <span className="text-sm">Google</span>
            </button>
            <button 
              onClick={() => handleOAuthSignIn('github')}
              disabled={loading}
              className="flex items-center justify-center gap-2 px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors disabled:opacity-50"
            >
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
