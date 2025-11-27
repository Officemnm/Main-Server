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
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# কনফিগারেশন (PO ফাইলের জন্য)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ৩০ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (JSON)
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
ACCESSORIES_DB_FILE = 'accessories_db.json' 

# --- ইউজার ম্যানেজমেন্ট ফাংশন ---
def load_users():
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"]
        },
        "KobirAhmed": {
            "password": "11223", 
            "role": "user", 
            "permissions": ["closing"]
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

# --- এক্সেসরিজ ডাটাবেস ফাংশন ---
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
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PO Logic)
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
# লজিক পার্ট: CLOSING REPORT API
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
# CSS & HTML Templates (Part 2)
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body {
            background-color: #2c3e50; 
            background-image: url('https://i.ibb.co.com/v64Lz1gj/Picsart-25-11-19-15-49-43-423.jpg');
            background-repeat: no-repeat;
            background-position: center center;
            background-attachment: fixed;
            background-size: cover;
            min-height: 100vh;
            overflow-x: hidden;
        }
        body::before {
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: -1;
            position: fixed;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 45px 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            color: white;
            animation: floatIn 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
        }

        .center-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            width: 100%;
            padding: 20px;
        }
        .center-container .glass-card {
            width: 100%;
            max-width: 450px;
            text-align: center;
        }

        @keyframes floatIn {
            from { opacity: 0; transform: translateY(30px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        h1 { color: #ffffff; font-size: 26px; font-weight: 600; margin-bottom: 8px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        p.subtitle { color: #e0e0e0; font-size: 13px; margin-bottom: 30px; font-weight: 300; letter-spacing: 0.5px; }
        
        .input-group { text-align: left; margin-bottom: 20px; }
        .input-group label {
            display: block;
            font-size: 12px;
            color: #ffffff;
            font-weight: 500;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }
        
        input[type="password"], input[type="text"], input[type="file"], select, input[type="number"] {
            width: 100%;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            font-size: 15px;
            color: #fff;
            transition: all 0.3s ease;
            outline: none;
            appearance: none;
        }
        
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .footer-credit-login {
            margin-top: 25px;
            font-size: 11px;
            color: rgba(255,255,255,0.5);
            text-align: center;
        }

        a.logout {
            display: inline-block;
            margin-top: 15px;
            color: #ff7675;
            text-decoration: none;
            font-size: 14px;
            font-weight: 600;
            transition: 0.3s;
        }
        a.logout:hover { color: white; }

        /* Admin Styles */
        .admin-container { display: flex; width: 100%; height: 100vh; position: fixed; top: 0; left: 0;}
        .admin-sidebar {
            width: 280px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            display: flex; flex-direction: column; padding: 25px;
        }
        .nav-link {
            display: flex; align-items: center; padding: 12px 15px;
            color: rgba(255, 255, 255, 0.7); text-decoration: none; border-radius: 10px;
            transition: all 0.3s ease; font-size: 14px; cursor: pointer; margin-bottom: 10px;
        }
        .nav-link:hover, .nav-link.active {
            background: linear-gradient(90deg, rgba(108, 92, 231, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%);
            color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transform: translateX(5px);
        }
        .admin-content { flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; }
        
        .user-table { width: 100%; border-collapse: collapse; color: white; margin-top: 20px; }
        .user-table th, .user-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; }
        .user-table th { background: rgba(255,255,255,0.1); font-weight: 600; }
        .user-btn { padding: 6px 12px; border-radius: 6px; border: none; font-size: 12px; cursor: pointer; color: white; margin-right: 5px; }
        .btn-edit { background: #f39c12; }
        .btn-delete { background: #e74c3c; }
        .perm-group { display: flex; gap: 15px; margin-top: 5px; flex-wrap: wrap; }
    </style>
"""

# --- PO SHEET REPORT TEMPLATE ---
PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PO Summary Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', sans-serif; }
        .container { max-width: 1200px; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 20px; }
        .title { font-size: 2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        
        .info-box { background: white; padding: 15px; border-radius: 8px; border-left: 5px solid #2c3e50; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
        .info-item { font-size: 1.1rem; font-weight: 600; color: #555; }
        .info-val { color: #000; font-weight: 800; }
        
        .table-card { background: white; margin-bottom: 30px; border: 1px solid #ddd; }
        .color-header { background: #2c3e50; color: white; padding: 10px; font-weight: 800; font-size: 1.3rem; text-transform: uppercase; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #000; padding: 8px; text-align: center; font-weight: 700; }
        th { background: #eee; }
        .total-col { background: #d1ecff; }
        
        .summary-row td { background: #e2e6ea; border-top: 2px solid #000; font-weight: 900; }
        
        @media print {
            .no-print { display: none; }
            .color-header { background: #2c3e50 !important; color: white !important; -webkit-print-color-adjust: exact; }
            .total-col { background: #d1ecff !important; -webkit-print-color-adjust: exact; }
            .summary-row td { background: #e2e6ea !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-end mb-3 no-print">
            <a href="/" class="btn btn-secondary me-2">Back to Dashboard</a>
            <button onclick="window.print()" class="btn btn-dark">🖨️ Print Report</button>
        </div>

        <div class="header">
            <div class="title">Cotton Clothing BD Limited</div>
            <div style="font-weight:600; color:#666;">PURCHASE ORDER SUMMARY</div>
        </div>

        {% if tables %}
        <div class="info-box">
            <div><span class="info-item">Buyer:</span> <span class="info-val">{{ meta.buyer }}</span></div>
            <div><span class="info-item">Booking:</span> <span class="info-val">{{ meta.booking }}</span></div>
            <div><span class="info-item">Style:</span> <span class="info-val">{{ meta.style }}</span></div>
            <div><span class="info-item">Dept:</span> <span class="info-val">{{ meta.dept }}</span></div>
            <div><span class="info-item">Season:</span> <span class="info-val">{{ meta.season }}</span></div>
            <div style="text-align:right;"><span class="info-item">Total Qty:</span> <span class="info-val" style="font-size:1.5rem;">{{ grand_total }}</span></div>
        </div>

        {% for item in tables %}
        <div class="table-card">
            <div class="color-header">COLOR: {{ item.color }}</div>
            <div class="table-responsive">
                {{ item.table | safe }}
            </div>
        </div>
        {% endfor %}
        
        <div class="text-center mt-5" style="border-top:1px solid #ddd; padding-top:10px; font-size:12px;">
            Report Created By <strong>Mehedi Hasan</strong>
        </div>
        {% else %}
        <div class="alert alert-warning text-center">{{ message }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

# --- CLOSING REPORT TEMPLATE ---
CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Closing Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1400px; }
        .company-header { text-align: center; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 10px; }
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        .report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; }
        
        .table-card { background: white; border-radius: 0; margin-bottom: 30px; border: none; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .color-header { background-color: #2c3e50; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; text-transform: uppercase; }
        
        .table th { background-color: #fff; color: #000; text-align: center; border: 1px solid #000; font-weight: 900; }
        .table td { text-align: center; border: 1px solid #000; padding: 6px; color: #000; font-weight: 600; }
        .col-3pct { background-color: #B9C2DF !important; }
        .col-input { background-color: #C4D09D !important; }
        
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 15px; }
        .btn-custom { border-radius: 50px; padding: 10px 25px; font-weight: 600; transition: transform 0.2s; }
        .btn-custom:hover { transform: translateY(-2px); }

        @media print {
            .no-print { display: none !important; }
            .action-bar { display: none; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important; }
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn btn-outline-secondary btn-custom">Back to Dashboard</a>
            <button onclick="downloadExcel()" class="btn btn-success btn-custom">Download Excel</button>
            <button onclick="window.print()" class="btn btn-dark btn-custom">🖨️ Print Report</button>
        </div>

        <div class="company-header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div class="report-title">CLOSING REPORT [ INPUT SECTION ]</div>
            <div>Date: <span id="date"></span></div>
        </div>

        {% if report_data %}
        <div style="background:white; padding:15px; margin-bottom:20px; border-left: 5px solid #2c3e50;">
            <div class="row">
                <div class="col-md-4"><strong>Buyer:</strong> {{ report_data[0].buyer }}</div>
                <div class="col-md-4"><strong>Style:</strong> {{ report_data[0].style }}</div>
                <div class="col-md-4 text-end"><strong>Booking:</strong> <span style="background:#2c3e50; color:white; padding:5px 10px; font-weight:bold;">{{ ref_no }}</span></div>
            </div>
        </div>

        {% for block in report_data %}
        <div class="table-card">
            <div class="color-header">COLOR: {{ block.color }}</div>
            <table class="table table-bordered">
                <thead>
                    <tr><th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th><th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th></tr>
                </thead>
                <tbody>
                    {% for i in range(block.headers|length) %}
                        {% set actual = block.gmts_qty[i]|replace(',', '')|int %}
                        {% set qty_3 = (actual * 1.03)|round|int %}
                        {% set cut_qc = block.cutting_qc[i]|replace(',', '')|int if i < block.cutting_qc|length else 0 %}
                        {% set inp_qty = block.sewing_input[i]|replace(',', '')|int if i < block.sewing_input|length else 0 %}
                        {% set balance = cut_qc - inp_qty %}
                        {% set short_plus = inp_qty - qty_3 %}
                        <tr>
                            <td>{{ block.headers[i] }}</td>
                            <td class="col-3pct">{{ qty_3 }}</td>
                            <td>{{ actual }}</td>
                            <td>{{ cut_qc }}</td>
                            <td class="col-input">{{ inp_qty }}</td>
                            <td>{{ balance }}</td>
                            <td style="color: {{ 'green' if short_plus >= 0 else 'red' }}">{{ short_plus }}</td>
                            <td>{{ "%.2f"|format((short_plus / qty_3)*100) if qty_3 > 0 else 0 }}%</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        <div class="text-center mt-4 text-muted" style="font-size:12px;">Report Generated By Mehedi Hasan</div>
        {% endif %}
    </div>

    <script>
        document.getElementById('date').innerText = new Date().toLocaleDateString('en-GB');
        function downloadExcel() {
            Swal.fire({
                title: 'Preparing Excel...',
                html: 'Please wait while we generate the file.',
                timer: 2000,
                timerProgressBar: true,
                didOpen: () => { Swal.showLoading() }
            }).then(() => {
                window.location.href = "/download-closing-excel?ref_no={{ ref_no }}";
                Swal.fire({
                    icon: 'success',
                    title: 'Downloaded!',
                    showConfirmButton: false,
                    timer: 1500
                });
            });
        }
    </script>
</body>
</html>
"""

# --- ACCESSORIES REPORT TEMPLATE (With Edit/Delete Restrictions) ---
ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessories Delivery Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        body { font-family: 'Poppins', sans-serif; background: #fff; padding: 20px; color: #000; }
        .container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; }
        
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; line-height: 1; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 18px; border-radius: 4px; }
        
        .info-grid { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
        .info-left { flex: 2; border: 1px dashed #555; padding: 15px; margin-right: 15px; }
        .info-right { flex: 1; border-left: 1px solid #ddd; padding-left: 15px; }
        
        .info-row { display: flex; margin-bottom: 5px; font-size: 14px; align-items: center; }
        .info-label { font-weight: 800; width: 80px; color: #444; }
        .info-val { font-weight: 700; font-size: 15px; color: #000; }
        .booking-border { border: 2px solid #000; padding: 2px 8px; display: inline-block; font-weight: 900; }

        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 10px; border: 1px solid #000; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; font-weight: 600; }
        
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff; }
        
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin: 0 2px; cursor: pointer; border: none; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }

        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }

        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; border-radius: 4px; font-size: 14px; text-decoration: none; }
        .btn-add { background: #27ae60; }
        
        @media print {
            .no-print { display: none; }
            .action-col { display: none; }
            .container { border: none; padding: 0; margin: 0; max-width: 100%; }
        }
    </style>
</head>
<body>

<div class="no-print">
    <a href="/admin/accessories" class="btn">Search Again</a>
    <form action="/admin/accessories/input" method="post" style="display:inline;">
        <input type="hidden" name="ref_no" value="{{ ref }}">
        <button type="submit" class="btn btn-add">Add New Item</button>
    </form>
    <button onclick="window.print()" class="btn">🖨️ Print</button>
</div>

<div class="container">
    <div class="header">
        <div class="company-name">Cotton Clothing BD Limited</div>
        <div style="font-size:12px; font-weight:600; margin:5px 0 10px;">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
        <div class="report-title">ACCESSORIES DELIVERY REPORT</div>
    </div>

    <div class="info-grid">
        <div class="info-left">
            <div class="info-row"><span class="info-label">Booking:</span> <span class="booking-border">{{ ref }}</span></div>
            <div class="info-row"><span class="info-label">Buyer:</span> <span class="info-val">{{ buyer }}</span></div>
            <div class="info-row"><span class="info-label">Style:</span> <span class="info-val">{{ style }}</span></div>
            <div class="info-row"><span class="info-label">Date:</span> <span class="info-val">{{ today }}</span></div>
        </div>
        <div class="info-right">
            <div style="font-weight:700; margin-bottom:8px;">Store: Clothing General Store</div>
            <div style="font-weight:700; margin-bottom:8px;">Send: Cutting</div>
            <div style="font-weight:700;">Item: <span style="border:1px solid #000; padding:0 5px;">{{ item_type if item_type else 'Top/Btm' }}</span></div>
        </div>
    </div>

    <div class="summary-container">
        <div style="font-weight:900; text-align:center; border-bottom:1px solid #000; margin-bottom:5px;">LINE-WISE SUMMARY</div>
        <table style="width:100%; font-size:13px; font-weight:700;">
            <tr>
            {% for line, qty in line_summary.items() %}
                <td>{{ line }}: {{ qty }} pcs</td>
                {% if loop.index % 4 == 0 %}</tr><tr>{% endif %}
            {% endfor %}
            </tr>
        </table>
        <div style="text-align:right; margin-top:5px; font-weight:800; border-top:1px solid #ccc;">Entries: {{ count }}</div>
    </div>

    <table class="main-table">
        <thead>
            <tr>
                <th>DATE</th><th>LINE NO</th><th>COLOR</th><th>SIZE</th><th>STATUS</th><th>QTY</th>
                {% if session.role == 'admin' %}<th class="action-col">ACTION</th>{% endif %}
            </tr>
        </thead>
        <tbody>
            {% set ns = namespace(grand_total=0) %}
            {% for item in challans %}
                {% set ns.grand_total = ns.grand_total + item.qty|int %}
                <tr>
                    <td>{{ item.date }}</td>
                    <td>{% if loop.index == count %}<div class="line-card">{{ item.line }}</div>{% else %}{{ item.line }}{% endif %}</td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td style="color:green; font-size:18px; font-weight:900;">✔</td>
                    <td style="font-size:16px; font-weight:800;">{{ item.qty }}</td>
                    
                    {% if session.role == 'admin' %}
                    <td class="action-col">
                        <a href="/admin/accessories/edit?ref={{ ref }}&index={{ loop.index0 }}" class="action-btn btn-edit-row"><i class="fas fa-pencil-alt"></i></a>
                        <button onclick="confirmDelete('{{ ref }}', {{ loop.index0 }})" class="action-btn btn-del-row"><i class="fas fa-trash"></i></button>
                    </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="footer-total"><div class="total-box">TOTAL QTY: {{ ns.grand_total }}</div></div>

    <div style="margin-top: 60px; display: flex; justify-content: space-between; text-align: center; font-weight: bold; padding: 0 50px;">
        <div style="border-top: 2px solid #000; width: 180px;">Store Incharge</div>
        <div style="border-top: 2px solid #000; width: 180px;">Received By</div>
        <div style="border-top: 2px solid #000; width: 180px;">Cutting Incharge</div>
    </div>
    
    <div class="text-center mt-5" style="font-size:12px; color:#555;">Report Generator: Mehedi Hasan</div>
</div>

<script>
    function confirmDelete(ref, index) {
        Swal.fire({
            title: 'Are you sure?',
            text: "You won't be able to revert this!",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!'
        }).then((result) => {
            if (result.isConfirmed) {
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '/admin/accessories/delete';
                const refInput = document.createElement('input'); refInput.type = 'hidden'; refInput.name = 'ref'; refInput.value = ref;
                const idxInput = document.createElement('input'); idxInput.type = 'hidden'; idxInput.name = 'index'; idxInput.value = index;
                form.appendChild(refInput); form.appendChild(idxInput);
                document.body.appendChild(form);
                form.submit();
            }
        });
    }
</script>
</body>
</html>
"""

# --- LOGIN TEMPLATE ---
LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ERP Gateway Access</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <h1>System Login</h1>
            <p class="subtitle">Secure Gateway for Cotton Clothing BD</p>
            <form action="/login" method="post">
                <div class="input-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" placeholder="Enter Username" required>
                </div>
                <div class="input-group">
                    <label for="password">Authentication PIN</label>
                    <input type="password" id="password" name="password" placeholder="Enter Password" required>
                </div>
                <button type="submit">Verify & Enter</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top:15px; color:#ff7675; font-size:13px;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            
            <div class="footer-credit-login">
                © Mehedi Hasan
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- USER DASHBOARD ---
USER_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard - User</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1>Dashboard</h1>
            <p class="subtitle">Welcome back, {{{{ session.user }}}}</p>
            
            {{% if 'closing' in session.permissions %}}
            <div style="margin-bottom: 25px; text-align:left;">
                <label style="color:#a29bfe; font-size:12px; font-weight:600;">CLOSING REPORT</label>
                <form action="/generate-report" method="post" onsubmit="showLoading()">
                    <div class="input-group" style="margin-bottom:10px;">
                        <input type="text" name="ref_no" placeholder="Enter Reference No" required>
                    </div>
                    <button type="submit"><i class="fas fa-file-export"></i> Generate Report</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'accessories' in session.permissions %}}
            <div style="margin-bottom: 25px; text-align:left; border-top:1px solid rgba(255,255,255,0.1); padding-top:15px;">
                <label style="color:#a29bfe; font-size:12px; font-weight:600;">ACCESSORIES STORE</label>
                <a href="/admin/accessories" style="display:block;">
                    <button style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
                        <i class="fas fa-box-open"></i> Manage Challans
                    </button>
                </a>
            </div>
            {{% endif %}}

            {{% if 'po_sheet' in session.permissions %}}
             <div style="margin-bottom: 20px; text-align:left; border-top:1px solid rgba(255,255,255,0.1); padding-top:15px;">
                <label style="color:#a29bfe; font-size:12px; font-weight:600;">PO SHEET GENERATOR</label>
                 <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoading()">
                    <input type="file" name="pdf_files" multiple accept=".pdf" required style="margin-bottom:10px;">
                    <button type="submit" style="background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%);">
                        <i class="fas fa-file-pdf"></i> Create PO Sheet
                    </button>
                </form>
            </div>
            {{% endif %}}
            
            <div class="footer-credit-login">
                <a href="/logout" style="color:#ff7675; text-decoration:none; font-weight:600; font-size:14px;">Sign Out</a>
                <div style="margin-top:5px;">© Mehedi Hasan</div>
            </div>
        </div>
    </div>
    <script>
        function showLoading() {{
            Swal.fire({{ title: 'Processing...', html: 'Processing data.', allowOutsideClick: false, didOpen: () => {{ Swal.showLoading() }} }});
        }}
    </script>
</body>
</html>
"""

# --- ADMIN DASHBOARD ---
ADMIN_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Console</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="admin-container">
        <div class="admin-sidebar">
            <div style="margin-bottom: 40px; text-align: center;">
                <h2 style="color: white; font-size: 22px; font-weight: 600;">Admin Panel</h2>
                <p style="color: #a29bfe; font-size: 12px; letter-spacing: 1px;">SUPER ADMIN ACCESS</p>
            </div>
            
            <ul style="list-style: none;">
                <li><a class="nav-link active" onclick="showSection('closing', this)"><i class="fas fa-file-export" style="margin-right:10px;"></i> Closing Report</a></li>
                <li><a class="nav-link" href="/admin/accessories"><i class="fas fa-box-open" style="margin-right:10px;"></i> Accessories Hub</a></li>
                <li><a class="nav-link" onclick="showSection('po', this)"><i class="fas fa-file-pdf" style="margin-right:10px;"></i> PO Sheet</a></li>
                <li><a class="nav-link" onclick="showSection('user-manage', this)"><i class="fas fa-users-cog" style="margin-right:10px;"></i> User Management</a></li>
                <li><a class="nav-link" onclick="showSection('history', this)"><i class="fas fa-history" style="margin-right:10px;"></i> System Logs</a></li>
            </ul>
            
            <div style="margin-top: auto; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px; text-align:center;">
                <a href="/logout" style="color: #ff7675; text-decoration:none; font-size:14px; font-weight:600;">Sign Out</a>
                <div style="font-size:10px; color:rgba(255,255,255,0.4); margin-top:5px;">© Mehedi Hasan</div>
            </div>
        </div>

        <div class="admin-content">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
                <div class="glass-card" style="padding:20px; text-align:left; animation:none;">
                    <h3 style="font-size:24px;">{{{{ stats.today }}}}</h3>
                    <p style="margin:0; font-size:12px; color:#ddd;">Today's Reports</p>
                </div>
                <div class="glass-card" style="padding:20px; text-align:left; animation:none;">
                    <h3 style="font-size:24px;">{{{{ stats.month }}}}</h3>
                    <p style="margin:0; font-size:12px; color:#ddd;">Monthly Total</p>
                </div>
            </div>

            <div id="work-area" style="flex: 1; background: rgba(0, 0, 0, 0.2); border-radius: 20px; padding: 30px; position: relative;">
                
                <div id="closing-section" class="work-section">
                    <h2 style="color:white; margin-bottom:20px;">Generate Closing Report</h2>
                    <div style="max-width:400px;">
                        <form action="/generate-report" method="post" onsubmit="showLoading()">
                            <input type="text" name="ref_no" placeholder="Enter Ref No" style="margin-bottom:10px;" required>
                            <button type="submit">Generate</button>
                        </form>
                    </div>
                </div>

                <div id="po-section" class="work-section" style="display:none;">
                    <h2 style="color:white; margin-bottom:20px;">PDF PO Sheet Generator</h2>
                    <div style="max-width:400px;">
                        <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoading()">
                            <input type="file" name="pdf_files" multiple accept=".pdf" required style="margin-bottom:10px;">
                            <button type="submit" style="background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%);">Process PDFs</button>
                        </form>
                    </div>
                </div>

                <div id="user-manage-section" class="work-section" style="display:none;">
                    <h2 style="color:white; margin-bottom:20px;">User Management</h2>
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                        <h4 style="color:#a29bfe; font-size:14px; margin-bottom:15px;">Add / Edit User</h4>
                        <form id="userForm">
                            <input type="hidden" id="action_type" value="create">
                            <div style="display:flex; gap:10px; margin-bottom:10px;">
                                <input type="text" id="new_username" placeholder="Username" required>
                                <input type="text" id="new_password" placeholder="Password" required>
                            </div>
                            <div style="margin-bottom:15px; color:white; font-size:13px;">
                                <label style="display:block; margin-bottom:5px;">Modules Permission:</label>
                                <div class="perm-group">
                                    <label><input type="checkbox" id="perm_closing" checked> Closing Report</label>
                                    <label><input type="checkbox" id="perm_acc"> Accessories</label>
                                    <label><input type="checkbox" id="perm_po"> PO Sheet</label>
                                </div>
                            </div>
                            <button type="button" onclick="handleUserSubmit()" id="saveUserBtn">Create User</button>
                            <button type="button" onclick="resetForm()" style="background:#95a5a6; margin-top:5px;">Reset</button>
                        </form>
                    </div>
                    <table class="user-table">
                        <thead><tr><th>User</th><th>Role</th><th>Permissions</th><th>Action</th></tr></thead>
                        <tbody id="userTableBody"></tbody>
                    </table>
                </div>

                <div id="history-section" class="work-section" style="display:none;">
                    <h2 style="color:white; margin-bottom:20px;">System Logs</h2>
                    <div style="overflow-y:auto; max-height:400px;">
                        <table class="user-table">
                            <thead><tr><th>Date</th><th>Time</th><th>User</th><th>Ref No</th></tr></thead>
                            <tbody>
                                {{% for log in stats.history %}}
                                <tr>
                                    <td>{{{{ log.date }}}}</td>
                                    <td>{{{{ log.time }}}}</td>
                                    <td>{{{{ log.user }}}}</td>
                                    <td style="color:#a29bfe;">{{{{ log.ref }}}}</td>
                                </tr>
                                {{% endfor %}}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showLoading() {{ Swal.fire({{ title: 'Processing...', didOpen: () => Swal.showLoading() }}); }}
        function showSection(id, el) {{
            document.querySelectorAll('.nav-link').forEach(e => e.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.work-section').forEach(e => e.style.display = 'none');
            document.getElementById(id + '-section').style.display = 'block';
            if(id === 'user-manage') loadUsers();
        }}
        function loadUsers() {{
            fetch('/admin/get-users').then(res => res.json()).then(data => {{
                let html = '';
                for (const [user, details] of Object.entries(data)) {{
                    html += `<tr><td>${{user}}</td><td>${{details.role}}</td><td>${{details.permissions ? details.permissions.join(', ') : ''}}</td>
                    <td>${{details.role !== 'admin' ? `<button class="user-btn btn-edit" onclick="editUser('${{user}}', '${{details.password}}', '${{details.permissions}}')">Edit</button><button class="user-btn btn-delete" onclick="deleteUser('${{user}}')">Delete</button>` : 'Admin'}}</td></tr>`;
                }}
                document.getElementById('userTableBody').innerHTML = html;
            }});
        }}
        function handleUserSubmit() {{
            const user = document.getElementById('new_username').value;
            const pass = document.getElementById('new_password').value;
            const action = document.getElementById('action_type').value;
            let perms = [];
            if(document.getElementById('perm_closing').checked) perms.push('closing');
            if(document.getElementById('perm_acc').checked) perms.push('accessories');
            if(document.getElementById('perm_po').checked) perms.push('po_sheet');
            fetch('/admin/save-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: user, password: pass, permissions: perms, action_type: action }}) }})
            .then(res => res.json()).then(data => {{
                if(data.status === 'success') {{ Swal.fire('Success', data.message, 'success'); loadUsers(); resetForm(); }}
                else {{ Swal.fire('Error', data.message, 'error'); }}
            }});
        }}
        function editUser(user, pass, permsStr) {{
            document.getElementById('new_username').value = user; document.getElementById('new_username').readOnly = true;
            document.getElementById('new_password').value = pass; document.getElementById('action_type').value = 'update';
            document.getElementById('saveUserBtn').innerText = 'Update User';
            const perms = permsStr.split(',');
            document.getElementById('perm_closing').checked = perms.includes('closing');
            document.getElementById('perm_acc').checked = perms.includes('accessories');
            document.getElementById('perm_po').checked = perms.includes('po_sheet');
        }}
        function resetForm() {{
            document.getElementById('userForm').reset(); document.getElementById('action_type').value = 'create';
            document.getElementById('saveUserBtn').innerText = 'Create User'; document.getElementById('new_username').readOnly = false;
        }}
        function deleteUser(user) {{
            Swal.fire({{ title: 'Are you sure?', text: "Delete user " + user + "?", icon: 'warning', showCancelButton: true, confirmButtonText: 'Yes, delete it!' }})
            .then((result) => {{ if (result.isConfirmed) {{
                fetch('/admin/delete-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: user }}) }})
                .then(res => res.json()).then(data => {{ Swal.fire('Deleted!', 'User deleted.', 'success'); loadUsers(); }});
            }} }});
        }}
    </script>
</body>
</html>
"""

# ==============================================================================
# FLASK ROUTES
# ==============================================================================

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
            stats = get_dashboard_summary()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            return render_template_string(USER_DASHBOARD_TEMPLATE)

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
        flash('Incorrect Username or Password.')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- USER API ---
@app.route('/admin/get-users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({})
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error', 'message': 'Unauthorized'})
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    permissions = data.get('permissions', [])
    action = data.get('action_type')
    if not username or not password: return jsonify({'status': 'error', 'message': 'Invalid Data'})
    users_db = load_users()
    if action == 'create':
        if username in users_db: return jsonify({'status': 'error', 'message': 'User already exists!'})
        users_db[username] = {"password": password, "role": "user", "permissions": permissions}
    elif action == 'update':
        if username not in users_db: return jsonify({'status': 'error', 'message': 'User not found!'})
        users_db[username]['password'] = password
        users_db[username]['permissions'] = permissions
    save_users(users_db)
    return jsonify({'status': 'success', 'message': 'User saved successfully!'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error', 'message': 'Unauthorized'})
    username = request.json.get('username')
    users_db = load_users()
    if username == 'Admin': return jsonify({'status': 'error', 'message': 'Cannot delete Main Admin!'})
    if username in users_db:
        del users_db[username]
        save_users(users_db)
        return jsonify({'status': 'success', 'message': 'User deleted!'})
    return jsonify({'status': 'error', 'message': 'User not found'})

# --- CLOSING REPORT ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'closing' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))
    internal_ref_no = request.form['ref_no']
    report_data = fetch_closing_report_data(internal_ref_no)
    if not report_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    internal_ref_no = request.args.get('ref_no')
    report_data = fetch_closing_report_data(internal_ref_no)
    if report_data:
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        stream = create_formatted_excel_report(report_data, internal_ref_no)
        return make_response(send_file(stream, as_attachment=True, download_name=f"Report-{internal_ref_no}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    return redirect(url_for('index'))

# --- ACCESSORIES ROUTES ---
@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions', []):
        flash("You do not have permission for Accessories.")
        return redirect(url_for('index'))
    return render_template_string(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Find Booking</title>{COMMON_STYLES}</head><body><div class="center-container"><div class="glass-card"><h1>Accessories Hub</h1><p class="subtitle">Welcome, {session.get('user')}</p><form action="/admin/accessories/input" method="post"><div class="input-group"><label>Booking Reference No</label><input type="text" name="ref_no" required></div><button type="submit">Proceed</button></form><br><a href="/" style="color:white;font-size:12px;">Back to Dashboard</a><div class="footer-credit-login"><a href="/logout" style="color:#ff7675;">Sign Out</a><div style="margin-top:5px;">© Mehedi Hasan</div></div></div></div></body></html>""")

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions', []): return redirect(url_for('index'))
    ref_no = request.form.get('ref_no').strip()
    db = load_accessories_db()
    if ref_no in db:
        data = db[ref_no]
        colors, style, buyer = data['colors'], data['style'], data['buyer']
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"No booking data found for {ref_no}")
            return redirect(url_for('accessories_search_page'))
        colors = sorted(list(set([item['color'] for item in api_data])))
        style, buyer = api_data[0].get('style', 'N/A'), api_data[0].get('buyer', 'N/A')
        db[ref_no] = {"style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": []}
        save_accessories_db(db)
    return render_template_string(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>New Challan</title>{COMMON_STYLES}</head><body><div class="center-container"><div class="glass-card"><h1>New Challan</h1><p class="subtitle">Booking: {ref_no}</p><div style="background:rgba(255,255,255,0.1);padding:10px;border-radius:8px;margin-bottom:20px;font-size:13px;text-align:left;"><div style="display:flex;justify-content:space-between;"><span><strong>Buyer:</strong> {buyer}</span><span><strong>Style:</strong> {style}</span></div></div><form action="/admin/accessories/save" method="post" id="challanForm"><input type="hidden" name="ref" value="{ref_no}"><div class="input-group"><label>Item Type</label><select name="item_type"><option value="" disabled selected>-- Select Item --</option><option value="Top">Top</option><option value="Bottom">Bottom</option></select></div><div class="input-group"><label>Color</label><select name="color" required><option value="" disabled selected>-- Choose Color --</option>{''.join([f'<option value="{c}">{c}</option>' for c in colors])}</select></div><div style="display:flex;gap:10px;"><div class="input-group" style="flex:1;"><label>Line No</label><input type="text" name="line_no" required></div><div class="input-group" style="flex:1;"><label>Size</label><input type="text" name="size" value="-"></div></div><div class="input-group"><label>Quantity</label><input type="number" name="qty" required></div><button type="submit">Save Entry</button></form><div style="margin-top:15px;display:flex;justify-content:space-between;"><a href="/admin/accessories/print?ref={ref_no}" style="color:#a29bfe;font-size:13px;">View Report</a><a href="/admin/accessories" style="color:white;font-size:13px;">Back</a></div><div class="footer-credit-login"><div style="margin-top:15px;">© Mehedi Hasan</div></div></div></div><script>document.getElementById('challanForm').addEventListener('submit', function(e){{e.preventDefault(); Swal.fire({{title:'Saving...', timer:1000, didOpen:()=>Swal.showLoading()}}).then(()=>{{e.target.submit()}});}});</script></body></html>""")

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form.get('ref')
    db = load_accessories_db()
    if ref in db:
        if request.form.get('item_type'): db[ref]['item_type'] = request.form.get('item_type')
        for item in db[ref]['challans']: item['status'] = "✔"
        db[ref]['challans'].append({
            "date": datetime.now().strftime("%d-%m-%Y"),
            "line": request.form.get('line_no'), "color": request.form.get('color'),
            "size": request.form.get('size'), "qty": request.form.get('qty'), "status": ""
        })
        save_accessories_db(db)
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref')
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search_page'))
    data = db[ref]
    line_summary = {}
    for c in data['challans']:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        line_summary[ln] = line_summary.get(ln, 0) + q
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, ref=ref, buyer=data['buyer'], style=data['style'], item_type=data.get('item_type', ''), challans=data['challans'], line_summary=dict(sorted(line_summary.items())), count=len(data['challans']), today=datetime.now().strftime("%d-%m-%Y"))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin': return "Unauthorized", 403
    ref = request.form.get('ref')
    try: index = int(request.form.get('index'))
    except: return redirect(url_for('accessories_search_page'))
    db = load_accessories_db()
    if ref in db and 0 <= index < len(db[ref]['challans']):
        del db[ref]['challans'][index]
        save_accessories_db(db)
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in') or session.get('role') != 'admin': return "Unauthorized", 403
    ref = request.args.get('ref')
    index = int(request.args.get('index'))
    db = load_accessories_db()
    return render_template_string(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Edit Challan</title>{COMMON_STYLES}</head><body><div class="center-container"><div class="glass-card"><h1>Edit Challan</h1><form action="/admin/accessories/update" method="post"><input type="hidden" name="ref" value="{ref}"><input type="hidden" name="index" value="{index}"><div class="input-group"><label>Line No</label><input type="text" name="line_no" value="{db[ref]['challans'][index]['line']}" required></div><div class="input-group"><label>Color</label><input type="text" name="color" value="{db[ref]['challans'][index]['color']}" required></div><div class="input-group"><label>Size</label><input type="text" name="size" value="{db[ref]['challans'][index]['size']}" required></div><div class="input-group"><label>Quantity</label><input type="number" name="qty" value="{db[ref]['challans'][index]['qty']}" required></div><button type="submit">Update</button></form><br><a href="/admin/accessories/print?ref={ref}" style="color:white;font-size:12px;">Cancel</a></div></div></body></html>""")

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in') or session.get('role') != 'admin': return "Unauthorized", 403
    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db = load_accessories_db()
    if ref in db:
        db[ref]['challans'][index].update({'qty': request.form.get('qty'), 'line': request.form.get('line_no'), 'color': request.form.get('color'), 'size': request.form.get('size')})
        save_accessories_db(db)
    return redirect(url_for('accessories_print_view', ref=ref))

# --- PO SHEET ROUTE ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'po_sheet' not in session.get('permissions', []):
         flash("Permission Denied")
         return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    uploaded_files = request.files.getlist('pdf_files')
    all_data = []
    final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    
    for file in uploaded_files:
        if file.filename == '': continue
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        data, meta = extract_data_dynamic(file_path)
        if meta['buyer'] != 'N/A': final_meta = meta
        if data: all_data.extend(data)
    
    if not all_data:
        return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO table data found in files.")

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
        
        # HTML Table Construction with custom classes
        table_html = pivot.to_html(classes='table', index=False, border=0)
        table_html = table_html.replace('<th>Total</th>', '<th class="total-col">Total</th>')
        table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        table_html = table_html.replace('<td>Actual Qty</td>', '<td style="text-align:right; padding-right:15px;">Actual Qty</td>')
        table_html = table_html.replace('<td>3% Order Qty</td>', '<td style="text-align:right; padding-right:15px;">3% Order Qty</td>')
        
        # Add summary row class
        table_html = re.sub(r'<tr>\s*<td[^>]*>Actual Qty</td>', '<tr class="summary-row"><td style="text-align:right; padding-right:15px;">Actual Qty</td>', table_html)
        table_html = re.sub(r'<tr>\s*<td[^>]*>3% Order Qty</td>', '<tr class="summary-row"><td style="text-align:right; padding-right:15px;">3% Order Qty</td>', table_html)

        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
