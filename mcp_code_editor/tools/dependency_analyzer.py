"""
Dependency Analyzer - Auto-detección de dependencias para apply_diff_tool
=========================================================================

Este módulo analiza automáticamente las dependencias y el impacto de los cambios
cuando se modifica código, especialmente funciones y clases.
"""

import ast
import re
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
import subprocess
import tempfile
import json

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Analiza dependencias y detecta el impacto de cambios en funciones/clases.
    """
    
    def __init__(self, ast_index: List[Dict]):
        self.ast_index = ast_index
        self._build_dependency_graph()
    
    def _build_dependency_graph(self):
        """Construye un grafo de dependencias del proyecto."""
        self.dependency_graph = {}
        self.reverse_dependency_graph = {}  # Quién depende de quién
        
        for definition in self.ast_index:
            file_path = definition.get("file", "")
            name = definition.get("name", "")
            
            if file_path not in self.dependency_graph:
                self.dependency_graph[file_path] = {
                    "functions": {},
                    "classes": {},
                    "imports": []
                }
            
            def_type = definition.get("type", "")
            if def_type == "function":
                self.dependency_graph[file_path]["functions"][name] = definition
            elif def_type == "class":
                self.dependency_graph[file_path]["classes"][name] = definition
            elif def_type == "import":
                self.dependency_graph[file_path]["imports"].append(definition)
    
    def analyze_diff_dependencies(self, file_path: str, diff_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analiza las dependencias afectadas por los cambios en diff_blocks.
        
        Args:
            file_path: Archivo siendo modificado
            diff_blocks: Bloques de cambios a aplicar
            
        Returns:
            Análisis completo de dependencias y impacto
        """
        analysis = {
            "modified_functions": [],
            "modified_classes": [],
            "signature_changes": [],
            "affected_callers": [],
            "files_to_review": [],
            "breaking_changes": [],
            "impact_level": "low",  # low, medium, high, critical
            "recommendations": []
        }
        
        try:
            # Leer contenido actual del archivo
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Detectar qué funciones/clases se están modificando
            modified_items = self._detect_modified_items(current_content, diff_blocks)
            analysis["modified_functions"] = modified_items["functions"]
            analysis["modified_classes"] = modified_items["classes"]
            
            # Analizar cambios de firma
            signature_changes = self._detect_signature_changes(file_path, diff_blocks, current_content)
            analysis["signature_changes"] = signature_changes
            
            # Encontrar callers afectados
            affected_callers = self._find_affected_callers(file_path, modified_items["functions"] + modified_items["classes"])
            analysis["affected_callers"] = affected_callers
            
            # Determinar archivos a revisar
            files_to_review = list(set([caller["file"] for caller in affected_callers]))
            analysis["files_to_review"] = files_to_review
            
            # Detectar breaking changes
            breaking_changes = self._detect_breaking_changes(signature_changes, affected_callers)
            analysis["breaking_changes"] = breaking_changes
            
            # NUEVAS FUNCIONALIDADES:
            
            # Analizar impacto en herencia para clases modificadas
            inheritance_impact = []
            for class_name in modified_items["classes"]:
                inheritance_issues = self._analyze_inheritance_impact(class_name, {})
                inheritance_impact.extend(inheritance_issues)
            analysis["inheritance_impact"] = inheritance_impact
            
            # Analizar impacto en composición
            composition_impact = []
            for class_name in modified_items["classes"]:
                composition_issues = self._analyze_composition_impact(class_name)
                composition_impact.extend(composition_issues)
            analysis["composition_impact"] = composition_impact
            
            # Trazar cadenas de dependencia
            all_modified = modified_items["functions"] + modified_items["classes"]
            dependency_chains = self._trace_dependency_chains(all_modified, max_depth=3)
            chains_impact = self._analyze_dependency_chains_impact(dependency_chains)
            analysis["dependency_chains"] = {
                "chains": dependency_chains,
                "impact_analysis": chains_impact
            }
            
            # Generar sugerencias de migración
            migration_suggestions = self._generate_migration_suggestions(breaking_changes)
            analysis["migration_suggestions"] = migration_suggestions
            
            # Generar parches automáticos
            auto_fix_patches = self._generate_auto_fix_patches(migration_suggestions)
            analysis["auto_fix_patches"] = auto_fix_patches
            
            # Calcular nivel de impacto (actualizado con nuevos datos)
            impact_level = self._calculate_impact_level(modified_items, affected_callers, breaking_changes)
            analysis["impact_level"] = impact_level
            
            # Generar recomendaciones (actualizado con nuevos datos)
            recommendations = self._generate_recommendations(analysis)
            analysis["recommendations"] = recommendations
            
            # ANÁLISIS ESTÁTICO CON PYLINT/PYFLAKES
            # Debug: agregar info básica antes de llamar análisis estático
            analysis["static_warnings"] = [{
                "tool": "debug",
                "line": 0,
                "severity": "info",
                "message": "Starting static analysis - method about to be called",
                "type": "debug_info",
                "code": "pre-analysis"
            }]
            
            try:
                static_warnings = self._run_static_analysis(file_path, diff_blocks, current_content)
                # Combinar debug info con resultados reales
                analysis["static_warnings"].extend(static_warnings)
            except Exception as e:
                analysis["static_warnings"].append({
                    "tool": "debug",
                    "line": 0,
                    "severity": "error",
                    "message": f"Static analysis failed with error: {str(e)}",
                    "type": "debug_info",
                    "code": "analysis-error"
                })
            
            # Actualizar nivel de impacto si hay errores críticos
            if any(w.get("severity") == "error" for w in static_warnings):
                analysis["impact_level"] = "critical"
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            analysis["error"] = str(e)
        
        return analysis
    
    def _detect_modified_items(self, current_content: str, diff_blocks: List[Dict]) -> Dict[str, List[str]]:
        """Detecta qué funciones y clases se están modificando."""
        modified_items = {"functions": [], "classes": []}
        
        try:
            current_tree = ast.parse(current_content)
            
            # Obtener todas las funciones y clases actuales con sus líneas
            current_definitions = self._extract_definitions_with_lines(current_tree)
            
            # Para cada bloque de diff, verificar qué definiciones afecta
            for block in diff_blocks:
                start_line = block.get("start_line", 1)
                end_line = block.get("end_line", start_line)
                
                for name, info in current_definitions.items():
                    def_start = info["line_start"]
                    def_end = info["line_end"]
                    
                    # Verificar si el diff overlaps con la definición
                    if self._ranges_overlap(start_line, end_line, def_start, def_end):
                        if info["type"] == "function":
                            if name not in modified_items["functions"]:
                                modified_items["functions"].append(name)
                        elif info["type"] == "class":
                            if name not in modified_items["classes"]:
                                modified_items["classes"].append(name)
        
        except Exception as e:
            logger.error(f"Error detecting modified items: {e}")
        
        return modified_items
    
    def _extract_definitions_with_lines(self, tree: ast.AST) -> Dict[str, Dict]:
        """Extrae definiciones con sus números de línea."""
        definitions = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                definitions[node.name] = {
                    "type": "function",
                    "line_start": node.lineno,
                    "line_end": getattr(node, 'end_lineno', node.lineno),
                    "args": [arg.arg for arg in node.args.args] if hasattr(node.args, 'args') else []
                }
            elif isinstance(node, ast.ClassDef):
                definitions[node.name] = {
                    "type": "class",
                    "line_start": node.lineno,
                    "line_end": getattr(node, 'end_lineno', node.lineno)
                }
        
        return definitions
    
    def _ranges_overlap(self, start1: int, end1: int, start2: int, end2: int) -> bool:
        """Verifica si dos rangos de líneas se superponen."""
        return not (end1 < start2 or end2 < start1)
    
    def _detect_signature_changes(self, file_path: str, diff_blocks: List[Dict], current_content: str) -> List[Dict]:
        """Detecta cambios en firmas de funciones."""
        signature_changes = []
        
        try:
            # Simular los cambios para obtener el contenido modificado
            modified_content = self._simulate_diff_changes(current_content, diff_blocks)
            
            # Parsear ambas versiones
            current_tree = ast.parse(current_content)
            modified_tree = ast.parse(modified_content)
            
            # Extraer firmas de funciones
            current_signatures = self._extract_function_signatures(current_tree)
            modified_signatures = self._extract_function_signatures(modified_tree)
            
            # Comparar firmas
            for func_name in current_signatures:
                if func_name in modified_signatures:
                    current_sig = current_signatures[func_name]
                    modified_sig = modified_signatures[func_name]
                    
                    if current_sig != modified_sig:
                        change_type = self._classify_signature_change(current_sig, modified_sig)
                        signature_changes.append({
                            "function": func_name,
                            "file": file_path,
                            "old_signature": current_sig,
                            "new_signature": modified_sig,
                            "change_type": change_type,
                            "is_breaking": change_type in ["removed_args", "changed_args", "removed_function"]
                        })
                elif func_name not in modified_signatures:
                    # Función removida
                    signature_changes.append({
                        "function": func_name,
                        "file": file_path,
                        "old_signature": current_signatures[func_name],
                        "new_signature": None,
                        "change_type": "removed_function",
                        "is_breaking": True
                    })
        
        except Exception as e:
            logger.error(f"Error detecting signature changes: {e}")
        
        return signature_changes
    
    def _simulate_diff_changes(self, content: str, diff_blocks: List[Dict]) -> str:
        """Simula la aplicación de diff blocks para obtener el contenido modificado."""
        lines = content.splitlines()
        
        # Ordenar bloques por línea en orden reverso para evitar problemas de índice
        sorted_blocks = sorted(diff_blocks, key=lambda b: b.get('start_line', 0), reverse=True)
        
        for block in sorted_blocks:
            start_line = block.get('start_line', 1) - 1  # Convert to 0-indexed
            search_content = block.get('search_content', '')
            replace_content = block.get('replace_content', '')
            
            search_lines = search_content.splitlines()
            replace_lines = replace_content.splitlines()
            
            if start_line < len(lines):
                end_line = start_line + len(search_lines)
                lines[start_line:end_line] = replace_lines
        
        return '\n'.join(lines)
    
    def _extract_function_signatures(self, tree: ast.AST) -> Dict[str, str]:
        """Extrae las firmas de todas las funciones."""
        signatures = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                signature = self._build_function_signature(node)
                signatures[node.name] = signature
        
        return signatures
    
    def _build_function_signature(self, node: ast.FunctionDef) -> str:
        """Construye la firma de una función a partir del nodo AST."""
        args = []
        
        # Argumentos posicionales
        for arg in node.args.args:
            args.append(arg.arg)
        
        # Argumentos con valores por defecto
        defaults_offset = len(node.args.args) - len(node.args.defaults)
        for i, default in enumerate(node.args.defaults):
            arg_index = defaults_offset + i
            if arg_index < len(node.args.args):
                args[arg_index] += f"={ast.unparse(default) if hasattr(ast, 'unparse') else 'default'}"
        
        # *args
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        
        # **kwargs
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        return f"{node.name}({', '.join(args)})"
    
    def _classify_signature_change(self, old_sig: str, new_sig: str) -> str:
        """Clasifica el tipo de cambio en la firma."""
        old_args = self._extract_args_from_signature(old_sig)
        new_args = self._extract_args_from_signature(new_sig)
        
        if len(new_args) < len(old_args):
            return "removed_args"
        elif len(new_args) > len(old_args):
            return "added_args"
        elif old_args != new_args:
            return "changed_args"
        else:
            return "renamed_function"
    
    def _extract_args_from_signature(self, signature: str) -> List[str]:
        """Extrae los argumentos de una firma de función."""
        # Extraer argumentos entre paréntesis
        match = re.search(r'\((.*)\)', signature)
        if match:
            args_str = match.group(1)
            if args_str.strip():
                return [arg.strip().split('=')[0] for arg in args_str.split(',')]
        return []
    
    def _find_affected_callers(self, file_path: str, modified_items: List[str]) -> List[Dict]:
        """Encuentra todos los callers de las funciones/clases modificadas usando análisis AST detallado."""
        affected_callers = []
        
        try:
            normalized_file_path = str(Path(file_path).resolve())
        except (OSError, ValueError):
            normalized_file_path = file_path
        
        # Obtener archivos únicos para análisis
        files_to_analyze = set()
        for definition in self.ast_index:
            def_file = definition.get("file", "")
            if def_file and def_file != normalized_file_path:
                files_to_analyze.add(def_file)
        
        # Analizar cada archivo usando AST
        for file_to_analyze in files_to_analyze:
            for item_name in modified_items:
                references = self._find_detailed_references(file_to_analyze, item_name)
                for ref in references:
                    affected_callers.append({
                        "caller_name": ref.get("context", f"Reference in {Path(file_to_analyze).name}"),
                        "caller_type": ref.get("type", "unknown"),
                        "file": file_to_analyze,
                        "line": ref.get("line", 0),
                        "calls": item_name,
                        "confidence": ref.get("confidence", 0.5),
                        "reference_type": ref.get("type", "unknown")
                    })
        
        return affected_callers
    
    def _find_detailed_references(self, file_path: str, function_name: str) -> List[Dict]:
        """Análisis AST real del código fuente para encontrar referencias."""
        references = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Buscar llamadas de función
                if isinstance(node, ast.Call):
                    if self._is_function_call(node, function_name):
                        references.append({
                            "type": "function_call",
                            "line": node.lineno,
                            "context": self._get_surrounding_context(content, node.lineno),
                            "confidence": 0.9
                        })
                
                # Buscar imports
                elif isinstance(node, ast.ImportFrom):
                    if self._imports_function(node, function_name):
                        references.append({
                            "type": "import",
                            "line": node.lineno,
                            "context": f"Import: {function_name}",
                            "confidence": 1.0
                        })
                
                # Buscar atributos y nombres
                elif isinstance(node, ast.Name) and node.id == function_name:
                    references.append({
                        "type": "name_reference",
                        "line": node.lineno,
                        "context": self._get_surrounding_context(content, node.lineno),
                        "confidence": 0.7
                    })
                
                elif isinstance(node, ast.Attribute) and node.attr == function_name:
                    references.append({
                        "type": "attribute_reference",
                        "line": node.lineno,
                        "context": self._get_surrounding_context(content, node.lineno),
                        "confidence": 0.8
                    })
        
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
        
        return references
    
    def _is_function_call(self, node: ast.Call, function_name: str) -> bool:
        """Verifica si un nodo Call es una llamada a la función especificada."""
        if isinstance(node.func, ast.Name):
            return node.func.id == function_name
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr == function_name
        return False
    
    def _imports_function(self, node: ast.ImportFrom, function_name: str) -> bool:
        """Verifica si un import incluye la función especificada."""
        if node.names:
            for alias in node.names:
                if alias.name == function_name or alias.asname == function_name:
                    return True
        return False
    
    def _get_surrounding_context(self, content: str, line_number: int, context_lines: int = 1) -> str:
        """Obtiene el contexto alrededor de una línea específica."""
        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context_lines_content = lines[start:end]
        return ' | '.join(context_lines_content).strip()
    
    def _analyze_inheritance_impact(self, class_name: str, changes: Dict) -> List[Dict]:
        """Analiza impacto en herencia de clases."""
        inheritance_issues = []
        
        # Buscar clases que heredan de esta
        for definition in self.ast_index:
            if definition.get("type") == "class":
                inheritance = definition.get("inheritance", [])
                if class_name in inheritance:
                    inheritance_issues.append({
                        "derived_class": definition.get("name"),
                        "file": definition.get("file"),
                        "impact": "may_break_inheritance",
                        "severity": "high",
                        "line": definition.get("line_start", definition.get("line", 0))
                    })
        
        # Buscar clases de las que esta hereda (cambios en clases padre)
        for definition in self.ast_index:
            if definition.get("type") == "class" and definition.get("name") == class_name:
                inheritance = definition.get("inheritance", [])
                for parent_class in inheritance:
                    # Verificar si alguna clase padre fue modificada
                    inheritance_issues.append({
                        "derived_class": class_name,
                        "parent_class": parent_class,
                        "file": definition.get("file"),
                        "impact": "parent_class_changed",
                        "severity": "medium",
                        "line": definition.get("line_start", definition.get("line", 0))
                    })
        
        return inheritance_issues
    
    def _analyze_composition_impact(self, class_name: str) -> List[Dict]:
        """Analiza impacto en composición de objetos."""
        composition_issues = []
        
        # Buscar donde se instancia esta clase
        for definition in self.ast_index:
            signature = definition.get("signature", "")
            if f"{class_name}(" in signature:
                composition_issues.append({
                    "composed_in": definition.get("name"),
                    "composed_in_type": definition.get("type"),
                    "file": definition.get("file"),
                    "impact": "composition_may_break",
                    "severity": "medium",
                    "line": definition.get("line_start", definition.get("line", 0))
                })
        
        return composition_issues
    
    def _trace_dependency_chains(self, modified_items: List[str], max_depth: int = 3) -> List[List[str]]:
        """Traza cadenas de dependencia hasta N niveles."""
        chains = []
        
        for item in modified_items:
            chain = [item]
            self._build_chain_recursive(item, chain, chains, max_depth, set())
        
        return chains
    
    def _build_chain_recursive(self, current_item: str, current_chain: List[str], 
                              all_chains: List[List[str]], max_depth: int, visited: Set[str]):
        """Construye cadenas de dependencia recursivamente."""
        if len(current_chain) >= max_depth or current_item in visited:
            if len(current_chain) > 1:  # Solo agregar cadenas con al menos 2 elementos
                all_chains.append(current_chain.copy())
            return
        
        visited.add(current_item)
        
        # Buscar qué depende de current_item
        dependents = self._find_direct_dependents(current_item)
        
        for dependent in dependents:
            if dependent not in visited:
                current_chain.append(dependent)
                self._build_chain_recursive(dependent, current_chain, all_chains, max_depth, visited.copy())
                current_chain.pop()  # Backtrack
        
        visited.remove(current_item)
    
    def _find_direct_dependents(self, item_name: str) -> List[str]:
        """Encuentra elementos que dependen directamente del item especificado."""
        dependents = []
        
        for definition in self.ast_index:
            signature = definition.get("signature", "")
            if item_name in signature and definition.get("name") != item_name:
                dependents.append(definition.get("name", ""))
        
        return dependents
    
    def _analyze_dependency_chains_impact(self, chains: List[List[str]]) -> Dict[str, Any]:
        """Analiza el impacto de las cadenas de dependencia."""
        impact_analysis = {
            "total_chains": len(chains),
            "max_chain_length": max([len(chain) for chain in chains]) if chains else 0,
            "affected_items_count": len(set([item for chain in chains for item in chain])),
            "high_impact_chains": [],
            "risk_level": "low"
        }
        
        # Identificar cadenas de alto impacto (largo > 2)
        for chain in chains:
            if len(chain) > 2:
                impact_analysis["high_impact_chains"].append({
                    "chain": chain,
                    "length": len(chain),
                    "risk": "high" if len(chain) > 3 else "medium"
                })
        
        # Calcular nivel de riesgo general
        if impact_analysis["max_chain_length"] > 3:
            impact_analysis["risk_level"] = "high"
        elif impact_analysis["max_chain_length"] > 2:
            impact_analysis["risk_level"] = "medium"
        
        return impact_analysis
    
    def _generate_migration_suggestions(self, breaking_changes: List[Dict]) -> List[Dict]:
        """Genera sugerencias específicas de migración."""
        suggestions = []
        
        for change in breaking_changes:
            change_type = change.get("change_type", "")
            function_name = change.get("function", "")
            
            if change_type == "removed_args":
                suggestions.append({
                    "type": "argument_removal",
                    "function": function_name,
                    "suggestion": f"Remove argument from calls to '{function_name}'",
                    "confidence": 0.8,
                    "auto_fixable": True,
                    "files_affected": change.get("files_affected", [])
                })
            
            elif change_type == "added_args":
                suggestions.append({
                    "type": "argument_addition",
                    "function": function_name,
                    "suggestion": f"Add required argument to calls to '{function_name}'",
                    "confidence": 0.7,
                    "auto_fixable": False,  # Requires manual intervention for argument values
                    "files_affected": change.get("files_affected", [])
                })
            
            elif change_type == "changed_args":
                suggestions.append({
                    "type": "argument_modification",
                    "function": function_name,
                    "suggestion": f"Update argument names/types in calls to '{function_name}'",
                    "confidence": 0.6,
                    "auto_fixable": False,
                    "files_affected": change.get("files_affected", [])
                })
            
            elif change_type == "removed_function":
                suggestions.append({
                    "type": "function_removal",
                    "function": function_name,
                    "suggestion": f"Find alternative for removed function '{function_name}'",
                    "confidence": 0.9,
                    "auto_fixable": False,
                    "files_affected": change.get("files_affected", [])
                })
        
        return suggestions
    
    def _generate_auto_fix_patches(self, suggestions: List[Dict]) -> List[Dict]:
        """Genera parches automáticos para sugerencias que se pueden arreglar automáticamente."""
        patches = []
        
        for suggestion in suggestions:
            if suggestion.get("auto_fixable", False):
                patch = {
                    "suggestion_id": id(suggestion),
                    "type": suggestion["type"],
                    "function": suggestion["function"],
                    "files_to_patch": suggestion.get("files_affected", []),
                    "patch_type": "regex_replacement",
                    "confidence": suggestion.get("confidence", 0.5)
                }
                
                if suggestion["type"] == "argument_removal":
                    patch["description"] = f"Auto-remove deprecated arguments in {suggestion['function']} calls"
                    patch["risk_level"] = "medium"
                
                patches.append(patch)
        
        return patches
    
    def _detect_breaking_changes(self, signature_changes: List[Dict], affected_callers: List[Dict]) -> List[Dict]:
        """Detecta breaking changes basado en cambios de firma y callers."""
        breaking_changes = []
        
        for change in signature_changes:
            if change.get("is_breaking", False):
                # Encontrar callers específicos para esta función
                function_callers = [caller for caller in affected_callers 
                                  if caller.get("calls") == change["function"]]
                
                breaking_changes.append({
                    "type": "signature_change",
                    "function": change["function"],
                    "change_type": change["change_type"],
                    "affected_callers": len(function_callers),
                    "files_affected": list(set([caller["file"] for caller in function_callers])),
                    "severity": "high" if len(function_callers) > 3 else "medium"
                })
        
        return breaking_changes
    
    def _calculate_impact_level(self, modified_items: Dict, affected_callers: List, breaking_changes: List) -> str:
        """Calcula el nivel de impacto general."""
        total_modified = len(modified_items["functions"]) + len(modified_items["classes"])
        total_callers = len(affected_callers)
        total_breaking = len(breaking_changes)
        
        if total_breaking > 0 and total_callers > 5:
            return "critical"
        elif total_breaking > 0 or total_callers > 10:
            return "high"
        elif total_callers > 3 or total_modified > 3:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Genera recomendaciones basadas en el análisis."""
        recommendations = []
        
        impact_level = analysis["impact_level"]
        breaking_changes = analysis["breaking_changes"]
        files_to_review = analysis["files_to_review"]
        
        if impact_level == "critical":
            recommendations.append("🚨 CRITICAL: This change has high impact with breaking changes. Consider:")
            recommendations.append("   • Create a backup before applying")
            recommendations.append("   • Update all affected files simultaneously")
            recommendations.append("   • Run comprehensive tests after changes")
        
        elif impact_level == "high":
            recommendations.append("⚠️  HIGH IMPACT: This change affects multiple files:")
            
        elif impact_level == "medium":
            recommendations.append("📋 MEDIUM IMPACT: Review the following files:")
        
        else:
            recommendations.append("✅ LOW IMPACT: Safe to apply with minimal review")
        
        if files_to_review:
            recommendations.append(f"📁 Files to review: {', '.join(files_to_review[:5])}")
            if len(files_to_review) > 5:
                recommendations.append(f"   ...and {len(files_to_review) - 5} more files")
        
        if breaking_changes:
            recommendations.append("💥 Breaking changes detected:")
            for change in breaking_changes[:3]:  # Show top 3
                recommendations.append(f"   • {change['function']}: {change['change_type']}")
        
        # Sugerencias específicas
        if analysis["signature_changes"]:
            recommendations.append("🔧 Consider: Use get_code_definition to verify all callers")
        
        # NUEVAS RECOMENDACIONES:
        
        # Herencia
        inheritance_impact = analysis.get("inheritance_impact", [])
        if inheritance_impact:
            recommendations.append(f"🏗️  INHERITANCE: {len(inheritance_impact)} inheritance relationships affected")
            high_inheritance = [i for i in inheritance_impact if i.get("severity") == "high"]
            if high_inheritance:
                recommendations.append("   • High risk: derived classes may break")
        
        # Composición
        composition_impact = analysis.get("composition_impact", [])
        if composition_impact:
            recommendations.append(f"📦 COMPOSITION: {len(composition_impact)} composition relationships affected")
        
        # Cadenas de dependencia
        dependency_chains = analysis.get("dependency_chains", {})
        chains_impact = dependency_chains.get("impact_analysis", {})
        if chains_impact.get("risk_level") in ["medium", "high"]:
            max_length = chains_impact.get("max_chain_length", 0)
            recommendations.append(f"🔗 DEPENDENCY CHAINS: Max depth {max_length} - review cascade effects")
        
        # Sugerencias de migración
        migration_suggestions = analysis.get("migration_suggestions", [])
        auto_fixable = [s for s in migration_suggestions if s.get("auto_fixable", False)]
        if auto_fixable:
            recommendations.append(f"🔧 AUTO-FIX: {len(auto_fixable)} issues can be automatically fixed")
        
        manual_fixes = [s for s in migration_suggestions if not s.get("auto_fixable", False)]
        if manual_fixes:
            recommendations.append(f"✋ MANUAL: {len(manual_fixes)} issues require manual intervention")
        
        if impact_level in ["high", "critical"]:
            recommendations.append("🧪 Strongly recommended: Run tests after applying changes")
        
        return recommendations
    
    def _run_static_analysis(self, file_path: str, diff_blocks: List[Dict], current_content: str) -> List[Dict]:
        """Ejecuta análisis estático en el contenido modificado"""
        try:
            # Simular aplicación del diff
            new_content = self._simulate_diff_application(current_content, diff_blocks)
            
            warnings = []
            
            # 1. PYFLAKES (rápido)
            pyflakes_warnings = self._run_pyflakes_analysis(new_content)
            warnings.extend(pyflakes_warnings)
            
            # 2. PYLINT (solo errores críticos)
            pylint_warnings = self._run_pylint_analysis(new_content)
            warnings.extend(pylint_warnings)
            
            # Agregar debug info sobre el contenido analizado
            content_debug = {
                "tool": "debug",
                "line": 0,
                "severity": "info",
                "message": f"Static analysis executed on content: {len(new_content)} chars, first 100: '{new_content[:100]}...'",
                "type": "debug_info", 
                "code": "content-debug"
            }
            warnings.append(content_debug)
            
            return warnings
            
        except Exception as e:
            logger.warning(f"Error in static analysis: {e}")
            return []
    
    def _simulate_diff_application(self, current_content: str, diff_blocks: List[Dict]) -> str:
        """Simula la aplicación de diff para obtener contenido nuevo"""
        lines = current_content.splitlines()
        
        # Aplicar cada bloque de diff
        for block in diff_blocks:
            start_line = block.get("start_line", 1) - 1  # Convert to 0-based
            end_line = block.get("end_line", start_line + 1)
            replace_content = block.get("replace_content", "")
            
            # Reemplazar líneas
            new_lines = replace_content.splitlines()
            lines[start_line:end_line] = new_lines
        
        return '\n'.join(lines)
    
    def _run_pyflakes_analysis(self, content: str) -> List[Dict]:
        """Ejecuta pyflakes en el contenido"""
        warnings = []
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            result = subprocess.run(
                ['python', '-m', 'pyflakes', temp_file_path],
                capture_output=True, text=True, timeout=10
            )
            
            # Debug: siempre agregar info sobre la ejecución usando MCP logging
            # Como no tenemos Context aquí, vamos a agregar debug info en static_warnings
            debug_info = {
                "tool": "debug",
                "line": 0,
                "severity": "info", 
                "message": f"Pyflakes executed - returncode: {result.returncode}, stdout_length: {len(result.stdout) if result.stdout else 0}, stderr: '{result.stderr}'",
                "type": "debug_info",
                "code": "pyflakes-debug"
            }
            warnings.append(debug_info)
            
            if result.returncode != 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        warning = self._parse_pyflakes_line(line, temp_file_path)
                        if warning:
                            warnings.append(warning)
            
            Path(temp_file_path).unlink()
            
        except Exception as e:
            logger.warning(f"Pyflakes analysis failed: {e}")
        
        return warnings
    
    def _run_pylint_analysis(self, content: str) -> List[Dict]:
        """Ejecuta pylint en el contenido (solo errores críticos)"""
        warnings = []
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            result = subprocess.run(
                ['pylint', temp_file_path, '--errors-only', '--output-format=json', '--disable=C,R,W'],
                capture_output=True, text=True, timeout=15
            )
            
            if result.stdout.strip():
                try:
                    pylint_data = json.loads(result.stdout)
                    for item in pylint_data:
                        warning = self._parse_pylint_item(item)
                        if warning:
                            warnings.append(warning)
                except json.JSONDecodeError:
                    # Fallback si no es JSON válido
                    logger.warning("Pylint output not in JSON format")
            
            Path(temp_file_path).unlink()
            
        except Exception as e:
            logger.warning(f"Pylint analysis failed: {e}")
        
        return warnings
    
    def _parse_pyflakes_line(self, line: str, temp_path: str) -> Optional[Dict]:
        """Parsea una línea de salida de pyflakes"""
        try:
            # Formato: filename:line:col: message
            if ':' in line:
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    line_num = int(parts[1])
                    message = parts[3].strip()
                    
                    return {
                        "tool": "pyflakes",
                        "line": line_num,
                        "severity": "error" if "undefined" in message else "warning",
                        "message": message,
                        "type": "static_analysis",
                        "code": "pyflakes"
                    }
        except (ValueError, IndexError):
            pass
        return None
    
    def _parse_pylint_item(self, item: Dict) -> Optional[Dict]:
        """Parsea un item de salida JSON de pylint"""
        try:
            severity_map = {
                "error": "error",
                "fatal": "error", 
                "warning": "warning"
            }
            
            return {
                "tool": "pylint",
                "line": item.get("line", 0),
                "severity": severity_map.get(item.get("type"), "warning"),
                "message": item.get("message", ""),
                "type": "static_analysis",
                "code": item.get("message-id", "")
            }
        except Exception:
            pass
        return None


def enhance_apply_diff_with_dependencies(file_path: str, diff_blocks: List[Dict], 
                                       ast_index: List[Dict]) -> Dict[str, Any]:
    """
    Función principal para integrar análisis de dependencias en apply_diff_tool.
    
    Args:
        file_path: Archivo siendo modificado
        diff_blocks: Bloques de cambios
        ast_index: Índice AST del proyecto
        
    Returns:
        Análisis de dependencias e impacto
    """
    try:
        analyzer = DependencyAnalyzer(ast_index)
        dependency_analysis = analyzer.analyze_diff_dependencies(file_path, diff_blocks)
        
        return {
            "dependency_analysis": dependency_analysis,
            "has_dependencies": len(dependency_analysis["affected_callers"]) > 0,
            "impact_summary": {
                "modified_items": len(dependency_analysis["modified_functions"]) + len(dependency_analysis["modified_classes"]),
                "affected_files": len(dependency_analysis["files_to_review"]),
                "breaking_changes": len(dependency_analysis["breaking_changes"]),
                "impact_level": dependency_analysis["impact_level"]
            }
        }
    
    except Exception as e:
        logger.error(f"Error in dependency analysis: {e}")
        return {
            "dependency_analysis": {"error": str(e)},
            "has_dependencies": False,
            "impact_summary": {"error": str(e)}
        }
    
