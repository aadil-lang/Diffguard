'use client';

import React, { useState, useMemo } from 'react';
import { Search, Filter, Download, CheckSquare, Layers, Bug, Sliders, Lightbulb } from 'lucide-react';
import { Finding, SeverityLevel, FindingCategory, FindingConfidence, FindingType } from '@/types';
import { FindingCard } from './FindingCard';

interface FindingsListProps {
  findings: Finding[];
  onNavigateToFile?: (file: string, line: number, lineSide?: string) => void;
}

export const FindingsList: React.FC<FindingsListProps> = ({ findings, onNavigateToFile }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedConfidence, setSelectedConfidence] = useState<string>('ALL');

  const counts = useMemo(() => {
    let defects = 0;
    let policies = 0;
    let recommendations = 0;
    findings.forEach((f) => {
      const t = f.finding_type || 'code_defect';
      if (t === 'policy_violation') policies++;
      else if (t === 'recommendation') recommendations++;
      else defects++;
    });
    return {
      all: findings.length,
      defects,
      policies,
      recommendations,
    };
  }, [findings]);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      // Finding Type filter
      const type = f.finding_type || 'code_defect';
      if (selectedType !== 'ALL' && type !== selectedType) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = f.title.toLowerCase().includes(q);
        const matchesFile = f.location.file_path.toLowerCase().includes(q);
        const matchesWhy = f.why_identified.toLowerCase().includes(q);
        const matchesRule = Boolean(
          (f.rule_id && f.rule_id.toLowerCase().includes(q)) ||
          (f.rule_name && f.rule_name.toLowerCase().includes(q)) ||
          (f.policy_category && f.policy_category.toLowerCase().includes(q))
        );
        if (!matchesTitle && !matchesFile && !matchesWhy && !matchesRule) return false;
      }

      // Severity filter
      if (selectedSeverity !== 'ALL' && f.severity !== selectedSeverity) {
        return false;
      }

      // Category filter
      if (selectedCategory !== 'ALL' && f.category !== selectedCategory) {
        return false;
      }

      // Confidence filter
      if (selectedConfidence !== 'ALL' && f.confidence !== selectedConfidence) {
        return false;
      }

      return true;
    });
  }, [findings, selectedType, searchQuery, selectedSeverity, selectedCategory, selectedConfidence]);

  const handleExportMarkdown = () => {
    let md = `# DiffGuard Code Review Report\n\n`;
    md += `Total Findings: ${findings.length} (Defects: ${counts.defects}, Policy Violations: ${counts.policies}, Recommendations: ${counts.recommendations})\n\n`;
    findings.forEach((f) => {
      md += `### [${f.id}] ${f.title}\n`;
      md += `- **Type:** ${f.finding_type || 'code_defect'}`;
      if (f.rule_id) md += ` | **Rule:** [${f.rule_id}] ${f.rule_name || ''}`;
      md += `\n- **Severity:** ${f.severity} | **Category:** ${f.category} | **Confidence:** ${f.confidence}\n`;
      md += `- **Location:** \`${f.location.file_path}:${f.location.start_line}\`\n`;
      md += `- **Root Cause:** ${f.why_identified}\n`;
      md += `- **Impact:** ${f.impact}\n`;
      if (f.suggested_fix) {
        md += `- **Suggested Fix:** ${f.suggested_fix.description}\n`;
        if (f.suggested_fix.replacement_code) {
          md += `\`\`\`\n${f.suggested_fix.replacement_code}\n\`\`\`\n`;
        }
      }
      md += `\n---\n\n`;
    });

    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diffguard-review-report-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Finding Type Segment Tabs */}
      <div className="flex items-center space-x-2 border-b border-gray-850 pb-2 overflow-x-auto text-xs">
        <button
          onClick={() => setSelectedType('ALL')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
            selectedType === 'ALL'
              ? 'bg-indigo-600/30 text-indigo-200 border border-indigo-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>All Findings</span>
          <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-gray-800 text-gray-300 font-mono">
            {counts.all}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('code_defect')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
            selectedType === 'code_defect'
              ? 'bg-rose-600/30 text-rose-200 border border-rose-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
          }`}
        >
          <Bug className="w-3.5 h-3.5 text-rose-400" />
          <span>Defects</span>
          <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-rose-950/60 text-rose-300 font-mono">
            {counts.defects}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('policy_violation')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
            selectedType === 'policy_violation'
              ? 'bg-purple-600/30 text-purple-200 border border-purple-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
          }`}
        >
          <Sliders className="w-3.5 h-3.5 text-purple-400" />
          <span>Policy Violations</span>
          <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-purple-950/60 text-purple-300 font-mono">
            {counts.policies}
          </span>
        </button>

        <button
          onClick={() => setSelectedType('recommendation')}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
            selectedType === 'recommendation'
              ? 'bg-teal-600/30 text-teal-200 border border-teal-500/40 shadow-sm'
              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
          }`}
        >
          <Lightbulb className="w-3.5 h-3.5 text-teal-400" />
          <span>Recommendations</span>
          <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-teal-950/60 text-teal-300 font-mono">
            {counts.recommendations}
          </span>
        </button>
      </div>

      {/* Search & Filter Controls */}
      <div className="bg-gray-900/90 border border-gray-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search findings by keyword, file, or rule..."
            className="w-full text-xs bg-gray-950/80 border border-gray-800 rounded-lg pl-9 pr-3 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Filter Dropdowns */}
        <div className="flex items-center space-x-2 flex-wrap gap-y-2">
          {/* Severity */}
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="text-xs bg-gray-950 border border-gray-800 text-gray-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
            <option value="INFO">Info</option>
          </select>

          {/* Category */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="text-xs bg-gray-950 border border-gray-800 text-gray-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Categories</option>
            <option value="SECURITY_AND_RELIABILITY">Security</option>
            <option value="BUG_OR_LOGIC_ERROR">Bugs & Logic</option>
            <option value="MISSING_TEST_COVERAGE">Test Coverage</option>
            <option value="CODE_QUALITY_AND_MAINTAINABILITY">Code Quality</option>
            <option value="STYLE_AND_CONSISTENCY">Style</option>
          </select>

          {/* Confidence */}
          <select
            value={selectedConfidence}
            onChange={(e) => setSelectedConfidence(e.target.value)}
            className="text-xs bg-gray-950 border border-gray-800 text-gray-300 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Confidences</option>
            <option value="CONFIRMED_ISSUE">Confirmed</option>
            <option value="POTENTIAL_ISSUE">Potential</option>
            <option value="IMPROVEMENT_SUGGESTION">Suggestion</option>
          </select>

          {/* Export Report */}
          <button
            onClick={handleExportMarkdown}
            className="flex items-center space-x-1.5 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-750 border border-gray-700 px-3 py-1.5 rounded-lg transition-colors"
            title="Download review report as Markdown"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </button>
        </div>
      </div>

      {/* Findings Count Header */}
      <div className="flex items-center justify-between text-xs text-gray-400 px-1">
        <span>
          Showing <span className="font-semibold text-white">{filteredFindings.length}</span> of{' '}
          <span className="font-semibold text-white">{findings.length}</span> findings
        </span>
        {(selectedType !== 'ALL' || selectedSeverity !== 'ALL' || selectedCategory !== 'ALL' || selectedConfidence !== 'ALL' || searchQuery) && (
          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedType('ALL');
              setSelectedSeverity('ALL');
              setSelectedCategory('ALL');
              setSelectedConfidence('ALL');
            }}
            className="text-indigo-400 hover:text-indigo-300 underline"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Findings List Items */}
      {filteredFindings.length > 0 ? (
        <div className="space-y-3">
          {filteredFindings.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              onNavigateToFile={onNavigateToFile}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-gray-900/40 border border-gray-800 rounded-2xl">
          <Layers className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-gray-300">No findings matched your criteria</h4>
          <p className="text-xs text-gray-500 mt-1">Try adjusting search filters or selecting All Severities.</p>
        </div>
      )}
    </div>
  );
};

