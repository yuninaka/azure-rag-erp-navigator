"""SessionHistoryManagerのテスト用インメモリCosmosコンテナ。"""

from copy import deepcopy

from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosResourceNotFoundError


class FakeCosmosContainer:
    def __init__(self):
        self._items: dict[str, dict] = {}
        self._pending_concurrent_docs: dict[str, dict] = {}
        self._fail_next_patch_item = False

    def simulate_concurrent_create(self, item_id: str, concurrent_document: dict) -> None:
        """次にこのidでcreate_itemが呼ばれたとき、他リクエストが先に作成し終えていたという
        レース条件を再現する。実際にドキュメントを先に書き込んだ上でconflictを送出する。"""
        self._pending_concurrent_docs[item_id] = concurrent_document

    def fail_next_patch_item(self) -> None:
        """次のpatch_item呼び出しを1回だけ失敗させる（ネットワーク瞬断等の再現用）。"""
        self._fail_next_patch_item = True

    def read_item(self, item: str, partition_key: str) -> dict:
        if item not in self._items:
            raise CosmosResourceNotFoundError(message="not found")
        return deepcopy(self._items[item])

    def create_item(self, body: dict) -> dict:
        item_id = body["id"]
        if item_id in self._pending_concurrent_docs:
            self._items[item_id] = deepcopy(self._pending_concurrent_docs.pop(item_id))
            raise CosmosResourceExistsError(message="conflict (concurrent create simulated)")
        if item_id in self._items:
            raise CosmosResourceExistsError(message="conflict")
        self._items[item_id] = deepcopy(body)
        return deepcopy(body)

    def patch_item(self, item: str, partition_key: str, patch_operations: list[dict]) -> dict:
        if self._fail_next_patch_item:
            self._fail_next_patch_item = False
            raise ConnectionError("simulated transient network failure")
        doc = self._items[item]
        for op in patch_operations:
            if op["op"] == "set":
                doc[op["path"].lstrip("/")] = op["value"]
        return deepcopy(doc)

    def query_items(self, query: str, parameters: list[dict], partition_key: str) -> list[dict]:
        params = {p["name"]: p["value"] for p in parameters}
        matches = [
            item
            for item in self._items.values()
            if item.get("sessionId") == params.get("@sid")
            and item.get("type") == params.get("@type")
        ]
        return deepcopy(sorted(matches, key=lambda item: item["turn_index"]))
