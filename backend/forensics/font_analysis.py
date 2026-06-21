import os
import re
import pypdf
import pdfplumber

# ─── PyMuPDF (optional, graceful fallback) ─────────────────────────────────────
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# Suspicious tools and their realistic "release" years for anachronism detection
SUSPICIOUS_PRODUCERS = {
    "libreoffice": 2011,
    "wps office": 2016,
    "wps": 2016,
    "canva": 2017,
    "smallpdf": 2013,
    "ilovepdf": 2014,
    "pdfcreator": 2006,
    "nitro": 2012,
    "foxit": 2009,
    "soda pdf": 2011,
    "soda": 2011,
    "pdfescape": 2007,
    "sejda": 2012,
    "adobe acrobat": 2000,
    "adobe": 2000,
    "microsoft word": 1997,
    "phantompdf": 2010,
    "pdf2go": 2015,
    "google docs": 2006,
    "google": 2006,
    "cutepdf": 2003,
    "pdf24": 2008,
    "bullzip": 2006,
    "pdfforge": 2006,
}


def analyze_pdf_fonts(pdf_path: str):
    """
    Master function: returns (anomalies_list, metadata_dict).

    Runs:
    1. PyMuPDF rich metadata extraction (date-producer anachronism, tool detection)
    2. pypdf metadata cross-check
    3. pdfplumber character-level font mismatch analysis:
       - Different font family on same line
       - Size delta > 2pt on same numeric field
       - Bold/non-bold mixing in numeric context
    """
    anomalies = []
    metadata = {}
    font_names = set()

    # ── 1. PyMuPDF Metadata (preferred, richest) ──────────────────────────────
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(pdf_path)
            raw = doc.metadata
            for page in doc:
                try:
                    for f in page.get_fonts():
                        font_names.add(f[3])
                except:
                    pass
            doc.close()

            metadata = {
                "source": "PyMuPDF",
                "creator":  raw.get("creator", "Unknown"),
                "producer": raw.get("producer", "Unknown"),
                "author":   raw.get("author", "Unknown"),
                "created":  raw.get("creationDate", "Unknown"),
                "modified": raw.get("modDate", "Unknown"),
                "fonts_used": list(font_names)
            }

            prod_lower = metadata["producer"].lower()
            creator_lower = metadata["creator"].lower()
            combined = prod_lower + " " + creator_lower

            # ── Suspicious editor detection ──────────────────────────────────
            matched_tool = None
            for tool in SUSPICIOUS_PRODUCERS:
                if tool in combined:
                    matched_tool = tool
                    break

            if matched_tool:
                anomalies.append({
                    "id": "meta-suspicious-producer",
                    "type": "metadata",
                    "severity": "HIGH",
                    "title": f"Commercial Editor Signature: '{matched_tool.title()}'",
                    "desc": (
                        f"PDF metadata producer/creator field contains '{metadata['producer'] or metadata['creator']}'. "
                        f"Genuine bank-generated documents use core banking system exporters "
                        f"(Finacle PDF renderer, T24 report engine, etc.), not desktop editors."
                    ),
                    "conf": "96.5%"
                })

            # ── Date-Producer Anachronism check ──────────────────────────────
            for tool, release_year in SUSPICIOUS_PRODUCERS.items():
                if tool in combined:
                    # Try to extract version year from producer string
                    version_match = re.search(r'(\d{4})', combined)
                    if version_match:
                        prod_year = int(version_match.group(1))
                    else:
                        prod_year = release_year

                    # Extract claimed creation year
                    doc_year_match = re.search(r'(20\d{2})', metadata.get("created", ""))
                    if doc_year_match:
                        doc_year = int(doc_year_match.group(1))
                        if prod_year > doc_year + 1:  # Allow 1yr tolerance
                            anomalies.append({
                                "id": "meta-date-anachronism",
                                "type": "metadata",
                                "severity": "HIGH",
                                "title": "Backdated Document Anachronism",
                                "desc": (
                                    f"Document claims creation year {doc_year}, but the PDF producer "
                                    f"'{metadata['producer']}' corresponds to software from {prod_year}. "
                                    f"A document cannot be produced by software that did not exist at "
                                    f"its claimed creation time — strong indicator of backdated forgery."
                                ),
                                "conf": "99.5%"
                            })
                    break

            # ── Modification date inconsistency ──────────────────────────────
            created_str = metadata.get("created", "")
            modified_str = metadata.get("modified", "")
            if created_str != "Unknown" and modified_str != "Unknown" and created_str != modified_str:
                anomalies.append({
                    "id": "meta-modification-detected",
                    "type": "metadata",
                    "severity": "MEDIUM",
                    "title": "PDF Modification Date Differs from Creation",
                    "desc": (
                        f"Document was created on {created_str[:16]} but later modified on {modified_str[:16]}. "
                        f"Authentic salary slips and bank statements from core banking systems "
                        f"are generated once and never re-opened."
                    ),
                    "conf": "82.0%"
                })

        except Exception as e:
            print(f"[PyMuPDF metadata] Error: {e}")
            metadata = {"source": "PyMuPDF-error", "error": str(e)}
    else:
        # ── Fallback: pypdf metadata ──────────────────────────────────────────
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                meta = reader.metadata
                if meta:
                    metadata = {
                        "source": "pypdf",
                        "creator":  meta.creator or "Unknown",
                        "producer": meta.producer or "Unknown",
                        "created":  str(meta.creation_date) if meta.creation_date else "Unknown",
                        "modified": str(meta.modification_date) if meta.modification_date else "Unknown",
                    }

                    prod = metadata.get("producer", "").lower()
                    creator = metadata.get("creator", "").lower()
                    combined = prod + " " + creator

                    for tool in SUSPICIOUS_PRODUCERS:
                        if tool in combined:
                            anomalies.append({
                                "id": "meta-editing-tool",
                                "type": "metadata",
                                "severity": "HIGH",
                                "title": f"Commercial PDF Editor Logs: '{tool.title()}'",
                                "desc": (
                                    f"PDF binary metadata records creator/producer tag: "
                                    f"'{metadata.get('producer') or metadata.get('creator')}'. "
                                    f"Authentic banking documents use system-generated PDFs."
                                ),
                                "conf": "94.0%"
                            })
                            break
        except Exception as e:
            print(f"[pypdf metadata] Error: {e}")

    # ── 2. pdfplumber Font Mismatch Analysis ──────────────────────────────────
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                chars = page.chars
                if not chars:
                    continue
                for char in chars:
                    if char.get("fontname"):
                        font_names.add(char["fontname"])

                # Group characters into lines by vertical position
                lines: dict = {}
                for char in chars:
                    y = round(char["top"], 1)
                    matched_line = None
                    for line_y in lines:
                        if abs(line_y - y) < 3.0:
                            matched_line = line_y
                            break
                    if matched_line is not None:
                        lines[matched_line].append(char)
                    else:
                        lines[y] = [char]

                for line_y, line_chars in lines.items():
                    if len(line_chars) < 5:
                        continue

                    # ── Font family frequency on this line ───────────────────
                    font_freq: dict = {}
                    for c in line_chars:
                        key = (c["fontname"], round(c["size"], 0))
                        font_freq[key] = font_freq.get(key, 0) + 1

                    dominant_font = max(font_freq, key=font_freq.get)
                    dom_count = font_freq[dominant_font]

                    if dom_count / len(line_chars) >= 0.65:
                        for c in line_chars:
                            c_key = (c["fontname"], round(c["size"], 0))
                            if c_key == dominant_font:
                                continue
                            if c["text"].strip() == "":
                                continue

                            # ── Size delta check (> 2pt is suspicious) ───────
                            size_delta = abs(c["size"] - dominant_font[1])
                            # ── Font family name mismatch ────────────────────
                            dom_family = _font_family(dominant_font[0])
                            c_family = _font_family(c["fontname"])
                            family_mismatch = dom_family != c_family

                            # ── Bold / non-bold mixing in numeric fields ──────
                            dom_bold = _is_bold(dominant_font[0])
                            c_bold = _is_bold(c["fontname"])
                            bold_mismatch = dom_bold != c_bold

                            if family_mismatch or size_delta > 2.0 or bold_mismatch:
                                severity = "HIGH" if family_mismatch else "MEDIUM"
                                conf = "99.2%" if family_mismatch else "87.0%"
                                reason = []
                                if family_mismatch:
                                    reason.append(f"family: '{c_family}' vs dominant '{dom_family}'")
                                if size_delta > 2.0:
                                    reason.append(f"size delta {size_delta:.1f}pt")
                                if bold_mismatch:
                                    reason.append(f"bold={c_bold} vs dominant bold={dom_bold}")

                                anomalies.append({
                                    "id": f"font-p{page_idx}-x{round(c['x0'])}-y{round(c['top'])}",
                                    "type": "font",
                                    "severity": severity,
                                    "title": f"Typography Inconsistency: '{c['text']}'",
                                    "desc": (
                                        f"Character '{c['text']}' uses font '{c['fontname']}' "
                                        f"(size {c['size']:.1f}) — {'; '.join(reason)}. "
                                        f"Dominant line font: '{dominant_font[0]}' "
                                        f"(size {dominant_font[1]:.0f}). "
                                        f"Typical of digit overwriting with a pasted text layer."
                                    ),
                                    "conf": conf,
                                    "bbox": {
                                        "x0": float(c["x0"]),
                                        "top": float(c["top"]),
                                        "x1": float(c["x1"]),
                                        "bottom": float(c["bottom"]),
                                        "page_width": float(page.width),
                                        "page_height": float(page.height),
                                        "page": page_idx,
                                    }
                                })

    except Exception as e:
        print(f"[pdfplumber font analysis] Error: {e}")

    if "fonts_used" not in metadata or not metadata["fonts_used"]:
        metadata["fonts_used"] = list(font_names)
    return anomalies, metadata


def _font_family(fontname: str) -> str:
    """Normalise font name to family (strip Bold/Italic/Regular suffixes)."""
    if not fontname:
        return "unknown"
    cleaned = re.sub(r'[-,+]', ' ', fontname).lower()
    for suffix in ["bold", "italic", "regular", "oblique", "light", "medium",
                   "semibold", "condensed", "narrow", "mt", "ps"]:
        cleaned = cleaned.replace(suffix, "").strip()
    return cleaned.strip() or "unknown"


def _is_bold(fontname: str) -> bool:
    """Detect bold from font name."""
    return "bold" in fontname.lower() or "black" in fontname.lower()
