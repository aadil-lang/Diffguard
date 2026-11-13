"""
Security Scanner Tool: Detects common OWASP and CWE vulnerabilities in diff code.
"""

import re
from typing import Dict, List, Any


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
            r"""(?i)(api[_-]?key|secret|token|password|jwt[_-]?secret|private[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_\-\.]{12,})["']""",
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

