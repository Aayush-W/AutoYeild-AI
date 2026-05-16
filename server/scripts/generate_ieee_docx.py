from __future__ import annotations

import copy
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("w", W_NS)


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DOCX = PROJECT_ROOT / "APGS_PAPER_IEEE[1].docx"
SOURCE_MD = PROJECT_ROOT / "reports" / "AutoYield_AI_IEEE_System_Paper.md"
OUTPUT_DOCX = PROJECT_ROOT / "reports" / "AutoYield_AI_IEEE_System_Paper.docx"


def clean_inline(text: str) -> str:
    text = text.strip()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = text.replace("**", "")
    text = text.replace("*", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_markdown(md_path: Path) -> dict:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Empty source file: {md_path}")

    title = ""
    authors: list[str] = []
    abstract = ""
    keywords = ""
    body_blocks: list[tuple[str, object]] = []

    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or not lines[i].startswith("# "):
        raise ValueError("Expected first non-empty line to be a Markdown title.")
    title = clean_inline(lines[i][2:])
    i += 1

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("**Abstract**"):
            break
        authors.append(clean_inline(line))
        i += 1

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        abstract_match = re.match(r"^\*\*Abstract\*\*\s*-\s*(.+)$", line)
        if abstract_match:
            abstract = clean_inline(abstract_match.group(1))
            i += 1
            continue

        keywords_match = re.match(r"^\*\*Keywords\*\*\s*-\s*(.+)$", line)
        if keywords_match:
            keywords = clean_inline(keywords_match.group(1))
            i += 1
            continue

        if line.startswith("## "):
            body_blocks.append(("h1", clean_inline(line[3:])))
            i += 1
            continue

        if line.startswith("### "):
            body_blocks.append(("h2", clean_inline(line[4:])))
            i += 1
            continue

        if line.startswith("**Table "):
            body_blocks.append(("table_caption", clean_inline(line)))
            i += 1
            continue

        if line.startswith("**Figure "):
            body_blocks.append(("figure_caption", clean_inline(line)))
            i += 1
            continue

        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1
            body_blocks.append(("table", parse_table(table_lines)))
            continue

        if re.match(r"^\[\d+\]\s+", line):
            body_blocks.append(("reference", clean_inline(line)))
            i += 1
            continue

        para_lines = [line]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line:
                i += 1
                break
            if (
                next_line.startswith("## ")
                or next_line.startswith("### ")
                or next_line.startswith("**Table ")
                or next_line.startswith("**Figure ")
                or next_line.startswith("|")
                or re.match(r"^\[\d+\]\s+", next_line)
            ):
                break
            para_lines.append(next_line)
            i += 1
        paragraph = clean_inline(" ".join(para_lines))
        if paragraph:
            body_blocks.append(("p", paragraph))

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "keywords": keywords,
        "blocks": body_blocks,
    }


