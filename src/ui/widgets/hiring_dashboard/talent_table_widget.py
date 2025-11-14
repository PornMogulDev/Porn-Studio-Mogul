from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QTableView, QHeaderView, QLabel, QCheckBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex
from typing import List, Dict

from ui.models.talent_table_model import TalentTableModel

class HiringTalentTableWidget(QWidget):
    """Widget displaying filtered talent available for hiring."""
    talent_selected = pyqtSignal(object)  # Talent
    name_filter_changed = pyqtSignal(str)
    additional_filters_changed = pyqtSignal(dict)
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by name:"))
        self.name_filter_input = QLineEdit()
        self.name_filter_input.textChanged.connect(self.name_filter_changed.emit)
        filter_layout.addWidget(self.name_filter_input)
        layout.addLayout(filter_layout)
        
        # Additional filters group (collapsed by default)
        filters_group = QGroupBox("Additional Filters")
        filters_layout = QVBoxLayout(filters_group)
        
        # Age range
        age_layout = QHBoxLayout()
        age_layout.addWidget(QLabel("Age:"))
        from PyQt6.QtWidgets import QSpinBox
        self.age_min_spin = QSpinBox()
        self.age_min_spin.setRange(18, 99)
        self.age_min_spin.setValue(18)
        self.age_min_spin.setPrefix("Min: ")
        age_layout.addWidget(self.age_min_spin)
        
        self.age_max_spin = QSpinBox()
        self.age_max_spin.setRange(18, 99)
        self.age_max_spin.setValue(99)
        self.age_max_spin.setPrefix("Max: ")
        age_layout.addWidget(self.age_max_spin)
        age_layout.addStretch()
        filters_layout.addLayout(age_layout)
        
        # Go-To list filter
        goto_layout = QHBoxLayout()
        self.goto_checkbox = QCheckBox("Only show Go-To talent")
        goto_layout.addWidget(self.goto_checkbox)
        goto_layout.addStretch()
        filters_layout.addLayout(goto_layout)
        
        filters_group.setCheckable(True)
        filters_group.setChecked(False)
        layout.addWidget(filters_group)
        
        # Connect filter changes
        self.age_min_spin.valueChanged.connect(self._emit_filter_change)
        self.age_max_spin.valueChanged.connect(self._emit_filter_change)
        self.goto_checkbox.stateChanged.connect(self._emit_filter_change)
        filters_group.toggled.connect(self._emit_filter_change)
        
        # Talent table
        self.talent_table_view = QTableView()
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        layout.addWidget(self.talent_table_view)
        
        # Connect double-click
        self.talent_table_view.doubleClicked.connect(self._on_talent_double_clicked)
        
        # Status label
        self.status_label = QLabel("Select a role to view available talent")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def initialize_model(self, cup_size_order):
        """Initialize the table model with dependencies."""
        self.talent_model = TalentTableModel(
            settings_manager=self.settings_manager,
            cup_size_order=cup_size_order,
            mode='casting'
        )
        self.talent_table_view.setModel(self.talent_model)
        self._configure_table_headers()
    
    def _configure_table_headers(self):
        """Configure column widths."""
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Alias
    
    def update_talent_table(self, talent_data: List[Dict]):
        """
        Update table with talent data.
        talent_data: List of dicts with 'talent' and 'demand' keys
        """
        if hasattr(self, 'talent_model'):
            self.talent_model.update_data(talent_data)
            count = len(talent_data)
            self.status_label.setText(f"Showing {count} available talent")
    
    def _on_talent_double_clicked(self, index: QModelIndex):
        """Handle double-click on talent."""
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.talent_selected.emit(talent)
    
    def _emit_filter_change(self):
        """Emit signal when additional filters change."""
        filters = {
            'age_min': self.age_min_spin.value(),
            'age_max': self.age_max_spin.value(),
            'go_to_list_only': self.goto_checkbox.isChecked()
        }
        self.additional_filters_changed.emit(filters)
    
    def get_current_filters(self) -> dict:
        """Get current filter state."""
        return {
            'name': self.name_filter_input.text(),
            'age_min': self.age_min_spin.value(),
            'age_max': self.age_max_spin.value(),
            'go_to_list_only': self.goto_checkbox.isChecked()
        }