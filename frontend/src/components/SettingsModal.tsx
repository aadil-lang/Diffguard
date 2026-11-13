'use client';

import React, { useState, useEffect } from 'react';
import { X, Key, Cpu, Sparkles, Check, ShieldCheck } from 'lucide-react';

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
    localStorage.setItem('diffguard_api_key', tempKey);
    localStorage.setItem('diffguard_model', tempModel);
    localStorage.setItem('diffguard_stream', String(tempStream));
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1000);
  };

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
            <label className="block text-xs font-medium text-gray-300 mb-1.5 flex items-center justify-between">
              <span className="flex items-center space-x-1.5">
                <Key className="w-3.5 h-3.5 text-gray-400" />
                <span>Custom Gemini API Key</span>
              </span>
              <span className="text-[10px] text-gray-500">Optional</span>
            </label>
            <input
              type="password"
              value={tempKey}
              onChange={(e) => setTempKey(e.target.value)}
              placeholder="AIzaSy... (Leave empty to use server default or heuristic fallback)"
              className="w-full text-xs bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 font-mono"
            />
            <p className="text-[11px] text-gray-500 mt-1">
              Keys are kept exclusively in local memory/localStorage and sent only to your own backend.
            </p>
          </div>

          {/* Model Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Model Engine</label>
            <select
              value={tempModel}
              onChange={(e) => setTempModel(e.target.value)}
              className="w-full text-xs bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-gray-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="gemini-2.5-flash">Gemini 2.5 Flash (Recommended: Fast & Accurate)</option>
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
