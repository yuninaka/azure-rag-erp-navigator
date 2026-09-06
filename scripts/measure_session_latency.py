"""Cosmos DBセッション管理のレイテンシを実測する。

append_turn は「セッションメタ点読み+ターン作成+メタpatch」の複数ラウンドトリップを
伴うため、ターン数が増えてもレイテンシが安定しているか（メタ点読みは常に1件、
ターン作成はO(1)）と、get_historyのレイテンシがセッションの累積ターン数に対して
どう変化するか（単一パーティションのクエリなのでO(件数)だが小規模なら軽微なはず）
を確認する。
"""

import statistics
import sys
import time
import uuid

from src.config import load_azure_cosmos_config
from src.session.cosmos_client import get_sessions_container
from src.session.history_manager import SessionHistoryManager

TURN_COUNT = 10


def _measure_append_turns(manager: SessionHistoryManager, session_id: str) -> list[float]:
    latencies_ms = []
    for i in range(TURN_COUNT):
        start = time.perf_counter()
        manager.append_turn(session_id, f"質問{i}", f"回答{i}")
        latencies_ms.append((time.perf_counter() - start) * 1000)
    return latencies_ms


def _measure_get_history(manager: SessionHistoryManager, session_id: str) -> float:
    start = time.perf_counter()
    manager.get_history(session_id)
    return (time.perf_counter() - start) * 1000


def main() -> int:
    container = get_sessions_container(load_azure_cosmos_config())
    manager = SessionHistoryManager(container)
    session_id = f"latency-test-{uuid.uuid4().hex[:8]}"

    append_latencies = _measure_append_turns(manager, session_id)
    history_latency = _measure_get_history(manager, session_id)

    print(f"append_turn x{TURN_COUNT} (session_id={session_id})")
    print(f"  1回目(セッション新規作成込み): {append_latencies[0]:.1f} ms")
    print(f"  2回目以降 平均: {statistics.mean(append_latencies[1:]):.1f} ms")
    print(f"  2回目以降 最大: {max(append_latencies[1:]):.1f} ms")
    print(f"get_history({TURN_COUNT}件): {history_latency:.1f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
