\# Refactoring Studio State and Policies



\## Goal Description

Refactor the game's state management by creating `StudioState` and `StudioStateDB` to centralize `studio\_policies`, `money`, and `location`. Migrate these attributes from `GameState` and `ShootingBloc`, and their DB counterparts. Remove policy-related logic from `Call Sheet` components, implement a new modeless policy dialog, temporarily disable scene event triggering, and update all relevant queries and persistence mechanisms.



\## User Review Required

> \[!IMPORTANT]

> \*\*Breaking Changes\*\*: This refactor changes the database schema (`ShootingBlocDB`, `GameInfoDB` usage, new `StudioStateDB`) and the `GameState` object structure. Existing saves might be incompatible or require migration (though we are treating this as a dev environment, so breaking saves is likely acceptable).



> \[!WARNING]

> \*\*Temporary Disabling\*\*: Scene event triggering will be disabled during this refactor as requested.



\## Proposed Changes



\### Data \& Database Layer



\#### \[MODIFY] \[game\_state.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/data/game\_state.py)

\- \*\*Fix Broken State\*\*: Ensure file syntax is correct.

\- \*\*New Dataclass\*\*: `StudioState` with `studio\_policies: List\[str]`, `money: int`, `location: str`.

\- \*\*Update `GameState`\*\*: Remove `active\_policies`, `money`, `studio\_location`. Add `studio: StudioState`.

\- \*\*Update `ShootingBloc`\*\*: Remove `on\_set\_policies`.



\#### \[MODIFY] \[db\_models.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/database/db\_models.py)

\- \*\*Fix Broken State\*\*: Ensure file syntax is correct and all models are present.

\- \*\*New Model\*\*: `StudioStateDB` (likely a singleton-style table or key-value, but a dedicated table `studio\_state` with one row is cleaner).

\- \*\*Update `ShootingBlocDB`\*\*: Remove `on\_set\_policies` column.

\- \*\*Update `GameInfoDB`\*\*: Deprecate usage for `money` and `studio\_location` (or migrate data if needed).



\#### \[MODIFY] \[save\_manager.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/data/save\_manager.py)

\- Update `load\_game` to populate `GameState.studio` from `StudioStateDB`.

\- Ensure `StudioState` is persisted correctly (likely via `DBManager` which handles `DataclassMapper` objects, or manual saving if `StudioState` isn't a list of objects).



\### Core \& Services



\#### \[MODIFY] \[game\_controller.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/core/game\_controller.py)

\- Update references: `self.game\_state.money` -> `self.game\_state.studio.money`.

\- Update references: `self.game\_state.studio\_location` -> `self.game\_state.studio.location`.

\- Update `find\_available\_roles\_for\_talent` to pass `studio.location`.



\#### \[MODIFY] \[talent\_availability\_checker.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/services/calculation/talent\_availability\_checker.py)

\- Update `\_check\_policies\_and\_production` to fetch policies from `StudioState` (needs access to `GameState` or `StudioState` passed in).

\- Update `check` method signature if necessary to pass `studio\_policies`.



\#### \[MODIFY] \[scene\_event\_trigger\_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/services/events/scene\_event\_trigger\_service.py)

\- \*\*Disable Events\*\*: Temporarily return `None` in `check\_for\_shoot\_event`.

\- Update logic to use `StudioState.studio\_policies` for future re-enabling.



\#### \[MODIFY] \[game\_query\_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/services/query/game\_query\_service.py)

\- Update `get\_shot\_scenes`, `get\_scene\_by\_id`, `get\_multiple\_scenes\_by\_ids`, `get\_scene\_history\_for\_talent`, `get\_incomplete\_scenes\_for\_week`, `get\_scene\_location` to query `StudioStateDB` for location instead of `GameInfoDB`.



\#### \[MODIFY] \[talent\_query\_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/services/query/talent\_query\_service.py)

\- Update `find\_available\_roles\_for\_talent` to use `studio\_location` correctly (already passed as arg, but ensure caller sends correct value).



\### Call Sheet \& Policy UI



\#### \[MODIFY] \[call\_sheet\_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/presenters/call\_sheet\_presenter.py)

\- Remove `populate\_policies` call in `initialize`.

\- Remove `on\_policy\_toggled`.



\#### \[MODIFY] \[call\_sheet\_builder.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/services/builders/call\_sheet\_builder.py)

\- Remove `active\_policies` attribute.

\- Remove `toggle\_policy`.

\- Update `commit` to not include policies (or include global ones if needed by command service, but likely not).



\#### \[MODIFY] \[call\_sheet\_dialog.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/dialogs/call\_sheet\_dialog.py)

\- Remove "On-Set Policies" GroupBox and related widgets.

\- Remove `populate\_policies` method.



\#### \[NEW] \[policy\_dialog.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/dialogs/policy\_dialog.py)

\- Create `PolicyDialog` class (modeless).

\- UI: List of checkboxes for policies.



\#### \[NEW] \[policy\_presenter.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/presenters/policy\_presenter.py)

\- Create `PolicyPresenter`.

\- Handle toggling policies -> updates `GameState.studio.studio\_policies` (and persists).



\#### \[MODIFY] \[ui\_manager.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/ui\_manager.py)

\- Add `show\_policy\_dialog` method.



\#### \[MODIFY] \[bottom\_bar\_widget.py](file:///c:/Users/Gen/Documents/PSM/Game/hire\_talent/0.4.6/src/ui/widgets/main\_window/bottom\_bar\_widget.py)

\- Add "Policies" button.

\- Emit signal on click.



\## Verification Plan



\### Automated Tests

\- None specified.



\### Manual Verification

1\.  \*\*Load Game\*\*: Verify game loads without crashing (requires DB migration or new game).

2\.  \*\*Check Studio State\*\*: Verify `money` and `location` are correct in UI.

3\.  \*\*Policy Dialog\*\*: Open "Policies" from bottom bar. Toggle policies. Close/Reopen to verify persistence.

4\.  \*\*Call Sheet\*\*: Open Call Sheet. Verify "Policies" section is GONE.

5\.  \*\*Talent Availability\*\*: Check if talent availability correctly respects the \*global\* studio policies (e.g. set a policy a talent dislikes, check if they refuse).

6\.  \*\*Scene Events\*\*: Verify no events trigger during shooting.



