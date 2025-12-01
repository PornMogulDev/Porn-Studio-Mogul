### 1. Critical Performance Bottleneck
**File:** `link_hover_delegate.py`

**Issue:** Instantiating `QTextDocument` inside `editorEvent` on `MouseMove`.
`editorEvent` fires continuously as the mouse moves across a cell. Creating, setting HTML, and laying out a `QTextDocument` is a heavy operation. Doing this hundreds of times per second will cause the UI to stutter, especially in the `ScenesTab` if the list is long.

**Solution:**
1.  **Rect Check First:** Inside `editorEvent`, check if the mouse position is even within the bounding box of the text before spinning up a `QTextDocument`.
2.  **Optimization:** Since you are using a standard `QTableView`, the `QStyleOptionViewItem` passed to `editorEvent` usually does not contain the correct font/rect context immediately.
3.  **Refactor:** Only perform the hit test if the mouse has moved a significant distance or implement a simple caching mechanism for the layout if the text hasn't changed.

### 2. Weak Patterns & Reusability
**Files:** `smart_table_view.py` and `smart_table_widget.py`

**Issue A: Hardcoded Column Logic**
Both classes contain this logic:
```python
if index.isValid() and index.column() == 0:
```
This restricts the "Smart" functionality exclusively to the first column. If you ever want to use this in a table where the name is in Column 1 (e.g., an ID in Col 0), this class breaks.

**Solution:**
Add a property `self._smart_columns = {0}` (a set of integers).
Change the check to: `if index.column() in self._smart_columns:`.
Add a method `set_smart_column(index: int)` to allow configuration from the View/Tab setup.

**Issue B: Code Duplication**
`SmartTableView` and `SmartTableWidget` share 90% of their logic (Event handling, Signal emission).
**Solution:** Create a Mixin class (`SmartHoverMixin`) that handles the mouse tracking and event filtering, then inherit from it in both the View and Widget.

### 3. Logical Inconsistencies
**Files:** `ui_manager.py` vs `details_widget.py`

**Issue: Syntax Compatibility**
In `details_widget.py`:
```python
self.location_label.setText(f'{data['current_location']} (on tour from {data['base_location']})')
```
You are using single quotes for the f-string *and* single quotes for the dictionary keys inside the expression.
*   **Context:** This syntax is only valid in Python 3.12+. If the project runs on Python 3.10 or 3.11, this will crash with a `SyntaxError`.
*   **Fix:** Use double quotes for the f-string wrapper: `f"{data['current_location']} ..."`

**Issue: Signal Naming**
*   `SmartLabel` uses `profile_requested`.
*   `SmartTableView` uses `smart_alt_clicked`.
*   `ScenesTab` uses `cast_alt_clicked`.
*   `LinkHoverDelegate` uses `link_alt_clicked`.
**Fix:** Standardize these signal names (e.g., `entity_action_triggered` or `profile_requested`) across all widgets to make the API predictable.

### 4. UX & Boundary Handling
**File:** `ui_manager.py`

**Issue:** Tooltip Off-screen Clippping
```python
# Position offset: slightly to the right and down
card.move(global_pos.x() + 15, global_pos.y() + 15)
```
If the user hovers over a name on the far right or bottom edge of the screen, the `EntitySummaryCard` will spawn off-screen or partially clipped.

**Solution:**
Calculate the screen geometry in `show_talent_summary`:
```python
screen_geo = QApplication.screenAt(global_pos).geometry()
card_geo = card.geometry()
x = global_pos.x() + 15
y = global_pos.y() + 15

# Check Right Edge
if x + card_geo.width() > screen_geo.right():
    x = global_pos.x() - card_geo.width() - 5 

# Check Bottom Edge
if y + card_geo.height() > screen_geo.bottom():
    y = global_pos.y() - card_geo.height() - 5

card.move(x, y)
```

### 5. Architectural bloat in UIManager
**File:** `ui_manager.py`

**Issue:** The `UIManager` is becoming a "God Object."
It is now handling high-level window management *and* low-level mouse hover logic (`show_talent_summary`, `hide_talent_summary`).
**Recommendation:**
Consider moving the Summary Card logic into a dedicated `TooltipManager` or `OverlayManager` service. The `UIManager` can initialize it, but shouldn't handle the nitty-gritty of moving widgets based on mouse coordinates.

### 6. Missing Implementation Details
**File:** `scenes_tab.py`

**Issue:** Delegate signals are connected, but `ScenesTab` doesn't forward them to `UIManager`.
In `setup_ui`:
```python
self.link_delegate.link_hover_entered.connect(self.cast_hover_entered)
# ...
```
The `ScenesTab` defines the signals `cast_hover_entered` etc., but I do not see where `ScenesTab` itself connects *its* signals to the `UIManager` (likely in `ScenesTabPresenter` or `MainWindowView`).
**Check:** Ensure the Presenter or the Main Window is actually catching `ScenesTab.cast_hover_entered` and calling `ui_manager.show_talent_summary`. Based on the files provided, this connection seems missing.

### Summary of Required Changes

1.  **Refactor `LinkHoverDelegate`**: Add hit-testing/caching to prevent `QTextDocument` creation on every pixel of mouse movement.
2.  **Fix Syntax**: Correct the f-string quotes in `details_widget.py`.
3.  **Boundary Checks**: Add screen boundary logic to `ui_manager.show_talent_summary`.
4.  **Flexible Columns**: Remove `index.column() == 0` hardcoding; allow configuration.
5.  **Signal Wiring**: Verify `ScenesTab` signals actually reach the `UIManager`.

**Action Item:**
Please apply the f-string fix immediately to prevent syntax errors, then prioritize the `LinkHoverDelegate` optimization, as that will cause noticeable lag in the application.