from PyQt6.QtWidgets import QTabWidget, QMainWindow, QApplication, QMenu
from PyQt6.QtCore import Qt, QPoint, QEvent, QRect, QSize
from PyQt6.QtGui import QAction

from data.settings_manager import SettingsManager
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class DetachableTabWidget(QTabWidget):
    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.defaultSize = QSize(1366, 768)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_tab_context_menu)
        self.detached_windows = {}
        self.settings_manager = settings_manager

    def show_tab_context_menu(self, pos: QPoint):
        """Shows a context menu when a tab is right-clicked."""
        tab_bar = self.tabBar()
        # The position is relative to the QTabWidget, so we map it to the tab bar
        tab_bar_pos = tab_bar.mapFromParent(pos)
        index = tab_bar.tabAt(tab_bar_pos)
        
        if index != -1:
            menu = QMenu(self)
            detach_action = menu.addAction("Detach Tab")
            
            global_pos = self.mapToGlobal(pos)
            detach_action.triggered.connect(
                lambda: self.detach_tab(index, global_pos)
            )
            
            menu.exec(global_pos)

    def detach_tab(self, index, pos):
        widget = self.widget(index)
        title = self.tabText(index)
        self.removeTab(index)

        window = DetachedTabWindow(widget, title, self, self.settings_manager, self.parent())
        window_name = window._get_window_name()
        if not self.settings_manager.get_window_geometry(window_name):
            window.move(pos)
        widget.show()
        window.show()
        self.detached_windows[title] = window

    def reattach_tab(self, title, widget):
        index = self.addTab(widget, title)
        self.setCurrentIndex(index)
        self.detached_windows.pop(title, None)

    def is_pos_over_tab_bar(self, global_pos: QPoint) -> bool:
        """Checks if the given global position is over this widget's tab bar."""
        tab_bar = self.tabBar()
        # Get the top-left corner of the tab bar in global coordinates
        global_tab_bar_pos = tab_bar.mapToGlobal(QPoint(0, 0))
        # Create a rectangle representing the tab bar in global coordinates
        global_tab_bar_rect = QRect(global_tab_bar_pos, tab_bar.size())
        return global_tab_bar_rect.contains(global_pos)

class DetachedTabWindow(QMainWindow, GeometryManagerMixin):
    def __init__(self, widget, title, parent_tab_widget, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.parent_tab_widget = parent_tab_widget
        self.widget = widget
        self.settings_manager = settings_manager
        self.setCentralWidget(widget)
        # Set a reasonable default size for the detached window
        # based on the content widget's preferred size.
        self.resize(widget.sizeHint())
        self._restore_geometry()
    
    def _get_window_name(self) -> str:
        """
        Overrides the mixin's method to provide a unique name for each detached tab
        window, ensuring their geometries are saved independently.
        """
        return f"DetachedTab_{self.windowTitle()}"

    def closeEvent(self, event):
        self._save_geometry()
        super().closeEvent(event)
        if event.isAccepted():
            widget = self.takeCentralWidget()
            if widget:
                    self.parent_tab_widget.reattach_tab(self.windowTitle(), widget)