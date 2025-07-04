# MCP Code Editor

Un servidor MCP (Model Context Protocol) avanzado que proporciona herramientas de edición de código inteligentes con análisis AST, gestión de proyectos e integración de consola interactiva.

## 🚀 Características Principales

### 🔧 Gestión de Proyectos
- **Análisis automático de estructura de proyecto** con indexación AST
- **Filtrado inteligente de archivos** respetando `.gitignore`
- **Caché de configuración** para operaciones rápidas
- **Detección automática de tipo de proyecto** (Python, JavaScript, etc.)

### 🔍 Análisis de Código AST
- **Búsqueda de definiciones** y ubicaciones de uso
- **Análisis de dependencias** entre funciones y clases
- **Detección de cambios estructurales** que pueden romper el código
- **Métricas de código** automáticas (conteo de funciones, clases, imports)

### ✏️ Edición Inteligente de Archivos
- **Modificaciones precisas** con sistema diff avanzado
- **Protección contra cambios críticos** con análisis de impacto
- **Creación y eliminación** de archivos con respaldo automático
- **Lectura con números de línea** y metadatos AST

### 📚 Integración de Librerías
- **Indexación de librerías externas** (pandas, numpy, requests, etc.)
- **Búsqueda en librerías indexadas** para autocompletado
- **Análisis de compatibilidad** entre librerías

### 🖥️ Consola Interactiva
- **Procesos de consola inteligentes** (Python, Node.js, CMD)
- **Detección automática** de prompts vs procesos en segundo plano
- **Gestión de múltiples procesos** simultáneos
- **Captura de salida** con filtrado por tipo

## 📦 Instalación

```bash
pip install mcp-code-editor
```

## ⚙️ Configuración MCP Client

Agrega la siguiente configuración a tu cliente MCP:

### Claude Desktop

