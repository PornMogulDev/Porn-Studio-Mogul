### 1. Settings Configuration
Define the new user preferences required to manage the layout behavior.

*   **File:** `data/settings_manager.py` (or via `SettingsDialogPresenter` logic)
*   **New Keys:**
    *   `casting_mode_show_role_details`: `bool` (Default: `True`) - Toggles the top-left widget.
    *   `casting_mode_show_scene_summary`: `bool` (Default: `True`) - Toggles the bottom-left widget.
    *   `auto_hide_filter_on_casting`: `bool` (Default: `True`) - Automatically collapses the filter sidebar when "Apply" is clicked during casting.
    *   `demand_column_user_preference`: `bool` (Default: `True`) - Stores whether the user *wants* to see the Demand column, separate from whether the mode allows it.

### 2. Refactor `ViewMenuButton`
Change the button to use an Eye icon, strictly manage columns using Actions with ticks, and support tooltips.

*   **File:** `ui/widgets/view_menu_button.py`
*   **Changes:**
    *   **Icon:** Set to "Eye" icon.
    *   **Menu Logic:**
        *   Iterate through items.
        *   Create `QAction` for each item.
        *   Set `action.setCheckable(True)`.
        *   Set `action.setChecked(is_visible)`.
        *   **Tooltip Support:** If the item dictionary contains a `tooltip` key, set `action.setToolTip(...)`. This is specifically for the "Demand" column clarification.
        *   Connect `triggered` signal to `visibility_changed`.
    *   **Removal:** Delete `QWidgetAction` and `QCheckBox` logic.

### 3. Create `TalentFilterWidget`
Convert the existing Dialog into a Widget for embedding in the Tab.

*   **File:** `ui/widgets/talent_filter_widget.py` (New File)
*   **Source:** Copy logic from `ui/dialogs/talent_filter_dialog.py`.
*   **Changes:**
    *   Inherit `QWidget` instead of `QDialog`.
    *   Remove `geometry_manager_mixin` (the Tab splitter will handle size).
    *   Remove "Close" button.
    *   Keep "Apply" and "Reset" buttons functionality.
    *   Ensure layout is suitable for a sidebar (vertical constraints).
*   **File:** `ui/dialogs/talent_filter_dialog.py`
    *   Delete or deprecate.

### 4. Layout Restructuring (`TalentTab`)
Implement the 3-column responsive layout with collapsible sidebars.

*   **File:** `ui/tabs/talent_tab.py`
*   **Layout Structure:**
    *   **Main H-Splitter:**
        *   **Left Widget:** `info_panel_container` (QWidget)
            *   Layout: `QVBoxLayout` or `QSplitter` (Vertical).
            *   Top: `RoleDetailsWidget`.
            *   Bottom: `SceneSummaryWidget`.
        *   **Middle Widget:** `TalentTableView`.
        *   **Right Widget:** `filter_container` (QWidget)
            *   Layout: `QHBoxLayout`.
            *   **Left:** Chevron `QToolButton` (for toggling visibility).
            *   **Right:** `TalentFilterWidget`.
*   **Logic:**
    *   **Collapsing Filters:**
        *   Slot connected to Chevron button: Toggles `TalentFilterWidget` visibility.
        *   Updates Chevron icon (`<` vs `>`).
    *   **Casting Mode Layout:**
        *   `set_info_panel_visible(visible: bool)`: Shows/Hides the entire Left Widget.
        *   `configure_info_panel(show_role: bool, show_summary: bool)`: Shows/Hides specific widgets inside the Left Widget based on user settings.

### 5. `TalentTabPresenter` Implementation
The Presenter becomes the central coordinator for the view's layout state and data flow.

*   **File:** `ui/presenters/talent_tab_presenter.py`
*   **Logic Updates:**
    *   **Initialization:**
        *   Load settings (`casting_mode_*`).
        *   Initialize `TalentFilterWidget` and connect its `apply` signal to `on_filters_changed`.
        *   Connect `ViewMenuButton` signals.
    *   **Column Visibility Logic (`Demand`):**
        *   Intercept column toggle requests.
        *   If "Demand" is toggled: Update `demand_column_user_preference` setting.
        *   **Calculation:** Actual visibility = `demand_column_user_preference` AND `is_casting_mode`.
        *   Apply visibility to View.
    *   **Casting Mode State Machine (`on_filters_changed`):**
        *   Determine `is_casting_mode` (Scene ID & VP ID present).
        *   **If Casting Mode:**
            *   Show Left Info Panel (if settings allow).
            *   Update Role Details & Scene Summary data.
            *   Calculate Demand Column visibility (User Pref + True).
            *   If `auto_hide_filter_on_casting` is True: Trigger View to collapse filter sidebar.
        *   **If Browsing Mode:**
            *   Hide Left Info Panel (Table moves to Left).
            *   Clear Role/Scene widgets.
            *   Force Demand Column hidden (User Pref + False).
    *   **View Menu Config:**
        *   When populating the `ViewMenuButton`:
        *   Add "Demand" item.
        *   Set `tooltip`: "Only visible during Casting Mode" (or similar).
        *   Set `checked`: Based on `demand_column_user_preference`.

### 6. Supporting Updates

*   **File:** `ui/models/talent_table_model.py`
    *   No major changes, ensure "Demand" index is retrievable.
*   **File:** `ui/widgets/scene_summary_widget.py`
    *   Ensure it handles empty data gracefully (already does, but verify `clear()`).
*   **File:** `ui/managers/icon_manager.py`
    *   Add `get_icon("eye")`, `get_icon("chevron_left")`, `get_icon("chevron_right")`.

### Implementation Order

1.  **Refactor Filter:** Create `TalentFilterWidget`.
2.  **Refactor View Button:** Update `ViewMenuButton` to use Actions/Eye Icon.
3.  **Refactor Tab Layout:** Rewrite `TalentTab` to use the 3-section Splitter layout and embed the new widgets.
4.  **Refactor Presenter:** Implement the logic to coordinate visibility, settings, and the "Demand" column rules.
5.  **Clean up:** Remove old Dialog files.