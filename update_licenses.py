#!/usr/bin/env python3
"""
Update THIRD_PARTY_LICENSES.md with license information from installed packages.

This script uses pip-licenses to extract license information from packages
listed in requirements.txt and formats them into a markdown table with
full license text.

Usage:
    python update_licenses.py [--dry-run] [--output THIRD_PARTY_LICENSES.md]
"""

import argparse
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Dict


def get_package_licenses(requirements_file: Path) -> List[Dict]:
    """
    Get license information for packages in requirements.txt.
    
    Returns list of dicts with package info including full license text.
    """
    if not requirements_file.exists():
        print(f"Error: {requirements_file} not found", file=sys.stderr)
        print("Run 'python generate_requirements.py' first", file=sys.stderr)
        sys.exit(1)
    
    print(f"Reading packages from {requirements_file}...")
    
    # Read package names from requirements.txt
    with open(requirements_file, 'r') as f:
        packages = []
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before ==, >=, etc.)
                pkg_name = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                packages.append(pkg_name)
    
    if not packages:
        print("No packages found in requirements.txt", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(packages)} packages: {', '.join(packages)}")
    print("\nExtracting license information with pip-licenses...")
    
    # Run pip-licenses with JSON output to get structured data
    try:
        cmd = [
            "pip-licenses",
            "--format=json",
            "--with-license-file",
            "--packages"
        ] + packages
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        licenses_data = json.loads(result.stdout)
        return licenses_data
        
    except subprocess.CalledProcessError as e:
        print(f"Error running pip-licenses: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing pip-licenses output: {e}", file=sys.stderr)
        sys.exit(1)


def format_license_markdown(licenses_data: List[Dict]) -> str:
    """
    Format license data into markdown table format matching existing structure.
    """
    markdown = "# Third-Party Licenses\n\n"
    markdown += "| Package | Version | License | Description |\n"
    markdown += "|----------|----------|----------|-------------|\n"
    
    for pkg in licenses_data:
        name = pkg.get('Name', 'Unknown')
        version = pkg.get('Version', 'Unknown')
        license_type = pkg.get('License', 'Unknown')
        
        # Get license text
        license_text = ""
        if pkg.get('LicenseFile') and pkg.get('LicenseText'):
            license_text = pkg['LicenseText']
        elif license_type != 'UNKNOWN':
            license_text = f"Licensed under {license_type}"
        
        # Format the row
        # Escape pipe characters in license text and format multi-line
        license_desc = license_text.replace('|', '\\|').strip()
        
        markdown += f"| {name} | {version} | {license_type} | {license_desc} |\n"
    
    return markdown


def main():
    parser = argparse.ArgumentParser(
        description="Update THIRD_PARTY_LICENSES.md from requirements.txt"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without writing to file",
    )
    parser.add_argument(
        "--output",
        default="THIRD_PARTY_LICENSES.md",
        help="Output file (default: THIRD_PARTY_LICENSES.md)",
    )
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Requirements file to read (default: requirements.txt)",
    )
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent
    requirements_file = project_root / args.requirements
    output_file = project_root / args.output
    
    # Get license information
    licenses_data = get_package_licenses(requirements_file)
    
    # Format as markdown
    markdown_content = format_license_markdown(licenses_data)
    
    if args.dry_run:
        print("\n" + "="*80)
        print("DRY RUN - Output preview:")
        print("="*80)
        print(markdown_content)
        print("="*80)
        print(f"\nRun without --dry-run to write to {output_file}")
    else:
        # Backup existing file if it exists
        if output_file.exists():
            backup_file = output_file.with_suffix('.md.bak')
            print(f"Backing up existing file to {backup_file}")
            output_file.rename(backup_file)
        
        # Write new file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        print(f"\n[OK] Successfully wrote {len(licenses_data)} licenses to {output_file}")
        print(f"\nNext steps:")
        print(f"  1. Review {output_file} for accuracy")
        print(f"  2. Add manual entries for assets (fonts, icons) to docs/ASSET_LICENSES.md")
        print(f"  3. Commit the updated license file")


if __name__ == "__main__":
    main()
