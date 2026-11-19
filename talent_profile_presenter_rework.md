\### Phase 2: Presenter Coordinator Pattern



\*\*Objective\*\*: Decompose the `TalentProfilePresenter` into a Coordinator and six specialized Sub-Presenters. This isolates the logic for Hiring, Schedule, Details, etc., preventing the main presenter from becoming a "God Class" and moving the Tour Sponsorship flow completely out of the View.



\*\*New File Structure\*\*:

`src/ui/presenters/talent\_profile/` (Package)

&nbsp; ├── `\_\_init\_\_.py`

&nbsp; ├── `details\_presenter.py`

&nbsp; ├── `schedule\_presenter.py`

&nbsp; ├── `preferences\_presenter.py`

&nbsp; ├── `history\_presenter.py`

&nbsp; ├── `chemistry\_presenter.py`

&nbsp; └── `hiring\_presenter.py`



\*\*Files to Modify\*\*:

1\.  `src/ui/presenters/talent\_profile\_presenter.py` (The Coordinator)

2\.  `src/ui/views/talent\_profile\_view.py` (Cleanup)



---



\#### Step 1: Create Sub-Presenter Infrastructure



Create the package directory `src/ui/presenters/talent\_profile/` and an empty `\_\_init\_\_.py`.



\#### Step 2: Implement Simple Sub-Presenters



Create the following files. Each class should inherit from `QObject` and accept `controller`, `widget`, and `parent` in `\_\_init\_\_`. They should implement a `set\_talent(talent)` method.



1\.  \*\*`details\_presenter.py`\*\*:

&nbsp;   \*   \*\*Imports\*\*: `TalentViewDataBuilder`, `Talent`.

&nbsp;   \*   \*\*Logic\*\*: Move `\_load\_and\_display\_details` logic here.

&nbsp;   \*   \*\*Method `set\_talent(talent)`\*\*: Calls the builder and updates `self.widget` (DetailsWidget).



2\.  \*\*`schedule\_presenter.py`\*\*:

&nbsp;   \*   \*\*Imports\*\*: `TalentScheduleWeekViewModel`, `TourViewModel`, `ScheduleStatus`, `time\_utils`, `Talent`.

&nbsp;   \*   \*\*Logic\*\*: Move `\_load\_and\_display\_schedule` logic here.

&nbsp;   \*   \*\*Method `set\_talent(talent)`\*\*: Fetches schedule status from controller, builds ViewModels, updates `self.widget` (ScheduleWidget).



3\.  \*\*`preferences\_presenter.py`\*\*:

&nbsp;   \*   \*\*Imports\*\*: `build\_preferences\_view\_model`, `Talent`.

&nbsp;   \*   \*\*Logic\*\*: Move `\_load\_and\_display\_preferences` logic here.

&nbsp;   \*   \*\*Method `set\_talent(talent)`\*\*: Fetches config/policy data, calls builder, updates `self.widget` (PreferencesWidget).

&nbsp;   \*   \*\*Method `handle\_theme\_change(danger\_color)`\*\*: Updates widget theme colors.



\#### Step 3: Implement Complex Sub-Presenters



1\.  \*\*`history\_presenter.py`\*\*:

&nbsp;   \*   \*\*Inputs\*\*: Needs `UIManager` in `\_\_init\_\_` for navigation.

&nbsp;   \*   \*\*Logic\*\*: Move `display\_scene\_history` logic here.

&nbsp;   \*   \*\*Signals\*\*: Connect `widget.open\_scene\_dialog\_requested` to a handler that calls `self.uimanager.show\_shot\_scene\_details` (migrated from main presenter `\_on\_shot\_scene\_details\_requested`).



2\.  \*\*`chemistry\_presenter.py`\*\*:

&nbsp;   \*   \*\*Inputs\*\*: Needs `UIManager` in `\_\_init\_\_`.

&nbsp;   \*   \*\*Logic\*\*: Move chemistry fetching/display logic here.

&nbsp;   \*   \*\*Signals\*\*: Connect widget signals (`talent\_profile\_requested`, `smart\_hover\_\*`) to `self.uimanager`.



3\.  \*\*`hiring\_presenter.py`\*\* (The most complex):

&nbsp;   \*   \*\*Inputs\*\*: Needs `view\_parent` (Window) in `\_\_init\_\_` to parent the `SponsorTourDialog`.

