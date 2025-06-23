"""
Core models and classes for file operations.
"""
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)


class DiffBlock(BaseModel):
    """
    Represents a single SEARCH/REPLACE block in a diff.
    
    This model validates the structure of diff blocks to ensure they contain
    all required fields with proper types.
    """
    start_line: int = Field(..., description="Starting line number for the search block (1-indexed)", gt=0)
    end_line: Optional[int] = Field(None, description="Ending line number for the search block (optional, 1-indexed)", gt=0)
    search_content: str = Field(..., description="The exact content to search for and replace", min_length=1)
    replace_content: str = Field(..., description="The new content to replace with (can be empty string for deletion)")
    
    @classmethod
    def validate_block_dict(cls, block_dict: dict) -> 'DiffBlock':
        """
        Validate a dictionary and convert it to a DiffBlock with helpful error messages.
        
        Args:
            block_dict: Dictionary containing block data
            strict_mode: If True, applies stricter validation rules
            
        Returns:
            DiffBlock instance
            
        Raises:
            ValueError: With detailed error message about what's wrong
        """
        if not isinstance(block_dict, dict):
            raise ValueError(f"Block must be a dictionary, got {type(block_dict).__name__}")
        
        required_fields = {'start_line', 'search_content', 'replace_content'}
        missing_fields = required_fields - set(block_dict.keys())
        
        if missing_fields:
            raise ValueError(
                f"Missing required fields: {', '.join(missing_fields)}. "
                f"Required format: {{\"start_line\": int, \"search_content\": str, \"replace_content\": str}}"
            )
        
        # Check for old/incorrect field names
        if 'old_content' in block_dict or 'new_content' in block_dict:
            raise ValueError(
                "Detected old field names 'old_content'/'new_content'. "
                "Please use 'search_content'/'replace_content' instead."
            )
        
        try:
            return cls(**block_dict)
        except Exception as e:
            raise ValueError(f"Invalid block structure: {str(e)}")


class DiffBuilder:
    """Builds diff strings from typed arguments."""
    
    @staticmethod
    def build_diff_string(blocks: List[DiffBlock]) -> str:
        """Build a complete diff string from DiffBlock objects."""
        diff_parts = []
        
        for block in blocks:
            diff_part = "<<<<<<< SEARCH\n"
            diff_part += f":start_line:{block.start_line}\n"
            
            if block.end_line is not None:
                diff_part += f":end_line:{block.end_line}\n"
            
            diff_part += "-------\n"
            diff_part += f"{block.search_content}\n"
            diff_part += "=======\n"
            diff_part += f"{block.replace_content}\n"
            diff_part += ">>>>>>> REPLACE"
            
            diff_parts.append(diff_part)
        
        return "\n\n".join(diff_parts)


class FileModifier:
    """Handles file modifications using diff blocks."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.lines: List[str] = []
        self.original_content = ""
        
    def load_file(self) -> None:
        """Load file content into memory."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.original_content = f.read()
            self.lines = self.original_content.splitlines(keepends=True)
    
    def find_matching_lines(self, diff_block: DiffBlock) -> tuple[int, int]:
        """Find the exact lines that match the search content using fuzzy matching."""
        search_lines = diff_block.search_content.splitlines()
        
        # Start search from the hinted line (1-indexed to 0-indexed)
        start_search_idx = max(0, diff_block.start_line - 1)
        
        # Try exact match first around the hinted area
        for i in range(max(0, start_search_idx - 2), 
                      min(len(self.lines), start_search_idx + 10)):
            
            # Check if we have enough lines for the match
            if i + len(search_lines) > len(self.lines):
                continue
                
            # Compare lines (strip whitespace for fuzzy matching)
            match = True
            for j, search_line in enumerate(search_lines):
                file_line = self.lines[i + j].rstrip('\n\r')
                if search_line.strip() != file_line.strip():
                    match = False
                    break
            
            if match:
                return i, i + len(search_lines)
        
        # If no exact match, try more fuzzy matching
        raise ValueError(
            f"Could not find matching content around line {diff_block.start_line}. "
            f"Expected content:\n{diff_block.search_content}"
        )
    
    def apply_diff_block(self, diff_block: DiffBlock) -> None:
        """Apply a single diff block to the file."""
        start_idx, end_idx = self.find_matching_lines(diff_block)
        
        # Prepare replacement lines
        replace_lines = []
        if diff_block.replace_content:
            replace_lines = [line + '\n' for line in diff_block.replace_content.splitlines()]
            # Preserve original line ending style if the last original line doesn't end with newline
            if start_idx < len(self.lines) and not self.lines[start_idx].endswith('\n'):
                if replace_lines and replace_lines[-1].endswith('\n'):
                    replace_lines[-1] = replace_lines[-1].rstrip('\n')
        
        # Replace the lines
        self.lines[start_idx:end_idx] = replace_lines
        
        logger.info(f"Applied diff block: lines {start_idx+1}-{end_idx} -> {len(replace_lines)} lines")
    
    def apply_all_diffs(self, diff_blocks: List[DiffBlock]) -> str:
        """Apply all diff blocks and return the result."""
        # Sort blocks by start_line in reverse order to avoid line number shifts
        sorted_blocks = sorted(diff_blocks, key=lambda b: b.start_line, reverse=True)
        
        for block in sorted_blocks:
            self.apply_diff_block(block)
        
        return ''.join(self.lines)
    
    def save_file(self, content: str) -> None:
        """Save the modified content back to the file."""
        # Save modified content directly without backup
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"File saved: {self.file_path}")
