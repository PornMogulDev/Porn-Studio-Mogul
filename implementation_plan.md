### Phase 1: Asset Organization

1.  **Directory Structure**:
    *   Create a new directory: `assets/icons/flags/`.
    *   Place SVG flag files here.
    *   **Naming Convention**: To minimize mapping logic, name the files exactly matching the database string for nationality, converted to lowercase and snake_case if necessary (e.g., `american.svg`, `japanese.svg`, `french.svg`). Alternatively, use ISO codes (e.g., `us.svg`) if you implement a mapping dictionary in `IconManager`.

2.  **Update `paths.py`**:
    *   Define a new constant `FLAGS_DIR = ICON_DIR / "flags"`.
    *   This ensures the `IconManager` has a reliable, single source of truth for the path.

### Phase 2: Core Service Update (`IconManager`)

The `IconManager` currently enforces a monochrome/recoloring logic suitable for UI controls. It needs to support "original color" assets.

1.  **Modify `get_icon`**:
    *   Add a parameter `original: bool = False` or `render_mode: str`.
    *   If `original` is `True`, skip the `_colorize_svg` step and `QPainter` composition mode. Instead, load the SVG directly into a `QPixmap` or `QIcon` without modification.

2.  **Add `get_flag_icon` Method**:
    *   Create a specific method: `get_flag_icon(nationality: str) -> QIcon`.
    *   This method handles the lookup logic (e.g., lowercasing the nationality string to find the file in `FLAGS_DIR`).
    *   It should handle missing flags gracefully (return an empty `QIcon` or a generic "globe" icon).
    *   It calls the internal load method with `original=True`.

### Phase 3: Talent Tab Implementation (Table View)

We need to inject the icon data into the table without making the ViewModel heavy.

1.  **Update `TalentTableModel`**:
    *   **Injection**: Pass `IconManager` into the `TalentTableModel` constructor (similar to `SettingsManager`).
    *   **Data Method**: In the `data()` method, handle the `Qt.ItemDataRole.DecorationRole`.
        *   Check if `index.column()` corresponds to the Nationality column.
        *   If yes, retrieve the nationality string from the ViewModel.
        *   Call `self.icon_manager.get_flag_icon(nationality_string)`.
        *   Return the `QIcon`.

2.  **View Adjustments (`TalentTab`)**:
    *   Ensure the `TalentTab` passes the `IconManager` (received from `TalentTabPresenter`) when initializing the `TalentTableModel`.

### Phase 4: Details Widget Implementation (Profile View)

`QLabel` cannot easily display an image and text side-by-side without using Rich Text (HTML) or a layout. A layout is cleaner for alignment.

1.  **Refactor `DetailsWidget` UI**:
    *   In `_setup_ui`, locate the "Nationality" row creation.
    *   Replace the single `self.nationality_label` with a small `QWidget` container (or simply a layout).
    *   Create a `QHBoxLayout` for this row.
    *   Add a new `self.nationality_icon_label` (fixed size, e.g., 24x16) to the layout.
    *   Add the existing `self.nationality_label` (text) to the layout.
    *   Add a spacer/stretch if necessary to keep it left-aligned.

2.  **Update `display_basic_info`**:
    *   Update the method signature to accept the `icon_manager` (or inject `IconManager` into `DetailsWidget` constructor).
    *   When setting the nationality text, also call `icon_manager.get_flag_icon(data['nationality'])`.
    *   Convert the `QIcon` to a `QPixmap` (via `icon.pixmap(size)`) and set it on `self.nationality_icon_label`.

### Phase 5: Dependency Injection Flow

1.  **`Application.py`**:
    *   `IconManager` is already created here.

2.  **`UIManager`**:
    *   Pass `IconManager` to `TalentTabPresenter`.

3.  **`TalentTabPresenter`**:
    *   Pass `IconManager` to `TalentTab` (View).
    *   Pass `IconManager` to `TalentTableModel`.

4.  **`TalentProfilePresenter`**:
    *   Pass `IconManager` to `TalentProfileWindow` -> `DetailsWidget`.

### Summary of Changes

*   **Assets**: Add flags to `assets/icons/flags`.
*   **Utils**: Update `paths.py`.
*   **Manager**: Update `IconManager` to support multi-colored/original SVGs and a flag lookup helper.
*   **Table**: Use `DecorationRole` in `TalentTableModel`.
*   **Profile**: Use a Horizontal Layout in `DetailsWidget` to render Icon + Text.