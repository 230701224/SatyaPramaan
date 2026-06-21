import re
import os

# ─── AWS Textract (optional, graceful fallback to regex) ───────────────────────
try:
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

# ─── PyMuPDF (optional, graceful fallback) ─────────────────────────────────────
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def extract_pdf_metadata_pymupdf(pdf_path: str) -> dict:
    """
    Uses PyMuPDF to extract rich PDF metadata including creation/modification
    dates and producer software. Flags anachronisms (doc date < producer release year).
    """
    if not PYMUPDF_AVAILABLE:
        return {"source": "unavailable", "note": "PyMuPDF not installed"}

    meta = {}
    anomalies = []
    try:
        doc = fitz.open(pdf_path)
        raw_meta = doc.metadata
        doc.close()

        meta = {
            "source": "PyMuPDF",
            "creator":   raw_meta.get("creator", "Unknown"),
            "producer":  raw_meta.get("producer", "Unknown"),
            "author":    raw_meta.get("author", "Unknown"),
            "created":   raw_meta.get("creationDate", "Unknown"),
            "modified":  raw_meta.get("modDate", "Unknown"),
            "subject":   raw_meta.get("subject", ""),
            "trapped":   raw_meta.get("trapped", ""),
        }

        # ── Anachronism check: doc claim year vs producer release year ──────
        producer_lower = meta["producer"].lower()
        creator_lower = meta["creator"].lower()

        # Suspicious editing tools with known release thresholds
        suspicious_tools = {
            "libreoffice": 2011,
            "wps office": 2016,
            "canva": 2017,
            "smallpdf": 2013,
            "ilovepdf": 2014,
            "pdfcreator": 2006,
            "nitro": 2012,
            "foxit": 2009,
            "soda pdf": 2011,
            "pdfescape": 2007,
            "sejda": 2012,
            "adobe acrobat": 2000,
            "microsoft word": 1997,
            "phantompdf": 2010,
            "pdf2go": 2015,
            "google docs": 2006,
        }

        for tool, _ in suspicious_tools.items():
            if tool in producer_lower or tool in creator_lower:
                anomalies.append({
                    "id": "meta-suspicious-producer",
                    "type": "metadata",
                    "severity": "HIGH",
                    "title": f"Suspicious PDF Editor Detected: '{tool.title()}'",
                    "desc": (
                        f"PDF binary metadata records producer/creator tag matching a "
                        f"known document editing tool: '{meta['producer'] or meta['creator']}'. "
                        f"Authentic bank-generated PDFs use core banking templates "
                        f"(Finacle, Temenos, FinnOne), not desktop editors."
                    ),
                    "conf": "96.0%"
                })
                break

        # ── LibreOffice version year vs document date anachronism ───────────
        lo_match = re.search(r'libreoffice[^\d]*(\d{2,4})', producer_lower)
        if lo_match:
            lo_year = int(lo_match.group(1))
            if lo_year < 100:
                lo_year += 2000
            # Extract claimed creation year from creationDate
            year_in_doc = re.search(r'(20\d{2})', meta.get("created", ""))
            if year_in_doc:
                doc_year = int(year_in_doc.group(1))
                if lo_year > doc_year:
                    anomalies.append({
                        "id": "meta-date-anachronism",
                        "type": "metadata",
                        "severity": "HIGH",
                        "title": "Date-Producer Anachronism Detected",
                        "desc": (
                            f"Document claims creation year {doc_year} but was produced "
                            f"by LibreOffice {lo_year} — a software version that did not exist "
                            f"in {doc_year}. Strong indicator of backdated document forgery."
                        ),
                        "conf": "99.5%"
                    })

        meta["anomalies"] = anomalies

    except Exception as e:
        meta = {"source": "PyMuPDF-error", "error": str(e), "anomalies": []}

    return meta


