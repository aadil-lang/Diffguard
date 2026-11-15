'use client';

import React, { useMemo } from 'react';
import { FileCode, AlertCircle, Plus, Minus } from 'lucide-react';
import { Finding } from '@/types';

interface DiffViewerProps {
  diffText: string;
  findings: Finding[];
  highlightFile?: string | null;
  highlightLine?: number | null;
  highlightSide?: string | null;
}

function normalizePath(rawPath: string): string {
  if (!rawPath) return '';
  let p = rawPath.trim().replace(/^["']|["']$/g, '').trim().replace(/\\/g, '/').replace(/^\//, '');
  while (p.startsWith('./')) {
    p = p.substring(2);
  }
  if (p.startsWith('a/') || p.startsWith('b/')) {
    p = p.substring(2);
  }
  while (p.startsWith('./')) {
    p = p.substring(2);
  }
  return p.replace(/^\//, '');
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diffText,
  findings,
  highlightFile,
  highlightLine,
  highlightSide,
}) => {
  // Index findings by file, side (new, old, both), and line number
  const findingsMap = useMemo(() => {
    const map = new Map<string, Finding[]>();

    findings.forEach((f) => {
      const canonical = normalizePath(f.location.file_path);
      const line = f.location.start_line;
      const side = f.location.line_side || 'new';

      // Disambiguate keys strictly by side to prevent old/new line collision
      const keys: string[] = [];
      if (side === 'new') {
        keys.push(`${canonical}:new:${line}`);
      } else if (side === 'old') {
        keys.push(`${canonical}:old:${line}`);
      } else if (side === 'both') {
        keys.push(`${canonical}:both:${line}`);
        keys.push(`${canonical}:new:${line}`);
        keys.push(`${canonical}:old:${line}`);
      } else if (side === 'file_level') {
        keys.push(`${canonical}:file_level`);
      } else {
        keys.push(`${canonical}:new:${line}`);
      }

      keys.forEach((key) => {
        const existing = map.get(key) || [];
        if (!existing.some((item) => item.id === f.id)) {
          existing.push(f);
        }
        map.set(key, existing);
      });
    });

    return map;
  }, [findings]);

  const parsedLines = useMemo(() => {
    if (!diffText) return [];
    const lines = diffText.replace(/\r\n/g, '\n').split('\n');
    let currentFile = '';
    let sourceLineNo = 0;
    let targetLineNo = 0;

    return lines.map((line, idx) => {
      let type: 'header' | 'file-header' | 'add' | 'del' | 'context' = 'context';
      let oldLine: number | null = null;
      let newLine: number | null = null;

      if (line.startsWith('diff --git')) {
        type = 'file-header';
        const match = line.match(/b\/(.*)$/);
        if (match) currentFile = normalizePath(match[1]);
      } else if (line.startsWith('+++ b/')) {
        type = 'file-header';
        currentFile = normalizePath(line.replace('+++ b/', ''));
      } else if (line.startsWith('--- a/')) {
        type = 'file-header';
        if (!currentFile) currentFile = normalizePath(line.replace('--- a/', ''));
      } else if (line.startsWith('@@')) {
        type = 'header';
        const match = line.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
        if (match) {
          sourceLineNo = parseInt(match[1], 10) - 1;
          targetLineNo = parseInt(match[2], 10) - 1;
        }
      } else if (line.startsWith('+')) {
        type = 'add';
        targetLineNo += 1;
        newLine = targetLineNo;
      } else if (line.startsWith('-')) {
        type = 'del';
        sourceLineNo += 1;
        oldLine = sourceLineNo;
      } else {
        type = 'context';
        sourceLineNo += 1;
        targetLineNo += 1;
        oldLine = sourceLineNo;
        newLine = targetLineNo;
      }

      // Find matching findings for this line with strict side distinction
      const matchedFindings: Finding[] = [];
      const seenIds = new Set<string>();

      const checkKeys: string[] = [];
      if (type === 'add' && newLine !== null) {
        checkKeys.push(`${currentFile}:new:${newLine}`);
      } else if (type === 'del' && oldLine !== null) {
        checkKeys.push(`${currentFile}:old:${oldLine}`);
      } else if (type === 'context') {
        if (newLine !== null) checkKeys.push(`${currentFile}:new:${newLine}`, `${currentFile}:both:${newLine}`);
        if (oldLine !== null) checkKeys.push(`${currentFile}:old:${oldLine}`);
      } else if (type === 'file-header') {
        checkKeys.push(`${currentFile}:file_level`);
      }

      checkKeys.forEach((k) => {
        const found = findingsMap.get(k);
        if (found) {
          found.forEach((f) => {
            if (!seenIds.has(f.id)) {
              seenIds.add(f.id);
              matchedFindings.push(f);
            }
          });
        }
      });

      // Highlight check with strict side distinction
      let isHighlighted = false;
      if (highlightFile) {
        const normHighlight = normalizePath(highlightFile);
        const fileMatches = currentFile === normHighlight || currentFile.endsWith('/' + normHighlight);
        if (fileMatches) {
          if (highlightSide === 'file_level' || highlightLine === 0) {
            isHighlighted = type === 'file-header';
          } else if (highlightSide === 'old') {
            isHighlighted = oldLine === highlightLine && (type === 'del' || type === 'context');
          } else if (highlightSide === 'new') {
            isHighlighted = newLine === highlightLine && (type === 'add' || type === 'context');
          } else if (highlightSide === 'both') {
            isHighlighted = (newLine === highlightLine || oldLine === highlightLine) && type === 'context';
          } else {
            isHighlighted = newLine === highlightLine || oldLine === highlightLine;
          }
        }
      }

      return {
        idx,
        text: line,
        type,
        currentFile,
        oldLine,
        newLine,
        findings: matchedFindings.length > 0 ? matchedFindings : undefined,
        isHighlighted,
      };
    });
  }, [diffText, findingsMap, highlightFile, highlightLine, highlightSide]);

  if (!diffText) return null;

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
      <div className="bg-gray-900 px-4 py-2.5 border-b border-gray-800 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center space-x-2">
          <FileCode className="w-4 h-4 text-indigo-400" />
          <span className="font-semibold text-gray-200">Unified Diff Code View</span>
        </div>
        <div className="flex items-center space-x-3 text-[11px] font-mono text-gray-500">
          <span className="flex items-center"><span className="w-2 h-2 rounded-full bg-red-500/50 inline-block mr-1"></span>Old (Deleted)</span>
          <span className="flex items-center"><span className="w-2 h-2 rounded-full bg-emerald-500/50 inline-block mr-1"></span>New (Added)</span>
          <span>{parsedLines.length} lines</span>
        </div>
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
                rowBg += ' ring-2 ring-indigo-500 bg-indigo-950/50';
              }

              return (
                <React.Fragment key={row.idx}>
                  <tr className={`${rowBg} transition-colors group`}>
                    {/* Old line number column */}
                    <td className="w-10 select-none text-right pr-2 text-[10px] text-gray-600 bg-gray-950/60 border-r border-gray-900">
                      {row.oldLine || ''}
                    </td>
                    {/* New line number column */}
                    <td className="w-10 select-none text-right pr-3 text-[10px] text-gray-600 bg-gray-950/60 border-r border-gray-800">
                      {row.newLine || ''}
                    </td>
                    {/* Code text */}
                    <td className="pl-3 pr-4 py-0.5 whitespace-pre font-mono">
                      <span className={textClass}>
                        {lineIcon}
                        {row.text}
                      </span>
                    </td>
                  </tr>

                  {/* Inline Finding Callout in Diff (supports both added and deleted lines) */}
                  {row.findings &&
                    row.findings.map((f) => (
                      <tr key={f.id} className="bg-red-950/30 border-y border-red-500/40">
                        <td colSpan={2} className="bg-red-950/60 border-r border-red-900/40 text-center py-1">
                          <AlertCircle className="w-3.5 h-3.5 text-red-400 mx-auto" />
                        </td>
                        <td className="p-3 text-xs">
                          <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider bg-red-500/20 text-red-300 px-1.5 py-0.2 rounded border border-red-500/30">
                              {f.severity}
                            </span>
                            <span className="font-semibold text-white">{f.title}</span>
                            {f.location.location_status && (
                              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-1.5 py-0.2 rounded border border-emerald-800/40">
                                {f.location.line_side === 'old' ? `Old Line ${row.oldLine}` : `New Line ${row.newLine}`}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-gray-300 mt-1 leading-normal">{f.why_identified}</p>
                          {f.suggested_fix?.description && (
                            <div className="mt-1.5 text-[11px] text-indigo-300 font-sans">
                              <strong>Suggested Fix:</strong> {f.suggested_fix.description}
                            </div>
                          )}
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
