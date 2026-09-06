"""SessionHistoryManagerのテスト用インメモリCosmosコンテナ。"""

from copy import deepcopy

from azure.cosmos.exceptions import CosmosResourceNotFoundError


class FakeCosmosContainer:
    def __init__(self):
        self._items: dict[str, dict] = {}

    def read_item(self, item: str, partition_key: str) -> dict:
        if item not in self._items:
            raise CosmosResourceNotFoundError(message="not found")
        return deepcopy(self._items[item])

    def create_item(self, body: dict) -> dict:
        self._items[body["id"]] = deepcopy(body)
        return deepcopy(body)

    def patch_item(self, item: str, partition_key: str, patch_operations: list[dict]) -> dict:
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
