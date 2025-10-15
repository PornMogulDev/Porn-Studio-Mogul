from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QRadioButton, QSpinBox, QDialogButtonBox, QGroupBox, QLabel,
    QPushButton, QCheckBox, QMessageBox
)
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class SceneFilterDialog(GeometryManagerMixin, QDialog):
    filters_applied = pyqtSignal(dict)

    def __init__(self, categories: list, orientations: list, mode: str, current_filters: dict, controller, parent=None):
        super().__init__(parent)
        self.mode = mode # 'thematic', 'physical', or 'action'
        self.current_filters = current_filters
        self.categories = categories
        self.orientations = orientations
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.applied_filters = {}

        self.setWindowTitle(f"Advanced {self.mode.title()} Tag Filter")
        self.setMinimumWidth(300)
        self.setup_ui()
        self.load_filters()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        # --- Favorites ---
        fav_group = QGroupBox("Favorites")
        fav_layout = QVBoxLayout(fav_group)
        self.favorites_only_checkbox = QCheckBox("Show Only Favorites")
        self.reset_favorites_button = QPushButton(f"Reset {self.mode.title()} Favorites")
        fav_layout.addWidget(self.favorites_only_checkbox)
        fav_layout.addWidget(self.reset_favorites_button)
        main_layout.addWidget(fav_group)
        # --- Categories ---
        cat_group = QGroupBox("Filter by Category")
        cat_layout = QVBoxLayout(cat_group)
        self.category_list = QListWidget(); self.category_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for category in self.categories:
            item = QListWidgetItem(category)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.category_list.addItem(item)
        cat_layout.addWidget(self.category_list)
        match_group = QGroupBox("Category Match Type")
        match_layout = QVBoxLayout(match_group)
        self.any_radio = QRadioButton("Match Any Category (OR)"); self.all_radio = QRadioButton("Match All Categories (AND)")
        match_layout.addWidget(self.any_radio); match_layout.addWidget(self.all_radio)
        cat_layout.addWidget(match_group)
        main_layout.addWidget(cat_group)
        # --- Orientations ---
        if self.orientations:
            orient_group = QGroupBox("Filter by Orientation")
            orient_layout = QVBoxLayout(orient_group)
            self.orientation_list = QListWidget(); self.orientation_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            for orientation in self.orientations:
                item = QListWidgetItem(orientation)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.orientation_list.addItem(item)
            orient_layout.addWidget(self.orientation_list)
            main_layout.addWidget(orient_group)
        # --- Participants (actions only) ---
        if self.mode == 'action':
            parts_group = QGroupBox("Filter by Participants")
            parts_layout = QHBoxLayout(parts_group)
            self.min_spin = QSpinBox(); self.min_spin.setRange(1, 40); self.min_spin.setValue(1)
            self.max_spin = QSpinBox(); self.max_spin.setRange(1, 40); self.max_spin.setValue(10)
            parts_layout.addWidget(QLabel("Min:")); parts_layout.addWidget(self.min_spin)
            parts_layout.addStretch(); parts_layout.addWidget(QLabel("Max:")); parts_layout.addWidget(self.max_spin)
            main_layout.addWidget(parts_group)
        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._apply_filters); button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.reset_favorites_button.clicked.connect(self._reset_favorites)

    def load_filters(self):
        self.favorites_only_checkbox.setChecked(self.current_filters.get('show_favorites_only', False))
        selected_categories = self.current_filters.get('categories', [])
        for i in range(self.category_list.count()):
            item = self.category_list.item(i)
            if item.text() in selected_categories: item.setCheckState(Qt.CheckState.Checked)
        if self.current_filters.get('match_mode', 'any') == 'all': self.all_radio.setChecked(True)
        else: self.any_radio.setChecked(True)
        if self.orientations:
            selected_orientations = self.current_filters.get('orientations', [])
            for i in range(self.orientation_list.count()):
                item = self.orientation_list.item(i)
                if item.text() in selected_orientations: item.setCheckState(Qt.CheckState.Checked)
        if self.mode == 'action':
            self.min_spin.setValue(self.current_filters.get('min_participants', 1))
            self.max_spin.setValue(self.current_filters.get('max_participants', 10))

    def _apply_filters(self):
        filters = {}
        filters['show_favorites_only'] = self.favorites_only_checkbox.isChecked()
        selected_cats = [self.category_list.item(i).text() for i in range(self.category_list.count()) if self.category_list.item(i).checkState() == Qt.CheckState.Checked]
        filters['categories'] = selected_cats
        filters['match_mode'] = 'all' if self.all_radio.isChecked() else 'any'
        if self.orientations:
            selected_orients = [self.orientation_list.item(i).text() for i in range(self.orientation_list.count()) if self.orientation_list.item(i).checkState() == Qt.CheckState.Checked]
            filters['orientations'] = selected_orients
        if self.mode == 'action':
            filters['min_participants'] = self.min_spin.value()
            filters['max_participants'] = self.max_spin.value()
        self.applied_filters = filters
        self.filters_applied.emit(filters)
        self.accept()

    def get_filters(self) -> dict: return self.applied_filters

    def _reset_favorites(self):
        reply = QMessageBox.question(self, f"Reset {self.mode.title()} Favorites",
                                     f"Are you sure you want to reset all your favorite {self.mode} tags?\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.controller.reset_favorite_tags(self.mode)