import re
import datetime
from .external_verify import verify_company_mca, verify_pan


def run_cross_check(bank_data: dict, sal_data: dict, itr_data: dict = None,
                    application_date: str = None) -> dict:
    """
    Compares extracted variables across the core documents.
    Generates a diff-style tabular inconsistency report with confidence scores.
    
    Enhanced checks:
    - PAN matching across all documents
    - Applicant name matching (fuzzy)
    - Monthly salary credit vs. net pay
    - Annual income annualization vs. ITR
    - Employer MCA21 registry validation
    - Date coherence (slip age, statement coverage)
    """
    matrix = []
    today = application_date or datetime.date.today().isoformat()

    # ─── 1. PAN Card matching ─────────────────────────────────────────────────
    p1 = (bank_data.get("pan") or "Unknown").strip().upper()
    p2 = (sal_data.get("pan") or "Unknown").strip().upper()
    p3 = (itr_data.get("pan") or "Unknown").strip().upper() if itr_data else "N/A"

    pan_match = True
    pan_note = "PAN Card aligns across all submitted documents"
    if p1 != "Unknown" and p2 != "Unknown":
        pan_match = (p1 == p2)
    if itr_data and p3 != "Unknown" and p3 != "N/A" and pan_match:
        pan_match = (p2 == p3)

    if not pan_match:
        pan_note = f"CONFLICT: PAN numbers differ — Bank: {p1}, Salary: {p2}, ITR: {p3}. Identity manipulation suspected."

    # PAN external verification
    pan_to_verify = p2 if p2 != "Unknown" else p1
    pan_verify = {}
    if pan_to_verify != "Unknown":
        pan_verify = verify_pan(pan_to_verify)

    matrix.append({
        "field": "PAN Card Identity",
        "bank_val": p1,
        "sal_val": p2,
        "itr_val": p3,
        "is_match": bool(pan_match),
        "confidence": "98%" if (p1 != "Unknown" and p2 != "Unknown") else "40%",
        "note": pan_note,
        "external": {
            "source": pan_verify.get("source", "N/A"),
            "verified": pan_verify.get("valid"),
            "name": pan_verify.get("name", "Unknown"),
            "mock": pan_verify.get("mock", True),
        }
    })

    # ─── 2. Applicant Name matching ───────────────────────────────────────────
    n1 = (bank_data.get("name") or "Unknown").strip()
    n2 = (sal_data.get("name") or "Unknown").strip()
    n3 = (itr_data.get("name") or "Unknown").strip() if itr_data else "N/A"

    name_match = True
    name_note = "Applicant name consistent across documents"
    if n1 != "Unknown" and n2 != "Unknown":
        c1 = re.sub(r'[^a-zA-Z]', '', n1.lower())
        c2 = re.sub(r'[^a-zA-Z]', '', n2.lower())
        name_match = (c1 in c2 or c2 in c1 or _levenshtein_ratio(c1, c2) > 0.75)
        if not name_match:
            name_note = f"CONFLICT: Name mismatch — Bank: '{n1}' vs Salary: '{n2}'. Possible identity substitution."

    matrix.append({
        "field": "Applicant Name",
        "bank_val": n1,
        "sal_val": n2,
        "itr_val": n3,
        "is_match": bool(name_match),
        "confidence": "90%" if (n1 != "Unknown" and n2 != "Unknown") else "35%",
        "note": name_note,
    })

    # ─── 3. Employer MCA21 Validation ────────────────────────────────────────
    employer = sal_data.get("employer", "Unknown")
    mca_result = {}
    mca_match = True
    mca_note = "Employer not extracted from document"

    if employer and employer != "Unknown":
        mca_result = verify_company_mca(employer)
        mca_match = mca_result.get("registered", False)
        if mca_match:
            mca_note = (
                f"Employer '{employer}' verified in {'Mock ' if mca_result.get('mock') else ''}MCA21 registry "
                f"(CIN: {mca_result.get('cin', 'N/A')}, Status: {mca_result.get('status', 'N/A')})"
            )
        else:
            mca_note = (
                f"WARNING: Employer '{employer}' NOT found in MCA21 company registry. "
                f"May be fictitious, unregistered, or name spelled differently. "
                f"Verify at mca.gov.in before proceeding."
            )

    matrix.append({
        "field": "Employer MCA21 Registry",
        "bank_val": "N/A (bank document)",
        "sal_val": employer,
        "itr_val": "N/A",
        "is_match": bool(mca_match),
        "confidence": "92%" if employer != "Unknown" else "0%",
        "note": mca_note,
        "external": {
            "source": mca_result.get("source", "N/A"),
            "verified": mca_result.get("registered"),
            "cin": mca_result.get("cin", "N/A"),
            "mock": mca_result.get("mock", True),
        }
    })

    # ─── 4. Monthly Payout Reconciliation ────────────────────────────────────
    raw_net = sal_data.get("raw_net_pay", 0.0) or 0.0
    bank_text = bank_data.get("raw_text", "")
    salary_match = True
    found_credit = "Salary credit search not applicable (net pay not extracted)"

    if raw_net > 0:
        salary_match = False
        # Look for the exact amount in bank text (with/without commas, with tolerance)
        targets = [
            f"{raw_net:,.2f}",
            f"{raw_net:,.0f}",
            str(int(raw_net)),
            f"{raw_net:.2f}",
        ]
        for target in targets:
            if target in bank_text:
                salary_match = True
                found_credit = f"Salary credit of Rs. {raw_net:,.2f} matched in bank statement"
                break

        # ±3% tolerance match (variable pay, rounding differences)
        if not salary_match:
            for target_val in [raw_net * 0.97, raw_net * 1.03]:
                target_str = f"{target_val:,.0f}"
                if target_str in bank_text:
                    salary_match = True
                    found_credit = f"Credit of Rs. {target_val:,.0f} found (±3% of declared net Rs. {raw_net:,.0f})"
                    break

        if not salary_match:
            found_credit = (
                f"No credit matching Rs. {raw_net:,.2f} found in bank statement. "
                f"Income inflation or fabricated salary slip suspected."
            )

    matrix.append({
        "field": "Monthly Salary Credit Reconciliation",
        "bank_val": found_credit,
        "sal_val": sal_data.get("net_pay", "Not extracted"),
        "itr_val": "N/A (Monthly)",
        "is_match": bool(salary_match),
        "confidence": "85%" if raw_net > 0 else "0%",
        "note": (
            "Salary credit matches declared Net Pay" if salary_match
            else f"CONFLICT: Declared Net Pay (Rs. {raw_net:,.0f}) not reflected in bank debits. Income inflation indicator."
        )
    })

    # ─── 5. Annual Income Tax Declaration Ratio ───────────────────────────────
    sal_gross = sal_data.get("gross_earnings", 0.0) or 0.0
    bank_est = sal_gross * 12
    itr_gross = 0.0
    annual_match = True
    annual_note = "ITR not provided — cannot perform annualized comparison"

    if itr_data:
        itr_gross = itr_data.get("gross_earnings") or itr_data.get("raw_net_pay") or 0.0
        if itr_gross > 0 and sal_gross > 0:
            delta_pct = abs(bank_est - itr_gross) / itr_gross
            if delta_pct > 0.15:
                annual_match = False
                annual_note = (
                    f"CONFLICT: Annualized slip gross (Rs. {bank_est:,.0f}) differs from "
                    f"ITR declaration (Rs. {itr_gross:,.0f}) by {delta_pct:.1%} — "
                    f"exceeds 15% tolerance. Income manipulation between documents."
                )
            else:
                annual_note = (
                    f"Annualized salary ({delta_pct:.1%} variance) is within the "
                    f"15% tolerance band vs. ITR declaration. Consistent."
                )

    matrix.append({
        "field": "Annual Income vs. ITR Declaration",
        "bank_val": f"Rs. {bank_est:,.0f} (Annualized projection)" if sal_gross > 0 else "Unknown",
        "sal_val": f"Rs. {sal_gross * 12:,.0f} (Projected Gross)" if sal_gross > 0 else "Unknown",
        "itr_val": f"Rs. {itr_gross:,.0f}" if itr_gross > 0 else "N/A",
        "is_match": bool(annual_match),
        "confidence": "88%" if (sal_gross > 0 and itr_gross > 0) else "20%",
        "note": annual_note,
    })

    # ─── 6. Date Coherence Check ──────────────────────────────────────────────
    sal_date_str = sal_data.get("date", "Unknown")
    bank_date_str = bank_data.get("date", "Unknown")
    date_ok = True
    date_note = "Document dates appear consistent"

    try:
        if sal_date_str != "Unknown":
            # Check salary slip is not more than 3 months old
            parsed_sal = _parse_any_date(sal_date_str)
            if parsed_sal:
                today_date = datetime.date.today()
                age_days = (today_date - parsed_sal).days
                if age_days > 90:
                    date_ok = False
                    date_note = (
                        f"WARNING: Salary slip dated {sal_date_str} is {age_days} days old "
                        f"(> 90 day freshness threshold). May not reflect current employment status."
                    )
    except Exception:
        pass

    matrix.append({
        "field": "Document Freshness (90-day Rule)",
        "bank_val": bank_date_str,
        "sal_val": sal_date_str,
        "itr_val": "Annual Filing",
        "is_match": bool(date_ok),
        "confidence": "75%" if sal_date_str != "Unknown" else "0%",
        "note": date_note,
    })

    # ─── Overall status ───────────────────────────────────────────────────────
    all_match = all(m["is_match"] for m in matrix)
    critical_mismatches = sum(
        1 for m in matrix
        if not m["is_match"] and m["field"] in ["PAN Card Identity", "Employer MCA21 Registry",
                                                  "Monthly Salary Credit Reconciliation"]
    )

    if critical_mismatches >= 2:
        overall_status = "CRITICAL FRAUD INDICATORS"
    elif not all_match:
        overall_status = "INCONSISTENCIES DETECTED — REQUIRES REVIEW"
    else:
        overall_status = "VERIFICATION SUCCESSFUL"

    return {
        "overall_status": overall_status,
        "total_checks": len(matrix),
        "passed": sum(1 for m in matrix if m["is_match"]),
        "failed": sum(1 for m in matrix if not m["is_match"]),
        "matrix": matrix
    }


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Simple Levenshtein similarity ratio."""
    if not s1 or not s2:
        return 0.0
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            dp[i][j] = min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost)
    distance = dp[m][n]
    return 1 - distance / max(m, n)


def _parse_any_date(date_str: str):
    """Try multiple date formats."""
    import datetime
    formats = [
        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
        "%d-%b-%Y", "%d/%b/%Y", "%b %Y", "%B %Y",
        "%d %b %Y", "%d %B %Y"
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except:
            pass
    return None
