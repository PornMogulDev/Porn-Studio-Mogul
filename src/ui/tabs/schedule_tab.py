from typing import List
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
    QLabel, QSpinBox
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from ui.view_models import ScheduleWeekViewModel
from ui.widgets.help_button import HelpButton

class ScheduleTab(QWidget):
    """
    A "dumb" view for displaying the weekly shooting schedule. It renders
    data provided by the ScheduleTabPresenter and emits signals for user actions.
    """
    # Signals emitted to the presenter
    year_changed = pyqtSignal(int)
    plan_bloc_requested = pyqtSignal()
    item_double_clicked = pyqtSignal(dict)
    help_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Control Bar ---
        menu_bar = QVBoxLayout()
        self.help_btn = HelpButton("schedule", self)
        menu_bar.addWidget(self.help_btn)
        
        top_bar = QHBoxLayout()
        self.plan_scene_btn = QPushButton("Plan Shooting Bloc")
        top_bar.addWidget(self.plan_scene_btn)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Viewing Year:"))
        self.year_spinbox = QSpinBox()
        top_bar.addWidget(self.year_spinbox)
        
        menu_bar.addLayout(top_bar)
        main_layout.addLayout(menu_bar)

        # --- Tree View ---
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.tree_view)
        
        # --- Signal Connections (View -> Presenter) ---
        self.year_spinbox.valueChanged.connect(self.year_changed)
        self.plan_scene_btn.clicked.connect(self.plan_bloc_requested)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        self.help_btn.help_requested.connect(self.help_requested)

    def update_year_selector(self, year: int, year_range_min: int, year_range_max: int):
        """Updates the year spinbox with a new value and range."""
        # Block signals to prevent the valueChanged signal from firing
        # while we programmatically set the value.
        self.year_spinbox.blockSignals(True)
        
        self.year_spinbox.setRange(year_range_min, year_range_max)
        self.year_spinbox.setValue(year)
        
        self.year_spinbox.blockSignals(False)

    def get_selected_year(self) -> int:
        """Allows the presenter to query the currently selected year."""
        return self.year_spinbox.value()

    def display_schedule(self, schedule_data: List[ScheduleWeekViewModel]):
        """
        Clears and rebuilds the entire schedule tree view from a list of
        view model objects.
        """
        self.model.clear()
        
        for week_vm in schedule_data:
            week_item = QStandardItem(week_vm.display_text)
            week_item.setEditable(False)
            week_item.setData(week_vm.user_data, Qt.ItemDataRole.UserRole)

            for bloc_vm in week_vm.blocs:
                bloc_item = QStandardItem(bloc_vm.display_text)
                bloc_item.setToolTip(bloc_vm.tooltip)
                bloc_item.setData(bloc_vm.user_data, Qt.ItemDataRole.UserRole)

                for scene_vm in bloc_vm.scenes:
                    scene_item = QStandardItem(scene_vm.display_text)
                    scene_item.setToolTip(scene_vm.tooltip)
                    scene_item.setData(scene_vm.user_data, Qt.ItemDataRole.UserRole)
                    bloc_item.appendRow(scene_item)
                
                week_item.appendRow(bloc_item)
            
            self.model.appendRow(week_item)
            
        self.tree_view.expandAll()

    def _on_item_double_clicked(self, index: QModelIndex):
        """
        Internal slot to handle a double-click. It extracts the item data
        and emits a signal for the presenter to handle the logic.
        """
        item = self.model.itemFromIndex(index)
        if item and (item_data := item.data(Qt.ItemDataRole.UserRole)):
            self.item_double_clicked.emit(item_data)