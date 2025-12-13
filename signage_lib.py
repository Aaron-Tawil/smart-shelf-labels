
import math
import os
import re
import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.units import cm
from io import BytesIO
import json
from google import genai
from google.genai import types
import copy
from google.cloud import firestore

from env_loader import load_env
load_env() # Load environment variables for local development

# --- LLM Configuration ---
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
        # We will use this client for generation calls
        # model object isn't persisted the same way in new SDK, just the client
        model_name = 'gemini-flash-latest' # Original model requested
        
        # Configure Search Tool
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        generate_config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )
        
        print(f"Selected Model: {model_name} with Google Search (New SDK)")
        
    except Exception as e:
        print(f"Error: Could not initialize Gemini Client: {e}. LLM features will be disabled.")
        client = None
else:
    client = None
    print("Warning: GEMINI_API_KEY environment variable not set. LLM features will be disabled.")


# --- Constants & Config ---
SIGN_WIDTH_CM = 10.2
SIGN_HEIGHT_CM = 3.6
SIGN_WIDTH = SIGN_WIDTH_CM * cm
SIGN_HEIGHT = SIGN_HEIGHT_CM * cm

# Colors
BG_COLOR = HexColor('#254778')
PATTERN_COLOR = HexColor('#1e3a61')
GOLD_START = HexColor('#C26F19')
GOLD_MID = HexColor('#F6B532')
GOLD_END = HexColor('#C26F19')
WHITE_COLOR = white
TEXT_COLOR = HexColor('#1A2236')
SALE_COLOR = HexColor('#D32F2F')

# Font Configuration
FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
FONT_REGULAR = 'Heebo-Regular'
FONT_BOLD = 'Heebo-Bold'
FONT_EXTRA_BOLD = 'Heebo-ExtraBold'

def register_fonts():
    """Registers fonts if available, otherwise falls back to Helvetica."""
    try:
        # Check if font files exist before registering
        reg_path = os.path.join(FONTS_DIR, 'Heebo-Regular.ttf')
        bold_path = os.path.join(FONTS_DIR, 'Heebo-Bold.ttf')
        extra_path = os.path.join(FONTS_DIR, 'Heebo-ExtraBold.ttf')
        if not all(os.path.exists(p) for p in [reg_path, bold_path, extra_path]):
             print(f"Warning: Font files not found in {FONTS_DIR}. Using defaults.")
             return False
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, reg_path))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, bold_path))
        pdfmetrics.registerFont(TTFont(FONT_EXTRA_BOLD, extra_path))
        return True
    except Exception as e:
        print(f"Warning: Could not register Heebo fonts: {e}. Using defaults.")
        return False

# --- Drawing Helpers ---
def draw_diagonal_hatch(c, x, y, width, height):
    """Simulates the diagonal hatch pattern."""
    c.saveState()
    path = c.beginPath()
    path.rect(x, y, width, height)
    c.clipPath(path, stroke=0)
    c.setStrokeColor(PATTERN_COLOR)
    c.setLineWidth(0.5)
    step = 3
    max_dim = width + height
    start_offset = -height
    end_offset = width
    for i in range(int(start_offset), int(end_offset), step):
        c.line(x + i, y, x + i + max_dim, y + max_dim)
    c.restoreState()

def draw_gold_gradient_rect(c, x, y, width, height):
    """Draws a rectangle with a linear gradient: Dark -> Light -> Dark"""
    c.saveState()
    path = c.beginPath()
    path.rect(x, y, width, height)
    c.clipPath(path, stroke=0)
    steps = 50
    step_width = width / steps
    for i in range(steps):
        ratio = i / (steps - 1)
        if ratio < 0.5:
            local_r, c1, c2 = ratio * 2, GOLD_START, GOLD_MID
        else:
            local_r, c1, c2 = (ratio - 0.5) * 2, GOLD_MID, GOLD_END
        r, g, b = (c1.red + (c2.red - c1.red) * local_r,
                   c1.green + (c2.green - c1.green) * local_r,
                   c1.blue + (c2.blue - c1.blue) * local_r)
        c.setFillColor(Color(r, g, b))
        c.rect(x + i * step_width, y, step_width + 0.5, height, fill=1, stroke=0)
    c.restoreState()

