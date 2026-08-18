"""Minimal .xlsx reader (zipfile + xml.etree) — no third-party dependencies.

read_workbook(path) -> {sheet_name: [row, row, ...]} where each row is a list of Cell
objects (None for empty positions) indexed by zero-based column.
"""
import re
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass
from typing import Optional

MAIN_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NAMESPACES = {"main": MAIN_NAMESPACE}
CELL_REFERENCE_PATTERN = re.compile(r"^([A-Z]+)(\d+)$")


@dataclass
class Cell:
    reference: str
    value: object                # str, float, or None
    formula: Optional[str]       # formula text without leading "=", when present
    kind: str                    # "string" | "number" | "empty"

    def as_text(self):
        return "" if self.value is None else str(self.value)

    def as_float(self):
        return None if self.value in (None, "") else float(self.value)


def column_letters_to_index(letters):
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _read_shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for shared_item in root.findall("main:si", NAMESPACES):
        strings.append("".join(t.text or "" for t in shared_item.iter(f"{{{MAIN_NAMESPACE}}}t")))
    return strings


def _read_sheet_paths(archive):
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationship_targets = {rel.get("Id"): rel.get("Target") for rel in relationships}
    sheet_paths = []
    for sheet in workbook.find("main:sheets", NAMESPACES):
        relationship_id = sheet.get(f"{{{RELATIONSHIP_NAMESPACE}}}id")
        target = relationship_targets[relationship_id]
        target = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        sheet_paths.append((sheet.get("name"), target))
    return sheet_paths


def _parse_cell(cell_element, shared_strings):
    reference = cell_element.get("r")
    cell_type = cell_element.get("t")
    value_element = cell_element.find("main:v", NAMESPACES)
    formula_element = cell_element.find("main:f", NAMESPACES)
    formula = formula_element.text if formula_element is not None else None
    if cell_type == "s" and value_element is not None:
        return Cell(reference, shared_strings[int(value_element.text)], formula, "string")
    if cell_type == "inlineStr":
        text = "".join(t.text or "" for t in cell_element.iter(f"{{{MAIN_NAMESPACE}}}t"))
        return Cell(reference, text, formula, "string")
    if value_element is None or value_element.text is None:
        return Cell(reference, None, formula, "empty")
    if cell_type == "str":
        return Cell(reference, value_element.text, formula, "string")
    return Cell(reference, float(value_element.text), formula, "number")


def _parse_sheet(xml_bytes, shared_strings):
    root = ElementTree.fromstring(xml_bytes)
    rows = []
    for row_element in root.find("main:sheetData", NAMESPACES).findall("main:row", NAMESPACES):
        row = []
        for cell_element in row_element.findall("main:c", NAMESPACES):
            cell = _parse_cell(cell_element, shared_strings)
            column_index = column_letters_to_index(CELL_REFERENCE_PATTERN.match(cell.reference).group(1))
            while len(row) <= column_index:
                row.append(None)
            row[column_index] = cell
        rows.append(row)
    return rows


def read_workbook(path):
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        return {
            sheet_name: _parse_sheet(archive.read(sheet_path), shared_strings)
            for sheet_name, sheet_path in _read_sheet_paths(archive)
        }


def rows_as_records(rows, header_row_index=0):
    """Turn a header row + data rows into a list of {header: Cell-or-None} dictionaries.

    Rows with no non-empty cells are skipped. Each record also carries "_row_number"
    (1-based spreadsheet row) so converted JSON can cite its source row."""
    headers = [cell.as_text().strip() if cell else "" for cell in rows[header_row_index]]
    records = []
    for row_offset, row in enumerate(rows[header_row_index + 1:], start=header_row_index + 2):
        if not row or all(cell is None or cell.kind == "empty" for cell in row):
            continue
        record = {"_row_number": row_offset}
        for column_index, header in enumerate(headers):
            if not header:
                continue
            record[header] = row[column_index] if column_index < len(row) else None
        records.append(record)
    return records
