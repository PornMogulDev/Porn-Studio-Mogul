from typing import List, Dict
from PyQt6.QtWidgets import QPushButton, QMenu, QWidgetAction, QCheckBox
from PyQt6.QtCore import pyqtSignal, Qt, QPoint, QSize
from PyQt6.QtGui import QIcon

class ViewMenuButton(QPushButton):
    """
    A reusable QPushButton that shows a non-closing, checkable menu.
    This button is designed to manage the visibility of a list of items,
    such as UI panels or table columns. It emits a signal when an item's
    visibility is changed by the user.
    """
    # Emits the item's unique key and its new visibility state (True for visible)
    visibility_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[Dict] = []
        self._setup_ui()
        self.clicked.connect(self._show_menu)

    def _setup_ui(self):
        """Sets the default appearance of the button."""
        style = self.style()
        icon = style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView)
        self.setIcon(QIcon(icon))
        self.setToolTip("Show/Hide Items")
        self.setFixedSize(QSize(32, 32))

    def set_items(self, items: List[Dict]):
        """
        Populates the button's menu with a list of manageable items.

        Args:
            items: A list of dictionaries, where each dictionary represents an
                   item and must contain 'key' (str), 'name' (str), and
                   'visible' (bool). An optional 'enabled' (bool) key can
                   be used to make an item non-toggleable.
        """
        self._items = items

    def _show_menu(self):
        """Creates and displays the checkable menu based on the current items."""
        if not self._items:
            return

        menu = QMenu(self)

        for item in self._items:
            key = item.get('key')
            name = item.get('name', 'Unnamed Item')
            is_visible = item.get('visible', True)
            is_enabled = item.get('enabled', True)

            if not key:
                continue

            # Use QWidgetAction to embed a QCheckBox, which prevents the menu
            # from closing when an item is clicked.
            widget_action = QWidgetAction(menu)
            checkbox = QCheckBox(name, menu)
            checkbox.setChecked(is_visible)
            checkbox.setEnabled(is_enabled)

            # Connect the state change signal to our handler
            checkbox.stateChanged.connect(
                lambda state, k=key: self.visibility_changed.emit(
                    k, state == Qt.CheckState.Checked.value
                )
            )
            widget_action.setDefaultWidget(checkbox)
            menu.addAction(widget_action)

        # Position the menu just below the button for a natural feel
        button_pos = self.mapToGlobal(QPoint(0, self.height()))
        menu.exec(button_pos)