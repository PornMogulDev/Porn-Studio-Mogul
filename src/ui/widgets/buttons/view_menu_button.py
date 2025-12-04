from typing import List, Dict
from PyQt6.QtWidgets import QToolButton, QMenu
from PyQt6.QtCore import pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QIcon, QMouseEvent

from ui.managers.icon_manager import IconManager

class StayOpenMenu(QMenu):
    """A QMenu that doesn't close when an item is clicked."""
    def mouseReleaseEvent(self, e: QMouseEvent):
        action = self.actionAt(e.pos())
        if action and action.isEnabled():
            action.trigger()
            # Do not call super().mouseReleaseEvent(e) to prevent closing
        else:
            super().mouseReleaseEvent(e)

class ViewMenuButton(QToolButton):
    """
    A reusable QToolButton that shows a non-closing menu to toggle visibility.
    Designed to manage the visibility of UI panels or table columns.
    Uses IconManager for theming, specifically using a custom 'tick_icon'.
    """
    # Emits the item's unique key and its new target visibility state
    visibility_changed = pyqtSignal(str, bool)

    def __init__(self, icon_manager: IconManager, parent=None):
        super().__init__(parent)
        self.icon_manager = icon_manager
        self._items: List[Dict] = []
        
        self._setup_ui()
        
        # We handle the menu manually to allow dynamic regeneration on every click
        self.clicked.connect(self._show_menu)

    def _setup_ui(self):
        """Sets the default appearance of the button."""
        self.setToolTip("Show/Hide Columns")
        self.refresh_icon()

    def refresh_icon(self):
        """Refreshes the icon from the manager (e.g. on font/theme change)."""
        self.icon_manager.apply_icon(self, "eye_icon", "accent")

    def set_items(self, items: List[Dict]):
        """
        Populates the button's menu with a list of manageable items.

        Args:
            items: A list of dictionaries. Each must contain:
                   - 'key' (str): Unique identifier.
                   - 'name' (str): Display text.
                   - 'visible' (bool): Checked state.
                   - 'enabled' (bool, optional): If False, item is grayed out.
                   - 'tooltip' (str, optional): Tooltip text for the menu item.
        """
        self._items = items

    def update_item_visibility(self, key: str, visible: bool):
        """
        Programmatically updates the visibility state of a menu item in the internal list.
        This ensures the next time the menu is opened, it shows the correct state.
        This does not emit a signal.
        """
        for item in self._items:
            if item.get('key') == key:
                item['visible'] = visible
                break

    def _show_menu(self):
        """Creates and displays the menu based on the current internal items state."""
        if not self._items:
            return

        menu = StayOpenMenu(self)
        menu.setToolTipsVisible(True)

        for item in self._items:
            key = item.get('key')
            name = item.get('name', 'Unnamed Item')
            is_visible = item.get('visible', True)
            is_enabled = item.get('enabled', True)
            tooltip = item.get('tooltip')

            if not key:
                continue

            action = QAction(name, menu)
            action.setEnabled(is_enabled)
            
            # Use custom tick icon logic instead of native checkable
            if is_visible:
                action.setIcon(self.icon_manager.get_icon("tick_icon", "accent"))
            else:
                action.setIcon(QIcon()) # Empty icon for alignment
            
            if tooltip:
                action.setToolTip(tooltip)
                action.setStatusTip(tooltip)

            # Define logic to handle immediate toggle without closing
            def on_trigger(checked, k=key, act=action):
                # 1. Find the current state in the mutable items list
                current_item = next((i for i in self._items if i['key'] == k), None)
                if current_item:
                    # 2. Toggle state
                    new_state = not current_item['visible']
                    current_item['visible'] = new_state
                    
                    # 3. Update UI immediately
                    if new_state:
                        act.setIcon(self.icon_manager.get_icon("tick_icon", "accent"))
                    else:
                        act.setIcon(QIcon())
                        
                    # 4. Emit signal to application
                    self.visibility_changed.emit(k, new_state)

            action.triggered.connect(on_trigger)
            
            menu.addAction(action)

        # Position the menu just below the button
        button_pos = self.mapToGlobal(QPoint(0, self.height()))
        menu.exec(button_pos)