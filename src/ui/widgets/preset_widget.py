from typing import List, Optional, Set
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import pyqtSignal

class PresetWidget(QWidget):
    load_requested = pyqtSignal(str)
    save_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._known_presets: Set[str] = set()
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Preset:"))
        
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(True)
        self.preset_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.preset_combo.setToolTip("Select a saved preset or type a new name to save.")
        self.preset_combo.setMinimumWidth(150)
        
        # Default placeholder
        self.preset_combo.lineEdit().setPlaceholderText("No presets found")
        
        layout.addWidget(self.preset_combo)
        
        self.load_btn = QPushButton("Load")
        self.save_btn = QPushButton("Save")
        self.delete_btn = QPushButton("Delete")
        
        layout.addWidget(self.load_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.delete_btn)

        layout.addStretch()

        # Connect internal signal for smart button state
        self.preset_combo.editTextChanged.connect(self._update_button_states)

        # Connect external actions
        self.load_btn.clicked.connect(self._on_load)
        self.save_btn.clicked.connect(self._on_save)
        self.delete_btn.clicked.connect(self._on_delete)
        
        # Initialize button states (all disabled initially)
        self._update_button_states("")

    def populate_presets(self, presets: List[str], current_selection: Optional[str] = None):
        """Updates the combo box items and handles placeholder text."""
        self._known_presets = set(presets)
        
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        
        if not presets:
            self.preset_combo.lineEdit().setPlaceholderText("No presets found")
            self.preset_combo.setCurrentIndex(-1)
        else:
            self.preset_combo.lineEdit().setPlaceholderText("Choose preset or type name...")
            self.preset_combo.addItems(sorted(presets))
            
            if current_selection:
                index = self.preset_combo.findText(current_selection)
                if index != -1:
                    self.preset_combo.setCurrentIndex(index)
                else:
                    # Handle case where selection might be a new name typed by user during save
                    self.preset_combo.setCurrentText(current_selection)
            else:
                # Clear selection to show placeholder
                self.preset_combo.setCurrentIndex(-1)
                self.preset_combo.setCurrentText("")

        self.preset_combo.blockSignals(False)
        
        # Force button update based on the new state
        self._update_button_states(self.preset_combo.currentText())

    def _update_button_states(self, text: str):
        """
        Enables/Disables buttons based on the current text input.
        """
        clean_text = text.strip()
        has_text = len(clean_text) > 0
        is_known_preset = clean_text in self._known_presets
        
        # Save: Enabled if there is any text (new or existing)
        self.save_btn.setEnabled(has_text)
        
        # Load/Delete: Enabled only if the text matches an existing preset
        self.load_btn.setEnabled(is_known_preset)
        self.delete_btn.setEnabled(is_known_preset)

    def _on_load(self): self.load_requested.emit(self.preset_combo.currentText())
    def _on_save(self): self.save_requested.emit(self.preset_combo.currentText())
    def _on_delete(self): self.delete_requested.emit(self.preset_combo.currentText())