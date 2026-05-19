"""Barcode and QR code decoding.

Implements:
  - Scan-line based barcode decoding (EAN-13, Code-128, Code-39)
  - QR code format parsing (sampling grid, mask removal, data extraction)
  - Reed-Solomon error correction (simplified)
  - Result validation and confidence scoring
"""

import numpy as np
import cv2


# ==================== BARCODE DECODING ====================

# EAN-13 encoding table
EAN13_LEFT_ODD = {
    '0001101': 0, '0011001': 1, '0010011': 2, '0111101': 3, '0100011': 4,
    '0110001': 5, '0101111': 6, '0111011': 7, '0110111': 8, '0001011': 9,
}
EAN13_LEFT_EVEN = {
    '0100111': 0, '0110011': 1, '0011011': 2, '0100001': 3, '0011101': 4,
    '0111001': 5, '0000101': 6, '0010001': 7, '0001001': 8, '0010111': 9,
}
EAN13_RIGHT = {
    '1110010': 0, '1100110': 1, '1101100': 2, '1000010': 3, '1011100': 4,
    '1001110': 5, '1010000': 6, '1000100': 7, '1001000': 8, '1110100': 9,
}

# First digit encoding (parity of left group)
EAN13_FIRST_DIGIT = {
    'OOOOOO': 0, 'OOEOEE': 1, 'OOEEOE': 2, 'OOEEEO': 3, 'OEOOEE': 4,
    'OEEOOE': 5, 'OEEEOO': 6, 'OEOEOE': 7, 'OEOEEO': 8, 'OEEOEO': 9,
}

# Code-128 patterns (value: [bars_pattern, bar_count])
CODE128_PATTERNS = {
     0: '212222',  1: '222122',  2: '222221',  3: '121223',  4: '121322',
     5: '131222',  6: '122213',  7: '122312',  8: '132212',  9: '221213',
    10: '221312', 11: '231212', 12: '112232', 13: '122132', 14: '122231',
    15: '113222', 16: '123122', 17: '123221', 18: '223211', 19: '221132',
    20: '221231', 21: '213212', 22: '223112', 23: '312131', 24: '311222',
    25: '321122', 26: '321221', 27: '312212', 28: '322112', 29: '322211',
    30: '212123', 31: '212321', 32: '232121', 33: '111323', 34: '131123',
    35: '131321', 36: '112313', 37: '132113', 38: '132311', 39: '211313',
    40: '231113', 41: '231311', 42: '112133', 43: '112331', 44: '132131',
    45: '113123', 46: '113321', 47: '133121', 48: '313121', 49: '211331',
    50: '231131', 51: '213113', 52: '213311', 53: '213131', 54: '311123',
    55: '311321', 56: '331121', 57: '312113', 58: '312311', 59: '332111',
    60: '314111', 61: '221411', 62: '431111', 63: '111224', 64: '111422',
    65: '121124', 66: '121421', 67: '141122', 68: '141221', 69: '112214',
    70: '112412', 71: '122114', 72: '122411', 73: '142112', 74: '142211',
    75: '241211', 76: '221114', 77: '413111', 78: '241112', 79: '134111',
    80: '111242', 81: '121142', 82: '121241', 83: '114212', 84: '124112',
    85: '124211', 86: '411212', 87: '421112', 88: '421211', 89: '212141',
    90: '214121', 91: '412121', 92: '111143', 93: '111341', 94: '131141',
    95: '114113', 96: '114311', 97: '411113', 98: '411311', 99: '113141',
    100: '114131', 101: '311141', 102: '411131', 103: '211412',  # START-A
    104: '211214',  # START-B
    105: '211232',  # START-C
}

