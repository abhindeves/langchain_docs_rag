import logging

from indexer.custom_splitters import (
    Document,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger(__name__)


def chunk_markdown_docs(docs: list[Document]) -> list[Document]:
    """
    Header-aware chunking.
    """
    logger.info(f"Splitting {len(docs)} documents using header-aware chunking...")

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ],
        strip_headers=False,
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=100,
    )

    all_chunks = []
    for doc in docs:
        header_splits = markdown_splitter.split_text(doc.page_content)

        # Preserve parent file metadata
        for split in header_splits:
            split.metadata.update(doc.metadata)

        # Recursively split any large header sections
        splits = text_splitter.split_documents(header_splits)

        # Stitch context headers and source URL back into page content
        for split in splits:
            context_lines = []

            # 1. Add Source URL if present
            if "url" in split.metadata:
                context_lines.append(f"Source URL: {split.metadata['url']}")

            # 2. Build header breadcrumb path
            headers = []
            if "Header 1" in split.metadata:
                headers.append(split.metadata["Header 1"])
            if "Header 2" in split.metadata:
                headers.append(split.metadata["Header 2"])
            if "Header 3" in split.metadata:
                headers.append(split.metadata["Header 3"])

            if headers:
                context_lines.append(f"Document Context: {' > '.join(headers)}")

            # 3. Prepend to chunk content
            if context_lines:
                prefix = "\n".join(context_lines) + "\n---\n"
                split.page_content = prefix + split.page_content

        all_chunks.extend(splits)

    logger.info(f"Created {len(all_chunks)} markdown chunks successfully.")
    return all_chunks
