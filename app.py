import requests
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
import time
import json
import os
import pypdf
import pandas as pd
import re
import shutil
import numpy as np

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# কনফিগারেশন
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ২ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)

# ==============================================================================
# ডেটা ম্যানেজমেন্ট (JSON Files) - User & Stats
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'

# --- Stats Management ---
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"downloads": [], "last_booking": "None"}
    try:
        with open(STATS_FILE, 'r') as f: return json.load(f)
    except: return {"downloads": [], "last_booking": "None"}

def save_stats(data):
    with open(STATS_FILE, 'w') as f: json.dump(data, f)

def update_stats(ref_no):
    data = load_stats()
    data['downloads'].append({"ref": ref_no, "time": datetime.now().isoformat()})
    data['last_booking'] = ref_no
    save_stats(data)

def get_dashboard_summary():
    data = load_stats()
    downloads = data.get('downloads', [])
    now = datetime.now()
    today_str, month_str = now.strftime('%Y-%m-%d'), now.strftime('%Y-%m')
    today_count = sum(1 for d in downloads if datetime.fromisoformat(d['time']).strftime('%Y-%m-%d') == today_str)
    month_count = sum(1 for d in downloads if datetime.fromisoformat(d['time']).strftime('%Y-%m') == month_str)
    return {"today": today_count, "month": month_count, "last_booking": data.get('last_booking', 'N/A')}

# --- User Management System ---
DEFAULT_USERS = {
    "Admin": {
        "password": "@Nijhum@12",
        "role": "admin",
        "permissions": ["closing", "po", "input", "cutting", "production", "efficiency", "user_manage"]
    },
    "KobirAhmed": {
        "password": "11223",
        "role": "user",
        "permissions": ["closing"]
    }
}

def load_users():
    if not os.path.exists(USERS_FILE):
        save_users(DEFAULT_USERS)
        return DEFAULT_USERS
    try:
        with open(USERS_FILE, 'r') as f: return json.load(f)
    except: return DEFAULT_USERS

def save_users(data):
    with open(USERS_FILE, 'w') as f: json.dump(data, f, indent=4)

# ==============================================================================
# লজিক ১: PO Sheet Parser Functions (আপনার দেওয়া কোড হুবহু)
# ==============================================================================
def is_potential_size(header):
    h = header.strip().upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P.O NO"]:
        return False
    if re.match(r'^\d+$', h): return True
    if re.match(r'^\d+[AMYT]$', h): return True
    if re.match(r'^(XXS|XS|S|M|L|XL|XXL|XXXL|TU|ONE\s*SIZE)$', h): return True
    if re.match(r'^[A-Z]\d{2,}$', h): return False
    return False

def sort_sizes(size_list):
    STANDARD_ORDER = [
        '0M', '1M', '3M', '6M', '9M', '12M', '18M', '24M', '36M',
        '2A', '3A', '4A', '5A', '6A', '8A', '10A', '12A', '14A', '16A', '18A',
        'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL',
        'TU', 'One Size'
    ]
    def sort_key(s):
        s = s.strip()
        if s in STANDARD_ORDER: return (0, STANDARD_ORDER.index(s))
        if s.isdigit(): return (1, int(s))
        match = re.match(r'^(\d+)([A-Z]+)$', s)
        if match: return (2, int(match.group(1)), match.group(2))
        return (3, s)
    return sorted(size_list, key=sort_key)

