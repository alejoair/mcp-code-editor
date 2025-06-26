# Tools package for mcp-code-editor

from .diff_tools import apply_diff
from .file_operations import create_file, read_file_with_lines, delete_file
from .project_tools import (setup_code_editor, project_files, ProjectState, 
                           setup_code_editor_with_ast, search_definitions, 
                           get_file_definitions, update_file_ast_index, has_structural_changes)
from .ast_analyzer import ASTAnalyzer
from .dependency_analyzer import DependencyAnalyzer, enhance_apply_diff_with_dependencies
from .library_indexer import (index_library, search_library, get_indexed_libraries, 
                             get_library_summary)
from .console_tools import (start_console_process, check_console, send_to_console,
                           list_console_processes, terminate_console_process, cleanup_terminated_processes,
                           check_console_input_state)

__all__ = ['apply_diff', 'create_file', 'read_file_with_lines', 'delete_file', 
           'setup_code_editor', 'project_files', 'ProjectState',
           'setup_code_editor_with_ast', 'search_definitions', 'get_file_definitions',
           'update_file_ast_index', 'has_structural_changes', 'ASTAnalyzer',
           'DependencyAnalyzer', 'enhance_apply_diff_with_dependencies',
           'index_library', 'search_library', 'get_indexed_libraries', 'get_library_summary',
           'start_console_process', 'check_console', 'send_to_console', 'list_console_processes',
           'terminate_console_process', 'cleanup_terminated_processes', 'check_console_input_state']
