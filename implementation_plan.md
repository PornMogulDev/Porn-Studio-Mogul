### 1. The Architecture: "Smart Entities"

We cannot simply paste strings like `"John Doe"` into widgets anymore. We need to attach metadata (the ID and Type) to the UI element holding the text.

We will create three core components:
1.  **`EntitySummaryCard`**: A reusable, borderless popup widget (the "Tooltip") that fetches and displays a snapshot of the entity (Avatar, Name, Status, Key Stats).
2.  **`InteractiveLabel`**: A replacement for `QLabel` for standalone text.
3.  **`SmartTableMixin` / `SmartListMixin`**: Logic to inject into Tables/Lists to handle mouse tracking and retrieving IDs from items.

### 2. Component Implementation

#### A. The Summary Card (The "Tooltip")
This is not a standard `QToolTip` (which only supports basic HTML). It is a `QWidget` with the `Qt.WindowType.ToolTip` flag.

```python
class EntitySummaryCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.layout = QVBoxLayout(self)
        # Add labels for Name, Stats, Status...
        # Styling via QSS to look like a floating card
    
    def load_talent(self, talent_dto):
        # Populate labels
        pass
```

#### B. The Interactive Label (For static text)
Used in forms, headers, and descriptions.

```python
class SmartLink(QLabel):
    link_clicked = pyqtSignal(str, int) # type, id

    def __init__(self, text, entity_type, entity_id, parent=None):
        super().__init__(text, parent)
        self.entity_type = entity_type
        self.entity_id = entity_id
        
        # Visual cues
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("color: #5A9Bcf; text-decoration: underline;") # Theme compliant link color

    def enterEvent(self, event):
        # 1. Fetch summary data via a global service/controller
        # 2. Position EntitySummaryCard near self.mapToGlobal(QPoint(0,0))
        # 3. Show card
        pass

    def leaveEvent(self, event):
        # Hide card
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                # Logic for Alt+Click
                pass
            else:
                self.link_clicked.emit(self.entity_type, self.entity_id)
```

#### C. Handling Tables and Lists
We cannot use `SmartLink` widgets inside `QTableWidget` cells easily (it's computationally heavy to have 1000 widgets in a grid). Instead, we use **`Qt.ItemDataRole.UserRole`** to store the ID inside the cell, and enable **Mouse Tracking**.

We create a Mixin for your Tables:

```python
class SmartHoverMixin:
    """Mixin for QTableWidget, QTreeWidget, QListWidget"""
    
    def setup_smart_hover(self):
        self.setMouseTracking(True)
        self.entered.connect(self._on_item_entered) # Fires when mouse moves over an item
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_entered(self, index):
        # 1. Get data: index.data(Qt.ItemDataRole.UserRole) -> returns ID
        # 2. If ID exists, show EntitySummaryCard at QCursor.pos()
        pass

    def _on_item_clicked(self, item):
        # Handle Alt+Click logic here
        pass
```

### 3. Implementation Plan

#### Step 1: The Data Service
We need a fast way to get "Summary" data without loading the heavy full profile.
*   **Action:** Add `get_talent_summary(id)` to `GameQueryService`.
*   **Return:** A lightweight DTO (`TalentSummaryViewModel`) containing just name, age, simple status, and thumbnail path.

#### Step 2: The UI Service (The "Pop-up Manager")
We don't want every label managing its own popup window instance.
*   **Action:** Create `TooltipManager` in `UIManager`.
*   **Logic:** It holds a single instance of `EntitySummaryCard`. It has a method `show_tooltip(global_pos, entity_type, entity_id)`.

#### Step 3: Refactoring Views
This is the "grunt work" phase.
1.  **Tables:** Anywhere we populate a table with a talent name (e.g., `ScenePlanner`, `TalentList`), we must set `item.setData(Qt.ItemDataRole.UserRole, talent_id)`.
2.  **Labels:** Replace specific `QLabel`s (like in the Scene Planner "Cast" list or Email sender) with `SmartLink`.

#### Step 4: Input Handling
*   **Standard Click:** Opens the profile (existing logic).
*   **Alt+Click:** We can reserve this for "Quick Actions" (e.g., instantly add to a casting shortlist) or just make it the specific trigger to open the full window if you want standard clicks to select rows.

### Feasibility Summary

*   **Performance:** High. Using `UserRole` in tables is zero-cost. Using `enterEvent` on labels is cheap.
*   **Complexity:** Moderate. Requires refactoring how lists are populated (adding the ID to the item data).
*   **UX Impact:** Massive improvement. It creates a "hyperlinked" feel to the application, making navigation significantly faster.