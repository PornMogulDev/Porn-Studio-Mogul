from PyQt6.QtWidgets import QSpinBox

class CategoricalSpinBox(QSpinBox):
    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.items = items
        self.item_to_index = {item: i for i, item in enumerate(self.items)}
        
        # Configure the spinbox for index-based operation
        self.setRange(0, len(self.items) - 1)

    def textFromValue(self, value: int) -> str:
        """
        Overrides the base method to return the string from our list
        at the index specified by 'value'.
        """
        if 0 <= value < len(self.items):
            return self.items[value]
        return "" # Return empty string for out-of-bounds values

    def valueFromText(self, text: str) -> int:
        """
        Overrides the base method to return the index corresponding
        to the given 'text' string.
        """
        # Return the index if the text is a valid item, otherwise return current value
        return self.item_to_index.get(text, self.value())

    def stepBy(self, steps: int):
        """Overrides stepBy to ensure wrapping behavior can be disabled if needed."""
        # QSpinBox has a `wrapping` property. If it's on, this works out of the box.
        # If not, you might add custom logic here, but default is usually fine.
        super().stepBy(steps)