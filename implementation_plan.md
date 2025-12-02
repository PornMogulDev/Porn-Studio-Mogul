### **Implementation Plan**

#### **1. Infrastructure: Asset Management**
We need a standardized way to store and load images.

*   **Directory Structure:**
    *   Create `assets/icons/`.
    *   Required assets: `lock_open.png` (or .svg), `lock_closed.png`, `inbox.png`, `inbox_unread.png`.
*   **New Service:** `ui/managers/icon_manager.py`.
    *   **Responsibility:** Load images from disk, convert them to `QIcon`, and cache them.
    *   **Theme Awareness:** (Optional but recommended) If using SVGs, this manager can colorize icons based on the `ThemeManager`'s current text or accent colors.
    *   **Methods:** `get_icon(name: str) -> QIcon`.

#### **2. Application Integration**
*   **Modify `application.py`:**
    *   Instantiate `IconManager` (passing `ThemeManager` if we want dynamic coloring).
    *   Inject `IconManager` into the `UIManager`.
*   **Modify `ui_manager.py`:**
    *   Update `create_main_window` to inject `IconManager` into `MainWindowView`.
    *   Update `create_call_sheet_dialog` (or the generic factory) to inject `IconManager` into the dialog, which passes it down to the sliders.

#### **3. Feature: Top Bar Inbox**
*   **Modify `ui/widgets/main_window/top_bar_widget.py`:**
    *   Update `__init__` to accept `IconManager`.
    *   Add the "Inbox" button here using a `QToolButton` (better for icons) or `QPushButton`.
    *   Set the icon using `icon_manager.get_icon("inbox")`.
    *   **Migration:** Remove the "Inbox" button from `ui/widgets/main_window/bottom_bar_widget.py`.
*   **Modify `ui/views/main_window_view.py`:**
    *   Re-route the `inbox_clicked` signal connection from `bottom_bar` to `top_bar`.
    *   Update `update_inbox_count`:
        *   Change the logic to update the `TopBarWidget` button.
        *   Logic change: Instead of just changing text, swap the icon to `inbox_unread.png` if count > 0, or overlay the number if using a custom paint event (simpler: Icon + Text "Inbox (3)").

#### **4. Feature: Call Sheet Lock Icons**
*   **Modify `ui/widgets/budget_slider_widget.py`:**
    *   **Constructor:** Accept `IconManager` as an argument.
    *   **UI Change:** Replace `self.checkbox_lock` (`QCheckBox`) with `self.btn_lock` (`QToolButton`).
    *   **Configuration:**
        *   Set `btn_lock.setCheckable(True)`.
        *   Set `btn_lock.setIcon(icon_manager.get_icon("lock_open"))`.
        *   Connect `toggled` signal to the existing logic.
    *   **Logic Update:**
        *   In the `toggled` handler, switch the icon:
            *   Checked (Locked) -> `lock_closed`.
            *   Unchecked (Unlocked) -> `lock_open`.
        *   Update `update_state` to visually reflect the locked state on the button rather than a checkbox checkmark.

#### **5. Cleanup**
*   Remove the orphaned "Inbox" logic from `BottomBarWidget`.
