import os
import shutil
import json
import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pdfplumber

from database.database import Base, engine, get_db
from database.models import User, Case, Document, AuditLog, FraudPattern
from forensics.font_analysis import analyze_pdf_fonts
from forensics.image_forgery import run_ela, run_copy_move_detection, run_fft_analysis
from forensics.seal_detection import detect_seals_and_signatures
from forensics.ocr import extract_document_values, extract_document_values_from_file
from forensics.risk_scoring import calculate_weighted_risk
from forensics.cross_document import run_cross_check
from forensics.graph_fraud import detect_fraud_rings
from forensics.llm_insight import generate_llm_insight_sync
from forensics.external_verify import verify_pan, verify_company_mca
from forensics.image_hashing import verify_document_duplicate, calculate_dhash
from forensics.liveness import verify_face_liveness
from forensics.signature_verify import run_cross_document_signature_check
from forensics.temporal_analysis import run_temporal_checks

# ─── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("JWT_SECRET", "satya_pramaan_ai_secret_key_2026")
ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ENABLE_SEAL_DETECTION = os.environ.get("ENABLE_SEAL_DETECTION", "true").lower() != "false"

# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SatyaPramaan AI Forgery Detection API",
    description="Production-grade loan document fraud detection — Layer 1-5 pipeline",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("samples", exist_ok=True)
Base.metadata.create_all(bind=engine)


# ─── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup_populate():
    # Drop and recreate tables to ensure columns are clean
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = next(get_db())
    if db.query(User).count() == 0:
        db.add(User(username="underwriter", password_hash=pwd_context.hash("underwriter123"), role="Underwriter"))
        db.add(User(username="admin", password_hash=pwd_context.hash("admin123"), role="Admin"))
        db.commit()
        print("[SatyaPramaan] Default users created: underwriter/underwriter123, admin/admin123")

    # Seed initial known fraud pattern library blocklist
    db.add(FraudPattern(
        pattern_type="pan", 
        pattern_value="FKPPA4521J", 
        severity="CRITICAL", 
        description="Known identity theft PAN card associated with multiple fraudulent claims"
    ))
    db.add(FraudPattern(
        pattern_type="employer", 
        pattern_value="APEX FICTITIOUS TEXTILES", 
        severity="HIGH", 
        description="Fictitious employer template registry match"
    ))
    db.commit()

    db.add(Case(case_id="SP-29402", applicant_name="Karan Singh", risk_score=89, status="Pending"))
    db.add(Case(case_id="SP-18491", applicant_name="Rajesh Kumar", risk_score=94, status="Pending"))
    db.add(Case(case_id="SP-40192", applicant_name="Amit Patel", risk_score=68, status="Escalated"))
    db.add(Case(case_id="SP-82910", applicant_name="Priya Sharma", risk_score=5, status="Approved"))
    db.commit()
    db.commit()

    # Seed mock documents to connect nodes and trigger the Fraud Ring Graph view
    db.add(Document(
        case_id="SP-29402",
        filename="salary_slip_karan.pdf",
        doc_type="Salary Slip",
        file_path="uploads/salary_slip_karan.pdf",
        risk_score=89,
        ocr_data=json.dumps({
            "name": "Karan Singh",
            "pan": "BPHPS2930K",
            "employer": "APEX TECH SOLUTIONS PVT LTD",
            "gross_earnings": 145000.0,
            "deductions": 12000.0,
            "raw_net_pay": 233000.0,
            "net_pay": "Rs. 2,33,000.00"
        }),
        font_anomalies="[]",
        metadata_anomalies="[]"
    ))
    db.add(Document(
        case_id="SP-18491",
        filename="salary_slip_rajesh.pdf",
        doc_type="Salary Slip",
        file_path="uploads/salary_slip_rajesh.pdf",
        risk_score=94,
        ocr_data=json.dumps({
            "name": "Rajesh Kumar",
            "pan": "BPHPS2930K",  # Shared PAN (Identity theft!)
            "employer": "APEX TECH SOLUTIONS PVT LTD",  # Shared Employer
            "gross_earnings": 145000.0,
            "deductions": 12000.0,
            "raw_net_pay": 133000.0,
            "net_pay": "Rs. 1,33,000.00"
        }),
        font_anomalies="[]",
        metadata_anomalies="[]"
    ))
    db.add(Document(
        case_id="SP-40192",
        filename="salary_slip_amit.pdf",
        doc_type="Salary Slip",
        file_path="uploads/salary_slip_amit.pdf",
        risk_score=68,
        ocr_data=json.dumps({
            "name": "Amit Patel",
            "pan": "AMIPAT9012A",
            "employer": "APEX TECH SOLUTIONS PVT LTD",  # Shared Employer
            "gross_earnings": 150000.0,
            "deductions": 15000.0,
            "raw_net_pay": 135000.0,
            "net_pay": "Rs. 1,35,000.00"
        }),
        font_anomalies="[]",
        metadata_anomalies="[]"
    ))
    db.commit()
    print("[SatyaPramaan] Seeded connected Fraud Ring Graph demo dataset")


