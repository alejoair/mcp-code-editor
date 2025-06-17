"""
Library indexer for external Python packages.
"""
import ast
import inspect
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LibraryIndexer:
    """Index external Python libraries for code definitions."""
    
    def __init__(self):
        self.indexed_libraries = {}
    
    def index_library(self, library_name: str, include_private: bool = False) -> Dict[str, Any]:
        """
        Index a Python library and extract all public definitions.
        
        Args:
            library_name: Name of the library to index (e.g., 'fastmcp', 'pathlib')
            include_private: Whether to include private members (starting with _)
            
        Returns:
            Dictionary with indexing results
        """
        try:
            # Import the library
            module = importlib.import_module(library_name)
            
            definitions = []
            
            # Get all public attributes
            for name in dir(module):
                # Skip private members unless requested
                if not include_private and name.startswith('_'):
                    continue
                
                try:
                    obj = getattr(module, name)
                    definition = self._analyze_object(name, obj, library_name)
                    if definition:
                        definitions.append(definition)
                except Exception as e:
                    logger.debug(f"Could not analyze {name} from {library_name}: {e}")
                    continue
            
            # Try to get source file if available
            source_info = self._get_source_info(module)
            
            result = {
                "library_name": library_name,
                "definitions": definitions,
                "total_definitions": len(definitions),
                "source_info": source_info,
                "categories": self._categorize_definitions(definitions)
            }
            
            # Cache the result
            self.indexed_libraries[library_name] = result
            
            logger.info(f"Indexed library '{library_name}': {len(definitions)} definitions")
            return result
            
        except ImportError as e:
            error_msg = f"Library '{library_name}' not found or not installed"
            logger.error(error_msg)
            return {
                "success": False,
                "error": "ImportError",
                "message": error_msg,
                "library_name": library_name
            }
        except Exception as e:
            error_msg = f"Error indexing library '{library_name}': {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": type(e).__name__,
                "message": error_msg,
                "library_name": library_name
            }
    
    def _analyze_object(self, name: str, obj: Any, library_name: str) -> Optional[Dict[str, Any]]:
        """Analyze a single object from the library."""
        try:
            obj_type = type(obj)
            
            base_info = {
                "name": name,
                "library": library_name,
                "python_type": obj_type.__name__,
                "docstring": inspect.getdoc(obj),
                "module_path": getattr(obj, '__module__', library_name)
            }
            
            # Analyze based on object type
            if inspect.isclass(obj):
                return self._analyze_class(obj, base_info)
            elif inspect.isfunction(obj) or inspect.ismethod(obj):
                return self._analyze_function(obj, base_info)
            elif inspect.ismodule(obj):
                return self._analyze_module(obj, base_info)
            elif callable(obj):
                return self._analyze_callable(obj, base_info)
            else:
                # Variable/constant
                return self._analyze_variable(obj, base_info)
                
        except Exception as e:
            logger.debug(f"Error analyzing object {name}: {e}")
            return None
    
    def _analyze_class(self, cls: type, base_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a class object."""
        info = base_info.copy()
        info.update({
            "type": "class",
            "mro": [c.__name__ for c in cls.__mro__[1:]],  # Skip self
            "methods": [],
            "properties": [],
            "class_variables": []
        })
        
        # Get source info if available
        try:
            info["source_file"] = inspect.getfile(cls)
            info["source_lines"] = inspect.getsourcelines(cls)[1]
        except (OSError, TypeError):
            pass
        
        # Analyze class members
        for member_name in dir(cls):
            if member_name.startswith('__') and member_name.endswith('__'):
                continue  # Skip magic methods for now
            
            try:
                member = getattr(cls, member_name)
                
                if inspect.ismethod(member) or inspect.isfunction(member):
                    method_info = {
                        "name": member_name,
                        "is_static": isinstance(inspect.getattr_static(cls, member_name), staticmethod),
                        "is_class_method": isinstance(inspect.getattr_static(cls, member_name), classmethod),
                        "signature": self._get_signature_safe(member),
                        "docstring": inspect.getdoc(member)
                    }
                    info["methods"].append(method_info)
                    
                elif isinstance(member, property):
                    info["properties"].append({
                        "name": member_name,
                        "docstring": inspect.getdoc(member)
                    })
                else:
                    # Class variable
                    info["class_variables"].append({
                        "name": member_name,
                        "type": type(member).__name__,
                        "value": str(member) if len(str(member)) < 100 else f"{str(member)[:100]}..."
                    })
            except Exception:
                continue
        
        return info
    
    def _analyze_function(self, func: callable, base_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a function object."""
        info = base_info.copy()
        info.update({
            "type": "function",
            "signature": self._get_signature_safe(func),
            "is_async": inspect.iscoroutinefunction(func),
            "is_generator": inspect.isgeneratorfunction(func)
        })
        
        # Get source info if available
        try:
            info["source_file"] = inspect.getfile(func)
            info["source_lines"] = inspect.getsourcelines(func)[1]
        except (OSError, TypeError):
            pass
        
        return info
    
    def _analyze_module(self, module: Any, base_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a module object."""
        info = base_info.copy()
        info.update({
            "type": "module",
            "file": getattr(module, '__file__', None),
            "package": getattr(module, '__package__', None),
            "version": getattr(module, '__version__', None)
        })
        return info
    
    def _analyze_callable(self, obj: callable, base_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a callable object (like built-in functions)."""
        info = base_info.copy()
        info.update({
            "type": "callable",
            "signature": self._get_signature_safe(obj),
            "is_builtin": inspect.isbuiltin(obj)
        })
        return info
    
    def _analyze_variable(self, obj: Any, base_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a variable/constant."""
        info = base_info.copy()
        info.update({
            "type": "variable",
            "value_type": type(obj).__name__,
            "value": str(obj) if len(str(obj)) < 200 else f"{str(obj)[:200]}...",
            "is_constant": base_info["name"].isupper()
        })
        return info
    
    def _get_signature_safe(self, obj: callable) -> Optional[str]:
        """Safely get signature of a callable."""
        try:
            return str(inspect.signature(obj))
        except (ValueError, TypeError):
            return None
    
    def _get_source_info(self, module: Any) -> Dict[str, Any]:
        """Get source file information for a module."""
        try:
            file_path = inspect.getfile(module)
            return {
                "source_file": file_path,
                "is_builtin": file_path.endswith('.so') or 'built-in' in file_path,
                "package_location": str(Path(file_path).parent) if file_path else None
            }
        except (OSError, TypeError):
            return {
                "source_file": None,
                "is_builtin": True,
                "package_location": None
            }
    
    def _categorize_definitions(self, definitions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize definitions by type."""
        categories = {}
        for definition in definitions:
            def_type = definition.get("type", "unknown")
            categories[def_type] = categories.get(def_type, 0) + 1
        return categories
    
    def search_library_definitions(self, library_name: str, query: str, 
                                 definition_type: str = "any") -> List[Dict[str, Any]]:
        """
        Search for definitions within an indexed library.
        
        Args:
            library_name: Name of the library to search in
            query: Search term
            definition_type: Type filter ("class", "function", "variable", "any")
            
        Returns:
            List of matching definitions
        """
        if library_name not in self.indexed_libraries:
            return []
        
        library_data = self.indexed_libraries[library_name]
        definitions = library_data.get("definitions", [])
        
        matches = []
        query_lower = query.lower()
        
        for definition in definitions:
            # Type filter
            if definition_type != "any" and definition.get("type") != definition_type:
                continue
            
            # Name matching
            name = definition.get("name", "").lower()
            if query_lower in name:
                # Calculate relevance score
                score = 0
                if name == query_lower:
                    score += 100
                elif name.startswith(query_lower):
                    score += 50
                else:
                    score += 10
                
                definition_with_score = definition.copy()
                definition_with_score["relevance_score"] = score
                matches.append(definition_with_score)
        
        # Sort by relevance
        matches.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return matches


# Global library indexer instance
_library_indexer = LibraryIndexer()


def index_library(library_name: str, include_private: bool = False) -> Dict[str, Any]:
    """Index a library and return the results."""
    return _library_indexer.index_library(library_name, include_private)


def search_library(library_name: str, query: str, definition_type: str = "any") -> List[Dict[str, Any]]:
    """Search for definitions in an indexed library."""
    return _library_indexer.search_library_definitions(library_name, query, definition_type)


def get_indexed_libraries() -> List[str]:
    """Get list of currently indexed libraries."""
    return list(_library_indexer.indexed_libraries.keys())


def get_library_summary(library_name: str) -> Optional[Dict[str, Any]]:
    """Get summary of an indexed library."""
    if library_name in _library_indexer.indexed_libraries:
        data = _library_indexer.indexed_libraries[library_name]
        return {
            "library_name": library_name,
            "total_definitions": data.get("total_definitions", 0),
            "categories": data.get("categories", {}),
            "source_info": data.get("source_info", {})
        }
    return None
