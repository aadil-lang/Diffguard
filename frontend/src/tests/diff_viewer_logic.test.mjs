import test from 'node:test';
import assert from 'node:assert';

// Pure implementation mirroring frontend/src/components/DiffViewer.tsx logic
function normalizePath(rawPath) {
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

function buildFindingsMap(findings) {
  const map = new Map();

  findings.forEach((f) => {
    const canonical = normalizePath(f.location.file_path);
    const line = f.location.start_line;
    const side = f.location.line_side || 'new';

    // Strict side-specific key registration to eliminate old/new line collision
    const keys = [];
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
}

function parseAndMatchLines(diffText, findingsMap, highlightFile = null, highlightLine = null, highlightSide = null) {
  const lines = diffText.replace(/\r\n/g, '\n').split('\n');
  let currentFile = '';
  let sourceLineNo = 0;
  let targetLineNo = 0;

  return lines.map((line, idx) => {
    let type = 'context';
    let oldLine = null;
    let newLine = null;

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

    const matchedFindings = [];
    const seenIds = new Set();
    const checkKeys = [];

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
}

// SAMPLE DIFF where line 10 exists on BOTH old side (deleted) and new side (added)
const TEST_COLLISION_DIFF = `diff --git a/services/auth.py b/services/auth.py
--- a/services/auth.py
+++ b/services/auth.py
@@ -10,2 +10,2 @@
-old insecure query at line 10
+new parameterized call at line 10
 context line 11
`;

test('P2-02: normalizePath handles quotes, ./, and prefixes safely', () => {
  assert.strictEqual(normalizePath('a/services/auth.py'), 'services/auth.py');
  assert.strictEqual(normalizePath('b/services/auth.py'), 'services/auth.py');
  assert.strictEqual(normalizePath('./services/auth.py'), 'services/auth.py');
  assert.strictEqual(normalizePath('"services/auth.py"'), 'services/auth.py');
  assert.strictEqual(normalizePath('"./a/services/auth.py"'), 'services/auth.py');
  assert.strictEqual(normalizePath('services\\auth.py'), 'services/auth.py');
  assert.strictEqual(normalizePath('  "b/my path/auth.py"  '), 'my path/auth.py');
});

test('P1-02 Requirement 1: Added line 10 with finding on new line 10 associates ONLY with added line', () => {
  const findings = [{
    id: 'DG-NEW-10',
    title: 'Finding on added line 10',
    location: { file_path: 'services/auth.py', start_line: 10, line_side: 'new' }
  }];
  const map = buildFindingsMap(findings);
  const rows = parseAndMatchLines(TEST_COLLISION_DIFF, map);

  const delRow = rows.find(r => r.type === 'del' && r.oldLine === 10);
  const addRow = rows.find(r => r.type === 'add' && r.newLine === 10);

  assert.ok(addRow, 'Added row line 10 should exist');
  assert.ok(delRow, 'Deleted row line 10 should exist');

  assert.strictEqual(addRow.findings?.length, 1, 'Added row MUST have finding DG-NEW-10');
  assert.strictEqual(addRow.findings?.[0].id, 'DG-NEW-10');
  assert.strictEqual(delRow.findings, undefined, 'Deleted row MUST NOT have finding DG-NEW-10');
});

test('P1-02 Requirement 2: Deleted line 10 with finding on old line 10 associates ONLY with deleted line', () => {
  const findings = [{
    id: 'DG-OLD-10',
    title: 'Finding on deleted line 10',
    location: { file_path: 'services/auth.py', start_line: 10, line_side: 'old' }
  }];
  const map = buildFindingsMap(findings);
  const rows = parseAndMatchLines(TEST_COLLISION_DIFF, map);

  const delRow = rows.find(r => r.type === 'del' && r.oldLine === 10);
  const addRow = rows.find(r => r.type === 'add' && r.newLine === 10);

  assert.strictEqual(delRow.findings?.length, 1, 'Deleted row MUST have finding DG-OLD-10');
  assert.strictEqual(delRow.findings?.[0].id, 'DG-OLD-10');
  assert.strictEqual(addRow.findings, undefined, 'Added row MUST NOT have finding DG-OLD-10');
});

test('P1-02 Requirements 3 & 4: Two findings on opposite sides of the same line 10 attach strictly to their respective sides', () => {
  const findings = [
    {
      id: 'DG-NEW-10',
      title: 'Added query issue',
      location: { file_path: 'services/auth.py', start_line: 10, line_side: 'new' }
    },
    {
      id: 'DG-OLD-10',
      title: 'Removed logic issue',
      location: { file_path: 'services/auth.py', start_line: 10, line_side: 'old' }
    }
  ];
  const map = buildFindingsMap(findings);
  const rows = parseAndMatchLines(TEST_COLLISION_DIFF, map);

  const delRow = rows.find(r => r.type === 'del' && r.oldLine === 10);
  const addRow = rows.find(r => r.type === 'add' && r.newLine === 10);

  assert.strictEqual(addRow.findings?.length, 1);
  assert.strictEqual(addRow.findings?.[0].id, 'DG-NEW-10');

  assert.strictEqual(delRow.findings?.length, 1);
  assert.strictEqual(delRow.findings?.[0].id, 'DG-OLD-10');
});

test('P1-02 Requirement 5: Navigation highlights intended side only', () => {
  const map = buildFindingsMap([]);

  // Navigate to NEW side line 10
  const rowsNavNew = parseAndMatchLines(TEST_COLLISION_DIFF, map, 'services/auth.py', 10, 'new');
  const addRowNew = rowsNavNew.find(r => r.type === 'add' && r.newLine === 10);
  const delRowNew = rowsNavNew.find(r => r.type === 'del' && r.oldLine === 10);

  assert.strictEqual(addRowNew.isHighlighted, true, 'Added line 10 MUST be highlighted when navigating to new side');
  assert.strictEqual(delRowNew.isHighlighted, false, 'Deleted line 10 MUST NOT be highlighted when navigating to new side');

  // Navigate to OLD side line 10
  const rowsNavOld = parseAndMatchLines(TEST_COLLISION_DIFF, map, 'services/auth.py', 10, 'old');
  const addRowOld = rowsNavOld.find(r => r.type === 'add' && r.newLine === 10);
  const delRowOld = rowsNavOld.find(r => r.type === 'del' && r.oldLine === 10);

  assert.strictEqual(delRowOld.isHighlighted, true, 'Deleted line 10 MUST be highlighted when navigating to old side');
  assert.strictEqual(addRowOld.isHighlighted, false, 'Added line 10 MUST NOT be highlighted when navigating to old side');
});

