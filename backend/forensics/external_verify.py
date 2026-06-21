"""
External Verification Stubs
Provides structured interfaces for:
- NSDL ITR verification (PAN validation)
- MCA21 company registry lookup
- DigiLocker document pull

Each function returns a consistent schema and clearly marks whether
the result is from the real API or a mock. Set REAL_API_MODE=true in
environment to enable real HTTP calls once you have API credentials.
"""
import os
import re
import hashlib

REAL_API_MODE = os.environ.get("REAL_API_MODE", "false").lower() == "true"

# ──────────────────────────────────────────────────────────────────────────────
# Known company registry (expanded mock dataset for realistic demos)
# ──────────────────────────────────────────────────────────────────────────────
_MOCK_COMPANIES = {
    "apex tech solutions": {
        "cin": "U72200KA2015PTC082341",
        "status": "Active",
        "category": "Private Limited",
        "incorporation_date": "2015-04-12",
        "registered_office": "44, Electronic City, Bangalore - 560100",
        "authorized_capital": "50,00,000",
    },
    "infosys": {
        "cin": "L85110KA1981PLC013115",
        "status": "Active",
        "category": "Public Limited",
        "incorporation_date": "1981-07-02",
        "registered_office": "Electronics City, Hosur Road, Bengaluru - 560100",
        "authorized_capital": "100,00,00,000",
    },
    "tata consultancy services": {
        "cin": "L22210MH1995PLC084781",
        "status": "Active",
        "category": "Public Limited",
        "incorporation_date": "1995-01-19",
        "registered_office": "TCS House, Raveline Street, Fort, Mumbai - 400001",
        "authorized_capital": "375,00,00,000",
    },
    "wipro": {
        "cin": "L32102KA1945PLC020800",
        "status": "Active",
        "category": "Public Limited",
        "incorporation_date": "1945-12-29",
        "registered_office": "Doddakannelli, Sarjapur Road, Bengaluru - 560035",
        "authorized_capital": "600,00,00,000",
    },
    "hdfc bank": {
        "cin": "L65920MH1994PLC080618",
        "status": "Active",
        "category": "Public Limited",
        "incorporation_date": "1994-08-30",
        "registered_office": "HDFC Bank House, Senapati Bapat Marg, Lower Parel, Mumbai",
        "authorized_capital": "550,00,00,000",
    },
}

# Mock valid PAN pool (for demo purposes — first 5 chars are initials + category)
_MOCK_VALID_PANS = {
    "BPHPS2930K": {"name": "Karan Singh", "status": "Active", "category": "Individual"},
    "ACLRK9821M": {"name": "Rajesh Kumar", "status": "Active", "category": "Individual"},
    "FKPPA4521J": {"name": "Priya Sharma", "status": "Active", "category": "Individual"},
    "ALWPA3020H": {"name": "Amit Patel", "status": "Active", "category": "Individual"},
    "AAACX2831K": {"name": "Apex Tech Solutions Pvt Ltd", "status": "Active", "category": "Company"},
}


def verify_pan(pan: str) -> dict:
    """
    Verify PAN via NSDL ITR verification API.
    
    Real API: https://www.nsdl.com/services/pan-verification (requires API key)
    Mock mode: returns from _MOCK_VALID_PANS dict or flags as unknown.
    
    Returns:
        {
            "source": "NSDL" | "MOCK",
            "pan": str,
            "valid": bool,
            "name": str,
            "status": str,
            "category": str,
            "confidence": float,
            "mock": bool,
            "note": str
        }
    """
    if not pan or len(pan) != 10:
        return _pan_error(pan, "Invalid PAN format (must be 10 characters)")

    pan = pan.upper().strip()
    pan_regex = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')
    if not pan_regex.match(pan):
        return _pan_error(pan, f"PAN '{pan}' does not match standard ABCDE1234F format")

    if REAL_API_MODE:
        return _real_nsdl_verify(pan)

    # ── Mock mode ─────────────────────────────────────────────────────────────
    if pan in _MOCK_VALID_PANS:
        info = _MOCK_VALID_PANS[pan]
        return {
            "source": "MOCK",
            "pan": pan,
            "valid": True,
            "name": info["name"],
            "status": info["status"],
            "category": info["category"],
            "confidence": 0.95,
            "mock": True,
            "note": "Mock response — configure REAL_API_MODE=true with NSDL API credentials for live verification"
        }
    else:
        # Unknown PAN: flag as unverifiable (not necessarily invalid)
        return {
            "source": "MOCK",
            "pan": pan,
            "valid": None,  # None = "could not verify"
            "name": "Unknown",
            "status": "Unverified",
            "category": "Unknown",
            "confidence": 0.0,
            "mock": True,
            "note": "PAN not found in mock registry. Real NSDL API required for authoritative verification."
        }


