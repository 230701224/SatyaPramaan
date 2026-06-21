import os
import cv2
import numpy as np
import urllib.request

CASCADE_XML_NAME = "haarcascade_frontalface_default.xml"
CASCADE_XML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), CASCADE_XML_NAME)
CASCADE_URL = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"

def _ensure_cascade_exists():
    """Download the Haar Cascade XML from OpenCV repository if not already present."""
    if not os.path.exists(CASCADE_XML_PATH):
        try:
            print(f"[Liveness] Downloading Haar Cascade XML to {CASCADE_XML_PATH}...")
            urllib.request.urlretrieve(CASCADE_URL, CASCADE_XML_PATH)
            print("[Liveness] Download complete.")
        except Exception as e:
            print(f"[Liveness] Failed to download Haar Cascade: {e}")

def verify_face_liveness(image_path: str) -> list:
    """
    Scans the document image for faces and performs anti-spoofing checks:
    1. Face Detection: Uses OpenCV Haar Cascade.
    2. Anti-Spoofing:
       - FFT Texture Analysis: Screen/printed photos show moiré pattern spikes (high frequency harmonics).
       - Laplacian Variance: Re-photographed images have a significantly lower focus/sharpness.
    """
    anomalies = []
    
    # Read image in color and grayscale
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        return anomalies
        
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # Ensure Haar cascade is available
    _ensure_cascade_exists()
    if not os.path.exists(CASCADE_XML_PATH):
        return anomalies
        
    try:
        face_cascade = cv2.CascadeClassifier(CASCADE_XML_PATH)
        # detectMultiScale parameters optimized for document photos
        faces = face_cascade.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=3, minSize=(40, 40))
        
        for idx, (x, y, w, h) in enumerate(faces):
            face_crop = img_gray[y:y+h, x:x+w]
            
            # ── 1. Laplacian Variance (Focus / Blur Check) ──
            # Re-photographed or heavily compressed fake faces show low variance (blur)
            laplacian = cv2.Laplacian(face_crop, cv2.CV_64F)
            lap_var = float(np.var(laplacian))
            
            # ── 2. FFT frequency analysis on the face crop (Moiré / Screen Check) ──
            f = np.fft.fft2(face_crop.astype(np.float32))
            fshift = np.fft.fftshift(f)
            magnitude = np.abs(fshift)
            log_mag = np.log1p(magnitude)
            
            # Remove DC component (center of the image)
            cx, cy = h // 2, w // 2
            log_mag_no_dc = log_mag.copy()
            log_mag_no_dc[cx-3:cx+3, cy-3:cy+3] = 0
            
            # Detect periodic spikes typical of moiré patterns
            threshold = np.mean(log_mag_no_dc) + 4.0 * np.std(log_mag_no_dc)
            peaks = int(np.sum(log_mag_no_dc > threshold))
            
            # Anti-spoofing decision rules
            is_spoof = False
            reasons = []
            severity = "MEDIUM"
            confidence = 75.0
            
            # Low focus variance indicator
            if lap_var < 80.0:
                is_spoof = True
                reasons.append(f"Low texture variance ({lap_var:.1f}) indicating excessive blur / scanned printout")
                severity = "HIGH"
                confidence = max(confidence, 85.0)
                
            # High frequency periodic spikes indicator (moiré pattern screen reproduction)
            if peaks > 6:
                is_spoof = True
                reasons.append(f"Moiré pattern detected ({peaks} FFT harmonic peaks) indicating screen recapture or print mesh")
                severity = "HIGH"
                confidence = max(confidence, 92.0)
                
            bbox = {
                "x1": int(x), "y1": int(y),
                "x2": int(x + w), "y2": int(y + h),
                "width": int(img_bgr.shape[1]),
                "height": int(img_bgr.shape[0])
            }
            
            if is_spoof:
                anomalies.append({
                    "id": f"face-liveness-spoof-{idx}",
                    "type": "liveness",
                    "severity": severity,
                    "title": "Photo Liveness Spoof Alert (Printed/Recaptured Face)",
                    "desc": (
                        f"Liveness audit on ID photo #{idx + 1} failed. "
                        f"Indicators: {'; '.join(reasons)}. "
                        f"Genuine ID cards feature sharp, direct physical photos without screen grids or moiré artifacts."
                    ),
                    "conf": f"{confidence:.1f}%",
                    "bbox": bbox
                })
            else:
                anomalies.append({
                    "id": f"face-liveness-genuine-{idx}",
                    "type": "liveness",
                    "severity": "INFO",
                    "title": "Face Photo Liveness Confirmed",
                    "desc": f"ID photo #{idx + 1} passed anti-spoofing tests. Texture sharp (variance: {lap_var:.1f}), no moiré patterns.",
                    "conf": "85.0%",
                    "bbox": bbox
                })
                
    except Exception as e:
        print(f"[verify_face_liveness] Error: {e}")
        
    return anomalies
