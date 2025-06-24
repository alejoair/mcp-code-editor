#!/usr/bin/env python3
"""
Script de utilidad para gestionar releases de mcp-code-editor.

Este script facilita:
- Bump de versiones localmente
- Validación de configuración
- Dry-run de releases
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, check=True, capture_output=True):
    """Ejecuta un comando y devuelve el resultado."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=check, 
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando: {cmd}")
        print(f"Error: {e.stderr if e.stderr else e}")
        sys.exit(1)


def get_current_version():
    """Obtiene la versión actual del proyecto."""
    try:
        # Intentar con tomllib primero (Python 3.11+)
        result = run_command(
            'python -c "import tomllib; print(tomllib.load(open(\'pyproject.toml\', \'rb\'))[\'project\'][\'version\'])"',
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Fallback a tomli
        result = run_command(
            'python -c "import tomli; print(tomli.load(open(\'pyproject.toml\', \'rb\'))[\'project\'][\'version\'])"'
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"❌ Error obteniendo versión: {e}")
        sys.exit(1)


def validate_setup():
    """Valida que el entorno esté configurado correctamente."""
    print("🔍 Validando configuración...")
    
    # Verificar archivos necesarios
    required_files = [
        'pyproject.toml',
        '.bumpversion.cfg',
        'mcp_code_editor/__init__.py'
    ]
    
    for file in required_files:
        if not Path(file).exists():
            print(f"❌ Archivo faltante: {file}")
            return False
    
    # Verificar que bump2version esté instalado
    result = run_command('bump2version --help', check=False)
    if result.returncode != 0:
        print("❌ bump2version no está instalado")
        print("Instalar con: pip install bump2version")
        return False
    
    # Verificar consistencia de versiones
    print("📦 Verificando consistencia de versiones...")
    
    pyproject_version = get_current_version()
    
    # Versión en __init__.py
    result = run_command(
        'python -c "import sys; sys.path.insert(0, \'.\'); import mcp_code_editor; print(mcp_code_editor.__version__)"'
    )
    init_version = result.stdout.strip()
    
    # Versión en .bumpversion.cfg
    result = run_command('grep "current_version" .bumpversion.cfg')
    bump_version = result.stdout.split()[-1].strip()
    
    print(f"  pyproject.toml: {pyproject_version}")
    print(f"  __init__.py: {init_version}")
    print(f"  .bumpversion.cfg: {bump_version}")
    
    if pyproject_version == init_version == bump_version:
        print("✅ Todas las versiones son consistentes")
        return True
    else:
        print("❌ Inconsistencia en versiones detectada")
        return False


def bump_version(version_type, dry_run=False):
    """Hace bump de la versión."""
    if not validate_setup():
        print("❌ Validación falló. No se puede continuar.")
        return False
    
    current_version = get_current_version()
    print(f"📋 Versión actual: {current_version}")
    
    # Dry run
    if dry_run:
        print(f"🧪 Dry run: bump2version {version_type} --dry-run")
        result = run_command(f'bump2version {version_type} --dry-run --verbose', capture_output=False)
        return True
    
    # Verificar estado del repositorio
    result = run_command('git status --porcelain', check=False)
    if result.stdout.strip():
        print("⚠️ Hay cambios sin commitear:")
        print(result.stdout)
        
        response = input("¿Continuar de todos modos? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operación cancelada")
            return False
    
    # Hacer el bump
    print(f"🔄 Haciendo bump de versión: {version_type}")
    result = run_command(f'bump2version {version_type} --verbose', capture_output=False)
    
    if result.returncode == 0:
        new_version = get_current_version()
        print(f"✅ Versión actualizada: {current_version} → {new_version}")
        print(f"🏷️ Tag creado: v{new_version}")
        return True
    else:
        print("❌ Error en bump de versión")
        return False


def show_status():
    """Muestra el estado actual del proyecto."""
    print("📊 Estado del proyecto MCP Code Editor")
    print("=" * 50)
    
    # Versión actual
    current_version = get_current_version()
    print(f"📦 Versión actual: {current_version}")
    
    # Estado del git
    result = run_command('git status --porcelain', check=False)
    if result.stdout.strip():
        print("📝 Cambios pendientes:")
        for line in result.stdout.strip().split('\n'):
            print(f"  {line}")
    else:
        print("✅ Repositorio limpio")
    
    # Último tag
    result = run_command('git describe --tags --abbrev=0', check=False)
    if result.returncode == 0:
        last_tag = result.stdout.strip()
        print(f"🏷️ Último tag: {last_tag}")
        
        # Commits desde último tag
        result = run_command(f'git rev-list {last_tag}..HEAD --count', check=False)
        if result.returncode == 0:
            commit_count = result.stdout.strip()
            print(f"📝 Commits desde último tag: {commit_count}")
    else:
        print("🏷️ No hay tags")
    
    # Verificar si puede hacer push
    result = run_command('git remote -v', check=False)
    if 'origin' in result.stdout:
        print("📡 Remote configurado: ✅")
    else:
        print("📡 Remote configurado: ❌")


def build_package():
    """Construye el paquete."""
    print("🔨 Construyendo paquete...")
    
    # Limpiar dist anterior
    import shutil
    if Path('dist').exists():
        shutil.rmtree('dist')
        print("🧹 Limpiado directorio dist")
    
    # Construir
    result = run_command('python -m build', capture_output=False)
    
    if result.returncode == 0:
        print("✅ Paquete construido exitosamente")
        
        # Verificar paquete
        result = run_command('python -m twine check dist/*')
        if result.returncode == 0:
            print("✅ Paquete verificado")
            
            # Mostrar archivos generados
            dist_files = list(Path('dist').glob('*'))
            print("📦 Archivos generados:")
            for file in dist_files:
                print(f"  {file.name} ({file.stat().st_size} bytes)")
            return True
    
    print("❌ Error construyendo paquete")
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Utilidad para gestionar releases de mcp-code-editor'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando status
    subparsers.add_parser('status', help='Mostrar estado del proyecto')
    
    # Comando validate
    subparsers.add_parser('validate', help='Validar configuración')
    
    # Comando bump
    bump_parser = subparsers.add_parser('bump', help='Hacer bump de versión')
    bump_parser.add_argument(
        'type', 
        choices=['patch', 'minor', 'major'],
        help='Tipo de bump de versión'
    )
    bump_parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Mostrar qué se haría sin ejecutar'
    )
    
    # Comando build
    subparsers.add_parser('build', help='Construir paquete')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'status':
            show_status()
        elif args.command == 'validate':
            if validate_setup():
                print("✅ Configuración válida")
            else:
                sys.exit(1)
        elif args.command == 'bump':
            if bump_version(args.type, args.dry_run):
                if not args.dry_run:
                    print("\n💡 Consejos:")
                    print("  - Revisa los cambios con: git log --oneline -5")
                    print("  - Push al repo con: git push origin master --tags")
                    print("  - O ejecuta el workflow de GitHub Actions para release automático")
            else:
                sys.exit(1)
        elif args.command == 'build':
            if not build_package():
                sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
