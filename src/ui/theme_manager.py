from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Theme:
    """Holds all the color and metric data for a UI theme."""
    name: str

    # Palette
    background: str = "#F0F0F0"
    background_light: str = "#FFFFFF"
    text: str = "#000000"
    border: str = "#B0B0B0"
    accent: str = "#0078D7"
    accent_hover: str = "#1088E7"
    accent_text: str = "#FFFFFF"
    danger: str = "#C50F1F"

    # Semantic colors for good/bad/neutral states
    color_good: str = "#107C10"      # Green
    color_bad: str = "#D83B01"       # Red/Orange
    color_warning: str = "#F7A800"   # Amber
    color_neutral: str = "#8A8A8A"    # Gray

    # Disabled state colors
    disabled_background: str = "#E0E0E0"
    disabled_text: str = "#A0A0A0"

    # Specific component overrides
    groupbox_border: str = "#D0D0D0"
    header_background: str = "#E1E1E1"

    # Notification styling
    notification_background: str = "rgba(51, 51, 51, 220)"
    notification_text: str = "#FFFFFF"

# --- Default Themes ---

DEFAULT_LIGHT = Theme(name="light") # This will use the new defaults we added above

DEFAULT_DARK = Theme(
    name="dark",
    background="#2D2D2D",
    background_light="#3C3C3C",
    text="#F0F0F0",
    border="#555555",
    accent="#5A9Bcf",
    accent_hover="#6AADDf",
    accent_text="#FFFFFF",
    danger="#D13438",

    # Brighter, more readable colors for the dark theme
    color_good="#66bb6a",
    color_bad="#ef5350",
    color_warning="#ffa726",
    color_neutral="#9e9e9e",

    # Disabled state colors for the dark theme
    disabled_background="#454545",
    disabled_text="#888888",

    # Specific component overrides
    groupbox_border="#4A4A4A",
    header_background="#383838",

    # Notification styling for dark theme
    notification_background="rgba(80, 80, 80, 230)",
    notification_text="#F0F0F0",
)