def verify_company_mca(company_name: str) -> dict:
    """
    Verify company registration via MCA21 portal.
    
    Real API: https://www.mca.gov.in/content/mca/global/en/data-and-reports/mca-services/mca21.html
    Mock mode: fuzzy-matches against _MOCK_COMPANIES dict.
    
    Returns:
        {
            "source": "MCA21" | "MOCK",
            "company_name": str,
            "registered": bool,
            "cin": str,
            "status": str,
            "confidence": float,
            "mock": bool,
            "details": dict
        }
    """
    if not company_name:
        return {"source": "MOCK", "company_name": "", "registered": False, "mock": True}

    if REAL_API_MODE:
        return _real_mca21_lookup(company_name)

    # Fuzzy match against mock registry
    normalized = company_name.lower().strip()
    normalized = re.sub(r'\b(pvt|ltd|limited|private|public|llp|inc|corp)\b', '', normalized).strip()

    best_match = None
    best_score = 0
    for key, info in _MOCK_COMPANIES.items():
        key_clean = re.sub(r'\b(pvt|ltd|limited|private|public)\b', '', key).strip()
        # Simple overlap scoring
        score = _string_overlap(normalized, key_clean)
        if score > best_score:
            best_score = score
            best_match = (key, info)

    if best_match and best_score > 0.55:
        key, info = best_match
        return {
            "source": "MOCK",
            "company_name": company_name,
            "matched_name": key.title(),
            "registered": info["status"] == "Active",
            "cin": info["cin"],
            "status": info["status"],
            "category": info["category"],
            "incorporation_date": info["incorporation_date"],
            "registered_office": info["registered_office"],
            "confidence": round(best_score, 2),
            "mock": True,
            "note": "Mock MCA21 response — configure REAL_API_MODE=true for live verification"
        }
    else:
        return {
            "source": "MOCK",
            "company_name": company_name,
            "registered": False,
            "cin": None,
            "status": "NOT FOUND",
            "confidence": 0.0,
            "mock": True,
            "note": f"Company '{company_name}' not found in mock MCA21 registry. "
                    f"High fraud risk: employer may be fictitious. Verify manually at mca.gov.in."
        }


def verify_digilocker_doc(doc_id: str, doc_type: str = "unknown") -> dict:
    """
    Pull authentic document from DigiLocker API (Indian Government).
    
    Real API: https://developers.digitallocker.gov.in/
    Requires: DigiLocker OAuth2 credentials (client_id, client_secret, user_token)
    
    Returns:
        {
            "source": "DigiLocker" | "MOCK",
            "doc_id": str,
            "authentic": bool,
            "issuer": str,
            "issued_date": str,
            "doc_type": str,
            "confidence": float,
            "mock": bool
        }
    """
    if REAL_API_MODE:
        return _real_digilocker_pull(doc_id, doc_type)

    # Mock: simulate authentic DigiLocker document
    mock_issuers = {
        "aadhaar": "UIDAI (Unique Identification Authority of India)",
        "pan": "Income Tax Department, Government of India",
        "driving_licence": "Ministry of Road Transport and Highways",
        "degree": "University Grants Commission",
        "bank_statement": "Reserve Bank of India Licensed Entity",
        "itr": "Central Board of Direct Taxes",
        "unknown": "Government of India",
    }

    return {
        "source": "MOCK",
        "doc_id": doc_id,
        "authentic": True,
        "issuer": mock_issuers.get(doc_type.lower(), mock_issuers["unknown"]),
        "issued_date": "2024-03-15",
        "doc_type": doc_type,
        "digitally_signed": True,
        "signature_valid": True,
        "confidence": 0.85,
        "mock": True,
        "note": (
            "Mock DigiLocker response. Real integration requires DigiLocker OAuth2 "
            "app registration at digitallocker.gov.in and user consent flow."
        )
    }


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _pan_error(pan, note):
    return {
        "source": "VALIDATION",
        "pan": pan,
        "valid": False,
        "name": "Unknown",
        "status": "Invalid Format",
        "category": "Unknown",
        "confidence": 0.0,
        "mock": True,
        "note": note
    }


