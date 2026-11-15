'use client';

import React, { useState, useRef } from 'react';
import { Play, Sparkles, UploadCloud, FileCode2, ChevronDown, ChevronUp, Trash2, CheckCircle2, ShieldCheck, FileCheck, Sliders } from 'lucide-react';
import { SampleDiff } from '@/types';

const SAMPLE_STANDARDS_YAML = `version: 1
project:
  name: sample-repository
standards:
  code_quality:
    max_function_length:
      enabled: true
      value: 50
      severity: medium
    max_nesting_depth:
      enabled: true
      value: 4
      severity: medium
  security:
    prohibited_imports:
      enabled: true
      values:
        - pickle
        - telnetlib
      severity: high
    custom_patterns:
      enabled: true
      rules:
        - id: SEC-RAW-SQL
          name: Raw SQL Query Pattern
          pattern: 'execute.*SELECT.*%'
          severity: high
          description: Avoid raw SQL string formatting; use parameterized queries
  testing:
    require_test_changes:
      enabled: true
      severity: medium
      min_additions_threshold: 8
`;

interface DiffInputProps {
  diffContent: string;
  setDiffContent: (val: string) => void;
  prTitle: string;
  setPrTitle: (val: string) => void;
  customInstructions: string;
  setCustomInstructions: (val: string) => void;
  standardsYaml?: string;
  setStandardsYaml?: (val: string) => void;
  samples: SampleDiff[];
  isLoading: boolean;
  onStartReview: () => void;
}

export const DiffInput: React.FC<DiffInputProps> = ({
  diffContent,
  setDiffContent,
  prTitle,
  setPrTitle,
  customInstructions,
  setCustomInstructions,
  standardsYaml = '',
  setStandardsYaml,
  samples,
  isLoading,
  onStartReview,
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showStandards, setShowStandards] = useState(false);
  const [selectedSampleId, setSelectedSampleId] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSampleChange = (sampleId: string) => {
    setSelectedSampleId(sampleId);
    if (!sampleId) return;
    const found = samples.find((s) => s.id === sampleId);
    if (found) {
      setDiffContent(found.diff_content);
      setPrTitle(found.title);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      if (text) {
        setDiffContent(text);
        setPrTitle(file.name.replace(/\.(diff|patch)$/, ''));
        setSelectedSampleId('');
      }
    };
    reader.readAsText(file);
  };

  const lineCount = diffContent ? diffContent.split('\n').length : 0;
  const charCount = diffContent.length;

  return (
    <div className="bg-gray-900/90 border border-gray-800 rounded-2xl p-5 shadow-xl">
      {/* Header with Title and Sample Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <FileCode2 className="w-5 h-5 text-indigo-400" />
            Git Diff / Pull Request Patch
          </h2>
          <p className="text-xs text-gray-400">
            Paste unified diff, drop a patch file, or test with bundled sample scenarios
          </p>
        </div>

        {/* Sample Picker */}
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400 whitespace-nowrap">Load Sample:</span>
          <select
            value={selectedSampleId}
            onChange={(e) => handleSampleChange(e.target.value)}
            disabled={isLoading}
            className="text-xs bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">-- Choose Sample Diff --</option>
            {samples.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} ({s.expected_severity})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* PR Title Input */}
      <div className="mb-3">
        <input
          type="text"
          value={prTitle}
          onChange={(e) => setPrTitle(e.target.value)}
          placeholder="PR / Change Title (e.g., Fix SQL injection in auth service or feat: batch settlements)"
          disabled={isLoading}
          className="w-full text-xs bg-gray-950/80 border border-gray-800 rounded-lg px-3 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
        />
      </div>

      {/* Diff Textarea */}
      <div className="relative border border-gray-800 rounded-xl overflow-hidden bg-gray-950/90 focus-within:border-indigo-500/80 transition-all">
        <textarea
          value={diffContent}
          onChange={(e) => {
            setDiffContent(e.target.value);
            setSelectedSampleId('');
          }}
          placeholder="Paste unified git diff here (e.g. diff --git a/services/auth.py b/services/auth.py&#10;--- a/services/auth.py&#10;+++ b/services/auth.py&#10;@@ -10,4 +10,6 @@...)"
          rows={10}
          disabled={isLoading}
          className="w-full bg-transparent text-xs font-mono text-gray-200 p-3.5 focus:outline-none resize-y placeholder-gray-600 leading-relaxed"
          spellCheck={false}
        />

        {/* Floating statistics and actions */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900/90 border-t border-gray-800/80 text-[11px] text-gray-400">
          <div className="flex items-center space-x-3">
            <span>{lineCount.toLocaleString()} lines</span>
            <span>•</span>
            <span>{(charCount / 1024).toFixed(1)} KB</span>
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".diff,.patch,.txt"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              className="hover:text-indigo-300 transition-colors flex items-center space-x-1"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Upload .patch</span>
            </button>

            {diffContent && (
              <>
                <span>•</span>
                <button
                  type="button"
                  onClick={() => {
                    setDiffContent('');
                    setSelectedSampleId('');
                  }}
                  disabled={isLoading}
                  className="hover:text-red-400 transition-colors flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Clear</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Engineering Standards Policy (.diffguard.yaml) Accordion */}
      <div className="mt-3 border border-gray-800/80 rounded-xl bg-gray-950/40 p-3">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setShowStandards(!showStandards)}
            className="flex items-center space-x-2 text-xs font-medium text-gray-300 hover:text-white transition-colors"
          >
            {showStandards ? <ChevronUp className="w-3.5 h-3.5 text-indigo-400" /> : <ChevronDown className="w-3.5 h-3.5 text-indigo-400" />}
            <Sliders className="w-3.5 h-3.5 text-purple-400" />
            <span>Engineering Standards Policy (.diffguard.yaml)</span>
          </button>

          <div className="flex items-center space-x-2">
            {standardsYaml && standardsYaml.trim() ? (
              <span className="text-[10px] font-mono text-purple-300 bg-purple-950/60 border border-purple-800/60 px-2 py-0.5 rounded-full flex items-center space-x-1">
                <CheckCircle2 className="w-2.5 h-2.5 text-purple-400" />
                <span>Custom Policy ({standardsYaml.split('\n').length} lines)</span>
              </span>
            ) : (
              <span className="text-[10px] text-gray-500 font-mono">
                Default Policies Active
              </span>
            )}
          </div>
        </div>

        {showStandards && (
          <div className="mt-3 space-y-2">
            <p className="text-[11px] text-gray-400 leading-relaxed">
              Define deterministic repository policies for function length, nesting depth, prohibited imports, custom regex patterns, and test requirements.
            </p>
            <div className="relative">
              <textarea
                value={standardsYaml}
                onChange={(e) => setStandardsYaml?.(e.target.value)}
                placeholder="Paste .diffguard.yaml content or load sample..."
                rows={8}
                disabled={isLoading}
                className="w-full text-xs font-mono bg-gray-950 border border-gray-800 rounded-lg p-3 text-purple-200 placeholder-gray-600 focus:outline-none focus:border-purple-500 leading-relaxed"
                spellCheck={false}
              />
            </div>
            <div className="flex items-center justify-between pt-1 text-xs">
              <span className="text-[10px] text-gray-500">
                Safe YAML parser (strict Pydantic schema validation, 64KB max)
              </span>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => setStandardsYaml?.(SAMPLE_STANDARDS_YAML)}
                  disabled={isLoading}
                  className="text-xs text-purple-300 hover:text-purple-200 bg-purple-950/40 border border-purple-800/50 px-2.5 py-1 rounded-md transition-colors"
                >
                  Load Sample Policy
                </button>
                {standardsYaml && (
                  <button
                    type="button"
                    onClick={() => setStandardsYaml?.('')}
                    disabled={isLoading}
                    className="text-xs text-gray-400 hover:text-red-400 px-2 py-1 transition-colors"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Advanced Guideline Accordion */}
      <div className="mt-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center space-x-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
        >
          {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          <span>Custom Review Guidelines / Team Rules (Optional)</span>
        </button>

        {showAdvanced && (
          <div className="mt-2">
            <textarea
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. Enforce strict GDPR compliance, check for microservice timeout propagation, ensure all database queries have indexes..."
              rows={2}
              disabled={isLoading}
              className="w-full text-xs bg-gray-950/80 border border-gray-800 rounded-lg p-2.5 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        )}
      </div>

      {/* Review Trigger Button */}
      <div className="mt-4 flex items-center justify-end space-x-3">
        <button
          onClick={onStartReview}
          disabled={isLoading || !diffContent.trim()}
          className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl font-medium text-xs sm:text-sm text-white shadow-lg transition-all ${
            isLoading || !diffContent.trim()
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed shadow-none'
              : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/25 active:scale-95'
          }`}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
              <span>Analyzing Diff...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 text-indigo-200" />
              <span>Start AI Code Review</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