def reshape_text(text):
    if not text: return ""
    return get_display(arabic_reshaper.reshape(str(text)))

def draw_wrapped_text(c, text, x, y, width, height, font_name, font_size, line_height=14):
    """Draws text wrapped within a box, centered vertically and horizontally."""
    words = text.split()
    lines = []
    current_line = []
    c.setFont(font_name, font_size)
    for word in words:
        test_line = " ".join(current_line + [word])
        if c.stringWidth(reshape_text(test_line), font_name, font_size) <= width:
            current_line.append(word)
        else:
            if current_line: lines.append(" ".join(current_line))
            current_line = [word]
    if current_line: lines.append(" ".join(current_line))
    max_lines = int(height / line_height)
    if len(lines) > max_lines: lines = lines[:max_lines]
    total_text_height = len(lines) * line_height
    # Start Y (Top of text block)
    start_y = (y + height) - (height - total_text_height) / 2 - line_height + 3 if total_text_height < height else (y + height) - line_height
    for i, line in enumerate(lines):
        c.drawCentredString(x + (width / 2), start_y - (i * line_height), reshape_text(line))

def draw_price_styled(c, x, y, price_val, font_main, main_size, color, stroke_color=None, stroke_width=0):
    """Draws price with smaller shekel and decimals. Optional strikethrough."""
    try: price_float = float(price_val)
    except: price_float = 0.0
    price_str = f"{price_float:.2f}"
    main_digits, decimal_part = price_str.split('.') if '.' in price_str else (price_str, "")
    if decimal_part: decimal_part = f".{decimal_part}"
    sub_size = main_size * 0.5
    c.setFillColor(color)
    # Calculate widths
    c.setFont(FONT_REGULAR, sub_size)
    w_shekel = c.stringWidth("₪", FONT_REGULAR, sub_size)
    w_dec = c.stringWidth(decimal_part, font_main, sub_size)
    c.setFont(font_main, main_size)
    w_main = c.stringWidth(main_digits, font_main, main_size)
    gap = 2
    total_width = w_shekel + gap + w_main + gap + w_dec
    # Draw starting at x
    cur_x = x
    # Shekel
    c.setFont(FONT_REGULAR, sub_size)
    c.drawString(cur_x, y, "₪")
    cur_x += w_shekel + gap
    # Main
    c.setFont(font_main, main_size)
    c.drawString(cur_x, y, main_digits)
    cur_x += w_main + gap
    # Decimals
    c.setFont(font_main, sub_size)
    c.drawString(cur_x, y, decimal_part)
    # Strikethrough
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)
        mid_y = y + (main_size * 0.35)
        c.line(x - 2, mid_y + (main_size * 0.3), x + total_width + 2, mid_y - (main_size * 0.3))
    return total_width

