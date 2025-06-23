"""
Apply diff tool for precise file modifications.
"""
import logging
from typing import Dict, List, Any
from ..core.models import DiffBlock, DiffBuilder, FileModifier

logger = logging.getLogger(__name__)


def apply_diff(path: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply precise file modifications using structured diff blocks.
    
    This tool makes surgical changes to files using fuzzy matching with line hints,
    making it more precise than simple search-and-replace operations.
    
    Args:
        path: The file path to modify
        blocks: List of diff blocks, each containing:
            - start_line: Starting line number (required)
            - end_line: Ending line number (optional)
            - search_content: Content to find and replace
            - replace_content: New content to replace with
    
    Returns:
        Dictionary with operation results and statistics
    """
    try:
        # Validate inputs
        if not path:
            raise ValueError("File path is required")
        if not blocks:
            raise ValueError("At least one diff block is required")
        
        # Convert dict blocks to DiffBlock objects
        diff_blocks = []
        for i, block_dict in enumerate(blocks):
            try:
                diff_block = DiffBlock.validate_block_dict(block_dict)
                diff_blocks.append(diff_block)
            except ValueError as e:
                raise ValueError(f"Invalid block {i+1}: {str(e)}")
            except Exception as e:
                raise ValueError(f"Unexpected error in block {i+1}: {str(e)}")
    
        
        logger.info(f"Processing {len(diff_blocks)} diff blocks for {path}")
        
        # Apply modifications
        modifier = FileModifier(path)
        modifier.load_file()
        
        # Store original stats
        original_lines = len(modifier.lines)
        
        # Apply all diffs
        new_content = modifier.apply_all_diffs(diff_blocks)
        new_lines = len(new_content.splitlines())
        
        # Save the file
        modifier.save_file(new_content)
        
        # Build the diff string for logging/debugging purposes
        diff_string = DiffBuilder.build_diff_string(diff_blocks)
        logger.debug(f"Applied diff:\n{diff_string}")
        
        return {
            "success": True,
            "message": f"Successfully applied {len(diff_blocks)} diff blocks to {path}",
            "file_path": str(modifier.file_path),
            "blocks_applied": len(diff_blocks),
            "original_lines": original_lines,
            "new_lines": new_lines,
            "lines_changed": new_lines - original_lines
        }
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return {
            "success": False,
            "error": "FileNotFoundError",
            "message": str(e)
        }
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {
            "success": False,
            "error": "ValidationError", 
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error applying diff: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }
