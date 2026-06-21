import os
from PIL import Image
import numpy as np

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

def calculate_dhash(file_path: str, hash_size: int = 8) -> str:
    """
    Computes a Difference Hash (dHash) for an image or PDF document.
    For PDFs, it renders the first page as a PIL Image.
    
    Difference Hashing:
    - Resizes to (hash_size + 1, hash_size)
    - Converts to grayscale (L)
    - Compares horizontal adjacent pixels (diff)
    - Returns a 16-character hex string representing the 64-bit hash
    """
    ext = os.path.splitext(file_path)[1].lower()
    img = None
    
    try:
        if ext == ".pdf":
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(file_path)
                if len(doc) > 0:
                    page = doc[0]
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                doc.close()
            else:
                # If no PyMuPDF, read raw bytes and hash them using sha256 as fallback
                import hashlib
                with open(file_path, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                return h[:16]
        else:
            img = Image.open(file_path)
            
        if img:
            # Convert to grayscale and resize
            img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = np.array(img)
            # Compute difference between adjacent columns
            diff = pixels[:, 1:] > pixels[:, :-1]
            
            # Pack bits into bytes and convert to hex
            decimal_value = 0
            hex_string = []
            for row in diff:
                row_val = 0
                for col in row:
                    row_val = (row_val << 1) | int(col)
                hex_string.append(f"{row_val:02x}")
            return "".join(hex_string)
            
    except Exception as e:
        print(f"[calculate_dhash] Error: {e}")
        # Fallback to file size + name hash on error
        import hashlib
        fallback_str = f"{os.path.basename(file_path)}_{os.path.getsize(file_path) if os.path.exists(file_path) else 0}"
        return hashlib.sha256(fallback_str.encode()).hexdigest()[:16]

def hamming_distance(hash1: str, hash2: str) -> int:
    """Computes the Hamming distance between two hex hashes."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 99
    try:
        bin1 = bin(int(hash1, 16))[2:].zfill(len(hash1) * 4)
        bin2 = bin(int(hash2, 16))[2:].zfill(len(hash2) * 4)
        return sum(c1 != c2 for c1, c2 in zip(bin1, bin2))
    except Exception:
        return 99

def verify_document_duplicate(file_path: str, db_docs: list, current_case_id: str) -> tuple:
    """
    Compares the calculated hash of the current file against all documents in the DB.
    If a match with Hamming distance <= 2 is found in another case, flags it.
    """
    anomalies = []
    current_hash = calculate_dhash(file_path)
    if not current_hash:
        return anomalies, current_hash
        
    for doc in db_docs:
        # Don't flag duplicates within the same case (e.g. re-uploading)
        if doc.case_id == current_case_id:
            continue
            
        stored_hash = getattr(doc, "doc_hash", None)
        if not stored_hash:
            continue
            
        dist = hamming_distance(current_hash, stored_hash)
        # Hamming distance of 0 means identical, 1-2 means extremely similar (minor compression/meta delta)
        if dist <= 2:
            anomalies.append({
                "id": "duplicate-document-clone",
                "type": "hash",
                "severity": "CRITICAL",
                "title": "Duplicate Document Clone Detected (Image Hashing)",
                "desc": (
                    f"Perceptual image hashing detected that this document is a duplicate "
                    f"or modification (Hamming distance: {dist}) of '{doc.filename}' "
                    f"uploaded in Case '{doc.case_id}'. "
                    f"Indicates cloned/fabricated documents shared across different loan applications."
                ),
                "conf": "99.0%",
                "matched_case_id": doc.case_id,
                "matched_filename": doc.filename
            })
            break  # One match is sufficient to raise high alarm
            
    return anomalies, current_hash
