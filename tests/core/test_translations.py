from pathlib import Path

import polib

BASE_DIR = Path(__file__).resolve().parents[2]


def test_kk_po_has_no_empty_translations():
    po = polib.pofile(str(BASE_DIR / "locale/kk/LC_MESSAGES/django.po"))
    missing = [e.msgid for e in po if not e.translated() and not e.obsolete]
    assert missing == []
