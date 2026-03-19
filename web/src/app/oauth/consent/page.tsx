'use client';

import React, { useState } from 'react';
import { Shield, Lock, Youtube, BarChart3, CloudUpload, ArrowRight, Sparkles } from 'lucide-react';
import { getYouTubeAuthUrl } from '../../settings/actions';

export default function OAuthConsentPage() {
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAuthorizedRedirect = async () => {
    setIsRedirecting(true);
    setError(null);
    try {
      const url = await getYouTubeAuthUrl();
      window.location.href = url;
    } catch (err: any) {
      setError(err.message || 'Failed to generate authorization URL. Please ensure your Client ID is saved in Settings.');
      setIsRedirecting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-[#f0f0f5] flex flex-col justify-center items-center p-6 bg-gradient-to-br from-[#0a0a0c] via-[#0f0c29] to-[#0a0a0c] overflow-hidden">
      {/* Background Decorative Elements */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#9d4edd]/10 rounded-full blur-[120px] -z-10" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-[120px] -z-10" />

      <div className="max-w-xl w-full space-y-8 relative">
        {/* Header Section */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center space-x-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full text-xs font-medium text-[#00e5ff] mb-2">
            <Shield className="w-3 h-3" />
            <span>Secure Authorization</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight leading-tight">
            Connect Your <br />
            <span className="premium-gradient">YouTube Empire</span>
          </h1>
          <p className="text-zinc-400 text-lg leading-relaxed">
            ShortsFlow requires specialized permissions to automate your content creation and track your viral growth.
          </p>
        </div>

        {/* Benefits/Permissions Card */}
        <div className="glass-card p-8 space-y-6 border-white/10 hover:border-white/20 transition-all">
          <div className="space-y-6">
            <div className="flex gap-4">
              <div className="w-12 h-12 bg-red-500/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <CloudUpload className="text-red-400" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-lg">Automated Video Uploads</h3>
                <p className="text-sm text-zinc-500">Enable the engine to post your generated shorts directly to your channel 24/7.</p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <BarChart3 className="text-blue-400" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-lg">Real-Time Analytics Sync</h3>
                <p className="text-sm text-zinc-500">Retrieve views, retention, and engagement data to optimize your content strategy.</p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center flex-shrink-0">
                <Lock className="text-purple-400" />
              </div>
              <div className="space-y-1">
                <h3 className="font-bold text-lg">Encrypted & Secure</h3>
                <p className="text-sm text-zinc-500">Your credentials are never shared. We only use them to talk to Google on your behalf.</p>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t border-white/5">
            {error && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm text-center font-medium">
                {error}
              </div>
            )}

            <button
              onClick={handleAuthorizedRedirect}
              disabled={isRedirecting}
              className="w-full btn-primary py-4 text-lg flex items-center justify-center gap-3 transition-all disabled:opacity-50 group"
            >
              {isRedirecting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Preparing Google Auth...</span>
                </>
              ) : (
                <>
                  <Youtube className="w-6 h-6" />
                  <span>Authorize ShortsFlow</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
            <p className="text-[10px] text-zinc-600 text-center mt-4 uppercase tracking-widest font-bold">
              Redirecting to Google Secure Consent Screen
            </p>
          </div>
        </div>

        {/* Trust Footer */}
        <div className="flex justify-center items-center gap-8 opacity-30 grayscale saturate-0 pointer-events-none">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            <span className="text-xs font-bold uppercase tracking-tighter">Verified Engine</span>
          </div>
          <div className="flex items-center gap-2">
             <Shield className="w-4 h-4" />
             <span className="text-xs font-bold uppercase tracking-tighter">AES-256 Storage</span>
          </div>
        </div>
      </div>
    </div>
  );
}
