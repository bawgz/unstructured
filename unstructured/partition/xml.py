from __future__ import annotations

import copy
from io import BytesIO
from typing import IO, Any, Iterator, Optional, cast

from lxml import etree

from unstructured.chunking import add_chunking_strategy
from unstructured.documents.elements import (
    Element,
    ElementMetadata,
    Text,
    process_metadata,
)
from unstructured.file_utils.encoding import read_txt_file
from unstructured.file_utils.filetype import add_metadata_with_filetype
from unstructured.file_utils.model import FileType
from unstructured.partition.common.common import (
    exactly_one,
    spooled_to_bytes_io_if_needed,
)
from unstructured.partition.common.metadata import get_last_modified_date
from unstructured.partition.lang import apply_lang_metadata
from unstructured.partition.text import element_from_text

DETECTION_ORIGIN: str = "xml"


def get_leaf_elements(
    filename: Optional[str] = None,
    file: Optional[IO[bytes]] = None,
    text: Optional[str] = None,
    xml_path: Optional[str] = None,
) -> Iterator[Optional[str]]:
    """Get leaf elements from the XML tree defined in filename, file, or text."""
    exactly_one(filename=filename, file=file, text=text)
    if filename:
        return _get_leaf_elements(filename, xml_path=xml_path)
    elif file:
        return _get_leaf_elements(file=spooled_to_bytes_io_if_needed(file), xml_path=xml_path)
    else:
        b = BytesIO(bytes(cast(str, text), encoding="utf-8"))
        return _get_leaf_elements(b, xml_path=xml_path)


def _get_leaf_elements(
    file: str | IO[bytes],
    xml_path: Optional[str] = None,
) -> Iterator[Optional[str]]:
    """Parse the XML tree in a memory efficient manner if possible."""
    element_stack: list[etree._Element] = []  # pyright: ignore[reportPrivateUsage]

    element_iterator = etree.iterparse(file, events=("start", "end"), resolve_entities=False)
    # NOTE(alan) If xml_path is used for filtering, I've yet to find a good way to stream
    # elements through in a memory efficient way, so we bite the bullet and load it all into
    # memory.
    if xml_path is not None:
        _, element = next(element_iterator)
        compiled_path = etree.XPath(xml_path)
        element_iterator = (("end", el) for el in compiled_path(element))

    for event, element in element_iterator:
        if event == "start":
            element_stack.append(element)

        if event == "end":
            if element.text is not None and element.text.strip():
                yield element.text

            element.clear()

        while element_stack and element_stack[-1].getparent() is None:
            element_stack.pop()


@process_metadata()
@add_metadata_with_filetype(FileType.XML)
@add_chunking_strategy
def partition_xml(
    filename: Optional[str] = None,
    file: Optional[IO[bytes]] = None,
    text: Optional[str] = None,
    xml_keep_tags: bool = False,
    xml_path: Optional[str] = None,
    metadata_filename: Optional[str] = None,
    include_metadata: bool = True,
    encoding: Optional[str] = None,
    metadata_last_modified: Optional[str] = None,
    languages: Optional[list[str]] = ["auto"],
    detect_language_per_element: bool = False,
    **kwargs: Any,
) -> list[Element]:
    """Partitions an XML document into its document elements.

    Parameters
    ----------
    filename
        A string defining the target filename path.
    file
        A file-like object using "rb" mode --> open(filename, "rb").
    text
        The text of the XML file.
    xml_keep_tags
        If True, will retain the XML tags in the output. Otherwise it will simply extract
        the text from within the tags.
    xml_path
        The xml_path to use for extracting the text. Only used if xml_keep_tags=False.
    encoding
        The encoding method used to decode the text input. If None, utf-8 will be used.
    include_metadata
        Determines whether or not metadata is included in the metadata attribute on the
        elements in the output.
    metadata_last_modified
        The day of the last modification.
    languages
        User defined value for `metadata.languages` if provided. Otherwise language is detected
        using naive Bayesian filter via `langdetect`. Multiple languages indicates text could be
        in either language.
        Additional Parameters:
            detect_language_per_element
                Detect language per element instead of at the document level.
    """
    exactly_one(filename=filename, file=file, text=text)

    elements: list[Element] = []

    last_modification_date = get_last_modified_date(filename) if filename else None

    if include_metadata:
        metadata = ElementMetadata(
            filename=metadata_filename or filename,
            last_modified=metadata_last_modified or last_modification_date,
        )
        metadata.detection_origin = DETECTION_ORIGIN
    else:
        metadata = ElementMetadata()

    if xml_keep_tags:
        if filename:
            raw_text = read_txt_file(filename=filename, encoding=encoding)[1]
        elif file:
            raw_text = read_txt_file(file=spooled_to_bytes_io_if_needed(file), encoding=encoding)[1]
        else:
            assert text is not None
            raw_text = text

        elements = [Text(text=raw_text, metadata=metadata)]

    else:
        leaf_elements = get_leaf_elements(
            filename=filename,
            file=file,
            text=text,
            xml_path=xml_path,
        )
        for leaf_element in leaf_elements:
            if leaf_element:
                element = element_from_text(leaf_element)
                element.metadata = copy.deepcopy(metadata)
                elements.append(element)

    elements = list(
        apply_lang_metadata(
            elements=elements,
            languages=languages,
            detect_language_per_element=detect_language_per_element,
        ),
    )
    return elements
