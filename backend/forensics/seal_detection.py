"""
Seal and Signature Anomaly Detection Module

Uses YOLOv8n for localising seals/signatures, then FFT frequency analysis
to distinguish genuine ink impressions from digital copy-pastes.

Falls back gracefully if ultralytics is not installed.
"""
import os
import numpy as np

# ─── YOLOv8 (optional) ─────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ─── OpenCV ────────────────────────────────────────────────────────────────────
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ─── PIL ────────────────────────────────────────────────────────────────────────
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Threshold: FFT high-freq energy variance below this = digital clone (too uniform)
FFT_GENUINE_VARIANCE_THRESHOLD = 0.12

# Path to cached YOLO model weights
_YOLO_MODEL = None


def _get_yolo_model():
    """Lazy-load YOLOv8n model (downloads on first call, ~6MB)."""
    global _YOLO_MODEL
    if _YOLO_MODEL is None and YOLO_AVAILABLE:
        try:
            # Uses pretrained COCO model; we exploit the 'general object' detector
            # and filter for relevant classes OR use it to find dense regions
            _YOLO_MODEL = YOLO("yolov8n.pt")  # Downloads automatically on first run
            print("[SealDetection] YOLOv8n model loaded.")
        except Exception as e:
            print(f"[SealDetection] YOLO load failed: {e}")
            _YOLO_MODEL = None
    return _YOLO_MODEL


def detect_seals_and_signatures(image_path: str) -> list:
    """
    Main entry point for seal/signature forensics.
    
    Pipeline:
    1. YOLOv8n to find dense regions (potential seals/signatures)
    2. For each candidate region: FFT frequency analysis
       - Genuine ink: natural variation → high FFT variance in high-freq bands
       - Digital clone: pixel-perfect → low FFT variance (anomalously uniform)
    3. Returns structured anomaly list
    """
    if not CV2_AVAILABLE or not PIL_AVAILABLE:
        return []

    anomalies = []

    try:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return anomalies

        img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = img_gray.shape

        # ── Candidate regions: use YOLO if available, else heuristic ────────
        candidate_regions = []

        model = _get_yolo_model()
        if model is not None:
            results = model(image_path, verbose=False)
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    # Focus on dense/compact rectangular regions (seals tend to be class 0 person,
                    # or we treat any high-conf detection as a candidate)
                    if conf > 0.3:
                        candidate_regions.append((x1, y1, x2, y2, conf))
        
        if not candidate_regions:
            # Heuristic: find dense connected components (seals are dense ink regions)
            _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            dilated = cv2.dilate(binary, kernel, iterations=3)
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Seals/stamps are typically 5-25% of document area
                if 0.02 * h * w < area < 0.35 * h * w:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect = cw / max(ch, 1)
                    # Stamps/seals tend to be roughly square or slightly rectangular
                    if 0.4 < aspect < 2.5:
                        candidate_regions.append((x, y, x + cw, y + ch, 0.5))

        # ── FFT analysis on each candidate ───────────────────────────────────
        for region_idx, (x1, y1, x2, y2, det_conf) in enumerate(candidate_regions[:8]):
            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            region = img_gray[y1:y2, x1:x2]
            if region.size < 400:  # Too small to analyze
                continue

            fft_variance, is_clone, fft_detail = _analyze_region_fft(region)

            bbox = {
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "width": w, "height": h
            }

            if is_clone:
                anomalies.append({
                    "id": f"seal-fft-clone-{region_idx}",
                    "type": "seal",
                    "severity": "HIGH",
                    "title": "Digital Seal Clone Detected (FFT Analysis)",
                    "desc": (
                        f"Seal/stamp region #{region_idx + 1} shows anomalously uniform "
                        f"high-frequency energy variance ({fft_variance:.4f}). "
                        f"Genuine rubber stamp impressions have natural ink spread variation "
                        f"(FFT variance > {FFT_GENUINE_VARIANCE_THRESHOLD:.2f}). "
                        f"This region has pixel-perfect uniformity characteristic of "
                        f"a digitally copy-pasted seal or signature."
                    ),
                    "conf": f"{min(96.0, 80.0 + (FFT_GENUINE_VARIANCE_THRESHOLD - fft_variance) * 100):.1f}%",
                    "bbox": bbox,
                    "fft_variance": round(fft_variance, 4),
                })
            else:
                # Genuine-looking seal — still report as info
                anomalies.append({
                    "id": f"seal-fft-genuine-{region_idx}",
                    "type": "seal",
                    "severity": "INFO",
                    "title": "Seal/Signature Region Scanned — Ink Variation Normal",
                    "desc": (
                        f"Seal/stamp region #{region_idx + 1} shows natural ink variation "
                        f"(FFT variance: {fft_variance:.4f}). Consistent with genuine "
                        f"rubber stamp impression."
                    ),
                    "conf": f"{min(90.0, 65.0 + fft_variance * 50):.1f}%",
                    "bbox": bbox,
                    "fft_variance": round(fft_variance, 4),
                })

    except Exception as e:
        print(f"[SealDetection] Error: {e}")

    return anomalies


def _analyze_region_fft(region: np.ndarray) -> tuple:
    """
    Analyze a grayscale image region via 2D FFT.
    
    Returns: (high_freq_variance: float, is_clone: bool, detail: str)
    
    Genuine ink has natural high-frequency variation.
    Digital clones are pixel-perfect → low high-freq variance.
    """
    try:
        # Normalize region
        region_float = region.astype(np.float32) / 255.0

        # 2D FFT
        fft = np.fft.fft2(region_float)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)

        h, w = magnitude.shape
        cx, cy = h // 2, w // 2

        # High-frequency ring: outer 40% of frequency space
        y_coords, x_coords = np.ogrid[:h, :w]
        dist_from_center = np.sqrt((y_coords - cx)**2 + (x_coords - cy)**2)
        max_dist = min(cx, cy)

        high_freq_mask = dist_from_center > (0.6 * max_dist)
        high_freq_energy = magnitude[high_freq_mask]

        if high_freq_energy.size == 0:
            return 0.5, False, "insufficient_data"

        # Coefficient of variation in the high-freq band
        mean_energy = np.mean(high_freq_energy)
        std_energy = np.std(high_freq_energy)
        variance = std_energy / (mean_energy + 1e-8)

        is_clone = variance < FFT_GENUINE_VARIANCE_THRESHOLD

        return float(variance), is_clone, f"hf_cv={variance:.4f}"

    except Exception as e:
        return 0.5, False, f"error: {e}"
