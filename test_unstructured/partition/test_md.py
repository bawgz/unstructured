from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import requests
from pytest_mock import MockFixture

from test_unstructured.unit_utils import assert_round_trips_through_JSON, example_doc_path
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import ElementType, Title
from unstructured.partition.md import partition_md
from unstructured.partition.utils.constants import UNSTRUCTURED_INCLUDE_DEBUG_METADATA


def test_partition_md_from_filename():
    filename = example_doc_path("README.md")
    elements = partition_md(filename=filename)
    assert "PageBreak" not in [elem.category for elem in elements]
    assert len(elements) > 0
    for element in elements:
        assert element.metadata.filename == "README.md"
    if UNSTRUCTURED_INCLUDE_DEBUG_METADATA:
        assert {element.metadata.detection_origin for element in elements} == {"md"}


def test_partition_md_from_filename_returns_uns_elements():
    filename = example_doc_path("README.md")
    elements = partition_md(filename=filename)
    assert len(elements) > 0
    assert isinstance(elements[0], Title)


def test_partition_md_from_filename_with_metadata_filename():
    filename = example_doc_path("README.md")
    elements = partition_md(filename=filename, metadata_filename="test")
    assert "PageBreak" not in [elem.category for elem in elements]
    assert len(elements) > 0
    for element in elements:
        assert element.metadata.filename == "test"


def test_partition_md_from_file():
    filename = example_doc_path("README.md")
    with open(filename, "rb") as f:
        elements = partition_md(file=f)
    assert len(elements) > 0
    for element in elements:
        assert element.metadata.filename is None


def test_partition_md_from_file_with_metadata_filename():
    filename = example_doc_path("README.md")
    with open(filename, "rb") as f:
        elements = partition_md(file=f, metadata_filename="test")
    assert len(elements) > 0
    assert all(element.metadata.filename == "test" for element in elements)


def test_partition_md_from_text():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()
    elements = partition_md(text=text)
    assert len(elements) > 0
    for element in elements:
        assert element.metadata.filename is None


class MockResponse:
    def __init__(self, text: str, status_code: int, headers: dict[str, Any] = {}):
        self.text = text
        self.status_code = status_code
        self.ok = status_code < 300
        self.headers = headers


def test_partition_md_from_url():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()

    response = MockResponse(
        text=text,
        status_code=200,
        headers={"Content-Type": "text/markdown"},
    )
    with patch.object(requests, "get", return_value=response) as _:
        elements = partition_md(url="https://fake.url")

    assert len(elements) > 0
    for element in elements:
        assert element.metadata.filename is None


def test_partition_md_from_url_raises_with_bad_status_code():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()

    response = MockResponse(
        text=text,
        status_code=500,
        headers={"Content-Type": "text/html"},
    )
    with patch.object(requests, "get", return_value=response) as _, pytest.raises(ValueError):
        partition_md(url="https://fake.url")


def test_partition_md_from_url_raises_with_bad_content_type():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()

    response = MockResponse(
        text=text,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )
    with patch.object(requests, "get", return_value=response) as _, pytest.raises(ValueError):
        partition_md(url="https://fake.url")


def test_partition_md_raises_with_none_specified():
    with pytest.raises(ValueError):
        partition_md()


def test_partition_md_raises_with_too_many_specified():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()

    with pytest.raises(ValueError):
        partition_md(filename=filename, text=text)


def test_partition_md_from_filename_exclude_metadata():
    filename = example_doc_path("README.md")
    elements = partition_md(filename=filename, include_metadata=False)
    for i in range(len(elements)):
        assert elements[i].metadata.to_dict() == {}


def test_partition_md_from_file_exclude_metadata():
    filename = example_doc_path("README.md")
    with open(filename, "rb") as f:
        elements = partition_md(file=f, include_metadata=False)
    for i in range(len(elements)):
        assert elements[i].metadata.to_dict() == {}


def test_partition_md_from_text_exclude_metadata():
    filename = example_doc_path("README.md")
    with open(filename) as f:
        text = f.read()
    elements = partition_md(text=text, include_metadata=False)
    for i in range(len(elements)):
        assert elements[i].metadata.to_dict() == {}


# -- .metadata.last_modified ---------------------------------------------------------------------


def test_partition_md_from_file_path_gets_last_modified_from_filesystem(mocker: MockFixture):
    filesystem_last_modified = "2029-07-05T09:24:28"
    mocker.patch(
        "unstructured.partition.md.get_last_modified_date", return_value=filesystem_last_modified
    )

    elements = partition_md(example_doc_path("README.md"))

    assert all(e.metadata.last_modified == filesystem_last_modified for e in elements)


def test_partition_md_from_file_gets_last_modified_None():
    with open(example_doc_path("README.md"), "rb") as f:
        elements = partition_md(file=f)

    assert all(e.metadata.last_modified is None for e in elements)


def test_partition_md_from_text_gets_last_modified_None():
    with open(example_doc_path("README.md")) as f:
        text = f.read()

    elements = partition_md(text=text)

    assert all(e.metadata.last_modified is None for e in elements)


def test_partition_md_from_file_path_prefers_metadata_last_modified(mocker: MockFixture):
    filesystem_last_modified = "2029-07-05T09:24:28"
    metadata_last_modified = "2020-07-05T09:24:28"
    mocker.patch(
        "unstructured.partition.md.get_last_modified_date", return_value=filesystem_last_modified
    )

    elements = partition_md(
        example_doc_path("README.md"), metadata_last_modified=metadata_last_modified
    )

    assert all(e.metadata.last_modified == metadata_last_modified for e in elements)


def test_partition_md_from_file_prefers_metadata_last_modified():
    metadata_last_modified = "2020-07-05T09:24:28"
    with open(example_doc_path("README.md"), "rb") as f:
        elements = partition_md(file=f, metadata_last_modified=metadata_last_modified)

    assert all(e.metadata.last_modified == metadata_last_modified for e in elements)


def test_partition_md_from_text_prefers_metadata_last_modified():
    metadata_last_modified = "2020-07-05T09:24:28"
    with open(example_doc_path("README.md")) as f:
        text = f.read()

    elements = partition_md(text=text, metadata_last_modified=metadata_last_modified)

    assert all(e.metadata.last_modified == metadata_last_modified for e in elements)


# ------------------------------------------------------------------------------------------------


def test_partition_md_with_json():
    with open(example_doc_path("README.md")) as f:
        text = f.read()
    elements = partition_md(text=text)
    assert_round_trips_through_JSON(elements)


def test_add_chunking_strategy_by_title_on_partition_md():
    filename = example_doc_path("README.md")
    elements = partition_md(filename)
    chunk_elements = partition_md(filename, chunking_strategy="by_title")
    chunks = chunk_by_title(elements)

    assert chunk_elements != elements
    assert chunk_elements == chunks


def test_partition_md_element_metadata_has_languages():
    filename = "example-docs/README.md"
    elements = partition_md(filename=filename)
    assert elements[0].metadata.languages == ["eng"]


def test_partition_md_respects_detect_language_per_element():
    filename = "example-docs/language-docs/eng_spa_mult.md"
    elements = partition_md(filename=filename, detect_language_per_element=True)
    langs = [element.metadata.languages for element in elements]
    assert langs == [["eng"], ["spa", "eng"], ["eng"], ["eng"], ["spa"]]


def test_partition_md_parse_table():
    filename = example_doc_path("simple-table.md")
    elements = partition_md(filename=filename)
    assert len(elements) > 0
    assert elements[0].category == ElementType.TABLE
