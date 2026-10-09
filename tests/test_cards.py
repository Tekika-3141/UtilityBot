import pytest
from app.cards import CardDocument, render_card


def test_card_coordinates_and_render():
    document = CardDocument(elements=[{"id": "welcome", "type": "text", "x": 0.1, "y": 0.2, "text": "こんにちは"}])
    output = render_card(document, {})
    assert output[:8] == b"\x89PNG\r\n\x1a\n"


def test_card_rejects_unknown_element():
    with pytest.raises(ValueError):
        CardDocument(elements=[{"id": "x", "type": "script", "x": 0, "y": 0}])
