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
from typing import List, Dict, Any
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
logging.basicConfig(level=logging.WARNING)
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
    
    🖥️ CONSOLE INTEGRATION (with intelligent input detection):
    • start_console_process: Start interactive console processes
      BEST PRACTICES: Use 'python -u -i' for Python, 'node' for Node.js, 'cmd' for Windows
    • check_console: Get snapshot of console output (requires wait_seconds parameter)
    • send_to_console: Send input with smart detection - automatically prevents sending
      commands to background processes. Use force_send=True for control signals (Ctrl+C)
    • list_console_processes: List and manage active console processes
    • terminate_console_process: Stop running console processes
    
    Perfect for automated code editing, intelligent refactoring, dependency analysis, and interactive development.
    """
)

# Initialize project state
mcp.project_state = ProjectState()

# Helper functions for library integration
def _enhance_dependency_analysis_with_libraries(analysis, indexed_libraries, file_path):
    """
    Enriquece el análisis de dependencias con información de librerías indexadas.
    
    Args:
        analysis: Análisis de dependencias existente
        indexed_libraries: Dict de librerías indexadas desde project_state
        file_path: Ruta del archivo siendo modificado
        
    Returns:
        Dict con información adicional sobre librerías indexadas
    """
    enhanced_info = {
        "library_context": [],
        "available_alternatives": [],
        "library_compatibility_warnings": []
    }
    
    # Analizar funciones modificadas para detectar uso de librerías indexadas
    for func_name in analysis.get("modified_functions", []):
        for lib_name, lib_data in indexed_libraries.items():
            # Buscar si la función usa métodos de esta librería
            library_usage = _check_function_uses_library(func_name, lib_name, lib_data, file_path)
            if library_usage:
                enhanced_info["library_context"].append({
                    "function": func_name,
                    "library": lib_name,
                    "methods_used": library_usage,
                    "compatibility_note": f"Function uses methods from indexed library '{lib_name}'"
                })
    
    return enhanced_info

def _check_function_uses_library(func_name, lib_name, lib_data, file_path):
    """
    Verifica si una función usa métodos de una librería específica.
    Implementación básica - puede ser mejorada con análisis AST más profundo.
    """
    try:
        # Leer el archivo y buscar patrones de uso de la librería
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar imports de la librería
        import_patterns = [
            f"from {lib_name} import",
            f"import {lib_name}",
        ]
        
        for pattern in import_patterns:
            if pattern in content:
                return [f"Uses {lib_name}"]
        
        return []
    except:
        return []

# Register tools with the MCP server
@mcp.tool
async def apply_diff_tool(path: str, blocks: List[Dict[str, Any]], force: bool = False, ctx: Context = None) -> dict:
    """
    ✏️ INTELLIGENT FILE MODIFICATION: Apply precise changes with automatic dependency analysis.
    
    🛡️ SMART PROTECTION: This tool automatically blocks critical breaking changes that could
    damage your codebase. Use force=True only when you're certain about the changes.
    
    This tool combines precise diff application with advanced AST analysis to:
    • Detect breaking changes before they happen
    • BLOCK critical changes that could break multiple files
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
        force: ADVANCED - Skip breaking change protection and apply changes anyway.
               By default, critical breaking changes are blocked to prevent accidental
               damage to the codebase. Set to True to bypass this safety mechanism.
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
    # Initialize dependency analysis with default structure (always available)
    dependency_analysis = {
        "modified_functions": [],
        "modified_classes": [],
        "affected_callers": [],
        "breaking_changes": [],
        "files_to_review": [],
        "impact_level": "low",
        "recommendations": []
    }
    impact_summary = {
        "modified_items": 0,
        "affected_files": 0,
        "breaking_changes": 0,
        "impact_level": "low"
    }
    
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
                # Note: In exception handler, we can't use await ctx.error() since we may not have async context
                # Keep traditional logging for critical error handling
                ast_warnings.append({
                    "type": "ast_analysis_error",
                    "severity": "medium", 
                    "message": f"AST analysis failed: {str(e)}"
                })
                # Initialize empty dependency analysis on error, but still include it
                dependency_analysis = {
                    "error": str(e),
                    "modified_functions": [],
                    "modified_classes": [],
                    "affected_callers": [],
                    "breaking_changes": [],
                    "files_to_review": [],
                    "impact_level": "unknown",
                    "recommendations": ["⚠️ Dependency analysis failed - manual review recommended"]
                }
                impact_summary = {
                    "error": str(e),
                    "modified_items": 0,
                    "affected_files": 0,
                    "breaking_changes": 0,
                    "impact_level": "unknown"
                }
    
    # Check for critical breaking changes (unless forced)
    if not force and dependency_analysis.get("breaking_changes"):
        breaking_changes = dependency_analysis["breaking_changes"]
        impact_level = dependency_analysis.get("impact_level", "low")
        
        # Block critical and high-impact breaking changes
        if impact_level in ["critical", "high"]:
            affected_files = dependency_analysis.get("files_to_review", [])
            return {
                "success": False,
                "error": "BREAKING_CHANGES_DETECTED",
                "message": f"Breaking changes detected affecting {len(affected_files)} files. This could break existing functionality.",
                "breaking_changes": breaking_changes,
                "affected_files": affected_files,
                    "impact_level": impact_level,
                    "ast_warnings": ast_warnings,
                    "dependency_analysis": dependency_analysis,
                    "suggested_action": "Fix the breaking changes first, or use force=True to apply anyway (not recommended).",
                    "recommendation": "Review and update all affected callers before applying this change."
                }
    
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
            
            # NUEVO: Agregar análisis de dependencias (SIEMPRE incluir, incluso si está vacío)
            result["dependency_analysis"] = dependency_analysis if 'dependency_analysis' in locals() else {}
            result["impact_summary"] = impact_summary if 'impact_summary' in locals() else {}
            
            # Log para debugging usando FastMCP Context
            if ctx:
                if not dependency_analysis or dependency_analysis.get("error"):
                    await ctx.warning(f"Dependency analysis missing or failed for {path}: {dependency_analysis.get('error', 'No dependency_analysis variable')}")
                else:
                    await ctx.info(f"Dependency analysis successful for {path}: {len(dependency_analysis.get('affected_callers', []))} callers affected")
            
            # NUEVO: Verificar si hay librerías indexadas disponibles para análisis mejorado
            state = getattr(mcp, 'project_state', None)
            if state and state.indexed_libraries:
                # Enriquecer el análisis con información de librerías indexadas
                enhanced_analysis = _enhance_dependency_analysis_with_libraries(
                    dependency_analysis, 
                    state.indexed_libraries,
                    path
                )
                dependency_analysis.update(enhanced_analysis)
                result["dependency_analysis"] = dependency_analysis
            
            # Provide clear guidance to LLM with dependency information
            impact_level = dependency_analysis.get("impact_level", "low")
            files_to_review = dependency_analysis.get("files_to_review", [])
            breaking_changes = dependency_analysis.get("breaking_changes", [])
            
            # Agregar información de librerías indexadas a las recomendaciones
            if dependency_analysis.get("library_context"):
                ast_recommendations.append("📚 LIBRARY CONTEXT: Modified functions use indexed libraries")
                for lib_info in dependency_analysis["library_context"]:
                    ast_recommendations.append(f"  • {lib_info['function']} uses {lib_info['library']}")
            
            # Mostrar warnings de análisis estático si existen
            static_warnings = dependency_analysis.get("static_warnings", [])
            if static_warnings:
                result["static_analysis"] = {
                    "warnings_found": len(static_warnings),
                    "warnings": static_warnings[:10],  # Limitar a 10 para no saturar
                    "tools_used": list(set(w.get("tool", "unknown") for w in static_warnings))
                }
                
                # Agregar a recomendaciones
                error_count = sum(1 for w in static_warnings if w.get("severity") == "error")
                if error_count > 0:
                    ast_recommendations.insert(0, f"🚨 STATIC ANALYSIS: {error_count} errors found - fix before applying")
                    ast_recommendations.insert(1, f"🔍 Check: {', '.join(w['message'][:50] + '...' if len(w['message']) > 50 else w['message'] for w in static_warnings[:3])}")
            
            # Actualizar suggested_next_action con contexto de librerías
            library_context_summary = ""
            if dependency_analysis.get("library_context"):
                library_context_summary = f" Functions use {len(dependency_analysis['library_context'])} indexed libraries."
            
            if breaking_changes and impact_level in ["critical", "high"]:
                result["suggested_next_action"] = f"🚨 BREAKING CHANGES APPLIED: Immediately test {len(files_to_review)} affected files: {', '.join(files_to_review[:3])}{'...' if len(files_to_review) > 3 else ''}{library_context_summary}"
            elif ast_warnings and any(w.get("severity") == "high" for w in ast_warnings):
                result["suggested_next_action"] = f"⚠️ HIGH RISK CHANGES APPLIED: Test immediately - breaking changes detected.{library_context_summary}"
            elif impact_level == "high" or (impact_level == "medium" and files_to_review):
                result["suggested_next_action"] = f"📋 MEDIUM IMPACT APPLIED: Verify {len(files_to_review)} affected files: {', '.join(files_to_review[:2])}{'...' if len(files_to_review) > 2 else ''}{library_context_summary}"
            elif ast_warnings and any(w.get("severity") == "medium" for w in ast_warnings):
                result["suggested_next_action"] = f"✅ CHANGES APPLIED: Use get_code_definition to verify affected functions still work correctly.{library_context_summary}"
            elif files_to_review:
                result["suggested_next_action"] = f"✅ CHANGES APPLIED: {len(files_to_review)} files may be affected, but changes appear safe.{library_context_summary}"
            elif ast_warnings:
                result["suggested_next_action"] = f"✅ Changes applied successfully. AST analysis shows low risk.{library_context_summary}"
            else:
                result["suggested_next_action"] = f"✅ Changes applied successfully. No issues detected.{library_context_summary}"
    
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
        path: Absolute file path to read (relative paths not supported)
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