Edita el archivo de configuración:
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mcp-code-editor": {
      "command": "mcp-code-editor",
      "args": [],
      "env": {}
    }
  }
}
```

### Otros Clientes MCP

```json
{
  "servers": {
    "mcp-code-editor": {
      "command": "mcp-code-editor",
      "args": [],
      "cwd": "/ruta/a/tu/proyecto"
    }
  }
}
```

## 🛠️ Herramientas Disponibles

### Gestión de Proyectos

#### `setup_code_editor`
Analiza la estructura del proyecto y construye el índice AST.
```
setup_code_editor(
    path="/ruta/al/proyecto",
    analyze_ast=True
)
```

#### `project_files`
Obtiene archivos del proyecto con filtros opcionales.
```
project_files(
    filter_extensions=[".py", ".js"],
    max_depth=3,
    format_as_tree=True
)
```

### Análisis de Código

#### `get_code_definition`
Busca definiciones y ubicaciones de uso de cualquier identificador.
```
get_code_definition(
    identifier="function_name",
    definition_type="function",
    include_usage=True
)
```

#### `read_file_with_lines`
Lee archivos con números de línea y metadatos AST para Python.
```
read_file_with_lines(
    path="archivo.py",
    start_line=10,
    end_line=50
)
```

### Edición de Archivos

#### `apply_diff_tool`
Aplica modificaciones precisas con análisis de dependencias automático.
```
apply_diff_tool(
    path="archivo.py",
    blocks=[
        {
            "start_line": 15,
            "end_line": 17,
            "search_content": "def old_function():",
            "replace_content": "def new_function():"
        }
    ],
    force=False
)
```

#### `create_file_tool`
Crea nuevos archivos con contenido.
```
create_file_tool(
    path="nuevo_archivo.py",
    content="print('Hello World')",
    overwrite=False
)
```

#### `delete_file_tool`
Elimina archivos con opción de respaldo.
```
delete_file_tool(
    path="archivo_obsoleto.py",
    create_backup=True
)
```

### Integración de Librerías

#### `index_library_tool`
Indexa librerías externas para análisis.
```
index_library_tool(
    library_name="pandas",
    include_private=False
)
```

#### `search_library_tool`
Busca definiciones en librerías indexadas.
```
search_library_tool(
    library_name="pandas",
    query="DataFrame",
    definition_type="class"
)
```

#### `list_indexed_libraries_tool`
Lista todas las librerías indexadas.
```
list_indexed_libraries_tool()
```

### Consola Interactiva

#### `start_console_process_tool`
Inicia procesos de consola interactivos.
```
start_console_process_tool(
    command="python -u -i",
    working_dir="/ruta/al/proyecto",
    name="python_session"
)
```

#### `send_to_console_tool`
Envía entrada a procesos de consola con detección inteligente.
```
send_to_console_tool(
    process_id="process_id",
    input_text="print('Hello')",
    wait_for_response=True,
    force_send=False
)
```

#### `check_console_tool`
Obtiene instantánea de salida de consola.
```
check_console_tool(
    process_id="process_id",
    wait_seconds=2,
    lines=50,
    filter_type="stdout"
)
```

#### `list_console_processes_tool`
Lista procesos de consola activos.
```
list_console_processes_tool(
    include_terminated=False,
    summary_only=True
)
```

#### `terminate_console_process_tool`
Termina procesos de consola.
```
terminate_console_process_tool(
    process_id="process_id",
    force=False,
    timeout=10
)
```

## 🔐 Características de Seguridad

### Protección Inteligente
- **Análisis de impacto** antes de modificaciones críticas
- **Bloqueo automático** de cambios que pueden romper múltiples archivos
- **Advertencias de dependencias** y archivos afectados
- **Sugerencias de revisión** basadas en el análisis AST

### Detección de Entrada Inteligente
- **Prevención automática** de envío de comandos a procesos en segundo plano
- **Detección de prompts** vs procesos ejecutándose
- **Modo force** para señales de control (Ctrl+C)

## 💡 Casos de Uso

### Desarrollo Automatizado
```
1. Configurar proyecto: setup_code_editor
2. Analizar estructura: project_files
3. Buscar función: get_code_definition
4. Modificar código: apply_diff_tool
5. Probar cambios: start_console_process_tool
```

### Refactoring Inteligente
```
1. Encontrar todas las ubicaciones: get_code_definition
2. Analizar dependencias: apply_diff_tool (sin force)
3. Revisar impacto: analizar warnings
4. Aplicar cambios: apply_diff_tool (con force si necesario)
```

### Exploración de Código
```
1. Indexar librerías: index_library_tool
2. Buscar en librerías: search_library_tool
3. Leer código con contexto: read_file_with_lines
4. Analizar dependencias: get_code_definition
```

## 🐛 Mejores Prácticas

### Comandos de Consola Recomendados
- **Python**: `python -u -i` (modo unbuffered + interactivo)
- **Node.js**: `node` (REPL por defecto)
- **Windows CMD**: `cmd`
- **PowerShell**: `powershell`
- **Bash**: `bash`

### Workflow de Edición Segura
1. Siempre usar `apply_diff_tool` sin `force=True` primero
2. Revisar warnings y análisis de dependencias
3. Solo usar `force=True` cuando estés seguro
4. Usar `get_code_definition` para entender el impacto

### Gestión de Procesos
- Usar `check_console_tool` con `wait_seconds` apropiado
- Verificar estado con `list_console_processes_tool`
- Limpiar procesos terminados con `cleanup_terminated_processes_tool`

## 📚 Documentación Adicional

- [Guía de API MCP](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Repositorio del Proyecto](https://github.com/alejoair/mcp-code-editor)

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature
3. Añade tests si es necesario
4. Envía un Pull Request

## 📄 Licencia

MIT License - ver archivo [LICENSE](LICENSE) para detalles.

## 🔗 Enlaces

- **PyPI**: https://pypi.org/project/mcp-code-editor/
- **GitHub**: https://github.com/alejoair/mcp-code-editor
- **Documentación**: https://alejoair.github.io/mcp-code-editor/
- **Issues**: https://github.com/alejoair/mcp-code-editor/issues
