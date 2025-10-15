import os
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QTextEdit, QLabel, QDialogButtonBox
)
from PyQt6.QtCore import Qt

from utils.paths import HELP_DIR
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class HelpDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setWindowTitle("Help")
        self.setMinimumSize(700, 500)

        self.setup_ui()
        self.connect_signals()
        
        self.populate_topics()
        self.topic_list_widget.setCurrentRow(0) # Select the first item by default

        self._restore_geometry()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        
        # --- Left Panel (Topic List) ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Topics"))
        self.topic_list_widget = QListWidget()
        left_panel.addWidget(self.topic_list_widget)
        
        # --- Right Panel (Topic Content) ---
        right_panel = QVBoxLayout()
        self.title_label = QLabel("...")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title_label.setWordWrap(True)
        
        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        
        right_panel.addWidget(self.title_label)
        right_panel.addWidget(self.content_text)
        
        close_button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        right_panel.addWidget(close_button_box)

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 3)
        
        close_button_box.rejected.connect(self.reject)

    def connect_signals(self):
        self.topic_list_widget.currentItemChanged.connect(self.on_topic_selected)

    def populate_topics(self):
        """Reads help topics from the controller and populates the list."""
        self.topic_list_widget.clear()
        
        # Sort topics by title for consistent ordering
        topics = self.controller.help_topics
        sorted_topics = sorted(topics.items(), key=lambda item: item[1].get('title', ''))

        for key, data in sorted_topics:
            item = QListWidgetItem(data.get('title', 'Untitled'))
            item.setData(Qt.ItemDataRole.UserRole, key) # Store the unique key
            self.topic_list_widget.addItem(item)
    
    def on_topic_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Updates the right panel when a topic is selected."""
        if not current_item:
            self.clear_details()
            return
            
        topic_key = current_item.data(Qt.ItemDataRole.UserRole)
        topic_data = self.controller.help_topics.get(topic_key)
        
        if topic_data:
            self.title_label.setText(topic_data.get('title', ''))
            content_path = topic_data.get('content_file')

            if content_path:
                # content_path is relative to the DATA_DIR
                full_path = os.path.join(HELP_DIR, content_path)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        markdown_content = f.read()
                    self.content_text.setMarkdown(markdown_content)
                except FileNotFoundError:
                    self.content_text.setPlainText(f"Error: Help file not found.\n\nPath: {full_path}")
                except Exception as e:
                    self.content_text.setPlainText(f"Error: Could not read help file.\n\nDetails: {e}")
            else:
                self.content_text.setPlainText("No content file specified for this topic.")

    def show_topic(self, topic_key: str):
        """Finds and selects a specific topic in the list."""
        for i in range(self.topic_list_widget.count()):
            item = self.topic_list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == topic_key:
                self.topic_list_widget.setCurrentItem(item)
                break
        
        self.show()
        self.raise_()
        self.activateWindow()

    def clear_details(self):
        """Clears the content panel."""
        self.title_label.setText("Select a Topic")
        self.content_text.clear()