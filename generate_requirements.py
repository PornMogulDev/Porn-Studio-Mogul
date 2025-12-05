#!/usr/bin/env python3
"""
Generate requirements.txt from actual package imports in the project.

This script scans the src/ directory for Python files and identifies
all third-party packages that are actually imported. It uses pipreqs
to analyze imports and generate a clean requirements.txt with only
runtime dependencies.

Usage:
    python generate_requirements.py [--output requirements.txt]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate requirements.txt from actual imports"
    )
    parser.add_argument(
        "--output",
        default="requirements.txt",
        help="Output file path (default: requirements.txt)",
    )
    parser.add_argument(
        "--source-dir",
        default="src",
        help="Source directory to scan (default: src)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing requirements.txt without prompting",
    )
    
    args = parser.parse_args()
    
    # Get project root (where this script is located)
    project_root = Path(__file__).parent
    source_dir = project_root / args.source_dir
    output_file = project_root / args.output
    
    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Check if output file exists
    if output_file.exists() and not args.force:
        response = input(f"{output_file} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    print(f"Scanning imports in {source_dir}...")
    
    # Run pipreqs to generate requirements
    try:
        # pipreqs with --force to overwrite, --savepath to specify output
        # --encoding utf-8 to handle Unicode characters in source files
        cmd = [
            "pipreqs",
            str(source_dir),
            "--force",
            "--encoding",
            "utf-8",
            "--savepath",
            str(output_file),
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print(f"\n[OK] Successfully generated {output_file}")
        print(f"\nNext steps:")
        print(f"  1. Review {output_file} for accuracy")
        print(f"  2. Run 'pip install -r {output_file}' to verify dependencies")
        print(f"  3. Run 'python update_licenses.py' to update license information")
        
    except subprocess.CalledProcessError as e:
        print(f"Error running pipreqs: {e}", file=sys.stderr)
        if e.stdout:
            print(f"stdout: {e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: pipreqs is not installed or not in PATH.", file=sys.stderr)
        print("Install it with: pip install pipreqs", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()