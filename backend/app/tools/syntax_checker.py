"""
Syntax and Linter Check Tool: Analyzes code snippets for syntax anomalies, unclosed structures,
and common runtime traps (such as missing await or undefined reference).
"""

import ast
import re
import textwrap
from typing import Dict, List, Any
from app.tools.security_scanner import redact_sensitive_line, sanitize_code_snippet


def check_python_syntax(code_snippet: str, file_path: str = "") -> List[Dict[str, Any]]:
    """Parse python code with ast to find syntax errors and missing await traps."""
    issues = []
    clean_lines = []
    
    for line in code_snippet.splitlines():
        if line.startswith("-"):
            continue
        clean_lines.append(line.lstrip("+ "))

    full_code = "\n".join(clean_lines)

    # 1. AST Validation
    # In unified diffs, hunks are code fragments. We strip common indentation and only
    # flag genuine syntax failures (e.g. unclosed brackets, invalid tokens), avoiding false positives
    # caused by missing outer def/class blocks in isolated hunks.
    try:
        ast.parse(textwrap.dedent(full_code))
    except (SyntaxError, IndentationError) as e:
        msg = str(e.msg).lower() if hasattr(e, "msg") else ""
        if any(kw in msg for kw in ("was never closed", "unmatched", "invalid character", "cannot assign to", "duplicate argument", "unterminated")):
            sanitized_full_code = sanitize_code_snippet(full_code)
            sanitized_lines = sanitized_full_code.splitlines()
            err_line_idx = (e.lineno - 1) if (e.lineno and 1 <= e.lineno <= len(sanitized_lines)) else None
            if err_line_idx is not None:
                sanitized_text = sanitized_lines[err_line_idx].strip()
            else:
                raw_text = e.text.strip() if e.text else ""
                sanitized_text = redact_sensitive_line(raw_text)

            sanitized_msg = redact_sensitive_line(str(e.msg))
            issues.append({
                "tool": "syntax_checker",
                "type": "SYNTAX_ERROR",
                "severity": "HIGH",
                "file_path": file_path,
                "line_number": e.lineno or 1,
                "message": f"Python Syntax Error: {sanitized_msg}",
                "text": sanitized_text
            })

    # 2. Check for common regex logic issues (e.g., except Exception: pass, bare except)
    for idx, line in enumerate(clean_lines, start=1):
        if re.search(r"except\s*:\s*$", line) or re.search(r"except\s+Exception\s*:\s*pass", line):
            issues.append({
                "tool": "syntax_checker",
                "type": "BARE_EXCEPT",
                "severity": "MEDIUM",
                "file_path": file_path,
                "line_number": idx,
                "message": "Silencing exceptions with bare 'except:' or 'except Exception: pass' hides critical runtime failures.",
                "text": redact_sensitive_line(line.strip())
            })

    return issues


def check_javascript_syntax(code_snippet: str, file_path: str = "") -> List[Dict[str, Any]]:
    """Check common JS/TS anomalies: unclosed delimiters, missing await, loose equality."""
    issues = []
    clean_lines = [line.lstrip("+ ") for line in code_snippet.splitlines() if not line.startswith("-")]

    for idx, line in enumerate(clean_lines, start=1):
        # Loose equality check
        if re.search(r"[^!=]==[^=]", line):
            issues.append({
                "tool": "syntax_checker",
                "type": "LOOSE_EQUALITY",
                "severity": "LOW",
                "file_path": file_path,
                "line_number": idx,
                "message": "Use strict equality '===' instead of loose equality '==' to prevent unexpected type coercion.",
                "text": redact_sensitive_line(line.strip())
            })
        
        # Missing await on common async calls
        if re.search(r"(?<!await\s)(fetch|axios\.(get|post|put|delete)|prisma\.\w+\.(find|create|update|delete))\s*\(", line):
            if "await" not in line and "return" not in line and ".then" not in line:
                issues.append({
                    "tool": "syntax_checker",
                    "type": "UNHANDLED_PROMISE",
                    "severity": "HIGH",
                    "file_path": file_path,
                    "line_number": idx,
                    "message": "Async function / Promise called without 'await' or promise chaining (.then). May cause race conditions or uncaught rejections.",
                    "text": redact_sensitive_line(line.strip())
                })

    return issues


def run_syntax_and_linter_checks(code_snippet: str, file_path: str = "", language: str = "unknown") -> List[Dict[str, Any]]:
    """Dispatcher for language-specific syntax checks."""
    if language == "python" or file_path.endswith(".py"):
        return check_python_syntax(code_snippet, file_path)
    elif language in ("javascript", "typescript") or any(file_path.endswith(ext) for ext in (".js", ".ts", ".jsx", ".tsx")):
        return check_javascript_syntax(code_snippet, file_path)
    return []

