from dev_game import prepare_casting_scene
from ui.presenters.talent_tab_presenter import TalentTabPresenter


def test_reset_clears_the_role_and_keeps_the_filter_panel_open(window):
    scene = prepare_casting_scene(window.controller)
    role, = scene.virtual_performers
    presenter = next(p for p in window.ui_manager.tab_presenters if isinstance(p, TalentTabPresenter))
    filters = presenter.filter_widget
    view = presenter.view
    window.settings_manager.set_setting("auto_hide_filter_on_apply", True)
    view.set_filter_panel_visible(True)
    filters.scene_combo.setCurrentIndex(filters.scene_combo.findData(scene.id))
    filters.role_combo.setCurrentIndex(filters.role_combo.findData(role.id))

    assert not filters.ethnicity_tree.isEnabled()
    assert filters.ethnicity_group.title() == "Ethnicity (set by role)"
    filters.apply_btn.click()
    assert view.advanced_filters["vp_id"] == role.id
    assert not view.is_filter_panel_expanded

    view.set_filter_panel_visible(True)
    filters.reset_btn.click()

    assert view.is_filter_panel_expanded
    assert "vp_id" not in view.advanced_filters
    assert filters.ethnicity_tree.isEnabled()
    assert filters.ethnicity_group.title() == "Ethnicity"
