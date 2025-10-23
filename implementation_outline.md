Implementation Outline

  Here is a proposed plan to implement the font and scaling features:

  1. Storing Font and Scale Settings

  I will extend the SettingsManager to store the new UI preferences. This will involve modifying
  src/data/settings_manager.py to add:
   * A setting for the font family (e.g., font_family: str).
   * A setting for the base font size (e.g., font_size: int).
   * A setting for the UI scale factor (e.g., ui_scale: float).

  I will set default values for these, using "Roboto" as the default font since it's already included in
  the project's assets.

  2. Applying Font and Scale Settings

  The apply_theme function in src/app/application.py is the ideal place to apply these settings globally. I
  will modify it to:
   * Read the font family, size, and scale from the SettingsManager.
   * Load the selected font. I will start with the fonts in assets/fonts and then expand to system fonts.
   * Create a QFont object with the chosen family and size.
   * Set this font as the default for the entire application using QApplication.setFont().
   * For UI scaling, I will investigate using Qt's built-in mechanisms. A good approach is to use stylesheets
     with relative units (like em) which scale with the font size. For elements with fixed sizes, I will apply
     the ui_scale factor directly.

  3. Creating the Settings UI

  I will update the settings dialog to allow players to customize these new options. This involves editing
  src/ui/dialogs/settings_dialog.py:
   * Add a QFontComboBox to the dialog, which will automatically populate with the user's installed system
     fonts.
   * Add a QSpinBox or a QComboBox to let the user select a base font size.
   * Add a QSlider or QDoubleSpinBox for adjusting the UI scale factor.
   * I will ensure these new widgets load the current settings from the SettingsManager and save any changes
     made by the user.

  4. Ensuring Proper Widget Scaling

  This is the most complex part. My strategy will be:
   * Layouts: Rely on Qt's layout managers (QVBoxLayout, QHBoxLayout, QGridLayout) as much as possible, as they
     handle resizing and scaling of widgets automatically.
   * Stylesheets: Use em or rem units in the application's stylesheet. These units are relative to the font
     size, so if the font size changes, the UI elements will scale proportionally.
   * Fixed-Size Elements: For any UI elements that have hardcoded pixel sizes, I will refactor them to calculate
      their size based on the ui_scale factor from the SettingsManager. I will create a utility function for
     this to ensure consistency.
   * Custom Widgets: Any custom-drawn widgets will need to be modified to respect the new scaling settings in
     their drawing logic.

  This outline provides a clear path forward. I will start by implementing the changes to the SettingsManager.
   Do you have any questions or suggestions about this plan?

> How do you plan to implement widgets scaling according to the ui_scale factor?

✦ Excellent question. Scaling widgets based on a ui_scale factor requires a systematic approach to avoid
  inconsistencies in the UI. Here’s a more detailed breakdown of how I plan to implement it:

  1. Centralized Scaling Logic

  I'll create a new utility function, let's call it scale, which will be the single source of truth for all
  scaling calculations. This function will live in a new file, src/utils/ui_utils.py, to keep UI-related
  utilities organized.

  The function will look something like this:

   1 # src/utils/ui_utils.py
   2 from data.settings_manager import SettingsManager
   3
   4 def scale(value: int) -> int:
   5     """Scales a given integer value based on the UI scale setting."""
   6     settings = SettingsManager()
   7     return int(value * settings.ui_scale)

  This ensures that every part of the application scales UI elements in the exact same way.

  2. Identifying and Refactoring Hardcoded Sizes

  I will systematically search the codebase for places where fixed sizes are set. My search will target
  methods like:
   * setFixedSize()
   * setFixedWidth()
   * setFixedHeight()
   * setGeometry()
   * setIconSize()

  For every instance of a hardcoded size, I will refactor it to use the new scale function.

  Example:

  A piece of code that currently looks like this:

   1 # Before
   2 save_button.setFixedSize(150, 40)
   3 cancel_button.setIconSize(QSize(24, 24))

  Will be changed to this:

   1 # After
   2 from src.utils.ui_utils import scale
   3
   4 save_button.setFixedSize(scale(150), scale(40))
   5 cancel_button.setIconSize(QSize(scale(24), scale(24)))

  3. Scaling in Custom Widgets

  For custom widgets that have their own paintEvent for drawing, I will apply the same scale function to any
  coordinates or sizes used in the drawing operations. This ensures that custom-drawn elements, like graphs,
  timelines, or special indicators, also scale correctly.

  Example:

   1 # Before
   2 def paintEvent(self, event):
   3     painter = QPainter(self)
   4     painter.drawRect(5, 5, 100, 20) # x, y, width, height

   1 # After
   2 from src.utils.ui_utils import scale
   3
   4 def paintEvent(self, event):
   5     painter = QPainter(self)
   6     painter.drawRect(scale(5), scale(5), scale(100), scale(20))

  4. Applying the Changes

  When the user changes the ui_scale factor in the settings dialog, the most reliable way to apply the changes
   across the entire application is to require a restart. I will add a notification in the settings dialog to
  inform the user about this. This approach is common in many applications and avoids the significant
  complexity of trying to dynamically rescale every UI element in real-time.

  By following these steps, I can ensure that the scaling is applied consistently and predictably across all
  components of the application, from standard buttons and icons to custom-drawn widgets.