&nbsp;   \*   \*\*Imports\*\*: `SponsorTourDialog`, `QMessageBox`, `prepare\_role\_details\_data`, `format\_role\_details\_html`.

&nbsp;   \*   \*\*Initialization\*\*:

&nbsp;       \*   Get discount tiers from controller config.

&nbsp;       \*   Call `widget.set\_discount\_tiers`.

&nbsp;       \*   Connect widget signals:

&nbsp;           \*   `preview\_cost\_requested` -> `\_calculate\_bulk\_hiring\_preview`

&nbsp;           \*   `hire\_confirmed` -> `\_on\_hire\_confirmed`

&nbsp;           \*   `sponsor\_tour\_requested` -> `\_on\_sponsor\_tour\_requested` (New logic location)

&nbsp;           \*   `contract\_preview\_requested` -> `\_on\_contract\_preview\_requested`

&nbsp;           \*   `contract\_sign\_requested` -> `\_on\_contract\_sign\_requested`

&nbsp;   \*   \*\*Logic Migration\*\*:

&nbsp;       \*   Move `refresh\_available\_roles` logic here.

&nbsp;       \*   Move `\_calculate\_bulk\_hiring\_preview` logic here.

&nbsp;       \*   Move `\_on\_hire\_confirmed` logic here.

&nbsp;       \*   Move Contract logic here.

&nbsp;   \*   \*\*Tour Sponsorship Refactor\*\*:

&nbsp;       \*   Implement `\_on\_sponsor\_tour\_requested(roles)`:

&nbsp;           1.  Call `controller.get\_tour\_sponsorship\_preview`.

&nbsp;           2.  If infeasible, show `QMessageBox` (using `view\_parent`).

&nbsp;           3.  If feasible, create `SponsorTourDialog(..., parent=self.view\_parent)`.

&nbsp;           4.  Connect `dialog.tour\_confirmed` to local `\_execute\_tour`.

&nbsp;           5.  Call `dialog.exec()`.

&nbsp;       \*   Implement `\_execute\_tour(...)`: Calls `controller.sponsor\_tour`.



\#### Step 4: Refactor Coordinator (`talent\_profile\_presenter.py`)



1\.  \*\*Imports\*\*: Remove specific builder/dialog imports. Import the new sub-presenters.

2\.  \*\*`\_\_init\_\_`\*\*:

&nbsp;   \*   Instantiate all 6 sub-presenters.

&nbsp;   \*   Pass `self.view.details\_widget` to `DetailsPresenter`, etc.

&nbsp;   \*   Pass `self.view` as `view\_parent` to `HiringPresenter`.

3\.  \*\*Clean Up Methods\*\*:

&nbsp;   \*   Delete all `\_load\_and\_display\_\*` methods.

&nbsp;   \*   Delete `refresh\_available\_roles`, `get\_tour\_sponsorship\_preview`, `\_on\_tour\_sponsorship\_confirmed`, `\_calculate\_bulk\_hiring\_preview`, etc.

4\.  \*\*`\_load\_data\_for\_current\_talent`\*\*:

&nbsp;   \*   Retrieve `talent` object.

&nbsp;   \*   Call `set\_talent(talent)` on all sub-presenters.

5\.  \*\*Signal Handling\*\*:

&nbsp;   \*   `\_refresh\_current\_talent\_data\_on\_change`: Call `set\_talent` again on relevant sub-presenters (Schedule, Hiring, History).

&nbsp;   \*   `\_on\_setting\_changed`:

&nbsp;       \*   If `theme`: Call `preferences\_presenter.handle\_theme\_change` and `hiring\_presenter.handle\_theme\_change`.

&nbsp;       \*   If `unit\_system`: Call `details\_presenter.set\_talent` (to refresh physical stats).



\#### Step 5: View Cleanup (`talent\_profile\_view.py`)



1\.  \*\*Remove Tour Logic\*\*:

&nbsp;   \*   Delete `\_on\_sponsor\_tour\_requested`.

&nbsp;   \*   Delete `tour\_sponsorship\_confirmed` signal.

&nbsp;   \*   Remove `SponsorTourDialog` import.

&nbsp;   \*   Remove `hiring\_widget.sponsor\_tour\_requested.connect(...)` from `\_connect\_signals` (The `HiringPresenter` handles this connection now).