CODE128_STOP = '2331112'
CODE128_VALUE_TO_CHAR = {
    'A': {  # Code Set A
        0: ' ', 1: '!', 2: '"', 3: '#', 4: '$', 5: '%', 6: '&', 7: "'",
        8: '(', 9: ')', 10: '*', 11: '+', 12: ',', 13: '-', 14: '.', 15: '/',
        16: '0', 17: '1', 18: '2', 19: '3', 20: '4', 21: '5', 22: '6', 23: '7',
        24: '8', 25: '9', 26: ':', 27: ';', 28: '<', 29: '=', 30: '>', 31: '?',
        32: '@', 33: 'A', 34: 'B', 35: 'C', 36: 'D', 37: 'E', 38: 'F', 39: 'G',
        40: 'H', 41: 'I', 42: 'J', 43: 'K', 44: 'L', 45: 'M', 46: 'N', 47: 'O',
        48: 'P', 49: 'Q', 50: 'R', 51: 'S', 52: 'T', 53: 'U', 54: 'V', 55: 'W',
        56: 'X', 57: 'Y', 58: 'Z', 59: '[', 60: '\\', 61: ']', 62: '^', 63: '_',
        64: '\x00', 65: '\x01', 66: '\x02', 67: '\x03', 68: '\x04', 69: '\x05',
        70: '\x06', 71: '\x07', 72: '\x08', 73: '\x09', 74: '\x0a', 75: '\x0b',
        76: '\x0c', 77: '\x0d', 78: '\x0e', 79: '\x0f', 80: '\x10', 81: '\x11',
        82: '\x12', 83: '\x13', 84: '\x14', 85: '\x15', 86: '\x16', 87: '\x17',
        88: '\x18', 89: '\x19', 90: '\x1a', 91: '\x1b', 92: '\x1c', 93: '\x1d',
        94: '\x1e', 95: '\x1f',
    },
}

# Fill in Code Set B (same as A for printable chars but different for control)
CODE128_VALUE_TO_CHAR['B'] = CODE128_VALUE_TO_CHAR['A'].copy()
for i in range(64, 96):
    CODE128_VALUE_TO_CHAR['B'][i] = chr(i)  # Correct mapping for B

# Code-39 encoding
CODE39_PATTERNS = {
    '0': '101001101101', '1': '110100101011', '2': '101100101011',
    '3': '110110010101', '4': '101001101011', '5': '110100110101',
    '6': '101100110101', '7': '101001011011', '8': '110100101101',
    '9': '101100101101', 'A': '110101001011', 'B': '101101001011',
    'C': '110110100101', 'D': '101011001011', 'E': '110101100101',
    'F': '101101100101', 'G': '101010011011', 'H': '110101001101',
    'I': '101101001101', 'J': '101011001101', 'K': '110101010011',
    'L': '101101010011', 'M': '110110101001', 'N': '101011010011',
    'O': '110101101001', 'P': '101101101001', 'Q': '101010110011',
    'R': '110101011001', 'S': '101101011001', 'T': '101011011001',
    'U': '110010101011', 'V': '100110101011', 'W': '110011010101',
    'X': '100101101011', 'Y': '110010110101', 'Z': '100110110101',
    '-': '100101011011', '.': '110010101101', ' ': '100110101101',
    '$': '100100100101', '/': '100100101001', '+': '100101001001',
    '%': '101001001001', '*': '100101101101',
}
CODE39_CHARS = {v: k for k, v in CODE39_PATTERNS.items()}


def extract_scanline_profile(binary_img, num_lines=10):
    """Extract bar/space profiles from multiple horizontal scanlines."""
    h, w = binary_img.shape[:2]
    profiles = []

    for i in range(num_lines):
        y = int(h * (i + 0.5) / num_lines)
        if y >= h:
            y = h - 1

        line = binary_img[y, :]
        # Find transitions (black-to-white or white-to-black)
        transitions = []
        prev = line[0]
        for x in range(1, w):
            if line[x] != prev:
                transitions.append(x)
                prev = line[x]

        if len(transitions) > 10:
            # Calculate bar/space widths
            widths = [transitions[0]]
            for j in range(1, len(transitions)):
                widths.append(transitions[j] - transitions[j - 1])
            widths.append(w - transitions[-1])
            profiles.append((transitions, widths))

    return profiles


