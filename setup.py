#!/usr/bin/env python3
"""
Setup script for mcp-code-editor
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ""

# Read requirements
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith('#')
        ]

setup(
    name="mcp-code-editor",
    version="0.1.9",
    author="MCP Code Editor Team",
    author_email="mcpcodeeditor@example.com",
    description="A FastMCP server providing powerful code editing tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mcp-code-editor/mcp-code-editor",
    packages=find_packages(include=['mcp_code_editor', 'mcp_code_editor.*']),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Editors",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "mcp-code-editor=mcp_code_editor.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="mcp, code-editor, fastmcp, development-tools",
    project_urls={
        "Bug Reports": "https://github.com/mcp-code-editor/mcp-code-editor/issues",
        "Source": "https://github.com/mcp-code-editor/mcp-code-editor",
    },
)
