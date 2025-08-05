#!/usr/bin/env python3
"""
Minimal test of apply_diff_tool to isolate the NameError
"""

from typing import List, Dict, Any
from mcp_code_editor.tools import apply_diff

def test_apply_diff_minimal(path: str, blocks: List[Dict[str, Any]]) -> dict:
    """Minimal version to test the apply_diff function"""
    print(f"Testing with path: {path}")
    print(f"Testing with blocks: {blocks}")
    
    try:
        result = apply_diff(path, blocks)
        print(f"Result: {result}")
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    path = "C:\\Users\\Usuario\\Desktop\\proyecto-mcp\\mcp-code-editor\\scratch\\test.py"
    blocks = [{"start_line": 2, "search_content": "    print(\"Hello World\")", "replace_content": "    print(\"Hello Python!\")"}]
    
    result = test_apply_diff_minimal(path, blocks)
    print("Test completed")