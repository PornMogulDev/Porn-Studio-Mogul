from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from superqt import QRangeSlider

from ui.widgets.talent_filter.categorical_spin_box import CategoricalSpinBox

class CategoricalRangeFilterWidget(QWidget):
    """
    A compound widget providing a min/max CategoricalSpinBox pair and a QRangeSlider.
    This widget is designed to handle an ordered list of string categories by mapping
    them to integer indices for the underlying slider and spinboxes.
    """
    valuesChanged = pyqtSignal(int, int) # Emits the min and max indices

    def __init__(self, items: list[str], parent: QWidget = None):
        """
        Initializes the categorical range filter widget.

        :param items: An ordered list of strings representing the categories.
        :param parent: The parent widget.
        """
        super().__init__(parent)
        self.items = items

        self._setup_ui()
        self._connect_signals()

        # The range is determined by the number of items provided.
        self.set_range(0, len(self.items) - 1)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Min:"))

        # Use the custom CategoricalSpinBox
        self.min_spinbox = CategoricalSpinBox(self.items)
        self.max_spinbox = CategoricalSpinBox(self.items)

        layout.addWidget(self.min_spinbox)

        self.slider = QRangeSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self.slider)

        layout.addWidget(QLabel("Max:"))
        layout.addWidget(self.max_spinbox)

    def _connect_signals(self):
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        self.min_spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.max_spinbox.valueChanged.connect(self._on_spinbox_changed)

    def set_range(self, min_limit: int, max_limit: int):
        """Sets the absolute minimum and maximum possible indices for the controls."""
        self.min_spinbox.setRange(min_limit, max_limit)
        self.max_spinbox.setRange(min_limit, max_limit)
        self.slider.setRange(min_limit, max_limit)

    def set_values(self, min_idx: int, max_idx: int):
        """Programmatically sets the current index values of the spinboxes."""
        # Block signals to prevent emitting valuesChanged prematurely
        self.min_spinbox.blockSignals(True)
        self.max_spinbox.blockSignals(True)

        self.min_spinbox.setValue(min_idx)
        self.max_spinbox.setValue(max_idx)

        # Unblock signals
        self.min_spinbox.blockSignals(False)
        self.max_spinbox.blockSignals(False)

        # After setting spinboxes, update the slider to match
        self._update_slider_from_spinboxes()

    def get_values(self) -> tuple[int, int]:
        """Returns the current min and max indices."""
        return self.min_spinbox.value(), self.max_spinbox.value()

    def _on_slider_value_changed(self, value: tuple):
        """SLOT: Handles the slider handles being moved. Updates spinboxes."""
        min_val, max_val = value
        self.min_spinbox.blockSignals(True)
        self.max_spinbox.blockSignals(True)

        self.min_spinbox.setValue(min_val)
        self.max_spinbox.setValue(max_val)

        self.min_spinbox.blockSignals(False)
        self.max_spinbox.blockSignals(False)

        self.valuesChanged.emit(self.min_spinbox.value(), self.max_spinbox.value())

    def _on_spinbox_changed(self):
        """SLOT: Handles either spinbox value changing. Updates slider."""
        min_val = self.min_spinbox.value()
        max_val = self.max_spinbox.value()

        # Enforce that min_val is never greater than max_val
        if min_val > max_val:
            # If the user was editing the min_spinbox, pull the max value up to match.
            if self.sender() == self.min_spinbox:
                self.max_spinbox.blockSignals(True)
                self.max_spinbox.setValue(min_val)
                self.max_spinbox.blockSignals(False)
            # If the user was editing the max_spinbox, push the min value down to match.
            else:
                self.min_spinbox.blockSignals(True)
                self.min_spinbox.setValue(max_val)
                self.min_spinbox.blockSignals(False)

        self._update_slider_from_spinboxes()
        self.valuesChanged.emit(self.min_spinbox.value(), self.max_spinbox.value())
        
    def _update_slider_from_spinboxes(self):
        """Updates the slider's handle positions based on spinbox values."""
        self.slider.blockSignals(True)
        self.slider.setValue((self.min_spinbox.value(), self.max_spinbox.value()))
        self.slider.blockSignals(False)