from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel,
    QPushButton, QMessageBox, QHBoxLayout, QFormLayout,
    QSlider, QSpinBox, QComboBox, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

class ContractPage(QWidget):
    """The exclusive contract negotiation form."""
    
    preview_requested = pyqtSignal(dict) # Emits terms
    sign_requested = pyqtSignal(dict)    # Emits terms
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.concept_checks = {}
        self.orientation_checks = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        neg_group = QGroupBox("Exclusive Contract Terms")
        form_layout = QFormLayout(neg_group)
        
        # Duration
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(12, 156)
        self.duration_slider.setValue(52)
        self.duration_label = QLabel("52 weeks")
        self.duration_slider.valueChanged.connect(lambda v: self.duration_label.setText(f"{v} weeks"))
        
        slider_container = QWidget()
        sc_layout = QHBoxLayout(slider_container)
        sc_layout.setContentsMargins(0,0,0,0)
        sc_layout.addWidget(self.duration_slider)
        sc_layout.addWidget(self.duration_label)
        form_layout.addRow("Duration:", slider_container)
        
        # Max Scenes
        self.max_scenes_spin = QSpinBox()
        self.max_scenes_spin.setRange(1, 7)
        self.max_scenes_spin.setValue(1)
        form_layout.addRow("Max Scenes/Week:", self.max_scenes_spin)
        
        # Dynamic Limit
        self.max_dynamic_combo = QComboBox()
        self.max_dynamic_combo.addItems(["0 (Vanilla)", "1 (Standard)", "2 (Hardcore)", "3 (Extreme)"])
        self.max_dynamic_combo.setCurrentIndex(3)
        form_layout.addRow("Max Intensity:", self.max_dynamic_combo)
        
        # Disposition
        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems(["Any", "Dom", "Sub", "Switch"])
        form_layout.addRow("Required Disposition:", self.disposition_combo)

        # Checkboxes for Scope (Scrollable)
        scope_area = QScrollArea()
        scope_widget = QWidget()
        self.scope_layout = QVBoxLayout(scope_widget)
        
        scope_widget.setLayout(self.scope_layout)
        scope_area.setWidget(scope_widget)
        scope_area.setWidgetResizable(True)
        scope_area.setFixedHeight(150) # Slightly shorter to fit layout
        layout.addWidget(neg_group)
        layout.addWidget(scope_area)
        
        # Result / Actions
        self.salary_preview_label = QLabel("Weekly Salary: Calculating...")
        self.salary_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.salary_preview_label)
        
        btn_row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.sign_button = QPushButton("Sign Contract")
        btn_row.addWidget(self.cancel_button)
        btn_row.addWidget(self.sign_button)
        layout.addLayout(btn_row)

        # Signals
        self.cancel_button.clicked.connect(self.cancel_clicked)
        self.sign_button.clicked.connect(self._on_sign_clicked)
        
        # Auto-update preview triggers
        self.duration_slider.valueChanged.connect(self._request_preview)
        self.max_scenes_spin.valueChanged.connect(self._request_preview)
        self.max_dynamic_combo.currentIndexChanged.connect(self._request_preview)
        self.disposition_combo.currentIndexChanged.connect(self._request_preview)

    def populate_options(self, concepts: list, orientations: list):
        """Populates the checkboxes dynamically."""
        while self.scope_layout.count():
            item = self.scope_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.concept_checks = {}
        self.orientation_checks = {}
        
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Concepts
        concepts_col = QVBoxLayout()
        concepts_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        concepts_col.addWidget(QLabel("<b>Allowed Concepts:</b>"))
        for c in concepts:
            chk = QCheckBox(c)
            chk.setChecked(True)
            chk.stateChanged.connect(self._request_preview)
            concepts_col.addWidget(chk)
            self.concept_checks[c] = chk
        container_layout.addLayout(concepts_col)
            
        # Orientations
        orient_col = QVBoxLayout()
        orient_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        orient_col.addWidget(QLabel("<b>Allowed Orientations:</b>"))
        for o in orientations:
            chk = QCheckBox(o)
            chk.setChecked(True)
            chk.stateChanged.connect(self._request_preview)
            orient_col.addWidget(chk)
            self.orientation_checks[o] = chk
        container_layout.addLayout(orient_col)
            
        self.scope_layout.addWidget(container)

    def get_terms(self) -> dict:
        return {
            'duration_weeks': self.duration_slider.value(),
            'max_scenes_per_week': self.max_scenes_spin.value(),
            'max_dynamic': self.max_dynamic_combo.currentIndex(),
            'disposition': self.disposition_combo.currentText() if self.disposition_combo.currentIndex() > 0 else None,
            'allowed_concepts': [c for c, chk in self.concept_checks.items() if chk.isChecked()],
            'allowed_orientations': [o for o, chk in self.orientation_checks.items() if chk.isChecked()]
        }

    def _request_preview(self):
        self.preview_requested.emit(self.get_terms())

    def _on_sign_clicked(self):
        terms = self.get_terms()
        if not terms['allowed_concepts'] and not terms['allowed_orientations']:
             QMessageBox.warning(self, "Invalid Contract", "You must select at least one concept or orientation.")
             return
        self.sign_requested.emit(terms)