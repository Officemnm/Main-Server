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

# --- Flask Library Imports ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# Configuration (For PO Files)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Session Timeout Configuration (30 Minutes) ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# ==============================================================================
# Helper Functions: Stats & History (JSON)
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
ACCESSORIES_DB_FILE = 'accessories_db.json' 

# --- User Management Functions ---
def load_users():
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"]
        }
    }
    
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump(default_users, f, indent=4)
        return default_users
    
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return default_users

def save_users(users_data):
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=4)

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"downloads": [], "last_booking": "None"}
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"downloads": [], "last_booking": "None"}

def save_stats(data):
    with open(STATS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def update_stats(ref_no, username):
    data = load_stats()
    now = datetime.now()
    new_record = {
        "ref": ref_no,
        "user": username,
        "date": now.strftime('%Y-%m-%d'),
        "time": now.strftime('%I:%M %p'),
        "iso_time": now.isoformat()
    }
    data['downloads'].insert(0, new_record)
    data['last_booking'] = ref_no
    save_stats(data)

def get_dashboard_summary():
    data = load_stats()
    downloads = data.get('downloads', [])
    last_booking = data.get('last_booking', 'N/A')
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    month_str = now.strftime('%Y-%m')
    
    today_count = 0
    month_count = 0
    
    for d in downloads:
        try:
            dt = datetime.fromisoformat(d.get('iso_time', datetime.now().isoformat()))
            if dt.strftime('%Y-%m-%d') == today_str:
                today_count += 1
            if dt.strftime('%Y-%m') == month_str:
                month_count += 1
        except: pass
            
    return {
        "today": today_count,
        "month": month_count,
        "last_booking": last_booking,
        "history": downloads 
    }

# --- Accessories Database Functions ---
def load_accessories_db():
    if not os.path.exists(ACCESSORIES_DB_FILE):
        return {}
    try:
        with open(ACCESSORIES_DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_accessories_db(data):
    with open(ACCESSORIES_DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ==============================================================================
# Logic Part: PURCHASE ORDER SHEET PARSER
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
# Logic Part: CLOSING REPORT API
# ==============================================================================
def get_authenticated_session(username, password):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    try:
        response = session_req.post(login_url, data=login_payload, timeout=300)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            return session_req
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def fetch_closing_report_data(internal_ref_no):
    active_session = get_authenticated_session("input2.clothing-cutting", "123456")
    if not active_session: return None

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
            except: continue
        if found_data: break
    
    if found_data:
        return parse_report_data(found_data)
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

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    # Styles
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
# CSS & HTML Templates (Redesigned based on Video - Dark Theme)
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-dark: #0f172a;       /* Deep Slate/Black like video bg */
            --card-dark: #1e293b;     /* Lighter slate for cards */
            --text-main: #f8fafc;     /* White/Light Gray text */
            --text-muted: #94a3b8;    /* Muted text */
            --accent-blue: #3b82f6;   /* Bright Blue */
            --accent-purple: #8b5cf6; /* Purple */
            --border-color: #334155;  /* Subtle border */
            --input-bg: #020617;      /* Very dark input bg */
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        
        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-dark); }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-blue); }

        /* Login & Center Container */
        .center-container {
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 20px;
        }
        
        .glass-card {
            background: var(--card-dark);
            border: 1px solid var(--border-color);
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
            width: 100%; max-width: 420px;
        }

        h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; color: white; }
        p.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 30px; }

        /* Forms & Inputs */
        .input-group { margin-bottom: 20px; text-align: left; }
        .input-group label {
            display: block; font-size: 13px; color: var(--text-muted);
            margin-bottom: 8px; font-weight: 500;
        }
        
        input[type="text"], input[type="password"], input[type="file"], input[type="number"], select {
            width: 100%; padding: 12px 16px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: white; font-size: 14px;
            transition: all 0.2s;
            outline: none;
        }
        input:focus, select:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }

        /* Buttons */
        button {
            width: 100%; padding: 12px;
            background: linear-gradient(to right, var(--accent-blue), var(--accent-purple));
            color: white; border: none; border-radius: 8px;
            font-size: 14px; font-weight: 600; cursor: pointer;
            transition: opacity 0.2s; margin-top: 10px;
        }
        button:hover { opacity: 0.9; }
        
        /* Dashboard Layout (Sidebar + Content) */
        .dashboard-container { display: flex; min-height: 100vh; }
        
        .sidebar {
            width: 260px; background: var(--card-dark);
            border-right: 1px solid var(--border-color);
            display: flex; flex-direction: column; padding: 20px;
            position: fixed; height: 100%; left: 0; top: 0; z-index: 100;
        }
        
        .sidebar-brand {
            font-size: 18px; font-weight: 800; color: white;
            margin-bottom: 40px; display: flex; align-items: center; gap: 10px;
            padding-left: 10px;
        }
        
        .nav-link {
            display: flex; align-items: center; padding: 12px 15px;
            color: var(--text-muted); text-decoration: none;
            border-radius: 8px; margin-bottom: 5px; font-size: 14px;
            transition: all 0.2s; cursor: pointer;
        }
        .nav-link:hover, .nav-link.active {
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-blue);
        }
        .nav-link i { width: 20px; margin-right: 12px; }

        .main-content {
            flex: 1; margin-left: 260px; padding: 30px;
            background: var(--bg-dark);
        }

        /* Stats Cards (Like Video) */
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }
        .stat-card {
            background: var(--card-dark); padding: 20px;
            border-radius: 12px; border: 1px solid var(--border-color);
            display: flex; align-items: center; justify-content: space-between;
        }
        .stat-info h3 { font-size: 24px; color: white; margin-bottom: 4px; }
        .stat-info p { font-size: 13px; color: var(--text-muted); }
        .stat-icon {
            font-size: 20px; color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.1); padding: 10px; border-radius: 8px;
        }

        /* Footer */
        .footer-credit {
            margin-top: auto; padding-top: 20px;
            text-align: center; font-size: 12px; color: var(--text-muted);
            border-top: 1px solid var(--border-color);
        }

        /* Loading & Success Animation */
        #loading-overlay {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(15, 23, 42, 0.9); z-index: 9999;
            flex-direction: column; justify-content: center; align-items: center;
        }
        .spinner {
            width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1);
            border-top-color: var(--accent-blue); border-radius: 50%;
            animation: spin 1s linear infinite; margin-bottom: 20px;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .success-checkmark { display: none; width: 80px; height: 80px; }
        .check-icon { font-size: 60px; color: #10b981; animation: popIn 0.5s ease; }
        @keyframes popIn { 0% { transform: scale(0); } 80% { transform: scale(1.1); } 100% { transform: scale(1); } }
        
        /* Tables (Dark Mode) */
        .custom-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .custom-table th { text-align: left; padding: 15px; color: var(--text-muted); border-bottom: 1px solid var(--border-color); font-size: 13px; text-transform: uppercase; }
        .custom-table td { padding: 15px; border-bottom: 1px solid var(--border-color); font-size: 14px; }
        .custom-table tr:last-child td { border-bottom: none; }
        
        .btn-action { padding: 6px 10px; border-radius: 6px; font-size: 12px; margin-right: 5px; width: auto; display: inline-block; }
        .btn-edit { background: #f59e0b; }
        .btn-del { background: #ef4444; }

        /* Print Override */
        @media print {
            body { background: white; color: black; }
            .no-print, .sidebar { display: none !important; }
            .main-content { margin: 0; padding: 0; }
            .glass-card { box-shadow: none; border: none; }
        }
    </style>
"""

# --- Report Preview Template (Logic Unchanged, Visuals adapted for container) ---
CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Closing Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; padding: 30px 0; font-family: 'Segoe UI', sans-serif; }
        .paper-container { max-width: 1400px; margin: 0 auto; background: white; padding: 40px; border-radius: 4px; min-height: 100vh; }
        
        /* Print Styles from original code preserved */
        .company-header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        .report-title { font-size: 1.1rem; font-weight: 600; text-transform: uppercase; }
        .booking-box { background: #2c3e50; color: white; padding: 10px; text-align: right; border-radius: 4px; }
        .table th { background: #fff !important; color: #000 !important; border: 1px solid #000; font-weight: 900; }
        .table td { border: 1px solid #000; font-weight: 600; }
        .col-3pct { background-color: #B9C2DF !important; }
        .col-input { background-color: #C4D09D !important; }
        .color-header { background-color: #2c3e50; color: white; padding: 10px; font-weight: 800; }
        
        .action-bar { position: fixed; top: 0; right: 0; padding: 20px; background: rgba(15,23,42,0.9); width: 100%; display: flex; justify-content: flex-end; gap: 10px; z-index: 999; backdrop-filter: blur(5px); }
        .btn-custom { border-radius: 50px; padding: 8px 25px; font-weight: 600; text-decoration: none; display: inline-block; border: none; }
        .btn-back { background: #64748b; color: white; }
        .btn-excel { background: #10b981; color: white; }
        .btn-print { background: #3b82f6; color: white; }

        @media print {
            body { background: white; padding: 0; }
            .paper-container { width: 100%; max-width: 100%; padding: 0; box-shadow: none; }
            .action-bar { display: none; }
            .booking-box, .color-header { -webkit-print-color-adjust: exact; background: #2c3e50 !important; color: white !important; }
            .col-3pct { -webkit-print-color-adjust: exact; background: #B9C2DF !important; }
            .col-input { -webkit-print-color-adjust: exact; background: #C4D09D !important; }
        }
    </style>
</head>
<body>
    <div class="action-bar no-print">
        <a href="/" class="btn-custom btn-back">Back to Dashboard</a>
        <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn-custom btn-excel">Download Excel</a>
        <button onclick="window.print()" class="btn-custom btn-print">Print Report</button>
    </div>

    <div class="paper-container">
        <div class="company-header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div class="report-title">CLOSING REPORT [ INPUT SECTION ]</div>
            <div>Date: <span id="date"></span></div>
        </div>

        {% if report_data %}
        <div class="d-flex justify-content-between align-items-end mb-3">
            <div>
                <div class="fs-5 fw-bold">Buyer: {{ report_data[0].buyer }}</div>
                <div class="fs-5 fw-bold">Style: {{ report_data[0].style }}</div>
            </div>
            <div class="booking-box">
                <div class="small fw-bold">IR/IB NO</div>
                <div class="fs-3 fw-bold">{{ ref_no }}</div>
            </div>
        </div>

        {% for block in report_data %}
        <div class="mb-4">
            <div class="color-header">COLOR: {{ block.color }}</div>
            <table class="table text-center">
                <thead>
                    <tr>
                        <th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th>
                        <th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th>
                    </tr>
                </thead>
                <tbody>
                    {% set ns = namespace(t_3=0, t_ac=0, t_cut=0, t_inp=0, t_bal=0, t_sp=0) %}
                    {% for i in range(block.headers|length) %}
                        {% set act = block.gmts_qty[i]|replace(',', '')|int %}
                        {% set q3 = (act * 1.03)|round|int %}
                        {% set cut = block.cutting_qc[i]|replace(',', '')|int if i < block.cutting_qc|length else 0 %}
                        {% set inp = block.sewing_input[i]|replace(',', '')|int if i < block.sewing_input|length else 0 %}
                        {% set bal = cut - inp %}
                        {% set sp = inp - q3 %}
                        
                        {% set ns.t_3 = ns.t_3 + q3 %}
                        {% set ns.t_ac = ns.t_ac + act %}
                        {% set ns.t_cut = ns.t_cut + cut %}
                        {% set ns.t_inp = ns.t_inp + inp %}
                        {% set ns.t_bal = ns.t_bal + bal %}
                        {% set ns.t_sp = ns.t_sp + sp %}
                        
                        <tr>
                            <td>{{ block.headers[i] }}</td>
                            <td class="col-3pct">{{ q3 }}</td>
                            <td>{{ act }}</td>
                            <td>{{ cut }}</td>
                            <td class="col-input">{{ inp }}</td>
                            <td class="fw-bold text-danger">{{ bal }}</td>
                            <td style="color:{{ 'green' if sp >=0 else 'red' }}">{{ sp }}</td>
                            <td>{{ "%.2f"|format((sp/q3)*100) if q3>0 else '0' }}%</td>
                        </tr>
                    {% endfor %}
                    <tr class="fw-bold" style="border-top:2px solid black;">
                        <td>TOTAL</td>
                        <td>{{ ns.t_3 }}</td><td>{{ ns.t_ac }}</td><td>{{ ns.t_cut }}</td>
                        <td>{{ ns.t_inp }}</td><td>{{ ns.t_bal }}</td><td>{{ ns.t_sp }}</td>
                        <td>{{ "%.2f"|format((ns.t_sp/ns.t_3)*100) if ns.t_3>0 else '0' }}%</td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endfor %}
        
        <div class="text-center mt-5 pt-3 border-top border-dark fw-bold">Report Generated By Mehedi Hasan</div>
        {% endif %}
    </div>
    <script>document.getElementById('date').innerText = new Date().toLocaleDateString('en-GB');</script>
</body>
</html>
"""

# --- Accessories Search Template (Dark) ---
ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Search</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="dashboard-container">
        <div class="sidebar">
            <div class="sidebar-brand"><i class="fas fa-layer-group"></i> Accessories</div>
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Home</a>
            <a href="/logout" class="nav-link" style="margin-top:auto; color:#ef4444;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>

        <div class="main-content">
            <h1 style="color:white; margin-bottom:30px;">Find Booking</h1>
            
            <div class="glass-card" style="max-width:500px; margin:0 auto;">
                <p class="subtitle">Enter Booking Number to Manage Challan</p>
                <form action="/admin/accessories/input" method="post">
                    <div class="input-group">
                        <label>Booking Reference No</label>
                        <input type="text" name="ref_no" placeholder="e.g. Booking-123..." required>
                    </div>
                    <button type="submit">Proceed <i class="fas fa-arrow-right"></i></button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- Accessories Input/Edit Template (Dark) ---
ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Manage Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-checkmark"><i class="fas fa-check-circle check-icon"></i></div>
        <div id="loading-text" style="color:white; font-weight:600;">Saving...</div>
    </div>

    <div class="dashboard-container">
        <div class="sidebar">
            <div class="sidebar-brand"><i class="fas fa-edit"></i> Challan Entry</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-search"></i> New Search</a>
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Dashboard</a>
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>

        <div class="main-content">
            <div class="glass-card" style="max-width:600px; margin:0 auto;">
                <h1>New Challan</h1>
                <div style="background:var(--input-bg); padding:15px; border-radius:8px; margin-bottom:20px; border:1px solid var(--border-color);">
                    <div style="color:var(--text-muted); font-size:12px;">BOOKING REF</div>
                    <div style="color:var(--accent-blue); font-weight:bold; font-size:16px;">{{{{ ref }}}}</div>
                    <div style="display:flex; justify-content:space-between; margin-top:10px;">
                        <div><small>Buyer:</small> <b>{{{{ buyer }}}}</b></div>
                        <div><small>Style:</small> <b>{{{{ style }}}}</b></div>
                    </div>
                </div>

                <form action="/admin/accessories/save" method="post" onsubmit="showAnim('Saving...')">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    
                    <div class="input-group">
                        <label>Item Type</label>
                        <select name="item_type">
                            <option value="" disabled selected>-- Select Type --</option>
                            <option value="Top">Top</option>
                            <option value="Bottom">Bottom</option>
                        </select>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                        <div class="input-group">
                            <label>Color</label>
                            <select name="color" required>
                                <option value="" disabled selected>Select Color</option>
                                {{% for c in colors %}}
                                <option value="{{{{ c }}}}">{{{{ c }}}}</option>
                                {{% endfor %}}
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Line No</label>
                            <input type="text" name="line_no" placeholder="Line-12" required>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                        <div class="input-group">
                            <label>Size (Optional)</label>
                            <input type="text" name="size" value="-" placeholder="XL">
                        </div>
                        <div class="input-group">
                            <label>Quantity</label>
                            <input type="number" name="qty" required>
                        </div>
                    </div>

                    <button type="submit">Save Entry</button>
                </form>
                
                <div style="text-align:center; margin-top:20px;">
                    <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:var(--accent-purple); text-decoration:none; font-size:14px;">View Report Only</a>
                </div>
            </div>
        </div>
    </div>
    <script>
        function showAnim(msg) {{
            document.getElementById('loading-text').innerText = msg;
            document.getElementById('loading-overlay').style.display = 'flex';
            setTimeout(() => {{
                document.querySelector('.spinner').style.display = 'none';
                document.querySelector('.success-checkmark').style.display = 'block';
            }}, 600);
            return true;
        }}
    </script>
</body>
</html>
"""

ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Edit Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="dashboard-container">
        <div class="main-content" style="margin-left:0; display:flex; justify-content:center;">
            <div class="glass-card" style="max-width:500px;">
                <h1>Edit Challan</h1>
                <p class="subtitle">Update entry for {{{{ ref }}}}</p>
                <form action="/admin/accessories/update" method="post">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    <input type="hidden" name="index" value="{{{{ index }}}}">
                    
                    <div class="input-group"><label>Line No</label><input type="text" name="line_no" value="{{{{ item.line }}}}" required></div>
                    <div class="input-group"><label>Color</label><input type="text" name="color" value="{{{{ item.color }}}}" required></div>
                    <div class="input-group"><label>Size</label><input type="text" name="size" value="{{{{ item.size }}}}" required></div>
                    <div class="input-group"><label>Quantity</label><input type="number" name="qty" value="{{{{ item.qty }}}}" required></div>
                    
                    <button type="submit">Update</button>
                </form>
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="display:block; text-align:center; margin-top:15px; color:var(--text-muted);">Cancel</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- Accessories Report Template (White Paper Look) ---
ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Delivery Report</title>
    <style>
        body { font-family: sans-serif; background: #555; padding: 20px; }
        .paper { background: white; max-width: 900px; margin: 0 auto; padding: 30px; min-height: 90vh; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .title { background: #2c3e50; color: white; padding: 5px 20px; display: inline-block; font-weight: bold; }
        .info-grid { display: flex; justify-content: space-between; margin-bottom: 20px; }
        .box { border: 1px solid #000; padding: 10px; flex: 1; margin-right: 10px; }
        .table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        .table th { background: #2c3e50; color: white; border: 1px solid #000; padding: 8px; }
        .table td { border: 1px solid #000; padding: 5px; text-align: center; }
        .no-print { margin-bottom: 10px; text-align: right; }
        .btn { padding: 8px 15px; background: #333; color: white; text-decoration: none; border: none; cursor: pointer; }
        
        @media print {
            body { background: white; padding: 0; }
            .no-print { display: none; }
            .paper { box-shadow: none; margin: 0; max-width: 100%; }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div class="no-print">
        <a href="/admin/accessories/input?ref_no={{ ref }}" onclick="document.forms[0].submit(); return false;" class="btn">Add New</a>
        <a href="/admin/accessories" class="btn">Back</a>
        <button onclick="window.print()" class="btn">Print</button>
        <form action="/admin/accessories/input" method="post" style="display:none;"><input type="hidden" name="ref_no" value="{{ ref }}"></form>
    </div>

    <div class="paper">
        <div class="header">
            <h1 style="margin:0; color:#2c3e50;">COTTON CLOTHING BD LIMITED</h1>
            <p style="margin:5px 0;">Kazi Tower, Tongi, Gazipur</p>
            <div class="title">ACCESSORIES DELIVERY REPORT</div>
        </div>

        <div class="info-grid">
            <div class="box">
                <div><b>Booking:</b> {{ ref }}</div>
                <div><b>Buyer:</b> {{ buyer }}</div>
                <div><b>Style:</b> {{ style }}</div>
                <div><b>Date:</b> {{ today }}</div>
            </div>
            <div style="flex:0.5; text-align:right;">
                <div><b>Store:</b> General Store</div>
                <div><b>To:</b> Cutting</div>
                <div><b>Type:</b> {{ item_type if item_type else 'N/A' }}</div>
            </div>
        </div>

        <div style="border:1px solid #000; padding:10px; background:#f9f9f9; font-size:12px; margin-bottom:20px;">
            <b>Line Summary:</b> 
            {% for line, qty in line_summary.items() %}
                [{{ line }}: {{ qty }}] 
            {% endfor %}
            <div style="text-align:right; margin-top:5px;"><b>Total Deliveries:</b> {{ count }}</div>
        </div>

        <table class="table">
            <thead>
                <tr>
                    <th>Date</th><th>Line</th><th>Color</th><th>Size</th><th>Status</th><th>Qty</th>
                    {% if session.role == 'admin' %}<th class="no-print">Action</th>{% endif %}
                </tr>
            </thead>
            <tbody>
                {% set ns = namespace(total=0) %}
                {% for item in challans %}
                {% set ns.total = ns.total + item.qty|int %}
                <tr>
                    <td>{{ item.date }}</td>
                    <td style="font-weight:bold;">{{ item.line }}</td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td style="color:green; font-weight:bold;">{{ item.status }}</td>
                    <td><b>{{ item.qty }}</b></td>
                    {% if session.role == 'admin' %}
                    <td class="no-print">
                        <a href="/admin/accessories/edit?ref={{ ref }}&index={{ loop.index0 }}"><i class="fas fa-edit"></i></a>
                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete?');">
                            <input type="hidden" name="ref" value="{{ ref }}">
                            <input type="hidden" name="index" value="{{ loop.index0 }}">
                            <button style="border:none; background:none; color:red; cursor:pointer;"><i class="fas fa-trash"></i></button>
                        </form>
                    </td>
                    {% endif %}
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div style="text-align:right; margin-top:20px; font-size:18px; font-weight:bold; padding:10px; border:2px solid #000; display:inline-block; float:right;">
            TOTAL: {{ ns.total }}
        </div>
        <div style="clear:both;"></div>

        <div style="margin-top:50px; display:flex; justify-content:space-between; text-align:center; font-weight:bold;">
            <div style="border-top:1px solid #000; width:150px;">Store Incharge</div>
            <div style="border-top:1px solid #000; width:150px;">Received By</div>
            <div style="border-top:1px solid #000; width:150px;">Cutting Incharge</div>
        </div>
        <div style="text-align:center; margin-top:30px; font-size:10px; border-top:1px solid #ccc;">Generated by Mehedi Hasan</div>
    </div>
</body>
</html>
"""

# --- Login Template (Dark) ---
LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login System</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card text-center">
            <h1 style="color:white; margin-bottom:5px;">Welcome Back</h1>
            <p class="subtitle">Please sign in to continue</p>
            
            <form action="/login" method="post">
                <div class="input-group">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="Enter username" required>
                </div>
                <div class="input-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="Enter password" required>
                </div>
                <button type="submit">Sign In</button>
            </form>
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top:20px; padding:10px; background:rgba(239, 68, 68, 0.2); border:1px solid #ef4444; color:#fca5a5; border-radius:8px; font-size:13px;">
                        {{{{ messages[0] }}}}
                    </div>
                {{% endif %}}
            {{% endwith %}}
            
            <div class="footer-credit" style="margin-top:30px;">© Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

# --- Common Dashboard Layout (Sidebar + Content) ---
DASHBOARD_LAYOUT = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard</title>
    {COMMON_STYLES}
    <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-checkmark"><i class="fas fa-check-circle check-icon"></i></div>
    </div>

    <div class="dashboard-container">
        <div class="sidebar">
            <div class="sidebar-brand">
                <div style="width:30px; height:30px; background:linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius:8px;"></div>
                Dashboard
            </div>
            
            <div style="margin-bottom:10px; color:var(--text-muted); font-size:11px; font-weight:600; text-transform:uppercase; padding-left:10px;">Menu</div>
            
            {{% if 'closing' in session.permissions %}}
            <div class="nav-link" onclick="showTab('closing', this)"><i class="fas fa-file-alt"></i> Closing Report</div>
            {{% endif %}}
            
            {{% if 'po_sheet' in session.permissions %}}
            <div class="nav-link" onclick="showTab('po', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            {{% endif %}}
            
            {{% if 'accessories' in session.permissions %}}
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-layer-group"></i> Accessories</a>
            {{% endif %}}
            
            {{% if session.role == 'admin' %}}
            <div class="nav-link" onclick="showTab('users', this)"><i class="fas fa-users"></i> User Manage</div>
            <div class="nav-link" onclick="showTab('history', this)"><i class="fas fa-history"></i> History</div>
            {{% endif %}}
            
            <a href="/logout" class="nav-link" style="margin-top:auto; color:#ef4444;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
            
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>

        <div class="main-content">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
                <div>
                    <h1>Overview</h1>
                    <p style="color:var(--text-muted); font-size:14px; margin:0;">Welcome back, {{{{ session.user }}}}</p>
                </div>
                <div style="background:var(--card-dark); padding:8px 15px; border-radius:20px; border:1px solid var(--border-color); font-size:13px;">
                    <i class="fas fa-calendar-alt text-primary"></i> <span id="currentDate"></span>
                </div>
            </div>
            
            <div id="stats-section">
                {{% if session.role == 'admin' and stats %}}
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-info"><h3>{{{{ stats.today }}}}</h3><p>Today's Reports</p></div>
                        <div class="stat-icon"><i class="fas fa-file-download"></i></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-info"><h3>{{{{ stats.month }}}}</h3><p>Monthly Total</p></div>
                        <div class="stat-icon"><i class="fas fa-calendar-check"></i></div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-info"><h3>{{{{ stats.last_booking }}}}</h3><p>Last Booking</p></div>
                        <div class="stat-icon"><i class="fas fa-history"></i></div>
                    </div>
                </div>
                
                <div class="glass-card" style="max-width:100%; height:200px; display:flex; align-items:flex-end; gap:10px; padding:20px; margin-bottom:30px;">
                     <div style="flex:1; background:#334155; height:40%; border-radius:4px;"></div>
                     <div style="flex:1; background:var(--accent-blue); height:70%; border-radius:4px;"></div>
                     <div style="flex:1; background:#334155; height:50%; border-radius:4px;"></div>
                     <div style="flex:1; background:var(--accent-purple); height:90%; border-radius:4px;"></div>
                     <div style="flex:1; background:#334155; height:60%; border-radius:4px;"></div>
                     <div style="flex:1; background:var(--accent-blue); height:80%; border-radius:4px;"></div>
                </div>
                {{% endif %}}
            </div>

            <div id="closing-section" style="display:none;">
                <div class="glass-card" style="max-width:500px;">
                    <h2 style="color:white; margin-bottom:20px;">Generate Closing Report</h2>
                    <form action="/generate-report" method="post" onsubmit="showLoading()">
                        <div class="input-group">
                            <label>Internal Reference No</label>
                            <input type="text" name="ref_no" placeholder="e.g. DFL/24/123" required>
                        </div>
                        <button type="submit">Generate Report</button>
                    </form>
                </div>
            </div>

            <div id="po-section" style="display:none;">
                <div class="glass-card" style="max-width:500px;">
                    <h2 style="color:white; margin-bottom:20px;">PO Sheet Generator</h2>
                    <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoading()">
                        <div class="input-group">
                            <label>Upload PDF Files (Booking & PO)</label>
                            <input type="file" name="pdf_files" multiple accept=".pdf" required>
                        </div>
                        <button type="submit">Process Files</button>
                    </form>
                </div>
            </div>

            <div id="users-section" style="display:none;">
                <div class="glass-card" style="max-width:100%;">
                    <h2 style="color:white; margin-bottom:20px;">User Management</h2>
                    <div style="background:var(--input-bg); padding:20px; border-radius:8px; margin-bottom:20px;">
                        <h4 style="color:white; margin-bottom:15px;">Create / Update User</h4>
                        <form id="userForm">
                            <input type="hidden" id="action_type" value="create">
                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:15px;">
                                <input type="text" id="u_name" placeholder="Username" required>
                                <input type="text" id="u_pass" placeholder="Password" required>
                            </div>
                            <div style="color:var(--text-muted); margin-bottom:10px;">Permissions:</div>
                            <div style="display:flex; gap:15px; margin-bottom:15px;">
                                <label style="display:flex; align-items:center; color:white;"><input type="checkbox" id="p_closing" value="closing" checked> Closing</label>
                                <label style="display:flex; align-items:center; color:white;"><input type="checkbox" id="p_po" value="po_sheet"> PO Sheet</label>
                                <label style="display:flex; align-items:center; color:white;"><input type="checkbox" id="p_acc" value="accessories"> Accessories</label>
                            </div>
                            <button type="button" onclick="saveUser()" id="saveBtn">Create User</button>
                        </form>
                    </div>
                    <table class="custom-table">
                        <thead><tr><th>User</th><th>Role</th><th>Permissions</th><th>Action</th></tr></thead>
                        <tbody id="userTableBody"></tbody>
                    </table>
                </div>
            </div>

            <div id="history-section" style="display:none;">
                 <div class="glass-card" style="max-width:100%;">
                    <h2 style="color:white;">Activity Log</h2>
                    <table class="custom-table">
                        <thead><tr><th>Date</th><th>Time</th><th>User</th><th>Reference</th></tr></thead>
                        <tbody>
                            {{% if stats and stats.history %}}
                            {{% for log in stats.history %}}
                            <tr>
                                <td>{{{{ log.date }}}}</td>
                                <td>{{{{ log.time }}}}</td>
                                <td>{{{{ log.user }}}}</td>
                                <td style="color:var(--accent-blue); font-weight:bold;">{{{{ log.ref }}}}</td>
                            </tr>
                            {{% endfor %}}
                            {{% endif %}}
                        </tbody>
                    </table>
                 </div>
            </div>

        </div>
    </div>

    <script>
        document.getElementById('currentDate').innerText = new Date().toLocaleDateString('en-GB', {{ day: 'numeric', month: 'short', year: 'numeric' }});

        function showLoading() {{
            document.getElementById('loading-overlay').style.display = 'flex';
            setTimeout(() => {{
                document.querySelector('.spinner').style.display = 'none';
                document.querySelector('.success-checkmark').style.display = 'block';
                setTimeout(() => {{ 
                   document.getElementById('loading-overlay').style.display = 'none';
                   document.querySelector('.spinner').style.display = 'block';
                   document.querySelector('.success-checkmark').style.display = 'none';
                }}, 1500);
            }}, 2000);
        }}

        function showTab(tabId, el) {{
            // Reset Sidebar active state
            document.querySelectorAll('.nav-link').forEach(e => e.classList.remove('active'));
            if(el) el.classList.add('active');

            // Hide all sections
            document.querySelectorAll('#stats-section, #closing-section, #po-section, #users-section, #history-section').forEach(s => s.style.display = 'none');

            if(tabId === 'closing') document.getElementById('closing-section').style.display = 'block';
            else if(tabId === 'po') document.getElementById('po-section').style.display = 'block';
            else if(tabId === 'users') {{
                document.getElementById('users-section').style.display = 'block';
                loadUsers();
            }}
            else if(tabId === 'history') document.getElementById('history-section').style.display = 'block';
            else document.getElementById('stats-section').style.display = 'block';
        }}

        // User Management Scripts
        function loadUsers() {{
            fetch('/admin/get-users').then(r => r.json()).then(data => {{
                let html = '';
                for(let u in data) {{
                    let role = data[u].role;
                    let perms = data[u].permissions ? data[u].permissions.join(', ') : '-';
                    let btns = role === 'admin' ? '<span style="opacity:0.5">Admin</span>' : 
                        `<div class="btn-action btn-edit" onclick="editU('${{u}}', '${{data[u].password}}', '${{perms}}')">Edit</div>` +
                        `<div class="btn-action btn-del" onclick="delU('${{u}}')">Del</div>`;
                    html += `<tr><td>${{u}}</td><td>${{role}}</td><td>${{perms}}</td><td>${{btns}}</td></tr>`;
                }}
                document.getElementById('userTableBody').innerHTML = html;
            }});
        }}

        function saveUser() {{
            let u = document.getElementById('u_name').value;
            let p = document.getElementById('u_pass').value;
            let perms = [];
            if(document.getElementById('p_closing').checked) perms.push('closing');
            if(document.getElementById('p_po').checked) perms.push('po_sheet');
            if(document.getElementById('p_acc').checked) perms.push('accessories');
            let action = document.getElementById('action_type').value;

            if(!u || !p) return swal("Error", "Fill all fields", "error");

            fetch('/admin/save-user', {{
                method: 'POST', headers: {{'Content-Type':'application/json'}},
                body: JSON.stringify({{username:u, password:p, permissions:perms, action_type:action}})
            }}).then(r=>r.json()).then(d=>{{
                if(d.status==='success') {{ swal("Success", d.message, "success"); loadUsers(); document.getElementById('userForm').reset(); }}
                else swal("Error", d.message, "error");
            }});
        }}
        
        function editU(u, p, perms) {{
            document.getElementById('u_name').value = u;
            document.getElementById('u_name').readOnly = true;
            document.getElementById('u_pass').value = p;
            document.getElementById('action_type').value = 'update';
            document.getElementById('saveBtn').innerText = 'Update User';
            document.getElementById('p_closing').checked = perms.includes('closing');
            document.getElementById('p_po').checked = perms.includes('po_sheet');
            document.getElementById('p_acc').checked = perms.includes('accessories');
        }}
        
        function delU(u) {{
            if(confirm('Delete user?')) {{
                fetch('/admin/delete-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}})}})
                .then(r=>r.json()).then(d=>{{ loadUsers(); }});
            }}
        }}
    </script>
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        # Unified Dashboard for both Admin and User
        # Logic: If admin, show stats. If user, show welcome but no stats unless we want to.
        # Permissions decide what they see in sidebar.
        stats = {}
        if session.get('role') == 'admin':
            stats = get_dashboard_summary()
        
        return render_template_string(DASHBOARD_LAYOUT, stats=stats)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    users_db = load_users()

    if username in users_db and users_db[username]['password'] == password:
        session.permanent = True
        session['logged_in'] = True
        session['user'] = username
        session['role'] = users_db[username]['role']
        session['permissions'] = users_db[username].get('permissions', [])
        return redirect(url_for('index'))
    else:
        flash('Invalid Credentials')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully')
    return redirect(url_for('index'))

# --- USER MANAGEMENT ROUTES (API) ---

@app.route('/admin/get-users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({})
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    permissions = data.get('permissions', [])
    action = data.get('action_type')
    
    if not username or not password:
         return jsonify({'status': 'error', 'message': 'Invalid Data'})

    users_db = load_users()
    
    if action == 'create':
        if username in users_db:
            return jsonify({'status': 'error', 'message': 'User already exists!'})
        users_db[username] = {
            "password": password,
            "role": "user",
            "permissions": permissions
        }
    elif action == 'update':
        if username not in users_db:
            return jsonify({'status': 'error', 'message': 'User not found!'})
        users_db[username]['password'] = password
        users_db[username]['permissions'] = permissions
    
    save_users(users_db)
    return jsonify({'status': 'success', 'message': 'User saved successfully!'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    username = request.json.get('username')
    users_db = load_users()
    
    if username == 'Admin':
         return jsonify({'status': 'error', 'message': 'Cannot delete Main Admin!'})

    if username in users_db:
        del users_db[username]
        save_users(users_db)
        return jsonify({'status': 'success', 'message': 'User deleted!'})
    
    return jsonify({'status': 'error', 'message': 'User not found'})

# --- CLOSING REPORT ROUTE ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if 'closing' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))

    internal_ref_no = request.form['ref_no']
    if not internal_ref_no: return redirect(url_for('index'))

    report_data = fetch_closing_report_data(internal_ref_no)

    if not report_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))

    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)

# ==============================================================================
# UPDATED: ACCESSORIES CHALLAN ROUTES
# ==============================================================================

# 1. Search Page (Direct Access)
@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    # Check permissions
    if 'accessories' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))
        
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

# 2. Input Form
@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no').strip()
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()

    if ref_no in db:
        data = db[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"No booking data found for {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        
        db[ref_no] = {
            "style": style,
            "buyer": buyer,
            "colors": colors,
            "item_type": "", 
            "challans": [] 
        }
        save_accessories_db(db)

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer)

# 3. Save Logic
@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if 'accessories' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))

    ref = request.form.get('ref')
    color = request.form.get('color')
    line = request.form.get('line_no')
    size = request.form.get('size')
    qty = request.form.get('qty')
    item_type = request.form.get('item_type') 
    
    db = load_accessories_db()
    
    if ref not in db:
        return redirect(url_for('accessories_search_page'))

    if item_type:
        db[ref]['item_type'] = item_type

    history = db[ref]['challans']
    for item in history:
        item['status'] = "✔"
    
    new_entry = {
        "date": datetime.now().strftime("%d-%m-%Y"),
        "line": line,
        "color": color,
        "size": size,
        "qty": qty,
        "status": "" 
    }
    
    history.append(new_entry)
    db[ref]['challans'] = history
    save_accessories_db(db)
    
    return redirect(url_for('accessories_print_view', ref=ref))

