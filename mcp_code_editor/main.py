#!/usr/bin/env python3
"""
MCP Code Editor Server

A FastMCP server providing powerful code editing tools including:
- Precise file modifications with diff-based operations
- File creation and reading with line numbers
- And more tools for code editing workflows

This modular server is designed to be easily extensible.
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP


from mcp_code_editor.tools import (apply_diff, create_file, read_file_with_lines, delete_file,
                                       setup_code_editor, project_files, ProjectState,
                                       setup_code_editor_with_ast, search_definitions, get_file_definitions,
                                       update_file_ast_index, has_structural_changes,
                                       index_library, search_library, get_indexed_libraries, get_library_summary,
                                       start_console_process, check_console, send_to_console, list_console_processes,
                                       terminate_console_process, cleanup_terminated_processes)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Context for state management
from fastmcp import Context

# Create the FastMCP server
mcp = FastMCP(
    name="MCPCodeEditor",
    instructions="""
    MCP Code Editor provides powerful tools for code editing workflows:
    
    • setup_code_editor: Analyze project structure and setup intelligent file management  
    • project_files: Get project files using cached setup with filtering options
    • get_code_definition: Get definitions of functions, classes, variables from code
    • index_library: Index external Python libraries for code analysis
    • search_library: Search definitions within indexed libraries
    • apply_diff: Make precise file modifications using structured diff blocks
    • create_file: Create new files with content and backup support
    • read_file_with_lines: Read files with line numbers and range filtering
    • delete_file: Delete files with optional backup creation
    • start_console_process: Start interactive console processes (npm, python, etc.)
    • check_console: Get snapshot of console output from running processes
    • send_to_console: Send input to interactive console processes
    • list_console_processes: List and manage active console processes
    • terminate_console_process: Stop running console processes
    
    Perfect for automated code editing, refactoring, file management, and interactive development tasks.
    """
)

# Initialize project state
mcp.project_state = ProjectState()

# Register tools with the MCP server
@mcp.tool
async def apply_diff_tool(path: str, blocks: list, ctx: Context = None) -> dict:
    """Apply precise file modifications using structured diff blocks."""
    result = apply_diff(path, blocks)
    
    # Auto-update AST if enabled and changes affect structure
    if result.get("success") and ctx:
        state = getattr(ctx.fastmcp, 'project_state', None)
        if state and state.ast_enabled:
            if has_structural_changes(blocks):
                # Update AST index for the modified file
                state.ast_index = update_file_ast_index(path, state.ast_index)
                await ctx.info(f"AST index updated for {path}")
    
    return result

@mcp.tool 
def create_file_tool(path: str, content: str, overwrite: bool = False) -> dict:
    """Create a new file with the specified content."""
    return create_file(path, content, overwrite)

@mcp.tool
def read_file_with_lines_tool(path: str, start_line: int = None, end_line: int = None) -> dict:
    """Read a text file and return its content with line numbers."""
    return read_file_with_lines(path, start_line, end_line)

@mcp.tool
def delete_file_tool(path: str, create_backup: bool = True) -> dict:
    """Delete a file with optional backup creation."""
    return delete_file(path, create_backup)

@mcp.tool
async def setup_code_editor_tool(path: str, analyze_ast: bool = True, ctx: Context = None) -> dict:
    """Setup code editor by analyzing project structure, .gitignore rules, and optionally AST."""
    result = setup_code_editor_with_ast(path, analyze_ast)
    
    # If setup was successful, store the state in the server
    if result.get("success"):
        # Store the project state in the server for later use
        from tools.project_tools import ProjectState, GitIgnoreParser, build_file_tree
        from tools.ast_analyzer import build_ast_index
        from pathlib import Path
        from datetime import datetime
        
        state = ProjectState()
        state.project_root = Path(path).resolve()
        state.setup_complete = True
        state.last_setup = datetime.fromisoformat(result["setup_time"])
        
        # Rebuild the state components
        gitignore_path = state.project_root / ".gitignore"
        gitignore_parser = GitIgnoreParser(gitignore_path)
        state.gitignore_rules = gitignore_parser.rules
        
        default_excludes = [
            "node_modules", ".git", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".tox", "venv", ".venv", "env", ".env",
            "dist", "build", ".next", ".nuxt", "target"
        ]
        state.exclude_dirs = default_excludes.copy()
        state.file_tree = build_file_tree(state.project_root, gitignore_parser, state.exclude_dirs)
        state.total_files = result["summary"]["total_files"]
        
        # Build AST index if requested
        if analyze_ast and result.get("ast_analysis"):
            state.ast_index = build_ast_index(state.project_root, state.file_tree)
            state.ast_enabled = True
            await ctx.info(f"Project setup complete: {state.total_files} files, {len(state.ast_index)} definitions indexed")
        else:
            state.ast_enabled = False
            await ctx.info(f"Project setup complete: {state.total_files} files indexed (AST disabled)")
        
        # Store in server context
        ctx.fastmcp.project_state = state
    
    return result

@mcp.tool
async def project_files_tool(
    filter_extensions: list = None, 
    max_depth: int = None, 
    format_as_tree: bool = True, 
    ctx: Context = None
) -> dict:
    """Get project files using cached setup with filtering options."""
    try:
        # Get the project state from server context
        state = ctx.fastmcp.project_state
        
        if not hasattr(state, 'setup_complete') or not state.setup_complete:
            return {
                "success": False,
                "error": "ProjectNotSetup",
                "message": "Project not setup. Please run setup_code_editor_tool first."
            }
        
        # Use the project_files function with the stored state
        result = project_files(state, filter_extensions, max_depth, format_as_tree)
        
        await ctx.info(f"Retrieved project files: {result['summary']['total_files']} files")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error retrieving project files: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

@mcp.tool
async def get_code_definition(
    identifier: str,
    context_file: str = None,
    definition_type: str = "any",
    include_usage: bool = False,
    ctx: Context = None
) -> dict:
    """
    Get definitions of functions, classes, variables, and imports from the project.
    
    Args:
        identifier: Name of function/class/variable to find
        context_file: Optional file context for prioritizing results
        definition_type: Filter by type ("function", "class", "variable", "import", "any")
        include_usage: Whether to include usage examples in the project
        
    Returns:
        Dictionary with found definitions and metadata
    """
    try:
        # Get the project state from server context
        state = getattr(ctx.fastmcp, 'project_state', None)
        
        if not state or not state.setup_complete:
            return {
                "success": False,
                "error": "ProjectNotSetup",
                "message": "Project not setup. Please run setup_code_editor_tool first."
            }
        
        if not state.ast_enabled:
            return {
                "success": False,
                "error": "ASTNotEnabled",
                "message": "AST analysis not enabled. Run setup with analyze_ast=True."
            }
        
        # Search for definitions
        matches = search_definitions(
            identifier, 
            state.ast_index, 
            definition_type, 
            context_file
        )
        
        if not matches:
            return {
                "success": True,
                "found": False,
                "message": f"No definitions found for '{identifier}'",
                "identifier": identifier,
                "search_criteria": {
                    "type": definition_type,
                    "context_file": context_file
                }
            }
        
        # Prepare results
        definitions = []
        for match in matches[:10]:  # Limit to top 10 results
            definition = {
                "name": match["name"],
                "type": match["type"],
                "file": match["file"],
                "relevance_score": match.get("relevance_score", 0)
            }
            
            # Add type-specific information
            if match["type"] == "function":
                definition.update({
                    "signature": match.get("signature", ""),
                    "line_start": match.get("line_start"),
                    "line_end": match.get("line_end"),
                    "is_async": match.get("is_async", False),
                    "args": match.get("args", []),
                    "docstring": match.get("docstring"),
                    "decorators": match.get("decorators", [])
                })
            
            elif match["type"] == "class":
                definition.update({
                    "line_start": match.get("line_start"),
                    "line_end": match.get("line_end"),
                    "methods": match.get("methods", []),
                    "inheritance": match.get("inheritance", []),
                    "docstring": match.get("docstring"),
                    "decorators": match.get("decorators", [])
                })
            
            elif match["type"] == "import":
                definition.update({
                    "line": match.get("line"),
                    "module": match.get("module"),
                    "import_type": match.get("import_type"),
                    "from_name": match.get("from_name"),
                    "alias": match.get("alias")
                })
            
            elif match["type"] == "variable":
                definition.update({
                    "line": match.get("line"),
                    "value_type": match.get("value_type"),
                    "is_constant": match.get("is_constant", False)
                })
            
            definitions.append(definition)
        
        result = {
            "success": True,
            "found": True,
            "identifier": identifier,
            "total_matches": len(matches),
            "definitions": definitions,
            "search_criteria": {
                "type": definition_type,
                "context_file": context_file
            }
        }
        
        await ctx.info(f"Found {len(definitions)} definitions for '{identifier}'")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error searching for definition '{identifier}': {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "identifier": identifier
        }

def test_new_function():
    """This is a test function added via apply_diff."""
    return "Hello from new function!"

@mcp.tool
async def index_library_tool(
    library_name: str,
    include_private: bool = False,
    ctx: Context = None
) -> dict:
    """
    Index an external Python library for code analysis.
    
    Args:
        library_name: Name of the library to index (e.g., 'fastmcp', 'pathlib')
        include_private: Whether to include private members (starting with _)
        
    Returns:
        Dictionary with indexing results and library information
    """
    try:
        await ctx.info(f"Indexing library '{library_name}'...")
        
        result = index_library(library_name, include_private)
        
        if result.get("success", True):  # Assume success if not explicitly failed
            await ctx.info(f"Library '{library_name}' indexed successfully: {result.get('total_definitions', 0)} definitions")
        else:
            await ctx.error(f"Failed to index library '{library_name}': {result.get('message', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error indexing library '{library_name}': {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "library_name": library_name
        }

@mcp.tool
async def search_library_tool(
    library_name: str,
    query: str,
    definition_type: str = "any",
    ctx: Context = None
) -> dict:
    """
    Search for definitions within an indexed library.
    
    Args:
        library_name: Name of the library to search in
        query: Search term (function/class/variable name)
        definition_type: Filter by type ("class", "function", "variable", "any")
        
    Returns:
        Dictionary with search results
    """
    try:
        # Check if library is indexed
        indexed_libs = get_indexed_libraries()
        if library_name not in indexed_libs:
            return {
                "success": False,
                "error": "LibraryNotIndexed",
                "message": f"Library '{library_name}' not indexed. Run index_library_tool first.",
                "indexed_libraries": indexed_libs
            }
        
        # Search for definitions
        matches = search_library(library_name, query, definition_type)
        
        if not matches:
            return {
                "success": True,
                "found": False,
                "message": f"No definitions found for '{query}' in library '{library_name}'",
                "library_name": library_name,
                "query": query,
                "search_criteria": {
                    "type": definition_type
                }
            }
        
        # Prepare results (limit to top 10)
        definitions = matches[:10]
        
        result = {
            "success": True,
            "found": True,
            "library_name": library_name,
            "query": query,
            "total_matches": len(matches),
            "definitions": definitions,
            "search_criteria": {
                "type": definition_type
            }
        }
        
        await ctx.info(f"Found {len(definitions)} definitions for '{query}' in '{library_name}'")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error searching library '{library_name}': {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "library_name": library_name,
            "query": query
        }

@mcp.tool
async def list_indexed_libraries_tool(ctx: Context = None) -> dict:
    """
    List all currently indexed libraries with summary information.
    
    Returns:
        Dictionary with list of indexed libraries and their summaries
    """
    try:
        indexed_libs = get_indexed_libraries()
        
        if not indexed_libs:
            return {
                "success": True,
                "message": "No libraries indexed yet. Use index_library_tool to index libraries.",
                "indexed_libraries": [],
                "total_libraries": 0
            }
        
        # Get summary for each library
        libraries_info = []
        for lib_name in indexed_libs:
            summary = get_library_summary(lib_name)
            if summary:
                libraries_info.append(summary)
        
        result = {
            "success": True,
            "message": f"Found {len(indexed_libs)} indexed libraries",
            "indexed_libraries": indexed_libs,
            "total_libraries": len(indexed_libs),
            "libraries_info": libraries_info
        }
        
        await ctx.info(f"Listed {len(indexed_libs)} indexed libraries")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error listing indexed libraries: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

@mcp.tool
async def start_console_process_tool(
    command: str,
    working_dir: str = None,
    env_vars: dict = None,
    name: str = None,
    shell: bool = False,
    ctx: Context = None
) -> dict:
    """
    Start an interactive console process.
    
    Args:
        command: The command to execute
        working_dir: Working directory for the process (optional)
        env_vars: Additional environment variables (optional)
        name: Descriptive name for the process (optional)
        shell: Whether to use shell for execution (optional)
        
    Returns:
        Dictionary with process information and status
    """
    try:
        await ctx.info(f"Starting console process: {command}")
        
        result = start_console_process(command, working_dir, env_vars, name, shell)
        
        if result.get("success"):
            await ctx.info(f"Console process started: {result.get('process_id')} - {result.get('name')}")
        else:
            await ctx.error(f"Failed to start console process: {result.get('message')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error starting console process: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

@mcp.tool
async def check_console_tool(
    process_id: str,
    lines: int = 50,
    include_timestamps: bool = False,
    filter_type: str = "all",
    since_timestamp: float = None,
    raw_output: bool = False,
    ctx: Context = None
) -> dict:
    """
    Get a snapshot of console output from an interactive process.
    
    Note: This function includes a 10-second delay before execution.
    
    Args:
        process_id: ID of the process to check
        lines: Number of recent lines to retrieve
        include_timestamps: Whether to include timestamps in output
        filter_type: Filter output by type ("all", "stdout", "stderr", "input")
        since_timestamp: Only return output after this timestamp
        raw_output: Return raw terminal output or processed
        
    Returns:
        Dictionary with console snapshot and metadata
    """
    import asyncio
    
    try:
        # Wait 10 seconds before executing
        await ctx.info(f"Waiting 10 seconds before checking console {process_id}...")
        await asyncio.sleep(10)
        
        result = check_console(process_id, lines, include_timestamps, 
                             filter_type, since_timestamp, raw_output)
        
        if result.get("success"):
            await ctx.info(f"Retrieved console snapshot for {process_id}: {result.get('displayed_lines')} lines")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error checking console {process_id}: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

@mcp.tool
async def send_to_console_tool(
    process_id: str,
    input_text: str,
    send_enter: bool = True,
    wait_for_response: bool = False,
    response_timeout: int = 5,
    expect_pattern: str = None,
    clear_input_echo: bool = True,
    ctx: Context = None
) -> dict:
    """
    Send input to an interactive console process.
    
    Args:
        process_id: ID of the process to send input to
        input_text: Text to send to the process
        send_enter: Whether to append newline to input
        wait_for_response: Whether to wait for response before returning
        response_timeout: Timeout in seconds for waiting for response
        expect_pattern: Regex pattern to wait for in response
        clear_input_echo: Whether to filter input echo from output
        
    Returns:
        Dictionary with send status and response if waited
    """
    try:
        await ctx.info(f"Sending input to console {process_id}: {input_text}")
        
        result = send_to_console(process_id, input_text, send_enter, 
                               wait_for_response, response_timeout, 
                               expect_pattern, clear_input_echo)
        
        if result.get("success"):
            if result.get("response_received"):
                await ctx.info(f"Input sent and response received from {process_id}")
            else:
                await ctx.info(f"Input sent to {process_id}")
        else:
            await ctx.error(f"Failed to send input to {process_id}: {result.get('message')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error sending input to console {process_id}: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

@mcp.tool
async def list_console_processes_tool(
    include_terminated: bool = False,
    summary_only: bool = True,
    ctx: Context = None
) -> dict:
    """
    List all console processes.
    
    Args:
        include_terminated: Whether to include terminated processes
        summary_only: Return only summary or full details
        
    Returns:
        Dictionary with list of processes and their status
    """
    try:
        result = list_console_processes(include_terminated, summary_only)
        
        if result.get("success"):
            await ctx.info(f"Listed console processes: {result.get('active_processes')} active, {result.get('terminated_processes')} terminated")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error listing console processes: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

@mcp.tool
async def terminate_console_process_tool(
    process_id: str,
    force: bool = False,
    timeout: int = 10,
    ctx: Context = None
) -> dict:
    """
    Terminate a console process.
    
    Args:
        process_id: ID of the process to terminate
        force: Whether to force kill the process
        timeout: Timeout before force killing
        
    Returns:
        Dictionary with termination status
    """
    try:
        await ctx.info(f"Terminating console process {process_id} (force={force})")
        
        result = terminate_console_process(process_id, force, timeout)
        
        if result.get("success"):
            await ctx.info(f"Console process {process_id} {result.get('action')}")
        else:
            await ctx.error(f"Failed to terminate {process_id}: {result.get('message')}")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error terminating console process {process_id}: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "process_id": process_id
        }

@mcp.tool
async def cleanup_terminated_processes_tool(ctx: Context = None) -> dict:
    """
    Clean up terminated processes from the registry.
    
    Returns:
        Dictionary with cleanup results
    """
    try:
        result = cleanup_terminated_processes()
        
        if result.get("success"):
            await ctx.info(f"Cleaned up {len(result.get('cleaned_processes', []))} terminated processes")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error cleaning up processes: {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }

def main():
    """Main entry point for the MCP Code Editor Server."""
    logger.info("Starting MCP Code Editor Server...")
    
    # Run the server with STDIO transport (default)
    mcp.run()
    
    # For HTTP transport, uncomment:
    # mcp.run(transport="streamable-http", host="127.0.0.1", port=9000)

if __name__ == "__main__":
    main()
