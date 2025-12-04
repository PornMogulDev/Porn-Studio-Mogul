from PyQt6.QtWidgets import QPushButton, QSizePolicy

class MenuButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        # Set the rules: This button can expand horizontally, but prefers a fixed height.
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set the safety nets
        self.setMinimumHeight(40)
        self.setMaximumHeight(100)