from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QGroupBox, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from typing import Optional

from data.game_state import Talent

class HiringTalentProfileWidget(QWidget):
    """Simplified talent profile widget for viewing and hiring."""
    hire_requested = pyqtSignal(object)  # Talent
    
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.current_talent = None
        self.current_demand = 0
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        
        # No selection placeholder
        self.no_selection_label = QLabel("Double-click a talent to view profile")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        self.content_layout.addWidget(self.no_selection_label)
        
        # Profile content (initially hidden)
        self.profile_content = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_content)
        self.profile_content.hide()
        self.content_layout.addWidget(self.profile_content)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Hire button
        hire_layout = QHBoxLayout()
        self.hire_button = QPushButton("Hire for Role")
        self.hire_button.clicked.connect(self._on_hire_clicked)
        self.hire_button.setEnabled(False)
        self.cost_label = QLabel("")
        hire_layout.addWidget(self.cost_label)
        hire_layout.addStretch()
        hire_layout.addWidget(self.hire_button)
        layout.addLayout(hire_layout)
    
    def display_talent(self, talent: Talent, demand: int):
        """Display talent profile and enable hiring."""
        self.current_talent = talent
        self.current_demand = demand
        
        # Clear previous content
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Build profile
        self._build_basic_info(talent)
        self._build_skills(talent)
        self._build_attributes(talent)
        
        # Show profile, hide placeholder
        self.no_selection_label.hide()
        self.profile_content.show()
        
        # Enable hiring
        self.hire_button.setEnabled(True)
        self.cost_label.setText(f"Cost: ${demand}")
    
    def _build_basic_info(self, talent: Talent):
        """Build basic info section."""
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)
        
        basic_layout.addRow("Alias:", QLabel(talent.alias))
        basic_layout.addRow("Age:", QLabel(str(talent.age)))
        basic_layout.addRow("Gender:", QLabel(talent.gender))
        basic_layout.addRow("Ethnicity:", QLabel(talent.ethnicity))
        basic_layout.addRow("Orientation:", QLabel(talent.orientation))
        basic_layout.addRow("Nationality:", QLabel(talent.nationality))
        basic_layout.addRow("Location:", QLabel(talent.base_location))
        
        self.profile_layout.addWidget(basic_group)
    
    def _build_skills(self, talent: Talent):
        """Build skills section."""
        from utils.formatters import get_fuzzed_skill_range
        
        skills_group = QGroupBox("Skills")
        skills_layout = QFormLayout(skills_group)
        
        # Calculate fuzzed ranges
        perf_range = get_fuzzed_skill_range(talent.performance, talent.experience, talent.id)
        act_range = get_fuzzed_skill_range(talent.acting, talent.experience, talent.id)
        dom_range = get_fuzzed_skill_range(talent.dom_skill, talent.experience, talent.id)
        sub_range = get_fuzzed_skill_range(talent.sub_skill, talent.experience, talent.id)
        stam_range = get_fuzzed_skill_range(talent.stamina, talent.experience, talent.id)
        
        def format_range(r):
            if isinstance(r, int):
                return str(r)
            return f"{r[0]}-{r[1]}"
        
        skills_layout.addRow("Performance:", QLabel(format_range(perf_range)))
        skills_layout.addRow("Acting:", QLabel(format_range(act_range)))
        skills_layout.addRow("Dom:", QLabel(format_range(dom_range)))
        skills_layout.addRow("Sub:", QLabel(format_range(sub_range)))
        skills_layout.addRow("Stamina:", QLabel(format_range(stam_range)))
        
        # Popularity
        pop = sum(p['score'] for p in talent.popularity_scores) if talent.popularity_scores else 0
        skills_layout.addRow("Popularity:", QLabel(str(round(pop))))
        
        self.profile_layout.addWidget(skills_group)
    
    def _build_attributes(self, talent: Talent):
        """Build physical attributes section."""
        attr_group = QGroupBox("Physical Attributes")
        attr_layout = QFormLayout(attr_group)
        
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        
        # Height
        if unit_system == "imperial":
            from utils.formatters import format_height_imperial
            height_str = format_height_imperial(talent.height)
        else:
            height_str = f"{talent.height} cm"
        attr_layout.addRow("Height:", QLabel(height_str))
        
        # Dick size
        if talent.dick_size:
            if unit_system == "imperial":
                dick_str = f"{talent.dick_size:.1f}\""
            else:
                from utils.formatters import inches_to_cm
                dick_str = f"{inches_to_cm(talent.dick_size):.1f} cm"
            attr_layout.addRow("Dick Size:", QLabel(dick_str))
        
        # Cup size
        if talent.cup_size:
            attr_layout.addRow("Cup Size:", QLabel(talent.cup_size))
        
        self.profile_layout.addWidget(attr_group)
        self.profile_layout.addStretch()
    
    def _on_hire_clicked(self):
        """Handle hire button click."""
        if self.current_talent:
            self.hire_requested.emit(self.current_talent)
    
    def clear(self):
        """Clear the profile display."""
        self.current_talent = None
        self.current_demand = 0
        self.no_selection_label.show()
        self.profile_content.hide()
        self.hire_button.setEnabled(False)
        self.cost_label.clear()