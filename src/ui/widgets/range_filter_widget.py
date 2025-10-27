from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox
from superqt import QRangeSlider

class RangeFilterWidget(QWidget):
    """A compound widget providing a min/max spinbox pair and a QRangeSlider."""
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

        self.slider = QRangeSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self.slider)

        layout.addWidget(QLabel("Max:"))
        layout.addWidget(self.max_spinbox)

    def _connect_signals(self):
        self.slider.valueChanged.connect(self._on_slider_value_changed)
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

        self.min_spinbox.setValue(min_val)
        self.max_spinbox.setValue(max_val)

        # Unblock signals
        self.min_spinbox.blockSignals(False)
        self.max_spinbox.blockSignals(False)

        # After setting spinboxes, update the slider to match
        self._update_slider_from_spinboxes()

    def get_values(self):
        """Returns the current min and max values."""
        return self.min_spinbox.value(), self.max_spinbox.value()

    def _on_slider_value_changed(self, value: tuple):
        """SLOT: Handles the slider handles being moved. Updates spinboxes."""
        min_slider, max_slider = value
        self.min_spinbox.blockSignals(True)
        self.max_spinbox.blockSignals(True)

        # Calculate the value based on the precision factor
        min_val = min_slider / self._precision_factor
        max_val = max_slider / self._precision_factor

        # For integer-based widgets, ensure the value is an integer.
        # For float-based widgets, it will correctly remain a float.
        if self._data_type == 'int':
            min_val = int(min_val)
            max_val = int(max_val)

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
        self.slider.setValue((int(self.min_spinbox.value() * self._precision_factor), 
                               int(self.max_spinbox.value() * self._precision_factor)))
        self.slider.blockSignals(False)