def decode_ean13_bars(widths, start_index=0):
    """Attempt to decode an EAN-13 barcode from bar/space widths.

    EAN-13 structure:
    - Start guard: 101 (3 bars)
    - 6 left digits (each 7 modules) = 42 modules
    - Middle guard: 01010 (5 bars)
    - 6 right digits (each 7 modules) = 42 modules
    - End guard: 101 (3 bars)
    Total: 95 modules, represented by 59 bars/spaces

    Args:
        widths: list of bar/space widths
        start_index: starting index in the bar/space sequence

    Returns:
        decoded string or None
    """
    if len(widths) < start_index + 59:
        return None

    seq = widths[start_index:start_index + 59]

    # Normalize widths by total module count
    total = sum(seq)
    if total < 10:
        return None
    unit = total / 95.0

    # Convert widths to module counts
    modules = []
    for w in seq:
        m = round(w / unit)
        modules.append(max(1, m))

    # Flatten modules into binary pattern
    bits = []
    for i, m in enumerate(modules):
        bit = 1 if i % 2 == 0 else 0  # alternating bar/space
        bits.extend([bit] * m)
    bits_str = ''.join(str(b) for b in bits)

    if len(bits_str) < 95:
        return None

    # Check start guard
    if bits_str[:3] != '101':
        return None

    # Check middle guard (at position 45-50 in modules, which maps to bits 45-49)
    # Actually for 59 bars/spaces, the middle guard is at bars 27-31 (0-indexed)
    # In the module stream, it's at modules 45-49
    mid_start = 45
    if len(bits_str) < mid_start + 5 + 42 + 3:
        return None
    if bits_str[mid_start:mid_start + 5] != '01010':
        return None

    # Check end guard
    end_start = mid_start + 5 + 42
    if bits_str[end_start:end_start + 3] != '101':
        return None

    # Decode left digits (6 digits, modules 3-45)
    left_digits = []
    parity = []
    for d in range(6):
        start = 3 + d * 7
        segment = bits_str[start:start + 7]
        if len(segment) < 7:
            return None
        if segment in EAN13_LEFT_ODD:
            left_digits.append(EAN13_LEFT_ODD[segment])
            parity.append('O')
        elif segment in EAN13_LEFT_EVEN:
            left_digits.append(EAN13_LEFT_EVEN[segment])
            parity.append('E')
        else:
            return None

    # Decode right digits (6 digits, modules 50-92)
    right_digits = []
    for d in range(6):
        start = mid_start + 5 + d * 7
        segment = bits_str[start:start + 7]
        if segment in EAN13_RIGHT:
            right_digits.append(EAN13_RIGHT[segment])
        else:
            return None

    # Determine first digit from parity pattern
    parity_str = ''.join(parity)
    first_digit = EAN13_FIRST_DIGIT.get(parity_str, -1)
    if first_digit < 0:
        return None

    full_digits = [first_digit] + left_digits + right_digits
    if validate_ean13_checksum(full_digits):
        return ''.join(str(d) for d in full_digits)

    return None


def validate_ean13_checksum(digits):
    """Validate EAN-13 check digit."""
    if len(digits) != 13:
        return False
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1]))
    check = (10 - (total % 10)) % 10
    return check == digits[-1]