class ThemeManager:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self._themes = {
            "light": DEFAULT_LIGHT,
            "dark": DEFAULT_DARK
        }
    
    def get_theme(self, name: str) -> Theme:
        """Retrieves a theme by name, falling back to light theme."""
        return self._themes.get(name, DEFAULT_LIGHT)

    def generate_stylesheet(self, theme: Theme, font_family: str, font_size: int) -> str:
        """
        Generates a full QSS string from theme data and font settings.
        """
        # --- DYNAMIC CALCULATION ---
        # Heuristic: The top margin should be the font size (in points) plus some
        # extra padding to ensure the title text has breathing room.
        # This makes the layout scale correctly with the font.
        groupbox_margin_top = font_size + 10 
        
        # Calculate font size for large headers like the email subject
        subject_font_size = min(font_size + 2, 30)

        qss = f"""
            /* --- Global Font & Color Settings --- */
            QWidget {{
                font-family: "{font_family}";
                font-size: {font_size}pt;
                color: {theme.text};
                background-color: {theme.background};
            }}

            /* --- Fix for GroupBox Title Overlap --- */
            QGroupBox {{
                border: 1px solid {theme.groupbox_border};
                border-radius: 4px;
                /* Using our dynamically calculated margin */
                margin-top: {groupbox_margin_top}px; 
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                background-color: {theme.background};
            }}

            /* --- Fix for Table Headers Not Scaling --- */
            QHeaderView::section {{
                background-color: {theme.header_background};
                padding: 4px;
                border: 1px solid {theme.border};
            }}
        
            /* --- General Widget Styling --- */
            QPushButton {{
                background-color: transparent;
                color: {theme.accent};
                border-radius: 4px;
                padding: 5px 10px;
                border: 2px solid {theme.accent};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.accent_hover};
            }}
            QPushButton[ButtonRole="DestructiveRole"] {{
                background-color: {theme.danger};
                border-color: {theme.danger};
            }}
            
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {theme.background_light};
                border: 1px solid {theme.border};
                border-radius: 4px;
                padding: 4px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {theme.accent};
            }}

            /* --- CheckBox Styling --- */
            /* Style all checkable indicators for consistency */
            QCheckBox::indicator, QGroupBox::indicator, QTreeView::indicator, QListWidget::indicator {{
                border: 1px solid {theme.border};
                border-radius: 3px;
                width: 15px;
                height: 15px;
                background-color: {theme.background_light};
            }}
            QCheckBox::indicator:hover, QGroupBox::indicator:hover, QTreeView::indicator:hover, QListWidget::indicator:hover {{
                border-color: {theme.accent};
            }}
            QCheckBox::indicator:checked, QGroupBox::indicator:checked, QTreeView::indicator:checked, QListWidget::indicator:checked {{
                background-color: {theme.accent};
                border-color: {theme.accent};
            }}
            QCheckBox::indicator:checked:hover, QGroupBox::indicator:checked:hover, QTreeView::indicator:checked:hover, QListWidget::indicator:checked:hover {{
                background-color: {theme.accent_hover};
                border-color: {theme.accent_hover};
            }}

            /* Specific state for tristate checkboxes (e.g., in TreeView) */
            QTreeView::indicator:indeterminate {{
                background-color: {theme.color_neutral};
                border-color: {theme.accent};
            }}
            QTreeView::indicator:indeterminate:hover {{
                background-color: {theme.accent_hover};
                border-color: {theme.accent_hover};
            }}

            /* --- QRangeSlider Specific Styling --- */
            QRangeSlider {{
                qproperty-barColor: {theme.accent};
                background: transparent;
            }}
            QRangeSlider:hover {{
                qproperty-handleColor: {theme.accent_hover};
            }}
            /* --- Disabled Widget States --- */
            QPushButton:disabled, QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {{
                background-color: {theme.disabled_background};
                color: {theme.disabled_text};
                border: 2px solid {theme.disabled_text};
            }}
            /* Ensure the dropdown arrow on a disabled combobox is also muted */
            QComboBox::down-arrow:disabled {{
                /* You could specify a custom disabled arrow image here if needed */
                /* For now, the parent background color change is sufficient */
            }}
            /* --- Style for disabled (non-selectable) items in a QComboBox dropdown --- */
            QComboBox QAbstractItemView::item:disabled {{
                color: {theme.disabled_text};
                background-color: {theme.disabled_background};
                /* We don't want selection-style colors for disabled items */
                selection-background-color: {theme.disabled_background};
            }}

            /* --- Tab Styling --- */
            QTabWidget::pane {{ /* The container for the tab pages */
                border: 1px solid {theme.border};
                border-top: none;
            }}
            QTabWidget::tab-bar {{
                alignment: left;
            }}
            QTabBar::tab {{
                background: {theme.background};
                border: 1px solid {theme.border};
                border-bottom: none; /* Merges with pane */
                padding: 8px 15px;
                margin-right: 2px;
            }}
            QTabBar::tab:hover {{
                background: {theme.background_light};
            }}
            QTabBar::tab:selected {{
                background: {theme.background_light};
                border-color: {theme.accent};
                border-bottom-color: {theme.background_light}; /* Creates seamless look */
            }}

             /* --- Semantic Status Colors for Labels --- */
            /* Used in Scene Planner for total runtime percentage */
            QLabel#totalPercentLabel[status="good"] {{
                color: {theme.color_good};
            }}
            QLabel#totalPercentLabel[status="bad"] {{
                color: {theme.color_bad};
            }}
            QLabel#totalPercentLabel[status="warning"] {{
                color: {theme.color_warning};
            }}
            QLabel#totalPercentLabel[status="neutral"] {{
                color: {theme.text};
            }}

            /* --- Specific Component Styling for Email Dialog --- */
            QLabel#emailSubjectLabel {{
                font-size: {subject_font_size}pt;
                font-weight: bold;
                /* Color is inherited from the global QWidget style */
            }}

            QLabel#emailDateLabel {{
                color: {theme.color_neutral};
            }}
        """
        return qss