def extract_with_textract(file_path: str) -> dict:
    """
    AWS Textract FORMS + TABLES extraction with bounding boxes per field.
    Returns structured data dict compatible with existing regex output format.
    Falls back to regex pipeline if credentials absent or Textract unavailable.
    """
    if not TEXTRACT_AVAILABLE:
        return None

    aws_key = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    aws_region = os.environ.get("AWS_DEFAULT_REGION", "ap-south-1")

    if not aws_key or not aws_secret:
        return None  # Graceful fallback signal

    try:
        client = boto3.client(
            "textract",
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )

        with open(file_path, "rb") as f:
            img_bytes = f.read()

        response = client.analyze_document(
            Document={"Bytes": img_bytes},
            FeatureTypes=["FORMS", "TABLES"]
        )

        # Build a key-value map from FORM fields
        blocks = response.get("Blocks", [])
        block_map = {b["Id"]: b for b in blocks}

        kv_pairs = {}
        bboxes = {}  # field_name -> bounding box

        for block in blocks:
            if block["BlockType"] == "KEY_VALUE_SET" and block.get("EntityTypes") == ["KEY"]:
                key_text = _get_text_from_block(block, block_map)
                value_block_id = None
                for rel in block.get("Relationships", []):
                    if rel["Type"] == "VALUE":
                        value_block_id = rel["Ids"][0]

                if value_block_id and value_block_id in block_map:
                    val_block = block_map[value_block_id]
                    value_text = _get_text_from_block(val_block, block_map)
                    kv_pairs[key_text.strip().lower()] = value_text.strip()
                    # Store bounding box of value
                    if "Geometry" in val_block:
                        bboxes[key_text.strip().lower()] = val_block["Geometry"]["BoundingBox"]

        # Map Textract KV to our standard schema
        data = _map_textract_to_schema(kv_pairs, bboxes)
        data["textract_source"] = True
        return data

    except (NoCredentialsError, ClientError, Exception) as e:
        print(f"[Textract] Fallback to regex pipeline: {e}")
        return None


def _get_text_from_block(block, block_map):
    """Recursively extract text from a Textract block via CHILD relationships."""
    text = ""
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = block_map.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    text += child.get("Text", "") + " "
    return text.strip()


def _map_textract_to_schema(kv: dict, bboxes: dict) -> dict:
    """Map Textract key-value pairs to our internal schema."""
    data = {
        "name": "Unknown",
        "pan": "Unknown",
        "aadhaar": "Unknown",
        "gstin": "Unknown",
        "net_pay": "Unknown",
        "raw_net_pay": 0.0,
        "gross_earnings": 0.0,
        "deductions": 0.0,
        "employer": "Unknown",
        "date": "Unknown",
        "bboxes": bboxes,
        "textract_source": True,
    }

    name_keys = ["employee name", "customer name", "full name", "applicant name", "name"]
    pan_keys = ["pan", "pan no", "pan number", "permanent account number"]
    net_keys = ["net pay", "net payout", "net salary", "net amount", "net transfer"]
    gross_keys = ["gross earnings", "gross pay", "gross salary", "gross amount"]
    ded_keys = ["total deductions", "deductions", "total deduction"]
    emp_keys = ["employer", "company name", "organization", "employer name"]
    date_keys = ["date", "pay date", "month", "period", "for the month"]

    for key, val in kv.items():
        for k in name_keys:
            if k in key:
                data["name"] = val
        for k in pan_keys:
            if k in key:
                data["pan"] = val
        for k in net_keys:
            if k in key:
                cleaned = re.sub(r'[^\d.]', '', val)
                try:
                    data["raw_net_pay"] = float(cleaned)
                    data["net_pay"] = f"Rs. {float(cleaned):,.2f}"
                except:
                    data["net_pay"] = val
        for k in gross_keys:
            if k in key:
                cleaned = re.sub(r'[^\d.]', '', val)
                try:
                    data["gross_earnings"] = float(cleaned)
                except:
                    pass
        for k in ded_keys:
            if k in key:
                cleaned = re.sub(r'[^\d.]', '', val)
                try:
                    data["deductions"] = float(cleaned)
                except:
                    pass
        for k in emp_keys:
            if k in key:
                data["employer"] = val
        for k in date_keys:
            if k in key and data["date"] == "Unknown":
                data["date"] = val

    return data


