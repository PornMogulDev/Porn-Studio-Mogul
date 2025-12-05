# Asset Licenses

This file tracks licenses for non-code assets such as icons, fonts, images, and other media files used in the project.

> [!IMPORTANT]
> This file must be **manually maintained**. When adding new assets to the project, ensure you document their license information here.

---

## Fonts

| Font Name | Version | License | Source | Attribution Required |
|-----------|---------|---------|--------|---------------------|
| Roboto | - | SIL OPEN FONT LICENSE Version 1.1 | [Google Fonts](https://github.com/googlefonts/roboto-3-classic) | Yes - See NOTICE.md |

---

## Icons

| Icon/Set Name | File(s) | License | Source | Attribution Required | Notes |
|---------------|---------|---------|--------|---------------------|-------|
| SVG Logos | Most brand icons at `assets/icons/brands` | CC0 1.0 Universal | [gilbarbara/logos](https://github.com/gilbarbara/logos) | No | Public domain |
| Bootstrap Icons | All game icons at `assets/icons` | MIT License | [Bootstrap Icons](https://github.com/twbs/icons) | Yes - See NOTICE.md | - |
| flag-icons | All flags at `assets/icons/flags` | MIT License | [flags-icons](https://github.com/lipis/flag-icons) | Yes - See NOTICE.md | - |
| F95 Zone Icon | `f95_icon.svg` | *[TO BE FILLED]* | [logos-world.net](https://logos-world.net/)| *[TO BE FILLED]* | Converted to SVG in [freeconvert.com](https://www.freeconvert.com/png-to-svg) |

---

## Images

| Image Name | File(s) | License | Source | Attribution Required | Notes |
|------------|---------|---------|--------|---------------------|-------|
| *[Add entries as needed]* | - | - | - | - | - |

---

## Common License Resources

When researching licenses for assets, check these common sources:

### Icon Licenses
- **[Font Awesome](https://fontawesome.com/license)** - Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT
- **[Feather Icons](https://feathericons.com/)** - MIT License
- **[Heroicons](https://heroicons.com/)** - MIT License
- **[Material Icons](https://fonts.google.com/icons)** - Apache License 2.0
- **[Bootstrap Icons](https://icons.getbootstrap.com/)** - MIT License

### Brand Icons
- **Discord** - [Brand Guidelines](https://discord.com/branding)
- **GitHub** - [Logos and Usage](https://github.com/logos)
- **Reddit** - [Brand Guidelines](https://reddit.com/brand)

### Font Licenses
- **[Google Fonts](https://fonts.google.com/)** - Mostly SIL OFL 1.1

---

## Adding New Assets

When adding a new asset to the project:

1. **Identify the source** - Where did you get this asset?
2. **Check the license** - What are the terms of use?
3. **Document attribution** - What attribution is required?
4. **Update this file** - Add an entry in the appropriate section above
5. **Add to NOTICE.md if required** - If the license requires prominent attribution

### Example Entry

```markdown
| Icon Name | `my_icon.svg` | MIT | [Icon Library](https://example.com) | Yes - See NOTICE.md | Downloaded 2025-12-05 |
```

---

## Notes

- **THIRD_PARTY_LICENSES.md** is for Python package licenses (auto-generated)
- **ASSET_LICENSES.md** (this file) is for fonts, icons, images (manual)
- **NOTICE.md** contains prominent attributions for important components
- Always verify license terms before using third-party assets
- When in doubt, contact the asset creator or use public domain alternatives
