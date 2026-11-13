'use client';

import React from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  Info,
  CheckCircle,
  XCircle,
  FileText,
  Plus,
  Minus,
  Sparkles,
  HelpCircle,
  Lightbulb,
} from 'lucide-react';
import { ReviewSummary, ReviewVerdict } from '@/types';

interface SummaryCardsProps {
  summary: ReviewSummary;
  parsedFilesCount: number;
  totalAdditions: number;
  totalDeletions: number;
  engineUsed: string;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({
  summary,
  parsedFilesCount,
  totalAdditions,
  totalDeletions,
  engineUsed,
}) => {
  const getVerdictDetails = (verdict: ReviewVerdict) => {
    switch (verdict) {
      case 'CRITICAL_BLOCKER':
        return {
          label: 'Critical Blocker',
          color: 'text-red-400 bg-red-950/40 border-red-500/40',
          icon: <XCircle className="w-5 h-5 text-red-400" />,
          desc: 'High-risk security vulnerabilities or fatal logic errors detected. Do not merge until resolved.',
        };
      case 'CHANGES_REQUESTED':
        return {
          label: 'Changes Requested',
          color: 'text-amber-400 bg-amber-950/40 border-amber-500/40',
          icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
          desc: 'Significant issues identified in correctness, reliability, or testing.',
        };
      case 'APPROVED_WITH_COMMENTS':
        return {
          label: 'Approved with Suggestions',
          color: 'text-blue-400 bg-blue-950/40 border-blue-500/40',
          icon: <Info className="w-5 h-5 text-blue-400" />,
          desc: 'No blockers found. Suggestions provided to enhance maintainability and code quality.',
        };
      case 'APPROVED':
        return {
          label: 'Approved',
          color: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/40',
          icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
          desc: 'Clean pull request. Passes security checks and meets quality standards.',
        };
    }
  };

  const verdict = getVerdictDetails(summary.verdict);
  const bySev = summary.by_severity || {};
  const byConf = summary.by_confidence || {};

  return (
    <div className="space-y-4 mb-6">
      {/* Top Banner: Verdict & Key Takeaways */}
      <div className={`border rounded-2xl p-5 ${verdict.color} flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl`}>
        <div className="flex items-start space-x-3.5">
          <div className="p-2.5 rounded-xl bg-black/30 border border-white/10 shrink-0 mt-0.5">
            {verdict.icon}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs uppercase font-mono tracking-wider opacity-80">Verdict</span>
              <span className="font-bold text-lg text-white">{verdict.label}</span>
            </div>
            <p className="text-xs text-gray-300 mt-1 max-w-2xl leading-relaxed">{verdict.desc}</p>
          </div>
        </div>

        <div className="text-left md:text-right text-xs text-gray-400 shrink-0">
          <div className="font-mono text-gray-300">Engine: <span className="text-white font-semibold">{engineUsed}</span></div>
          <div className="mt-1 flex items-center md:justify-end space-x-3 font-mono">
            <span>{parsedFilesCount} file(s)</span>
            <span className="text-emerald-400 flex items-center"><Plus className="w-3 h-3 mr-0.5" />{totalAdditions}</span>
            <span className="text-red-400 flex items-center"><Minus className="w-3 h-3 mr-0.5" />{totalDeletions}</span>
          </div>
        </div>
      </div>

      {/* Key Takeaways */}
      {summary.key_takeaways && summary.key_takeaways.length > 0 && (
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-4 text-xs">
          <h4 className="font-semibold text-gray-300 mb-2 flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Key Review Findings & Takeaways</span>
          </h4>
          <ul className="space-y-1 text-gray-400">
            {summary.key_takeaways.map((takeaway, idx) => (
              <li key={idx} className="flex items-start space-x-2">
                <span className="text-indigo-400 font-bold">•</span>
                <span>{takeaway}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Total Issues */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-gray-400">Total Findings</span>
          <div className="text-2xl font-bold text-white mt-1">{summary.total_findings}</div>
          <span className="text-[10px] text-gray-500 mt-0.5">Across all categories</span>
        </div>

        {/* Critical */}
        <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-red-400 flex items-center justify-between">
            <span>Critical</span>
            <span className="w-2 h-2 rounded-full bg-red-500" />
          </span>
          <div className="text-2xl font-bold text-red-300 mt-1">{bySev['CRITICAL'] || 0}</div>
          <span className="text-[10px] text-red-400/70 mt-0.5">Immediate blockers</span>
        </div>

        {/* High */}
        <div className="bg-amber-950/20 border border-amber-900/30 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-amber-400 flex items-center justify-between">
            <span>High</span>
            <span className="w-2 h-2 rounded-full bg-amber-500" />
          </span>
          <div className="text-2xl font-bold text-amber-300 mt-1">{bySev['HIGH'] || 0}</div>
          <span className="text-[10px] text-amber-400/70 mt-0.5">Reliability/logic risks</span>
        </div>

        {/* Medium */}
        <div className="bg-yellow-950/20 border border-yellow-900/30 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-yellow-400 flex items-center justify-between">
            <span>Medium</span>
            <span className="w-2 h-2 rounded-full bg-yellow-500" />
          </span>
          <div className="text-2xl font-bold text-yellow-300 mt-1">{bySev['MEDIUM'] || 0}</div>
          <span className="text-[10px] text-yellow-400/70 mt-0.5">Quality & test gaps</span>
        </div>

        {/* Low & Info */}
        <div className="bg-blue-950/20 border border-blue-900/30 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-blue-400 flex items-center justify-between">
            <span>Low & Style</span>
            <span className="w-2 h-2 rounded-full bg-blue-500" />
          </span>
          <div className="text-2xl font-bold text-blue-300 mt-1">
            {(bySev['LOW'] || 0) + (bySev['INFO'] || 0)}
          </div>
          <span className="text-[10px] text-blue-400/70 mt-0.5">Maintainability items</span>
        </div>

        {/* Confirmed vs Potential Ratio */}
        <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-3.5 flex flex-col justify-between">
          <span className="text-[11px] font-medium text-gray-400">Confidence</span>
          <div className="text-xs font-mono text-gray-300 mt-1 space-y-0.5">
            <div className="flex justify-between">
              <span className="text-red-400">Confirmed:</span>
              <span className="font-bold text-white">{byConf['CONFIRMED_ISSUE'] || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-amber-400">Potential:</span>
              <span className="font-bold text-white">{byConf['POTENTIAL_ISSUE'] || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-indigo-400">Suggestion:</span>
              <span className="font-bold text-white">{byConf['IMPROVEMENT_SUGGESTION'] || 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