# --- Sign Drawing ---
def draw_discount_sign(c, x, y, data):
    """Draws a sign with a special discount design."""
    f_bold, f_extra, f_reg = FONT_BOLD, FONT_EXTRA_BOLD, FONT_REGULAR
    # 1. Background (Standard)
    c.setFillColor(BG_COLOR)
    c.rect(x, y, SIGN_WIDTH, SIGN_HEIGHT, fill=1, stroke=0)
    draw_diagonal_hatch(c, x, y, SIGN_WIDTH, SIGN_HEIGHT)
    
    # 3. White Box (Right) - Same as standard
    scale = SIGN_WIDTH / 102.0
    wx, wy, ww, wh = x + (66 * scale), y + SIGN_HEIGHT - (3 * scale) - (30 * scale), 34 * scale, 30 * scale
    c.setFillColor(WHITE_COLOR)
    c.roundRect(wx, wy, ww, wh, 0, fill=1, stroke=0)
    
    # Product Info (Right)
    box_center_x = wx + (ww / 2)
    c.setFillColor(TEXT_COLOR)
    c.setFont(f_reg, 8)
    c.drawCentredString(box_center_x, wy + 5, str(data.get('barcode', '')))
    text_area_y, text_area_h = wy + 15, wh - 15 - 2
    draw_wrapped_text(c, str(data.get('name', '')), wx, text_area_y, ww - 4, text_area_h, f_bold, 12)
    
    # 4. Price Area (Left)
    price_val, prev_price_val = data.get('price', 0), data.get('prev_price', 0)
    current_price_y, current_price_x = y + 1.5 * cm, x + 1.2 * cm
    
    # Gold Strip and Previous Price (Crossed Out)
    if prev_price_val:
        # Gold Strip
        strip_y, strip_h, strip_w, strip_x = y + 1.1 * cm, 0.1 * cm, 60 * scale, x + (2 * scale)
        draw_gold_gradient_rect(c, strip_x, strip_y, strip_w, strip_h)
        # Previous Price
        prev_price_y, prev_price_x = y + 0.5 * cm, x + 2.0 * cm
        draw_price_styled(c, prev_price_x, prev_price_y, prev_price_val, f_bold, 14, HexColor('#B0BEC5'), stroke_color=SALE_COLOR, stroke_width=1.5)
        draw_price_styled(c, current_price_x, current_price_y, price_val, f_extra, 40, white)
    else:
        draw_price_styled(c, current_price_x - 10, current_price_y - 10, price_val, f_extra, 45, white)
        # No previous price: Draw Top and Bottom Gold Stripes (Standard Style)
        gw, gh = 60 * scale, 1 * scale
        draw_gold_gradient_rect(c, x + (2 * scale), y + SIGN_HEIGHT - (3 * scale), gw, gh)
        draw_gold_gradient_rect(c, x + (2 * scale), y + SIGN_HEIGHT - (34 * scale), gw, gh)

    # 2. "Sale" Ribbon (Diagonal Band)
    c.saveState()
    tl_x, tl_y = x, y + SIGN_HEIGHT
    d_in, d_out = 1 * cm, 1 * cm + (1 * cm * 1.414)
    path = c.beginPath(); path.moveTo(tl_x, tl_y - d_in); path.lineTo(tl_x, tl_y - d_out); path.lineTo(tl_x + d_out, tl_y); path.lineTo(tl_x + d_in, tl_y); path.close()
    c.setFillColor(SALE_COLOR); c.drawPath(path, fill=1, stroke=0)
    # Text "מבצע!"
    cx, cy = tl_x + ((d_in + d_out) / 4), tl_y - ((d_in + d_out) / 4)
    c.translate(cx, cy); c.rotate(45); c.setFillColor(white); c.setFont(f_reg, 20); c.drawCentredString(0, -7, reshape_text("מבצע!"))
    c.restoreState()

