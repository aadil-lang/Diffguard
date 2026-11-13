'use client';

import React from 'react';
import { ShieldCheck, Cpu, Settings2, Github, Sparkles } from 'lucide-react';

interface NavbarProps {
  onOpenSettings: () => void;
  isCustomKeySet: boolean;
  selectedModel: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenSettings,
  isCustomKeySet,
  selectedModel,
}) => {
  return (
    <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600/20 p-2 rounded-xl border border-indigo-500/30 flex items-center justify-center shadow-lg shadow-indigo-500/10">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xl font-bold tracking-tight text-white">DiffGuard</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded-full border border-indigo-500/30">
                Agentic v1.0
              </span>
            </div>
            <p className="text-xs text-gray-400 hidden sm:block">AI-Powered Git Diff & Pull Request Review Agent</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="hidden md:flex items-center space-x-2 text-xs bg-gray-800/70 border border-gray-700/60 px-3 py-1.5 rounded-lg text-gray-300">
            <Cpu className="w-3.5 h-3.5 text-indigo-400" />
            <span>Model: <span className="font-semibold text-white">{selectedModel}</span></span>
            {isCustomKeySet ? (
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-1" title="Custom Gemini API Key active" />
            ) : (
              <span className="text-[10px] bg-gray-700 text-gray-300 px-1.5 py-0.2 rounded font-mono ml-1">Default/Fallback</span>
            )}
          </div>

          <button
            onClick={onOpenSettings}
            className="flex items-center space-x-2 text-xs font-medium text-gray-300 hover:text-white bg-gray-800/80 hover:bg-gray-750 border border-gray-750 px-3 py-2 rounded-lg transition-colors"
            title="Configure Gemini API Key & Model"
          >
            <Settings2 className="w-4 h-4 text-gray-400" />
            <span className="hidden sm:inline">Settings</span>
          </button>
        </div>
      </div>
    </header>
  );
};
