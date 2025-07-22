"""
File operations tools for creating and reading files.
"""
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_file(path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Create a new file with the specified content.
    
    Args:
        path: The file path to create
        content: The content to write to the file
        overwrite: Whether to overwrite if file already exists (default: False)
        
    Returns:
        Dictionary with creation results and file information
    """
    try:
        file_path = Path(path)
        
        # Check if file already exists
        if file_path.exists() and not overwrite:
            raise ValueError(f"File already exists: {path}. Use overwrite=True to replace it.")
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # No backup creation - backup functionality disabled
        
        # Write content to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Get file stats
        lines_count = len(content.splitlines())
        char_count = len(content)
        
        logger.info(f"Created file: {file_path} ({lines_count} lines, {char_count} characters)")
        
        result = {
            "success": True,
            "message": f"Successfully created file: {path}",
            "file_path": str(file_path),
            "lines_created": lines_count,
            "characters_written": char_count,
            "overwritten": file_path.exists() and overwrite,
            "directories_created": not file_path.parent.exists()
        }
        
        # AST update moved to server.py to avoid circular imports
            
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {
            "success": False,
            "error": "ValidationError",
            "message": str(e)
        }
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return {
            "success": False,
            "error": "PermissionError",
            "message": f"Permission denied: {str(e)}"
        }
    except OSError as e:
        logger.error(f"OS error: {e}")
        return {
            "success": False,
            "error": "OSError", 
            "message": f"OS error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error creating file: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }


def read_file_with_lines(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read a text file and return its content with line numbers.
    
    Args:
        path: The file path to read
        start_line: Optional starting line number (1-indexed, inclusive)
        end_line: Optional ending line number (1-indexed, inclusive)
        
    Returns:
        Dictionary with file content, line numbers, and metadata
    """
    try:
        file_path = Path(path)
        
        # Validate that the path is absolute
        if not file_path.is_absolute():
            raise ValueError(f"Path must be absolute, got relative path: {path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Apply line range filtering if specified
        if start_line is not None:
            start_idx = max(0, start_line - 1)  # Convert to 0-indexed
        else:
            start_idx = 0
            
        if end_line is not None:
            end_idx = min(total_lines, end_line)  # Convert to 0-indexed + 1
        else:
            end_idx = total_lines
        
        # Validate range
        if start_line is not None and (start_line < 1 or start_line > total_lines):
            raise ValueError(f"start_line {start_line} is out of range (1-{total_lines})")
        
        if end_line is not None and (end_line < 1 or end_line > total_lines):
            raise ValueError(f"end_line {end_line} is out of range (1-{total_lines})")
        
        if start_line is not None and end_line is not None and start_line > end_line:
            raise ValueError(f"start_line ({start_line}) cannot be greater than end_line ({end_line})")
        
        # Get the requested lines
        selected_lines = lines[start_idx:end_idx]
        
        # Format content with line numbers
        numbered_lines = []
        content_lines = []
        
        for i, line in enumerate(selected_lines):
            line_number = start_idx + i + 1
            line_content = line.rstrip('\n\r')  # Remove line endings for display
            numbered_lines.append(f"{line_number:4d}: {line_content}")
            content_lines.append(line_content)
        
        numbered_content = '\n'.join(numbered_lines)
        plain_content = '\n'.join(content_lines)
        
        return {
            "success": True,
            "file_path": str(file_path),
            "total_lines": total_lines,
            "displayed_lines": len(selected_lines),
            "line_range": {
                "start": start_idx + 1,
                "end": start_idx + len(selected_lines)
            },
            "content_with_numbers": numbered_content,
            "plain_content": plain_content,
            "encoding": "utf-8"
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
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error: {e}")
        return {
            "success": False,
            "error": "UnicodeDecodeError",
            "message": f"Could not decode file as UTF-8: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error reading file: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }


def delete_file(path: str, create_backup: bool = False) -> Dict[str, Any]:
    """
    Delete a file with automatic dependency analysis.
    
    Args:
        path: The file path to delete
        create_backup: DEPRECATED - backup functionality removed
        
    Returns:
        Dictionary with deletion results, dependency warnings, and affected files
    """
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        # Get file info before deletion
        file_size = file_path.stat().st_size
        
        # Dependency analysis moved to server.py to avoid circular imports
        dependency_warnings = []
        affected_files = []
        definitions_lost = []
        
        # Analysis logic moved to server.py
        
        # Eliminar el archivo (sin backup)
        file_path.unlink()
        
        logger.info(f"Deleted file: {file_path} ({file_size} bytes)")
        if dependency_warnings:
            logger.warning(f"File deletion may break {len(affected_files)} dependent files")
        
        result = {
            "success": True,
            "message": f"Successfully deleted file: {path}",
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "dependency_warnings": dependency_warnings,
            "affected_files": affected_files,
            "definitions_lost": definitions_lost,
            "breaking_change_risk": len(dependency_warnings) > 0
        }
            
        return result
        
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
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return {
            "success": False,
            "error": "PermissionError",
            "message": f"Permission denied: {str(e)}"
        }
    except OSError as e:
        logger.error(f"OS error: {e}")
        return {
            "success": False,
            "error": "OSError", 
            "message": f"OS error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error deleting file: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }
