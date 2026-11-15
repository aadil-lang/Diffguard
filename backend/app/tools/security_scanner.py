"""
Security Scanner Tool: Detects common OWASP and CWE vulnerabilities in diff code.
"""

import re
from typing import Dict, List, Any, Tuple, Optional


# Common sensitive variable naming pattern (supports singular/plural, compound prefixes, and quoted dict keys)
SENSITIVE_VAR_PATTERN = r"""["'`]?(?:api[_-]?(?:keys?|tokens?)|aws[_-]?(?:secrets?[_-]?)?keys?|(?:database|db)[_-]?(?:passwords?|passwd)|(?:client[_-]?)?secrets?(?:[_-]?(?:keys?|tokens?))?|auth[_-]?(?:tokens?|keys?|secrets?)|tokens?|passwords?|passwd|jwt[_-]?(?:secrets?[_-]?)?keys?|jwt[_-]?secrets?|private[_-]?keys?)["'`]?"""

# Container opening delimiters and optional dictionary key prefixes
CONTAINER_PREFIX_PATTERN = r"""(?:[\[\(\{]+\s*)*(?:["'`][A-Za-z0-9_\-\.]+["'`]\s*:\s*)?"""

SECURITY_RULES = [
    {
        "id": "SEC-SQLI-001",
        "cwe": "CWE-89",
        "name": "SQL Injection Risk",
        "severity": "CRITICAL",
        "description": "SQL query constructed via string formatting, f-strings, or string concatenation instead of parameterized queries.",
        "pattern": re.compile(
            r"""(execute|cursor\.execute|query|raw)\s*\(\s*(f["']|["'].*?%|["'].*?\bformat\b|\w+\s*\+\s*["'])|(query|sql|raw_query)\s*=\s*f["'].*(SELECT|INSERT|UPDATE|DELETE)|(SELECT|INSERT|UPDATE|DELETE)\s+.*?\bWHERE\b.*?['"]\s*\{\w+\}['"]""",
            re.IGNORECASE
        ),
        "remediation": "Use parameterized queries or ORM query builders (e.g., cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password_hash)))"
    },
    {
        "id": "SEC-SECRET-002",
        "cwe": "CWE-798",
        "name": "Hardcoded Secret / Credential",
        "severity": "CRITICAL",
        "description": "Hardcoded API key, token, private key, or password detected in source code.",
        "pattern": re.compile(
            r"""(?i)(""" + SENSITIVE_VAR_PATTERN + r""")\s*([:=])\s*""" + CONTAINER_PREFIX_PATTERN + r"""((?:["'`][A-Za-z0-9_\-\.]+["'`]\s*\+\s*)*["'`]([A-Za-z0-9_\-\.]{12,})["'`](?:\s*\+\s*["'`][A-Za-z0-9_\-\.]+["'`])*)""",
            re.MULTILINE
        ),
        "remediation": "Load sensitive credentials from environment variables or a secure secret manager (e.g., os.getenv('API_KEY'))"
    },
    {
        "id": "SEC-CMD-003",
        "cwe": "CWE-78",
        "name": "OS Command Injection Risk",
        "severity": "HIGH",
        "description": "Executing shell commands with shell=True or direct string interpolation.",
        "pattern": re.compile(
            r"""(?i)(os\.system|subprocess\.(call|Popen|run)\s*\([^)]*shell\s*=\s*True)""",
            re.MULTILINE
        ),
        "remediation": "Avoid shell=True. Pass command arguments as a list of strings: subprocess.run(['cmd', arg1, arg2], check=True)"
    },
    {
        "id": "SEC-DESER-004",
        "cwe": "CWE-502",
        "name": "Insecure Deserialization",
        "severity": "HIGH",
        "description": "Untrusted deserialization using pickle.loads or unsafe yaml.load.",
        "pattern": re.compile(
            r"""(?i)(pickle\.loads|yaml\.load\s*\([^,)]*(?!\bLoader=yaml\.SafeLoader\b)[^)]*\))""",
            re.MULTILINE
        ),
        "remediation": "Use safe serializers like json.loads() or yaml.safe_load() to prevent arbitrary code execution."
    },
    {
        "id": "SEC-CRYPTO-005",
        "cwe": "CWE-327",
        "name": "Broken Cryptographic Algorithm",
        "severity": "MEDIUM",
        "description": "Using weak hashing algorithms (MD5, SHA1) for security or password hashing.",
        "pattern": re.compile(
            r"""(?i)hashlib\.(md5|sha1)\s*\(""",
            re.MULTILINE
        ),
        "remediation": "Use SHA-256/SHA-512 for checksums, or bcrypt/argon2id for password hashing."
    },
    {
        "id": "SEC-XSS-006",
        "cwe": "CWE-79",
        "name": "Cross-Site Scripting (XSS) Risk",
        "severity": "HIGH",
        "description": "Direct insertion of unescaped HTML or using dangerouslySetInnerHTML.",
        "pattern": re.compile(
            r"""(?i)(dangerouslySetInnerHTML|innerHTML\s*=)""",
            re.MULTILINE
        ),
        "remediation": "Sanitize user input before rendering with DOMPurify or use standard React text interpolation."
    },
    {
        "id": "SEC-TRAVERSAL-007",
        "cwe": "CWE-22",
        "name": "Path Traversal Risk",
        "severity": "HIGH",
        "description": "Directly joining file paths with user input without sanitisation.",
        "pattern": re.compile(
            r"""(?i)(open|send_file|create_read_stream)\s*\(\s*(os\.path\.join\([^)]*user|path\.join\([^)]*req)""",
            re.MULTILINE
        ),
        "remediation": "Validate input against an allowlist, use os.path.basename(), and ensure resolved path starts with base directory."
    }
]


