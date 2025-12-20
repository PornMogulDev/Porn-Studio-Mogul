# TalentProfileWindow Refactoring Plan

Refactor the `TalentProfileWindow` to use splitter-based layouts instead of dock widgets, and adopt a coordinator pattern for the presenter architecture.

## Design Decisions (Resolved)

- **Layout Preset Migration**: Clear silently (early development, no users to migrate)
- **Fixed Layout**: Acceptable trade-off for predictability  
- **Bottom Panel**: Remains tabbed (`QTabWidget`)

---

## Phase 1: Layout Migration (Docks → Splitters)

Replace `QDockWidget`-based layout with a nested `QSplitter` structure for predictable sizing and simpler persistence.

### Component: View Layer

#### [MODIFY] [talent_profile_view.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/views/talent_profile_view.py)

Major changes:
1. **Change base class to `BaseGameWindow`** (inherits from `QDialog` + `GeometryManagerMixin`, provides min/max buttons)
2. Remove all dock widget infrastructure:
   - Remove `setDockNestingEnabled(True)`
   - Remove `_add_dock()` helper
   - Remove `view_menu` (no toggle actions needed)
   - Remove `self.saveState()`/`restoreState()` calls
3. Add splitter-based layout:

```python
# New layout structure (pseudocode):
main_layout = QVBoxLayout(self)
main_layout.addWidget(self.tab_toolbar)
main_layout.addWidget(self.layout_toolbar)

# Content area: Three-way vertical split
self.main_splitter = QSplitter(Qt.Orientation.Vertical)

# Top section: Two-way horizontal split
self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
self.left_splitter = QSplitter(Qt.Orientation.Vertical)
self.right_splitter = QSplitter(Qt.Orientation.Vertical)

self.left_splitter.addWidget(self.details_widget)
self.left_splitter.addWidget(self.preferences_widget)

self.right_splitter.addWidget(self.schedule_widget)
self.right_splitter.addWidget(self.hiring_widget)

self.top_splitter.addWidget(self.left_splitter)
self.top_splitter.addWidget(self.right_splitter)

# Bottom section: Tabbed History/Chemistry
self.bottom_tabs = QTabWidget()
self.bottom_tabs.addTab(self.history_widget, "Scene History")
self.bottom_tabs.addTab(self.chemistry_widget, "Chemistry")

self.main_splitter.addWidget(self.top_splitter)
self.main_splitter.addWidget(self.bottom_tabs)

main_layout.addWidget(self.main_splitter)
```

4. Replace layout save/load with splitter size persistence:

```python
def _save_layout(self) -> dict:
    return {
        'main': self.main_splitter.sizes(),
        'top': self.top_splitter.sizes(),
        'left': self.left_splitter.sizes(),
        'right': self.right_splitter.sizes(),
    }

def _load_layout(self, data: dict):
    if sizes := data.get('main'): self.main_splitter.setSizes(sizes)
    if sizes := data.get('top'): self.top_splitter.setSizes(sizes)
    if sizes := data.get('left'): self.left_splitter.setSizes(sizes)
    if sizes := data.get('right'): self.right_splitter.setSizes(sizes)
```

5. Update toolbar: Change "Save Layout" to save splitter sizes dict (JSON-serializable).

#### No changes to [geometry_manager_mixin.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/mixins/geometry_manager_mixin.py)

Already bundled into `BaseGameWindow`.

---

### Component: Settings Layer

#### [MODIFY] [settings_manager.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/data/settings_manager.py)

The existing `get_talent_profile_layouts()` / `set_talent_profile_layouts()` methods can stay. The stored format changes from:
- **Old**: `{"layout_name": "<base64 QMainWindow state>"}`  
- **New**: `{"layout_name": {"main": [h1, h2], "top": [w1, w2], ...}}`

This is a breaking change (existing layouts become invalid), but no code changes needed in `SettingsManager`—the view handles the format.

---

### Component: Integration

#### [MODIFY] [ui_manager.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/managers/ui_manager.py)

Update `show_talent_profile()`:
- Change type annotation from `TalentProfileWindow` (was `QMainWindow`) to `QWidget`
- No functional changes needed—method already treats it as a generic window

---

## Phase 2: Presenter Coordinator Pattern

Extract widget-specific logic from the monolithic `TalentProfilePresenter` into specialized sub-presenters, with the main presenter acting as a coordinator.

### Base Class Strategy

| Presenter Type | Base Class | Rationale |
|---------------|------------|----------|
| **Coordinator** (`TalentProfilePresenter`) | `BasePresenter` | Connects to `controller.signals.*` (roster_changed, scenes_changed, setting_changed). Needs `cleanup()` for proper lifecycle. |
| **Sub-presenters** (Details, Schedule, etc.) | Plain `QObject` | Do NOT connect to controller signals directly. They receive data from coordinator via `set_talent()`. No cleanup needed. |

> [!NOTE]
> Sub-presenters are owned by the coordinator (passed as `parent`). When the coordinator is cleaned up, Qt automatically destroys child QObjects. Sub-presenters only connect to their widget's local signals, which are destroyed with the widget.

### Component: New Presenter Files

#### [NEW] [hiring_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/hiring_presenter.py)

