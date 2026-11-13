export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type FindingCategory =
  | 'BUG_OR_LOGIC_ERROR'
  | 'SECURITY_AND_RELIABILITY'
  | 'MISSING_TEST_COVERAGE'
  | 'CODE_QUALITY_AND_MAINTAINABILITY'
  | 'STYLE_AND_CONSISTENCY';

export type FindingConfidence =
  | 'CONFIRMED_ISSUE'
  | 'POTENTIAL_ISSUE'
  | 'IMPROVEMENT_SUGGESTION';

export type ReviewVerdict =
  | 'APPROVED'
  | 'APPROVED_WITH_COMMENTS'
  | 'CHANGES_REQUESTED'
  | 'CRITICAL_BLOCKER';

export interface CodeLocation {
  file_path: string;
  start_line: number;
  end_line?: number | null;
  hunk_header?: string | null;
  code_context?: string | null;
}

export interface SuggestedFix {
  description: string;
  replacement_code?: string | null;
  diff_patch?: string | null;
}

export interface Finding {
  id: string;
  title: string;
  category: FindingCategory;
  severity: SeverityLevel;
  confidence: FindingConfidence;
  location: CodeLocation;
  why_identified: string;
  impact: string;
  suggested_fix?: SuggestedFix | null;
  tool_evidence: string[];
}

export interface ReviewSummary {
  total_findings: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  by_confidence: Record<string, number>;
  verdict: ReviewVerdict;
  key_takeaways: string[];
}

export type StageStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

export interface ProcessingStage {
  stage_id: string;
  name: string;
  status: StageStatus;
  details?: string | null;
  duration_ms?: number | null;
}

export interface ReviewRequest {
  diff_content: string;
  title?: string | null;
  custom_instructions?: string | null;
  api_key?: string | null;
  model_name?: string | null;
}

export interface ReviewResponse {
  review_id: string;
  timestamp: string;
  parsed_files_count: number;
  total_additions: number;
  total_deletions: number;
  summary: ReviewSummary;
  findings: Finding[];
  stages_executed: ProcessingStage[];
  engine_used: string;
}

export interface SampleDiff {
  id: string;
  title: string;
  description: string;
  category_highlight: string;
  expected_severity: SeverityLevel;
  diff_content: string;
}