# Match string literal in single, double, or backtick quotes
STRING_LITERAL = r"""(?:"[^"\r\n]*"|'[^'\r\n]*'|`[^`\r\n]*`)"""

# Unclosed quote on sensitive assignment pattern (ANY length >= 0)
UNCLOSED_SECRET_PATTERN = re.compile(
    r"""(?i)(""" + SENSITIVE_VAR_PATTERN + r""")\s*([:=])\s*((?:[\[\(\{]+\s*)*(?:["'`][A-Za-z0-9_\-\.]+["'`]\s*:\s*)?)(["'`][^"'`\r\n]*)(?:[\]\)\}\s#,].*)?$""",
    re.MULTILINE
)

# Standalone single-line sensitive assignment for disclosure redaction (ANY length >= 0)
STANDALONE_SECRET_ASSIGNMENT = re.compile(
    r"""(?i)(""" + SENSITIVE_VAR_PATTERN + r""")\s*([:=])\s*""" + CONTAINER_PREFIX_PATTERN + r"""((?:""" + STRING_LITERAL + r"""\s*\+\s*)*""" + STRING_LITERAL + r""")""",
    re.MULTILINE
)

# Sensitive container start pattern (detects containers assigned to sensitive variable names)
SENSITIVE_CONTAINER_START = re.compile(
    r"""(?i)(""" + SENSITIVE_VAR_PATTERN + r""")\s*([:=])\s*([\[\(\{])""",
    re.MULTILINE
)

# String element or compound concatenation pattern inside containers (ANY length >= 0)
STRING_ELEM_PATTERN = re.compile(
    r"""((?:""" + STRING_LITERAL + r"""\s*\+\s*)*""" + STRING_LITERAL + r""")"""
)


def is_quote_count_odd(text: str) -> Tuple[bool, Optional[int]]:
    """
    Checks if there is an unclosed quote on the line.
    Returns (True, last_quote_idx) if odd/unclosed, (False, None) if even/closed.
    Respects backslash escaping and inline comments.
    """
    in_quote = False
    quote_char = ''
    escape = False
    last_quote_start = -1

    for idx, char in enumerate(text):
        if in_quote:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote_char:
                in_quote = False
                quote_char = ''
        else:
            if char in ('"', "'", '`'):
                in_quote = True
                quote_char = char
                last_quote_start = idx
            elif char == '#':
                break

    return (in_quote, last_quote_start if in_quote else None)


def is_index_inside_quote(line: str, target_idx: int) -> bool:
    """
    Checks whether a specific character index in line occurs inside a string literal
    (single, double, or backtick quote), accounting for backslash escaping.
    """
    in_quote = False
    quote_char = ''
    escape = False

    for idx, char in enumerate(line):
        if idx >= target_idx:
            break
        if in_quote:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote_char:
                in_quote = False
                quote_char = ''
        else:
            if char in ('"', "'", '`'):
                in_quote = True
                quote_char = char
            elif char == '#':
                break

    return in_quote


