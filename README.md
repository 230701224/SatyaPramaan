# SatyaPramaan AI — Real-Time Document Forgery Detection & Underwriting Cockpit

SatyaPramaan AI ("Truth Verification through AI") is an enterprise-grade cybersecurity and fintech document integrity verification platform designed for bank underwriting workflows. This repository contains the complete full-stack implementation built for the cybersecurity hackathon, featuring a **FastAPI backend** (housing real image forensics, pdfplumber character-level font scanners, regex OCR parsers, and a secure SQLite database) and a **React.js (Vite) frontend** (using Tailwind CSS, Recharts, and Framer Motion).

---

## 🛠️ Tech Stack & Forensics Engines

### 1. Python FastAPI Backend (`/backend`)
*   **PDF Typography forensics (`/forensics/font_analysis.py`)**: Uses `pdfplumber` to extract character-level coordinates, sizes, and font-names. Groups text by horizontal lines and runs anomaly filters to detect characters or words rendered in a different font style than the line's dominant font (e.g. overwriting a number using a standard font editor).
*   **Image Error Level Analysis (ELA) (`/forensics/image_forgery.py`)**: For uploaded JPEG/PNG scanned sheets, it resaves the file at 95% compression, calculates pixel-level difference scales, and generates a visual forensic contrast heatmap highlighting spliced signature overlays.
*   **Copy-Move Cloning Detector (`/forensics/image_forgery.py`)**: Implements OpenCV's **ORB (Oriented FAST and Rotated BRIEF) keypoints descriptor matches** to scan for duplicate image blocks copied and pasted in separate regions (indicating signature/seal duplication).
*   **Regex OCR Extractor (`/forensics/ocr.py`)**: Parses PDF text for PAN Card patterns, Aadhaar numbers, GSTIN codes, and salary balances.
*   **Relational Database (`/database`)**: Sets up SQLite schemas via SQLAlchemy (`models.py`) mapping Users, Cases, Documents, and Audit Logs.
*   **Security & JWT Auths (`/main.py`)**: Full JSON Web Token (JWT) token sessions with Role-Based Access Controls (Underwriter, Admin, Reviewer, Compliance Officer).

### 2. Vite React Frontend (`/frontend`)
*   **Dashboard Cockpit**: Uses `Recharts` to draw fraud trends and incident categories, coupled with real-time pending queues fetched from the DB.
*   **Forensic Scan Workspace**: Fully integrated dropzone. Displays side-by-side original next to the ELA heatmap (for images) and draws red tooltips highlighting font outlier coordinate boxes in PDF texts.
*   **Cross-Document Analyzer Matrix**: Compares files side-by-side (Bank Statement vs. Salary Slip vs. ITR-V) and highlights discrepancies.
*   **Audit Vault Logs**: Standard logger records user entries, logins, and dispositions (Approve, Reject, Escalate).

---

## 🚀 Setup & Launch Instructions

### Prerequisites
Make sure you have **Node.js (v18+)** and **Python (v3.10+)** installed.

### Step 1: Generate PDF Test Samples
In the root directory, compile the ReportLab test PDFs (one genuine and one tampered with font mismatch and ledger math errors):
```bash
python create_samples.py
```
This generates `sample_genuine.pdf` and `sample_tampered.pdf` in the `/samples` folder.

### Step 2: Start the FastAPI Backend
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Launch the Uvicorn server on port **8001**:
   ```bash
   python -m uvicorn main:app --port 8001 --host 127.0.0.1
   ```
   *The SQLite database `secure.db` is initialized on startup and prepopulates default credentials.*

### Step 3: Start the Vite React Frontend
1. Open a new terminal and navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Start the Vite dev server on port **5173**:
   ```bash
   npm run dev
   ```
3. Open your browser and navigate to: **[http://localhost:5173](http://localhost:5173)**

---

### ⚡ Alternative: Run Full-Stack locally (Single Process)
For convenience during local testing, you can run both the FastAPI backend and the compiled React production frontend on port **8001** with a single command from the project root directory:
```bash
python main.py
```
This loads the full backend logic and automatically serves the React application. Open your browser and navigate to: **[http://localhost:8001](http://localhost:8001)**

---


## 👤 Predefined Hackathon Credentials

Log in using the prepopulated database credentials:
*   **Role: Underwriter**
    *   **Username**: `underwriter`
    *   **Password**: `underwriter123`
*   **Role: Admin**
    *   **Username**: `admin`
    *   **Password**: `admin123`

---

## 🔒 Security & Verification Checks to Demonstrate

1.  **PDF Font Manipulation**: Upload `sample_tampered.pdf` in the Integrity Scanner. The backend parses it, highlights `2,33,000.00` in red as a Times-Roman font outlier, and warns of a Gross-to-Net math calculation discrepancy.
2.  **Scanned Image ELA Heatmaps**: Upload any scanned page (e.g., JPEG/PNG). ELA generates a side-by-side compression contrast view.
3.  **Crosscheck Reconciliations**: Go to Crosscheck Analyzer. Load bank statement, salary slip, and ITR. Reconcile to see mismatches between bankcredits and salary slip net values.
