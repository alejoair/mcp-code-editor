"""
Diff Simulator - Utilidad común para simular la aplicación de diff blocks.

Esta utilidad centraliza la lógica de simulación de cambios de diff
para evitar duplicación de código entre ast_integration.py y dependency_analyzer.py.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class DiffSimulator:
    """
    Simula la aplicación de diff blocks para obtener contenido modificado.
    """
    
    @staticmethod
    def simulate_diff_changes(content: str, diff_blocks: List[Dict[str, Any]]) -> str:
        """
        Simula la aplicación de diff blocks para obtener el contenido modificado.
        
        Args:
            content: Contenido original del archivo
            diff_blocks: Lista de bloques de cambios a aplicar
            
        Returns:
            Contenido modificado después de aplicar los diff blocks
        """
        if not content:
            return ""
            
        if not diff_blocks:
            return content
            
        lines = content.splitlines()
        
        # Ordenar bloques por línea en orden reverso para evitar problemas de índice
        sorted_blocks = sorted(diff_blocks, key=lambda b: b.get('start_line', 0), reverse=True)
        
        for block in sorted_blocks:
            try:
                start_line = block.get('start_line', 1) - 1  # Convert to 0-indexed
                search_content = block.get('search_content', '')
                replace_content = block.get('replace_content', '')
                
                search_lines = search_content.splitlines()
                replace_lines = replace_content.splitlines()
                
                # Verificar que el start_line esté dentro del rango válido
                if 0 <= start_line < len(lines):
                    # Simple replacement for simulation
                    end_line = start_line + len(search_lines)
                    lines[start_line:end_line] = replace_lines
                
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error simulating diff block: {e}")
                continue
        
        return '\n'.join(lines)
    
    @staticmethod
    def simulate_diff_application(current_content: str, diff_blocks: List[Dict]) -> str:
        """
        Alias para simulate_diff_changes para mantener compatibilidad.
        
        Args:
            current_content: Contenido actual del archivo
            diff_blocks: Bloques de diff a aplicar
            
        Returns:
            Contenido modificado
        """
        return DiffSimulator.simulate_diff_changes(current_content, diff_blocks)


# Funciones de conveniencia para uso directo
def simulate_diff_changes(content: str, diff_blocks: List[Dict[str, Any]]) -> str:
    """Función de conveniencia para simular cambios de diff."""
    return DiffSimulator.simulate_diff_changes(content, diff_blocks)


def simulate_diff_application(current_content: str, diff_blocks: List[Dict]) -> str:
    """Función de conveniencia para simular aplicación de diff."""
    return DiffSimulator.simulate_diff_application(current_content, diff_blocks)