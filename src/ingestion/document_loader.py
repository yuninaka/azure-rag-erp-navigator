"""ダミー業務文書（Markdown + YAMLフロントマター）の読み込み。"""

from dataclasses import dataclass
from pathlib import Path

import yaml

_SOURCE_TYPE_BY_DIRECTORY = {
    "manuals": "manual",
    "faq": "faq",
    "troubleshooting": "troubleshooting",
}


@dataclass(frozen=True)
class SourceDocument:
    title: str
    module_tags: list[str]
    last_updated: str
    source_type: str
    source_file: str
    body: str


def _split_frontmatter(raw_text: str) -> tuple[dict[str, object], str]:
    if not raw_text.startswith("---\n"):
        raise ValueError("Markdownファイルの先頭にYAMLフロントマターがありません")
    _, frontmatter_text, body = raw_text.split("---\n", 2)
    metadata = yaml.safe_load(frontmatter_text)
    return metadata, body.strip()


def _load_document(path: Path, source_type: str) -> SourceDocument:
    metadata, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    title = metadata["title"]
    module_tags = metadata["module_tags"]
    if not isinstance(title, str):
        raise TypeError(f"{path}: フロントマターの title は文字列である必要があります")
    if not isinstance(module_tags, list):
        raise TypeError(f"{path}: フロントマターの module_tags はリストである必要があります")
    return SourceDocument(
        title=title,
        module_tags=module_tags,
        last_updated=str(metadata["last_updated"]),
        source_type=source_type,
        source_file=path.name,
        body=body,
    )


def load_source_documents(root_dir: Path) -> list[SourceDocument]:
    """`root_dir` 配下の manuals/faq/troubleshooting ディレクトリから文書を読み込む。"""
    documents: list[SourceDocument] = []
    for directory_name, source_type in _SOURCE_TYPE_BY_DIRECTORY.items():
        directory = root_dir / directory_name
        for path in sorted(directory.glob("*.md")):
            documents.append(_load_document(path, source_type))
    return documents
