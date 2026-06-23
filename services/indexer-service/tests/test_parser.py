from indexer.parser import parse_raw_docs


def test_parse_raw_docs():
    # Arrange: Create mock multiline string mirroring the structure of llms-full.txt
    mock_content = """# Header 1
Source: https://example.com/doc1
This is the content for the first page.

# Header 2
Source: https://example.com/doc2
This is the content for the second page.
It has multiple lines.
"""

    # Act
    documents = parse_raw_docs(mock_content)

    # Assert
    assert len(documents) == 2

    # First document verification
    assert documents[0].metadata["title"] == "Header 1"
    assert documents[0].metadata["url"] == "https://example.com/doc1"
    assert documents[0].metadata["source"] == "https://example.com/doc1"
    assert "This is the content for the first page." in documents[0].page_content

    # Second document verification
    assert documents[1].metadata["title"] == "Header 2"
    assert documents[1].metadata["url"] == "https://example.com/doc2"
    assert "This is the content for the second page." in documents[1].page_content


def test_download_raw_docs_retry_success():
    import urllib.error
    from unittest.mock import MagicMock, patch

    from indexer.parser import download_raw_docs

    # Mock urllib.request.urlopen to fail twice then succeed
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = b"success content"

    call_count = 0

    def mock_urlopen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise urllib.error.URLError("Temporary connection issue")
        return mock_response

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        content = download_raw_docs(url="https://mockurl.com")
        assert content == "success content"
        assert call_count == 3
