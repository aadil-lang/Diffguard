"""
Tool Registry: Connects agent tools to Gemini function calling definitions
and provides batch execution for agent reasoning.
"""

from typing import Dict, List, Any
from app.models.diff_models import ParsedDiff
from app.tools.security_scanner import scan_security_issues
from app.tools.syntax_checker import run_syntax_and_linter_checks
from app.tools.complexity_analyzer import analyze_complexity
from app.tools.test_requirement_analyzer import analyze_test_coverage


# Gemini Function Declarations schemas
TOOL_DECLARATIONS = [
    {
        "name": "scan_security_vulnerabilities",
        "description": "Scans code snippet for SQL injection, hardcoded secrets, command injection, path traversal, and OWASP Top 10 vulnerabilities.",
        "parameters": {
            "type": "object",
            "properties": {
                "code_snippet": {
                    "type": "string",
                    "description": "The modified code lines or hunk to inspect for security flaws."
                },
                "file_path": {
                    "type": "string",
                    "description": "The path of the file being checked."
                }
            },
            "required": ["code_snippet"]
        }
    },
    {
        "name": "verify_syntax_and_lint",
        "description": "Runs AST parsing and checks for syntax errors, missing awaits on async operations, unclosed constructs, and dangerous bare excepts.",
        "parameters": {
            "type": "object",
            "properties": {
                "code_snippet": {
                    "type": "string",
                    "description": "The source code snippet to parse."
                },
                "file_path": {
                    "type": "string",
                    "description": "The file path to determine language and context."
                },
                "language": {
                    "type": "string",
                    "description": "The programming language (e.g., 'python', 'javascript', 'typescript')."
                }
            },
            "required": ["code_snippet"]
        }
    },
    {
        "name": "measure_code_complexity",
        "description": "Computes cyclomatic complexity, maximum nesting depth, and code churn to evaluate maintainability and cognitive load.",
        "parameters": {
            "type": "object",
            "properties": {
                "code_snippet": {
                    "type": "string",
                    "description": "The code block to calculate complexity metrics for."
                },
                "file_path": {
                    "type": "string",
                    "description": "Target file path."
                }
            },
            "required": ["code_snippet"]
        }
    }
]


def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Executes a single agent tool call by name with validated arguments."""
    if tool_name == "scan_security_vulnerabilities":
        return scan_security_issues(
            code_snippet=arguments.get("code_snippet", ""),
            file_path=arguments.get("file_path", "")
        )
    elif tool_name == "verify_syntax_and_lint":
        return run_syntax_and_linter_checks(
            code_snippet=arguments.get("code_snippet", ""),
            file_path=arguments.get("file_path", ""),
            language=arguments.get("language", "unknown")
        )
    elif tool_name == "measure_code_complexity":
        return analyze_complexity(
            code_snippet=arguments.get("code_snippet", ""),
            file_path=arguments.get("file_path", "")
        )
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def execute_all_analysis_tools(parsed_diff: ParsedDiff) -> Dict[str, Any]:
    """
    Executes all static analysis and validation tools on a parsed diff.
    Aggregates empirical evidence for the AI agent workflow.
    """
    security_results = []
    syntax_results = []
    complexity_results = []

    for file_obj in parsed_diff.files:
        for hunk in file_obj.hunks:
            snippet = hunk.raw_hunk
            
            # Security scan
            sec_issues = scan_security_issues(snippet, file_obj.target_file)
            if sec_issues:
                # Adjust line numbers relative to hunk target start
                for s in sec_issues:
                    s["adjusted_line"] = hunk.target_start + (s["line_number"] - 1)
                security_results.extend(sec_issues)

            # Syntax and linting check
            syn_issues = run_syntax_and_linter_checks(
                code_snippet=snippet,
                file_path=file_obj.target_file,
                language=file_obj.language
            )
            if syn_issues:
                for syn in syn_issues:
                    syn["adjusted_line"] = hunk.target_start + (syn.get("line_number", 1) - 1)
                syntax_results.extend(syn_issues)

            # Complexity check
            comp_res = analyze_complexity(snippet, file_obj.target_file)
            if comp_res.get("warning"):
                complexity_results.append(comp_res)

    # Test coverage analysis
    test_coverage_results = analyze_test_coverage(parsed_diff)

    return {
        "security_findings": security_results,
        "syntax_findings": syntax_results,
        "complexity_findings": complexity_results,
        "test_coverage_findings": test_coverage_results
    }

