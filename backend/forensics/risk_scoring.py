def calculate_weighted_risk(
    font_anomalies: list,
    math_inconsistent: bool,
    metadata_anomalies: list,
    pixel_anomalies: list,
    hash_anomalies: list = None,
    liveness_anomalies: list = None,
    signature_anomalies: list = None,
    temporal_anomalies: list = None,
    library_anomalies: list = None
):
    """
    Computes a weighted risk score (0 to 100) based on detected anomalies.
    Also returns a confidence score representing detector alignment.
    """
    score = 0
    weights = {
        "font_mismatch": 45,       # High indicator of numeric alterations
        "math_mismatch": 40,       # High indicator of ledger fabrication
        "metadata_editor": 15,     # Medium indicator of re-saving files
        "copy_move_cloned": 35,    # High indicator of signature/seal copy-paste
        "edge_irregularity": 20,   # Medium indicator of graphic overlays
        "duplicate_document": 55,  # CRITICAL: Document cloned across cases
        "face_spoofing": 50,       # CRITICAL: Fake ID photo (screen recapture)
        "signature_mismatch": 40,  # High: Signatures differ across docs
        "temporal_anomaly": 35,    # High: Chronological order impossibility
        "known_fraud_match": 80,   # CRITICAL: Document features match fraud pattern library
    }
    
    reasons = []
    
    # 1. Font anomalies check
    has_font = len([a for a in font_anomalies if a.get("type") == "font"]) > 0
    if has_font:
        score += weights["font_mismatch"]
        reasons.append("Typography font style discrepancies (numeric substitution signature)")
        
    # 2. Math checks
    if math_inconsistent:
        score += weights["math_mismatch"]
        reasons.append("Arithmetic balance mismatch (Gross - Deductions != Net)")
        
    # 3. Metadata check
    has_meta = len([a for a in metadata_anomalies if a.get("type") == "metadata"]) > 0
    if has_meta:
        score += weights["metadata_editor"]
        reasons.append("PDF binary contains commercial editor trace metadata")
        
    # 4. Pixel anomalies check
    has_clone = any(a.get("id") == "copy-move-cloned" for a in pixel_anomalies)
    has_edge = any(a.get("id") == "edge-irregularity" for a in pixel_anomalies)
    
    if has_clone:
        score += weights["copy_move_cloned"]
        reasons.append("OpenCV copy-move ORB descriptor matches (region cloning detected)")
    if has_edge:
        score += weights["edge_irregularity"]
        reasons.append("Canny edge density irregularity (digital graphic boundary overlay)")
        
    # 5. Hash anomalies check (Duplicate Clones)
    if hash_anomalies and len(hash_anomalies) > 0:
        score += weights["duplicate_document"]
        reasons.append("Perceptual image hashing duplicate clone matches across application cases")
        
    # 6. Face Liveness check
    has_spoof = liveness_anomalies and any(a.get("severity") in ("HIGH", "CRITICAL") for a in liveness_anomalies)
    if has_spoof:
        score += weights["face_spoofing"]
        reasons.append("Face liveness analysis failed (texture blur / FFT screen grid frequency moire)")
        
    # 7. Signature cross-document check
    has_sig_mismatch = signature_anomalies and any(a.get("severity") == "HIGH" for a in signature_anomalies)
    if has_sig_mismatch:
        score += weights["signature_mismatch"]
        reasons.append("Cross-document signature verification mismatch or spliced clone detected")
        
    # 8. Temporal chronological check
    has_temp_anomaly = temporal_anomalies and len(temporal_anomalies) > 0
    if has_temp_anomaly:
        score += weights["temporal_anomaly"]
        reasons.append("Temporal chronological sequence impossibility (employment pre-incorporation or future dates)")
        
    # 9. Fraud Pattern Library check
    has_lib_match = library_anomalies and len(library_anomalies) > 0
    if has_lib_match:
        score += weights["known_fraud_match"]
        reasons.append("Extracted entities or hashes matched known blocklisted entries in fraud library")
        
    # Cap final risk score at 99
    final_score = min(99, max(5, score))
    
    if final_score > 75:
        level = "HIGH"
    elif final_score > 30:
        level = "MEDIUM"
    else:
        level = "LOW"
        
    # Calculate detector confidence (based on multiple overlapping signals)
    confidence = 75.0
    signals = [
        has_font, 
        math_inconsistent, 
        has_meta, 
        has_clone or has_edge,
        bool(hash_anomalies),
        has_spoof,
        has_sig_mismatch,
        has_temp_anomaly,
        has_lib_match
    ]
    active_signals = sum(1 for s in signals if s)
    if active_signals >= 3:
        confidence = 98.5
    elif active_signals == 2:
        confidence = 88.0
    elif active_signals == 1:
        confidence = 80.0
        
    return {
        "risk_score": final_score,
        "risk_level": level,
        "confidence": f"{confidence}%",
        "reasons": reasons
    }
