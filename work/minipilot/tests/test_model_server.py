import pytest
from pilot.model_server import parse_output


def test_valid_normalizes_declared_units():
    result = parse_output('{"quality_usable":true,"objects":[{"category":"chair","bbox":[10,20,100,400]}]}')
    assert result["objects"][0]["bbox"] == [.01,.02,.1,.4]


@pytest.mark.parametrize("text", [
    '{"quality_usable":"true","objects":[]}',
    '{"quality_usable":true,"objects":[{"category":"cable","bbox":[10,20,100,400]}]}',
    '{"quality_usable":true,"objects":[{"category":"chair","bbox":[100,20,10,400]}]}',
    '{"quality_usable":true,"objects":[{"category":"chair","bbox":[0,20,1001,400]}]}',
    'The answer is {"quality_usable":true,"objects":[]}',
    '{"quality_usable":true,"objects":[',
])
def test_malformed_does_not_become_empty_success(text):
    with pytest.raises((ValueError, TypeError)):
        parse_output(text)


def test_unusable_is_preserved():
    assert parse_output('{"quality_usable":false,"objects":[]}')["quality_usable"] is False