def parse_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if idx == 1 and set(stripped.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
            continue
        cells = [clean_inline(cell) for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def make_text_run(parent: ET.Element, text: str, *, bold: bool = False) -> None:
    run = ET.SubElement(parent, w("r"))
    if bold:
        r_pr = ET.SubElement(run, w("rPr"))
        ET.SubElement(r_pr, w("b"))
    t = ET.SubElement(run, w("t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def make_paragraph(
    text: str,
    *,
    style: str | None = None,
    align: str | None = None,
    bold: bool = False,
) -> ET.Element:
    paragraph = ET.Element(w("p"))
    if style or align:
        p_pr = ET.SubElement(paragraph, w("pPr"))
        if style:
            p_style = ET.SubElement(p_pr, w("pStyle"))
            p_style.set(w("val"), style)
        if align:
            jc = ET.SubElement(p_pr, w("jc"))
            jc.set(w("val"), align)
    make_text_run(paragraph, text, bold=bold)
    return paragraph


def is_numericish(text: str) -> bool:
    normalized = text.replace("%", "").replace(",", "").replace("`", "").strip()
    if not normalized:
        return False
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", normalized):
        return True
    if re.fullmatch(r"[-+]?\d+:\d+", normalized):
        return True
    return False


def compute_table_widths(rows: list[list[str]], total_width: int = 9300) -> list[int]:
    col_count = max(len(row) for row in rows)
    weights = [8] * col_count
    for row in rows:
        for idx, cell in enumerate(row):
            weights[idx] = max(weights[idx], min(len(cell), 48))
    weight_sum = sum(weights)
    widths = [max(900, int(total_width * weight / weight_sum)) for weight in weights]
    diff = total_width - sum(widths)
    widths[-1] += diff
    return widths


def make_table(rows: list[list[str]]) -> ET.Element:
    tbl = ET.Element(w("tbl"))

    tbl_pr = ET.SubElement(tbl, w("tblPr"))
    tbl_style = ET.SubElement(tbl_pr, w("tblStyle"))
    tbl_style.set(w("val"), "TableNormal")
    tbl_w = ET.SubElement(tbl_pr, w("tblW"))
    tbl_w.set(w("w"), "0")
    tbl_w.set(w("type"), "auto")
    tbl_look = ET.SubElement(tbl_pr, w("tblLook"))
    tbl_look.set(w("val"), "04A0")
    tbl_look.set(w("firstRow"), "1")
    tbl_look.set(w("lastRow"), "0")
    tbl_look.set(w("firstColumn"), "1")
    tbl_look.set(w("lastColumn"), "0")
    tbl_look.set(w("noHBand"), "0")
    tbl_look.set(w("noVBand"), "1")

    widths = compute_table_widths(rows)
    tbl_grid = ET.SubElement(tbl, w("tblGrid"))
    for width in widths:
        grid_col = ET.SubElement(tbl_grid, w("gridCol"))
        grid_col.set(w("w"), str(width))

    for row_index, row in enumerate(rows):
        tr = ET.SubElement(tbl, w("tr"))
        for col_index, cell_text in enumerate(row):
            tc = ET.SubElement(tr, w("tc"))
            tc_pr = ET.SubElement(tc, w("tcPr"))
            tc_w = ET.SubElement(tc_pr, w("tcW"))
            tc_w.set(w("w"), str(widths[col_index]))
            tc_w.set(w("type"), "dxa")

            paragraph = ET.SubElement(tc, w("p"))
            p_pr = ET.SubElement(paragraph, w("pPr"))
            p_style = ET.SubElement(p_pr, w("pStyle"))
            p_style.set(w("val"), "tablecolhead" if row_index == 0 else "tablecopy")
            jc = ET.SubElement(p_pr, w("jc"))
            if row_index == 0:
                jc.set(w("val"), "center")
            elif is_numericish(cell_text):
                jc.set(w("val"), "right")
            else:
                jc.set(w("val"), "left")

            make_text_run(paragraph, cell_text, bold=(row_index == 0))
    return tbl


def build_document_xml(template_docx: Path, parsed: dict) -> bytes:
    with zipfile.ZipFile(template_docx, "r") as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    body = root.find(w("body"))
    if body is None:
        raise ValueError("Template document is missing <w:body>.")

    sect_pr = body.find(w("sectPr"))
    sect_pr_copy = copy.deepcopy(sect_pr) if sect_pr is not None else None

    for child in list(body):
        body.remove(child)

    body.append(make_paragraph(parsed["title"], style="papertitle"))

    author_lines = parsed["authors"]
    if author_lines:
        body.append(make_paragraph(author_lines[0], style="Author"))
    for line in author_lines[1:]:
        body.append(make_paragraph(line, style="Affiliation"))

    if parsed["abstract"]:
        body.append(make_paragraph(f"Abstract— {parsed['abstract']}", style="Abstract"))
    if parsed["keywords"]:
        body.append(make_paragraph(f"Keywords— {parsed['keywords']}", style="Keywords"))

    for block_type, value in parsed["blocks"]:
        if block_type == "h1":
            body.append(make_paragraph(str(value), style="Heading1"))
        elif block_type == "h2":
            body.append(make_paragraph(str(value), style="Heading2"))
        elif block_type == "p":
            body.append(make_paragraph(str(value), style="NormalWeb"))
        elif block_type == "figure_caption":
            body.append(make_paragraph(str(value), style="figurecaption"))
        elif block_type == "table_caption":
            body.append(make_paragraph(str(value), style="tablehead"))
        elif block_type == "table":
            body.append(make_table(value))  # type: ignore[arg-type]
        elif block_type == "reference":
            body.append(make_paragraph(str(value), style="references"))

    if sect_pr_copy is not None:
        body.append(sect_pr_copy)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def generate_docx(template_docx: Path, source_md: Path, output_docx: Path) -> None:
    parsed = parse_markdown(source_md)
    document_xml = build_document_xml(template_docx, parsed)

    with zipfile.ZipFile(template_docx, "r") as src, zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "word/document.xml":
                data = document_xml
            dst.writestr(item, data)


if __name__ == "__main__":
    generate_docx(TEMPLATE_DOCX, SOURCE_MD, OUTPUT_DOCX)
    print(f"Generated {OUTPUT_DOCX}")
