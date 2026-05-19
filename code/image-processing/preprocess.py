"""Image preprocessing for barcode/QR code recognition.

Uses traditional digital image processing techniques:
grayscale conversion, Gaussian filtering, adaptive thresholding,
and morphological operations.
"""

import cv2
import numpy as np


def to_grayscale(img):
    """Convert image to grayscale using weighted average: Gray = 0.299R + 0.587G + 0.114B."""
    if img is None:
        raise ValueError("Input image is None")
    if len(img.shape) == 2:
        return img.copy()
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.copy()


def gaussian_filter(img, kernel_size=5, sigma=1.5):
    """Apply Gaussian blur to reduce noise."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), sigma)


def median_filter(img, kernel_size=3):
    """Apply median filter — effective for salt-and-pepper noise."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.medianBlur(img, kernel_size)


def otsu_threshold(img):
    """Global Otsu thresholding — best for uniform lighting."""
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def adaptive_threshold(img, block_size=25, c=8):
    """Local adaptive thresholding — handles uneven lighting.

    block_size: must be odd, ~ 1/10 to 1/15 of image width
    c: constant subtracted from the mean
    """
    if block_size % 2 == 0:
        block_size += 1
    return cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size, c)


def adaptive_threshold_mean(img, block_size=25, c=8):
    """Adaptive thresholding using mean (instead of Gaussian)."""
    if block_size % 2 == 0:
        block_size += 1
    return cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        block_size, c)


def clahe_enhance(img, clip_limit=2.0, tile_grid_size=(8, 8)):
    """Contrast Limited Adaptive Histogram Equalization — enhances low-contrast images."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(img)


def morph_open(img, kernel_size=3):
    """Opening: erosion then dilation — removes small noise."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)


def morph_close(img, kernel_size=3):
    """Closing: dilation then erosion — fills small gaps."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)


def morph_dilate(img, kernel_size=5, iterations=1):
    """Dilate — expands bright regions."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.dilate(img, kernel, iterations=iterations)


def morph_erode(img, kernel_size=3, iterations=1):
    """Erode — shrinks bright regions."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.erode(img, kernel, iterations=iterations)


def preprocess(img, adaptive=True, block_size=25, c=8):
    """Run the full preprocessing pipeline.

    Returns:
        gray: grayscale image
        binary: binarized image
        enhanced: CLAHE-enhanced image (for edge detection)
    """
    gray = to_grayscale(img)
    enhanced = clahe_enhance(gray)
    denoised = gaussian_filter(gray, sigma=1.2)

    if adaptive:
        binary = adaptive_threshold(denoised, block_size=block_size, c=c)
    else:
        binary = otsu_threshold(denoised)

    return gray, binary, enhanced
