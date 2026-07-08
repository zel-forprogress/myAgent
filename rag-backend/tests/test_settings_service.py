from app.models import AppSetting
from app.services.settings_service import (
    RETRIEVAL_MIN_SCORE_DEFAULT,
    get_retrieval_min_score,
    set_retrieval_min_score,
)


class FakeSettingsSession:
    def __init__(self):
        self.rows = {}

    def get(self, model, key):
        _ = model
        return self.rows.get(key)

    def add(self, row):
        self.rows[row.key] = row

    def commit(self):
        pass


def test_retrieval_min_score_uses_default():
    session = FakeSettingsSession()
    assert get_retrieval_min_score(session) == RETRIEVAL_MIN_SCORE_DEFAULT


def test_set_retrieval_min_score():
    session = FakeSettingsSession()
    set_retrieval_min_score(session, 0.62)

    assert get_retrieval_min_score(session) == 0.62


def test_retrieval_min_score_clamps_to_valid_range():
    session = FakeSettingsSession()
    set_retrieval_min_score(session, 1.5)
    assert get_retrieval_min_score(session) == 1.0

    row = session.get(AppSetting, "retrieval.min_score")
    row.value = "-0.2"

    assert get_retrieval_min_score(session) == 0.0
