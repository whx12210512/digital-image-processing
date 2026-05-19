"""Barcode / QR code region localization.

Implements multi-strategy detection:
  (a) Edge + morphology coarse detection
  (b) Gradient direction histogram for barcode refinement
  (c) Finder Pattern detection for QR codes
"""

import cv2
import numpy as np
from math import sqrt, atan2, degrees


# ---------- (a) Edge + Morphology Coarse Detection ----------

def canny_edges(img, low=50, high=150):
    """Canny edge detection."""
    return cv2.Canny(img, low, high)


def find_barcode_candidates(edge_img, min_area_ratio=0.01, max_area_ratio=0.80):
    """Find candidate barcode/QR regions from edge image using contours.

    Returns list of rotated rectangles (cv2.RotatedRect).
    """
    h, w = edge_img.shape[:2]
    img_area = h * w
    min_area = img_area * min_area_ratio
    max_area = img_area * max_area_ratio

    # Dilate to connect nearby edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    dilated = cv2.dilate(edge_img, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue

        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
        box = np.int32(box)

        # Rectangularity: contour area / bounding box area
        rect_area = cv2.contourArea(box)
        if rect_area < 1:
            continue
        rectangularity = area / rect_area

        # Filter by shape
        w_rect, h_rect = rect[1]
        if w_rect < 10 or h_rect < 10:
            continue
        aspect_ratio = max(w_rect, h_rect) / min(w_rect, h_rect)

        # Barcodes are elongated (AR > 2), QR codes are squarish
        if rectangularity > 0.5:
            candidates.append((rect, rectangularity, aspect_ratio))

    # Sort by rectangularity (higher = more likely)
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [c[0] for c in candidates]


def find_qr_candidates(edge_img):
    """Shortcut: filter for roughly square candidates (aspect ratio ~1)."""
    all_candidates = find_barcode_candidates(edge_img)
    return [r for r in all_candidates if 0.7 < (min(r[1]) / max(r[1])) < 1.5]


# ---------- (b) Gradient Direction Histogram ----------

def gradient_orientation_density(img, block_size=32):
    """Compute gradient orientation histogram for each block.

    Used to detect barcode regions where gradient directions
    cluster around two opposite angles (parallel edges).
    """
    grad_x = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)

    magnitude = np.sqrt(grad_x ** 2 + grad_y ** 2)
    orientation = np.arctan2(grad_y, grad_x) * 180.0 / np.pi % 180

    h, w = img.shape[:2]
    bh, bw = h // block_size, w // block_size
    density_map = np.zeros((bh, bw), dtype=np.float32)

    for i in range(bh):
        for j in range(bw):
            block_mag = magnitude[i * block_size:(i + 1) * block_size,
                                  j * block_size:(j + 1) * block_size]
            block_ori = orientation[i * block_size:(i + 1) * block_size,
                                     j * block_size:(j + 1) * block_size]

            # Dominant orientation: find the peak in histogram
            # A barcode has two peaks ~180° apart
            hist, _ = np.histogram(block_ori[block_mag > np.mean(block_mag)],
                                    bins=18, range=(0, 180))  # 10° bins
            if len(hist) > 0 and np.max(hist) > 0:
                # High density = strong single direction = likely barcode
                density_map[i, j] = np.max(hist) / (np.sum(hist) + 1e-6)

    return density_map


# ---------- (c) QR Finder Pattern Detection ----------

