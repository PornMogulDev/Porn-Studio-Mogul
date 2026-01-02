\### Phase 1: Layout Migration (Docks → Splitters)



\*\*Objective\*\*: Replace the flexible but complex `QDockWidget` system with a predictable, nested `QSplitter` layout, and update the persistence logic to save splitter sizes instead of window state.



\*\*Files to Modify\*\*:

1\.  `src/ui/views/talent\_profile\_view.py`

2\.  `src/ui/managers/ui\_manager.py` (Type hinting updates only)



\*\*Reference Files\*\*:

\-   `src/ui/base\_game\_window.py`

\-   `src/data/settings\_manager.py`



---



\#### Step 1: View Class Restructuring (`talent\_profile\_view.py`)



1\.  \*\*Imports\*\*:

&nbsp;   \*   Add `QSplitter`, `QVBoxLayout`, `QTabWidget` to imports from `PyQt6.QtWidgets`.

&nbsp;   \*   Import `BaseGameWindow` from `ui.base\_game\_window`.

&nbsp;   \*   Remove unused imports related to docks (`QDockWidget`, `QMenuBar` if no longer used).



2\.  \*\*Inheritance\*\*:

&nbsp;   \*   Change class signature to: `class TalentProfileWindow(BaseGameWindow):`.

&nbsp;   \*   Update `\_\_init\_\_` to call `super().\_\_init\_\_(settings\_manager, parent)`.



3\.  \*\*Cleanup Old UI Components\*\*:

&nbsp;   \*   Remove `self.setDockNestingEnabled(True)`.

&nbsp;   \*   Remove `menu\_bar` and `view\_menu` creation.

&nbsp;   \*   Remove `self.addToolBar(...)` calls (we will add them to the layout manually).

&nbsp;   \*   Remove `\_add\_dock()` helper method.

&nbsp;   \*   Remove `saveState()` and `restoreState()` logic from `closeEvent` or initialization.



\#### Step 2: Implement New Layout (`talent\_profile\_view.py`)



1\.  \*\*Main Layout\*\*:

&nbsp;   \*   Create `self.main\_layout = QVBoxLayout(self)`.

&nbsp;   \*   Set contents margins to 0.



2\.  \*\*Toolbars\*\*:

&nbsp;   \*   Add `self.tab\_toolbar` to `self.main\_layout`.

&nbsp;   \*   Add `self.layout\_toolbar` to `self.main\_layout`.



3\.  \*\*Splitter Hierarchy\*\*:

&nbsp;   \*   Instantiate widgets (`details\_widget`, `preferences\_widget`, `schedule\_widget`, `hiring\_widget`, `history\_widget`, `chemistry\_widget`) directly (do not wrap in docks).

&nbsp;   \*   Create \*\*Left Splitter\*\* (Vertical): Add `details\_widget` and `preferences\_widget`.

&nbsp;   \*   Create \*\*Right Splitter\*\* (Vertical): Add `schedule\_widget` and `hiring\_widget`.

&nbsp;   \*   Create \*\*Top Splitter\*\* (Horizontal): Add Left Splitter and Right Splitter.

&nbsp;   \*   Create \*\*Bottom Tabs\*\* (`QTabWidget`):

&nbsp;       \*   Add `history\_widget` ("Scene History").

&nbsp;       \*   Add `chemistry\_widget` ("Chemistry").

&nbsp;   \*   Create \*\*Main Splitter\*\* (Vertical):

&nbsp;       \*   Add Top Splitter.

&nbsp;       \*   Add Bottom Tabs.

&nbsp;   \*   Add `Main Splitter` to `self.main\_layout`.



4\.  \*\*Initial Sizes\*\*:

&nbsp;   \*   Set sensible defaults for splitter sizes (e.g., `setSizes(\[600, 300])`) to ensure panels aren't collapsed by default if no save exists.



\#### Step 3: Layout Persistence (`talent\_profile\_view.py`)



1\.  \*\*Define Structure\*\*:

&nbsp;   \*   The save state will now be a dict: `{"main": \[int, int], "top": \[...], "left": \[...], "right": \[...]}`.



2\.  \*\*Refactor `\_save\_layout`\*\*:

&nbsp;   \*   Capture sizes: `sizes = {'main': self.main\_splitter.sizes(), ...}`.

&nbsp;   \*   Save this dict to `settings\_manager` via `set\_talent\_profile\_layouts`.



3\.  \*\*Refactor `\_load\_layout\_by\_name`\*\*:

&nbsp;   \*   Retrieve data from `settings\_manager`.

&nbsp;   \*   \*\*Validation\*\*: Check if the retrieved data is a `dict`. If it is a string (legacy `saveState` data), log a warning and return/ignore to avoid crashing.

&nbsp;   \*   Apply sizes: `self.main\_splitter.setSizes(data\['main'])`, etc.



4\.  \*\*Refactor `\_load\_last\_used\_layout`\*\*:

&nbsp;   \*   Ensure it calls the updated `\_load\_layout\_by\_name`.



\#### Step 4: Cleanup Integration (`ui\_manager.py`)



1\.  Update the type hint for `\_talent\_profile\_window\_singleton` from `TalentProfileWindow` (which previously implied QMainWindow behavior) to generic or the updated class, if explicit casting was used. (Likely just a check, Python is dynamic).

