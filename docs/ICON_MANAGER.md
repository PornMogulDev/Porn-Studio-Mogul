# IconManager Documentation

The `IconManager` is a central service responsible for loading, recoloring, caching, and managing all UI icons within the application. It serves two primary purposes:

1.  **Dynamic Theming**: It loads monochrome SVGs and recolors them on-the-fly based on the active application theme (e.g., changing icons from black to white when switching to Dark Mode, or coloring an icon red for a "Danger" state).
2.  **Dynamic Sizing**: It scales icons automatically based on the user's selected font size settings to ensure UI consistency.

## Directory Structure

The manager expects assets to be located in the directories defined in `utils.paths`:

*   **Monochrome Icons**: `assets/icons/` (e.g., `save.svg`, `menu.svg`)
*   **Flag Icons**: `assets/icons/flags/` (e.g., `us.svg`, `fr.svg`)

## Key Concepts

### Semantic Roles
Instead of requesting specific colors (e.g., "red", "blue"), you request icons based on their **Semantic Role**. The manager maps these roles to specific colors defined in the `ThemeManager`.

| Role | Description | Theme Attribute |
| :--- | :--- | :--- |
| `text` / `primary` | Standard UI elements. | `theme.text` |
| `accent` | Highlighted elements. | `theme.accent` |
| `accent_hover` | Interaction states. | `theme.accent_hover` |
| `disabled` | Unavailable elements. | `theme.disabled_text` |
| `success` | Positive states. | `theme.color_good` |
| `warning` | Warnings or alerts. | `theme.color_warning` |
| `error` / `danger` | Critical errors or destructive actions. | `theme.danger` / `theme.color_bad` |
| `neutral` | Informational or low-priority. | `theme.color_neutral` |

### Caching
The `IconManager` maintains an internal memory cache.
*   **Keys**: Combinations of `icon_name` + `resolved_color_hex` (e.g., `save_#FF0000`).
*   **Behavior**: When the theme changes or the font size is updated, the cache is automatically cleared to allow regeneration of assets.

---

## Usage Examples

### 1. Basic Usage (Getting a QIcon)
Use this when you need a raw `QIcon` object, for example, setting a window icon or an item in a view model.

```python
# Get a standard icon colored with the theme's 'text' color
save_icon = icon_manager.get_icon("save_icon", "text")

# Get an icon colored for a destructive action
delete_icon = icon_manager.get_icon("trash_icon", "danger")
```

### 2. Applying to Buttons (Helper Method)
The `apply_icon` helper method is the preferred way to set icons on UI widgets (`QPushButton`, `QToolButton`, `QAction`). It handles:
1.  Fetching the icon.
2.  Setting the icon on the widget.
3.  **Setting the icon size** (crucial for font scaling).
4.  Setting the Qt dynamic property `iconRole` on the widget.

```python
# Standard application
icon_manager.apply_icon(self.save_button, "save_icon", "primary")

# Warning state
icon_manager.apply_icon(self.alert_button, "alert_icon", "warning")
```

### 3. Retrieving Flag Icons
Flag icons are **not** recolored. They are loaded as-is. The manager handles mapping nationality strings (e.g., "American") to ISO codes (e.g., "us.svg").

```python
# Returns the US flag
flag_icon = icon_manager.get_flag_icon("US") 

# Returns the generic globe fallback if the nationality isn't found
unknown_flag = icon_manager.get_flag_icon("Martian")
```

---

## API Reference

### `get_icon(name: str, role: str = "text") -> QIcon`
Retrieves a recolored monochrome icon.
*   **name**: The filename without extension (e.g., `"save"`).
*   **role**: The semantic role (e.g., `"accent"`). Can also be a raw hex code (`"#FF0000"`), though semantic roles are preferred.
*   **Returns**: A `QIcon`. If the file is missing, returns an empty `QIcon`.

### `apply_icon(target: QObject, icon_name: str, role: str = None)`
Applies an icon to a UI target.
*   **target**: The widget to receive the icon (usually `QAbstractButton` or `QAction`).
*   **icon_name**: Filename without extension.
*   **role**: (Optional) The semantic role. if `None`, it attempts to read the `iconRole` property from the target widget.
*   **Note**: This method automatically calls `target.setIconSize()` based on the current font settings.

### `get_flag_icon(nationality: str) -> QIcon`
Retrieves a full-color flag icon.
*   **nationality**: A string representing the country (e.g., "French", "US", "Germany").
*   **Fallback**: If the specific flag is not found, it returns a generic "globe" icon.
*   **Caching**: Results (including fallbacks) are cached to prevent repeated filesystem checks.

### `refresh_theme()`
Clears the internal cache and updates the reference to the current theme object. This is called automatically when the `ThemeManager` or `SettingsManager` signals a change.

### `get_target_size() -> QSize`
Calculates the ideal icon size (square) based on the application's current `font_size` setting.
*   **Formula**: `int(font_size * 2.0)` (e.g., 12pt font results in 24px icons).

---

## Adding New Icons

### Monochrome Icons
1.  Create an SVG file.
2.  Ensure the paths use a solid fill color (usually black `#000000`).
3.  Remove any hardcoded `stroke` or `style` attributes that might interfere with recoloring.
4.  Save to `assets/icons/`.

### Flag Icons
1.  Obtain the flag SVG.
2.  Rename the file to the **2-letter ISO code** (lowercase). Example: `us.svg`, `jp.svg`.
3.  Save to `assets/icons/flags/`.
4.  If adding a new nationality that isn't a standard country name, update `IconManager.NATIONALITY_MAP` in `ui/managers/icon_manager.py` to map the string to the ISO code.

```python
# Example mapping update
NATIONALITY_MAP = {
    # ... existing maps ...
    "Martian": "mars" # Maps "Martian" to mars.svg
}
```