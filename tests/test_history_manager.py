import logging

import pytest

from src.session.history_manager import Citation, SessionHistoryManager
from tests.fakes.fake_cosmos_container import FakeCosmosContainer


def _manager() -> SessionHistoryManager:
    return SessionHistoryManager(FakeCosmosContainer(), session_ttl_seconds=3600)


def test_start_session_creates_meta_once_and_is_idempotent() -> None:
    manager = _manager()

    first = manager.start_session("session-1")
    second = manager.start_session("session-1")

    assert first["turn_count"] == 0
    assert first["created_at"] == second["created_at"]


def test_start_session_recovers_from_concurrent_creation_race() -> None:
    container = FakeCosmosContainer()
    manager = SessionHistoryManager(container, session_ttl_seconds=3600)
    concurrent_meta = {
        "id": "session-race",
        "sessionId": "session-race",
        "type": "session_meta",
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_active_at": "2026-01-01T00:00:00+00:00",
        "turn_count": 0,
        "ttl": 3600,
    }
    container.simulate_concurrent_create("session-race", concurrent_meta)

    result = manager.start_session("session-race")

    assert result == concurrent_meta


def test_append_turn_assigns_sequential_indices_and_updates_turn_count() -> None:
    manager = _manager()

    turn0 = manager.append_turn("session-1", "質問1", "回答1")
    turn1 = manager.append_turn("session-1", "質問2", "回答2")

    assert turn0.turn_index == 0
    assert turn1.turn_index == 1
    meta = manager.start_session("session-1")
    expected_turn_count = 2
    assert meta["turn_count"] == expected_turn_count


def test_append_turn_without_prior_start_session_still_works() -> None:
    manager = _manager()

    turn = manager.append_turn("new-session", "初回質問", "初回回答")

    assert turn.turn_index == 0


def test_get_history_returns_turns_in_order_with_citations() -> None:
    manager = _manager()
    citations = [
        Citation(
            title="初期設定ガイド",
            section_path="初期設定ガイド > テナントの作成",
            source_file="01_initial_setup.md",
        )
    ]

    manager.append_turn("session-1", "質問1", "回答1", citations)
    manager.append_turn("session-1", "質問2", "回答2")

    history = manager.get_history("session-1")

    assert [t.user_message for t in history] == ["質問1", "質問2"]
    assert history[0].citations == citations
    assert history[1].citations == []


def test_get_history_respects_max_turns() -> None:
    manager = _manager()
    for i in range(5):
        manager.append_turn("session-1", f"質問{i}", f"回答{i}")

    history = manager.get_history("session-1", max_turns=2)

    assert [t.user_message for t in history] == ["質問3", "質問4"]


def test_append_turn_logs_and_reraises_when_turn_count_patch_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    container = FakeCosmosContainer()
    manager = SessionHistoryManager(container, session_ttl_seconds=3600)
    container.fail_next_patch_item()

    with caplog.at_level(logging.WARNING), pytest.raises(ConnectionError):
        manager.append_turn("session-1", "質問1", "回答1")

    assert any("turn_count" in record.message for record in caplog.records)
    # ターン本体はcreate_item済みのため、コンテナ上には保存されている
    stored_turn = container.read_item(item="session-1-0000", partition_key="session-1")
    assert stored_turn["user_message"] == "質問1"


def test_build_chat_messages_alternates_user_and_assistant_roles() -> None:
    manager = _manager()
    manager.append_turn("session-1", "質問1", "回答1")
    manager.append_turn("session-1", "質問2", "回答2")

    messages = manager.build_chat_messages("session-1")

    assert messages == [
        {"role": "user", "content": "質問1"},
        {"role": "assistant", "content": "回答1"},
        {"role": "user", "content": "質問2"},
        {"role": "assistant", "content": "回答2"},
    ]
