import sys
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QObject
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QListWidget, QPushButton, QRadioButton, QButtonGroup,
    QFormLayout, QComboBox, QCheckBox, QDialogButtonBox,
    QMessageBox, QTreeView, QListWidgetItem
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

# --- Mock Objects for Standalone Testing ---
# These classes are simplified versions of what you likely have elsewhere.
# This allows the dialog to be run by itself for testing.

class MockSettingsManager:
    def __init__(self):
        self._presets = {}

    def get_talent_filter_presets(self):
        return self._presets

    def set_talent_filter_presets(self, presets):
        self._presets = presets

    def get_window_geometry(self, name):
        return None

    def set_window_geometry(self, name, geo):
        pass

class GeometryManagerMixin:
    """A mock mixin for standalone execution."""
    def _save_geometry(self):
        pass
    def _restore_geometry(self):
        self.resize(self.defaultSize)

class RangeFilterWidget(QGroupBox):
    """A mock RangeFilterWidget for standalone execution."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Min:"))
        layout.addWidget(QComboBox())
        layout.addWidget(QLabel("Max:"))
        layout.addWidget(QComboBox())
    
    def set_range(self, min_val, max_val): pass
    def set_values(self, min_val, max_val): pass
    def get_values(self): return 0, 100

# --- The Corrected Dialog Class ---

class TalentFilterDialog(GeometryManagerMixin, QDialog):
    filters_applied = pyqtSignal(dict)
    apply_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    apply_and_close_requested = pyqtSignal()
    go_to_toggled = pyqtSignal(bool)

    def __init__(self, ethnicities_hierarchy: dict, cup_sizes: list, nationalities: list, locations_by_region: dict, go_to_categories: list, current_filters: dict, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Advanced Talent Filter")
        self.defaultSize = QSize(700, 1000)

        self.ethnicities_hierarchy = ethnicities_hierarchy
        self.locations_by_region = locations_by_region
        self.all_nationalities = nationalities
        self.all_cup_sizes = cup_sizes
        self.go_to_categories = go_to_categories

        # --- KEY CHANGE 1: Create models as instance attributes ---
        self.ethnicity_model = QStandardItemModel()
        self.location_model = QStandardItemModel()

        self.setup_ui()
        self._populate_presets_combobox()
        self.connect_signals()

        self.presenter = TalentFilterPresenter(self, current_filters)
        self.presenter.load_initial_data()

        self._restore_geometry()
    
    def _populate_presets_combobox(self):
        current_text = self.preset_combo.currentText()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        presets = self.settings_manager.get_talent_filter_presets()
        if presets:
            self.preset_combo.addItems(sorted(presets.keys()))
        
        index = self.preset_combo.findText(current_text)
        if index != -1: self.preset_combo.setCurrentIndex(index)
        else: self.preset_combo.setCurrentIndex(-1)
        self.preset_combo.blockSignals(False)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Presets Group (omitted for brevity - no changes)
        presets_group = QGroupBox("Filter Presets"); presets_layout = QHBoxLayout(presets_group)
        presets_layout.addWidget(QLabel("Preset:")); self.preset_combo = QComboBox(); self.preset_combo.setEditable(True)
        self.preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); presets_layout.addWidget(self.preset_combo)
        self.load_preset_button = QPushButton("Load"); presets_layout.addWidget(self.load_preset_button)
        self.save_preset_button = QPushButton("Save"); presets_layout.addWidget(self.save_preset_button)
        self.delete_preset_button = QPushButton("Delete"); presets_layout.addWidget(self.delete_preset_button)
        main_layout.addWidget(presets_group)

        # Other UI groups (Go-To, Gender, Age, Skills, etc.) are unchanged
        # ... (imagine all the unchanged UI setup code is here) ...
        go_to_group = QGroupBox("Go-To List Filter"); go_to_layout = QVBoxLayout(go_to_group)
        self.go_to_only_checkbox = QCheckBox("Show only talent in Go-To Lists"); go_to_layout.addWidget(self.go_to_only_checkbox)
        self.category_combo = QComboBox(); self.category_combo.setEnabled(False); self.category_combo.addItem("Any", -1)
        for category in sorted(self.go_to_categories, key=lambda c: c['name']): self.category_combo.addItem(category['name'], category['id'])
        go_to_layout.addWidget(self.category_combo); main_layout.addWidget(go_to_group)
        gender_group = QGroupBox("Gender"); gender_layout = QHBoxLayout(gender_group)
        self.gender_any_radio = QRadioButton("Any"); self.gender_female_radio = QRadioButton("Female"); self.gender_male_radio = QRadioButton("Male")
        self.gender_button_group = QButtonGroup(); self.gender_button_group.addButton(self.gender_any_radio); self.gender_button_group.addButton(self.gender_female_radio); self.gender_button_group.addButton(self.gender_male_radio)
        gender_layout.addWidget(self.gender_any_radio); gender_layout.addWidget(self.gender_female_radio); gender_layout.addWidget(self.gender_male_radio)
        main_layout.addWidget(gender_group)
        age_group = QGroupBox("Age Range"); age_layout = QVBoxLayout(age_group); self.age_range = RangeFilterWidget(); self.age_range.set_range(18, 99); age_layout.addWidget(self.age_range); main_layout.addWidget(age_group)
        skills_group = QGroupBox("Core Skills"); skills_layout = QFormLayout(skills_group); self.perf_range = RangeFilterWidget(); self.perf_range.set_range(0, 100); self.act_range = RangeFilterWidget(); self.act_range.set_range(0, 100); self.stam_range = RangeFilterWidget(); self.stam_range.set_range(0, 100); self.dom_range = RangeFilterWidget(); self.dom_range.set_range(0, 100); self.sub_range = RangeFilterWidget(); self.sub_range.set_range(0, 100)
        skills_layout.addRow("Performance:", self.perf_range); skills_layout.addRow("Acting:", self.act_range); skills_layout.addRow("Stamina:", self.stam_range); skills_layout.addRow("Dominance:", self.dom_range); skills_layout.addRow("Submission:", self.sub_range)
        main_layout.addWidget(skills_group)
        phys_group = QGroupBox("Physical Attributes"); phys_layout = QFormLayout(phys_group); self.dick_range = RangeFilterWidget(); self.dick_range.set_range(0, 20); phys_layout.addRow("Dick Size (in):", self.dick_range); self.cup_list = QListWidget(); self.cup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection); 
        for cup in self.all_cup_sizes: self.cup_list.addItem(cup)
        cup_label = QLabel("Cup Size:"); cup_label.setAlignment(Qt.AlignmentFlag.AlignTop); phys_layout.addRow(cup_label, self.cup_list); main_layout.addWidget(phys_group)
        nationality_group = QGroupBox("Nationality"); nationality_layout = QVBoxLayout(nationality_group); self.nationality_list = QListWidget(); self.nationality_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self.nationality_list.addItems(sorted(self.all_nationalities)); nationality_layout.addWidget(self.nationality_list); main_layout.addWidget(nationality_group)

        # --- Location Filter (Tree View) ---
        location_group = QGroupBox("Location")
        location_layout = QVBoxLayout(location_group)
        self.location_tree = QTreeView()
        self.location_tree.setHeaderHidden(True)
        # --- KEY CHANGE 2: Set the model, then populate it ---
        self.location_tree.setModel(self.location_model)
        self._populate_tree_model(self.location_model, self.locations_by_region)
        location_layout.addWidget(self.location_tree)
        main_layout.addWidget(location_group)

        # --- Ethnicity Filter (Tree View) ---
        ethnicity_group = QGroupBox("Ethnicity")
        ethnicity_layout = QVBoxLayout(ethnicity_group)
        self.ethnicity_tree = QTreeView()
        self.ethnicity_tree.setHeaderHidden(True)
        # --- KEY CHANGE 2 (cont.): Set the model, then populate it ---
        self.ethnicity_tree.setModel(self.ethnicity_model)
        self._populate_tree_model(self.ethnicity_model, self.ethnicities_hierarchy)
        ethnicity_layout.addWidget(self.ethnicity_tree)
        main_layout.addWidget(ethnicity_group)

        main_layout.setStretchFactor(nationality_group, 3)
        main_layout.setStretchFactor(location_group, 4)
        main_layout.setStretchFactor(ethnicity_group, 4)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Reset | QDialogButtonBox.StandardButton.Close)
        button_box.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.apply_and_close_requested)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_requested)
        button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset_requested)
        button_box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.reject)
        main_layout.addWidget(button_box)

    # --- KEY CHANGE 3: The population method now acts on the model directly ---
    def _populate_tree_model(self, model: QStandardItemModel, data: dict):
        """Populates a QStandardItemModel with a checkable, two-level hierarchy."""
        model.clear() # Clear existing items before populating
        for parent_name, children in data.items():
            parent_item = QStandardItem(parent_name)
            parent_item.setCheckable(True)
            parent_item.setAutoTristate(True)
            
            for child_name in children:
                child_item = QStandardItem(child_name)
                child_item.setCheckable(True)
                parent_item.appendRow(child_item)
            
            model.appendRow(parent_item)

    def connect_signals(self):
        self.go_to_only_checkbox.stateChanged.connect(
            lambda state: self.go_to_toggled.emit(state == Qt.CheckState.Checked.value)
        )
        self.load_preset_button.clicked.connect(self._on_load_preset_clicked)
        self.save_preset_button.clicked.connect(self._on_save_preset_clicked)
        self.delete_preset_button.clicked.connect(self._on_delete_preset_clicked)
        
        # --- KEY CHANGE 4: Connect directly to the model attributes ---
        self.ethnicity_model.itemChanged.connect(self._on_tree_item_changed)
        self.location_model.itemChanged.connect(self._on_tree_item_changed)

    # _on_tree_item_changed remains the same, it's already correct.
    def _on_tree_item_changed(self, item: QStandardItem):
        model = item.model()
        if not model: return
        model.blockSignals(True)
        try:
            if not item.parent():
                state = item.checkState()
                for i in range(item.rowCount()):
                    child = item.child(i)
                    if child: child.setCheckState(state)
            else:
                parent = item.parent()
                checked_count = 0
                total_children = parent.rowCount()
                for i in range(total_children):
                    if parent.child(i).checkState() == Qt.CheckState.Checked:
                        checked_count += 1
                
                if checked_count == total_children:
                    parent.setCheckState(Qt.CheckState.Checked)
                elif checked_count == 0:
                    parent.setCheckState(Qt.CheckState.Unchecked)
                else:
                    parent.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            model.blockSignals(False)

    def load_filters(self, filters: dict):
        # Unchanged methods are not shown in full...
        # ...
        self._load_tree_filters(self.ethnicity_model, filters.get('ethnicities', []))
        self._load_tree_filters(self.location_model, filters.get('locations', []))

    def _load_tree_filters(self, model: QStandardItemModel, selected_items: list):
        if not model: return
        model.blockSignals(True)
        try:
            for row in range(model.rowCount()):
                parent_item = model.item(row)
                if not parent_item: continue
                
                all_children_checked = True
                any_child_checked = False

                for child_row in range(parent_item.rowCount()):
                    child_item = parent_item.child(child_row)
                    if child_item:
                        is_checked = child_item.text() in selected_items
                        child_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                        if not is_checked: all_children_checked = False
                        if is_checked: any_child_checked = True
                
                if parent_item.rowCount() > 0:
                    if all_children_checked:
                        parent_item.setCheckState(Qt.CheckState.Checked)
                    elif any_child_checked:
                        parent_item.setCheckState(Qt.CheckState.PartiallyChecked)
                    else:
                        parent_item.setCheckState(Qt.CheckState.Unchecked)
                else: # Parent is an end-node itself
                    is_checked = parent_item.text() in selected_items
                    parent_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)

        finally:
            model.blockSignals(False)


    def gather_current_filters(self) -> dict:
        # ...
        return {
            # ... other filters
            'ethnicities': self._gather_checked_from_model(self.ethnicity_model),
            'locations': self._gather_checked_from_model(self.location_model),
            # ... other filters
        }
    
    def _gather_checked_from_model(self, model: QStandardItemModel) -> list:
        checked_items = []
        if not model: return []
        for row in range(model.rowCount()):
            parent = model.item(row)
            if parent.rowCount() == 0:
                if parent.checkState() == Qt.CheckState.Checked:
                    checked_items.append(parent.text())
            else:
                for child_row in range(parent.rowCount()):
                    child = parent.child(child_row)
                    if child and child.checkState() == Qt.CheckState.Checked:
                        checked_items.append(child.text())
        return checked_items

    # --- Other methods (_on_load_preset_clicked, etc.) are unchanged ---
    # They are omitted here for brevity but should be kept in your file.
    def _on_load_preset_clicked(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name: return
        presets = self.settings_manager.get_talent_filter_presets()
        preset_data = presets.get(preset_name)
        if preset_data: self.load_filters(preset_data)
        else: QMessageBox.warning(self, "Load Error", f"Could not find preset named '{preset_name}'.")

    def _on_save_preset_clicked(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name: QMessageBox.warning(self, "Save Preset", "Please enter a name for the preset."); return
        current_filters = self.gather_current_filters()
        presets = self.settings_manager.get_talent_filter_presets()
        presets[preset_name] = current_filters
        self.settings_manager.set_talent_filter_presets(presets)
        self._populate_presets_combobox()
        self.preset_combo.setCurrentText(preset_name)
        QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' has been saved.")

    def _on_delete_preset_clicked(self):
        preset_name = self.preset_combo.currentText()
        if not preset_name: return
        reply = QMessageBox.question(self, "Delete Preset", f"Are you sure you want to delete the preset '{preset_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            presets = self.settings_manager.get_talent_filter_presets()
            if preset_name in presets:
                del presets[preset_name]
                self.settings_manager.set_talent_filter_presets(presets)
                self._populate_presets_combobox()

    def set_category_combo_enabled(self, is_enabled: bool):
        self.category_combo.setEnabled(is_enabled)
        if not is_enabled: self.category_combo.setCurrentIndex(0)
        
# A dummy presenter for standalone testing
class TalentFilterPresenter(QObject):
    def __init__(self, view, initial_filters):
        super().__init__()
        self.view = view
        self.initial_filters = initial_filters.copy()
        self._connect_signals()
    def load_initial_data(self):
        self.view.load_filters(self.initial_filters)
    def _connect_signals(self):
        self.view.apply_requested.connect(self.on_apply_requested)
    def on_apply_requested(self):
        print("Presenter: Apply requested.")
        current_filters = self.view.gather_current_filters()
        print(current_filters)
        self.view.filters_applied.emit(current_filters)


# --- Standalone Execution for Testing ---
if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Sample data for testing
    ethnicities = {
        "Asian": ["Chinese", "Japanese", "Korean"],
        "Black": ["African", "Caribbean"],
        "Caucasian": ["American", "European", "Irish"]
    }
    locations = {
        "North America": ["USA", "Canada", "Mexico"],
        "Europe": ["UK", "France", "Germany"]
    }
    cups = ["A", "B", "C", "D", "DD+"]
    nationalities = ["American", "British", "Canadian", "French"]
    categories = [{"id": 1, "name": "Favorites"}, {"id": 2, "name": "Top Performers"}]
    
    # Start with some filters checked
    initial_filters = {
        'ethnicities': ['Japanese', 'European'],
        'locations': ['USA']
    }

    # Create and show the dialog
    dialog = TalentFilterDialog(
        ethnicities_hierarchy=ethnicities,
        cup_sizes=cups,
        nationalities=nationalities,
        locations_by_region=locations,
        go_to_categories=categories,
        current_filters=initial_filters,
        settings_manager=MockSettingsManager()
    )
    dialog.show()
    sys.exit(app.exec())