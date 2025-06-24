"""
Enhanced AST integration for existing tools.

This module provides AST-powered enhancements for apply_diff_tool and other tools
to make them more intelligent and safe.
"""
import ast
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ASTDiffAnalyzer:
    """Analyzes diffs using AST to provide intelligent insights."""
    
    def __init__(self, ast_index: Dict[str, Any]):
        self.ast_index = ast_index
    
    def analyze_diff_impact(self, file_path: str, diff_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the impact of applying diff blocks using AST information.
        
        Args:
            file_path: Path to the file being modified
            diff_blocks: List of diff blocks to analyze
            
        Returns:
            Dictionary with impact analysis results
        """
        try:
            # Parse current file
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            current_tree = ast.parse(current_content)
            
            # Simulate the changes to get new content
            modified_content = self._simulate_diff_changes(current_content, diff_blocks)
            
            try:
                new_tree = ast.parse(modified_content)
            except SyntaxError as e:
                return {
                    "valid": False,
                    "error": f"Syntax error in modified code: {str(e)}",
                    "error_type": "syntax"
                }
            
            # Analyze changes
            analysis = {
                "valid": True,
                "changes_detected": {},
                "potential_issues": [],
                "affected_definitions": [],
                "dependencies_impact": [],
                "recommendations": []
            }
            
            # Detect what changed
            changes = self._detect_ast_changes(current_tree, new_tree)
            analysis["changes_detected"] = changes
            
            # Find affected definitions in the project
            affected = self._find_affected_definitions(file_path, changes)
            analysis["affected_definitions"] = affected
            
            # Check for potential issues
            issues = self._check_potential_issues(changes, affected)
            analysis["potential_issues"] = issues
            
            # Generate recommendations
            recommendations = self._generate_recommendations(changes, issues)
            analysis["recommendations"] = recommendations
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing diff impact: {e}")
            return {
                "valid": False,
                "error": f"Analysis error: {str(e)}",
                "error_type": "analysis"
            }
    
    def _simulate_diff_changes(self, content: str, diff_blocks: List[Dict[str, Any]]) -> str:
        """Simulate applying diff blocks to get the modified content."""
        lines = content.splitlines()
        
        # Sort blocks by line number in reverse order to avoid index shifting
        sorted_blocks = sorted(diff_blocks, key=lambda b: b.get('start_line', 0), reverse=True)
        
        for block in sorted_blocks:
            start_line = block.get('start_line', 1) - 1  # Convert to 0-indexed
            search_content = block.get('search_content', '')
            replace_content = block.get('replace_content', '')
            
            search_lines = search_content.splitlines()
            replace_lines = replace_content.splitlines()
            
            # Find the exact match
            if start_line < len(lines):
                # Simple replacement for simulation
                end_line = start_line + len(search_lines)
                lines[start_line:end_line] = replace_lines
        
        return '\n'.join(lines)
    
    def _detect_ast_changes(self, old_tree: ast.AST, new_tree: ast.AST) -> Dict[str, List[str]]:
        """Detect what changed between two AST trees."""
        changes = {
            "functions_added": [],
            "functions_removed": [],
            "functions_modified": [],
            "classes_added": [],
            "classes_removed": [],
            "classes_modified": [],
            "imports_added": [],
            "imports_removed": []
        }
        
        # Extract function and class names from both trees
        old_functions = {node.name for node in ast.walk(old_tree) if isinstance(node, ast.FunctionDef)}
        new_functions = {node.name for node in ast.walk(new_tree) if isinstance(node, ast.FunctionDef)}
        
        old_classes = {node.name for node in ast.walk(old_tree) if isinstance(node, ast.ClassDef)}
        new_classes = {node.name for node in ast.walk(new_tree) if isinstance(node, ast.ClassDef)}
        
        # Detect changes
        changes["functions_added"] = list(new_functions - old_functions)
        changes["functions_removed"] = list(old_functions - new_functions)
        changes["functions_modified"] = list(old_functions & new_functions)  # Conservative: assume all existing are modified
        
        changes["classes_added"] = list(new_classes - old_classes)
        changes["classes_removed"] = list(old_classes - new_classes)
        changes["classes_modified"] = list(old_classes & new_classes)
        
        return changes
    
    def _find_affected_definitions(self, file_path: str, changes: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Find definitions in other files that might be affected by changes."""
        affected = []
        
        if not self.ast_index:
            return affected
        
        # Look for usages of removed/modified functions and classes
        changed_items = (changes.get("functions_removed", []) + 
                        changes.get("functions_modified", []) +
                        changes.get("classes_removed", []) +
                        changes.get("classes_modified", []))
        
        for item in changed_items:
            # Find references in the AST index
            from pathlib import Path
            try:
                normalized_file_path = str(Path(file_path).resolve())
            except (OSError, ValueError):
                normalized_file_path = file_path
            for definition in self.ast_index:
                try:
                    def_file = str(Path(definition.get("file", "")).resolve()) if definition.get("file") else ""
                except (OSError, ValueError):
                    def_file = definition.get("file", "")
                if def_file != normalized_file_path:  # Different file
                    # This is a simplified check - in practice, we'd need more sophisticated analysis
                    if item in definition.get("signature", ""):
                        affected.append({
                            "definition": definition.get("name"),
                            "file": definition.get("file"),
                            "type": definition.get("type"),
                            "potentially_affected_by": item
                        })
        
        return affected
    
    def _check_potential_issues(self, changes: Dict[str, List[str]], affected: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Check for potential issues based on changes."""
        issues = []
        
        # Check for removed functions/classes that are used elsewhere
        removed_items = changes.get("functions_removed", []) + changes.get("classes_removed", [])
        if removed_items and affected:
            issues.append({
                "type": "breaking_change",
                "severity": "high",
                "message": f"Removing {', '.join(removed_items)} may break {len(affected)} other definitions"
            })
        
        # Check for modified functions that might change signature
        modified_functions = changes.get("functions_modified", [])
        if modified_functions:
            issues.append({
                "type": "signature_change",
                "severity": "medium", 
                "message": f"Modified functions {', '.join(modified_functions)} - verify signature compatibility"
            })
        
        return issues
    
    def _generate_recommendations(self, changes: Dict[str, List[str]], issues: List[Dict[str, str]]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if any(issue["severity"] == "high" for issue in issues):
            recommendations.append("⚠️  High-impact changes detected. Consider running tests after applying.")
        
        if changes.get("functions_removed") or changes.get("classes_removed"):
            recommendations.append("🔍 Consider using 'get_code_definition' to check all usages before removing.")
        
        if changes.get("imports_added"):
            recommendations.append("📦 New imports added. Verify they are available in the environment.")
        
        return recommendations


def enhance_apply_diff_with_ast(file_path: str, diff_blocks: List[Dict[str, Any]], 
                              ast_index: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced version of apply_diff that includes AST analysis.
    
    Args:
        file_path: Path to file being modified
        diff_blocks: Diff blocks to apply
        ast_index: Current AST index
        
    Returns:
        Enhanced result with AST analysis
    """
    analyzer = ASTDiffAnalyzer(ast_index)
    
    # Pre-apply analysis
    impact_analysis = analyzer.analyze_diff_impact(file_path, diff_blocks)
    
    # Solo bloquear si hay errores de sintaxis, no por impacto
    should_proceed = True
    if not impact_analysis.get("valid", True):
        # Solo bloquear si el error es de sintaxis, no de análisis
        if impact_analysis.get("error_type") == "syntax":
            should_proceed = False
        # Para otros tipos de error (análisis), proceder con warnings
    
    return {
        "ast_analysis": impact_analysis,
        "should_proceed": should_proceed,
        "warnings": impact_analysis.get("potential_issues", []),
        "recommendations": impact_analysis.get("recommendations", [])
    }
