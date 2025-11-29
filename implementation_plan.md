### 1. Data Layer & Models

**File:** `services/query/game_query_service.py`
*   **Update `GameQueryService`**:
    *   Add `get_all_ai_studios() -> List[AIStudio]`: Fetches all AI studios from the database, converts them to dataclasses.
    *   Add `get_ai_studio_scenes(studio_id: int) -> List[AIScene]`: Fetches all scenes associated with a specific AI studio ID.

**File:** `view_models.py`
*   **Add `AIStudioViewModel`**:
    *   Fields: `id`, `name`, `location`, `money_str`, `active_status_str`.
*   **Add `AISceneViewModel`**:
    *   Fields: `id`, `title`, `date_str`, `quality_score_str`, `revenue_str` (if simulated), `market_group`.

### 2. UI Widgets (The Parts)

Create a new directory: `ui/widgets/ai_studios/`

**File:** `ui/widgets/ai_studios/studio_list_widget.py`
*   Inherits `QWidget`.
*   Contains a `QTreeWidget` or `QTableWidget` to display the list of studios.
*   Signal: `studio_selected(int)` (emits the studio ID).
*   Method: `set_studios(studios: List[AIStudioViewModel])`.

**File:** `ui/widgets/ai_studios/studio_details_widget.py`
*   Inherits `QWidget` (using `GeometryManagerMixin` if persistent geometry is needed, though likely not for a sub-panel).
*   Layout: `QFormLayout` or `QGridLayout`.
*   Displays: Name, Location, Current Funds, Target Output, Preferred Markets.
*   Method: `display_studio(studio: AIStudio)`.
*   Method: `clear()`.

**File:** `ui/widgets/ai_studios/studio_scenes_widget.py`
*   Inherits `QWidget`.
*   Contains a `QTableWidget` for the scenes.
*   Columns: Title, Release Date, Market, Quality.
*   Method: `set_scenes(scenes: List[AISceneViewModel])`.

### 3. The View (The Shell)

**File:** `ui/tabs/ai_studios_tab.py`
*   Inherits `QWidget`.
*   **Layout Structure**:
    *   Top: Toolbar area containing `ViewMenuButton`.
    *   Center: `QSplitter` (Horizontal).
        *   Left Pane: `StudioListWidget`.
        *   Right Pane: `QSplitter` (Vertical).
            *   Top: `StudioDetailsWidget`.
            *   Bottom: `StudioScenesWidget`.
*   **API**:
    *   Expose methods to access the sub-widgets (e.g., `get_list_widget()`).
    *   Method `set_widget_visibility(key: str, visible: bool)` to handle logic from the `ViewMenuButton`.

### 4. The Presenter (The Logic)

**File:** `ui/presenters/ai_studios_tab_presenter.py`
*   Class `AIStudiosTabPresenter`.
*   **Dependencies**: `GameController`, `AIStudiosTab`, `ViewMenuButton`.
*   **Initialization**:
    *   Load the visibility state from `SettingsManager`.
    *   Populate `ViewMenuButton` items (List, Details, Scenes).
    *   Connect `ViewMenuButton.visibility_changed` to the View's visibility logic.
    *   Connect `StudioListWidget.studio_selected` to `_on_studio_selected`.
*   **Logic**:
    *   `load_initial_data()`: Fetch studios via `controller.query_service`, convert to ViewModels, populate List.
    *   `_on_studio_selected(studio_id)`: Fetch full studio details and scene list, update Details and Scenes widgets.
    *   `refresh()`: Reloads data (useful after a turn advance).

### 5. Integration

**File:** `ui_manager.py`
*   **Import**: New View and Presenter.
*   **Update `_assemble_tabs`**:
    *   Instantiate `AIStudiosTab`.
    *   Instantiate `AIStudiosTabPresenter`.
    *   Add the tab to `MainWindowView` with the label "AI Studios".
    *   Add the presenter to `self.tab_presenters` list to ensure it receives refresh calls.

**File:** `data/settings_manager.py`
*   **Update `_default_settings`**:
    *   Add `ai_studio_panel_visibility`: Dict to store the user's show/hide preferences for the three widgets.

### 6. File Creation Order

1.  Modify `services/query/game_query_service.py`.
2.  Modify `view_models.py`.
3.  Create `ui/widgets/ai_studios/*.py`.
4.  Create `ui/tabs/ai_studios_tab.py`.
5.  Create `ui/presenters/ai_studios_tab_presenter.py`.
6.  Modify `ui_manager.py`.
7.  Modify `data/settings_manager.py`.