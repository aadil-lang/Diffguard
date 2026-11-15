"""
Explicit Gemini Tool Declarations for DiffGuard.
Constructs official google.genai types.Tool and types.FunctionDeclaration objects.
"""

from typing import List
from google.genai import types


def get_gemini_tools() -> List[types.Tool]:
    """
    Constructs the model-facing Gemini tool declarations for on-demand diff analysis.
    Uses strict types.Schema definitions decoupled from dispatcher implementation.
    """
    hunk_decl = types.FunctionDeclaration(
        name="inspect_diff_hunk",
        description="Inspects a specific diff hunk for a modified file in the submitted patch, returning added lines, deleted lines, line bounds, and context lines.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description="Relative repository file path to inspect (e.g. services/auth.py)"
                ),
                "hunk_index": types.Schema(
                    type=types.Type.INTEGER,
                    description="Zero-based index of the hunk to inspect within the file (defaults to 0)"
                )
            },
            required=["file_path"]
        )
    )

    ctx_decl = types.FunctionDeclaration(
        name="inspect_patch_context",
        description="Retrieves line context available within the submitted patch for a specific file and line range.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "file_path": types.Schema(
                    type=types.Type.STRING,
                    description="Relative repository file path to inspect"
                ),
                "start_line": types.Schema(
                    type=types.Type.INTEGER,
                    description="Starting line number to inspect (1-based)"
                ),
                "end_line": types.Schema(
                    type=types.Type.INTEGER,
                    description="Ending line number to inspect (inclusive)"
                ),
                "line_side": types.Schema(
                    type=types.Type.STRING,
                    description="Side of diff to inspect: 'new' (added lines), 'old' (deleted lines), or 'both' (context)"
                )
            },
            required=["file_path", "start_line"]
        )
    )

    return [types.Tool(function_declarations=[hunk_decl, ctx_decl])]

