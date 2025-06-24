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
from typing import List, Dict
from fastmcp import FastMCP
from pathlib import Path


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
    MCP Code Editor v0.1.12 - Advanced code editing tools with intelligent AST analysis:
    
    🔧 PROJECT MANAGEMENT:
    • setup_code_editor: Analyze project structure, build AST index, and setup intelligent file management
    • project_files: Get project files using cached setup with filtering options
    
    🔍 CODE ANALYSIS (AST-powered):
    • get_code_definition: Find definitions AND usage locations of functions/classes/variables
      - Shows where items are defined and where they're used throughout the codebase
      - Includes usage context, confidence scores, and impact analysis
      - Essential for refactoring and dependency analysis
    • read_file_with_lines: Read files with line numbers + AST metadata for Python files
      - Shows function/class counts and suggests next actions
    
    📚 LIBRARY INTEGRATION:
    • index_library: Index external Python libraries for code analysis
    • search_library: Search definitions within indexed libraries
    
    ✏️ FILE OPERATIONS:
    • apply_diff: Make precise file modifications with automatic dependency impact analysis
      - Detects breaking changes, affected callers, and provides safety recommendations
    • create_file: Create new files with content and backup support
    • delete_file: Delete files with optional backup creation
    
    🖥️ CONSOLE INTEGRATION:
    • start_console_process: Start interactive console processes (npm, python, etc.)
    • check_console: Get snapshot of console output (requires wait_seconds parameter)
    • send_to_console: Send input to interactive console processes
    • list_console_processes: List and manage active console processes
    • terminate_console_process: Stop running console processes
    
    Perfect for automated code editing, intelligent refactoring, dependency analysis, and interactive development.
    """
)

# Initialize project state
mcp.project_state = ProjectState()

# Register tools with the MCP server
@mcp.tool
async def apply_diff_tool(path: str, blocks: list, ctx: Context = None) -> dict:
    """
    ✏️ INTELLIGENT FILE MODIFICATION: Apply precise changes with automatic dependency analysis.
    
    This tool combines precise diff application with advanced AST analysis to:
    • Detect breaking changes before they happen
    • Identify affected functions and callers automatically  
    • Provide safety recommendations and impact warnings
    • Suggest files to review after modifications
    
    Each block in the list must be a dictionary with the following structure:
    {
        "start_line": int,              # Required: Starting line number (1-indexed)
        "end_line": int,                # Optional: Ending line number  
        "search_content": str,          # Required: Exact content to find
        "replace_content": str          # Required: Content to replace with
    }
    
    Example:
    [
        {
            "start_line": 10,
            "end_line": 12,
            "search_content": "def calculate_total(items, tax_rate):",
            "replace_content": "def calculate_total(items):"
        }
    ]
    
    Args:
        path: File path to modify
        blocks: List of diff block dictionaries (see structure above)
        ctx: MCP context (optional)
        
    Returns:
        Dictionary with operation results, dependency analysis, and safety recommendations:
        - success: Whether the operation completed
        - ast_warnings: List of potential issues detected
        - dependency_analysis: Impact analysis including affected callers
        - suggested_next_action: Contextual guidance based on impact level
        
    Note: Content matching uses fuzzy whitespace matching but requires exact text.
    """
    # AST-powered pre-analysis if enabled
    ast_warnings = []
    ast_recommendations = []
    dependency_analysis = {}
    impact_summary = {}
    
    # Get state from context or directly from mcp server
    state = None
    if ctx:
        state = getattr(mcp, 'project_state', None)
    else:
        # Fallback: try to get state directly from mcp server
        state = getattr(mcp, 'project_state', None)
    
    if state and state.ast_enabled and hasattr(state, 'ast_index'):
            try:
                from mcp_code_editor.tools.ast_integration import enhance_apply_diff_with_ast
                pre_analysis = enhance_apply_diff_with_ast(path, blocks, state.ast_index)
                
                # Collect warnings and recommendations for the response
                ast_warnings = pre_analysis.get("warnings", [])
                ast_recommendations = pre_analysis.get("recommendations", [])
                
                # NUEVO: Análisis de dependencias automático
                from mcp_code_editor.tools.dependency_analyzer import enhance_apply_diff_with_dependencies
                dependency_result = enhance_apply_diff_with_dependencies(path, blocks, state.ast_index)
                
                dependency_analysis = dependency_result.get("dependency_analysis", {})
                impact_summary = dependency_result.get("impact_summary", {})
                
                # Agregar información de dependencias a las advertencias
                if dependency_analysis.get("breaking_changes"):
                    for breaking_change in dependency_analysis["breaking_changes"]:
                        ast_warnings.append({
                            "type": "breaking_change",
                            "severity": breaking_change.get("severity", "high"),
                            "message": f"Breaking change in {breaking_change['function']}: {breaking_change['change_type']}",
                            "affected_files": breaking_change.get("files_affected", []),
                            "affected_callers": breaking_change.get("affected_callers", 0)
                        })
                
                # Agregar recomendaciones de dependencias
                if dependency_analysis.get("recommendations"):
                    ast_recommendations.extend(dependency_analysis["recommendations"])
                
                # Check if we should proceed - solo bloquear errores de sintaxis
                should_proceed = pre_analysis.get("should_proceed", True)
                ast_analysis = pre_analysis.get("ast_analysis", {})
                error_type = ast_analysis.get("error_type")
                
                # Solo bloquear errores de sintaxis, no errores de análisis
                if not should_proceed and error_type == "syntax":
                    return {
                        "success": False,
                        "error": "SYNTAX_ERROR",
                        "message": f"Syntax error in modified code: {ast_analysis.get('error', 'Unknown syntax error')}",
                        "ast_warnings": ast_warnings,
                        "ast_recommendations": ast_recommendations,
                        "suggested_action": "Fix the syntax error before applying the diff."
                    }
                elif not should_proceed:
                    # Para otros tipos de problemas, agregar warning pero continuar
                    ast_warnings.append({
                        "type": "analysis_concern", 
                        "severity": "medium",
                        "message": f"Analysis detected issues: {ast_analysis.get('error', 'Unknown issue')}"
                    })
                    
            except Exception as e:
                ast_warnings.append({
                    "type": "ast_analysis_error",
                    "severity": "low", 
                    "message": f"AST analysis failed: {str(e)}"
                })
                # Initialize empty dependency analysis on error
                dependency_analysis = {}
                impact_summary = {}
    
    # Apply the diff
    result = apply_diff(path, blocks)
    
    # Enhance result with AST information for LLM decision making
    if result.get("success"):
        # Update AST if needed
        if ctx:
            state = getattr(mcp, 'project_state', None)
            if state and state.ast_enabled and has_structural_changes(blocks):
                state.ast_index = update_file_ast_index(path, state.ast_index)
        
        # Add AST insights to successful result (ALWAYS when AST is enabled)
        if ctx and getattr(mcp, 'project_state', None) and getattr(mcp.project_state, 'ast_enabled', False):
            result["ast_warnings"] = ast_warnings
            result["ast_recommendations"] = ast_recommendations
            result["ast_enabled"] = True  # Confirm AST is working
            
            # NUEVO: Agregar análisis de dependencias
            if dependency_analysis:
                result["dependency_analysis"] = dependency_analysis
                result["impact_summary"] = impact_summary
            
            # Provide clear guidance to LLM with dependency information
            impact_level = dependency_analysis.get("impact_level", "low")
            files_to_review = dependency_analysis.get("files_to_review", [])
            breaking_changes = dependency_analysis.get("breaking_changes", [])
            
            if breaking_changes and impact_level in ["critical", "high"]:
                result["suggested_next_action"] = f"🚨 CRITICAL: Breaking changes detected affecting {len(files_to_review)} files. Review: {', '.join(files_to_review[:3])}{'...' if len(files_to_review) > 3 else ''}"
            elif ast_warnings and any(w.get("severity") == "high" for w in ast_warnings):
                result["suggested_next_action"] = "HIGH PRIORITY: Test the changes immediately as breaking changes were detected."
            elif impact_level == "high" or (impact_level == "medium" and files_to_review):
                result["suggested_next_action"] = f"📋 MEDIUM IMPACT: Review {len(files_to_review)} affected files: {', '.join(files_to_review[:2])}{'...' if len(files_to_review) > 2 else ''}"
            elif ast_warnings and any(w.get("severity") == "medium" for w in ast_warnings):
                result["suggested_next_action"] = "RECOMMENDED: Use get_code_definition to verify affected functions still work correctly."
            elif files_to_review:
                result["suggested_next_action"] = f"✅ LOW IMPACT: {len(files_to_review)} files may be affected, but changes appear safe."
            elif ast_warnings:
                result["suggested_next_action"] = "Changes applied successfully. AST analysis shows low risk."
            else:
                result["suggested_next_action"] = "Changes applied successfully. No issues detected."
    
    return result

@mcp.tool 
def create_file_tool(path: str, content: str, overwrite: bool = False) -> dict:
    """Create a new file with the specified content."""
    result = create_file(path, content, overwrite)
    
    # NUEVO: Actualizar AST automáticamente para archivos Python
    if result.get("success") and path.endswith(".py"):
        try:
            state = getattr(mcp, 'project_state', None)
            if state and state.ast_enabled and hasattr(state, 'ast_index'):
                from mcp_code_editor.tools.ast_analyzer import ASTAnalyzer
                analyzer = ASTAnalyzer()
                file_analysis = analyzer.analyze_file(Path(path))
                
                # Agregar nuevas definiciones al índice
                if file_analysis and isinstance(file_analysis, list):
                    state.ast_index.extend(file_analysis)
                    result["ast_updated"] = True
                    result["new_definitions"] = len(file_analysis)
                    logger.info(f"Updated AST index with {len(file_analysis)} new definitions from {path}")
                else:
                    result["ast_updated"] = False
                    result["new_definitions"] = 0
        except Exception as e:
            logger.warning(f"Failed to update AST for {path}: {e}")
            result["ast_update_error"] = str(e)
    
    return result

@mcp.tool
async def read_file_with_lines_tool(path: str, start_line: int = None, end_line: int = None, ctx: Context = None) -> dict:
    """
    📝 Read files with line numbers + intelligent AST analysis for Python files.
    
    For Python files, automatically provides:
    • Function and class counts from AST analysis
    • Import summaries and definitions overview
    • Contextual suggestions for next actions
    • Enhanced metadata for code navigation
    
    Args:
        path: File path to read
        start_line: Optional starting line number (1-indexed)
        end_line: Optional ending line number (inclusive)
        
    Returns:
        File content with line numbers, plus ast_info and suggested_next_action for Python files
    """
    result = read_file_with_lines(path, start_line, end_line)
    
    # Enhance Python files with AST information if available
    if result.get("success") and path.endswith('.py') and ctx:
        state = getattr(mcp, 'project_state', None)
        # Enhanced AST integration for Python files
        if state and state.ast_enabled and hasattr(state, 'ast_index'):
            # Find definitions in this file with multiple fallback strategies
            from pathlib import Path
            file_definitions = []
            
            # Strategy 1: Try normalized absolute paths (convert to forward slashes)
            try:
                normalized_path = str(Path(path).resolve()).replace('\\', '/')
                for d in state.ast_index:
                    try:
                        d_file = str(Path(d.get('file', '')).resolve()).replace('\\', '/') if d.get('file') else ''
                        if d_file == normalized_path:
                            file_definitions.append(d)
                    except (OSError, ValueError):
                        pass
            except (OSError, ValueError):
                pass
            
            # Strategy 2: Direct string comparison if no matches
            if not file_definitions:
                file_definitions = [d for d in state.ast_index if d.get('file') == path]
            
            # Strategy 3: Compare by filename only if still no matches
            if not file_definitions:
                try:
                    filename = Path(path).name
                    for d in state.ast_index:
                        try:
                            d_filename = Path(d.get('file', '')).name if d.get('file') else ''
                            if d_filename == filename:
                                file_definitions.append(d)
                        except (OSError, ValueError):
                            pass
                except (OSError, ValueError):
                    pass
            # Always add ast_info for Python files when AST is enabled, even if empty
            result["ast_info"] = {
                "definitions_found": len(file_definitions),
                "functions": [d["name"] for d in file_definitions if d.get("type") == "function"],
                "classes": [d["name"] for d in file_definitions if d.get("type") == "class"],
                "imports": [d["name"] for d in file_definitions if d.get("type") == "import"][:10]  # Limit to first 10
            }
            if file_definitions:
                result["suggested_next_action"] = f"This Python file contains {len(file_definitions)} definitions. Use get_code_definition to explore specific functions or classes."
            else:
                result["suggested_next_action"] = "This Python file has no definitions indexed. The file might be empty or contain only comments/docstrings."
    
    return result

@mcp.tool
def delete_file_tool(path: str, create_backup: bool = False) -> dict:
    """Delete a file with automatic dependency analysis and warnings."""
    
    # NUEVO: Análisis de dependencias antes de eliminar
    dependency_warnings = []
    affected_files = []
    definitions_lost = []
    
    if path.endswith(".py"):
        try:
            state = getattr(mcp, 'project_state', None)
            if state and state.ast_enabled and hasattr(state, 'ast_index'):
                from mcp_code_editor.tools.dependency_analyzer import DependencyAnalyzer
                
                # Encontrar definiciones en el archivo a eliminar
                file_definitions = [d for d in state.ast_index if d.get('file') == path]
                definitions_lost = [d.get('name', 'unknown') for d in file_definitions]
                
                if file_definitions:
                    analyzer = DependencyAnalyzer(state.ast_index)
                    
                    # Analizar cada definición que se perderá
                    for definition in file_definitions:
                        def_name = definition.get('name', '')
                        if def_name:
                            # Buscar qué archivos usan esta definición
                            callers = analyzer._find_affected_callers(path, [def_name])
                            
                            for caller in callers:
                                caller_file = caller.get('file', '')
                                if caller_file and caller_file not in affected_files:
                                    affected_files.append(caller_file)
                                
                                dependency_warnings.append({
                                    "type": "lost_definition",
                                    "severity": "high",
                                    "definition": def_name,
                                    "definition_type": definition.get('type', 'unknown'),
                                    "used_in": caller_file,
                                    "caller": caller.get('caller_name', 'unknown'),
                                    "message": f"Definition '{def_name}' used in {caller_file} will be lost"
                                })
        except Exception as e:
            logger.warning(f"Failed to analyze dependencies for {path}: {e}")
            dependency_warnings.append({
                "type": "analysis_error",
                "severity": "medium", 
                "message": f"Could not analyze dependencies: {str(e)}"
            })
    
    # Ejecutar eliminación
    result = delete_file(path, create_backup)
    
    # Agregar análisis de dependencias al resultado
    if result.get("success"):
        result["dependency_warnings"] = dependency_warnings
        result["affected_files"] = affected_files
        result["definitions_lost"] = definitions_lost
        result["breaking_change_risk"] = len(dependency_warnings) > 0
        
        # Actualizar AST eliminando definiciones del archivo
        if path.endswith(".py"):
            try:
                state = getattr(mcp, 'project_state', None)
                if state and state.ast_enabled and hasattr(state, 'ast_index'):
                    original_count = len(state.ast_index)
                    state.ast_index = [d for d in state.ast_index if d.get('file') != path]
                    removed_count = original_count - len(state.ast_index)
                    if removed_count > 0:
                        logger.info(f"Removed {removed_count} definitions from AST index for {path}")
            except Exception as e:
                logger.warning(f"Failed to update AST index after deleting {path}: {e}")
    
    return result

@mcp.tool
async def setup_code_editor_tool(path: str, analyze_ast: bool = True, ctx: Context = None) -> dict:
    """Setup code editor by analyzing project structure, .gitignore rules, and optionally AST."""
    result = setup_code_editor_with_ast(path, analyze_ast)
    
    # If setup was successful, store the state in the server
    if result.get("success"):
        # Store the project state in the server for later use
        from mcp_code_editor.tools.project_tools import ProjectState, GitIgnoreParser, build_file_tree
        from mcp_code_editor.tools.ast_analyzer import build_ast_index
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
        
        # Store in server instance (persists across all tool calls)
        mcp.project_state = state
    
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
        state = getattr(mcp, 'project_state', None)
        
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

def _find_identifier_usage(identifier: str, ast_index: List[Dict], definition_files: List[str]) -> List[Dict]:
    """
    Encuentra dónde se usa un identificador en el código.
    
    Args:
        identifier: Nombre del identificador a buscar
        ast_index: Índice AST completo del proyecto
        definition_files: Archivos donde se define el identificador (para excluir)
        
    Returns:
        Lista de ubicaciones donde se usa el identificador
    """
    usage_locations = []
    
    # Normalizar archivos de definición para comparación
    from pathlib import Path
    normalized_def_files = set()
    for def_file in definition_files:
        try:
            normalized_def_files.add(str(Path(def_file).resolve()).replace('\\', '/'))
        except (OSError, ValueError):
            normalized_def_files.add(def_file)
    
    # Buscar usos en todo el AST index
    for definition in ast_index:
        def_file = definition.get("file", "")
        
        # Normalizar archivo actual
        try:
            normalized_file = str(Path(def_file).resolve()).replace('\\', '/')
        except (OSError, ValueError):
            normalized_file = def_file
        
        # Skip archivos donde está definido el identificador
        if normalized_file in normalized_def_files:
            continue
        
        # Buscar referencias en diferentes tipos de definiciones
        def_type = definition.get("type", "")
        def_name = definition.get("name", "")
        signature = definition.get("signature", "")
        
        # Análisis básico: buscar el identificador en signatures y contenido
        found_usage = False
        usage_context = ""
        
        if def_type == "function":
            # Buscar en la firma de la función (parámetros, llamadas)
            if identifier in signature and def_name != identifier:
                found_usage = True
                usage_context = f"Used in function signature: {signature}"
        
        elif def_type == "class":
            # Buscar en métodos de la clase
            methods = definition.get("methods", [])
            for method in methods:
                method_info = method if isinstance(method, dict) else {"name": str(method)}
                if identifier in str(method_info):
                    found_usage = True
                    usage_context = f"Used in class {def_name} method {method_info.get('name', 'unknown')}"
                    break
        
        elif def_type == "import":
            # Buscar si importa el identificador
            module = definition.get("module", "")
            from_name = definition.get("from_name", "")
            if identifier in module or identifier in from_name:
                found_usage = True
                usage_context = f"Imported: {from_name or module}"
        
        # Si encontramos uso, agregarlo a la lista
        if found_usage:
            usage_locations.append({
                "file": def_file,
                "line": definition.get("line_start", definition.get("line")),
                "context_name": def_name,
                "context_type": def_type,
                "usage_context": usage_context,
                "confidence": "medium"  # Análisis básico = confianza media
            })
    
    # Limitar resultados para evitar spam
    return usage_locations[:20]  # Top 20 usos


@mcp.tool
async def get_code_definition(
    identifier: str,
    context_file: str = None,
    definition_type: str = "any",
    include_usage: bool = False,
    ctx: Context = None
) -> dict:
    """
    🔍 ADVANCED CODE ANALYSIS: Find definitions AND usage locations of any identifier.
    
    This tool provides comprehensive analysis of code elements including:
    - WHERE items are defined (functions, classes, variables, imports)
    - WHERE and HOW they are used throughout the codebase  
    - Usage context and confidence scoring
    - Impact analysis for refactoring decisions
    
    Essential for:
    • Understanding code dependencies before making changes
    • Finding all locations that will be affected by modifications
    • Refactoring with confidence
    • Code exploration and navigation
    
    Args:
        identifier: Name of function/class/variable to find (e.g., "calculate_total")
        context_file: Optional file path to prioritize results from specific file
        definition_type: Filter by type - "function", "class", "variable", "import", or "any"
        include_usage: Set to True to always include usage analysis (default: auto-enabled when definitions found)
        
    Returns:
        Dictionary containing:
        - definitions: List of where the identifier is defined
        - usage_locations: List of where the identifier is used/called  
        - total_usages: Count of usage locations
        - suggested_next_action: Contextual guidance for next steps
        - Detailed metadata for each definition and usage
        
    Example Response:
        {
            "definitions": [{"name": "calculate_total", "type": "function", "file": "calc.py", ...}],
            "usage_locations": [{"file": "order.py", "context": "Called in process_order", ...}],
            "total_usages": 3,
            "suggested_next_action": "Found 1 function 'calculate_total' in calc.py. Used in 3 locations..."
        }
    """
    try:
        # Get the project state from server instance
        state = getattr(mcp, 'project_state', None)
        
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
            # No definitions found, but still search for usages if requested
            usage_locations = []
            if include_usage:
                usage_locations = _find_identifier_usage(identifier, state.ast_index, [])
            
            return {
                "success": True,
                "found": False,
                "message": f"No definitions found for '{identifier}'",
                "identifier": identifier,
                "usage_locations": usage_locations,
                "total_usages": len(usage_locations),
                "suggested_next_action": f"No definitions found for '{identifier}'. Found {len(usage_locations)} potential usages." if usage_locations else f"No definitions or usages found for '{identifier}'. Check spelling or search with definition_type='any' for broader results.",
                "search_criteria": {
                    "type": definition_type,
                    "context_file": context_file,
                    "include_usage": include_usage
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
        
        # NUEVO: Buscar usos/referencias del identificador si se solicita o hay definiciones
        usage_locations = []
        if include_usage or definitions:
            usage_locations = _find_identifier_usage(identifier, state.ast_index, [d["file"] for d in definitions])
        
        result = {
            "success": True,
            "found": True,
            "identifier": identifier,
            "total_matches": len(matches),
            "definitions": definitions,
            "usage_locations": usage_locations,
            "total_usages": len(usage_locations),
            "search_criteria": {
                "type": definition_type,
                "context_file": context_file,
                "include_usage": include_usage
            }
        }
        
        # Add actionable insights for LLM with usage information
        usage_summary = f" Used in {len(usage_locations)} locations." if usage_locations else " No usages found."
        
        if len(definitions) == 1:
            def_info = definitions[0]
            result["suggested_next_action"] = f"Found 1 {def_info['type']} '{identifier}' in {def_info['file']}.{usage_summary} Use read_file_with_lines_tool to see the implementation or apply_diff_tool to modify it."
        elif len(definitions) > 1:
            result["suggested_next_action"] = f"Found {len(definitions)} definitions for '{identifier}'.{usage_summary} Review each location before making changes to ensure you modify the correct one."
        
        # All processing complete
        
        return result
        
    except Exception as e:
        await ctx.error(f"Error searching for definition '{identifier}': {str(e)}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e),
            "identifier": identifier
        }


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
    wait_seconds: int,
    lines: int = 50,
    include_timestamps: bool = False,
    filter_type: str = "all",
    since_timestamp: float = None,
    raw_output: bool = False,
    ctx: Context = None
) -> dict:
    """
    Get a snapshot of console output from an interactive process.
    
    Args:
        process_id: ID of the process to check
        wait_seconds: Number of seconds to wait before checking console (required)
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
        # Wait specified seconds before executing
        await ctx.info(f"Waiting {wait_seconds} seconds before checking console {process_id}...")
        await asyncio.sleep(wait_seconds)
        
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
