#!/usr/bin/env python3
"""
Entry point script for MCP Code Editor.
This script handles the import path issues when run via uvx.
"""

def main():
    """Main entry point that handles import issues."""
    import sys
    import os
    from pathlib import Path
    
    # Get the package directory (where this cli.py file is located)
    package_dir = Path(__file__).parent
    
    # Get the parent directory (where mcp_code_editor package is located)
    parent_dir = package_dir.parent
    
    # Add parent directory to path first
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    # Also add the package directory itself
    if str(package_dir) not in sys.path:
        sys.path.insert(0, str(package_dir))
    
    # Now import and run the main function
    try:
        # Try direct import first (when run as a script)
        from main import main as main_func
        main_func()
    except ImportError:
        # Fallback: try package import
        try:
            from mcp_code_editor.main import main as main_func
            main_func()
        except ImportError as e:
            print(f"Error importing MCP Code Editor: {e}")
            print("Please ensure the package is properly installed.")
            print(f"Package directory: {package_dir}")
            print(f"Parent directory: {parent_dir}")
            print(f"Python path: {sys.path}")
            sys.exit(1)

if __name__ == "__main__":
    main()
