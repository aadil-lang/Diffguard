'use client';

import React, { useState, useEffect } from 'react';
import { Navbar } from '@/components/Navbar';
import { DiffInput } from '@/components/DiffInput';
import { ProgressStages } from '@/components/ProgressStages';
import { SummaryCards } from '@/components/SummaryCards';
import { FindingsList } from '@/components/FindingsList';
import { DiffViewer } from '@/components/DiffViewer';
import { SettingsModal } from '@/components/SettingsModal';
import { ReviewResponse, ProcessingStage, SampleDiff, StageStatus } from '@/types';
import { AlertCircle, Code, ShieldCheck, Sparkles, Layers } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 
  (typeof window !== 'undefined' && (window.location.hostname.includes('vercel.app') || window.location.hostname.includes('netlify.app'))
    ? 'https://diffguard.onrender.com'
    : 'http://127.0.0.1:8000');

export default function Home() {
  const [diffContent, setDiffContent] = useState<string>('');
  const [prTitle, setPrTitle] = useState<string>('');
  const [customInstructions, setCustomInstructions] = useState<string>('');
  const [standardsYaml, setStandardsYaml] = useState<string>('');
  const [samples, setSamples] = useState<SampleDiff[]>([]);
  const [stages, setStages] = useState<ProcessingStage[]>([]);
  const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'findings' | 'diff'>('findings');
  const [highlightFile, setHighlightFile] = useState<string | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [highlightSide, setHighlightSide] = useState<string | null>(null);

  // Settings state (apiKey is strictly kept in-memory for session security)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('gemini-3.5-flash-lite');
  const [useStreaming, setUseStreaming] = useState(true);

  // Load samples and UI preferences on mount
  useEffect(() => {
    // Purge any legacy API key from localStorage
    localStorage.removeItem('diffguard_api_key');

    const savedModel = localStorage.getItem('diffguard_model') || 'gemini-3.5-flash-lite';
    const savedStream = localStorage.getItem('diffguard_stream') !== 'false';
    setSelectedModel(savedModel);
    setUseStreaming(savedStream);

    // Fetch sample diffs from backend
    fetch(`${API_BASE_URL}/api/samples`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load samples');
        return res.json();
      })
      .then((data: SampleDiff[]) => {
        setSamples(data);
        // Pre-fill with the first sample scenario
        if (data.length > 0 && !diffContent) {
          setDiffContent(data[0].diff_content);
          setPrTitle(data[0].title);
        }
      })
      .catch((err) => {
        console.warn('Backend samples fetch notice:', err);
      });
  }, []);

  const handleNavigateToFile = (file: string, line: number, lineSide?: string) => {
    setHighlightFile(file);
    setHighlightLine(line);
    setHighlightSide(lineSide || 'new');
    setActiveTab('diff');
  };

  const handleStartReview = async () => {
    if (!diffContent.trim()) return;

    setIsLoading(true);
    setErrorMessage(null);
    setReviewResult(null);

    // Initial stages template
    const initialStages: ProcessingStage[] = [
      { stage_id: 'STAGE_RECEIVED', name: 'Input Validation & Ingestion', status: 'IN_PROGRESS' },
      { stage_id: 'STAGE_PARSING', name: 'Unified Diff Decomposition', status: 'PENDING' },
      { stage_id: 'STAGE_TOOL_EXECUTION', name: 'Static Tool Analysis & Heuristics', status: 'PENDING' },
      { stage_id: 'STAGE_AGENT_REASONING', name: 'AI Agent Synthesis & Reasoning', status: 'PENDING' },
      { stage_id: 'STAGE_STRUCTURED_VALIDATION', name: 'Findings Validation & Formatting', status: 'PENDING' },
    ];
    setStages(initialStages);

    const payload = {
      diff_content: diffContent,
      title: prTitle || undefined,
      custom_instructions: customInstructions || undefined,
      standards_yaml: standardsYaml.trim() ? standardsYaml : undefined,
      api_key: apiKey || undefined,
      model_name: selectedModel || undefined,
    };

    if (useStreaming) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/review/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body stream is not readable.');

        const decoder = new TextDecoder();
        let buffer = '';

        const processBlock = (block: string) => {
          if (!block.trim()) return;
          const eventMatch = block.match(/^event:\s*(\w+)/m);
          const eventType = eventMatch ? eventMatch[1] : 'message';
          const dataIdx = block.indexOf('data:');
          if (dataIdx === -1) return;
          const rawData = block.slice(dataIdx + 5).trim();

          try {
            const data = JSON.parse(rawData);

            if (eventType === 'stage_update') {
              const stage = data as ProcessingStage;
              setStages((prev) => {
                const idx = prev.findIndex((s) => s.stage_id === stage.stage_id);
                if (idx >= 0) {
                  const next = [...prev];
                  next[idx] = stage;
                  return next;
                }
                return [...prev, stage];
              });
            } else if (eventType === 'completed') {
              const result = data as ReviewResponse;
              setReviewResult(result);
              setStages(result.stages_executed || []);
              setIsLoading(false);
            } else if (eventType === 'error') {
              setErrorMessage(data.message || 'Error occurred during review processing.');
              setIsLoading(false);
            }
          } catch (jsonErr) {
            console.error('Failed to parse SSE event data:', jsonErr, rawData);
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            if (buffer.trim()) {
              processBlock(buffer.trim());
            }
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split(/\r?\n\r?\n/);
          buffer = lines.pop() || '';

          for (const block of lines) {
            processBlock(block);
          }
        }
      } catch (err: any) {
        console.error('Streaming review error:', err);
        setErrorMessage(err.message || 'Network or connection error. Falling back to synchronous endpoint.');
        setIsLoading(false);
      }
    } else {
      // Synchronous review fallback
      try {
        const res = await fetch(`${API_BASE_URL}/api/review`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Server returned ${res.status}`);
        }

        const data: ReviewResponse = await res.json();
        setReviewResult(data);
        setStages(data.stages_executed || []);
      } catch (err: any) {
        setErrorMessage(err.message || 'Failed to complete code review.');
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar
        onOpenSettings={() => setIsSettingsOpen(true)}
        isCustomKeySet={!!apiKey}
        selectedModel={selectedModel}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Error Banner */}
        {errorMessage && (
          <div className="bg-red-950/40 border border-red-500/40 rounded-xl p-4 flex items-start space-x-3 text-red-300 text-xs">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold block text-red-200">Review Execution Notice</span>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        {/* Diff Input and Sample Picker */}
        <DiffInput
          diffContent={diffContent}
          setDiffContent={setDiffContent}
          prTitle={prTitle}
          setPrTitle={setPrTitle}
          customInstructions={customInstructions}
          setCustomInstructions={setCustomInstructions}
          standardsYaml={standardsYaml}
          setStandardsYaml={setStandardsYaml}
          samples={samples}
          isLoading={isLoading}
          onStartReview={handleStartReview}
        />

        {/* Live Processing Pipeline Stages */}
        <ProgressStages stages={stages} isLoading={isLoading} />

        {/* Review Results Section */}
        {reviewResult && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Metric Summary Cards */}
            <SummaryCards
              summary={reviewResult.summary}
              parsedFilesCount={reviewResult.parsed_files_count}
              totalAdditions={reviewResult.total_additions}
              totalDeletions={reviewResult.total_deletions}
              engineUsed={reviewResult.engine_used}
            />

            {/* Tab Switcher: Findings vs Unified Diff */}
            <div className="border-b border-gray-800 flex items-center justify-between">
              <div className="flex space-x-4">
                <button
                  onClick={() => setActiveTab('findings')}
                  className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-colors ${
                    activeTab === 'findings'
                      ? 'border-indigo-500 text-white'
                      : 'border-transparent text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <Layers className="w-4 h-4 text-indigo-400" />
                  <span>Structured Findings ({reviewResult.findings.length})</span>
                </button>

                <button
                  onClick={() => setActiveTab('diff')}
                  className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-colors ${
                    activeTab === 'diff'
                      ? 'border-indigo-500 text-white'
                      : 'border-transparent text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <Code className="w-4 h-4 text-indigo-400" />
                  <span>Unified Diff View</span>
                </button>
              </div>
            </div>

            {/* Tab Content */}
            {activeTab === 'findings' ? (
              <FindingsList
                findings={reviewResult.findings}
                onNavigateToFile={handleNavigateToFile}
              />
            ) : (
              <DiffViewer
                diffText={diffContent}
                findings={reviewResult.findings}
                highlightFile={highlightFile}
                highlightLine={highlightLine}
                highlightSide={highlightSide}
              />
            )}
          </div>
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        apiKey={apiKey}
        setApiKey={setApiKey}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        useStreaming={useStreaming}
        setUseStreaming={setUseStreaming}
      />

      {/* Footer */}
      <footer className="border-t border-gray-850 bg-gray-950 py-6 text-center text-xs text-gray-500">
        <p>DiffGuard AI Code Review Agent — Evaluated for FLEXGCC Practical AI Engineering Standard</p>
      </footer>
    </div>
  );
}

