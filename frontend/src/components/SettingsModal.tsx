'use client';

import React, { useState, useEffect } from 'react';
import { X, Key, Cpu, Sparkles, Check, ShieldCheck, Trash2, ShieldAlert } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  setApiKey: (key: string) => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  useStreaming: boolean;
  setUseStreaming: (streaming: boolean) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  apiKey,
  setApiKey,
  selectedModel,
  setSelectedModel,
  useStreaming,
  setUseStreaming,
}) => {
  const [tempKey, setTempKey] = useState(apiKey);
  const [tempModel, setTempModel] = useState(selectedModel);
  const [tempStream, setTempStream] = useState(useStreaming);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setTempKey(apiKey);
    setTempModel(selectedModel);
    setTempStream(useStreaming);
  }, [apiKey, selectedModel, useStreaming, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    setApiKey(tempKey);
    setSelectedModel(tempModel);
    setUseStreaming(tempStream);
    // Persist only non-sensitive UI preferences in localStorage.
    // Sensitive API keys are strictly in-memory per Phase 1 security standard.
    localStorage.setItem('diffguard_model', tempModel);
    localStorage.setItem('diffguard_stream', String(tempStream));
    // Ensure any legacy persistent key in localStorage is purged
    localStorage.removeItem('diffguard_api_key');

    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  };

  const handleClearKey = () => {
    setTempKey('');
    setApiKey('');
    localStorage.removeItem('diffguard_api_key');
  };

  const isKeyEntered = Boolean(tempKey && tempKey.trim().length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-md p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white p-1 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2.5 mb-5">
          <div className="bg-indigo-600/20 p-2 rounded-xl border border-indigo-500/30">
            <Cpu className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Agent & Model Settings</h3>
            <p className="text-xs text-gray-400">Configure Gemini API Key and inference options</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Gemini API Key */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-gray-300 flex items-center space-x-1.5">
                <Key className="w-3.5 h-3.5 text-gray-400" />
                <span>Custom Gemini API Key</span>
              </label>

              {isKeyEntered && (
                <button
                  type="button"
                  onClick={handleClearKey}
                  className="text-[11px] text-red-400 hover:text-red-300 flex items-center space-x-1 transition-colors"
                  title="Clear key from memory"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Clear Key</span>
                </button>
              )}
            </div>

            <div className="relative">
              <input
                type="password"
                value={tempKey}
                onChange={(e) => setTempKey(e.target.value)}
                placeholder={isKeyEntered ? '••••••••••••••••••••••••' : 'AIzaSy... (Leave empty for default/fallback)'}
                className="w-full text-xs bg-gray-950 border border-gray-800 rounded-lg p-2.5 pr-20 text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 font-mono"
              />
              {isKeyEntered && (
                <span className="absolute right-2.5 top-2.5 text-[10px] bg-emerald-950/80 text-emerald-300 border border-emerald-800/50 px-1.5 py-0.5 rounded font-medium">
                  Active in Memory
                </span>
              )}
            </div>

            <div className="mt-2 flex items-start space-x-1.5 text-[11px] text-gray-400 bg-gray-950/50 p-2 rounded-lg border border-gray-800/60">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                <strong>In-Memory Security:</strong> Keys are held strictly in React application state and are never stored in localStorage, cookies, or persistent storage.
              </span>
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Model Engine</label>
            <select
              value={tempModel}
              onChange={(e) => setTempModel(e.target.value)}
              className="w-full text-xs bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-gray-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="gemini-3.8-flash">Gemini 3.8 Flash (Latest: Fast & Accurate)</option>
              <option value="gemini-3.5-flash">Gemini 3.5 Flash (Verified Responsive)</option>
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
              <option value="gemini-1.5-pro">Gemini 1.5 Pro (Deep Reasoning)</option>
            </select>
          </div>

          {/* Streaming Toggle */}
          <div className="pt-2">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <span className="text-xs font-medium text-gray-300 block">Server-Sent Events (SSE) Streaming</span>
                <span className="text-[11px] text-gray-500 block">Stream execution stages in real-time</span>
              </div>
              <input
                type="checkbox"
                checked={tempStream}
                onChange={(e) => setTempStream(e.target.checked)}
                className="w-4 h-4 text-indigo-600 rounded bg-gray-950 border-gray-700 focus:ring-indigo-500"
              />
            </label>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex items-center justify-end space-x-3">
          <button
            onClick={onClose}
            className="text-xs text-gray-400 hover:text-white px-3 py-2 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-4 py-2 rounded-lg shadow-lg shadow-indigo-600/20 transition-colors"
          >
            {saved ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Saved!</span>
              </>
            ) : (
              <span>Save Preferences</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
