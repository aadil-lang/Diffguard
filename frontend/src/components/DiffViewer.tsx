'use client';

import React, { useMemo } from 'react';
import { FileCode, AlertCircle, Plus, Minus } from 'lucide-react';
import { Finding } from '@/types';

interface DiffViewerProps {
  diffText: string;
  findings: Finding[];
  highlightFile?: string | null;
  highlightLine?: number | null;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diffText,
  findings,
  highlightFile,
  highlightLine,
}) => {
  // Map line numbers to findings
  const findingsByFileAndLine = useMemo(() => {
    const map = new Map<string, Finding[]>();
    findings.forEach((f) => {
      const key = `${f.location.file_path}:${f.location.start_line}`;
      const existing = map.get(key) || [];
      existing.push(f);
      map.set(key, existing);
    });
    return map;
  }, [findings]);

  const parsedLines = useMemo(() => {
    if (!diffText) return [];
    const lines = diffText.replace(/\r\n/g, '\n').split('\n');
    let currentFile = '';
    let targetLineNo = 0;

    return lines.map((line, idx) => {
      let type: 'header' | 'file-header' | 'add' | 'del' | 'context' = 'context';
      let lineNum: number | null = null;

      if (line.startsWith('diff --git')) {
        type = 'file-header';
        const match = line.match(/b\/(.*)$/);
        if (match) currentFile = match[1];
      } else if (line.startsWith('+++ b/')) {
        type = 'file-header';
        currentFile = line.replace('+++ b/', '').trim();
      } else if (line.startsWith('--- a/')) {
        type = 'file-header';
      } else if (line.startsWith('@@')) {
        type = 'header';
        const match = line.match(/\+(\d+)/);
        if (match) targetLineNo = parseInt(match[1], 10) - 1;
      } else if (line.startsWith('+')) {
        type = 'add';
        targetLineNo += 1;
        lineNum = targetLineNo;
      } else if (line.startsWith('-')) {
        type = 'del';
      } else {
        type = 'context';
        targetLineNo += 1;
        lineNum = targetLineNo;
      }

      const findingKey = `${currentFile}:${lineNum}`;
      const lineFindings = lineNum ? findingsByFileAndLine.get(findingKey) : undefined;
      const isHighlighted =
        highlightFile &&
        highlightLine &&
        currentFile.includes(highlightFile) &&
        lineNum === highlightLine;

      return {
        idx,
        text: line,
        type,
        currentFile,
        lineNum,
        findings: lineFindings,
        isHighlighted,
      };
    });
  }, [diffText, findingsByFileAndLine, highlightFile, highlightLine]);

  if (!diffText) return null;

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
      <div className="bg-gray-900 px-4 py-2.5 border-b border-gray-800 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center space-x-2">
          <FileCode className="w-4 h-4 text-indigo-400" />
          <span className="font-semibold text-gray-200">Unified Diff Code View</span>
        </div>
        <span className="font-mono text-[11px] text-gray-500">{parsedLines.length} total lines</span>
      </div>

      <div className="overflow-x-auto max-h-[600px] overflow-y-auto font-mono text-xs leading-relaxed">
        <table className="w-full border-collapse">
          <tbody>
            {parsedLines.map((row) => {
              let rowBg = 'hover:bg-gray-900/60';
              let textClass = 'text-gray-300';
              let lineIcon = null;

              if (row.type === 'file-header') {
                rowBg = 'bg-gray-900/90 font-bold border-y border-gray-800 text-indigo-300';
              } else if (row.type === 'header') {
                rowBg = 'bg-indigo-950/20 text-indigo-400 font-semibold border-y border-indigo-900/20';
              } else if (row.type === 'add') {
                rowBg = 'diff-added';
                textClass = 'text-emerald-300';
                lineIcon = <Plus className="w-3 h-3 text-emerald-400 shrink-0 inline mr-1" />;
              } else if (row.type === 'del') {
                rowBg = 'diff-deleted';
                textClass = 'text-red-400 line-through opacity-80';
                lineIcon = <Minus className="w-3 h-3 text-red-400 shrink-0 inline mr-1" />;
              }

              if (row.isHighlighted) {
                rowBg += ' ring-2 ring-indigo-500 bg-indigo-950/40';
              }

              return (
                <React.Fragment key={row.idx}>
                  <tr className={`${rowBg} transition-colors group`}>
                    <td className="w-12 select-none text-right pr-3 text-[10px] text-gray-600 bg-gray-950/60 border-r border-gray-850">
                      {row.lineNum || ''}
                    </td>
                    <td className="pl-3 pr-4 py-0.5 whitespace-pre font-mono">
                      <span className={textClass}>
                        {lineIcon}
                        {row.text}
                      </span>
                    </td>
                  </tr>

                  {/* Inline Finding Callout in Diff */}
                  {row.findings &&
                    row.findings.map((f) => (
                      <tr key={f.id} className="bg-red-950/30 border-y border-red-500/30">
                        <td className="bg-red-950/50 border-r border-red-900/40 text-center">
                          <AlertCircle className="w-3 h-3 text-red-400 mx-auto" />
                        </td>
                        <td className="p-2 text-xs">
                          <div className="flex items-center space-x-2">
                            <span className="text-[10px] font-bold uppercase tracking-wider bg-red-500/20 text-red-300 px-1.5 py-0.2 rounded border border-red-500/30">
                              {f.severity}
                            </span>
                            <span className="font-semibold text-white">{f.title}</span>
                          </div>
                          <p className="text-[11px] text-gray-300 mt-1">{f.why_identified}</p>
                        </td>
                      </tr>
                    ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