def _string_overlap(a: str, b: str) -> float:
    """Simple word-overlap Jaccard similarity."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _real_nsdl_verify(pan: str) -> dict:
    """
    Real NSDL API call. Requires env vars:
    - NSDL_API_KEY
    - NSDL_CLIENT_ID
    """
    try:
        import httpx
        api_key = os.environ.get("NSDL_API_KEY", "")
        client_id = os.environ.get("NSDL_CLIENT_ID", "")
        if not api_key:
            raise ValueError("NSDL_API_KEY not configured")

        # NSDL PAN verification endpoint (illustrative — actual endpoint requires agreement with NSDL)
        url = "https://apiportal.nsdl.com/pan-verification/v1/verify"
        headers = {"Authorization": f"Bearer {api_key}", "client_id": client_id}
        payload = {"pan": pan}

        response = httpx.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()

        return {
            "source": "NSDL",
            "pan": pan,
            "valid": data.get("status") == "E",  # E = Valid
            "name": data.get("name", "Unknown"),
            "status": data.get("panStatus", "Unknown"),
            "category": data.get("lastName", "Unknown"),
            "confidence": 1.0,
            "mock": False,
        }
    except Exception as e:
        return _pan_error(pan, f"NSDL API error: {e}")


def _real_mca21_lookup(company_name: str) -> dict:
    """Real MCA21 API call. Requires MCA21 API credentials."""
    try:
        import httpx
        mca_key = os.environ.get("MCA21_API_KEY", "")
        if not mca_key:
            raise ValueError("MCA21_API_KEY not configured")

        url = f"https://www.mca.gov.in/api/v1/company/search?name={company_name}"
        headers = {"Authorization": f"Bearer {mca_key}"}
        response = httpx.get(url, headers=headers, timeout=10)
        data = response.json()

        results = data.get("companyDetails", [])
        if results:
            c = results[0]
            return {
                "source": "MCA21",
                "company_name": company_name,
                "matched_name": c.get("companyName", company_name),
                "registered": c.get("companyStatus", "") == "Active",
                "cin": c.get("cin", ""),
                "status": c.get("companyStatus", "Unknown"),
                "confidence": 1.0,
                "mock": False,
            }
        return {
            "source": "MCA21",
            "company_name": company_name,
            "registered": False,
            "confidence": 1.0,
            "mock": False,
            "note": "Not found in MCA21 registry"
        }
    except Exception as e:
        return {"source": "MCA21-error", "company_name": company_name, "error": str(e), "mock": False}


def _real_digilocker_pull(doc_id: str, doc_type: str) -> dict:
    """Real DigiLocker OAuth2 API call. Requires app registration."""
    try:
        import httpx
        access_token = os.environ.get("DIGILOCKER_ACCESS_TOKEN", "")
        if not access_token:
            raise ValueError("DIGILOCKER_ACCESS_TOKEN not configured (requires user OAuth2 flow)")

        url = f"https://api.digitallocker.gov.in/public/oauth2/2/file/{doc_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = httpx.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        return {
            "source": "DigiLocker",
            "doc_id": doc_id,
            "authentic": True,
            "confidence": 1.0,
            "mock": False,
            "content_type": response.headers.get("content-type", "unknown"),
        }
    except Exception as e:
        return {
            "source": "DigiLocker-error",
            "doc_id": doc_id,
            "authentic": False,
            "error": str(e),
            "mock": False,
        }
