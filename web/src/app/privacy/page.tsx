'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, ShieldCheck, Lock, Eye, FileText } from 'lucide-react';

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] p-8 bg-gradient-to-b from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c]">
      <div className="max-w-3xl mx-auto space-y-12 py-12">
        <header className="space-y-4">
          <Link href="/" className="inline-flex items-center gap-2 text-zinc-500 hover:text-white transition-colors mb-4 group">
            <ArrowLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
            Back to Home
          </Link>
          <h1 className="text-4xl font-extrabold premium-gradient flex items-center gap-3">
            <ShieldCheck className="text-[#00e5ff]" size={40} />
            Privacy Policy
          </h1>
          <p className="text-zinc-500">Last Updated: April 7, 2026</p>
        </header>

        <section className="glass-card p-8 space-y-6 border-[#00e5ff]/20">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#00e5ff]/10 rounded-lg">
              <Eye className="text-[#00e5ff]" size={20} />
            </div>
            <h2 className="text-xl font-bold uppercase tracking-widest">Data We Collect</h2>
          </div>
          <p className="text-zinc-400 text-sm leading-relaxed">
            ShortsFlow is designed to automate your content creation workflow. To provide these services, we collect:
          </p>
          <ul className="list-disc list-inside text-zinc-400 text-sm space-y-2 ml-4">
            <li>Account credentials for third-party platforms (YouTube, Pinterest, Instagram).</li>
            <li>Content generation preferences (Vibes, Categories, Personas).</li>
            <li>Usage metrics to optimize our AI generation models.</li>
          </ul>
        </section>

        <section className="glass-card p-8 space-y-6 border-[#9d4edd]/20">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#9d4edd]/10 rounded-lg">
              <Lock className="text-[#9d4edd]" size={20} />
            </div>
            <h2 className="text-xl font-bold uppercase tracking-widest">Security & Encryption</h2>
          </div>
          <p className="text-zinc-400 text-sm leading-relaxed">
            Your trust is our priority. All sensitive API credentials (YouTube Refresh Tokens, Pinterest Access Tokens) are **encrypted using AES-256-GCM** before being stored in our database. 
            We never store your raw client secrets or passwords in plain text.
          </p>
        </section>

        <section className="glass-card p-8 space-y-6 border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-zinc-800 rounded-lg">
              <FileText className="text-zinc-400" size={20} />
            </div>
            <h2 className="text-xl font-bold uppercase tracking-widest">Social Media Platforms</h2>
          </div>
          <p className="text-zinc-400 text-sm leading-relaxed">
            Our application integrates with third-party APIs. By using ShortsFlow, you also agree to be bound by the Terms of Service and Privacy Policies of these platforms:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <a href="https://policies.google.com/privacy" className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-xs font-bold text-center">YouTube / Google</a>
            <a href="https://policy.pinterest.com/en/privacy-policy" className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-xs font-bold text-center">Pinterest</a>
            <a href="https://help.instagram.com/519522125107875" className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-xs font-bold text-center">Meta / Instagram</a>
          </div>
        </section>

        <footer className="text-center text-zinc-600 text-xs py-8">
          <p>© 2026 ShortsFlow Automation Engine. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
}