def detect_finder_patterns(binary_img):
    """Detect QR Code Finder Patterns by scanning for the 1:1:3:1:1 ratio.

    The Finder Pattern has a distinctive "回" shape with alternating
    black/white modules in a 1:1:3:1:1 ratio.

    Returns list of (cx, cy, estimated_module_size) tuples.
    """
    h, w = binary_img.shape[:2]
    centers = []

    # Scan horizontally from center outward
    for y in range(h // 4, 3 * h // 4, 2):
        scanline = binary_img[y, :]
        transitions = np.diff(scanline.astype(np.int32))
        edges = np.where(transitions != 0)[0]

        for i in range(len(edges) - 5):
            e = edges[i:i + 5]
            widths = np.diff(e)

            # Check 1:1:3:1:1 ratio (with tolerance)
            if len(widths) < 5:
                continue
            module = np.mean(widths) / 7.0
            if module < 2:
                continue

            if is_finder_ratio(widths, module, tolerance=0.35):
                cx = int((e[0] + e[-1]) / 2)
                centers.append((cx, y, module))

    return deduplicate_centers(centers, min_dist=15)


def is_finder_ratio(widths, module, tolerance=0.35):
    """Check if 5 width segments match the 1:1:3:1:1 Finder Pattern ratio."""
    expected = np.array([1, 1, 3, 1, 1]) * module
    ratios = widths / (expected + 1e-6)
    return np.all(np.abs(ratios - 1.0) < tolerance)


def deduplicate_centers(centers, min_dist=15):
    """Merge nearby detected centers."""
    if not centers:
        return []

    centers = np.array(centers)  # (cx, cy, module_size)
    kept = []
    used = set()

    for i, c1 in enumerate(centers):
        if i in used:
            continue
        cluster = [c1]
        for j, c2 in enumerate(centers):
            if j <= i or j in used:
                continue
            if np.hypot(c1[0] - c2[0], c1[1] - c2[1]) < min_dist:
                cluster.append(c2)
                used.add(j)
        kept.append(np.mean(cluster, axis=0))

    return [(int(k[0]), int(k[1]), float(k[2])) for k in kept]


def group_finder_patterns(finder_centers, max_qr_size=600):
    """Group three Finder Pattern centers that form a QR code corner triangle.

    In QR codes, the three finder patterns form a right triangle.
    The fourth corner (bottom-right) contains no finder pattern.
    """
    if len(finder_centers) < 3:
        return []

    groups = []
    n = len(finder_centers)

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                a, b, c = finder_centers[i], finder_centers[j], finder_centers[k]
                pts = np.float32([(a[0], a[1]), (b[0], b[1]), (c[0], c[1])])

                # Sort by distance: find the right-angle corner
                # The two farthest points are the hypotenuse endpoints
                dists = [
                    np.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]),
                    np.hypot(pts[1][0] - pts[2][0], pts[1][1] - pts[2][1]),
                    np.hypot(pts[2][0] - pts[0][0], pts[2][1] - pts[0][1]),
                ]

                # Right triangle check: c^2 ≈ a^2 + b^2
                idx = np.argsort(dists)
                short1, short2, long = dists[idx[0]], dists[idx[1]], dists[idx[2]]
                if long < 30:
                    continue
                if abs(short1 ** 2 + short2 ** 2 - long ** 2) / (long ** 2 + 1e-6) < 0.25:
                    # Compute fourth corner
                    # Find which point is between the two hypotenuse endpoints
                    # The corner with the two shorter edges is the right-angle corner
                    corner_indices = list(range(3))
                    right_corner = pts[idx[0]] if idx[0] not in [idx[2]] else pts[idx[1]]
                    # Actually, find the point that's NOT on the hypotenuse
                    hyp_endpoints = [pts[idx[2]], pts[idx[0]]]  # Longest + one short
                    # The right-angle point is the one NOT participating in the hypotenuse
                    for ci in range(3):
                        if ci not in [idx[2], idx[0]]:
                            right_corner = pts[ci]
                            hyp_endpoints = [pts[idx[2]], pts[idx[0]]]
                            break
                    else:
                        right_corner = pts[idx[1]]
                        hyp_endpoints = [pts[idx[2]], pts[idx[1]]]

                    # Fourth point = hyp1 + hyp2 - corner (parallelogram completion)
                    fourth = hyp_endpoints[0] + hyp_endpoints[1] - right_corner

                    # Estimate QR module size from finder patterns
                    mod_size = np.mean([a[2], b[2], c[2]])
                    qr_size = np.hypot(fourth[0] - pts[0][0], fourth[1] - pts[0][1])

                    if qr_size < max_qr_size:
                        # Order: TL, TR, BL, BR (fourth)
                        corners = order_qr_corners(np.float32([pts[0], pts[1], pts[2], fourth]))
                        groups.append((corners, mod_size))

    return groups


def order_qr_corners(pts):
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    # Sort by y, then x
    sorted_y = pts[np.argsort(pts[:, 1])]
    top = sorted_y[:2]
    bottom = sorted_y[2:]

    top_left = top[np.argmin(top[:, 0])]
    top_right = top[np.argmax(top[:, 0])]
    bottom_left = bottom[np.argmin(bottom[:, 0])]
    bottom_right = bottom[np.argmax(bottom[:, 0])]

    return np.float32([top_left, top_right, bottom_right, bottom_left])


# ---------- Full Localization Pipeline ----------

def localize(img, binary, enhanced):
    """Detect and localize all barcodes/QR codes in the image.

    Returns dict with:
        'barcode_rects': list of (rotated_rect, confidence)
        'qr_corners': list of (4_corner_points, module_size)
        'edge_img': for visualization
    """
    h, w = binary.shape[:2]

    # Step 1: Edge detection
    edges = canny_edges(enhanced, low=40, high=140)

    # Step 2: Coarse candidate detection
    candidates = find_barcode_candidates(edges)

    # Sort: barcode-like (AR > 2) and QR-like (AR ~ 1) separately
    barcode_rects = []
    qr_rects = []
    for rect in candidates:
        rw, rh = rect[1]
        if min(rw, rh) < 5:
            continue
        ar = max(rw, rh) / min(rw, rh) if min(rw, rh) > 0 else 999
        if ar > 2.0:
            barcode_rects.append((rect, min(ar / 10.0, 0.9)))
        else:
            qr_rects.append((rect, 0.8))

    # Step 3: QR Finder Pattern based localization
    fp_centers = detect_finder_patterns(binary)
    qr_groups = group_finder_patterns(fp_centers)

    # Step 4: Gradient-based barcode refinement
    grad_map = gradient_orientation_density(enhanced)

    return {
        'barcode_rects': barcode_rects[:10],
        'qr_rects': qr_rects[:10],
        'qr_corners': qr_groups,
        'finder_patterns': fp_centers,
        'gradient_density': grad_map,
        'edges': edges,
    }
