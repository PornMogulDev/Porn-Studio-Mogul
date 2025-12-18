\### Implementation Plan



\#### 1. Core Architecture (New Base Classes)

We will create reusable base classes to enforce the architecture defined in your documentation.



\*   \*\*`src/ui/presenters/base\_presenter.py`\*\*

&nbsp;   \*   \*\*Class:\*\* `BasePresenter(QObject)`

&nbsp;   \*   \*\*Responsibilities:\*\* 

&nbsp;       \*   Implements the standard `cleanup()` method to disconnect signals.

&nbsp;       \*   Provides `connect\_signal(signal, slot)` helper to track connections.

&nbsp;       \*   Standardizes the `view` and `controller` injection.



\*   \*\*`src/ui/dialogs/base\_game\_window.py`\*\*

&nbsp;   \*   \*\*Class:\*\* `BaseGameWindow(QDialog, GeometryManagerMixin)`

&nbsp;   \*   \*\*Responsibilities:\*\*

&nbsp;       \*   Sets standard Window Flags (Minimize, Maximize, Close).

&nbsp;       \*   Sets `WA\_DeleteOnClose` attribute.

&nbsp;       \*   Handles `show()` to restore geometry automatically.

&nbsp;       \*   Handles `closeEvent` to save geometry automatically.



\#### 2. Data \& Service Layer Updates

\*   \*\*`src/utils/time\_utils.py`\*\*

&nbsp;   \*   Add `format\_year\_month\_week(absolute\_week: int) -> str`.

&nbsp;       \*   Uses existing `to\_month` to return string format "YYYY/MM/W".



\*   \*\*`src/data/game\_state.py`\*\*

&nbsp;   \*   Update `Contract` dataclass to include `end\_absolute\_week` property (calculated from start + duration).



\*   \*\*`src/services/query/talent\_query\_service.py`\*\*

&nbsp;   \*   Add `get\_contracted\_talents() -> List\[Talent]`: Fetches all talents that have an active contract.

&nbsp;   \*   Add `get\_contracted\_scene\_count\_for\_month(talent\_id: int, current\_abs\_week: int) -> int`:

&nbsp;       \*   Calculates start/end week of the current month using `time\_utils`.

&nbsp;       \*   Queries `SceneCastDB` joined with `SceneDB` to count scenes where status is not 'cancelled' within that range.



\#### 3. View Models

\*   \*\*`src/ui/models/roster\_view\_model.py`\*\*

&nbsp;   \*   \*\*Class:\*\* `RosterViewModel` (Dataclass)

&nbsp;   \*   \*\*Fields:\*\* 

&nbsp;       \*   `talent\_obj` (For UserRole/EntityCard).

&nbsp;       \*   `alias`, `salary` (formatted), `compliance` (e.g., "95%"), `dates` (formatted string "Start - End"), `duration\_left` (e.g., "12w"), `usage` (e.g., "2/4").

&nbsp;       \*   `allowed\_orientations`, `allowed\_concepts`, `limits` (dynamic/disposition).

&nbsp;   \*   \*\*Sort Keys:\*\* Integer/Float values for sorting the formatted strings.



\*   \*\*`src/ui/models/roster\_table\_model.py`\*\*

&nbsp;   \*   \*\*Class:\*\* `RosterTableModel(QAbstractTableModel)`

&nbsp;   \*   \*\*Responsibilities:\*\*

&nbsp;       \*   Holds list of `RosterViewModel`.

&nbsp;       \*   Implements `data()` handling `DisplayRole` (text), `UserRole` (talent obj), and potentially `ForegroundRole` (coloring compliance red if low).

&nbsp;       \*   Implements `sort()`.



\#### 4. UI Implementation (The View)

\*   \*\*`src/ui/dialogs/roster\_window.py`\*\*

&nbsp;   \*   \*\*Inherits:\*\* `BaseGameWindow`.

&nbsp;   \*   \*\*Layout:\*\*

&nbsp;       \*   \*\*Top Bar:\*\* `HelpButton` ("overview"), `ViewMenuButton` (Column Toggler).

&nbsp;       \*   \*\*Main:\*\* `SmartTableView`.

&nbsp;   \*   \*\*Components:\*\*

&nbsp;       \*   Instance of `RosterTableModel`.

&nbsp;       \*   Instance of `SmartTableView`.

&nbsp;   \*   \*\*Signals:\*\* `visibility\_changed` (from ViewMenuButton), `smart\_hover`, `double\_clicked`.



\#### 5. Presenter Implementation

\*   \*\*`src/ui/presenters/roster\_presenter.py`\*\*

&nbsp;   \*   \*\*Inherits:\*\* `BasePresenter`.

&nbsp;   \*   \*\*Responsibilities:\*\*

&nbsp;       \*   \*\*Init:\*\* Load column visibility settings from `SettingsManager`. Configure `ViewMenuButton`.

&nbsp;       \*   \*\*Data Loading:\*\* 

&nbsp;           \*   Call `TalentQueryService` for talents.

&nbsp;           \*   Loop through talents, calc usage, format dates via `time\_utils`.

&nbsp;           \*   Populate `RosterTableModel`.

&nbsp;       \*   \*\*Events:\*\*

&nbsp;           \*   Listen to `roster\_changed` signal (from `ContractCommandService`) to refresh data.

&nbsp;           \*   Handle column visibility toggles -> Update Table \& Save to Settings.

&nbsp;           \*   Handle Table Double Click -> `ui\_manager.show\_talent\_profile`.



\#### 6. Integration \& Wiring

\*   \*\*`src/ui/managers/ui\_manager.py`\*\*

&nbsp;   \*   Add `show\_roster()`.

&nbsp;   \*   Instantiates `RosterWindow` and `RosterPresenter`.

&nbsp;   \*   Links them using `window.set\_presenter(presenter)`.



\*   \*\*`src/ui/widgets/main\_window/bottom\_bar\_widget.py`\*\*

&nbsp;   \*   Add `Roster` button.



\*   \*\*`src/ui/presenters/main\_window\_presenter.py`\*\*

&nbsp;   \*   Connect Bottom Bar signal to `ui\_manager.show\_roster`.



\*   \*\*`src/data/settings\_manager.py`\*\*

&nbsp;   \*   Add default `roster\_visible\_columns` to `\_default\_settings`.



This plan ensures a clean separation of concerns, leverages your existing systems (TimeUtils, SmartTable, ThemeManager), and introduces the requested base classes to streamline future dialog creation.

