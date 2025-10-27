from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox, QSlider

class RangeFilterWidget(QWidget):
    """
    A compound widget that provides a min/max spinbox pair and a slider.
    It supports two modes of interaction:
    1. Range Mode: The user sets a min and max value using the spinboxes.
    2. Single Value Mode: The user drags the slider, which sets both min and max
       to the slider's value for precise filtering.
    The last control touched dictates the current mode.
    """
    valuesChanged = pyqtSignal(object, object)

    def __init__(self, data_type: str = 'int', parent=None):
        """
        Initializes the widget.
        :param data_type: 'int' for QSpinBox or 'float' for QDoubleSpinBox.
        """
        super().__init__(parent)
        self._data_type = data_type
        self._precision_factor = 100 if data_type == 'float' else 1

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Min:"))

        if self._data_type == 'float':
            self.min_spinbox = QDoubleSpinBox()
            self.max_spinbox = QDoubleSpinBox()
        else:
            self.min_spinbox = QSpinBox()
            self.max_spinbox = QSpinBox()

        layout.addWidget(self.min_spinbox)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self.slider)

        layout.addWidget(QLabel("Max:"))
        layout.addWidget(self.max_spinbox)

    def _connect_signals(self):
        # When slider is moved, enter "single value" mode
        self.slider.valueChanged.connect(self._on_slider_moved)

        # When spinboxes are changed, enter "range" mode
        self.min_spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.max_spinbox.valueChanged.connect(self._on_spinbox_changed)

    def set_range(self, min_limit, max_limit):
        """Sets the absolute minimum and maximum possible values for the controls."""
        self.min_spinbox.setRange(min_limit, max_limit)
        self.max_spinbox.setRange(min_limit, max_limit)
        self.slider.setRange(int(min_limit * self._precision_factor), int(max_limit * self._precision_factor))

    def set_values(self, min_val, max_val):
        """Programmatically sets the current values of the spinboxes."""
        # Block signals to prevent emitting valuesChanged prematurely
        self.min_spinbox.blockSignals(True)
        self.max_spinbox.blockSignals(True)
        self.slider.blockSignals(True)

        self.min_spinbox.setValue(min_val)
        self.max_spinbox.setValue(max_val)

        # If it's a single value, update the slider position
        if min_val == max_val:
            self.slider.setValue(int(min_val * self._precision_factor))

        # Unblock signals
        self.min_spinbox.blockSignals(False)
        self.max_spinbox.blockSignals(False)
        self.slider.blockSignals(False)

    def get_values(self):
        """Returns the current min and max values."""
        return self.min_spinbox.value(), self.max_spinbox.value()

    def _on_slider_moved(self, slider_value: int):
        """SLOT: Handles the slider being moved. Forces single-value mode."""
        # Convert slider integer value to the appropriate data type
        value = slider_value / self._precision_factor
        if self._data_type == 'int':
            value = int(value)

        # Block spinbox signals to prevent a feedback loop
        self.min_spinbox.blockSignals(True)
        self.max_spinbox.blockSignals(True)

        self.min_spinbox.setValue(value)
        self.max_spinbox.setValue(value)

        self.min_spinbox.blockSignals(False)
        self.max_spinbox.blockSignals(False)

        # Emit the change
        self.valuesChanged.emit(value, value)

    def _on_spinbox_changed(self):
        """SLOT: Handles either spinbox value changing. Forces range mode."""
        min_val = self.min_spinbox.value()
        max_val = self.max_spinbox.value()

        # Enforce min <= max without feedback loops
        if self.sender() == self.min_spinbox and min_val > max_val:
            self.max_spinbox.blockSignals(True)
            self.max_spinbox.setValue(min_val)
            self.max_spinbox.blockSignals(False)
            max_val = min_val # Update local variable for emit
        elif self.sender() == self.max_spinbox and max_val < min_val:
            self.min_spinbox.blockSignals(True)
            self.min_spinbox.setValue(max_val)
            self.min_spinbox.blockSignals(False)
            min_val = max_val # Update local variable for emit

        # Ensure the other spinbox's limits are correct
        self.max_spinbox.setMinimum(min_val)
        self.min_spinbox.setMaximum(max_val)

        # Emit the change
        self.valuesChanged.emit(min_val, max_val)