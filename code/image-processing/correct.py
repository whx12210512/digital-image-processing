"""Geometric correction for barcode/QR code images.

Handles rotation correction (Hough transform for barcodes,
Finder Pattern geometry for QR) and perspective correction.
"""

import cv2
import numpy as np
from math import sin, cos, radians


# ---------- Rotation Correction ----------

def correct_rotation(img, angle, center=None):
    """Rotate image by 'angle' degrees around 'center'."""
    h, w = img.shape[:2]
    if center is None:
        center = (w // 2, h // 2)

    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos_val = abs(rot_mat[0, 0])
    sin_val = abs(rot_mat[0, 1])

    new_w = int(h * sin_val + w * cos_val)
    new_h = int(h * cos_val + w * sin_val)

    rot_mat[0, 2] += (new_w / 2) - center[0]
    rot_mat[1, 2] += (new_h / 2) - center[1]

    return cv2.warpAffine(img, rot_mat, (new_w, new_h),
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def detect_barcode_angle(edge_img, rect):
    """Detect barcode rotation angle using Hough line transform
    on the barcode region.

    Returns angle in degrees (positive = clockwise rotation needed).
    """
    # Extract region around the barcode
    center, size, det_angle = rect
    bw, bh = size

    # Rotate the edge region to upright, then use Hough
    rot = cv2.getRotationMatrix2D(center, det_angle, 1.0)
    h, w = edge_img.shape[:2]
    rotated_edges = cv2.warpAffine(edge_img, rot, (w, h))

    # Crop to barcode region
    cx, cy = int(center[0]), int(center[1])
    bx, by = int(bw), int(bh)
    x1 = max(0, cx - bx // 2)
    x2 = min(w, cx + bx // 2)
    y1 = max(0, cy - by // 2)
    y2 = min(h, cy + by // 2)

    if x2 <= x1 or y2 <= y1:
        return det_angle

    roi = rotated_edges[y1:y2, x1:x2]

    # Hough line transform
    lines = cv2.HoughLines(roi, 1, np.pi / 180, threshold=30)
    if lines is None or len(lines) < 3:
        return det_angle

    # Find dominant angle
    angles = []
    for line in lines:
        rho, theta = line[0]
        angle = np.degrees(theta)
        # Normalize to [0, 180)
        angle = angle % 180
        if angle > 90:
            angle -= 180
        angles.append(angle)

    if not angles:
        return det_angle

    # Use median angle for robustness
    median_angle = np.median(angles)
    return median_angle


def correct_barcode_rotation(gray_img, rect):
    """Apply rotation correction to a detected barcode region.

    Returns: (corrected_roi, corrected_rect)
    """
    center, size, angle = rect
    w, h = size

    # Ensure rectangle is horizontal (width > height)
    if h > w:
        angle += 90
        w, h = h, w

    # Normalize angle
    angle = angle % 180
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90

    # Extract and rotate the region
    src_pts = cv2.boxPoints(rect)
    src_pts = np.int32(src_pts)

    # Get the bounding rect and extract
    x, y, rw, rh = cv2.boundingRect(src_pts)
    x, y = max(0, x), max(0, y)
    roi = gray_img[y:y + rh, x:x + rw].copy()

    h_roi, w_roi = roi.shape[:2]
    if h_roi < 2 or w_roi < 2:
        return None, None

    rot_mat = cv2.getRotationMatrix2D((w_roi // 2, h_roi // 2), angle, 1.0)
    corrected = cv2.warpAffine(roi, rot_mat, (w_roi, h_roi),
                               borderMode=cv2.BORDER_CONSTANT, borderValue=255)

    return corrected, angle


# ---------- Perspective Correction ----------

def four_point_transform(img, src_pts, dst_size=None):
    """Apply perspective transform to warp a quadrilateral region to a rectangle.

    Args:
        img: source image
        src_pts: 4 corner points (np.float32, shape 4x2)
        dst_size: (width, height) of output. If None, computed from src.

    Returns:
        warped image
    """
    if dst_size is None:
        # Compute output size from source
        (tl, tr, br, bl) = src_pts
        width_top = np.hypot(br[0] - bl[0], br[1] - bl[1])
        width_bottom = np.hypot(tr[0] - tl[0], tr[1] - tl[1])
        max_width = max(int(width_top), int(width_bottom))

        height_left = np.hypot(tr[0] - br[0], tr[1] - br[1])
        height_right = np.hypot(tl[0] - bl[0], tl[1] - bl[1])
        max_height = max(int(height_left), int(height_right))

        dst_size = (max_width, max_height)

    dst_pts = np.float32([
        [0, 0],
        [dst_size[0] - 1, 0],
        [dst_size[0] - 1, dst_size[1] - 1],
        [0, dst_size[1] - 1],
    ])

    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(img, matrix, dst_size,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    return warped


def correct_qr_perspective(img, qr_corners, target_size=300):
    """Apply perspective correction to a QR code region.

    Args:
        img: source image (grayscale or color)
        qr_corners: 4 ordered corners (TL, TR, BR, BL)
        target_size: output square size

    Returns:
        warped QR code image (square)
    """
    if qr_corners is None or len(qr_corners) != 4:
        return None
    return four_point_transform(img, qr_corners, (target_size, target_size))


def correct_barcode_perspective(img, barcode_rect, target_height=120):
    """Extract a barcode region using its rotated rect, warping it horizontal.

    Uses a simpler bounding-box + rotation approach for robustness.
    """
    center, size, angle = barcode_rect
    rw, rh = size

    # Normalize angle: ensure barcode is roughly horizontal
    if rw < rh:
        angle += 90
        rw, rh = rh, rw

    # Keep angle in [-45, 45]
    angle = angle % 180
    if angle > 90:
        angle -= 180
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90

    h_img, w_img = img.shape[:2]

    # Build rotation matrix around barcode center
    rot_mat = cv2.getRotationMatrix2D(tuple(center), angle, 1.0)
    rotated = cv2.warpAffine(img, rot_mat, (w_img, h_img),
                             borderMode=cv2.BORDER_CONSTANT, borderValue=255)

    # After rotation, the barcode center is at the same position
    cx, cy = int(center[0]), int(center[1])
    half_w = int(rw * 0.65)
    # Barcode bars are thin — expand vertically 3x to capture quiet zones and text
    half_h = max(int(rh * 2.5), 40)
    if half_w < 60:
        half_w = 80

    x1 = max(0, cx - half_w)
    x2 = min(w_img, cx + half_w)
    y1 = max(0, cy - half_h)
    y2 = min(h_img, cy + half_h)

    if x2 <= x1 or y2 <= y1:
        return None

    roi = rotated[y1:y2, x1:x2]
    return roi


def order_points(pts):
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # TL: smallest sum
    rect[2] = pts[np.argmax(s)]  # BR: largest sum
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # TR: smallest diff
    rect[3] = pts[np.argmax(diff)]  # BL: largest diff
    return rect


# ---------- Composite Correction ----------

def correct_region(img, localization_result):
    """Apply geometric correction to all detected regions.

    Returns:
        corrected_regions: list of dicts with 'image', 'type', 'corners'
    """
    results = []
    gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Correct barcode regions (elongated)
    for rect, conf in localization_result.get('barcode_rects', []):
        try:
            corrected_img = correct_barcode_perspective(gray, rect)
            if corrected_img is not None:
                results.append({
                    'image': corrected_img,
                    'type': 'barcode',
                    'rect': rect,
                    'confidence': conf,
                })
        except Exception:
            continue

    # Correct QR code regions from finder pattern grouping (precise)
    for corners, mod_size in localization_result.get('qr_corners', []):
        try:
            corrected_img = correct_qr_perspective(gray, corners)
            if corrected_img is not None:
                results.append({
                    'image': corrected_img,
                    'type': 'qr',
                    'corners': corners,
                    'module_size': mod_size,
                    'confidence': 0.90,
                })
        except Exception:
            continue

    # Fallback: correct QR-like regions from coarse detection
    for rect, conf in localization_result.get('qr_rects', []):
        try:
            # Expand the rotated rect by a margin to handle rotation
            center, size, angle = rect
            rw, rh = size
            # Add 25% margin to ensure full QR code is captured (especially rotated ones)
            expanded_size = (max(rw, rh) * 1.25, max(rw, rh) * 1.25)
            expanded_rect = (center, expanded_size, angle)
            src_pts = cv2.boxPoints(expanded_rect)
            src_pts = order_points(src_pts)
            out_size = int(max(rw, rh) * 1.25)
            corrected_img = four_point_transform(gray, src_pts, (out_size, out_size))
            if corrected_img is not None and corrected_img.size > 100:
                results.append({
                    'image': corrected_img,
                    'type': 'qr',
                    'rect': rect,
                    'confidence': conf * 0.7,
                })
        except Exception:
            continue

    return results
