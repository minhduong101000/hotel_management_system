from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_SCRIPT = ROOT / "static/js/room_settings.js"


def test_room_settings_client_rendering_does_not_interpret_room_data_as_html():
    source = SETTINGS_SCRIPT.read_text(encoding="utf-8")

    assert "innerHTML" not in source
    assert "insertAdjacentHTML" not in source
    assert "setAttribute('onclick'" not in source
    assert 'setAttribute("onclick"' not in source
    assert "room.room_number" in source
    assert "room.room_type" in source
    assert ".textContent" in source
