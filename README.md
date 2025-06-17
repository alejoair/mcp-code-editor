# MCP Code Editor

A FastMCP server providing powerful code editing tools including precise file modifications with diff-based operations, file creation and reading with line numbers, and more tools for code editing workflows.

## Features

- **Precise file modifications** with diff-based operations
- **File creation and reading** with line numbers
- **Project analysis** and structure inspection
- **AST (Abstract Syntax Tree)** analysis for Python code
- **Console tools** for interactive processes
- **Library indexing** for external dependencies
- **Code definition search** and navigation
- **No automatic backup files** (v0.1.10+) - cleaner file operations without .bak files

## Installation

```bash
pip install mcp-code-editor
```

## Usage

### As a standalone server
```bash
mcp-code-editor
```

### As a library
```python
from core import DiffBlock, DiffBuilder, FileModifier
from tools import ProjectAnalyzer, ASTAnalyzer

# Create and apply file modifications
modifier = FileModifier("path/to/file.py")
diff_block = DiffBlock(
    old_content="old code",
    new_content="new code",
    start_line=10,
    end_line=15
)
modifier.apply_diff(diff_block)
```

## Architecture

The project is structured as follows:

- `core/`: Core models and utilities
  - `models.py`: Data models for diff operations
- `tools/`: Tool implementations
  - `file_operations.py`: File reading, writing, and modification tools
  - `diff_tools.py`: Diff-based modification tools
  - `project_tools.py`: Project analysis and structure tools
  - `ast_analyzer.py`: AST analysis for Python code
  - `console_tools.py`: Interactive console process tools
  - `library_indexer.py`: External library indexing tools

## Requirements

- Python 3.8+
- fastmcp>=0.1.0

## Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the server: `python main.py`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
