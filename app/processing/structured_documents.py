from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from pathlib import Path

import defusedxml.ElementTree as ET


# The security gate forbids importing stdlib `xml` at all, so the serializer's
# namespace registry is reached through defusedxml, which re-exports tostring from it.
_register_namespace = ET.tostring.__globals__["register_namespace"]

STRUCTURED_DOCUMENT_EXTENSIONS = frozenset({".docx", ".xlsx", ".hwpx"})


class StructuredDocumentError(ValueError):
    pass


def rewrite_document(path: Path, destination: Path, transform: Callable[[str], str]) -> None:
    """Rewrite Office Open XML text nodes while preserving the package entries."""
    if not zipfile.is_zipfile(path):
        raise StructuredDocumentError("문서가 올바른 ZIP/XML 형식이 아닙니다.")

    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(destination, "w") as target:
            for info in source.infolist():
                data = source.read(info)
                if info.filename.lower().endswith(".xml"):
                    data = _rewrite_xml(data, transform)
                target.writestr(info, data)
    except (OSError, zipfile.BadZipFile) as exc:
        raise StructuredDocumentError("문서 패키지를 읽거나 저장하지 못했습니다.") from exc


def _rewrite_xml(data: bytes, transform: Callable[[str], str]) -> bytes:
    try:
        _register_namespaces(data)
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise StructuredDocumentError("문서 XML을 읽지 못했습니다.") from exc

    changed = False
    for element in root.iter():
        if _local_name(element.tag) not in {"t", "delText"} or not element.text:
            continue
        transformed = transform(element.text)
        if transformed != element.text:
            element.text = transformed
            changed = True
    if not changed:
        return data
    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=data.lstrip().startswith(b"<?xml"),
    )


def _register_namespaces(data: bytes) -> None:
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
        if prefix in {"xml", "xmlns"} or (prefix and re.fullmatch(r"ns\d+", prefix)):
            continue
        _register_namespace(prefix, uri)


def _local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""
