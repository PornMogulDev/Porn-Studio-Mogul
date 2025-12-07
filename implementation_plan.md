# Introduce 13-Month Calendar System

## Overview

Adding a 13-month calendar system (4 weeks per month, 52 weeks per year) with month display in the UI and converting weekly contract scene limits to monthly limits. Backend batching logic for AI studios and tours will use monthly cycles.

## User Review Required

> [!WARNING]
> **Breaking Change: Contract System**  
> Contracts will change from `max_scenes_per_week` to `max_scenes_per_month`. This affects:
> - Contract validation logic (now checks 4-week periods instead of single weeks)
> - Database migration needed for existing contracts
> - Players will have more flexibility but monthly validation is more complex

> [!IMPORTANT]
> **Batch Processing Changes**  
> AI studios and autonomous tours will switch from variable weekly batching to fixed monthly batching (13 batches per year). This changes when AI decisions occur.

## Proposed Changes

### Core Time Utilities

#### [MODIFY] [time_utils.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/utils/time_utils.py)

Add month conversion functions:
- `to_month(absolute_week: int) -> Tuple[int, int, int]` - Returns (year, month, week_in_month) 
- `from_month(year: int, month: int) -> int` - Returns first absolute_week of the month
- `get_month_range(absolute_week: int) -> Tuple[int, int]` - Returns (start_week, end_week) for the month containing the given week

Update constant:
- Add `WEEKS_PER_MONTH = 4`
- Add `MONTHS_PER_YEAR = 13`

---

### UI Updates

#### [MODIFY] [top_bar_widget.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/widgets/main_window/top_bar_widget.py)

Update display format from "Week X, Year YYYY" to "Month X, Week Y, Year YYYY":
- Modify `update_time_display()` to accept month parameter
- Update label text format

**Presenter changes needed**: The presenter calling this widget needs to calculate and pass the month value.

#### [MODIFY] [hiring_widget.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/ui/widgets/talent_profile/hiring_widget.py)

Update contract negotiation UI:
- Change "Max Scenes/Week" label to "Max Scenes/Month"
- Update spinner range from 1-7 to 4-28 (assuming 1-7 per week × 4 weeks)
- Update preview label to show monthly limit

---

### Data Models

#### [MODIFY] [game_state.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/data/game_state.py)

Update `Contract` dataclass:
- Rename `max_scenes_per_week: int` to `max_scenes_per_month: int`

#### [MODIFY] [db_models.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/database/db_models.py)

Update `ContractDB`:
- Rename `max_scenes_per_week` column to `max_scenes_per_month`
- **Migration required**: Add database migration script to update column name and multiply existing values by 4

---

### Contract Validation & Calculation

#### [MODIFY] [bulk_booking_validator.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/calculation/bulk_booking_validator.py)

Change validation from weekly to monthly:
- Replace `weekly_counts` with `monthly_counts` (keyed by month, not absolute_week)
- In `try_book_role()`, calculate which month the scene belongs to
- Check against `contract.max_scenes_per_month` instead of `max_scenes_per_week`
- For non-contracted talent, keep weekly ambition-based calculation but accumulate across the month

**Critical**: Maintain weekly burnout detection - this should not change.

#### [MODIFY] [contract_command_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/contract_command_service.py)

Update contract creation:
- Change parameter from `max_scenes_per_week` to `max_scenes_per_month` in `sign_contract()`
- Keep weekly salary payment logic unchanged (paid every week)

#### [MODIFY] [talent_demand_calculator.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/calculation/talent_demand_calculator.py)

Update salary calculation:
- In `calculate_contract_salary()`, parameter changes from `max_scenes_per_week` to `max_scenes_per_month`
- Adjust formula: `weekly_salary = adjusted_base * (max_scenes_per_month / 4) * contract_premium`
  - This maintains that more scenes per month = higher weekly salary

---

### Backend Monthly Batching

#### [MODIFY] [ai_studio_director.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/ai/ai_studio_director.py)

