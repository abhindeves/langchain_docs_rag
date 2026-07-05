from indexer.chunker import chunk_markdown_docs
from indexer.custom_splitters import Document


def test_chunk_markdown_docs():
    # Arrange: Create a sample markdown document with headers and metadata
    content = """# Header 1
    This is text under header 1.

    ## Header 2
    This is text under header 2. It has some more details to ensure it splits properly.

    ### Header 3
    This is text under header 3.
    """
    doc = Document(
        page_content=content,
        metadata={"source": "test_doc.md", "category": "documentation"},
    )

    # Act
    chunks = chunk_markdown_docs([doc])

    # Assert
    assert len(chunks) > 0
    for chunk in chunks:
        assert isinstance(chunk, Document)
        # Check that page metadata was preserved
        assert chunk.metadata["source"] == "test_doc.md"
        assert chunk.metadata["category"] == "documentation"

        # Check that markdown headers are extracted in metadata
        # MarkdownHeaderTextSplitter adds headers to metadata
        assert any(k in chunk.metadata for k in ["Header 1", "Header 2", "Header 3"])

    print("\n--- Test passed successfully! ---")