# ─── Helpers ───────────────────────────────────────────────────────────────────
def log_action(db: Session, action: str, username: str, notes: str = None):
    log = AuditLog(action=action, username=username, notes=notes)
    db.add(log)
    db.commit()


def get_user_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception as e:
        print(f"[get_user_from_token] Decode failed: {e}. Token: {repr(token)}")
        return None



# ─── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    token = jwt.encode({"sub": user.username, "role": user.role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    log_action(db, "USER_LOGIN", user.username, f"Role: {user.role}")
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}


# ─── Health Check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    """Returns real-time connectivity status for each external service."""
    status_map = {}

    # Ollama Local Service
    import urllib.request
    ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
    ollama_available = False
    ollama_status = "Not Running"
    ollama_model = "llama3.2:latest"
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                ollama_available = True
                ollama_status = "Connected"
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                if models:
                    ollama_model = ", ".join(models[:3])
    except Exception as e:
        ollama_status = f"Unreachable: {str(e)[:30]}"

    status_map["ollama_api"] = {
        "available": ollama_available,
        "status": ollama_status,
        "model": ollama_model,
    }

    # AWS Textract
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    status_map["textract"] = {
        "available": bool(aws_key),
        "status": "Connected" if aws_key else "No Credentials",
        "region": os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"),
    }

    # NSDL
    nsdl_key = os.environ.get("NSDL_API_KEY", "")
    status_map["nsdl"] = {
        "available": bool(nsdl_key),
        "status": "Connected" if nsdl_key else "Mock Mode",
    }

    # DigiLocker
    dl_token = os.environ.get("DIGILOCKER_ACCESS_TOKEN", "")
    status_map["digilocker"] = {
        "available": bool(dl_token),
        "status": "Connected" if dl_token else "Mock Mode",
    }

    # MCA21
    mca_key = os.environ.get("MCA21_API_KEY", "")
    status_map["mca21"] = {
        "available": bool(mca_key),
        "status": "Connected" if mca_key else "Mock Mode",
    }

    # networkx
    try:
        import networkx
        status_map["networkx"] = {"available": True, "status": "Installed", "version": networkx.__version__}
    except ImportError:
        status_map["networkx"] = {"available": False, "status": "Not Installed"}

    # YOLOv8
    try:
        from ultralytics import YOLO
        status_map["yolov8"] = {"available": True, "status": "Installed"}
    except ImportError:
        status_map["yolov8"] = {"available": False, "status": "Not Installed"}

    return {"pipeline_version": "3.0.0", "services": status_map}


# ─── Cases ─────────────────────────────────────────────────────────────────────
@app.get("/api/cases")
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.created_at.desc()).all()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    documents = db.query(Document).filter(Document.case_id == case_id).all()
    parsed_docs = []
    for doc in documents:
        parsed_docs.append({
            "id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type,
            "risk_score": doc.risk_score,
            "ela_image_url": doc.ela_image_url,
            "ela_overlay_url": getattr(doc, "ela_overlay_url", None),
            "ocr_data": json.loads(doc.ocr_data),
            "font_anomalies": json.loads(doc.font_anomalies),
            "metadata_anomalies": json.loads(doc.metadata_anomalies),
        })

    return {"case_details": case, "documents": parsed_docs}