class ContainerScopeTracker:
    """
    Tracks state of sensitive container scopes across multiple lines.
    Maintains a depth counter for open brackets/braces/parentheses within sensitive assignments.
    Quote-aware to avoid bracket counts inside string literals.
    """
    def __init__(self):
        self.depth: int = 0
        self.active_var: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.depth > 0

    def process_line(self, line: str) -> str:
        """
        Processes a line in the context of this scope tracker.
        Returns the sanitized line and updates scope depth.
        """
        if not line or not line.strip():
            return line

        # If scope is NOT active, check if this line OPENS a sensitive container
        if not self.is_active:
            m_start = SENSITIVE_CONTAINER_START.search(line)
            if m_start and not is_index_inside_quote(line, m_start.start(1)):
                var_name = m_start.group(1)
                container_start_idx = m_start.start(3)
                sanitized_line = self._sanitize_container_elements(line, container_start_idx)
                net_depth = self._compute_net_delimiters(sanitized_line[container_start_idx:])
                if net_depth > 0:
                    self.depth = net_depth
                    self.active_var = var_name
                else:
                    self.depth = 0
                    self.active_var = None
                return sanitized_line
            else:
                return redact_single_line_secrets(line)

        else:
            sanitized_line = self._sanitize_continuation_line(line)
            net_depth = self._compute_net_delimiters(sanitized_line)
            self.depth += net_depth
            if self.depth <= 0:
                self.depth = 0
                self.active_var = None
            return sanitized_line

    def _sanitize_container_elements(self, line: str, start_idx: int) -> str:
        """Sanitizes string elements within container starting from start_idx."""
        prefix = line[:start_idx]
        tail = line[start_idx:]
        
        odd, pos = is_quote_count_odd(tail)
        if odd and pos is not None:
            head = tail[:pos]
            head_san = self._replace_closed_strings(head)
            return prefix + head_san + '"[REDACTED]"'
        else:
            tail_san = self._replace_closed_strings(tail)
            return prefix + tail_san

    def _sanitize_continuation_line(self, line: str) -> str:
        """Sanitizes a continuation line inside active container scope."""
        odd, pos = is_quote_count_odd(line)
        if odd and pos is not None:
            head = line[:pos]
            head_san = self._replace_closed_strings(head)
            return head_san + '"[REDACTED]"'
        else:
            return self._replace_closed_strings(line)

    def _replace_closed_strings(self, text: str) -> str:
        matches = list(STRING_ELEM_PATTERN.finditer(text))
        if not matches:
            return text

        valid_spans = []
        for m in matches:
            s, e = m.span(1)
            raw_val = m.group(1)
            tail = text[e:].lstrip()
            if tail.startswith(':'):
                # Dictionary key, do not redact
                continue
            if raw_val.startswith("`") and raw_val.endswith("`") and '+' not in raw_val:
                repl = "`[REDACTED]`"
            elif raw_val.startswith("'") and raw_val.endswith("'") and '+' not in raw_val:
                repl = "'[REDACTED]'"
            else:
                repl = '"[REDACTED]"'
            valid_spans.append((s, e, repl))

        valid_spans.sort(key=lambda x: x[0], reverse=True)
        res = text
        for s, e, repl in valid_spans:
            res = res[:s] + repl + res[e:]

        return res

    def _compute_net_delimiters(self, text: str) -> int:
        """Computes net delimiter depth change (open - close), ignoring characters in quotes or comments."""
        net = 0
        in_quote = False
        quote_char = ''
        escape = False

        for char in text:
            if in_quote:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == quote_char:
                    in_quote = False
            else:
                if char in ('"', "'", '`'):
                    in_quote = True
                    quote_char = char
                elif char == '#':
                    break
                elif char in ('[', '(', '{'):
                    net += 1
                elif char in (']', ')', '}'):
                    net -= 1
        return net