def _filter_library_warnings(warnings, indexed_libraries):
    """
    Filtra advertencias sobre definiciones que están disponibles en librerías indexadas.
    
    Args:
        warnings: Lista de advertencias de dependencias
        indexed_libraries: Dict de librerías indexadas
        
    Returns:
        Dict con warnings filtradas y alternativas disponibles
    """
    filtered_warnings = []
    alternatives = []
    
    for warning in warnings:
        definition_name = warning.get("definition", "")
        
        # Verificar si esta definición está disponible en alguna librería indexada
        available_in_library = _find_definition_in_libraries(definition_name, indexed_libraries)
        
        if available_in_library:
            # No agregar la advertencia, pero registrar la alternativa
            alternatives.append({
                "definition": definition_name,
                "available_in": available_in_library,
                "original_warning": warning,
                "replacement_suggestion": f"'{definition_name}' is available in indexed library '{available_in_library}'"
            })
        else:
            # Mantener la advertencia original
            filtered_warnings.append(warning)
    
    return {
        "warnings": filtered_warnings,
        "alternatives": alternatives
    }

def _find_definition_in_libraries(definition_name, indexed_libraries):
    """
    Busca si una definición está disponible en las librerías indexadas.
    
    Args:
        definition_name: Nombre de la definición a buscar
        indexed_libraries: Dict de librerías indexadas
        
    Returns:
        Nombre de la librería donde está disponible, o None
    """
    for lib_name, lib_data in indexed_libraries.items():
        if "definitions" in lib_data:
            for lib_def in lib_data["definitions"]:
                if lib_def.get("name") == definition_name:
                    return lib_name
    return None

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
    
    # NUEVO: Filtrar advertencias sobre definiciones que están disponibles en librerías indexadas
    state = getattr(mcp, 'project_state', None)
    if state and state.indexed_libraries:
        filtered_warnings = _filter_library_warnings(dependency_warnings, state.indexed_libraries)
        dependency_warnings = filtered_warnings["warnings"]
        library_alternatives = filtered_warnings["alternatives"]
    else:
        library_alternatives = []
    
    # Ejecutar eliminación
    result = delete_file(path, create_backup)
    
    # Agregar análisis de dependencias al resultado
    if result.get("success"):
        result["dependency_warnings"] = dependency_warnings
        result["affected_files"] = affected_files
        result["definitions_lost"] = definitions_lost
        result["breaking_change_risk"] = len(dependency_warnings) > 0
        result["library_alternatives"] = library_alternatives
        
        # Si hay alternativas de librerías, actualizar el mensaje
        if library_alternatives:
            alt_count = len(library_alternatives)
            original_message = result.get("message", "")
            result["message"] = f"{original_message} Note: {alt_count} definitions are available in indexed libraries."
            
            # Agregar detalles de alternativas
            result["library_availability"] = [
                f"{alt['definition']} -> available in {alt['available_in']}" 
                for alt in library_alternatives
            ]
        
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
    Encuentra dónde se usa un identificador en el código mediante análisis AST real.
    
    CORREGIDO: Ahora analiza el código fuente real de los archivos en lugar de solo metadatos.
    
    Args:
        identifier: Nombre del identificador a buscar
        ast_index: Índice AST completo del proyecto
        definition_files: Archivos donde se define el identificador (para excluir)
        
    Returns:
        Lista de ubicaciones donde se usa el identificador
    """
    import ast
    from pathlib import Path
    
    usage_locations = []
    processed_files = set()
    
    # Normalizar archivos de definición para comparación
    normalized_def_files = set()
    for def_file in definition_files:
        try:
            normalized_def_files.add(str(Path(def_file).resolve()).replace('\\', '/'))
        except (OSError, ValueError):
            normalized_def_files.add(def_file)
    
    # Obtener lista única de archivos para analizar
    files_to_analyze = set()
    for definition in ast_index:
        file_path = definition.get("file", "")
        if file_path:
            files_to_analyze.add(file_path)
    
    # Funciones auxiliares para análisis AST (copiadas de dependency_analyzer.py)
    def _is_function_call(node: ast.Call, function_name: str) -> bool:
        """Verifica si un nodo Call es una llamada a la función especificada."""
        if isinstance(node.func, ast.Name):
            return node.func.id == function_name
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr == function_name
        return False
    
    def _imports_function(node: ast.ImportFrom, function_name: str) -> bool:
        """Verifica si un import incluye la función especificada."""
        if node.names:
            for alias in node.names:
                if alias.name == function_name or alias.asname == function_name:
                    return True
        return False
    
    def _get_surrounding_context(content: str, line_number: int, context_lines: int = 1) -> str:
        """Obtiene el contexto alrededor de una línea específica."""
        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context_lines_content = lines[start:end]
        return ' | '.join(context_lines_content).strip()
    
    # Analizar cada archivo con AST real
    for file_path in files_to_analyze:
        try:
            # Normalizar archivo actual
            try:
                normalized_file = str(Path(file_path).resolve()).replace('\\', '/')
            except (OSError, ValueError):
                normalized_file = file_path
            
            # Skip archivos donde está definido el identificador
            if normalized_file in normalized_def_files:
                continue
                
            # Skip archivos ya procesados
            if normalized_file in processed_files:
                continue
                
            processed_files.add(normalized_file)
            
            # NUEVO: Leer y analizar el código fuente real
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Buscar usos del identificador en el AST
            for node in ast.walk(tree):
                # Buscar llamadas de función
                if isinstance(node, ast.Call):
                    if _is_function_call(node, identifier):
                        usage_locations.append({
                            "file": file_path,
                            "line": node.lineno,
                            "context_name": "function_call",
                            "context_type": "call",
                            "usage_context": _get_surrounding_context(content, node.lineno),
                            "confidence": "high"
                        })
                
                # Buscar imports
                elif isinstance(node, ast.ImportFrom):
                    if _imports_function(node, identifier):
                        usage_locations.append({
                            "file": file_path,
                            "line": node.lineno,
                            "context_name": "import",
                            "context_type": "import",
                            "usage_context": f"Import: {identifier}",
                            "confidence": "high"
                        })
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == identifier or alias.asname == identifier:
                            usage_locations.append({
                                "file": file_path,
                                "line": node.lineno,
                                "context_name": "import",
                                "context_type": "import",
                                "usage_context": f"Import: {identifier}",
                                "confidence": "high"
                            })
                
                # Buscar referencias por nombre
                elif isinstance(node, ast.Name) and node.id == identifier:
                    usage_locations.append({
                        "file": file_path,
                        "line": node.lineno,
                        "context_name": "name_reference",
                        "context_type": "name",
                        "usage_context": _get_surrounding_context(content, node.lineno),
                        "confidence": "medium"
                    })
                
                # Buscar referencias por atributo (ej: pyautogui.position)
                elif isinstance(node, ast.Attribute) and node.attr == identifier:
                    usage_locations.append({
                        "file": file_path,
                        "line": node.lineno,
                        "context_name": "attribute_reference",
                        "context_type": "attribute",
                        "usage_context": _get_surrounding_context(content, node.lineno),
                        "confidence": "high"
                    })
        
        except Exception as e:
            # Log error pero continuar procesando otros archivos
            logging.warning(f"Error analyzing {file_path} for usage of '{identifier}': {e}")
            continue
    
    # Eliminar duplicados basados en archivo + línea
    seen = set()
    unique_usages = []
    for usage in usage_locations:
        key = (usage["file"], usage["line"])
        if key not in seen:
            seen.add(key)
            unique_usages.append(usage)
    
    # Ordenar por archivo y línea
    unique_usages.sort(key=lambda x: (x["file"], x["line"]))
    
    # Limitar resultados para evitar spam
    return unique_usages[:50]  # Top 50 usos (aumentado desde 20)


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
        
        # Search for definitions in project AST
        matches = search_definitions(
            identifier, 
            state.ast_index, 
            definition_type, 
            context_file
        )
        
        # NUEVO: Also search in indexed libraries
        library_matches = []
        for lib_name, lib_data in state.indexed_libraries.items():
            if "definitions" in lib_data:
                for lib_def in lib_data["definitions"]:
                    if definition_type != "any" and lib_def.get("type") != definition_type:
                        continue
                    
                    name = lib_def.get("name", "").lower()
                    identifier_lower = identifier.lower()
                    
                    if identifier_lower in name:
                        # Calculate relevance score
                        score = 0
                        if name == identifier_lower:
                            score = 100
                        elif name.startswith(identifier_lower):
                            score = 50
                        else:
                            score = 10
                        
                        # Add library context
                        lib_match = lib_def.copy()
                        lib_match["relevance_score"] = score
                        lib_match["source"] = "external_library"
                        lib_match["library_name"] = lib_name
                        library_matches.append(lib_match)
        
        # Sort library matches by relevance
        library_matches.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Combine project and library matches (prioritize project matches)
        all_matches = matches + library_matches[:5]  # Limit library matches to 5
        
        if not all_matches:
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
        for match in all_matches[:10]:  # Limit to top 10 results from both sources
            definition = {
                "name": match["name"],
                "type": match["type"],
                "file": match.get("file", match.get("library_name", "")),
                "relevance_score": match.get("relevance_score", 0)
            }
            
            # Add source information (project vs library)
            if match.get("source") == "external_library":
                definition["source"] = "external_library"
                definition["library_name"] = match.get("library_name")
                definition["module_path"] = match.get("module_path")
            else:
                definition["source"] = "project"
            
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
            "total_matches": len(all_matches),
            "project_matches": len(matches),
            "library_matches": len(library_matches),
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
        
        # Get project state to store indexed libraries
        state = getattr(mcp, 'project_state', None)
        if not state:
            await ctx.error("Project state not initialized. Run setup_code_editor_tool first.")
            return {
                "success": False,
                "error": "ProjectNotSetup",
                "message": "Project state not initialized. Run setup_code_editor_tool first."
            }
        
        result = index_library(library_name, include_private)
        
        if result.get("success", True):  # Assume success if not explicitly failed
            # Store in project state instead of isolated storage
            state.indexed_libraries[library_name] = result
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
        # Get project state to access indexed libraries
        state = getattr(mcp, 'project_state', None)
        if not state:
            return {
                "success": False,
                "error": "ProjectNotSetup",
                "message": "Project state not initialized. Run setup_code_editor_tool first."
            }
        
        # Check if library is indexed in project state
        if library_name not in state.indexed_libraries:
            return {
                "success": False,
                "error": "LibraryNotIndexed",
                "message": f"Library '{library_name}' not indexed. Run index_library_tool first.",
                "indexed_libraries": list(state.indexed_libraries.keys())
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
        # Get project state to access indexed libraries
        state = getattr(mcp, 'project_state', None)
        if not state:
            return {
                "success": False,
                "error": "ProjectNotSetup",
                "message": "Project state not initialized. Run setup_code_editor_tool first."
            }
        
        indexed_libs = list(state.indexed_libraries.keys())
        
        if not indexed_libs:
            return {
                "success": True,
                "message": "No libraries indexed yet. Use index_library_tool to index libraries.",
                "indexed_libraries": [],
                "total_libraries": 0
            }
        
        # Get summary for each library from project state
        libraries_info = []
        for lib_name in indexed_libs:
            library_data = state.indexed_libraries.get(lib_name)
            if library_data:
                summary = {
                    "library_name": lib_name,
                    "total_definitions": library_data.get("total_definitions", 0),
                    "categories": library_data.get("categories", {}),
                    "source_info": library_data.get("source_info", {})
                }
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
    
    RECOMMENDED COMMANDS for best compatibility:
    - Python interactive: Use 'python -u -i' (unbuffered + interactive mode)
    - Node.js REPL: Use 'node' (works out of the box)
    - Command Prompt: Use 'cmd' (Windows) or 'bash' (Unix)
    - PowerShell: Use 'powershell' (Windows)
    
    TROUBLESHOOTING:
    - If Python doesn't show output: Add '-u -i' flags
    - If process seems frozen: Check if it's waiting for input vs running
    - Use send_to_console with force_send=True for background processes
    
    Args:
        command: The command to execute (see recommended commands above)
        working_dir: Working directory for the process (optional). 
                    If provided, the command will execute from this directory.
                    If not provided, uses the terminal's default directory.
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
    force_send: bool = False,
    ctx: Context = None
) -> dict:
    """
    Send input to an interactive console process with intelligent input detection.
    
    SMART BEHAVIOR: This tool automatically detects if the process is currently
    awaiting user input (interactive prompt like >>>, $, >) vs running in background
    (servers, long tasks). If the process is NOT awaiting input, it will return an
    error instead of sending a command that would be ignored.
    
    Examples:
    - python (shows >>> prompt) -> Commands are sent normally
    - python -m http.server 8000 (serving) -> Error returned, suggests using force_send
    - cmd (shows prompt) -> Commands are sent normally
    - ping google.com (running) -> Error returned unless force_send=True
    
    Args:
        process_id: ID of the process to send input to
        input_text: Text to send to the process
        send_enter: Whether to append newline to input
        wait_for_response: Whether to wait for response before returning
        response_timeout: Timeout in seconds for waiting for response
        expect_pattern: Regex pattern to wait for in response
        clear_input_echo: Whether to filter input echo from output
        force_send: ADVANCED - Skip smart detection and force send input even if process
                   may not be awaiting input. By default, the tool intelligently detects
                   if the process is waiting for input (interactive prompt) vs running in
                   background (servers, long tasks) to prevent sending useless commands.
                   Set to True to bypass this protection when you need to send control
                   signals (Ctrl+C), interrupt processes, or handle special cases.
        
    Returns:
        Dictionary with send status and response if waited
    """
    try:
        await ctx.info(f"Sending input to console {process_id}: {input_text}")
        
        result = send_to_console(process_id, input_text, send_enter, 
                               wait_for_response, response_timeout, 
                               expect_pattern, clear_input_echo, force_send)
        
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