@app.post("/api/cases")
def create_case(case_id: str = Form(...), applicant_name: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(Case).filter(Case.case_id == case_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Case already exists")
    case = Case(case_id=case_id, applicant_name=applicant_name, status="Pending")
    db.add(case)
    db.commit()
    return case


@app.post("/api/cases/{case_id}/disposition")
def case_disposition(
    case_id: str,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session token")

    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.status = status
    db.commit()
    log_action(db, f"CASE_{status.upper()}", user, f"Case {case_id}: {notes or 'No notes'}")
    return {"message": f"Case marked as {status}"}


# ─── Document Scan ─────────────────────────────────────────────────────────────
@app.post("/api/scan")
async def scan_document(
    case_id: str = Form(...),
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found. Create case first.")

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    # Save uploaded file
    file_path = os.path.join("uploads", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    font_anomalies = []
    metadata = {}
    ocr_data = {}
    pixel_anomalies = []
    ela_url = None
    ela_overlay_url = None
    high_anomaly_pct = 0.0

    # ── 1. Calculate Perceptual Document Hash & Check Duplicates ──
    all_docs = db.query(Document).all()
    hash_anomalies, doc_hash = verify_document_duplicate(file_path, all_docs, case_id)

    # ── 2. Run Face Liveness Spoofing Checks ──
    liveness_file_path = file_path
    temp_liveness_img = None
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=150)
                temp_liveness_img = file_path + ".liveness_temp.png"
                pix.save(temp_liveness_img)
                liveness_file_path = temp_liveness_img
            doc.close()
        except Exception as e:
            print(f"[Scan Liveness] PDF render failed: {e}")
            
    liveness_anomalies = verify_face_liveness(liveness_file_path)
    if temp_liveness_img and os.path.exists(temp_liveness_img):
        try:
            os.remove(temp_liveness_img)
        except:
            pass

    # ── 3. Parse File Formats & Extract OCR ──
    math_inconsistent = False
    if ext == ".pdf":
        # ── Layer 1: Metadata + Font Analysis ──
        font_anomalies, metadata = analyze_pdf_fonts(file_path)
        # ── Layer 1: OCR ──
        ocr_data = extract_document_values_from_file(file_path)
        
        # Math checks
        g = ocr_data.get("gross_earnings", 0) or 0
        d = ocr_data.get("deductions", 0) or 0
        n = ocr_data.get("raw_net_pay", 0) or 0
        if g > 0 and d >= 0 and n > 0:
            if abs((g - d) - n) > 10.0:
                math_inconsistent = True

    elif ext in [".jpg", ".jpeg", ".png"]:
        # ── Layer 2: ELA with hot colormap + overlay ──
        ela_filename, overlay_filename, high_anomaly_pct = run_ela(file_path)
        ela_url = f"/uploads/{ela_filename}"
        ela_overlay_url = f"/uploads/{overlay_filename}"

        # ── Copy-Move Detection ──
        pixel_anomalies = run_copy_move_detection(file_path)
        # ── FFT Splice Detection ──
        fft_anomalies = run_fft_analysis(file_path)
        pixel_anomalies.extend(fft_anomalies)

        # ── Seal / Signature Detection ──
        if ENABLE_SEAL_DETECTION:
            seal_anomalies = detect_seals_and_signatures(file_path)
            pixel_anomalies.extend([
                a for a in seal_anomalies
                if a.get("severity") in ("HIGH", "MEDIUM")
            ])

        # ── ELA summary anomaly ──
        ela_severity = "HIGH" if high_anomaly_pct > 0.05 else "MEDIUM"
        pixel_anomalies.append({
            "id": "image-ela-forensics",
            "type": "heatmap",
            "severity": ela_severity,
            "title": f"ELA Compression Analysis — {high_anomaly_pct:.1%} High-Anomaly Pixels",
            "desc": (
                f"Error Level Analysis re-saved image at 95% JPEG quality and computed "
                f"pixel-wise residuals. {high_anomaly_pct:.1%} of pixels exceed the "
                f"manipulation threshold. Red/yellow regions in the heatmap indicate "
                f"areas modified after original compression."
            ),
            "conf": f"{min(97.0, 70.0 + high_anomaly_pct * 500):.1f}%"
        })

        # ── OCR for images via Textract ──
        ocr_data = extract_document_values_from_file(file_path)
    else:
        raise HTTPException(status_code=400, detail="Only PDF and JPEG/PNG files supported")

    # ── 4. Cross-Document Signature Check ──
    case_docs = db.query(Document).filter(Document.case_id == case_id).all()
    curr_temp_doc = Document(filename=filename, file_path=file_path)
    signature_anomalies = run_cross_document_signature_check(case_docs + [curr_temp_doc])

    # ── 5. Temporal Chronology checks ──
    mca_data = {}
    if ocr_data.get("employer") and ocr_data.get("employer") != "Unknown":
        mca_data = verify_company_mca(ocr_data.get("employer"))
    temporal_anomalies = run_temporal_checks(ocr_data, mca_data)

    # ── 6. Known Fraud Pattern Library Checks ──
    library_anomalies = []
    blocklist = db.query(FraudPattern).all()
    for pattern in blocklist:
        if pattern.pattern_type == "hash" and doc_hash:
            from forensics.image_hashing import hamming_distance
            if hamming_distance(doc_hash, pattern.pattern_value) <= 2:
                library_anomalies.append({
                    "id": f"library-blocklist-hash-{pattern.id}",
                    "type": "library",
                    "severity": pattern.severity,
                    "title": "Blocklisted Document Hash Match",
                    "desc": f"Document hash matches a blocklisted fraud pattern: {pattern.description}",
                    "conf": "99.0%"
                })
        elif pattern.pattern_type == "pan" and ocr_data.get("pan") and ocr_data.get("pan") != "Unknown":
            curr_pan = ocr_data["pan"].strip().upper()
            if curr_pan == pattern.pattern_value.strip().upper():
                library_anomalies.append({
                    "id": f"library-blocklist-pan-{pattern.id}",
                    "type": "library",
                    "severity": pattern.severity,
                    "title": "Blocklisted PAN Card Match",
                    "desc": f"Extracted PAN card number matches blocklisted identity: {pattern.description}",
                    "conf": "99.0%"
                })
        elif pattern.pattern_type == "employer" and ocr_data.get("employer") and ocr_data.get("employer") != "Unknown":
            curr_emp = ocr_data["employer"].strip().upper()
            if pattern.pattern_value.strip().upper() in curr_emp or curr_emp in pattern.pattern_value.strip().upper():
                library_anomalies.append({
                    "id": f"library-blocklist-employer-{pattern.id}",
                    "type": "library",
                    "severity": pattern.severity,
                    "title": "Blocklisted Fictitious Employer Match",
                    "desc": f"Employer name matches a blocklisted fictitious entity: {pattern.description}",
                    "conf": "95.0%"
                })

    # Combine all anomalies
    meta_anom = [a for a in font_anomalies if a.get("type") == "metadata"]
    font_anom = [a for a in font_anomalies if a.get("type") == "font"]
    
    all_anomalies = (
        font_anomalies + 
        pixel_anomalies + 
        hash_anomalies + 
        liveness_anomalies + 
        signature_anomalies + 
        temporal_anomalies + 
        library_anomalies
    )

    # ── 7. Unified Weighted Risk Scoring ──
    risk_results = calculate_weighted_risk(
        font_anomalies=font_anom,
        math_inconsistent=math_inconsistent,
        metadata_anomalies=meta_anom,
        pixel_anomalies=pixel_anomalies,
        hash_anomalies=hash_anomalies,
        liveness_anomalies=liveness_anomalies,
        signature_anomalies=signature_anomalies,
        temporal_anomalies=temporal_anomalies,
        library_anomalies=library_anomalies
    )

    # ── Layer 3: Fraud Ring Check (graph-based) ──────────────────────────────
    all_cases = db.query(Case).all()
    all_docs = db.query(Document).all()

    # Build cases data for graph
    graph_cases = []
    for c in all_cases:
        docs_for_case = [d for d in all_docs if d.case_id == c.case_id]
        employer = "Unknown"
        pan = "Unknown"
        for d in docs_for_case:
            try:
                ocr = json.loads(d.ocr_data)
                if ocr.get("employer", "Unknown") != "Unknown":
                    employer = ocr["employer"]
                if ocr.get("pan", "Unknown") != "Unknown":
                    pan = ocr["pan"]
            except:
                pass
        graph_cases.append({
            "case_id": c.case_id,
            "applicant_name": c.applicant_name,
            "employer": employer,
            "pan": pan,
        })

    # Add current case with extracted data
    graph_cases.append({
        "case_id": case_id,
        "applicant_name": case.applicant_name,
        "employer": ocr_data.get("employer", "Unknown"),
        "pan": ocr_data.get("pan", "Unknown"),
    })

    fraud_ring = detect_fraud_rings(graph_cases, current_case_id=case_id)
    if fraud_ring.get("fraud_ring_detected"):
        for node in fraud_ring.get("suspicious_nodes", [])[:3]:
            all_anomalies.append({
                "id": f"graph-fraud-ring-{node.get('type')}",
                "type": "graph",
                "severity": "HIGH",
                "title": f"Fraud Ring Signal: Shared {node.get('type', 'entity').title()}",
                "desc": node.get("reason", "Entity appears in multiple loan applications"),
                "conf": "91.0%"
            })

    # ── Layer 4: LLM Insight (Claude Sonnet 4) ────────────────────────────────
    llm_result = generate_llm_insight_sync(all_anomalies, ocr_data, case_id)
    llm_insight_html = llm_result.get("html_summary", "")
    llm_json = {k: v for k, v in llm_result.items() if k != "html_summary"}

    # ── Save to DB ────────────────────────────────────────────────────────────
    doc_record = Document(
        case_id=case_id,
        filename=filename,
        doc_type=doc_type,
        file_path=file_path,
        ela_image_url=ela_url,
        risk_score=risk_results["risk_score"],
        ocr_data=json.dumps(ocr_data),
        font_anomalies=json.dumps(all_anomalies),
        metadata_anomalies=json.dumps([metadata] if metadata else []),
        doc_hash=doc_hash
    )
    # Store overlay URL if column exists
    try:
        doc_record.ela_overlay_url = ela_overlay_url
    except:
        pass

    db.add(doc_record)

    if risk_results["risk_score"] > (case.risk_score or 0):
        case.risk_score = risk_results["risk_score"]
    db.commit()

    # ── Response ──────────────────────────────────────────────────────────────
    return {
        "filename": filename,
        "doc_type": doc_type,
        "risk_score": risk_results["risk_score"],
        "risk_level": risk_results["risk_level"],
        "confidence": risk_results["confidence"],
        "ela_image_url": ela_url,
        "ela_overlay_url": ela_overlay_url,
        "ela_anomaly_pct": round(high_anomaly_pct * 100, 2),
        "anomalies": all_anomalies,
        "extracted_data": ocr_data,
        "llm_insight": llm_insight_html,
        "llm_json": llm_json,
        "fraud_ring": fraud_ring,
        "recommendation": f"RISK LEVEL: {risk_results['risk_level']} — {llm_result.get('recommended_action', 'MANUAL_REVIEW')}",
        "textract_used": ocr_data.get("textract_source", False),
        "metadata": metadata,
    }


# ─── Cross-Document Verification ──────────────────────────────────────────────
@app.post("/api/cross-verify")
async def cross_verify(
    bank_stmt: UploadFile = File(...),
    salary_slip: UploadFile = File(...),
    itr: Optional[UploadFile] = File(None)
):
    bank_path = os.path.join("uploads", bank_stmt.filename)
    with open(bank_path, "wb") as b:
        shutil.copyfileobj(bank_stmt.file, b)

    sal_path = os.path.join("uploads", salary_slip.filename)
    with open(sal_path, "wb") as s:
        shutil.copyfileobj(salary_slip.file, s)

    itr_path = None
    if itr:
        itr_path = os.path.join("uploads", itr.filename)
        with open(itr_path, "wb") as i:
            shutil.copyfileobj(itr.file, i)

    def parse_pdf_text(path):
        if not path:
            return ""
        txt = ""
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    content = page.extract_text()
                    if content:
                        txt += content + "\n"
        except:
            pass
        return txt

    # Try Textract first (file-level), fallback to pdfplumber text extraction
    bank_vals = extract_document_values_from_file(bank_path)
    sal_vals = extract_document_values_from_file(sal_path)
    itr_vals = extract_document_values_from_file(itr_path) if itr_path else None

    # Store raw text for salary-bank credit matching
    bank_vals["raw_text"] = parse_pdf_text(bank_path)

    result = run_cross_check(bank_vals, sal_vals, itr_vals)
    return result


# ─── Fraud Graph Analysis ─────────────────────────────────────────────────────
@app.get("/api/graph-analysis/{case_id}")
def get_graph_analysis(case_id: str, db: Session = Depends(get_db)):
    """On-demand fraud ring analysis for a specific case."""
    all_cases = db.query(Case).all()
    all_docs = db.query(Document).all()

    graph_cases = []
    for c in all_cases:
        docs_for_case = [d for d in all_docs if d.case_id == c.case_id]
        employer = "Unknown"
        pan = "Unknown"
        for d in docs_for_case:
            try:
                ocr = json.loads(d.ocr_data)
                if ocr.get("employer", "Unknown") != "Unknown":
                    employer = ocr["employer"]
                if ocr.get("pan", "Unknown") != "Unknown":
                    pan = ocr["pan"]
            except:
                pass
        graph_cases.append({
            "case_id": c.case_id,
            "applicant_name": c.applicant_name,
            "employer": employer,
            "pan": pan,
        })

    return detect_fraud_rings(graph_cases, current_case_id=case_id)


# ─── External Verify ─────────────────────────────────────────────────────────
@app.get("/api/external-verify")
def external_verify(
    pan: Optional[str] = None,
    company: Optional[str] = None
):
    result = {}
    if pan:
        result["pan"] = verify_pan(pan)
    if company:
        result["company"] = verify_company_mca(company)
    if not pan and not company:
        raise HTTPException(status_code=400, detail="Provide at least one of: pan, company")
    return result


# ─── Fraud Pattern Library ───────────────────────────────────────────────────
@app.get("/api/fraud-library")
def list_fraud_patterns(db: Session = Depends(get_db)):
    return db.query(FraudPattern).order_by(FraudPattern.created_at.desc()).all()

@app.post("/api/fraud-library")
def report_fraud_pattern(
    pattern_type: str = Form(...),
    pattern_value: str = Form(...),
    description: str = Form("Reported by Underwriter Cockpit"),
    db: Session = Depends(get_db)
):
    val = pattern_value.strip().upper()
    existing = db.query(FraudPattern).filter(
        FraudPattern.pattern_type == pattern_type,
        FraudPattern.pattern_value == val
    ).first()
    if existing:
        return {"message": "Pattern already blocklisted", "item": existing}
        
    pattern = FraudPattern(
        pattern_type=pattern_type,
        pattern_value=val,
        severity="CRITICAL" if pattern_type in ("hash", "pan") else "HIGH",
        description=description
    )
    db.add(pattern)
    db.commit()
    log_action(db, "REPORT_FRAUD_PATTERN", "system", f"Blocklisted {pattern_type}: {val}")
    return {"message": "Successfully added to Fraud Pattern Library", "item": pattern}

# ─── Audit Logs ──────────────────────────────────────────────────────────────
@app.get("/api/audit-logs")
def get_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()


# ─── Static file serving ─────────────────────────────────────────────────────
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/samples", StaticFiles(directory="samples"), name="samples")

# Subclass StaticFiles to support SPA routing (fallback to index.html)
from starlette.exceptions import HTTPException as StarletteHTTPException

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                # Do NOT fallback to index.html for assets, uploads, or files with extensions
                if path.startswith("assets/") or path.startswith("uploads/") or "." in path.split("/")[-1]:
                    raise ex
                return await super().get_response("index.html", scope)
            raise ex

# Serve React frontend static application directly from the frontend/dist folder
# The API endpoints are registered first, so they are resolved before StaticFiles matches the files
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dist_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend", "dist"))
if os.path.exists(frontend_dist_dir):
    app.mount("/", SPAStaticFiles(directory=frontend_dist_dir, html=True), name="static")
else:
    print(f"[SatyaPramaan] Warning: Frontend dist directory not found at {frontend_dist_dir}. Serving API only.")