def draw_sign(c, x, y, data, use_heebo=True):
    """Draws a single sign at (x, y)."""
    f_bold, f_extra, f_reg = (FONT_BOLD, FONT_EXTRA_BOLD, FONT_REGULAR) if use_heebo else ('Helvetica-Bold', 'Helvetica-Bold', 'Helvetica')
    # 1. Background
    c.setFillColor(BG_COLOR); c.rect(x, y, SIGN_WIDTH, SIGN_HEIGHT, fill=1, stroke=0)
    # 2. Pattern Overlay
    draw_diagonal_hatch(c, x, y, SIGN_WIDTH, SIGN_HEIGHT)
    # 3. Gold Stripes
    scale = SIGN_WIDTH / 102.0
    to_rl = lambda svg_x, svg_y, svg_h=0: (x + (svg_x * scale), y + SIGN_HEIGHT - (svg_y * scale) - (svg_h * scale))
    gw, gh = 60 * scale, 1 * scale
    draw_gold_gradient_rect(c, *to_rl(2, 2, 1), gw, gh); draw_gold_gradient_rect(c, *to_rl(2, 33, 1), gw, gh)
    # 4. White Box (Right)
    wx, wy, ww, wh = *to_rl(66, 3, 30), 34 * scale, 30 * scale
    c.setFillColor(WHITE_COLOR); c.roundRect(wx, wy, ww, wh, 0, fill=1, stroke=0)
    # --- Content: Price (Left) ---
    try: price_float = float(data.get('price', 0))
    except (ValueError, TypeError): price_float = 0.0
    main_digits, decimal_part = f"{price_float:.2f}".split('.'); decimal_part = f".{decimal_part}"
    base_font_size, sub_size = 50, 25
    price_center_x, price_center_y = x + (33 * scale), y + (SIGN_HEIGHT / 2) - (base_font_size * 0.35)
    c.setFillColor(WHITE_COLOR); c.setFont(f_extra, base_font_size)
    w_main = c.stringWidth(main_digits, f_extra, base_font_size)
    c.setFont(f_extra, sub_size); w_dec = c.stringWidth(decimal_part, f_extra, sub_size)
    # Shekel with Regular Font
    c.setFont(f_reg, sub_size); w_shekel = c.stringWidth("₪", f_reg, sub_size)
    gap = 2; total_w = w_shekel + gap + w_main + gap + w_dec
    cur_x = price_center_x - (total_w / 2)
    # Draw Shekel, Main, Decimals
    c.setFont(f_reg, sub_size); c.drawString(cur_x, price_center_y, "₪")
    cur_x += w_shekel + gap
    c.setFont(f_extra, base_font_size); c.drawString(cur_x, price_center_y, main_digits)
    cur_x += w_main + gap
    c.setFont(f_extra, sub_size); c.drawString(cur_x, price_center_y, decimal_part)
    # --- Content: Product Info (Right) ---
    box_center_x = wx + (ww / 2)
    c.setFillColor(TEXT_COLOR); c.setFont(f_reg, 8); barcode_y = wy + 5
    c.drawCentredString(box_center_x, barcode_y, str(data.get('barcode', '')))
    text_area_y, text_area_h = barcode_y + 10, wy + wh - 2 - barcode_y - 10
    draw_wrapped_text(c, str(data.get('name', '')), wx, text_area_y, ww - 4, text_area_h, f_bold, 12)

# --- LLM Name Cleaning ---
def clean_product_names_batch(dirty_names):
    """
    Sends a list of product names to Gemini and returns a {dirty: cleaned} map.
    """
    if not client:
        print("LLM model not configured. Skipping name cleaning.")
        return {name: name for name in dirty_names}
    
    # Load few-shot examples
    examples_str = ""
    try:
        examples_path = os.path.join(os.path.dirname(__file__), 'few_shot_examples.json')
        if os.path.exists(examples_path):
            with open(examples_path, 'r', encoding='utf-8') as f:
                examples_data = json.load(f)
                # Take a subset of examples to save tokens if needed, e.g., first 10 and last 5
                # or just use all if the list isn't huge. The current list is ~50 items, which fits fine.
                examples_str = json.dumps(examples_data, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: Could not load few-shot examples: {e}")

    prompt = f"""
    You are an expert retail copywriter for a high-end home goods store.
    Your task is to reformat and clean raw product names from an ERP system for display on elegant customized shelf signage.

    ### Goal
    Transform raw, messy data into clean, professional, and inviting product names.

    ### Strict Rules
    1. **Use Your Tools**: If a name contains a barcode, code, or is ambiguous (e.g. '72900123', 'MKT-50'), **USE GOOGLE SEARCH** to find the real product name.
    2. **Remove Noise**: SCRUB all internal codes, SKUs, catalogue ID's (e.g., '7290...', 'MKT123', '(24)', 'OH-029'), and irrelevant technical info.
    3. **Fix Syntax**: Correct spacing, punctuation, and Hebrew grammar. Remove double spaces, weird dashes, etc.
    4. **Standardize Format**: 
       - Use "×" (multiplication sign) instead of "X" or "*" for dimensions (e.g., "20×20 cm").
       - Ensure units are formatted nicely (e.g., "100 מ״ל" or "1.5 ליטר").
    5. **Hebrew Focus**: Ensure the text flows naturally in Hebrew.
    6. **Keep Essentials**: Preserving brand names (if recognizable/premium) and key attributes (color, size, material) is vital.
    7. **JSON Output**: You must return ONLY a JSON object mapping Original Name -> Cleaned Name.

    ### Few-Shot Examples (Learn from these patterns)
    {examples_str}

    ### Input List (Clean these)
    {json.dumps(dirty_names, ensure_ascii=False)}

    ### Output JSON
    """
    retry_config = types.GenerateContentConfig(
        response_mime_type='application/json'
    )

    # Attempt 1: With Search Tool (Standard)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=generate_config
        )
        result = _parse_and_validate_llm_response(response.text if response.text else "", "Attempt 1")
        if result: return result
        
    except Exception as e:
         print(f"Error in Attempt 1: {e}")

    # Attempt 2: Retry without tools, forcing JSON
    print("Retrying with forced JSON structure (no tools)...")
    try:
        # Append a clear instruction for the retry
        retry_prompt = prompt + "\n\nIMPORTANT: Previous attempt failed. You MUST return a simple JSON Object mapping Original Name -> Cleaned Name. Do not return a list."
        
        response = client.models.generate_content(
            model=model_name,
            contents=retry_prompt,
            config=retry_config
        )
        result = _parse_and_validate_llm_response(response.text if response.text else "", "Attempt 2")
        if result: return result
        
    except Exception as e:
        print(f"Error in Attempt 2: {e}")

    print("All attempts failed. Returning original names.")
    return {name: name for name in dirty_names}

