"""RAG回答生成の動作確認用CLI。1つの質問に対する回答と引用元を表示する。

使い方: uv run python scripts/ask_question.py "質問文" [session_id]
"""

import sys
import uuid

from src.rag.dependencies import build_rag_dependencies
from src.rag.generator import generate_answer

_MIN_ARGC_WITH_QUESTION = 2
_ARGC_WITH_SESSION_ID = 3


def main() -> int:
    if len(sys.argv) < _MIN_ARGC_WITH_QUESTION:
        print('使い方: uv run python scripts/ask_question.py "質問文" [session_id]')
        return 1
    query = sys.argv[1]
    has_session_id = len(sys.argv) >= _ARGC_WITH_SESSION_ID
    session_id = sys.argv[2] if has_session_id else f"cli-{uuid.uuid4().hex[:8]}"

    deps = build_rag_dependencies()
    result = generate_answer(query=query, session_id=session_id, deps=deps)

    print(f"session_id: {session_id}")
    print(f"\n回答:\n{result.answer}")
    print("\n引用元:")
    for i, citation in enumerate(result.citations, start=1):
        print(f"  [{i}] {citation.section_path} ({citation.source_file})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