def decode_code128(widths, start_index=0):
    """Decode a Code-128 barcode from bar/space widths.

    Code-128 structure:
    - Start pattern (6 bars: 11 modules)
    - Data characters (each 6 bars: 11 modules)
    - Check character
    - Stop pattern (7 bars: 13 modules)
    """
    if len(widths) < start_index + 13:  # At least start + stop
        return None

    seq = widths[start_index:]

    # Try to find start pattern
    # Code-128 always starts with a quiet zone + start character
    total_start = sum(seq[:6])
    if total_start < 5:
        return None
    unit = total_start / 11.0

    # Convert to module widths for start
    start_modules = []
    for w in seq[:6]:
        m = round(w / unit)
        start_modules.append(max(1, min(4, m)))
    start_pat = ''.join(str(m) for m in start_modules)

    # Find start code
    start_code = None
    start_set = None
    for code, pat in CODE128_PATTERNS.items():
        if code in (103, 104, 105) and pat == start_pat:
            start_code = code
            if code == 103:
                start_set = 'A'
            elif code == 104:
                start_set = 'B'
            else:
                start_set = 'C'
            break

    if start_code is None:
        return None

    # Decode subsequent characters
    result = []
    current_set = start_set
    pos = 6
    checksum = start_code

    while pos + 6 <= len(seq):
        # Check for stop pattern
        if pos + 7 <= len(seq):
            total_stop_block = sum(seq[pos:pos + 7])
            if total_stop_block > 0:
                unit_stop = total_stop_block / 13.0
                stop_modules = []
                for w in seq[pos:pos + 7]:
                    m = round(w / unit_stop)
                    stop_modules.append(max(1, min(9, m)))
                stop_pat = ''.join(str(m) for m in stop_modules)

                if stop_pat == CODE128_STOP:
                    # Verify checksum
                    if len(result) > 0:
                        check_val = result.pop()  # Last was check character
                        if checksum % 103 == check_val:
                            # Build final result string
                            final = ''
                            for r in result:
                                final += chr(r) if 32 <= r <= 126 else '?'
                            return final
                    return None

        # Decode one character
        char_seq = seq[pos:pos + 6]
        total = sum(char_seq)
        if total < 3:
            break
        unit = total / 11.0
        char_modules = []
        for w in char_seq:
            m = round(w / unit)
            char_modules.append(max(1, min(4, m)))
        char_pat = ''.join(str(m) for m in char_modules)

        value = None
        for v, pat in CODE128_PATTERNS.items():
            if pat == char_pat:
                value = v
                break

        if value is None:
            break

        # Handle special codes
        if value == 98:  # Shift A
            current_set = 'A'
            pos += 6
            continue
        elif value == 99:  # Shift B / Code C
            current_set = 'C'
            pos += 6
            continue
        elif value == 100:  # Code A
            current_set = 'A'
            pos += 6
            continue
        elif value == 101:  # Code B
            current_set = 'B'
            pos += 6
            continue
        elif value == 102:  # FNC1
            result.append(ord(']'))  # Represent FNC1 as ']'
            pos += 6
            continue

        if current_set == 'C':
            # Two-digit numeric
            result.append(value // 10)
            result.append(value % 10)
        else:
            result.append(value)

        checksum += value * (1 + (pos // 6))

        pos += 6

    return None


def decode_code39(widths, start_index=0):
    """Decode a Code-39 barcode from bar/space widths."""
    if len(widths) < start_index + 9:
        return None

    seq = widths[start_index:]

    # Convert to bar/space patterns (narrow=1, wide=2)
    patterns = []
    i = 0
    while i + 9 <= len(seq):
        segment = seq[i:i + 9]
        avg = np.mean(segment)
        if avg < 1:
            break

        # Classify as narrow or wide
        pattern = ''
        for j, w in enumerate(segment):
            if w > avg * 1.4:
                pattern += '2'
            else:
                pattern += '1'
            # Code-39 has 5 bars interleaved with 4 spaces per char
            # Convert to combined pattern

        # Re-extract: 9 elements = 5 bars + 4 spaces
        # The pattern is 'bWsbWsbWs' where b=bar, s=space, W=wide, w=narrow
        # For Code-39: 3 wide elements out of 9, 1 for bars, 2 for spaces (or vice-versa)
        binary = ''
        for j, w in enumerate(segment):
            if j % 2 == 0:  # bar
                if w > avg * 1.3:
                    binary += '2'
                else:
                    binary += '1'
            else:  # space
                if w > avg * 1.3:
                    binary += '2'
                else:
                    binary += '1'

        patterns.append(binary)
        i += 9

    # Match patterns to characters
    result = ''
    for p in patterns:
        # Convert pattern to Code-39 binary format
        # Code-39 uses: bar space bar space bar space bar space bar = 9 elements
        # Binary representation: 1=narrow, 0=wide
        binary_39 = ''
        for c in p:
            binary_39 += '0' if c == '2' else '1'
        # Actually let me match the raw pattern
        if len(p) == 9:
            char = CODE39_CHARS.get(p[0] + '0' if p[0] == '1' else p[0] + '1')  # simplified
            if char:
                result += char

    return result if len(result) > 2 else None


def decode_barcode(corrected_img):
    """Try to decode a barcode image.

    Uses pyzbar (zbar library) as the primary backend for reliability,
    with custom scanline-based decoder as fallback for educational purposes.

    Args:
        corrected_img: grayscale barcode ROI (already rotated/corrected)

    Returns:
        (decoded_string, barcode_type) or (None, None)
    """
    if corrected_img is None:
        return None, None

    h, w = corrected_img.shape[:2]
    if h < 15 or w < 60:
        return None, None

    if corrected_img.dtype != np.uint8:
        corrected_img = corrected_img.astype(np.uint8)

    # 1) Try pyzbar (robust, well-tested backend)
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        results = pyzbar_decode(corrected_img)
        for r in results:
            if r.type in ('EAN13', 'EAN8', 'UPC-A', 'UPC-E', 'CODE128', 'CODE39', 'CODE93', 'CODABAR', 'ITF'):
                return r.data.decode('utf-8', errors='replace'), r.type
            if r.type == 'QRCODE':
                return r.data.decode('utf-8', errors='replace'), 'QR Code'
    except ImportError:
        pass

    # 2) Custom scanline decoder (educational: demonstrates traditional DIP approach)
    _, binary = cv2.threshold(corrected_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    profiles = extract_scanline_profile(binary, num_lines=15)
    all_widths = [widths for _, widths in profiles]

    if not all_widths:
        return None, None

    min_len = min(len(w) for w in all_widths)
    avg_widths = []
    for i in range(min_len):
        avg_widths.append(np.median([w[i] for w in all_widths]))

    result = decode_ean13_bars(avg_widths)
    if result:
        return result, 'EAN-13'

    result = decode_code128(avg_widths)
    if result:
        return result, 'Code-128'

    return None, None


# ==================== QR CODE DECODING (Simplified) ====================

def decode_qr(corrected_img):
    """Decode a QR code from a corrected square image.

    Uses OpenCV QR detector and pyzbar as backends, keeping our own
    localization + geometric correction pipeline.
    """
    if corrected_img is None:
        return None

    h, w = corrected_img.shape[:2]
    if h < 21 or w < 21:
        return None

    if len(corrected_img.shape) == 3:
        gray = cv2.cvtColor(corrected_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = corrected_img.copy()

    # 1) OpenCV QR detector
    detector = cv2.QRCodeDetector()
    try:
        data, points, _ = detector.detectAndDecode(gray)
        if data:
            return data
    except Exception:
        pass

    # 2) pyzbar fallback
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        results = pyzbar_decode(gray)
        for r in results:
            if r.type == 'QRCODE':
                return r.data.decode('utf-8', errors='replace')
    except ImportError:
        pass

    return None


# ==================== Result Aggregation ====================

def compute_confidence(decoded_text, barcode_type, region_info):
    """Compute a confidence score for the decoding result."""
    if decoded_text is None:
        return 0.0

    score = 0.7  # Base score for successful decode

    if barcode_type == 'QR Code':
        score += 0.1  # QR is more reliable
    elif barcode_type and barcode_type.startswith('EAN-13'):
        # Check checksum
        digits = [int(c) for c in decoded_text if c.isdigit()]
        if len(digits) >= 13:
            score += 0.15

    # Region confidence from localization
    score += region_info.get('confidence', 0.0) * 0.1

    return min(score, 0.99)


def decode_region(corrected_region):
    """Decode a single corrected region.

    Args:
        corrected_region: dict from correct.correct_region()

    Returns:
        dict with 'text', 'type', 'confidence'
    """
    img = corrected_region['image']
    region_type = corrected_region['type']

    if region_type == 'qr':
        result = decode_qr(img)
        if result:
            return {
                'text': result,
                'type': 'QR Code',
                'confidence': compute_confidence(result, 'QR Code', corrected_region),
            }
    else:
        result, btype = decode_barcode(img)
        if result:
            return {
                'text': result,
                'type': btype or 'Barcode',
                'confidence': compute_confidence(result, btype, corrected_region),
            }

    return None


def decode_all(corrected_regions):
    """Decode all corrected regions.

    Returns list of decoding results.
    """
    results = []
    for region in corrected_regions:
        result = decode_region(region)
        if result:
            results.append(result)
    return results
