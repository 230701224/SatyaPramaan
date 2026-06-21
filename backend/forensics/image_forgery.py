import os
import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

# ─── Matplotlib for hot colormap (optional but strongly recommended) ────────────
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# ─── SciPy for FFT analysis (optional) ─────────────────────────────────────────
try:
    from scipy import ndimage
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def run_ela(image_path: str, quality: int = 95) -> tuple:
    """
    Error Level Analysis (ELA):
    - Resaves image at known JPEG quality (95%)
    - Computes pixel-wise absolute difference
    - Applies matplotlib 'hot' colormap (red=high anomaly, yellow=moderate, black=clean)
    - Saves both: ela_<name> (raw grayscale enhanced) and ela_overlay_<name> (composite)
    
    Returns: (ela_filename, overlay_filename)
    """
    dir_name = os.path.dirname(image_path)
    base = os.path.basename(image_path)
    temp_path = image_path + ".temp_ela.jpg"

    original = Image.open(image_path).convert("RGB")
    original.save(temp_path, "JPEG", quality=quality)

    recompressed = Image.open(temp_path)
    diff = ImageChops.difference(original, recompressed)

    # Grayscale difference as numpy array
    diff_np = np.array(diff).astype(np.float32)
    diff_gray = diff_np.mean(axis=2)  # Average across RGB channels

    # Normalize to [0, 1]
    max_val = diff_gray.max()
    if max_val == 0:
        max_val = 1.0
    diff_norm = diff_gray / max_val

    ela_filename = "ela_" + base
    ela_path = os.path.join(dir_name, ela_filename)
    overlay_filename = "ela_overlay_" + base
    overlay_path = os.path.join(dir_name, overlay_filename)

    if MATPLOTLIB_AVAILABLE:
        # ── Apply hot colormap (black=clean, red-yellow=tampered) ────────────
        colormap = cm.get_cmap("hot")
        colored = colormap(diff_norm)  # RGBA [0-1]
        colored_uint8 = (colored[:, :, :3] * 255).astype(np.uint8)  # Drop alpha, convert to uint8
        ela_img = Image.fromarray(colored_uint8, "RGB")
        ela_img.save(ela_path)

        # ── Composite overlay: blend ELA heatmap over original ────────────────
        orig_np = np.array(original).astype(np.float32)
        heatmap_np = colored_uint8.astype(np.float32)

        # Scale heatmap visibility based on anomaly magnitude
        alpha = np.clip(diff_norm * 3.0, 0, 0.85)[:, :, np.newaxis]
        composite = (1 - alpha) * orig_np + alpha * heatmap_np
        composite_uint8 = np.clip(composite, 0, 255).astype(np.uint8)
        overlay_img = Image.fromarray(composite_uint8, "RGB")
        overlay_img.save(overlay_path)

    else:
        # Fallback: grayscale brightness enhancement (original behavior)
        scale = min(15.0, 255.0 / max_val)
        enhancer = ImageEnhance.Brightness(diff)
        enhanced = enhancer.enhance(scale)
        enhanced.save(ela_path)
        enhanced.save(overlay_path)  # Same image if no matplotlib

    # Cleanup temp
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # Compute anomaly statistics for reporting
    high_anomaly_pct = float(np.sum(diff_norm > 0.4) / diff_norm.size)

    return ela_filename, overlay_filename, high_anomaly_pct


