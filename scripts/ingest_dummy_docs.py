"""ダミー業務文書を全チャンク分割方針でAzure AI Searchに投入する。"""

import sys
from pathlib import Path

from src.ingestion.ingest_pipeline import run_ingestion

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dummy_docs"


def main() -> int:
    print(f"投入元ディレクトリ: {DATA_DIR}")
    try:
        uploaded_counts = run_ingestion(DATA_DIR)
    except Exception as error:  # noqa: BLE001 - CLIとして原因を表示して終了する
        print(f"投入失敗: {type(error).__name__}: {error}")
        return 1

    for strategy, count in uploaded_counts.items():
        print(f"  {strategy}: {count} 件投入")
    print("OK: 全戦略の投入が完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
