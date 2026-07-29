from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_complex_operational_workflows_use_shared_modal_variants():
    for template in (
        'templates/rooms/map.html',
        'templates/rooms/timeline.html',
        'templates/billing/index.html',
    ):
        source = (ROOT / template).read_text(encoding='utf-8')

        assert 'workflow-modal' in source


def test_shared_styles_cover_wide_and_fullscreen_workflow_modals():
    source = (ROOT / 'static/css/style.css').read_text(encoding='utf-8')

    assert '.workflow-modal' in source
    assert '.workflow-modal--fullscreen' in source
    assert '.workflow-modal--wide' in source
