import test from 'node:test';
import assert from 'node:assert';

// Pure logic tests mirroring FindingsList and SummaryCards standards filtering & metrics

function computeFindingCounts(findings) {
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
}

function filterFindings(findings, { selectedType = 'ALL', searchQuery = '', selectedSeverity = 'ALL' } = {}) {
  return findings.filter((f) => {
    const type = f.finding_type || 'code_defect';
    if (selectedType !== 'ALL' && type !== selectedType) {
      return false;
    }

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

    if (selectedSeverity !== 'ALL' && f.severity !== selectedSeverity) {
      return false;
    }

    return true;
  });
}

const SAMPLE_FINDINGS = [
  {
    id: 'F-001',
    title: 'SQL Injection in Auth Route',
    finding_type: 'code_defect',
    severity: 'CRITICAL',
    category: 'SECURITY_AND_RELIABILITY',
    confidence: 'CONFIRMED_ISSUE',
    location: { file_path: 'backend/auth.py', start_line: 42 },
    why_identified: 'Direct string concatenation in SQL execute',
    impact: 'Full database takeover',
  },
  {
    id: 'F-002',
    title: 'Prohibited import pickle detected',
    finding_type: 'policy_violation',
    rule_id: 'POLICY-IMPORT-001',
    rule_name: 'prohibited_imports',
    policy_category: 'security',
    policy_evaluation_status: 'violated',
    severity: 'HIGH',
    category: 'SECURITY_AND_RELIABILITY',
    confidence: 'CONFIRMED_ISSUE',
    location: { file_path: 'backend/loader.py', start_line: 12 },
    why_identified: 'Importing prohibited module pickle violates engineering standards',
    impact: 'Repository security standard breach',
  },
  {
    id: 'F-003',
    title: 'Function calculate_tax exceeds 50 lines',
    finding_type: 'policy_violation',
    rule_id: 'POLICY-LEN-001',
    rule_name: 'max_function_length',
    policy_category: 'code_style',
    policy_evaluation_status: 'violated',
    severity: 'LOW',
    category: 'CODE_QUALITY_AND_MAINTAINABILITY',
    confidence: 'CONFIRMED_ISSUE',
    location: { file_path: 'backend/tax.py', start_line: 1 },
    why_identified: 'Function length of 72 lines violates max limit of 50',
    impact: 'Maintenance difficulty',
  },
  {
    id: 'F-004',
    title: 'Consider using dataclasses instead of raw dicts',
    finding_type: 'recommendation',
    severity: 'INFO',
    category: 'CODE_QUALITY_AND_MAINTAINABILITY',
    confidence: 'IMPROVEMENT_SUGGESTION',
    location: { file_path: 'backend/models.py', start_line: 25 },
    why_identified: 'Typed structure improves maintainability',
    impact: 'Minor DX improvement',
  },
  {
    id: 'F-005',
    title: 'Legacy unclassified finding defaults to defect',
    // finding_type omitted
    severity: 'MEDIUM',
    category: 'BUG_OR_LOGIC_ERROR',
    confidence: 'POTENTIAL_ISSUE',
    location: { file_path: 'backend/utils.py', start_line: 15 },
    why_identified: 'Potential off-by-one error',
    impact: 'Array boundary crash',
  },
];

test('Phase 3 UI: computeFindingCounts accurately partitions defects, policies, and recommendations', () => {
  const counts = computeFindingCounts(SAMPLE_FINDINGS);
  assert.strictEqual(counts.all, 5);
  assert.strictEqual(counts.defects, 2); // F-001 and legacy F-005
  assert.strictEqual(counts.policies, 2); // F-002 and F-003
  assert.strictEqual(counts.recommendations, 1); // F-004
});

test('Phase 3 UI: filterFindings by finding_type filters correctly', () => {
  const policyViolations = filterFindings(SAMPLE_FINDINGS, { selectedType: 'policy_violation' });
  assert.strictEqual(policyViolations.length, 2);
  assert.ok(policyViolations.every((f) => f.finding_type === 'policy_violation'));

  const defects = filterFindings(SAMPLE_FINDINGS, { selectedType: 'code_defect' });
  assert.strictEqual(defects.length, 2);

  const recommendations = filterFindings(SAMPLE_FINDINGS, { selectedType: 'recommendation' });
  assert.strictEqual(recommendations.length, 1);
  assert.strictEqual(recommendations[0].id, 'F-004');
});

test('Phase 3 UI: search matching rule_id, rule_name, and policy_category', () => {
  const byRuleId = filterFindings(SAMPLE_FINDINGS, { searchQuery: 'POLICY-IMPORT' });
  assert.strictEqual(byRuleId.length, 1);
  assert.strictEqual(byRuleId[0].id, 'F-002');

  const byRuleName = filterFindings(SAMPLE_FINDINGS, { searchQuery: 'max_function_length' });
  assert.strictEqual(byRuleName.length, 1);
  assert.strictEqual(byRuleName[0].id, 'F-003');

  const byPolicyCat = filterFindings(SAMPLE_FINDINGS, { searchQuery: 'code_style' });
  assert.strictEqual(byPolicyCat.length, 1);
  assert.strictEqual(byPolicyCat[0].id, 'F-003');
});