def redact_single_line_secrets(line: str) -> str:
    """
    Safely redacts secrets on a single line (standalone or single-line container).
    Redacts any recognized sensitive assignment regardless of length.
    """
    if not line or not line.strip():
        return line

    evidence = line

    # 1. Unclosed quote on sensitive assignment (only when there is an unclosed quote on the line)
    is_odd, _ = is_quote_count_odd(evidence)
    if is_odd:
        unclosed_m = UNCLOSED_SECRET_PATTERN.search(evidence)
        if unclosed_m and not is_index_inside_quote(evidence, unclosed_m.start(1)):
            try:
                var_name = unclosed_m.group(1)
                op = unclosed_m.group(2)
                prefix_containers = unclosed_m.group(3) or ""
                s = unclosed_m.start()
                return evidence[:s] + f'{var_name} {op} {prefix_containers}"[REDACTED]"'
            except Exception:
                return "[REDACTED]"

    # 2. Check container on single line
    container_m = SENSITIVE_CONTAINER_START.search(evidence)
    valid_spans = []
    if container_m and not is_index_inside_quote(evidence, container_m.start(1)):
        container_start = container_m.start(3)
        for sm in STRING_ELEM_PATTERN.finditer(evidence[container_start:]):
            raw_val = sm.group(1)
            s = container_start + sm.start(1)
            e = container_start + sm.end(1)
            tail = evidence[e:].lstrip()
            if tail.startswith(':'):
                # Dictionary key, do not redact
                continue
            if 0 <= s < e <= len(evidence):
                if raw_val.startswith("`") and raw_val.endswith("`") and '+' not in raw_val:
                    repl = "`[REDACTED]`"
                elif raw_val.startswith("'") and raw_val.endswith("'") and '+' not in raw_val:
                    repl = "'[REDACTED]'"
                else:
                    repl = '"[REDACTED]"'
                valid_spans.append((s, e, repl, raw_val))

    # Also match standalone assignments and dict keys
    matches = list(STANDALONE_SECRET_ASSIGNMENT.finditer(evidence))
    for m in matches:
        if is_index_inside_quote(evidence, m.start(1)):
            continue
        try:
            var_name = m.group(1)
            op = m.group(2)
            raw_val = m.group(3)
            s, e = m.span(3)

            if not isinstance(s, int) or not isinstance(e, int) or s < 0 or e < 0 or s >= e or e > len(evidence):
                return f'{var_name} {op} "[REDACTED]"'

            if raw_val.startswith("`") and raw_val.endswith("`") and '+' not in raw_val:
                repl = "`[REDACTED]`"
            elif raw_val.startswith("'") and raw_val.endswith("'") and '+' not in raw_val:
                repl = "'[REDACTED]'"
            else:
                repl = '"[REDACTED]"'
            if not any(ex_s == s and ex_e == e for ex_s, ex_e, _, _ in valid_spans):
                valid_spans.append((s, e, repl, raw_val))
        except Exception:
            return "[REDACTED]"

    if not valid_spans:
        return evidence

    valid_spans.sort(key=lambda x: x[0], reverse=True)
    # Check overlaps
    for i in range(len(valid_spans) - 1):
        if valid_spans[i][0] < valid_spans[i + 1][1]:
            return "[REDACTED]"

    for s, e, repl, _ in valid_spans:
        evidence = evidence[:s] + repl + evidence[e:]

    return evidence

    if not valid_spans:
        return evidence

    valid_spans.sort(key=lambda x: x[0], reverse=True)
    # Check overlaps
    for i in range(len(valid_spans) - 1):
        if valid_spans[i][0] < valid_spans[i + 1][1]:
            return "[REDACTED]"

    for s, e, repl, _ in valid_spans:
        evidence = evidence[:s] + repl + evidence[e:]

    return evidence


def redact_sensitive_line(line: str) -> str:
    """
    Public API: safely redacts all credential values from a single line.
    Handles multiple secrets on one line, containerized secret assignments (lists, tuples, dicts),
    compound string concatenation, different quote styles, whitespace, and unclosed quotes.
    Validates capture spans and fails closed if safe replacement cannot be established.
    """
    return redact_single_line_secrets(line)


def sanitize_code_snippet(code: str) -> str:
    """
    Sanitizes a multi-line code snippet maintaining container scope across lines.
    Used by syntax and linter checkers to ensure multi-line container secrets are redacted.
    """
    if not code:
        return code
    tracker = ContainerScopeTracker()
    sanitized_lines = []
    for line in code.splitlines():
        sanitized_lines.append(tracker.process_line(line))
    return "\n".join(sanitized_lines)


