from config import DEFAULT_SETTINGS
from models import FolderPair, SyncMode


def test_pair_roundtrip(db):
    saved = db.save_pair(FolderPair(None, "Docs", "C:/a", "D:/b", SyncMode.LEFT_TO_RIGHT))
    assert saved.id is not None
    saved.paused = True
    db.save_pair(saved)
    [loaded] = db.list_pairs()
    assert loaded == saved
    assert db.mark_synced(saved.id) == db.list_pairs()[0].last_sync
    db.delete_pair(saved.id)
    assert db.list_pairs() == []


def test_settings(db):
    assert db.settings() == DEFAULT_SETTINGS
    db.set_setting("auto_start_sync", "1")
    db.initialize()  # re-initialising keeps user changes
    assert db.settings()["auto_start_sync"] == "1"