# 4. Print View
@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.args.get('ref')
    db = load_accessories_db()
    
    if ref not in db:
        return redirect(url_for('accessories_search_page'))
    
    data = db[ref]
    challans = data['challans']
    item_type = data.get('item_type', '')

    line_summary = {}
    for c in challans:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        if ln in line_summary: line_summary[ln] += q
        else: line_summary[ln] = q
    
    sorted_line_summary = dict(sorted(line_summary.items()))

    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref,
                                  buyer=data['buyer'],
                                  style=data['style'],
                                  item_type=item_type,
                                  challans=challans,
                                  line_summary=sorted_line_summary,
                                  count=len(challans),
                                  today=datetime.now().strftime("%d-%m-%Y"))

# 5. Delete Route (RESTRICTED TO ADMIN)
@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if session.get('role') != 'admin':
        flash("Only Admin can delete records.")
        return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    try:
        index = int(request.form.get('index'))
    except:
        return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()
    if ref in db:
        challans = db[ref]['challans']
        if 0 <= index < len(challans):
            del challans[index]
            db[ref]['challans'] = challans
            save_accessories_db(db)
    
    return redirect(url_for('accessories_print_view', ref=ref))

# 6. Edit Page (RESTRICTED TO ADMIN)
@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in'): return redirect(url_for('index'))

    if session.get('role') != 'admin':
        flash("Only Admin can edit records.")
        return redirect(url_for('index'))
    
    ref = request.args.get('ref')
    try:
        index = int(request.args.get('index'))
    except:
        return redirect(url_for('accessories_search_page'))
        
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search_page'))
    
    challans = db[ref]['challans']
    if index < 0 or index >= len(challans):
         return redirect(url_for('accessories_print_view', ref=ref))
         
    item_to_edit = challans[index]
    
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item_to_edit)

