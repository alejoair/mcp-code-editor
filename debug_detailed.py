#!/usr/bin/env python3
"""
Detailed debug of the diff block validation and application
"""

from mcp_code_editor.core.models import DiffBlock

def test_block_validation():
    """Test the block validation process"""
    
    block_dict = {
        "start_line": 2, 
        "search_content": "    print(\"Hello World\")", 
        "replace_content": "    print(\"Hello Python!\")"
    }
    
    print(f"Testing block_dict: {block_dict}")
    
    try:
        # Test validation
        diff_block = DiffBlock.validate_block_dict(block_dict)
        print(f"OK Validation successful: {diff_block}")
        
        # Test the actual diff block properties
        print(f"Start line: {diff_block.start_line}")
        print(f"Search content: {repr(diff_block.search_content)}")
        print(f"Replace content: {repr(diff_block.replace_content)}")
        
        return diff_block
        
    except Exception as e:
        print(f"ERROR Validation failed: {e}")
        return None

if __name__ == "__main__":
    test_block_validation()