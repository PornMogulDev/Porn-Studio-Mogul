### Objective
Ensure that all application icons (SVG-based and colored via `IconManager`) are generated at a resolution proportional to the user's selected `font_size` setting. When the font size changes, the icon cache should flush, and the UI should update to display crisply scaled icons.

### Strategy

1.  **Centralize Sizing Logic:** Modify `IconManager` to calculate the target icon size (in pixels) based on the `SettingsManager`'s font size property.
2.  **Dynamic Generation:** Update the `_colorize_svg` method in `IconManager` to use this calculated size instead of the hardcoded 64x64 resolution.
3.  **Cache Invalidation:** Connect `IconManager` to the `setting_changed` signal. If "font_size" changes, clear the internal icon cache.
4.  **UI Refresh:** Implement a `refresh_styling()` or `refresh_icons()` pattern in the Views (Main Window, Top Bar, etc.) to re-request icons from the manager after a settings change.

---

### Implementation Plan

#### 1. Modify `ui/managers/icon_manager.py`

*   **Dependency Injection:** Ensure `SettingsManager` is passed into `__init__` (currently only `ThemeManager` is).
*   **New Method `get_target_size()`:**
    *   Retrieve `font_size` from settings (default 12pt).
    *   Apply a scaling multiplier (e.g., `1.5` or `2.0`) to convert the point size to a pixel size suitable for icons (e.g., 12pt text -> 24px icon).
    *   Return a `QSize`.
*   **Update `_colorize_svg`:**
    *   Replace `base_size = QSize(64, 64)` with `base_size = self.get_target_size()`.
*   **Signal Handling:**
    *   Connect to `self.settings_manager.signals.setting_changed`.
    *   If the key is `"font_size"`, call `self._cache.clear()`.
*   **Update `apply_icon`:**
    *   Ensure that when applying an icon to a `QAbstractButton`, we also call `target.setIconSize(self.get_target_size())`. This ensures the button layout reserves enough space for the larger icon.

#### 2. Modify `ui/widgets/main_window/top_bar_widget.py`

*   **New Method `refresh_icons()`:**
    *   Move the logic that sets icons for buttons (Menu, Next Week, etc.) into this method (or call `setup_ui` logic that is safe to re-run).
    *   Specifically, re-call `icon_manager.apply_icon(...)` for the **Inbox** button, as its icon depends on state ("read" vs "unread").
    *   Ensure standard buttons (Menu, Next Week) have their icons re-set so they pick up the new resolution.

#### 3. Modify `ui/widgets/main_window/bottom_bar_widget.py` (and similar widgets)

*   **New Method `refresh_icons()`:**
    *   Similar to TopBar, iterate over buttons/labels that use icons and re-apply them via `IconManager`.

#### 4. Modify `ui/views/main_window_view.py`

*   **Update `set_font_from_settings`:**
    *   This method is already called when settings change.
    *   Add calls to `self.top_bar.refresh_icons()` and `self.bottom_bar.refresh_icons()`.

#### 5. Modify `ui/widgets/talent_profile/details_widget.py`

*   **Update `display_basic_info`:**
    *   Currently, this sets a fixed size for the flag: `self.nationality_icon_label.setFixedSize(24, 16)`.
    *   Change this to calculate dimensions based on `IconManager.get_target_size()` to maintain the aspect ratio but scale with the font.

#### 6. Modify `ui/models/talent_table_model.py`

*   **Update `refresh()`:**
    *   The model handles data. The `IconManager` handles the cache.
    *   When `font_size` changes, the Presenter will trigger a refresh.
    *   The `data()` method calls `icon_manager.get_flag_icon`. Since the cache was cleared in Step 1, this will automatically generate a new, correctly sized Pixmap. No code changes needed here specifically, provided the Presenter triggers the refresh.

#### 7. Modify `ui/presenters/main_window_presenter.py`

*   **Signal Connection:**
    *   Ensure the `on_setting_changed` slot handles `"font_size"`.
    *   It should trigger `view.set_font_from_settings` (which now updates icons per Step 4).
    *   It should also trigger a general app-wide refresh (like `refresh_main_window_data`) to force tables to redraw.

### Expected Flow

1.  User changes Font Size in Settings Dialog.
2.  `SettingsManager` emits `setting_changed("font_size")`.
3.  `IconManager` hears signal -> Clears `_cache`.
4.  `MainWindowPresenter` hears signal -> Calls `view.set_font_from_settings()`.
5.  `MainWindowView` updates stylesheet -> Calls `top_bar.refresh_icons()`.
6.  `TopBarWidget` asks `IconManager` for "menu_icon".
7.  `IconManager` calculates new size (e.g., 32px), generates new Pixmap, caches it, and returns `QIcon`.
8.  `TopBarWidget` sets the new icon on the button.
9.  Visual result: Icons grow/shrink to match the text legibility.