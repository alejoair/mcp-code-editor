"""
Project management tools for code editor functionality.
"""
import os
import time
import logging
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ProjectState:
    """Holds the state of the current project setup."""
    
    def __init__(self):
        self.project_root: Optional[Path] = None
        self.gitignore_rules: List[str] = []
        self.exclude_dirs: List[str] = []
        self.file_tree: Dict[str, Any] = {}
        self.last_setup: Optional[datetime] = None
        self.total_files: int = 0
        self.setup_complete: bool = False
        self.ast_index: List[Dict[str, Any]] = []
        self.ast_enabled: bool = False
        self.file_timestamps: Dict[str, float] = {}
        # Indexed libraries storage
        self.indexed_libraries: Dict[str, Dict[str, Any]] = {}

    def reset(self):
        """Reset the project state."""
        self.__init__()


class GitIgnoreParser:
    """Parser for .gitignore rules."""
    
    def __init__(self, gitignore_path: Path):
        self.rules = []
        self.load_gitignore(gitignore_path)
    
    def load_gitignore(self, gitignore_path: Path):
        """Load and parse .gitignore file."""
        if not gitignore_path.exists():
            return
        
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        self.rules.append(line)
        except Exception as e:
            logger.warning(f"Could not parse .gitignore: {e}")
    
    def should_ignore(self, path: Path, relative_to: Path) -> bool:
        """Check if a path should be ignored based on gitignore rules."""
        try:
            relative_path = path.relative_to(relative_to)
            relative_str = str(relative_path)
            
            for rule in self.rules:
                # Handle directory rules (ending with /)
                if rule.endswith('/'):
                    if path.is_dir() and fnmatch.fnmatch(relative_str, rule[:-1]):
                        return True
                    if fnmatch.fnmatch(relative_str + '/', rule):
                        return True
                else:
                    # Handle file and directory rules
                    if fnmatch.fnmatch(relative_str, rule):
                        return True
                    # Check if any parent directory matches
                    for parent in relative_path.parents:
                        if fnmatch.fnmatch(str(parent), rule):
                            return True
            
            return False
        except ValueError:
            # Path is not relative to the project root
            return False


def build_file_tree(root_path: Path, gitignore_parser: GitIgnoreParser, 
                   exclude_dirs: List[str], max_depth: int = 10) -> Dict[str, Any]:
    """Build a file tree structure with gitignore support."""
    
    def _scan_directory(dir_path: Path, current_depth: int = 0) -> Dict[str, Any]:
        if current_depth > max_depth:
            return {"type": "directory", "truncated": True}
        
        tree = {
            "type": "directory",
            "children": {},
            "file_count": 0,
            "dir_count": 0
        }
        
        try:
            items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                # Skip hidden files/dirs unless specifically included
                if item.name.startswith('.') and item.name not in ['.gitignore', '.env']:
                    continue
                
                # Check gitignore rules
                if gitignore_parser.should_ignore(item, root_path):
                    continue
                
                # Check exclude directories
                if item.is_dir() and item.name in exclude_dirs:
                    continue
                
                if item.is_dir():
                    tree["children"][item.name] = _scan_directory(item, current_depth + 1)
                    tree["dir_count"] += 1
                else:
                    tree["children"][item.name] = {
                        "type": "file",
                        "size": item.stat().st_size,
                        "extension": item.suffix.lower() if item.suffix else None
                    }
                    tree["file_count"] += 1
        
        except PermissionError:
            tree["error"] = "Permission denied"
        except Exception as e:
            tree["error"] = str(e)
        
        return tree
    
    return _scan_directory(root_path)


