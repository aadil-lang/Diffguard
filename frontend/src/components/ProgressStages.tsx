'use client';

import React from 'react';
import { CheckCircle2, Clock, Loader2, AlertCircle, Sparkles } from 'lucide-react';
import { ProcessingStage, StageStatus } from '@/types';

interface ProgressStagesProps {
  stages: ProcessingStage[];
  isLoading: boolean;
}

export const ProgressStages: React.FC<ProgressStagesProps> = ({ stages, isLoading }) => {
  if (!stages || stages.length === 0) return null;

  const getStatusIcon = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'IN_PROGRESS':
        return <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />;
      case 'FAILED':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  const getStatusBorder = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED':
        return 'border-emerald-500/30 bg-emerald-950/10 text-gray-200';
      case 'IN_PROGRESS':
        return 'border-indigo-500/50 bg-indigo-950/20 text-white shadow-lg shadow-indigo-500/5';
      case 'FAILED':
        return 'border-red-500/30 bg-red-950/10 text-red-300';
      default:
        return 'border-gray-800 bg-gray-900/40 text-gray-500';
    }
  };

  return (
    <div className="bg-gray-900/90 border border-gray-800 rounded-2xl p-5 mb-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>Agent Execution Pipeline</span>
        </h3>
        {isLoading && (
          <span className="text-[11px] font-medium text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20 animate-pulse">
            Processing Stages Active
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {stages.map((stage, idx) => (
          <div
            key={stage.stage_id || idx}
            className={`border rounded-xl p-3 flex flex-col justify-between transition-all ${getStatusBorder(
              stage.status
            )}`}
          >
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono text-gray-400">Step 0{idx + 1}</span>
                {getStatusIcon(stage.status)}
              </div>
              <h4 className="text-xs font-semibold leading-snug line-clamp-1">{stage.name}</h4>
              {stage.details && (
                <p className="text-[11px] text-gray-400 mt-1 leading-normal line-clamp-2" title={stage.details}>
                  {stage.details}
                </p>
              )}
            </div>

            {stage.duration_ms !== undefined && stage.duration_ms !== null && (
              <div className="mt-2 text-[10px] font-mono text-gray-500 text-right">
                {stage.duration_ms} ms
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
