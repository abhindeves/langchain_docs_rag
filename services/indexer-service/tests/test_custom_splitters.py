from indexer.custom_splitters import (
    Document,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


def test_document_repr():
    doc = Document("Hello world", {"key": "val"})
    assert repr(doc) == "Document(page_content='Hello world...', metadata={'key': 'val'})"


def test_markdown_header_text_splitter_basic():
    headers = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=True)

    markdown_text = """# Introduction
This is the intro.
## Getting Started
Some setup steps.
### Prerequisites
You need python.
## Core Concepts
Understanding the system.
"""
    chunks = splitter.split_text(markdown_text)

    # We expect 4 chunks:
    # 1. intro
    # 2. setup
    # 3. prerequisites
    # 4. core concepts
    assert len(chunks) == 4

    assert chunks[0].page_content.strip() == "This is the intro."
    assert chunks[0].metadata == {"Header 1": "Introduction"}

    assert chunks[1].page_content.strip() == "Some setup steps."
    assert chunks[1].metadata == {"Header 1": "Introduction", "Header 2": "Getting Started"}

    assert chunks[2].page_content.strip() == "You need python."
    assert chunks[2].metadata == {
        "Header 1": "Introduction",
        "Header 2": "Getting Started",
        "Header 3": "Prerequisites",
    }

    assert chunks[3].page_content.strip() == "Understanding the system."
    assert chunks[3].metadata == {"Header 1": "Introduction", "Header 2": "Core Concepts"}


def test_markdown_header_text_splitter_no_strip():
    headers = [("#", "Header 1"), ("##", "Header 2")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=False)

    markdown_text = """# Title
Content
## Section
Sub-content
"""
    chunks = splitter.split_text(markdown_text)
    assert len(chunks) == 2

    # Since strip_headers=False, the headers should be preserved inside the content.
    assert "# Title" in chunks[0].page_content
    assert "Content" in chunks[0].page_content
    assert "## Section" in chunks[1].page_content
    assert "Sub-content" in chunks[1].page_content


def test_markdown_header_text_splitter_code_block_shielding():
    headers = [("#", "Header 1"), ("##", "Header 2")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=True)

    # Contains mock headers inside code blocks
    markdown_text = """# Main Header
Intro
```python
# This is a comment, not a Header 1
def test():
    pass
```
## Sub Header
```
~~~
# Another nested code block comment
~~~
```
"""
    chunks = splitter.split_text(markdown_text)

    # We expect 2 chunks, split at "# Main Header" and "## Sub Header".
    # The headers inside the code block should be ignored.
    assert len(chunks) == 2

    assert chunks[0].metadata == {"Header 1": "Main Header"}
    assert "# This is a comment, not a Header 1" in chunks[0].page_content

    assert chunks[1].metadata == {"Header 1": "Main Header", "Header 2": "Sub Header"}
    assert "# Another nested code block comment" in chunks[1].page_content


def test_markdown_header_text_splitter_tildes_code_block():
    headers = [("#", "Header 1")]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers=True)

    markdown_text = """# Header
~~~bash
# A bash comment in tildes code block
echo "hello"
~~~
"""
    chunks = splitter.split_text(markdown_text)
    assert len(chunks) == 1
    assert "# A bash comment in tildes code block" in chunks[0].page_content


def test_markdown_header_text_splitter_no_headers():
    splitter = MarkdownHeaderTextSplitter([("#", "Header 1")], strip_headers=True)
    text = "Just some text without headers."
    chunks = splitter.split_text(text)
    assert len(chunks) == 1
    assert chunks[0].page_content == text
    assert chunks[0].metadata == {}


def test_recursive_character_text_splitter_basic():
    splitter = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=5)
    text = "abcdefghijklmnopqrstuvwxyz"
    # Single long word with no separators. It should split by character because empty string is the last separator
    chunks = splitter.split_text(text)
    assert chunks == ["abcdefghijklmnopqrst", "pqrstuvwxyz"]


def test_recursive_character_text_splitter_with_separators():
    splitter = RecursiveCharacterTextSplitter(chunk_size=15, chunk_overlap=3)
    text = "line1\n\nline2\nline3 word4 word5"

    # Should try to split at \n\n first, then \n, then space
    chunks = splitter.split_text(text)
    assert len(chunks) > 0

    # Ensure no chunk exceeds the 15 character limit
    for chunk in chunks:
        assert len(chunk) <= 15


def test_recursive_character_text_splitter_overlap():
    # Let's verify that overlapping characters are copied over correctly.
    # We will split a list of words.
    splitter = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=4, separators=[" "])
    text = "word1 word2 word3"
    chunks = splitter.split_text(text)

    # "word1 word2" is 11 chars.
    # Splits should be:
    # chunk 0: "word1" or "word1 word2" (if chunk_size was larger)
    # Here, chunk_size=10.
    # "word1" is 5 chars. "word1 word2" is 11 chars (>10).
    # So "word1" is chunk 1.
    # Remaining is "word2 word3".
    # Because of overlap, it will try to keep the last part of "word1" if it fits.
    # Let's check chunks output.
    assert len(chunks) > 0
    # The output should recombine to represent the full text.
    assert "word1" in chunks[0]
    assert "word2" in chunks[1]


def test_recursive_character_text_splitter_documents():
    splitter = RecursiveCharacterTextSplitter(chunk_size=15, chunk_overlap=2)
    docs = [
        Document("doc1 content is long", {"id": 1}),
        Document("doc2 content is also long", {"id": 2}),
    ]
    split_docs = splitter.split_documents(docs)

    assert len(split_docs) >= 2
    for doc in split_docs:
        assert isinstance(doc, Document)
        assert len(doc.page_content) <= 15
        assert doc.metadata["id"] in [1, 2]