def get_project_summary(file_tree: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a summary of the project structure."""
    
    def _count_items(tree_node: Dict[str, Any]) -> Dict[str, int]:
        counts = {"files": 0, "directories": 0}
        extensions = {}
        
        if tree_node.get("type") == "file":
            counts["files"] = 1
            ext = tree_node.get("extension")
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1
        elif tree_node.get("type") == "directory":
            counts["directories"] = 1
            for child in tree_node.get("children", {}).values():
                child_counts = _count_items(child)
                counts["files"] += child_counts["files"]
                counts["directories"] += child_counts["directories"]
                for ext, count in child_counts.get("extensions", {}).items():
                    extensions[ext] = extensions.get(ext, 0) + count
        
        return {**counts, "extensions": extensions}
    
    return _count_items(file_tree)


def setup_code_editor(path: str) -> Dict[str, Any]:
    """
    Setup code editor by analyzing project structure and .gitignore rules.
    
    Args:
        path: The project root directory path
        
    Returns:
        Dictionary with setup results and project information
    """
    try:
        project_path = Path(path).resolve()
        
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {path}")
        
        if not project_path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        # Reset and setup project state
        state = ProjectState()
        state.project_root = project_path
        state.last_setup = datetime.now()
        
        # Default exclude directories (can be overridden by .gitignore)
        default_excludes = [
            "node_modules", ".git", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".tox", "venv", ".venv", "env", ".env",
            "dist", "build", ".next", ".nuxt", "target"
        ]
        state.exclude_dirs = default_excludes.copy()
        
        # Parse .gitignore if it exists
        gitignore_path = project_path / ".gitignore"
        gitignore_parser = GitIgnoreParser(gitignore_path)
        state.gitignore_rules = gitignore_parser.rules
        
        # Build file tree
        logger.info(f"Building file tree for project: {project_path}")
        state.file_tree = build_file_tree(project_path, gitignore_parser, state.exclude_dirs)
        
        # Generate project summary
        summary = get_project_summary(state.file_tree)
        state.total_files = summary["files"]
        state.setup_complete = True
        
        # Detect project type
        project_type = detect_project_type(project_path)
        
        logger.info(f"Project setup complete: {summary['files']} files, {summary['directories']} directories")
        
        return {
            "success": True,
            "message": f"Successfully setup code editor for project: {path}",
            "mcp_version": "mcp-code-editor v0.1.12",
            "project_root": str(project_path),
            "project_type": project_type,
            "gitignore_found": gitignore_path.exists(),
            "gitignore_rules_count": len(state.gitignore_rules),
            "exclude_dirs": state.exclude_dirs,
            "summary": {
                "total_files": summary["files"],
                "total_directories": summary["directories"],
                "file_extensions": dict(sorted(summary["extensions"].items(), 
                                             key=lambda x: x[1], reverse=True)[:10])  # Top 10 extensions
            },
            "setup_time": state.last_setup.isoformat()
        }
        
    except FileNotFoundError as e:
        logger.error(f"Project path not found: {e}")
        return {
            "success": False,
            "error": "FileNotFoundError",
            "message": str(e)
        }
    except ValueError as e:
        logger.error(f"Invalid project path: {e}")
        return {
            "success": False,
            "error": "ValueError",
            "message": str(e)
        }
    except PermissionError as e:
        logger.error(f"Permission denied accessing project: {e}")
        return {
            "success": False,
            "error": "PermissionError",
            "message": f"Permission denied: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error during setup: {e}")
        return {
            "success": False,
            "error": type(e).__name__,
            "message": str(e)
        }


def detect_project_type(project_path: Path) -> str:
    """Detect the type of project based on files present."""
    
    # Check for specific files that indicate project type
    indicators = {
        "package.json": "JavaScript/Node.js",
        "requirements.txt": "Python",
        "Pipfile": "Python (Pipenv)",
        "pyproject.toml": "Python (Modern)",
        "Cargo.toml": "Rust",
        "pom.xml": "Java (Maven)",
        "build.gradle": "Java/Kotlin (Gradle)",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "go.mod": "Go",
        ".csproj": "C#/.NET",
        "mix.exs": "Elixir",
        "deno.json": "Deno/TypeScript"
    }
    
    for file, project_type in indicators.items():
        if (project_path / file).exists():
            return project_type
    
    # Check for language-specific directories/patterns
    if (project_path / "src").exists():
        return "Source Code Project"
    elif (project_path / "docs").exists() and (project_path / "README.md").exists():
        return "Documentation Project"
    elif any(f.suffix == ".py" for f in project_path.glob("*.py")):
        return "Python Scripts"
    elif any(f.suffix in [".js", ".ts"] for f in project_path.glob("*")):
        return "JavaScript/TypeScript"
    
    return "Generic Project"


def project_files(project_state: ProjectState, 
                 filter_extensions: Optional[List[str]] = None,
                 max_depth: Optional[int] = None, 
                 format_as_tree: bool = True) -> Dict[str, Any]:
    """
    Get project files using cached setup information.
    
    Args:
        project_state: The current project state
        filter_extensions: Optional list of file extensions to filter by (e.g., [".py", ".js"])
        max_depth: Optional maximum depth to traverse  
        format_as_tree: Whether to return as tree structure or flat list
        
    Returns:
        Dictionary with project files and tree structure
    """
    if not project_state.setup_complete:
        raise ValueError("Project not setup. Please run setup_code_editor first.")
    
    def _filter_tree(tree_node: Dict[str, Any], current_depth: int = 0) -> Optional[Dict[str, Any]]:
        if max_depth is not None and current_depth > max_depth:
            return None
        
        if tree_node.get("type") == "file":
            # Filter by extension if specified
            if filter_extensions:
                ext = tree_node.get("extension")
                if ext not in filter_extensions:
                    return None
            return tree_node.copy()
        
        elif tree_node.get("type") == "directory":
            filtered_children = {}
            
            for name, child in tree_node.get("children", {}).items():
                filtered_child = _filter_tree(child, current_depth + 1)
                if filtered_child is not None:
                    filtered_children[name] = filtered_child
            
            if filtered_children or not filter_extensions:  # Keep empty dirs if no filter
                result = tree_node.copy()
                result["children"] = filtered_children
                return result
        
        return None
    
    def _flatten_tree(tree_node: Dict[str, Any], current_path: str = "") -> List[Dict[str, Any]]:
        files = []
        
        if tree_node.get("type") == "file":
            file_info = tree_node.copy()
            file_info["path"] = current_path
            files.append(file_info)
        
        elif tree_node.get("type") == "directory":
            for name, child in tree_node.get("children", {}).items():
                child_path = f"{current_path}/{name}" if current_path else name
                files.extend(_flatten_tree(child, child_path))
        
        return files
    
    # Apply filters to the tree
    filtered_tree = _filter_tree(project_state.file_tree)
    
    if filtered_tree is None:
        filtered_tree = {"type": "directory", "children": {}}
    
    # Generate summary of filtered results
    summary = get_project_summary(filtered_tree)
    
    result = {
        "success": True,
        "project_root": str(project_state.project_root),
        "last_setup": project_state.last_setup.isoformat() if project_state.last_setup else None,
        "filters_applied": {
            "extensions": filter_extensions,
            "max_depth": max_depth
        },
        "summary": {
            "total_files": summary["files"],
            "total_directories": summary["directories"],
            "file_extensions": summary["extensions"]
        }
    }
    
    if format_as_tree:
        result["file_tree"] = filtered_tree
    else:
        result["files"] = _flatten_tree(filtered_tree)
    
    return result


def setup_code_editor_with_ast(path: str, analyze_ast: bool = True) -> Dict[str, Any]:
    """
    Enhanced setup that includes AST analysis.
    
    Args:
        path: The project root directory path
        analyze_ast: Whether to build AST index
        
    Returns:
        Dictionary with setup results including AST analysis
    """
    # Run normal setup first
    result = setup_code_editor(path)
    
    if not result.get("success") or not analyze_ast:
        return result
    
    try:
        from .ast_analyzer import build_ast_index
        
        project_path = Path(path).resolve()
        
        # We need to reconstruct some state to pass to AST analyzer
        # This is a bit redundant but ensures consistency
        gitignore_path = project_path / ".gitignore"
        gitignore_parser = GitIgnoreParser(gitignore_path)
        
        default_excludes = [
            "node_modules", ".git", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".tox", "venv", ".venv", "env", ".env",
            "dist", "build", ".next", ".nuxt", "target"
        ]
        
        file_tree = build_file_tree(project_path, gitignore_parser, default_excludes)
        
        # Build AST index
        logger.info("Building AST index...")
        ast_index = build_ast_index(project_path, file_tree)
        
        # Add AST results to response
        ast_stats = {
            "functions": len([d for d in ast_index if d["type"] == "function"]),
            "classes": len([d for d in ast_index if d["type"] == "class"]),
            "imports": len([d for d in ast_index if d["type"] == "import"]),
            "variables": len([d for d in ast_index if d["type"] == "variable"]),
            "total_definitions": len(ast_index)
        }
        
        result["ast_analysis"] = ast_stats
        result["message"] += f" AST indexed: {len(ast_index)} definitions."
        
        logger.info(f"AST analysis complete: {ast_stats}")
        
        return result
        
    except Exception as e:
        logger.error(f"AST analysis failed: {e}")
        result["ast_analysis_error"] = str(e)
        return result


def search_definitions(query: str, ast_index: List[Dict[str, Any]], 
                      definition_type: str = "any", 
                      context_file: str = None) -> List[Dict[str, Any]]:
    """
    Search for definitions in the AST index.
    
    Args:
        query: Name to search for
        ast_index: The AST index to search in
        definition_type: Type filter ("function", "class", "import", "variable", "any")
        context_file: Optional file context for prioritizing results
        
    Returns:
        List of matching definitions
    """
    matches = []
    
    for definition in ast_index:
        # Type filter
        if definition_type != "any" and definition["type"] != definition_type:
            continue
        
        # Name matching (exact match or starts with)
        name = definition["name"].lower()
        query_lower = query.lower()
        
        if name == query_lower or name.startswith(query_lower):
            # Calculate relevance score
            score = 0
            
            # Exact match gets highest score
            if name == query_lower:
                score += 100
            
            # Context file match gets bonus
            if context_file and definition["file"].endswith(context_file):
                score += 50
            
            # Function/class definitions get higher priority than imports
            if definition["type"] in ["function", "class"]:
                score += 20
            
            definition_with_score = definition.copy()
            definition_with_score["relevance_score"] = score
            matches.append(definition_with_score)
    
    # Sort by relevance score (highest first)
    matches.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    return matches


def get_file_definitions(file_path: str, ast_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get all definitions from a specific file.
    
    Args:
        file_path: Path to the file
        ast_index: The AST index to search in
        
    Returns:
        List of definitions in the file
    """
    file_path = str(Path(file_path).resolve())
    
    definitions = [d for d in ast_index if d["file"] == file_path]
    
    # Sort by line number
    definitions.sort(key=lambda x: x.get("line_start", x.get("line", 0)))
    
    return definitions


def update_file_ast_index(file_path: str, ast_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Update AST index for a single file that has been modified.
    
    Args:
        file_path: Path to the modified file
        ast_index: Current AST index
        
    Returns:
        Updated AST index
    """
    try:
        from .ast_analyzer import update_ast_for_file
        return update_ast_for_file(Path(file_path), ast_index)
    except Exception as e:
        logger.error(f"Failed to update AST for {file_path}: {e}")
        return ast_index


def has_structural_changes(diff_blocks: List[Dict[str, Any]]) -> bool:
    """
    Determine if diff blocks contain structural changes that affect AST.
    
    Args:
        diff_blocks: List of diff blocks from apply_diff
        
    Returns:
        True if changes affect code structure
    """
    structural_keywords = [
        "import ", "from ", "def ", "class ", "async def",
        "@",  # decorators
        "="   # variable assignments (at line start)
    ]
    
    for block in diff_blocks:
        # Check both search and replace content
        content_to_check = [
            block.get("search_content", ""),
            block.get("replace_content", "")
        ]
        
        for content in content_to_check:
            lines = content.split('\n')
            for line in lines:
                stripped = line.strip()
                if any(stripped.startswith(kw) for kw in structural_keywords):
                    return True
    
    return False
