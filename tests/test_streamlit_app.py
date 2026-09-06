import logging

from src.app.streamlit_app import _generate_answer_safely
from src.rag.generator import RagAnswer


def _raising_generate_answer(*, query, session_id, **kwargs):
    raise RuntimeError("boom: some Azure SDK internal detail")


def _succeeding_generate_answer(*, query, session_id, **kwargs):
    return RagAnswer(answer="回答です。", citations=[])


def test_generate_answer_safely_returns_result_on_success():
    result = _generate_answer_safely(
        query="質問", session_id="session-1", generate_answer_fn=_succeeding_generate_answer
    )

    assert result == RagAnswer(answer="回答です。", citations=[])


def test_generate_answer_safely_returns_none_and_logs_on_failure(caplog):
    with caplog.at_level(logging.ERROR):
        result = _generate_answer_safely(
            query="質問", session_id="session-1", generate_answer_fn=_raising_generate_answer
        )

    assert result is None
    error_record = next(r for r in caplog.records if "RAG回答生成に失敗しました" in r.message)
    # logger.exception なので例外の詳細(traceback)はexc_infoとしてログレコードに残る
    assert error_record.exc_info is not None
    assert "boom: some Azure SDK internal detail" in str(error_record.exc_info[1])
