'use client';

import React, { useState } from 'react';
import {
  ShieldAlert,
  Bug,
  TestTube2,
  Cpu,
  Palette,
  CheckCircle2,
  HelpCircle,
  Lightbulb,
  Copy,
  Check,
  FileCode,
  ArrowRight,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Finding, SeverityLevel, FindingCategory, FindingConfidence } from '@/types';

interface FindingCardProps {
  finding: Finding;
  onNavigateToFile?: (file: string, line: number) => void;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding, onNavigateToFile }) => {
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  const getSeverityBadge = (severity: SeverityLevel) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      case 'HIGH':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'MEDIUM':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
      case 'LOW':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'INFO':
        return 'bg-gray-500/20 text-gray-300 border-gray-500/30';
    }
  };

  const getCategoryIcon = (category: FindingCategory) => {
    switch (category) {
      case 'SECURITY_AND_RELIABILITY':
        return <ShieldAlert className="w-3.5 h-3.5 text-red-400" />;
      case 'BUG_OR_LOGIC_ERROR':
        return <Bug className="w-3.5 h-3.5 text-amber-400" />;
      case 'MISSING_TEST_COVERAGE':
        return <TestTube2 className="w-3.5 h-3.5 text-indigo-400" />;
      case 'CODE_QUALITY_AND_MAINTAINABILITY':
        return <Cpu className="w-3.5 h-3.5 text-blue-400" />;
      case 'STYLE_AND_CONSISTENCY':
        return <Palette className="w-3.5 h-3.5 text-purple-400" />;
    }
  };

  const getCategoryLabel = (category: FindingCategory) => {
    switch (category) {
      case 'SECURITY_AND_RELIABILITY':
        return 'Security & Reliability';
      case 'BUG_OR_LOGIC_ERROR':
        return 'Bug & Logic Error';
      case 'MISSING_TEST_COVERAGE':
        return 'Missing Test Coverage';
      case 'CODE_QUALITY_AND_MAINTAINABILITY':
        return 'Quality & Maintainability';
      case 'STYLE_AND_CONSISTENCY':
        return 'Style & Consistency';
    }
  };

  const getConfidenceBadge = (conf: FindingConfidence) => {
    switch (conf) {
      case 'CONFIRMED_ISSUE':
        return {
          icon: <CheckCircle2 className="w-3 h-3 text-red-400" />,
          label: 'Confirmed Issue',
          color: 'text-red-400 bg-red-950/40 border-red-800/40',
        };
      case 'POTENTIAL_ISSUE':
        return {
          icon: <HelpCircle className="w-3 h-3 text-amber-400" />,
          label: 'Potential Issue',
          color: 'text-amber-400 bg-amber-950/40 border-amber-800/40',
        };
      case 'IMPROVEMENT_SUGGESTION':
        return {
          icon: <Lightbulb className="w-3 h-3 text-indigo-400" />,
          label: 'Improvement Suggestion',
          color: 'text-indigo-400 bg-indigo-950/40 border-indigo-800/40',
        };
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const confBadge = getConfidenceBadge(finding.confidence);

  return (
    <div className="bg-gray-900/90 border border-gray-800 rounded-xl overflow-hidden shadow-lg transition-all hover:border-gray-700">
      {/* Finding Header */}
      <div className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gray-850/60 border-b border-gray-800/80">
        <div className="flex items-start sm:items-center space-x-2.5 flex-wrap gap-y-1.5">
          <span className="font-mono text-xs text-gray-400 font-semibold">{finding.id}</span>

          <span
            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${getSeverityBadge(
              finding.severity
            )}`}
          >
            {finding.severity}
          </span>

          <span className="flex items-center space-x-1 text-[11px] font-medium text-gray-300 bg-gray-800/80 border border-gray-700/60 px-2 py-0.5 rounded-md">
            {getCategoryIcon(finding.category)}
            <span>{getCategoryLabel(finding.category)}</span>
          </span>

          <span
            className={`flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-md border ${confBadge.color}`}
          >
            {confBadge.icon}
            <span>{confBadge.label}</span>
          </span>
        </div>

        {/* File and Line Anchor */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onNavigateToFile?.(finding.location.file_path, finding.location.start_line)}
            className="flex items-center space-x-1 text-xs font-mono text-indigo-400 hover:text-indigo-300 bg-indigo-950/30 border border-indigo-800/40 px-2.5 py-1 rounded-md transition-colors"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>
              {finding.location.file_path}:{finding.location.start_line}
            </span>
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-gray-200 p-1"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main Body */}
      {isExpanded && (
        <div className="p-4 space-y-3.5">
          {/* Finding Title */}
          <h3 className="text-sm font-semibold text-white leading-snug">{finding.title}</h3>

          {/* Code Context if present */}
          {finding.location.code_context && (
            <div className="bg-gray-950/90 border border-gray-800 rounded-lg p-2.5 font-mono text-xs text-amber-200/90 overflow-x-auto">
              <code>{finding.location.code_context}</code>
            </div>
          )}

          {/* Why Identified (Root Cause) */}
          <div>
            <h4 className="text-[11px] uppercase tracking-wider font-semibold text-gray-400 mb-1">
              Why this was identified
            </h4>
            <p className="text-xs text-gray-300 leading-relaxed bg-gray-950/40 p-2.5 rounded-lg border border-gray-800/50">
              {finding.why_identified}
            </p>
          </div>

          {/* Impact */}
          <div>
            <h4 className="text-[11px] uppercase tracking-wider font-semibold text-gray-400 mb-1">
              Risk & Operational Impact
            </h4>
            <p className="text-xs text-gray-400 leading-relaxed bg-gray-950/40 p-2.5 rounded-lg border border-gray-800/50">
              {finding.impact}
            </p>
          </div>

          {/* Suggested Fix */}
          {finding.suggested_fix && (
            <div className="border border-indigo-900/40 bg-indigo-950/15 rounded-xl p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-[11px] uppercase tracking-wider font-semibold text-indigo-300 flex items-center space-x-1.5">
                  <Lightbulb className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Actionable Suggested Correction</span>
                </h4>

                {finding.suggested_fix.replacement_code && (
                  <button
                    onClick={() => copyToClipboard(finding.suggested_fix!.replacement_code!)}
                    className="flex items-center space-x-1 text-[11px] text-indigo-300 hover:text-white bg-indigo-900/40 hover:bg-indigo-900/70 border border-indigo-700/50 px-2 py-0.5 rounded transition-colors"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy Fix'}</span>
                  </button>
                )}
              </div>

              <p className="text-xs text-gray-300 leading-relaxed">
                {finding.suggested_fix.description}
              </p>

              {finding.suggested_fix.replacement_code && (
                <pre className="bg-gray-950/90 border border-gray-800 rounded-lg p-2.5 font-mono text-xs text-emerald-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                  <code>{finding.suggested_fix.replacement_code}</code>
                </pre>
              )}
            </div>
          )}

          {/* Tool Evidence Tags */}
          {finding.tool_evidence && finding.tool_evidence.length > 0 && (
            <div className="pt-2 border-t border-gray-800/60 flex items-center flex-wrap gap-1.5">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider mr-1">Evidence:</span>
              {finding.tool_evidence.map((evidence, idx) => (
                <span
                  key={idx}
                  className="text-[10px] font-mono text-gray-400 bg-gray-800/60 border border-gray-700/50 px-2 py-0.5 rounded-full"
                >
                  {evidence}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
