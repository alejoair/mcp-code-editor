"""
AST analyzer for code structure analysis and indexing.
"""
import ast
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ASTAnalyzer:
    """Analyzes Python files using AST to extract code structure."""
    
    def __init__(self):
        self.definitions = []
    
    def analyze_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Analyze a single Python file and extract all definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            definitions = []
            definitions.extend(self._extract_imports(tree, file_path))
            definitions.extend(self._extract_functions(tree, file_path))
            definitions.extend(self._extract_classes(tree, file_path))
            definitions.extend(self._extract_variables(tree, file_path))
            
            return definitions
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return []
    
    def _extract_imports(self, tree: ast.AST, file_path: Path) -> List[Dict[str, Any]]:
        """Extract import statements."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "name": alias.asname or alias.name,
                        "original_name": alias.name,
                        "type": "import",
                        "file": str(file_path),
                        "line": node.lineno,
                        "import_type": "import",
                        "module": alias.name,
                        "alias": alias.asname
                    })
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "name": alias.asname or alias.name,
                        "original_name": alias.name,
                        "type": "import", 
                        "file": str(file_path),
                        "line": node.lineno,
                        "import_type": "from",
                        "module": module,
                        "from_name": alias.name,
                        "alias": alias.asname
                    })
        
        return imports
    
    def _extract_functions(self, tree: ast.AST, file_path: Path) -> List[Dict[str, Any]]:
        """Extract function definitions."""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip nested functions for now (could be added later)
                if self._is_top_level_or_class_method(node, tree):
                    functions.append({
                        "name": node.name,
                        "type": "function",
                        "file": str(file_path),
                        "line_start": node.lineno,
                        "line_end": getattr(node, 'end_lineno', node.lineno),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "args": [arg.arg for arg in node.args.args],
                        "defaults": len(node.args.defaults),
                        "docstring": ast.get_docstring(node),
                        "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                        "returns": self._get_return_annotation(node),
                        "signature": self._build_function_signature(node)
                    })
        
        return functions
    
    def _extract_classes(self, tree: ast.AST, file_path: Path) -> List[Dict[str, Any]]:
        """Extract class definitions."""
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Get methods
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "line": item.lineno,
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "is_private": item.name.startswith('_'),
                            "is_magic": item.name.startswith('__') and item.name.endswith('__')
                        })
                
                classes.append({
                    "name": node.name,
                    "type": "class",
                    "file": str(file_path),
                    "line_start": node.lineno,
                    "line_end": getattr(node, 'end_lineno', node.lineno),
                    "docstring": ast.get_docstring(node),
                    "inheritance": [self._get_base_name(base) for base in node.bases],
                    "methods": methods,
                    "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list]
                })
        
        return classes
    
    def _extract_variables(self, tree: ast.AST, file_path: Path) -> List[Dict[str, Any]]:
        """Extract global variable assignments."""
        variables = []
        
        # Only get top-level assignments
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Simple variable assignment
                        variables.append({
                            "name": target.id,
                            "type": "variable",
                            "file": str(file_path),
                            "line": node.lineno,
                            "value_type": self._get_value_type(node.value),
                            "is_constant": target.id.isupper()
                        })
        
        return variables
    
    def _is_top_level_or_class_method(self, func_node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if function is top-level or a class method (not nested)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.Module)):
                if func_node in node.body:
                    return True
        return False
    
    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Get decorator name as string."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{self._get_attribute_chain(decorator)}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return self._get_attribute_chain(decorator.func)
        return "unknown"
    
    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Get full attribute chain like 'mcp.tool'."""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))
    
    def _get_return_annotation(self, func_node: ast.FunctionDef) -> Optional[str]:
        """Get function return type annotation."""
        if func_node.returns:
            return ast.unparse(func_node.returns) if hasattr(ast, 'unparse') else "annotated"
        return None
    
    def _build_function_signature(self, func_node: ast.FunctionDef) -> str:
        """Build a readable function signature."""
        args = []
        
        # Regular arguments
        for i, arg in enumerate(func_node.args.args):
            arg_str = arg.arg
            
            # Add type annotation if present
            if arg.annotation:
                if hasattr(ast, 'unparse'):
                    arg_str += f": {ast.unparse(arg.annotation)}"
                else:
                    arg_str += ": annotated"
            
            # Add default value if present
            default_offset = len(func_node.args.args) - len(func_node.args.defaults)
            if i >= default_offset:
                default_idx = i - default_offset
                if hasattr(ast, 'unparse'):
                    arg_str += f" = {ast.unparse(func_node.args.defaults[default_idx])}"
                else:
                    arg_str += " = default"
            
            args.append(arg_str)
        
        # Build signature
        signature = f"{func_node.name}({', '.join(args)})"
        
        # Add return type
        if func_node.returns:
            if hasattr(ast, 'unparse'):
                signature += f" -> {ast.unparse(func_node.returns)}"
            else:
                signature += " -> return_type"
        
        return signature
    
    def _get_base_name(self, base: ast.expr) -> str:
        """Get base class name."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return self._get_attribute_chain(base)
        return "unknown"
    
    def _get_value_type(self, value: ast.expr) -> str:
        """Get the type of an assigned value."""
        if isinstance(value, ast.Constant):
            return type(value.value).__name__
        elif isinstance(value, ast.List):
            return "list"
        elif isinstance(value, ast.Dict):
            return "dict"
        elif isinstance(value, ast.Set):
            return "set"
        elif isinstance(value, ast.Tuple):
            return "tuple"
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return f"call_{value.func.id}"
            return "call"
        return "unknown"


def build_ast_index(project_root: Path, file_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build AST index for all Python files in the project."""
    analyzer = ASTAnalyzer()
    all_definitions = []
    
    def _process_tree_node(node: Dict[str, Any], current_path: Path):
        if node.get("type") == "file":
            if current_path.suffix == ".py":
                definitions = analyzer.analyze_file(current_path)
                all_definitions.extend(definitions)
        
        elif node.get("type") == "directory":
            for name, child in node.get("children", {}).items():
                child_path = current_path / name
                _process_tree_node(child, child_path)
    
    _process_tree_node(file_tree, project_root)
    
    logger.info(f"AST analysis complete: {len(all_definitions)} definitions found")
    return all_definitions


def update_ast_for_file(file_path: Path, ast_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update AST index for a single modified file."""
    file_str = str(file_path)
    
    # Remove old definitions for this file
    updated_index = [d for d in ast_index if d.get("file") != file_str]
    
    # Add new definitions
    if file_path.suffix == ".py" and file_path.exists():
        analyzer = ASTAnalyzer()
        new_definitions = analyzer.analyze_file(file_path)
        updated_index.extend(new_definitions)
        
        logger.info(f"Updated AST for {file_path}: {len(new_definitions)} definitions")
    
    return updated_index
