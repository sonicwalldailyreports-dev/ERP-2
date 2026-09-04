"""Dependency-free export adapters.

CSV is the canonical interchange format.  SpreadsheetML is deliberately used
for XLSX requests so Excel can open the result without adding a package.  PDF
is a pluggable adapter: deployments can register a renderer later without
coupling the API to a system PDF library.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal
from html import escape
from typing import Any

from fastapi import HTTPException

from app.modules.reports.schemas import ReportPage


def _value(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return "" if value is None else str(value)


def _csv_value(value: Any) -> str:
    rendered = _value(value)
    if rendered.startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered


class CsvExporter:
    media_type = "text/csv; charset=utf-8"
    extension = "csv"

    def render(self, report: ReportPage) -> bytes:
        stream = io.StringIO(newline="")
        rows = report.items
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        if not keys:
            keys = list(report.totals) or ["message"]
            rows = [report.totals] if report.totals else [{"message": "No rows"}]
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: _csv_value(row.get(key)) for key in keys} for row in rows)
        if report.totals:
            writer.writerow({key: _csv_value(report.totals.get(key)) for key in keys})
        return stream.getvalue().encode("utf-8-sig")


class SpreadsheetMlExporter:
    """Minimal OOXML workbook writer, requiring no third-party dependency."""

    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    extension = "xlsx"

    def render(self, report: ReportPage) -> bytes:
        rows = report.items
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        if not keys:
            keys = list(report.totals) or ["message"]
            rows = [report.totals] if report.totals else [{"message": "No rows"}]
        cells = [[key for key in keys]]
        for row in rows:
            cells.append([_value(row.get(key)) for key in keys])
        if report.totals:
            cells.append([_value(report.totals.get(key)) for key in keys])
        sheet_rows = []
        for row in cells:
            values = []
            for value in row:
                values.append(
                    f'<c t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
            sheet_rows.append(f"<row>{''.join(values)}</row>")
        sheet = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
        )
        files = {
            "[Content_Types].xml": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>"
            ),
            "_rels/.rels": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
            "xl/workbook.xml": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>'
            ),
            "xl/_rels/workbook.xml.rels": (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
            "xl/worksheets/sheet1.xml": sheet,
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as workbook:
            for name, content in files.items():
                workbook.writestr(name, content)
        return stream.getvalue()


class PdfExporter:
    """Deferred renderer seam; no unnecessary PDF dependency is installed."""

    media_type = "application/pdf"
    extension = "pdf"

    def render(self, report: ReportPage) -> bytes:
        raise HTTPException(
            status_code=501,
            detail="PDF export is not configured. Register a PDF renderer for this deployment.",
        )


EXPORTERS = {"csv": CsvExporter(), "xlsx": SpreadsheetMlExporter(), "pdf": PdfExporter()}


def register_exporter(format_name: str, exporter: Any) -> None:
    """Install an optional renderer (for example a deployment PDF adapter)."""
    EXPORTERS[format_name.lower()] = exporter