def extract_document_values(text: str) -> dict:
    """
    Primary extraction function. Attempts Textract first (if file_path provided),
    falls back to regex parsing on raw text.
    This overload works on pre-extracted text strings.
    """
    data = {
        "name": "Unknown",
        "pan": "Unknown",
        "aadhaar": "Unknown",
        "gstin": "Unknown",
        "net_pay": "Unknown",
        "raw_net_pay": 0.0,
        "gross_earnings": 0.0,
        "deductions": 0.0,
        "employer": "Unknown",
        "date": "Unknown",
        "bboxes": {},
        "textract_source": False,
    }

    if not text:
        return data

    clean_text = " ".join(text.split())

    # PAN Card (ABCDE1234F)
    pan_match = re.search(r'[A-Z]{5}\d{4}[A-Z]', clean_text)
    if pan_match:
        data["pan"] = pan_match.group(0)

    # Aadhaar (1234 5678 9012)
    aadhaar_match = re.search(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', clean_text)
    if aadhaar_match:
        data["aadhaar"] = aadhaar_match.group(0)

    # GSTIN
    gst_match = re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Zz]{1}[A-Z\d]{1}\b', clean_text)
    if gst_match:
        data["gstin"] = gst_match.group(0)

    # Net Pay
    net_match = re.search(
        r'(?:Net\s*(?:Payout|Pay|Value|Transfer|Salary)|Transfer\s*Value|NET\s*(?:PAY|PAYOUT))[^\d]*([\d,]+\.?\d*)',
        clean_text, re.IGNORECASE
    )
    if net_match:
        val_str = net_match.group(1).replace(",", "")
        try:
            data["net_pay"] = f"Rs. {float(val_str):,.2f}"
            data["raw_net_pay"] = float(val_str)
        except:
            data["net_pay"] = net_match.group(1)

    # Gross Earnings
    gross_match = re.search(
        r'(?:Gross\s*(?:Earnings|Pay|Salary))[^\d]*([\d,]+\.?\d*)',
        clean_text, re.IGNORECASE
    )
    if gross_match:
        try:
            data["gross_earnings"] = float(gross_match.group(1).replace(",", ""))
        except:
            pass

    # Deductions
    ded_match = re.search(
        r'(?:Total\s*Deductions?|Deductions?)[^\d]*([\d,]+\.?\d*)',
        clean_text, re.IGNORECASE
    )
    if ded_match:
        try:
            data["deductions"] = float(ded_match.group(1).replace(",", ""))
        except:
            pass

    # Name
    name_match = re.search(
        r'(?:Employee|Customer|Full|Applicant)\s*Name[^\w]*([A-Za-z\s]{3,30})',
        clean_text, re.IGNORECASE
    )
    if name_match:
        data["name"] = name_match.group(1).strip()
    else:
        deeds_name = re.search(
            r'(?:Vendor|Vendee|Buyer|Seller)[^\w]*([A-Za-z\s]{3,25})',
            clean_text, re.IGNORECASE
        )
        if deeds_name:
            data["name"] = deeds_name.group(1).strip()

    # Employer
    emp_match = re.search(
        r'(?:Employer|Company|Organization)\s*Name[^\w]*([A-Za-z0-9\s\.,]{3,40})',
        clean_text, re.IGNORECASE
    )
    if emp_match:
        data["employer"] = emp_match.group(1).strip()

    # Date
    date_match = re.search(
        r'\b(?:\d{1,2}[-\/\s]\d{1,2}[-\/\s]\d{4}|\d{1,2}[-\/\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\/\s]\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
        clean_text, re.IGNORECASE
    )
    if date_match:
        data["date"] = date_match.group(0)

    return data


def extract_document_values_from_file(file_path: str) -> dict:
    """
    Unified entry point: tries Textract first (AWS), then PyMuPDF text extraction,
    then pdfplumber regex fallback. Always returns consistent schema.
    """
    import os
    ext = os.path.splitext(file_path)[1].lower()

    # For images: Textract works directly
    if ext in [".jpg", ".jpeg", ".png"]:
        textract_result = extract_with_textract(file_path)
        if textract_result:
            return textract_result
        # No Textract: return empty (images need Textract for form extraction)
        return extract_document_values("")

    # For PDFs: try Textract, then pymupdf text, then pdfplumber
    if ext == ".pdf":
        # Option 1: Textract
        textract_result = extract_with_textract(file_path)
        if textract_result:
            return textract_result

        # Option 2: PyMuPDF text extraction
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                full_text = ""
                for page in doc:
                    full_text += page.get_text("text") + "\n"
                doc.close()
                if full_text.strip():
                    return extract_document_values(full_text)
            except Exception as e:
                print(f"[PyMuPDF text extraction] {e}")

        # Option 3: pdfplumber (always available, slowest)
        try:
            import pdfplumber
            txt = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    content = page.extract_text()
                    if content:
                        txt += content + "\n"
            return extract_document_values(txt)
        except Exception as e:
            print(f"[pdfplumber fallback] {e}")

    return extract_document_values("")
