import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class Document:
    """
    Lightweight, custom implementation of LangChain's Document class.
    """

    def __init__(self, page_content: str, metadata: dict[str, Any] | None = None):
        self.page_content = page_content
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"Document(page_content='{self.page_content[:50]}...', metadata={self.metadata})"


class MarkdownHeaderTextSplitter:
    """
    Lightweight, custom implementation of LangChain's MarkdownHeaderTextSplitter.
    Splits markdown text based on specified headers (#, ##, ###) while maintaining context in metadata.
    """

    def __init__(
        self,
        headers_to_split_on: list[tuple[str, str]],
        strip_headers: bool = True,
    ):
        self.headers_to_split_on = sorted(headers_to_split_on, key=lambda split: len(split[0]), reverse=True)
        self.strip_headers = strip_headers

    def aggregate_lines_to_chunks(self, lines: list[dict[str, Any]]) -> list[Document]:
        aggregated_chunks: list[dict[str, Any]] = []
        for line in lines:
            if aggregated_chunks and aggregated_chunks[-1]["metadata"] == line["metadata"]:
                aggregated_chunks[-1]["content"] += "\n" + line["content"]
            else:
                aggregated_chunks.append(line)

        return [Document(page_content=chunk["content"], metadata=chunk["metadata"]) for chunk in aggregated_chunks]

    def split_text(self, text: str) -> list[Document]:
        lines = text.split("\n")
        lines_with_metadata: list[dict[str, Any]] = []
        current_content: list[str] = []
        current_metadata: dict[str, str] = {}
        header_stack: list[dict[str, Any]] = []
        initial_metadata: dict[str, str] = {}
        in_code_block = False
        opening_fence = ""

        for line in lines:
            stripped_line = line.strip()
            stripped_line = "".join(filter(str.isprintable, stripped_line))

            # Handle code blocks
            if not in_code_block:
                if stripped_line.startswith("```") and stripped_line.count("```") == 1:
                    in_code_block = True
                    opening_fence = "```"
                elif stripped_line.startswith("~~~"):
                    in_code_block = True
                    opening_fence = "~~~"
            elif stripped_line.startswith(opening_fence):
                in_code_block = False
                opening_fence = ""

            if in_code_block:
                current_content.append(line)
                continue

            header_found = False
            for sep, name in self.headers_to_split_on:
                is_header = stripped_line.startswith(sep) and (len(stripped_line) == len(sep) or stripped_line[len(sep)] == " ")
                if is_header:
                    current_header_level = sep.count("#")
                    while header_stack and header_stack[-1]["level"] >= current_header_level:
                        popped = header_stack.pop()
                        if popped["name"] in initial_metadata:
                            initial_metadata.pop(popped["name"])

                    header_text = stripped_line[len(sep) :].strip()
                    header = {
                        "level": current_header_level,
                        "name": name,
                        "data": header_text,
                    }
                    header_stack.append(header)
                    initial_metadata[name] = header_text

                    if current_content:
                        lines_with_metadata.append(
                            {
                                "content": "\n".join(current_content),
                                "metadata": current_metadata.copy(),
                            }
                        )
                        current_content.clear()

                    if not self.strip_headers:
                        current_content.append(line)

                    header_found = True
                    break

            if not header_found:
                current_content.append(line)

            current_metadata = initial_metadata.copy()

        if current_content:
            lines_with_metadata.append(
                {
                    "content": "\n".join(current_content),
                    "metadata": current_metadata.copy(),
                }
            )

        return self.aggregate_lines_to_chunks(lines_with_metadata)


class RecursiveCharacterTextSplitter:
    """
    Lightweight, custom implementation of LangChain's RecursiveCharacterTextSplitter.
    Recursively splits text by paragraph, line, and word separators to achieve target chunk sizes.
    """

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = separators or ["\n\n", "\n", " ", ""]

    def _split_text_with_regex(self, text: str, separator: str) -> list[str]:
        if not separator:
            return list(text)
        splits = re.split(separator, text)
        return [s for s in splits if s]

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        final_chunks = []
        separator = separators[-1]
        new_separators = []

        for i, s_ in enumerate(separators):
            if not s_:
                separator = s_
                break
            if re.search(re.escape(s_), text):
                separator = s_
                new_separators = separators[i + 1 :]
                break

        splits = self._split_text_with_regex(text, re.escape(separator))

        good_splits = []
        for s in splits:
            if len(s) < self._chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator)
                    final_chunks.extend(merged)
                    good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    final_chunks.extend(self._split_text(s, new_separators))

        if good_splits:
            merged = self._merge_splits(good_splits, separator)
            final_chunks.extend(merged)

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        separator_len = len(separator)
        docs = []
        current_doc = []
        total = 0

        for d in splits:
            len_ = len(d)
            if total + len_ + (separator_len if len(current_doc) > 0 else 0) > self._chunk_size:
                if len(current_doc) > 0:
                    doc = separator.join(current_doc)
                    if doc:
                        docs.append(doc)
                    while total > self._chunk_overlap or (total + len_ + (separator_len if len(current_doc) > 0 else 0) > self._chunk_size and total > 0):
                        total -= len(current_doc[0]) + (separator_len if len(current_doc) > 1 else 0)
                        current_doc = current_doc[1:]

            current_doc.append(d)
            total += len_ + (separator_len if len(current_doc) > 1 else 0)

        doc = separator.join(current_doc)
        if doc:
            docs.append(doc)
        return docs

    def split_text(self, text: str) -> list[str]:
        return self._split_text(text, self._separators)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        texts = []
        metadatas = []
        for doc in documents:
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)

        split_docs = []
        for i, text in enumerate(texts):
            chunks = self.split_text(text)
            metadata = metadatas[i]
            for chunk in chunks:
                split_docs.append(Document(page_content=chunk, metadata=metadata.copy()))
        return split_docs