def _parse_and_validate_llm_response(text, attempt_name):
    """
    Parses LLM JSON response and attempts to recover data if it's a list.
    """
    try:
        # Clean markdown code blocks if present
        cleaned_text = text.strip()
        if cleaned_text.startswith("```"):
            first_newline = cleaned_text.find("\n")
            if first_newline != -1:
                cleaned_text = cleaned_text[first_newline+1:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        
        data = json.loads(cleaned_text)
        
        if isinstance(data, dict):
            return data
        
        if isinstance(data, list):
            # Using ensure_ascii=True to avoid UnicodeEncodeError on Windows consoles
            print(f"Warning ({attempt_name}): LLM returned a list: {json.dumps(data, ensure_ascii=True)}")
            # Attempt to recover from list
            # Case 1: List of dicts with 'original' and 'cleaned' keys (common pattern)
            # Case 2: List of strings (maybe just cleaned names?) - risky to map blindly
            # Case 3: List of dicts but assuming it's the map just wrapped in a list
            
            recovered_map = {}
            success = True
            for item in data:
                if isinstance(item, dict):
                    # check for common keys
                    keys = [k.lower() for k in item.keys()]
                    if 'original' in keys and 'cleaned' in keys:
                            # find exact keys
                            orig_k = next(k for k in item.keys() if k.lower() == 'original')
                            clean_k = next(k for k in item.keys() if k.lower() == 'cleaned')
                            recovered_map[item[orig_k]] = item[clean_k]
                    else:
                            # Maybe it's a list of single-key dicts? {orig: clean}
                            for k, v in item.items():
                                recovered_map[k] = v
                else:
                    success = False
                    break
            
            if success and recovered_map:
                print(f"Info: Successfully recovered {len(recovered_map)} items from list structure.")
                return recovered_map

        print(f"Warning ({attempt_name}): Response is not a valid dict or recoverable list.")
        return None
    except json.JSONDecodeError as e:
        print(f"Warning ({attempt_name}): JSON decode error: {e}")
        return None
    except Exception as e:
            print(f"Warning ({attempt_name}): Validation error: {e}")
            return None

# --- PDF Generation Logic ---
def _create_pdf_from_products(products, use_heebo):
    """
    Helper function to draw a list of products to a PDF canvas and return the PDF as bytes.
    """
    output_buffer = BytesIO()
    c = canvas.Canvas(output_buffer, pagesize=A4)
    width, height = A4
    x_gap, y_gap, x_start = 0.03 * cm, 1, 0
    y_start = height - SIGN_HEIGHT
    cur_x, cur_y, col_count = x_start, y_start, 0
    for prod in products:
        draw_discount_sign(c, cur_x, cur_y, prod) if prod.get('is_sale') else draw_sign(c, cur_x, cur_y, prod, use_heebo)
        col_count += 1
        if col_count < 2:
            cur_x += SIGN_WIDTH + x_gap
        else:
            col_count, cur_x, cur_y = 0, x_start, cur_y - (SIGN_HEIGHT + y_gap)
            if cur_y < 0:
                c.showPage()
                cur_x, cur_y = x_start, y_start
    c.save()
    output_buffer.seek(0)
    return output_buffer
    
# --- Data Handling & Main Functions ---
def filter_and_update_products(df):
    """
    Filters the DataFrame to include only products that need new signs.
    - 'Force Print' is True
    - Product is new (not in Firestore)
    - Price has changed
    Updates Firestore with new prices for these products.
    """
    try:
        db = firestore.Client()
        collection_ref = db.collection('products')
    except Exception as e:
        print(f"Warning: Could not connect to Firestore: {e}. Skipping persistence check.")
        return df
    barcodes = df['ברקוד'].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x).tolist()
    refs = [collection_ref.document(b) for b in barcodes]
    snapshots, existing_prices = [], {}
    for i in range(0, len(refs), 500):
        snapshots.extend(db.get_all(refs[i:i+500]))
    for snap in snapshots:
        if snap.exists: existing_prices[snap.id] = snap.get('price')
    batch, batch_count, indices_to_keep = db.batch(), 0, []
    has_delete_col = 'מחק' in df.columns

    for index, row in df.iterrows():
        barcode = str(row['ברקוד']); barcode = barcode[:-2] if barcode.endswith('.0') else barcode
        
        # Check for Delete flag
        to_delete = False
        if has_delete_col:
            val = row['מחק']
            if pd.notna(val) and str(val).strip() != "":
                to_delete = True

        try: price = float(row['מכירה'])
        except: price = 0.0
        
        force_print = 'אלץ הדפסה' in df.columns and pd.notna(row['אלץ הדפסה']) and str(row['אלץ הדפסה']).strip() != ""
        
        if to_delete:
            # Always print, and Delete from Firestore
            indices_to_keep.append(index)
            # Only delete if it exists to save writes/avoid errors (though delete on non-existing is usually fine in Firestore, 
            # checking existence might be safer or just blind delete)
            # Standard Firestore delete is idempotent/safe on non-existent docs.
            batch.delete(collection_ref.document(barcode))
            batch_count += 1
            print(f"Product {barcode} marked for deletion.")
            
        else:
            # Standard Logic
            should_print = force_print or barcode not in existing_prices or existing_prices[barcode] != price
            if should_print:
                indices_to_keep.append(index)
                if not force_print:
                    batch.set(collection_ref.document(barcode), {'price': price}); batch_count += 1
        
        if batch_count >= 400:
            batch.commit(); batch = db.batch(); batch_count = 0
    if batch_count > 0: batch.commit()
    print(f"Filtered {len(df)} products down to {len(indices_to_keep)} for printing.")
    return df.loc[indices_to_keep]

