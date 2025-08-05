# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP Code Editor is a FastMCP server providing advanced code editing tools with AST analysis, project management, and interactive console integration. The project is structured as a Python package that exposes code editing capabilities through the Model Context Protocol (MCP).

## Development Commands

### Build and Development
- **Development build**: `./dev-build.sh` (Linux/macOS) or `dev-build.bat` (Windows)
  - Creates virtual environment, installs dependencies, builds package, and validates distribution
- **Package build**: `python -m build`
- **Install dependencies**: `pip install -r requirements.txt`
- **Install development dependencies**: `pip install -e .[dev]`

### Testing
- **Integration test**: `python integration_test.py`
- **Run tests**: `pytest` (when pytest is available in dev dependencies)
- **Package validation**: `twine check dist/*`

### Package Management
- **Version bump**: Update version in both `pyproject.toml` and `mcp_code_editor/__init__.py`
- **Upload to PyPI**: `twine upload dist/*`
- **Upload to Test PyPI**: `twine upload --repository testpypi dist/*`

## Architecture

### Core Structure
- **`mcp_code_editor/server.py`**: Main FastMCP server with tool definitions and MCP protocol handling
- **`mcp_code_editor/core/`**: Core models and data structures (DiffBlock, validation models)
- **`mcp_code_editor/tools/`**: All tool implementations organized by functionality

### Tool Categories
1. **Project Management** (`project_tools.py`): Setup, file listing, project state management
2. **File Operations** (`file_operations.py`): Create, read, delete files with line number support
3. **Diff Tools** (`diff_tools.py`): Precise file modifications with search/replace blocks
4. **AST Analysis** (`ast_analyzer.py`, `ast_integration.py`): Python code structure analysis
5. **Dependency Analysis** (`dependency_analyzer.py`): Breaking change detection and impact analysis
6. **Library Integration** (`library_indexer.py`): External library indexing and search
7. **Console Tools** (`console_tools.py`): Interactive process management (Python, Node.js, shell)

### Key Components
- **ProjectState**: Manages project configuration, file indexing, and AST caching
- **ASTAnalyzer**: Handles Python code parsing and definition extraction
- **DependencyAnalyzer**: Detects breaking changes and analyzes code dependencies
- **ConsoleManager**: Manages multiple interactive processes with intelligent input detection

## Tool Usage Patterns

### Project Setup Workflow
1. Use `setup_code_editor` to analyze project structure and build AST index
2. Use `project_files` for file listings with intelligent filtering
3. Use `get_code_definition` to find function/class definitions and usage locations

### Safe Code Modification
1. Always use `apply_diff_tool` without `force=True` first to see impact analysis
2. Review dependency warnings and breaking change alerts
3. Only use `force=True` after understanding the impact
4. Use `get_code_definition` to understand affected code locations

### Console Integration
- **Python**: Start with `python -u -i` for unbuffered interactive mode
- **Node.js**: Use `node` for REPL
- **Shell commands**: Use appropriate shell (`cmd`, `powershell`, `bash`)
- Always check console state with `check_console_tool` before sending input

## Development Notes

### Dependencies
- **Core**: `fastmcp>=2.8.0` for MCP protocol implementation
- **Development**: `build`, `twine`, `pytest`, `pytest-cov` for packaging and testing
- **Code Quality**: `pylint>=3.0.0`, `pyflakes>=3.0.0` for static analysis

### File Conventions
- All tools return structured responses with metadata
- AST analysis is automatically cached for Python files
- Console processes use intelligent prompt detection to prevent accidental command execution
- File paths must be absolute when working with tools

### Security Features
- Breaking change detection prevents unsafe modifications
- Dependency impact analysis shows affected files
- Force mode requires explicit confirmation for risky changes
- Console tools prevent sending commands to background processes