def extract_metadata(first_page_text):
    meta = {
        'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 
        'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'
    }
    
    if "KIABI" in first_page_text.upper():
        meta['buyer'] = "KIABI"
    else:
        buyer_match = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", first_page_text)
        if buyer_match: meta['buyer'] = buyer_match.group(1).strip()

    booking_block_match = re.search(r"(?:Internal )?Booking NO\.?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match: 
        raw_booking = booking_block_match.group(1).strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking: clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\.?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match: meta['style'] = style_match.group(1).strip()
    else:
        style_match = re.search(r"Style Des\.?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match: meta['style'] = style_match.group(1).strip()

    season_match = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re.IGNORECASE)
    if season_match: meta['season'] = season_match.group(1).strip()

    dept_match = re.search(r"Dept\.?[\s\n:]*([A-Za-z]+)", first_page_text, re.IGNORECASE)
    if dept_match: meta['dept'] = dept_match.group(1).strip()

    item_match = re.search(r"Garments? Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
    if item_match: 
        item_text = item_match.group(1).strip()
        if "Style" in item_text: item_text = item_text.split("Style")[0].strip()
        meta['item'] = item_text

    return meta

def extract_data_dynamic(file_path):
    extracted_data = []
    metadata = {
        'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 
        'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'
    }
    order_no = "Unknown"
    
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        
        if "Main Fabric Booking" in first_page_text or "Fabric Booking Sheet" in first_page_text:
            metadata = extract_metadata(first_page_text)
            return [], metadata 

        order_match = re.search(r"Order no\D*(\d+)", first_page_text, re.IGNORECASE)
        if order_match: order_no = order_match.group(1)
        else:
            alt_match = re.search(r"Order\s*[:\.]?\s*(\d+)", first_page_text, re.IGNORECASE)
            if alt_match: order_no = alt_match.group(1)
        
        order_no = str(order_no).strip()
        if order_no.endswith("00"): order_no = order_no[:-2]

        for page in reader.pages:
            text = page.extract_text()
            lines = text.split('\n')
            sizes = []
            capturing_data = False
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue

                if ("Colo" in line or "Size" in line) and "Total" in line:
                    parts = line.split()
                    try:
                        total_idx = [idx for idx, x in enumerate(parts) if 'Total' in x][0]
                        raw_sizes = parts[:total_idx]
                        temp_sizes = [s for s in raw_sizes if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/", "Size's"]]
                        
                        valid_size_count = sum(1 for s in temp_sizes if is_potential_size(s))
                        if temp_sizes and valid_size_count >= len(temp_sizes) / 2:
                            sizes = temp_sizes
                            capturing_data = True
                        else:
                            sizes = []
                            capturing_data = False
                    except: pass
                    continue
                
                if capturing_data:
                    if line.startswith("Total Quantity") or line.startswith("Total Amount"):
                        capturing_data = False
                        continue
                    
                    lower_line = line.lower()
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line:
                        continue
                        
                    clean_line = line.replace("Spec. price", "").replace("Spec", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line): continue
                    if re.match(r'^[A-Z]\d+$', clean_line) or "Assortment" in clean_line: continue

                    numbers_in_line = re.findall(r'\b\d+\b', line)
                    quantities = [int(n) for n in numbers_in_line]
                    color_name = clean_line
                    final_qtys = []

                    if len(quantities) >= len(sizes):
                        if len(quantities) == len(sizes) + 1: final_qtys = quantities[:-1] 
                        else: final_qtys = quantities[:len(sizes)]
                        color_name = re.sub(r'\s\d+$', '', color_name).strip()
                    elif len(quantities) < len(sizes): 
                        vertical_qtys = []
                        for next_line in lines[i+1:]:
                            next_line = next_line.strip()
                            if "Total" in next_line or re.search(r'[a-zA-Z]', next_line.replace("Spec", "").replace("price", "")): break
                            if re.match(r'^\d+$', next_line): vertical_qtys.append(int(next_line))
                        if len(vertical_qtys) >= len(sizes): final_qtys = vertical_qtys[:len(sizes)]
                    
                    if final_qtys and color_name:
                         for idx, size in enumerate(sizes):
                            extracted_data.append({
                                'P.O NO': order_no,
                                'Color': color_name,
                                'Size': size,
                                'Quantity': final_qtys[idx]
                            })
    except Exception as e: print(f"Error processing file: {e}")
    return extracted_data, metadata

# ==============================================================================
# লজিক ২: CLOSING REPORT (ERP Login & Parsing) - হুবহু আপনার আগের কোড
# ==============================================================================
def get_authenticated_session(username, password):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    try:
        # 5 Minute Timeout (300 Seconds)
        response = session_req.post(login_url, data=login_payload, timeout=300)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            return session_req
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def parse_report_data(html_content):
    all_report_data = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row: return None
        all_th = header_row.find_all('th')
        headers = [th.get_text(strip=True) for th in all_th if 'total' not in th.get_text(strip=True).lower()]
        data_rows = soup.select('div#scroll_body table tbody tr')
        item_blocks = []
        current_block = []
        for row in data_rows:
            if row.get('bgcolor') == '#cddcdc':
                if current_block: item_blocks.append(current_block)
                current_block = []
            else:
                current_block.append(row)
        if current_block: item_blocks.append(current_block)
        for block in item_blocks:
            style, color, buyer_name, gmts_qty_data, sewing_input_data, cutting_qc_data = "N/A", "N/A", "N/A", None, None, None
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0].get_text(strip=True)
                    criteria_sub = cells[2].get_text(strip=True)
                    main_lower, sub_lower = criteria_main.lower(), criteria_sub.lower()
                    if main_lower == "style": style = cells[1].get_text(strip=True)
                    elif main_lower == "color & gmts. item": color = cells[1].get_text(strip=True)
                    elif "buyer" in main_lower: buyer_name = cells[1].get_text(strip=True)
                    if sub_lower == "gmts. color /country qty": gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in main_lower: sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in sub_lower: sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "cutting qc" in main_lower and "balance" not in main_lower:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "cutting qc" in sub_lower and "balance" not in sub_lower:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            if gmts_qty_data:
                plus_3_percent_data = []
                for value in gmts_qty_data:
                    try:
                        new_qty = round(int(value.replace(',', '')) * 1.03)
                        plus_3_percent_data.append(str(new_qty))
                    except (ValueError, TypeError):
                        plus_3_percent_data.append(value)
                all_report_data.append({'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 'gmts_qty': gmts_qty_data, 'plus_3_percent': plus_3_percent_data, 'sewing_input': sewing_input_data if sewing_input_data else [], 'cutting_qc': cutting_qc_data if cutting_qc_data else []})
        return all_report_data
    except Exception as e:
        return None

# ==============================================================================
# ফাংশন ৩: ফরম্যাটেড এক্সেল রিপোর্ট (হুবহু আপনার দেওয়া কোড)
# ==============================================================================
def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
   
    # --- স্টাইল এবং কালার প্যালেট ---
    bold_font = Font(bold=True)
    title_font = Font(size=32, bold=True, color="7B261A") 
    white_bold_font = Font(size=16.5, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    color_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    medium_border = Border(left=Side(style='medium'), right=Side(style='medium'), top=Side(style='medium'), bottom=Side(style='medium'))
    
    ir_ib_fill = PatternFill(start_color="7B261A", end_color="7B261A", fill_type="solid") 
    header_row_fill = PatternFill(start_color="DE7465", end_color="DE7465", fill_type="solid") 
    light_brown_fill = PatternFill(start_color="DE7465", end_color="DE7465", fill_type="solid") 
    light_blue_fill = PatternFill(start_color="B9C2DF", end_color="B9C2DF", fill_type="solid") 
    light_green_fill = PatternFill(start_color="C4D09D", end_color="C4D09D", fill_type="solid") 
    dark_green_fill = PatternFill(start_color="f1f2e8", end_color="f1f2e8", fill_type="solid") 

    NUM_COLUMNS, TABLE_START_ROW = 9, 8
   
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NUM_COLUMNS)
    ws['A1'].value = "COTTON CLOTHING BD LTD"
    ws['A1'].font = title_font 
    ws['A1'].alignment = center_align

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=NUM_COLUMNS)
    ws['A2'].value = "CLOSING REPORT [ INPUT SECTION ]"
    ws['A2'].font = Font(size=15, bold=True) 
    ws['A2'].alignment = center_align
    ws.row_dimensions[3].height = 6

    formatted_ref_no = internal_ref_no.upper()
    current_date = datetime.now().strftime("%d/%m/%Y")
    left_sub_headers = {'A4': 'BUYER', 'B4': report_data[0].get('buyer', ''), 'A5': 'IR/IB NO', 'B5': formatted_ref_no, 'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')}
    
    for cell_ref, value in left_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell.font = bold_font
        cell.alignment = left_align
        cell.border = thin_border
        if cell_ref == 'B5':
            cell.fill = ir_ib_fill      
            cell.font = white_bold_font 
        else:
            cell.fill = dark_green_fill 

    ws.merge_cells('B4:G4'); ws.merge_cells('B5:G5'); ws.merge_cells('B6:G6')
    
    right_sub_headers = {'H4': 'CLOSING DATE', 'I4': current_date, 'H5': 'SHIPMENT', 'I5': 'ALL', 'H6': 'PO NO', 'I6': 'ALL'}
    for cell_ref, value in right_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell.font = bold_font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = dark_green_fill 

    for row in range(4, 7):
        for col in range(3, 8): 
            cell = ws.cell(row=row, column=col)
            cell.border = thin_border
       
    current_row = TABLE_START_ROW
   
    for block in report_data:
        table_headers = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for col_idx, header in enumerate(table_headers, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=header)
            cell.font = bold_font
            cell.alignment = center_align
            cell.border = medium_border
            cell.fill = header_row_fill 

        current_row += 1
        start_merge_row = current_row
        full_color_name = block.get('color', 'N/A')

        for i, size in enumerate(block['headers']):
            color_to_write = full_color_name if i == 0 else ""
            actual_qty = int(block['gmts_qty'][i].replace(',', '') or 0)
            input_qty = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cutting_qc_val = int(block.get('cutting_qc', [])[i].replace(',', '') or 0) if i < len(block.get('cutting_qc', [])) else 0
            
            ws.cell(row=current_row, column=1, value=color_to_write)
            ws.cell(row=current_row, column=2, value=size)
            ws.cell(row=current_row, column=4, value=actual_qty)
            ws.cell(row=current_row, column=5, value=cutting_qc_val)
            ws.cell(row=current_row, column=6, value=input_qty)
            
            ws.cell(row=current_row, column=3, value=f"=ROUND(D{current_row}*1.03, 0)")      
            ws.cell(row=current_row, column=7, value=f"=E{current_row}-F{current_row}")      
            ws.cell(row=current_row, column=8, value=f"=F{current_row}-C{current_row}")      
            ws.cell(row=current_row, column=9, value=f'=IF(C{current_row}<>0, H{current_row}/C{current_row}, 0)') 
            
            for col_idx in range(1, NUM_COLUMNS + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = medium_border if col_idx == 2 else thin_border
                cell.alignment = center_align
                if col_idx in [1, 2, 3, 6, 9]: cell.font = bold_font
                
                if col_idx == 3: cell.fill = light_blue_fill      
                elif col_idx == 6: cell.fill = light_green_fill   
                else: cell.fill = dark_green_fill 

                if col_idx == 9:
                    cell.number_format = '0.00%' 
            current_row += 1
            
        end_merge_row = current_row - 1
        if start_merge_row <= end_merge_row:
            ws.merge_cells(start_row=start_merge_row, start_column=1, end_row=end_merge_row, end_column=1)
            merged_cell = ws.cell(row=start_merge_row, column=1)
            merged_cell.alignment = color_align
            if not merged_cell.font.bold: merged_cell.font = bold_font

        total_row_str = str(current_row)
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
        
        totals_formulas = {
            "A": "TOTAL",
            "C": f"=SUM(C{start_merge_row}:C{end_merge_row})",
            "D": f"=SUM(D{start_merge_row}:D{end_merge_row})",
            "E": f"=SUM(E{start_merge_row}:E{end_merge_row})",
            "F": f"=SUM(F{start_merge_row}:F{end_merge_row})",
            "G": f"=SUM(G{start_merge_row}:G{end_merge_row})",
            "H": f"=SUM(H{start_merge_row}:H{end_merge_row})",
            "I": f"=IF(C{total_row_str}<>0, H{total_row_str}/C{total_row_str}, 0)"
        }
        
        for col_letter, value_or_formula in totals_formulas.items():
            cell = ws[f"{col_letter}{current_row}"]
            cell.value = value_or_formula
            cell.font = bold_font
            cell.border = medium_border
            cell.alignment = center_align
            cell.fill = light_brown_fill 
            if col_letter == 'I':
                cell.number_format = '0.00%'
        
        for col_idx in range(2, NUM_COLUMNS + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            if not cell.value: 
                cell.fill = dark_green_fill 
                cell.border = medium_border
        current_row += 2
       
    image_row = current_row + 1
   
    try:
        direct_image_url = 'https://i.ibb.co/v6bp0jQW/rockybilly-regular.webp'
        image_response = requests.get(direct_image_url)
        image_response.raise_for_status()
        original_img = PILImage.open(BytesIO(image_response.content))
        padded_img = PILImage.new('RGBA', (original_img.width + 400, original_img.height), (0, 0, 0, 0))
        padded_img.paste(original_img, (400, 0))
        padded_image_io = BytesIO()
        padded_img.save(padded_image_io, format='PNG')
        img = Image(padded_image_io)
        aspect_ratio = padded_img.height / padded_img.width
        img.width = 95
        img.height = int(img.width * aspect_ratio)
        ws.row_dimensions[image_row].height = img.height * 0.90
        ws.add_image(img, f'A{image_row}')
    except Exception:
        pass

    signature_row = image_row + 1
    ws.merge_cells(start_row=signature_row, start_column=1, end_row=signature_row, end_column=NUM_COLUMNS)
    titles = ["Prepared By", "Input Incharge", "Cutting Incharge", "IE & Planning", "Sewing Manager", "Cutting Manager"]
    signature_cell = ws.cell(row=signature_row, column=1)
    signature_cell.value = "                 ".join(titles)
    signature_cell.font = Font(bold=True, size=15)
    signature_cell.alignment = Alignment(horizontal='center', vertical='center')

    last_data_row = current_row - 2
    for row in ws.iter_rows(min_row=4, max_row=last_data_row):
        for cell in row:
            if cell.coordinate == 'B5': continue
            if cell.font:
                existing_font = cell.font
                if cell.row != 1: 
                    new_font = Font(name=existing_font.name, size=16.5, bold=existing_font.bold, italic=existing_font.italic, vertAlign=existing_font.vertAlign, underline=existing_font.underline, strike=existing_font.strike, color=existing_font.color)
                    cell.font = new_font
   
    ws.column_dimensions['A'].width = 23
    ws.column_dimensions['B'].width = 8.5
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 17
    ws.column_dimensions['E'].width = 17
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 13.5
    ws.column_dimensions['H'].width = 23
    ws.column_dimensions['I'].width = 18
   
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1 
    ws.page_setup.horizontalCentered = True
    ws.page_setup.verticalCentered = False 
    ws.page_setup.left = 0.25
    ws.page_setup.right = 0.25
    ws.page_setup.top = 0.45
    ws.page_setup.bottom = 0.45
    ws.page_setup.header = 0
    ws.page_setup.footer = 0
   
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==============================================================================
# CSS & TEMPLATES
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body {
            background-color: #2c3e50; 
            background-image: url('https://i.ibb.co.com/v64Lz1gj/Picsart-25-11-19-15-49-43-423.jpg');
            background-repeat: no-repeat; background-position: center; background-attachment: fixed; background-size: cover;
            height: 100vh; overflow: hidden; color: white;
        }
        body::before { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.5); z-index: -1; }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); padding: 40px; color: white;
        }
        
        input, select, button { width: 100%; padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.3); background: rgba(255,255,255,0.1); color: white; margin-bottom: 15px; outline: none; }
        input:focus, select:focus { background: rgba(255,255,255,0.2); border-color: white; }
        select option { background: #2c3e50; }
        button { background: linear-gradient(135deg, #667eea, #764ba2); border: none; font-weight: 600; cursor: pointer; transition: 0.3s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }
        .danger-btn { background: linear-gradient(135deg, #ff7675, #d63031); }

        .admin-container { display: flex; height: 100vh; }
        .sidebar { width: 280px; background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); padding: 25px; display: flex; flex-direction: column; border-right: 1px solid rgba(255,255,255,0.1); }
        .nav-item { padding: 12px; cursor: pointer; color: rgba(255,255,255,0.7); transition: 0.3s; border-radius: 8px; margin-bottom: 5px; display: flex; align-items: center; text-decoration: none; }
        .nav-item:hover, .nav-item.active { background: rgba(255,255,255,0.1); color: white; }
        .nav-item i { margin-right: 10px; width: 20px; text-align: center; }
        
        .content { flex: 1; padding: 30px; overflow-y: auto; }
        .section { display: none; animation: fadeIn 0.5s; }
        .section.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .user-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .user-table th, .user-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; }
        .user-table th { background: rgba(255,255,255,0.1); }
        
        .checkbox-group { display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 15px; }
        .checkbox-item { display: flex; align-items: center; gap: 5px; font-size: 14px; background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 20px; cursor: pointer; }
        .checkbox-item input { width: auto; margin: 0; }

        /* Loader */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 9999; justify-content: center; align-items: center; flex-direction: column; }
        .spinner { width: 50px; height: 50px; border: 5px solid rgba(255,255,255,0.3); border-top-color: #a29bfe; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .success-icon { font-size: 60px; color: #2ecc71; display: none; margin-bottom: 10px; animation: popIn 0.5s ease; }
        @keyframes popIn { from { transform: scale(0); } to { transform: scale(1); } }
        #loading-text { font-size: 18px; font-weight: 500; letter-spacing: 1px; text-align: center; }
        .loader-error .spinner { border-top-color: #e74c3c; animation: none; }
        .loader-error #loading-text { color: #e74c3c; font-weight: 700; }
        .loader-success .spinner { display: none; }
        .loader-success .success-icon { display: block; }
        .loader-success #loading-text { color: #2ecc71; font-weight: 600; }

        /* Admin Dashboard CSS */
        .admin-sidebar { width: 280px; background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(15px); border-right: 1px solid rgba(255, 255, 255, 0.1); display: flex; flex-direction: column; padding: 25px; }
        .sidebar-header { margin-bottom: 40px; text-align: center; }
        .sidebar-header h2 { color: white; font-size: 22px; font-weight: 600; }
        .sidebar-header p { color: #a29bfe; font-size: 12px; letter-spacing: 1px; }
        .nav-menu { list-style: none; }
        .nav-item { margin-bottom: 15px; }
        .nav-link { display: flex; align-items: center; padding: 12px 15px; color: rgba(255, 255, 255, 0.7); text-decoration: none; border-radius: 10px; transition: all 0.3s ease; font-size: 14px; cursor: pointer; }
        .nav-link i { margin-right: 12px; width: 20px; text-align: center; }
        .nav-link:hover, .nav-link.active { background: linear-gradient(90deg, rgba(108, 92, 231, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%); color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transform: translateX(5px); }
        .admin-footer { margin-top: auto; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px; }
        .admin-content { flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); padding: 20px; border-radius: 15px; display: flex; align-items: center; transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.15); }
        .stat-icon { width: 50px; height: 50px; border-radius: 12px; background: rgba(255, 255, 255, 0.1); display: flex; align-items: center; justify-content: center; font-size: 20px; color: #fff; margin-right: 15px; }
        .stat-info h3 { font-size: 24px; color: white; margin-bottom: 5px; }
        .stat-info p { font-size: 13px; color: #dcdcdc; }
        .bg-purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .bg-orange { background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%); }
        .bg-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .work-area { flex: 1; background: rgba(0, 0, 0, 0.2); border-radius: 20px; padding: 30px; display: flex; justify-content: center; align-items: flex-start; position: relative; }
        .swal-overlay { background-color: rgba(0, 0, 0, 0.6); }
        .swal-modal { background-color: #2d3436; border: 1px solid rgba(255,255,255,0.1); }
        .swal-title { color: white; }
        .swal-text { color: #b2bec3; }
    </style>
"""

LOGIN_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head><title>MEHEDI HASAN</title>{COMMON_STYLES}</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="width: 400px; text-align: center;">
            <h2 style="margin-bottom: 20px;">System Login</h2>
            <form action="/login" method="post">
                <div class="input-group">
                    <label for="username">Select User</label>
                    <select id="username" name="username" required>
                        <option value="KobirAhmed">KobirAhmed</option>
                        <option value="Admin">Admin</option>
                    </select>
                </div>
                <div class="input-group">
                    <label for="password">Authentication PIN</label>
                    <input type="password" id="password" name="password" placeholder="Enter Password" required>
                </div>
                <button type="submit">Verify & Enter</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
        </div>
    </div>
</body>
</html>
"""

PO_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><title>PO Report</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{background:#f8f9fa;font-family:sans-serif}.container{max-width:1200px}.company-header{text-align:center;border-bottom:2px solid #000;margin-bottom:20px}.company-name{font-size:2.2rem;font-weight:800;color:#2c3e50}.table th{background:#2c3e50;color:white;text-align:center}.table td{text-align:center;font-weight:bold}@media print{.no-print{display:none}.table th{background:#2c3e50!important;color:white!important;-webkit-print-color-adjust:exact}}</style></head><body><div class="container mt-4"><div class="d-flex justify-content-between no-print mb-3"><a href="/" class="btn btn-secondary">Back</a><button onclick="window.print()" class="btn btn-primary">Print</button></div><div class="company-header"><div class="company-name">Cotton Clothing BD Limited</div><h4>Purchase Order Summary</h4></div>{% if message %}<div class="alert alert-warning">{{ message }}</div>{% endif %}{% if tables %}<div class="row mb-3 border p-2"><div class="col-md-6"><strong>Buyer:</strong> {{ meta.buyer }}<br><strong>Style:</strong> {{ meta.style }}</div><div class="col-md-6 text-end"><h3>Total: {{ grand_total }}</h3></div></div>{% for item in tables %}<div class="card mb-3"><div class="card-header bg-light"><strong>COLOR: {{ item.color }}</strong></div><div class="card-body p-0">{{ item.table | safe }}</div></div>{% endfor %}{% endif %}</div></body></html>"""

ADMIN_DASHBOARD = f"""
<!DOCTYPE html>
<html lang="en">
<head><title>Admin Panel</title>{COMMON_STYLES}
<script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
</head>
<body>
    <div id="loading-overlay"><div class="spinner"></div><h3 style="margin-top:20px">Processing...</h3></div>
    
    <div class="admin-container">
        <div class="admin-sidebar">
            <div class="sidebar-header">
                <h2>Admin Panel</h2>
                <p>SUPER ADMIN ACCESS</p>
            </div>
            
            <ul class="nav-menu">
                <li class="nav-item">
                    <a class="nav-link active" onclick="showTab('dashboard', this)" id="link-dashboard"><i class="fas fa-home"></i> Dashboard</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showTab('closing', this)" id="link-closing"><i class="fas fa-file-export"></i> Closing Report</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showTab('po', this)" id="link-po"><i class="fas fa-file-invoice"></i> PO Sheet</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showTab('users', this)" id="link-users"><i class="fas fa-users-cog"></i> User Management</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Input & Output Report')"><i class="fas fa-exchange-alt"></i> Input & Output Report</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Cutting Plan Sheet')"><i class="fas fa-cut"></i> Cutting Plan Sheet</a>
                </li>
            </ul>
            
            <div class="admin-footer">
                <a href="/logout" class="nav-link" style="color: #ff7675;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        </div>
        
        <div class="admin-content">
            <div id="dashboard" class="section active">
                <h1>Welcome, {{{{ session.user }}}}</h1>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-icon bg-purple"><i class="fas fa-calendar-day"></i></div>
                        <div class="stat-info">
                            <h3>{{{{ stats.today }}}}</h3>
                            <p>Today's Downloads</p>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon bg-orange"><i class="fas fa-calendar-alt"></i></div>
                        <div class="stat-info">
                            <h3>{{{{ stats.month }}}}</h3>
                            <p>Monthly Downloads</p>
                        </div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon bg-green"><i class="fas fa-history"></i></div>
                        <div class="stat-info">
                            <h3 style="font-size: 16px; word-break: break-all;">{{{{ stats.last_booking }}}}</h3>
                            <p>Last Generated Booking</p>
                        </div>
                    </div>
                </div>
            </div>

            <div id="closing" class="section">
                <div class="work-area">
                    <div class="glass-card" style="width: 100%; max-width: 500px; background: rgba(255,255,255,0.05); box-shadow: none; border: none;">
                        <h2 style="margin-bottom: 20px; font-weight: 500;"><i class="fas fa-file-export"></i> Generate Closing Report</h2>
                        <form action="/generate-report" method="post" onsubmit="startDownloadProcess()">
                            <div class="input-group">
                                <label for="ref_no">Internal Reference No</label>
                                <input type="text" id="ref_no" name="ref_no" placeholder="Enter Ref No (e.g. DFL/24/..)" required>
                                <input type="hidden" name="download_token" id="download_token">
                            </div>
                            <button type="submit">Generate Report</button>
                        </form>
                    </div>
                </div>
            </div>

            <div id="po" class="section">
                <div class="work-area">
                    <div class="glass-card" style="width: 100%; max-width: 500px; background: rgba(255,255,255,0.05); box-shadow: none; border: none;">
                        <h2 style="margin-bottom: 20px; font-weight: 500;"><i class="fas fa-file-invoice"></i> PDF Report Generator</h2>
                        <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                            <div class="input-group">
                                <label for="pdf_files">Select PDF Files (Booking & PO)</label>
                                <input type="file" id="pdf_files" name="pdf_files" multiple accept=".pdf" required style="height: auto;">
                            </div>
                            <button type="submit" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">Generate Report</button>
                        </form>
                    </div>
                </div>
            </div>

            <div id="users" class="section">
                <div class="glass-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h2>User Management</h2>
                        <button onclick="document.getElementById('add-user-form').style.display='block'" style="width:auto; padding: 8px 20px;">+ Add User</button>
                    </div>
                    
                    <div id="add-user-form" style="display:none; background: rgba(0,0,0,0.2); padding: 20px; border-radius: 10px; margin-top: 20px;">
                        <h3>Create / Edit User</h3>
                        <form action="/manage-users/add" method="post">
                            <input type="text" name="new_username" placeholder="Username" required>
                            <input type="text" name="new_password" placeholder="Password" required>
                            <label>Permissions:</label>
                            <div class="checkbox-group">
                                <label class="checkbox-item"><input type="checkbox" name="perms" value="closing"> Closing Report</label>
                                <label class="checkbox-item"><input type="checkbox" name="perms" value="po"> PO Sheet</label>
                                <label class="checkbox-item"><input type="checkbox" name="perms" value="input"> Input Report</label>
                                <label class="checkbox-item"><input type="checkbox" name="perms" value="cutting"> Cutting Report</label>
                                <label class="checkbox-item"><input type="checkbox" name="perms" value="user_manage"> User Manage</label>
                            </div>
                            <button type="submit">Save User</button>
                            <button type="button" onclick="document.getElementById('add-user-form').style.display='none'" class="danger-btn">Cancel</button>
                        </form>
                    </div>

                    <table class="user-table">
                        <thead><tr><th>Username</th><th>Role</th><th>Permissions</th><th>Actions</th></tr></thead>
                        <tbody>
                            {% for name, details in users.items() %}
                            <tr>
                                <td>{{{{ name }}}}</td>
                                <td><span style="padding: 2px 8px; border-radius: 4px; background: {{{{ 'rgba(46, 204, 113,0.3)' if details.role=='admin' else 'rgba(52, 152, 219,0.3)' }}}};">{{{{ details.role }}}}</span></td>
                                <td>{{{{ details.permissions | join(', ') }}}}</td>
                                <td>
                                    {% if name != 'Admin' %}
                                    <form action="/manage-users/delete" method="post" style="display:inline;" onsubmit="return confirm('Delete user?');">
                                        <input type="hidden" name="username" value="{{{{ name }}}}">
                                        <button type="submit" class="danger-btn" style="width:auto; padding:5px 10px; font-size:12px;"><i class="fas fa-trash"></i></button>
                                    </form>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showTab(id, element) {{
            document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            if(element) element.classList.add('active');
        }}
        function showComingSoon(featureName) {{
            swal({{ title: "Feature Coming Soon!", text: "The '" + featureName + "' module will be launched very soon. Stay tuned!", icon: "info", button: "Got it!", className: "swal-dark" }});
        }}
        function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; setTimeout(() => {{ location.reload(); }}, 3000); }}
        
        // Cookie logic for closing report
        function getCookie(name) {{ let parts = document.cookie.split(name + "="); if (parts.length == 2) return parts.pop().split(";").shift(); return null; }}
        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); const loadingText = document.getElementById('loading-text'); const spinner = document.querySelector('.spinner'); const successIcon = document.querySelector('.success-icon'); const tokenInput = document.getElementById('download_token');
            const token = new Date().getTime(); tokenInput.value = token;
            overlay.style.display = 'flex'; overlay.className = ''; loadingText.innerHTML = "Processing data...<br><span style='font-size:12px; opacity:0.8'>Downloading will start automatically</span>"; spinner.style.display = 'block'; successIcon.style.display = 'none';
            let attempts = 0;
            const downloadTimer = setInterval(function() {{
                const cookieValue = getCookie("download_token");
                if (cookieValue == token) {{
                    clearInterval(downloadTimer);
                    overlay.classList.add('loader-success'); loadingText.innerHTML = "Successful Download Complete!";
                    setTimeout(() => {{ window.location.reload(); }}, 2000);
                }}
                attempts++; if (attempts > 300) {{ clearInterval(downloadTimer); overlay.classList.add('loader-error'); spinner.style.display = 'none'; loadingText.innerHTML = "Server Timeout"; }}
            }}, 1000);
        }}

        // Show success/error messages
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                swal("Notification", "{{{{ messages[0] }}}}", "info");
            {% endif %}
        {% endwith %}
    </script>
</body>
</html>
"""

USER_DASHBOARD = f"""
<!DOCTYPE html>
<html lang="en">
<head><title>Dashboard</title>{COMMON_STYLES}</head>
<body>
    <div id="loading-overlay"><div class="spinner"></div><h3>Processing...</h3></div>
    <div style="display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; gap: 20px;">
        <div class="glass-card" style="text-align: center; width: 400px;">
            <h2>Welcome, {{{{ session.user }}}}</h2>
            <p style="color:#a29bfe;">Select a Module</p>
            
            {% if 'closing' in perms %}
            <button onclick="document.getElementById('closing-modal').style.display='block'" style="margin-top:10px;"><i class="fas fa-file-export"></i> Closing Report</button>
            {% endif %}
            
            {% if 'po' in perms %}
            <button onclick="document.getElementById('po-modal').style.display='block'" style="background: linear-gradient(135deg, #11998e, #38ef7d); margin-top:10px;"><i class="fas fa-file-invoice"></i> PO Sheet</button>
            {% endif %}
            
            <a href="/logout" style="color: #ff7675; display: block; margin-top: 20px;">Logout</a>
        </div>
    </div>

    <div id="closing-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:100;">
        <div style="display:flex; justify-content:center; align-items:center; height:100%;">
            <div class="glass-card" style="width:400px; position:relative;">
                <span onclick="document.getElementById('closing-modal').style.display='none'" style="position:absolute; top:10px; right:20px; cursor:pointer; font-size:20px;">&times;</span>
                <h3>Closing Report</h3>
                <form action="/generate-report" method="post" onsubmit="startDownloadProcess()">
                    <input type="text" name="ref_no" placeholder="Reference No" required>
                    <input type="hidden" name="download_token" id="download_token">
                    <button type="submit">Generate</button>
                </form>
            </div>
        </div>
    </div>

    <div id="po-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:100;">
        <div style="display:flex; justify-content:center; align-items:center; height:100%;">
            <div class="glass-card" style="width:400px; position:relative;">
                <span onclick="document.getElementById('po-modal').style.display='none'" style="position:absolute; top:10px; right:20px; cursor:pointer; font-size:20px;">&times;</span>
                <h3>PO Sheet</h3>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                    <input type="file" name="pdf_files" multiple accept=".pdf" required>
                    <button type="submit" style="background: linear-gradient(135deg, #11998e, #38ef7d);">Generate</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; setTimeout(() => {{ location.reload(); }}, 3000); }}
        // Cookie logic same as admin
        function getCookie(name) {{ let parts = document.cookie.split(name + "="); if (parts.length == 2) return parts.pop().split(";").shift(); return null; }}
        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); const spinner = document.querySelector('.spinner'); 
            const tokenInput = document.getElementById('download_token');
            const token = new Date().getTime(); tokenInput.value = token;
            overlay.style.display = 'flex'; 
            let attempts = 0;
            const downloadTimer = setInterval(function() {{
                const cookieValue = getCookie("download_token");
                if (cookieValue == token) {{
                    clearInterval(downloadTimer);
                    overlay.style.display = 'none';
                }}
                attempts++; if (attempts > 300) {{ clearInterval(downloadTimer); overlay.style.display = 'none'; }}
            }}, 1000);
        }}
    </script>
</body>
</html>
"""

# ==============================================================================
# ROUTING LOGIC
# ==============================================================================

@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_HTML)
    
    users = load_users()
    current_user = session.get('user')
    
    # Handle case where user might be deleted while logged in
    if current_user not in users:
        session.clear()
        return redirect('/')

    user_data = users.get(current_user, {})
    role = user_data.get('role', 'user')
    perms = user_data.get('permissions', [])

    if role == 'admin':
        stats = get_dashboard_summary()
        return render_template_string(ADMIN_DASHBOARD, stats=stats, users=users)
    else:
        return render_template_string(USER_DASHBOARD, perms=perms)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    users = load_users()

    if username in users and users[username]['password'] == password:
        session.permanent = True
        session['logged_in'] = True
        session['user'] = username
        return redirect(url_for('index'))
    else:
        flash('Invalid Credentials')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully')
    return redirect(url_for('index'))

# --- User Management Routes ---
@app.route('/manage-users/add', methods=['POST'])
def add_user():
    if not session.get('logged_in'): return redirect('/')
    # Check admin permission
    users = load_users()
    if users.get(session['user'], {}).get('role') != 'admin':
        flash("Unauthorized"); return redirect('/')

    new_user = request.form.get('new_username')
    new_pass = request.form.get('new_password')
    perms = request.form.getlist('perms')

    if new_user and new_pass:
        users[new_user] = {
            "password": new_pass,
            "role": "user",
            "permissions": perms
        }
        save_users(users)
        flash(f"User {new_user} saved successfully!")
    return redirect('/')

@app.route('/manage-users/delete', methods=['POST'])
def delete_user():
    if not session.get('logged_in'): return redirect('/')
    users = load_users()
    if users.get(session['user'], {}).get('role') != 'admin': return redirect('/')
    
    target_user = request.form.get('username')
    if target_user == 'Admin':
        flash("Cannot delete Super Admin!")
    elif target_user in users:
        del users[target_user]
        save_users(users)
        flash(f"User {target_user} deleted.")
    return redirect('/')

# --- Report Generators ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect('/')
    # Check Permission
    users = load_users()
    user_perms = users.get(session['user'], {}).get('permissions', [])
    # Admin always has access, others check permission
    if 'closing' not in user_perms and users.get(session['user'], {}).get('role') != 'admin':
        flash("Permission Denied"); return redirect('/')

    internal_ref_no = request.form['ref_no']
    download_token = request.form.get('download_token')

    if not internal_ref_no:
        flash("Ref No required.")
        return redirect(url_for('index'))

    active_session = get_authenticated_session("input2.clothing-cutting", "123456")
    if not active_session:
        flash("ERP Connection Failed.")
        return redirect(url_for('index'))

    report_url = 'http://180.92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload_template = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'cbo_floor_id': '0', 'cbo_buyer_name': '0', 'txt_internal_ref_no': internal_ref_no, 'reportType': '3'}
    found_data = None
   
    for year in ['2025', '2024']:
        for company_id in range(1, 6):
            payload = payload_template.copy()
            payload['cbo_year_selection'] = year
            payload['cbo_company_name'] = str(company_id)
            try:
                response = active_session.post(report_url, data=payload, timeout=300)
                if response.status_code == 200 and "Data not Found" not in response.text:
                    found_data = response.text
                    break
            except requests.exceptions.RequestException:
                continue
        if found_data:
            break
           
    if not found_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))

    report_data = parse_report_data(found_data)
    if not report_data:
        flash(f"Data parsing error for: {internal_ref_no}")
        return redirect(url_for('index'))

    excel_file_stream = create_formatted_excel_report(report_data, internal_ref_no)
    
    if excel_file_stream:
        update_stats(internal_ref_no)
        response = make_response(send_file(
            excel_file_stream,
            as_attachment=True,
            download_name=f"Closing-Report-{internal_ref_no.replace('/', '_')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        if download_token:
            response.set_cookie('download_token', download_token, max_age=60, path='/')
        return response
    else:
        flash("Excel generation failed.")
        return redirect(url_for('index'))

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect('/')
    users = load_users()
    user_perms = users.get(session['user'], {}).get('permissions', [])
    if 'po' not in user_perms and users.get(session['user'], {}).get('role') != 'admin':
        flash("Permission Denied"); return redirect('/')

    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)
    
    all_data = []
    meta = {'buyer': 'N/A', 'style': 'N/A'}
    
    files = request.files.getlist('pdf_files')
    for f in files:
        if not f.filename: continue
        path = os.path.join(UPLOAD_FOLDER, f.filename)
        f.save(path)
        d, m = extract_data_dynamic(path)
        if m['buyer'] != 'N/A': meta = m
        all_data.extend(d)
        
    if not all_data: return render_template_string(PO_TEMPLATE, message="No Data Found", tables=[])
    
    # Process DataFrame
    df = pd.DataFrame(all_data)
    df['Color'] = df['Color'].str.strip()
    df = df[df['Color']!=""]
    tables = []
    grand_total = 0
    
    for color in df['Color'].unique():
        cdf = df[df['Color']==color]
        piv = cdf.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        piv = piv[sort_sizes(piv.columns.tolist())]
        piv['Total'] = piv.sum(axis=1)
        grand_total += piv['Total'].sum()
        
        # Add Summary Rows
        act = piv.sum(); act.name='Actual Qty'
        p3 = (act * 1.03).round().astype(int); p3.name='3% Order Qty'
        piv = pd.concat([piv, act.to_frame().T, p3.to_frame().T])
        
        html = piv.reset_index().to_html(classes='table table-bordered table-striped', index=False)
        
        # HTML Injections for PO Styling
        html = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', html)
        html = html.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
        html = html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        html = html.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
        html = html.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
        html = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', html)

        tables.append({'color': color, 'table': html})

    return render_template_string(PO_TEMPLATE, tables=tables, meta=meta, grand_total=f"{grand_total:,}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
