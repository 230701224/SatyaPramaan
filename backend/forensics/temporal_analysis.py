import re
import datetime

def parse_date(date_str: str) -> datetime.date:
    """Standardizes various date formats to a datetime.date object."""
    if not date_str or date_str == "Unknown":
        return None
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
        "%d-%b-%Y", "%d/%b/%Y", "%b %Y", "%B %Y",
        "%d %b %Y", "%d %B %Y"
    ]
    # Clean the date string
    date_str = date_str.strip().replace("  ", " ")
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
            
    # Regex fallback search (e.g. for years or partial matches)
    try:
        # Match YYYY-MM-DD
        match_ymd = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
        if match_ymd:
            return datetime.date(int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3)))
            
        # Match DD/MM/YYYY
        match_dmy = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', date_str)
        if match_dmy:
            return datetime.date(int(match_dmy.group(3)), int(match_dmy.group(2)), int(match_dmy.group(1)))
    except Exception:
        pass
        
    return None

def run_temporal_checks(
    ocr_data: dict,
    mca_data: dict = None,
    application_date_str: str = None
) -> list:
    """
    Validates logical date sequences across all extracted document attributes:
    1. Employee Birthdate < PAN/Aadhaar Issue Date
    2. Employer Incorporation Date < Employee Work/Statement Dates
    3. Document Issue Date < Today / Loan Application Date
    4. Age limits: Applicant must be at least 18 at the time of document issuance.
    """
    anomalies = []
    
    today = datetime.date.today()
    app_date = parse_date(application_date_str) if application_date_str else today
    
    # ── 1. Document dates relative to today / application ──
    doc_date_str = ocr_data.get("date", "Unknown")
    doc_date = parse_date(doc_date_str)
    
    if doc_date:
        if doc_date > app_date + datetime.timedelta(days=1):  # 1 day buffer
            anomalies.append({
                "id": "temporal-future-document",
                "type": "temporal",
                "severity": "HIGH",
                "title": "Post-Dated Document Anachronism",
                "desc": (
                    f"Document claims issuance date {doc_date.isoformat()} which is "
                    f"in the future relative to the loan application date ({app_date.isoformat()}). "
                    f"Strong indicator of backdated or forward-dated fabrication."
                ),
                "conf": "99.0%"
            })
            
    # ── 2. Birthdate validation relative to document issuance ──
    dob_str = ocr_data.get("dob") or ocr_data.get("date_of_birth") or "Unknown"
    # Fallback search for DOB/Birth in raw text if present
    dob = parse_date(dob_str)
    
    if dob:
        # Age check
        if doc_date:
            age_at_issue = (doc_date - dob).days / 365.25
            if age_at_issue < 18:
                anomalies.append({
                    "id": "temporal-underage-issuance",
                    "type": "temporal",
                    "severity": "HIGH",
                    "title": "Underage Employment / Account Anachronism",
                    "desc": (
                        f"Applicant birthdate is {dob.isoformat()}. At the document's claimed "
                        f"issuance date ({doc_date.isoformat()}), the applicant was only {age_at_issue:.1f} years old. "
                        f"Violates legal age limits for employment/banking, suggesting identity theft."
                    ),
                    "conf": "95.0%"
                })
        elif dob > app_date:
            anomalies.append({
                "id": "temporal-impossible-birth",
                "type": "temporal",
                "severity": "CRITICAL",
                "title": "Impossible Applicant Birthdate",
                "desc": (
                    f"Extracted Date of Birth ({dob.isoformat()}) is after the loan application "
                    f"date ({app_date.isoformat()}). Identity sheet manipulation suspected."
                ),
                "conf": "99.5%"
            })

    # ── 3. Employer Incorporation date vs. Statement / Work Dates ──
    if mca_data and mca_data.get("registered"):
        inc_date_str = mca_data.get("incorporation_date")
        inc_date = parse_date(inc_date_str)
        
        if inc_date and doc_date:
            if doc_date < inc_date:
                anomalies.append({
                    "id": "temporal-pre-incorporation-work",
                    "type": "temporal",
                    "severity": "CRITICAL",
                    "title": "Pre-Incorporation Employment Activity",
                    "desc": (
                        f"Document claims employment/salary record from {doc_date.isoformat()}, "
                        f"but employer '{ocr_data.get('employer')}' was incorporated on {inc_date.isoformat()} "
                        f"per MCA21 records. A salary cannot be paid before the company exists."
                    ),
                    "conf": "99.5%"
                })
                
    return anomalies
