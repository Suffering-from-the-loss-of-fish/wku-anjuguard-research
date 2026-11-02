import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pilot'))
from recompute import require_complete

def test_missing_or_duplicate_outputs_fail_closed():
    with pytest.raises(ValueError):require_complete([{'id':'a'}],['a','b'],'id')
    with pytest.raises(ValueError):require_complete([{'id':'a'},{'id':'a'}],['a','b'],'id')
    require_complete([{'id':'b'},{'id':'a'}],['a','b'],'id')