# 7. Update Logic
@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    ref = request.form.get('ref')
    try:
        index = int(request.form.get('index'))
        qty = request.form.get('qty')
        line = request.form.get('line_no')
        color = request.form.get('color')
        size = request.form.get('size')
    except:
        return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()
    if ref in db:
        challans = db[ref]['challans']
        if 0 <= index < len(challans):
            challans[index]['qty'] = qty
            challans[index]['line'] = line
            challans[index]['color'] = color
            challans[index]['size'] = size
            db[ref]['challans'] = challans
            save_accessories_db(db)
            
    return redirect(url_for('accessories_print_view', ref=ref))


# --- EXCEL DOWNLOAD ROUTE ---
@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    internal_ref_no = request.args.get('ref_no')
    if not internal_ref_no: return redirect(url_for('index'))

    report_data = fetch_closing_report_data(internal_ref_no)
    
    if not report_data:
        flash(f"Error: {internal_ref_no}")
        return redirect(url_for('index'))

    excel_file_stream = create_formatted_excel_report(report_data, internal_ref_no)
    
    if excel_file_stream:
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        return make_response(send_file(excel_file_stream, as_attachment=True, download_name=f"Closing-Report-{internal_ref_no.replace('/', '_')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    else:
        return redirect(url_for('index'))

# --- PO SHEET REPORT ---
PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PO Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        @media print { .no-print { display:none; } }
        .table th { background: #2c3e50; color: white; }
    </style>
</head>
<body class="p-4">
    <div class="no-print mb-3 text-end">
        <a href="/" class="btn btn-secondary">Back</a>
        <button onclick="window.print()" class="btn btn-primary">Print</button>
    </div>
    <div class="text-center mb-4 border-bottom border-dark pb-2">
        <h2>COTTON CLOTHING BD LIMITED</h2>
        <h5>PO SUMMARY REPORT</h5>
    </div>
    {% if tables %}
        <div class="row mb-3">
            <div class="col-md-8">
                <div><b>Buyer:</b> {{ meta.buyer }}</div>
                <div><b>Style:</b> {{ meta.style }}</div>
                <div><b>Booking:</b> {{ meta.booking }}</div>
            </div>
            <div class="col-md-4 text-end">
                <div class="bg-dark text-white p-2 rounded">
                    <div class="small">Grand Total</div>
                    <div class="h2 mb-0">{{ grand_total }}</div>
                </div>
            </div>
        </div>
        {% for item in tables %}
            <div class="mb-4 break-inside-avoid">
                <div class="bg-light p-2 fw-bold border mb-2">COLOR: {{ item.color }}</div>
                {{ item.table | safe }}
            </div>
        {% endfor %}
        <div class="text-center mt-5 small">Report Generated by Mehedi Hasan</div>
    {% endif %}
</body>
</html>
"""

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    if 'po_sheet' not in session.get('permissions', []):
         return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    uploaded_files = request.files.getlist('pdf_files')
    all_data = []
    final_meta = { 'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A' }
    
    for file in uploaded_files:
        if file.filename == '': continue
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        data, meta = extract_data_dynamic(file_path)
        if meta['buyer'] != 'N/A': final_meta = meta
        if data: all_data.extend(data)
    
    if not all_data:
        return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No Data")

    df = pd.DataFrame(all_data)
    df['Color'] = df['Color'].str.strip()
    df = df[df['Color'] != ""]
    unique_colors = df['Color'].unique()
    
    final_tables = []
    grand_total_qty = 0

    for color in unique_colors:
        color_df = df[df['Color'] == color]
        pivot = color_df.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        
        existing_sizes = pivot.columns.tolist()
        sorted_sizes = sort_sizes(existing_sizes)
        pivot = pivot[sorted_sizes]
        
        pivot['Total'] = pivot.sum(axis=1)
        grand_total_qty += pivot['Total'].sum()

        actual_qty = pivot.sum()
        actual_qty.name = 'Actual Qty'
        qty_plus_3 = (actual_qty * 1.03).round().astype(int)
        qty_plus_3.name = '3% Order Qty'
        
        pivot = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
        pivot = pivot.reset_index()
        pivot = pivot.rename(columns={'index': 'P.O NO'})
        pivot.columns.name = None

        pd.set_option('colheader_justify', 'center')
        table_html = pivot.to_html(classes='table table-bordered table-striped', index=False, border=0)
        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(debug=True)
