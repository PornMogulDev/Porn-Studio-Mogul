---
description: Update third-party licenses
---

# Update Third-Party Licenses Workflow

This workflow updates the license documentation for the project. Run this workflow:
- Before every release
- After adding new Python package dependencies
- After adding new assets (icons, fonts, images)

## Step 1: Update Python Package Licenses

### 1.1 Generate/Update requirements.txt

Scan the codebase for actual imports and generate requirements.txt:

```powershell
python generate_requirements.py
```

This will:
- Scan all Python files in `src/` directory
- Identify third-party packages that are imported
- Generate `requirements.txt` with only runtime dependencies
- Backup existing `requirements.txt` as `requirements.txt.bak`

**Review the output** to ensure all necessary packages are included and versions are correct.

### 1.2 Extract License Information

Extract license information for packages in requirements.txt:

```powershell
# First, do a dry-run to preview the output
python update_licenses.py --dry-run

# If output looks good, generate the file
python update_licenses.py
```

This will:
- Read packages from `requirements.txt`
- Use pip-licenses to extract license information
- Format output as markdown table with full license text
- Backup existing `THIRD_PARTY_LICENSES.md` as `THIRD_PARTY_LICENSES.md.bak`
- Generate new `THIRD_PARTY_LICENSES.md`

**Review the generated file** to ensure:
- All licenses are correctly identified
- Full license text is included
- No packages are missing

## Step 2: Update Asset Licenses

For icons, fonts, and other assets, manually update `docs/ASSET_LICENSES.md`:

1. Open `docs/ASSET_LICENSES.md`
2. For each new asset added since last update:
   - Identify the source and license
   - Add entry to appropriate table (Fonts/Icons/Images)
   - Include attribution requirements
3. Save the file

Common sources:
- Brand icons: Check brand guidelines (Discord, GitHub, Reddit, etc.)
- Icon sets: Check the icon library website
- Fonts: Check Google Fonts or font foundry

## Step 3: Update NOTICE.md (If Required)

If any new licenses require **prominent attribution** (not just in license files):

1. Open `NOTICE.md`
2. Add entry for the component
3. Include copyright notice and link to full license

Components typically requiring NOTICE.md entries:
- GPL/LGPL licensed packages (like PyQt6)
- Packages with specific attribution requirements
- Major frameworks or libraries

## Step 4: Verify and Commit

// turbo
```powershell
# Review all changes
git status

# Check the diff
git diff THIRD_PARTY_LICENSES.md
git diff requirements.txt
git diff docs/ASSET_LICENSES.md
```

```powershell
# Commit the changes
git add THIRD_PARTY_LICENSES.md requirements.txt docs/ASSET_LICENSES.md NOTICE.md
git commit -m "Update third-party licenses"
```

## Troubleshooting

### "pipreqs not found"
```powershell
pip install pipreqs
```

### "pip-licenses not found"
```powershell
pip install pip-licenses
```

### Missing packages in requirements.txt

If a package is imported but not listed:
- Ensure the import is in a `.py` file in `src/` directory
- Check if it's a standard library module (won't be listed)
- Run `pipreqs --debug src` for verbose output

### License not found for a package

If pip-licenses shows "UNKNOWN" for a license:
- Check the package's PyPI page manually
- Look for LICENSE file in the package source
- Add manual entry to THIRD_PARTY_LICENSES.md if needed

## Advanced Usage

### Generate requirements for specific directory
```powershell
python generate_requirements.py --source-dir custom/path --output custom_requirements.txt
```

### Update licenses from custom requirements file
```powershell
python update_licenses.py --requirements custom_requirements.txt --output CUSTOM_LICENSES.md
```

### Include specific packages only
Edit `requirements.txt` to include only desired packages, then run:
```powershell
python update_licenses.py
```