Extracted from `TalentProfilePresenter`. Handles:
- `HiringWidget` signals: `hire_confirmed`, `preview_cost_requested`, `sponsor_tour_requested`, `contract_*`
- Methods: `refresh_available_roles()`, `_calculate_bulk_hiring_preview()`, `_on_hire_confirmed()`, `_on_contract_*` 
- Tour sponsorship flow (`get_tour_sponsorship_preview()`, `_on_tour_sponsorship_confirmed()`)

```python
class HiringPresenter(QObject):
    """Handles hiring, contracts, and tour sponsorship for a talent."""
    
    def __init__(self, controller: IGameController, widget: HiringWidget, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget
        self._current_talent: Optional[Talent] = None
        self._connect_signals()
    
    def set_talent(self, talent: Optional[Talent]):
        """Called by coordinator when the active talent changes."""
        self._current_talent = talent
        if talent:
            self._refresh_available_roles()
            self._update_contract_options()
```

#### [NEW] [details_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/details_presenter.py)

Handles `DetailsWidget`. Minimal—mostly data formatting:
- Method: `_load_and_display_details(talent)`

#### [NEW] [schedule_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/schedule_presenter.py)

Handles `ScheduleWidget`:
- Method: `_load_and_display_schedule()` (includes ViewModel mapping)

#### [NEW] [preferences_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/preferences_presenter.py)

Handles `PreferencesWidget`:
- Method: `_load_and_display_preferences(talent)` (calls builder)

#### [NEW] [history_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/history_presenter.py)

Handles `HistoryWidget`:
- Signal routing: `open_scene_dialog_requested`
- Method: Load and display scene history

#### [NEW] [chemistry_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/chemistry_presenter.py)

Handles `ChemistryWidget`:
- Signals: `talent_profile_requested`, `smart_hover_*`, `smart_alt_clicked`
- Needs reference to `UIManager` for navigation

#### [NEW] [__init__.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile/__init__.py)

Package init exporting all presenters.

---

### Component: Refactored Coordinator

#### [MODIFY] [talent_profile_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/presenters/talent_profile_presenter.py)

Transform into coordinator role (~150 lines down from ~345):

```python
class TalentProfilePresenter(QObject):
    """Coordinates sub-presenters for the TalentProfileWindow."""
    open_talent_profile_requested = pyqtSignal(int)

    def __init__(self, controller, view, uimanager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.view = view
        self.uimanager = uimanager
        
        self.open_talents = {}  # Shared state
        self.current_talent_id = None
        
        # Initialize sub-presenters
        self._details_presenter = DetailsPresenter(controller, view.details_widget, self)
        self._schedule_presenter = SchedulePresenter(controller, view.schedule_widget, self)
        self._preferences_presenter = PreferencesPresenter(controller, view.preferences_widget, self)
        self._history_presenter = HistoryPresenter(controller, view.history_widget, uimanager, self)
        self._chemistry_presenter = ChemistryPresenter(controller, view.chemistry_widget, uimanager, self)
        self._hiring_presenter = HiringPresenter(controller, view.hiring_widget, self)
        
        self._connect_coordinator_signals()
    
    def _load_data_for_current_talent(self):
        """Notifies all sub-presenters of the new active talent."""
        talent = self.open_talents.get(self.current_talent_id)
        for presenter in self._sub_presenters:
            presenter.set_talent(talent)
```

Key changes:
- Remove all widget-specific signal connections (delegated to sub-presenters)
- Remove all `_load_and_display_*` methods (delegated)
- Keep: `open_talent()`, `switch_to_talent()`, `close_talent()`, `_on_setting_changed()` (theme coordination)
- Add: Broadcast mechanism to notify sub-presenters of talent/theme changes

---

## Verification Plan

### Automated Tests

No existing automated tests cover UI components (`tests/` contains only business logic tests like `test_revenue_calculator.py`). Writing meaningful UI tests for PyQt6 requires `pytest-qt` which isn't in the project.

**Recommendation**: Skip new automated tests for this refactoring. The changes are structural and best verified manually.

### Manual Verification

> [!NOTE]
> All manual testing should be done by launching the application and navigating to a talent profile.

#### Phase 1 Verification (Layout)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Launch app, open any talent profile | Window opens with new splitter layout (Details + Preferences left, Schedule + Hiring right, History/Chemistry tabbed bottom) |
| 2 | Resize panels by dragging splitter handles | Handles respond, panels resize smoothly |
| 3 | Click "Save" button with a layout name | Layout saves without error |
| 4 | Resize panels differently, click "Load" with saved name | Panels return to saved proportions |
| 5 | Close and reopen the profile window | Last-used layout is restored |
| 6 | Open a second talent tab, switch between tabs | Both tabs share the same layout, data updates correctly per talent |

#### Phase 2 Verification (Presenters)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open talent profile, verify all 6 widgets load data | Details, Skills, Schedule, Preferences, History, Chemistry all populated |
| 2 | Switch to a different talent tab | All widgets refresh with new talent's data |
| 3 | In Hiring widget, select a role and click "Assign" | Casting flow works, signals route correctly |
| 4 | In Chemistry widget, click another talent's name | Second talent's profile opens (cross-widget navigation works) |
| 5 | Change theme in settings | All widgets recolor correctly (theme broadcast works) |
| 6 | Change unit system in settings | Physical attributes label in Details updates (settings broadcast works) |

---

## Implementation Order

**Recommended sequence**:

1. **Phase 1 first** (layout changes are isolated to view layer)
2. **Phase 2 after Phase 1 is verified** (presenter changes touch more files but are lower risk)

This ordering minimizes the debugging surface at each step.