def sanitize_diff_content(diff_text: str) -> str:
    """
    Sanitizes git diff content with:
    1. Structural unified-diff awareness (file headers vs hunk bodies).
    2. Strict deleted-line classification inside hunks (supports `--`, `- `, `---`).
    3. Diff-side-aware multi-line container scope tracking (old_scope and new_scope).
    4. Short credential redaction.
    """
    if not diff_text:
        return diff_text

    sanitized_lines = []
    in_hunk = False
    old_scope = ContainerScopeTracker()
    new_scope = ContainerScopeTracker()

    lines = diff_text.splitlines()
    for idx, line in enumerate(lines):
        # 1. Structural file headers and metadata outside hunks
        if line.startswith("diff --git"):
            in_hunk = False
            old_scope = ContainerScopeTracker()
            new_scope = ContainerScopeTracker()
            sanitized_lines.append(line)
            continue

        # Check for non-git diff file header boundary
        if line.startswith("--- ") and (idx + 1 < len(lines) and lines[idx + 1].startswith("+++ ")):
            in_hunk = False
            old_scope = ContainerScopeTracker()
            new_scope = ContainerScopeTracker()
            sanitized_lines.append(line)
            continue

        if not in_hunk:
            if (line.startswith("index ") or line.startswith("--- ") or
                line.startswith("+++ ") or line.startswith("new file mode") or
                line.startswith("deleted file mode") or line.startswith("similarity index") or
                line.startswith("rename from") or line.startswith("rename to") or
                line.startswith("Binary files")):
                sanitized_lines.append(line)
                continue
            elif line.startswith("@@"):
                in_hunk = True
                sanitized_lines.append(line)
                continue
            else:
                sanitized_lines.append(line)
                continue

        # 2. Inside a hunk!
        if line.startswith("@@"):
            # New hunk header in same file
            sanitized_lines.append(line)
            continue
        elif line.startswith("+"):
            content = line[1:]
            redacted = new_scope.process_line(content)
            sanitized_lines.append("+" + redacted)
        elif line.startswith("-"):
            content = line[1:]
            redacted = old_scope.process_line(content)
            sanitized_lines.append("-" + redacted)
        elif line.startswith(" "):
            content = line[1:]
            # Context line exists on BOTH old and new sides
            redacted_new = new_scope.process_line(content)
            _ = old_scope.process_line(content)
            sanitized_lines.append(" " + redacted_new)
        elif line.startswith("\\"):
            sanitized_lines.append(line)
        else:
            sanitized_lines.append(line)

    return "\n".join(sanitized_lines)


def scan_security_issues(code_snippet: str, file_path: str = "") -> List[Dict[str, Any]]:
    """
    Run security scanner across code snippet and return structured detections.
    """
    findings = []
    lines = code_snippet.splitlines()

    for rule in SECURITY_RULES:
        for line_no, line in enumerate(lines, start=1):
            if line.startswith("-"):
                # Skip removed lines in diffs
                continue

            clean_line = line.lstrip("+ ")

            if rule["id"] == "SEC-SECRET-002":
                matches = [m for m in rule["pattern"].finditer(clean_line) if not is_index_inside_quote(clean_line, m.start(1))]
                if not matches:
                    is_odd, _ = is_quote_count_odd(clean_line)
                    if is_odd:
                        unclosed_m = UNCLOSED_SECRET_PATTERN.search(clean_line)
                        if unclosed_m and not is_index_inside_quote(clean_line, unclosed_m.start(1)):
                            matches = [unclosed_m]
                if matches:
                    evidence_code = redact_sensitive_line(clean_line)
                    findings.append({
                        "rule_id": rule["id"],
                        "cwe": rule["cwe"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "file_path": file_path,
                        "line_number": line_no,
                        "matched_code": evidence_code.strip(),
                        "remediation": rule["remediation"]
                    })
            else:
                match = rule["pattern"].search(clean_line)
                if match:
                    findings.append({
                        "rule_id": rule["id"],
                        "cwe": rule["cwe"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "description": rule["description"],
                        "file_path": file_path,
                        "line_number": line_no,
                        "matched_code": clean_line.strip(),
                        "remediation": rule["remediation"]
                    })

    return findings