def validate_dataframe(df):
    """
    Validates the input DataFrame, raising ValueError if checks fail.
    """
    if df.empty: raise ValueError("The Excel file contains no data.")
    required = ['מכירה', 'שם פריט', 'ברקוד']
    if missing := [col for col in required if col not in df.columns]:
        raise ValueError(f"Missing required columns: {', '.join(missing)}. Please check your template.")

def generate_llm_and_original_pdfs(excel_file_obj):
    """
    Generates two PDFs from an Excel file: one with LLM-cleaned names and one with original names.
    Also generates an Excel file with the final names used in the LLM version.
    Returns a tuple of BytesIO objects: (llm_pdf_bytes, original_pdf_bytes, llm_excel_bytes).
    """
    use_heebo = register_fonts()
    try:
        df = pd.read_excel(excel_file_obj)
        df.columns = df.columns.str.strip()
        validate_dataframe(df)
        df_to_print = filter_and_update_products(df)
        if df_to_print.empty:
            print("No items to print (all filtered out).")
            return (None, None, None)
    except Exception as e:
        print(f"Error reading/validating Excel: {e}")
        raise e
    
    clean_str = lambda val: str(val).strip() if pd.notna(val) else ""
    clean_barcode = lambda val: clean_str(val)[:-2] if clean_str(val).endswith('.0') else clean_str(val)
    clean_price = lambda val: float(val) if pd.notna(val) else 0

    # Prepare data for LLM and PDFs
    products_for_pdf = []
    names_to_clean = []
    original_names = []
    
    # Check if 'Force Original Name' column exists
    force_col = 'אלץ שם מקורי'
    has_force_col = force_col in df_to_print.columns

    for index, row in df_to_print.iterrows():
        original_name = clean_str(row.get('שם פריט'))
        forced = False
        if has_force_col:
            val = row[force_col]
            if pd.notna(val) and str(val).strip() != "":
                forced = True
        
        prod_data = {
            "price": clean_price(row.get('מכירה', 0)), 
            "name": original_name,
            "barcode": clean_barcode(row.get('ברקוד')), 
            "is_sale": pd.notna(row.get('מבצע')) and clean_str(row.get('מבצע')) != '',
            "prev_price": clean_price(row.get('מחיר קודם', 0)),
            "force_original": forced,
            "original_row_index": index # Keep track of original index to update DataFrame later
        }
        products_for_pdf.append(prod_data)
        original_names.append(original_name)
        
        if not forced:
            names_to_clean.append(original_name)

    # Batch clean words using LLM
    cleaned_names_map = {}
    if names_to_clean:
        print(f"Sending {len(names_to_clean)} names to the LLM for cleaning...")
        cleaned_names_map = clean_product_names_batch(names_to_clean)
        print("Received cleaned names from LLM.")

    # Apply cleaned names where appropriate
    products_llm = []
    products_original = []
    
    # Store final names map for Excel update
    final_names_map = {} # index -> final_name

    for prod in products_for_pdf:
        # Create LLM version
        p_llm = prod.copy()
        if prod['force_original']:
             p_llm['name'] = prod['name'] # Keep original
        else:
             p_llm['name'] = cleaned_names_map.get(prod['name'], prod['name'])
        
        products_llm.append(p_llm)
        final_names_map[prod['original_row_index']] = p_llm['name']

        # Create Original version
        p_orig = prod.copy() # Name is already original
        products_original.append(p_orig)

    print("Generating PDF with LLM-cleaned names...")
    llm_pdf_bytes = _create_pdf_from_products(products_llm, use_heebo)
    print("Generating PDF with original names...")
    original_pdf_bytes = _create_pdf_from_products(products_original, use_heebo)
    
    # --- Generate Excel with Cleaned Names ---
    print("Generating Excel with cleaned names...")
    
    # Create a copy of the dataframe to avoid modifying the original if passed by reference (though read_excel creates new)
    df_output = df_to_print.copy()
    
    # Add 'Cleaned Name' column
    # We map the final names back using the original index
    df_output['Cleaned Name'] = df_output.index.map(final_names_map)
    
    output_excel_buffer = BytesIO()
    with pd.ExcelWriter(output_excel_buffer, engine='openpyxl') as writer:
        df_output.to_excel(writer, index=False)
    output_excel_buffer.seek(0)
    
    print("PDF and Excel generation complete.")
    
    return (llm_pdf_bytes, original_pdf_bytes, output_excel_buffer)

def generate_pdf_bytes(excel_file_obj):
    """
    Legacy function for backward compatibility with the HTTP endpoint.
    Generates a single PDF with LLM-cleaned names.
    Returns None if no items to print.
    """
    llm_pdf, _, _ = generate_llm_and_original_pdfs(excel_file_obj)
    return llm_pdf