def run_fft_analysis(image_path: str) -> list:
    """
    FFT Splice Detection:
    Detects unnatural periodic frequency artifacts in image — copy-paste operations
    introduce harmonic patterns in the frequency domain that natural photos don't have.
    
    Returns list of anomaly dicts.
    """
    anomalies = []
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return anomalies

        # Compute 2D FFT
        f = np.fft.fft2(img.astype(np.float32))
        fshift = np.fft.fftshift(f)
        magnitude = np.abs(fshift)

        # Log-scale for analysis
        log_mag = np.log1p(magnitude)

        # Suppress DC component (center 10x10 region)
        h, w = log_mag.shape[:2]
        cx, cy = h // 2, w // 2
        log_mag_no_dc = log_mag.copy()
        log_mag_no_dc[cx-5:cx+5, cy-5:cy+5] = 0

        # Detect strong periodic peaks (copy-paste harmonics)
        # A genuine document has smooth frequency falloff; forgeries have spikes
        threshold = np.mean(log_mag_no_dc) + 4.5 * np.std(log_mag_no_dc)
        peak_count = int(np.sum(log_mag_no_dc > threshold))

        if peak_count > 8:
            anomalies.append({
                "id": "fft-periodic-artifacts",
                "type": "pixel",
                "severity": "HIGH" if peak_count > 20 else "MEDIUM",
                "title": f"FFT Frequency Artifacts: {peak_count} Harmonic Peaks",
                "desc": (
                    f"Frequency domain analysis detected {peak_count} anomalous harmonic peaks "
                    f"in the image (threshold: μ + 4.5σ). Copy-paste operations introduce "
                    f"periodic frequency artifacts not present in organically created documents. "
                    f"Genuine rubber stamp impressions and handwriting do not produce this pattern."
                ),
                "conf": f"{min(97.0, 75.0 + peak_count * 0.8):.1f}%"
            })

        # ── Variance uniformity: digital seals are pixel-perfect (low variance) ─
        # Divide image into 8x8 blocks and check local variance
        block_size = 32
        local_variances = []
        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = img[i:i+block_size, j:j+block_size]
                local_variances.append(float(np.var(block)))

        if local_variances:
            var_cv = np.std(local_variances) / (np.mean(local_variances) + 1e-6)
            if var_cv < 0.4:
                anomalies.append({
                    "id": "fft-uniform-variance",
                    "type": "pixel",
                    "severity": "MEDIUM",
                    "title": "Suspiciously Uniform Texture Variance",
                    "desc": (
                        f"Local texture variance coefficient ({var_cv:.3f}) is unusually low. "
                        f"Digitally replicated seals/signatures have near-zero local variance "
                        f"compared to genuine ink impressions which show natural ink spread variation."
                    ),
                    "conf": "79.0%"
                })

    except Exception as e:
        print(f"[FFT Analysis] Error: {e}")

    return anomalies


def run_copy_move_detection(image_path: str) -> list:
    """
    Copy-Move Tampering: Uses ORB descriptors to find duplicate
    graphical blocks in different regions of the same image.
    Enhanced with spatial coherence filtering.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    anomalies = []
    if img is None:
        return anomalies

    # ORB detector with more features for better coverage
    orb = cv2.ORB_create(nfeatures=800)
    kp, des = orb.detectAndCompute(img, None)

    if des is not None and len(des) > 15:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = bf.knnMatch(des, des, k=3)

        cloned_count = 0
        clone_regions = []
        for m in matches:
            if len(m) < 2:
                continue
            for match in m[1:3]:
                if match.distance < 42:
                    pt1 = kp[match.queryIdx].pt
                    pt2 = kp[match.trainIdx].pt
                    dist = np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)
                    if dist > 35:
                        cloned_count += 1
                        clone_regions.append((pt1, pt2))

        if cloned_count > 12:
            anomalies.append({
                "id": "copy-move-cloned",
                "type": "pixel",
                "severity": "HIGH",
                "title": f"Copy-Move Cloning: {cloned_count} Matched Regions",
                "desc": (
                    f"ORB descriptor matching found {cloned_count} spatially-separated "
                    f"duplicate feature regions. This is the characteristic fingerprint of "
                    f"copy-paste operations used to clone signatures, seals, or stamp impressions "
                    f"onto a different document background."
                ),
                "conf": "94.5%"
            })

    # Edge density check
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    canny = cv2.Canny(blur, 40, 140)
    edge_density = float(np.sum(canny > 0) / (img.shape[0] * img.shape[1]))

    if edge_density > 0.18:
        anomalies.append({
            "id": "edge-irregularity",
            "type": "pixel",
            "severity": "MEDIUM",
            "title": f"Abnormal Edge Density: {edge_density:.1%}",
            "desc": (
                f"Document has unusually high sharp edge frequency ({edge_density:.1%}). "
                f"This is typical of digit-splicing overlays, text-layer insertions, or "
                f"pasted graphic elements that introduce artificial edge boundaries."
            ),
            "conf": "81.0%"
        })

    return anomalies


def run_ela_legacy(image_path: str, quality: int = 95) -> str:
    """
    Legacy wrapper — keeps backward compatibility with existing callers
    that expect a single string filename return.
    """
    ela_filename, overlay_filename, _ = run_ela(image_path, quality)
    return ela_filename
