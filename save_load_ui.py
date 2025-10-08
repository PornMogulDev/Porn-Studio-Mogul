from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QPushButton, 
    QHBoxLayout, QLabel, QLineEdit, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from datetime import datetime

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin


class SaveLoadDialog(GeometryManagerMixin, QDialog):
    save_selected = pyqtSignal(str)

    def __init__(self, controller, mode='load', parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.save_manager = self.controller.save_manager
        self.mode = mode  # 'load' or 'save'
        self.setup_ui()
        self._restore_geometry()
    
    def setup_ui(self):
        self.setWindowTitle("Save/Load Game")
        self.setMinimumSize(400, 500)
        
        layout = QVBoxLayout(self)
        
        # Mode indicator
        mode_label = QLabel(f"{'Save' if self.mode == 'save' else 'Load'} Game")
        mode_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(mode_label)
        
        # Save name input (for save mode)
        if self.mode == 'save':
            name_label = QLabel("Save Name:")
            layout.addWidget(name_label)
            
            self.save_name_input = QLineEdit()
            self.save_name_input.setPlaceholderText("Enter save name or select from list to overwrite")
            layout.addWidget(self.save_name_input)
        
        # Save list
        list_label = QLabel("Existing Saves:")
        layout.addWidget(list_label)
        
        self.save_list = QListWidget()
        layout.addWidget(self.save_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        if self.mode == 'save':
            confirm_btn = QPushButton("Save Game")
            confirm_btn.clicked.connect(self.on_save)
        else:
            confirm_btn = QPushButton("Load Game")
            confirm_btn.clicked.connect(self.on_load)
            confirm_btn.setEnabled(False)  # Disabled until selection
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        # Delete button (for both modes)
        delete_btn = QPushButton("Delete Save")
        delete_btn.clicked.connect(self.on_delete)
        delete_btn.setEnabled(False)
        
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        # Store button references
        self.confirm_btn = confirm_btn
        self.delete_btn = delete_btn
        
        # Connect list selection
        self.save_list.itemSelectionChanged.connect(self.on_selection_changed)
        
        self.refresh_save_list()
    
    def refresh_save_list(self):
        """Refresh the list of save files"""
        self.save_list.clear()
        saves = self.save_manager.get_save_files()
        
        if not saves:
            item = QListWidgetItem("No saved games found")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
            self.save_list.addItem(item)
            return
        
        for save in saves:
            # Format the display text
            display_text = f"{save['name']}\n"
            display_text += f"Date: {save['date'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            display_text += f"Size: {save['size']/1024:.1f} KB"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, save['name'])
            self.save_list.addItem(item)
    
    def on_selection_changed(self):
        """Handle list selection changes"""
        current_item = self.save_list.currentItem()
        has_selection = current_item is not None
        
        # Check if it's a valid save (has UserRole data)
        is_valid_save = False
        if has_selection:
            save_name = current_item.data(Qt.ItemDataRole.UserRole)
            is_valid_save = save_name is not None and save_name != ""
        
        if self.mode == 'load':
            self.confirm_btn.setEnabled(is_valid_save)
        elif self.mode == 'save' and is_valid_save:
            # When an item is selected in save mode, populate the input field.
            self.save_name_input.setText(save_name)

        self.delete_btn.setEnabled(is_valid_save)
    
    def on_save(self):
        """Handle save button click"""
        save_name = ""
        if hasattr(self, 'save_name_input'):
            save_name = self.save_name_input.text().strip()
        
        # If no name provided, generate one
        if not save_name:
            save_name = f"save_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Check if a save with this name already exists.
        existing_saves = [s['name'] for s in self.save_manager.get_save_files()]
        if save_name in existing_saves:
            reply = QMessageBox.question(
                self,
                "Overwrite Save",
                f"A save named '{save_name}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return  # User chose not to overwrite, so we stop here.
        
        self.save_selected.emit(save_name)
        self.accept()
    
    def on_load(self):
        """Handle load button click"""
        selected = self.save_list.currentItem()
        if selected and selected.data(Qt.ItemDataRole.UserRole):
            save_name = selected.data(Qt.ItemDataRole.UserRole)
            self.save_selected.emit(save_name)
            self.accept()
    
    def on_delete(self):
        """Handle delete button click"""
        selected = self.save_list.currentItem()
        if not selected or not selected.data(Qt.ItemDataRole.UserRole):
            return
        
        save_name = selected.data(Qt.ItemDataRole.UserRole)
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Delete Save", 
            f"Are you sure you want to delete '{save_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = self.controller.delete_save_file(save_name)
            if success:
                # The signal from the controller will handle updating other windows.
                # We just need to refresh our own list.
                self.refresh_save_list()
                QMessageBox.information(self, "Success", f"Deleted save '{save_name}'")
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete save: {save_name}")