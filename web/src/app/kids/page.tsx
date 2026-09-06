"use client";

import React, { useState, useEffect } from 'react';
import { Sparkles, BookOpen, Volume2, ArrowLeft, ArrowRight, RotateCcw, Paintbrush, Wand2, Compass } from 'lucide-react';

interface Page {
  text: string;
  image_prompt: string;
  imageUrl?: string;
}

interface Story {
  title: string;
  pages: Page[];
}

export default function KidsStorybookPage() {
  // App States: 'setup' | 'loading' | 'storybook'
  const [step, setStep] = useState<'setup' | 'loading' | 'storybook'>('setup');
  
  // Selection States
  const [hero, setHero] = useState<string>('🧸 Luna the Sleepy Bear');
  const [heroName, setHeroName] = useState<string>('');
  const [companion, setCompanion] = useState<string>('🧚 Twinkle the Pixie');
  const [magicItem, setMagicItem] = useState<string>('✨ Magic Wand');
  const [setting, setSetting] = useState<string>('🌌 Starry Night Forest');

  // Generated Story States
  const [story, setStory] = useState<Story | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [loadingStatus, setLoadingStatus] = useState<string>('Magical portals opening... 🌌');
  const [imageLoading, setImageLoading] = useState<boolean>(false);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);

  // Setup Options
  const heroes = [
    { name: '🧸 Luna the Sleepy Bear', desc: 'Loves stars and cozy blankets' },
    { name: '🐉 Barnaby the Friendly Dragon', desc: 'Breathes warm bubbles instead of fire' },
    { name: '🐿️ Pip the Brave Squirrel', desc: 'Always searching for the magical acorn' },
    { name: '🦄 Sparkle the Magic Unicorn', desc: 'Can make rainbows appear out of thin air' },
    { name: '🐟 Finley the Curious Fish', desc: 'Wants to discover the sky' }
  ];

  const companions = [
    { name: '🧚 Twinkle the Pixie', desc: 'Leaves a trail of fairy dust' },
    { name: ' Owls Oliver the Wise Owl', desc: 'Knows the answer to every question' },
    { name: '🦫 Barnaby the Busy Beaver', desc: 'Can build anything out of branches' },
    { name: '🦋 Flutter the Rainbow Butterfly', desc: 'Changes color when she lands on a flower' }
  ];

  const magicItems = [
    { name: '✨ Magic Wand', desc: 'Makes items float and spin' },
    { name: '🔑 Golden Key', desc: 'Opens secret doors in trees' },
    { name: '🗺️ Secret Map', desc: 'Shows where hidden toys are buried' },
    { name: '🎒 Bag of Shiny Seeds', desc: 'Grows glowing flowers in seconds' }
  ];

  const settings = [
    { name: '🌌 Starry Night Forest', desc: 'Where the trees whisper secrets' },
    { name: '🍭 Candy Land Adventure', desc: 'Gumdrop hills and marshmallow rivers' },
    { name: '🏰 Underwater Castle', desc: 'Full of playful sea shells' },
    { name: '☁️ Sky Island Palace', desc: 'Floating cities in the fluffy clouds' }
  ];

  // Rotate loading messages
  useEffect(() => {
    if (step !== 'loading') return;
    const messages = [
      'Waking up the characters... 🧸',
      'Painting the magical sky... 🎨',
      'Whispering spells to the stars... ✨',
      'Binding the storybook pages... 📖',
      'Sprinkling fairy dust... 🧚'
    ];
    let idx = 0;
    const interval = setInterval(() => {
      setLoadingStatus(messages[idx]);
      idx = (idx + 1) % messages.length;
    }, 3000);
    return () => clearInterval(interval);
  }, [step]);

  // Handle Speech synthesis
  const handleSpeak = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel(); // Stop any ongoing speech
      
      if (isSpeaking) {
        setIsSpeaking(false);
        return;
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9; // Slightly slower for children
      utterance.pitch = 1.1; // Friendly higher pitch
      
      utterance.onend = () => {
        setIsSpeaking(false);
      };
      
      setIsSpeaking(true);
      window.speechSynthesis.speak(utterance);
    } else {
      alert("Oops! Your browser doesn't support reading aloud. Try Google Chrome!");
    }
  };

  // Stop speech when changing pages
  useEffect(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }, [currentPage]);

  // Generate Story
  const generateStorybook = async () => {
    setStep('loading');
    try {
      const response = await fetch('/api/kids-story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hero,
          heroName: heroName || 'Buddy',
          companion,
          quest: `Finding a secret path in the ${setting} using the ${magicItem}`,
          setting
        })
      });

      const resData = await response.json();
      if (!resData.success || !resData.story) {
        throw new Error(resData.error || 'Failed to generate story');
      }

      const generatedStory: Story = resData.story;
      
      // Start generating the image for the first page immediately
      setStory(generatedStory);
      setCurrentPage(0);
      setStep('storybook');
      fetchPageImage(generatedStory, 0);

    } catch (e) {
      console.error(e);
      alert('Oh no! The magic portal closed. Let\'s try again!');
      setStep('setup');
    }
  };

  // Fetch page image in the background
  const fetchPageImage = async (currentStory: Story, pageIdx: number) => {
    if (currentStory.pages[pageIdx].imageUrl) return; // already loaded
    
    setImageLoading(true);
    try {
      const imgRes = await fetch('/api/kids-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: currentStory.pages[pageIdx].image_prompt })
      });
      const imgData = await imgRes.json();
      
      if (imgData.success && imgData.imageUrl) {
        const updatedStory = { ...currentStory };
        updatedStory.pages[pageIdx].imageUrl = imgData.imageUrl;
        setStory(updatedStory);
      }
    } catch (e) {
      console.error('Failed to load scene image:', e);
    } finally {
      setImageLoading(false);
    }
  };

  // Turn page
  const handleNextPage = () => {
    if (!story) return;
    const nextIdx = currentPage + 1;
    if (nextIdx < story.pages.length) {
      setCurrentPage(nextIdx);
      fetchPageImage(story, nextIdx);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 0) {
      setCurrentPage(currentPage - 1);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-tr from-amber-100 via-pink-100 to-indigo-100 text-slate-800 font-sans p-6 md:p-12 flex flex-col items-center justify-center">
      
      {/* --- STEP 1: SETUP/CHARACTER CREATOR --- */}
      {step === 'setup' && (
        <div className="max-w-4xl w-full bg-white/70 backdrop-blur-xl border border-white/60 rounded-3xl shadow-2xl p-8 md:p-12 animate-fade-in">
          
          <div className="text-center mb-10">
            <h1 className="text-4xl md:text-5xl font-extrabold text-indigo-700 flex items-center justify-center gap-3 drop-shadow-sm">
              <Sparkles className="text-amber-500 animate-bounce" size={40} />
              My Magical Storybook
            </h1>
            <p className="text-lg text-indigo-900/70 mt-2 font-medium">Create your hero and go on a magical journey!</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
            
            {/* Hero Selection */}
            <div className="space-y-4">
              <label className="text-xl font-bold text-indigo-900 flex items-center gap-2">
                <Paintbrush className="text-indigo-500" size={24} />
                1. Choose Your Hero
              </label>
              <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2">
                {heroes.map((h) => (
                  <button
                    key={h.name}
                    onClick={() => setHero(h.name)}
                    className={`text-left p-3 rounded-2xl border-2 transition-all duration-300 ${
                      hero === h.name 
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-950 scale-[1.02] shadow-md' 
                        : 'border-slate-200/80 bg-white/50 hover:bg-white text-slate-700'
                    }`}
                  >
                    <div className="font-bold text-base">{h.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{h.desc}</div>
                  </button>
                ))}
              </div>

              {/* Name customisation */}
              <div className="mt-4">
                <label className="block text-sm font-bold text-indigo-900 mb-1">Give your hero a fun name:</label>
                <input
                  type="text"
                  placeholder="e.g. Barnaby"
                  value={heroName}
                  onChange={(e) => setHeroName(e.target.value)}
                  className="w-full p-3 rounded-2xl border-2 border-slate-200/80 bg-white/50 focus:border-indigo-500 focus:bg-white focus:outline-none transition-all placeholder:text-slate-400"
                />
              </div>
            </div>

            {/* Companion Selection */}
            <div className="space-y-4">
              <label className="text-xl font-bold text-indigo-900 flex items-center gap-2">
                <Wand2 className="text-indigo-500" size={24} />
                2. Pick a Friendly Companion
              </label>
              <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2">
                {companions.map((c) => (
                  <button
                    key={c.name}
                    onClick={() => setCompanion(c.name)}
                    className={`text-left p-3 rounded-2xl border-2 transition-all duration-300 ${
                      companion === c.name 
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-950 scale-[1.02] shadow-md' 
                        : 'border-slate-200/80 bg-white/50 hover:bg-white text-slate-700'
                    }`}
                  >
                    <div className="font-bold text-base">{c.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{c.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Magic Item */}
            <div className="space-y-4">
              <label className="text-xl font-bold text-indigo-900 flex items-center gap-2">
                <Sparkles className="text-indigo-500" size={24} />
                3. Choose a Magical Item
              </label>
              <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2">
                {magicItems.map((item) => (
                  <button
                    key={item.name}
                    onClick={() => setMagicItem(item.name)}
                    className={`text-left p-3 rounded-2xl border-2 transition-all duration-300 ${
                      magicItem === item.name 
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-950 scale-[1.02] shadow-md' 
                        : 'border-slate-200/80 bg-white/50 hover:bg-white text-slate-700'
                    }`}
                  >
                    <div className="font-bold text-base">{item.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{item.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Setting */}
            <div className="space-y-4">
              <label className="text-xl font-bold text-indigo-900 flex items-center gap-2">
                <Compass className="text-indigo-500" size={24} />
                4. Select the Setting
              </label>
              <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2">
                {settings.map((s) => (
                  <button
                    key={s.name}
                    onClick={() => setSetting(s.name)}
                    className={`text-left p-3 rounded-2xl border-2 transition-all duration-300 ${
                      setting === s.name 
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-950 scale-[1.02] shadow-md' 
                        : 'border-slate-200/80 bg-white/50 hover:bg-white text-slate-700'
                    }`}
                  >
                    <div className="font-bold text-base">{s.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{s.desc}</div>
                  </button>
                ))}
              </div>
            </div>

          </div>

          <div className="flex justify-center">
            <button
              onClick={generateStorybook}
              className="py-4 px-10 rounded-full text-xl font-extrabold text-white bg-gradient-to-r from-pink-500 via-purple-600 to-indigo-600 hover:from-pink-600 hover:to-indigo-700 shadow-xl hover:shadow-indigo-500/20 active:scale-95 transition-all duration-300 flex items-center gap-3 cursor-pointer"
            >
              <BookOpen size={24} />
              🎨 Create My Storybook!
            </button>
          </div>

        </div>
      )}

      {/* --- STEP 2: ANIMATED LOADING SCREEN --- */}
      {step === 'loading' && (
        <div className="flex flex-col items-center justify-center p-12 text-center max-w-md bg-white/60 backdrop-blur-md rounded-3xl border border-white/40 shadow-xl animate-pulse">
          <div className="relative mb-8">
            <div className="w-24 h-24 rounded-full border-4 border-indigo-200 border-t-indigo-600 animate-spin"></div>
            <Sparkles className="absolute inset-0 m-auto text-amber-500 animate-bounce" size={40} />
          </div>
          <h2 className="text-2xl font-extrabold text-indigo-950 mb-3">Whispering Spells to Gemini... 🪄</h2>
          <p className="text-indigo-900/80 font-medium text-lg min-h-[2.5rem]">{loadingStatus}</p>
        </div>
      )}

      {/* --- STEP 3: INTERACTIVE STORYBOOK VIEWER --- */}
      {step === 'storybook' && story && (
        <div className="max-w-5xl w-full flex flex-col items-center gap-8 animate-fade-in">
          
          <div className="text-center">
            <h1 className="text-3xl md:text-4xl font-extrabold text-indigo-950 flex items-center justify-center gap-2 drop-shadow-sm">
              ✨ {story.title} ✨
            </h1>
          </div>

          {/* Double-Page Storybook Layout */}
          <div className="grid grid-cols-1 md:grid-cols-2 w-full bg-amber-50 border-[16px] border-amber-900/90 rounded-3xl shadow-2xl overflow-hidden min-h-[450px]">
            
            {/* Left Page: Illustration */}
            <div className="bg-amber-100/50 flex items-center justify-center border-b-[8px] md:border-b-0 md:border-r-[8px] border-amber-950/20 p-6 md:p-8 relative min-h-[300px]">
              {imageLoading ? (
                <div className="flex flex-col items-center justify-center gap-3 text-slate-500">
                  <div className="w-12 h-12 rounded-full border-4 border-indigo-200 border-t-indigo-500 animate-spin"></div>
                  <span className="font-bold text-indigo-900/60">Coloring the page... 🎨</span>
                </div>
              ) : story.pages[currentPage].imageUrl ? (
                <img
                  src={story.pages[currentPage].imageUrl}
                  alt={story.pages[currentPage].text}
                  className="rounded-2xl max-w-full max-h-[350px] shadow-lg object-contain border-4 border-white"
                />
              ) : (
                <div className="flex flex-col items-center justify-center text-slate-400 p-8 text-center gap-2">
                  <span className="text-5xl">📖</span>
                  <span className="font-medium text-slate-500">Loading scene illustration...</span>
                </div>
              )}
            </div>

            {/* Right Page: Story text & Speech */}
            <div className="flex flex-col justify-between p-8 md:p-12 relative bg-amber-50">
              
              <div className="space-y-6">
                {/* Page indicator */}
                <div className="flex justify-between items-center text-amber-900/60 font-bold uppercase tracking-wider text-sm">
                  <span>✨ Adventure Book</span>
                  <span>Page {currentPage + 1} of {story.pages.length}</span>
                </div>
                
                {/* Story text */}
                <p className="text-xl md:text-2xl font-medium leading-relaxed text-slate-800 font-serif min-h-[160px]">
                  {story.pages[currentPage].text}
                </p>
              </div>

              {/* Narrator Voice Button */}
              <div className="flex items-center justify-between mt-6 pt-6 border-t border-amber-950/10">
                <button
                  onClick={() => handleSpeak(story.pages[currentPage].text)}
                  className={`py-3 px-6 rounded-full font-bold shadow-md flex items-center gap-2 transition-all active:scale-95 cursor-pointer ${
                    isSpeaking 
                      ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse' 
                      : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                  }`}
                >
                  <Volume2 size={20} />
                  {isSpeaking ? 'Pause Voice' : 'Listen 🔊'}
                </button>
              </div>

            </div>

          </div>

          {/* Navigation Controls */}
          <div className="flex items-center gap-4">
            <button
              onClick={handlePrevPage}
              disabled={currentPage === 0}
              className="p-4 rounded-full bg-white/80 hover:bg-white text-indigo-900 border border-indigo-200/50 shadow-md disabled:opacity-40 transition-all cursor-pointer active:scale-90"
            >
              <ArrowLeft size={24} />
            </button>

            <span className="font-extrabold text-indigo-950 text-lg px-4 bg-white/60 rounded-full py-2 shadow-inner">
              {currentPage + 1} / {story.pages.length}
            </span>

            {currentPage === story.pages.length - 1 ? (
              <button
                onClick={() => setStep('setup')}
                className="py-3 px-6 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white font-extrabold shadow-md flex items-center gap-2 transition-all cursor-pointer active:scale-95"
              >
                <RotateCcw size={20} />
                Create Another Adventure!
              </button>
            ) : (
              <button
                onClick={handleNextPage}
                className="p-4 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-md transition-all cursor-pointer active:scale-90"
              >
                <ArrowRight size={24} />
              </button>
            )}
          </div>

        </div>
      )}

    </div>
  );
}