Update to monthly cycles:
- In `_should_create_scene()`, use monthly batching instead of weekly
- Calculate: `month = time_utils.to_month(current_week)[1]`
- Probability: `studio.scenes_per_month_target / 4.0` (remains same formula, but clearer intent)
- Add randomization to distribute within the month's 4 weeks

#### [MODIFY] [tour_command_service.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/command/tour_command_service.py)

Update autonomous tour batching:
- In `process_autonomous_tour_decisions()`, change from weekly modulo batching to monthly
- Replace: `target_remainder = current_absolute_week % batch_size` 
- With: Calculate month, use `month % 13` or similar for 13 batches
- Filter candidates based on monthly batch assignment

---

### Configuration

#### [MODIFY] [configs.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/src/services/models/configs.py)

Update `HiringConfig`:
- Keep `max_scenes_per_week_base` and `max_scenes_per_week_ambition_modifier` (still used for non-contracted talent weekly limits)
- Document that these apply per-week for non-contracted talent, but contracts use monthly limits

---

### Database Migration

#### [NEW] [migration_script.py](file:///c:/Users/Gen/Documents/PSM/Game/hire_talent/0.4.6/migrations/add_monthly_contract_limits.py)

Create migration to:
1. Add new column `max_scenes_per_month` with NOT NULL constraint
2. Populate with `max_scenes_per_week * 4` for existing contracts
3. Drop old `max_scenes_per_week` column

**Note**: Verify migration approach with existing database setup.

---

## Verification Plan

### Automated Tests

**Note**: The project has limited test coverage (only 4 test files in `tests/` directory). Most verification will need to be manual.

### Manual Verification

#### Test 1: Time Display
1. Launch the game
2. Verify top bar shows "Month X, Week Y, Year YYYY" format
3. Click "Next Week" button multiple times
4. Verify:
   - Week cycles 1-4 within each month
   - Month increments when week goes from 4 to 1
   - Year increments when month goes from 13 to 1

#### Test 2: Contract Creation & Monthly Limits
1. Open talent profile for any talent
2. Click "Offer Exclusive Contract"
3. Verify UI shows "Max Scenes/Month" (not "per week")
4. Set to 8 scenes/month
5. Sign contract
6. Attempt to hire talent for 3 scenes in week 1 of month ✓ (should succeed, 3 < 8)
7. Advance to week 2 of same month
8. Attempt to hire for 6 more scenes ✓ (should fail, 3+6=9 > 8)
9. Advance to next month
10. Attempt to hire for 6 scenes ✓ (should succeed, new month resets counter)

#### Test 3: Non-Contracted Talent Weekly Limits
1. Find talent without contract
2. Hire for 2 scenes in same week (assuming default limit is 2)
3. Attempt to hire for 3rd scene in same week ✗ (should fail with "Weekly limit reached")
4. Verify this is still enforced WEEKLY, not monthly

#### Test 4: AI Studio Monthly Batching
1. Note current week and month
2. Observe AI studio scene creation patterns over 2-3 months
3. Verify scenes are created approximately evenly across months (not clustered by week modulo)

#### Test 5: Tour Autonomous Decisions
1. Observe talent autonomous tour booking over several months
2. Verify batching appears monthly (different talents evaluated each month)

#### Test 6: Database Migration
1. Create a test save with contracts that have `max_scenes_per_week = 2`
2. Run migration script
3. Load save and verify contracts show `max_scenes_per_month = 8`
4. Verify validation works correctly with migrated data

### Success Criteria
- [ ] Top bar displays months correctly
- [ ] Week/month/year transitions are accurate
- [ ] Contract UI shows monthly limits
- [ ] Monthly contract validation works (Test 2 passes)
- [ ] Weekly limits still apply to non-contracted talent (Test 3 passes)
- [ ] AI studios use monthly batching
- [ ] Tours use monthly batching
- [ ] Migration preserves contract intent (weekly limit × 4)
