#!/usr/bin/env python3
"""
Debug FileModifier to see what's happening with diff application
"""

from mcp_code_editor.core.models import DiffBlock, FileModifier

def test_file_modifier():
    """Test the FileModifier process"""
    
    file_path = "C:\\Users\\Usuario\\Desktop\\proyecto-mcp\\mcp-code-editor\\scratch\\test.py"
    
    block_dict = {
        "start_line": 2, 
        "search_content": "    print(\"Hello World\")", 
        "replace_content": "    print(\"Hello Python!\")"
    }
    
    print(f"Testing with file: {file_path}")
    print(f"Testing with block: {block_dict}")
    
    try:
        # Create and validate the diff block
        diff_block = DiffBlock.validate_block_dict(block_dict)
        print(f"Diff block created: {diff_block}")
        
        # Create FileModifier and load file
        modifier = FileModifier(file_path)
        modifier.load_file()
        
        print(f"File loaded. Lines: {len(modifier.lines)}")
        for i, line in enumerate(modifier.lines, 1):
            print(f"  {i}: {repr(line)}")
        
        # Try to apply the diff
        print(f"\\nApplying diff block...")
        new_content = modifier.apply_all_diffs([diff_block])
        
        print(f"New content:\\n{new_content}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_file_modifier()