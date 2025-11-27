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
import uuid # এডিট/ডিলিট এর জন্য ইউনিক আইডি লাগবে

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# কনফিগারেশন (PO ফাইলের জন্য)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ২ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60) 

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (JSON)
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
ACCESSORIES_DB_FILE = 'accessories_db.json' # চালানের ডাটা সেভ রাখার নতুন ফাইল

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

# --- এক্সেসরিজ ডাটাবেস ফাংশন (নতুন) ---
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
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (ORIGINAL)
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
# লজিক পার্ট: CLOSING REPORT (ORIGINAL)
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
# CSS & HTML Templates
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
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
            color: white;
        }
        body::before {
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.4);
            z-index: -1;
            position: fixed;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 45px 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            color: white;
            width: 100%;
        }
        .center-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            width: 100%;
            padding: 20px;
        }
        .input-group { text-align: left; margin-bottom: 20px; }
        .input-group label {
            display: block;
            font-size: 12px;
            color: #ffffff;
            font-weight: 500;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        input, select, button {
            width: 100%;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            font-size: 15px;
            color: #fff;
            outline: none;
        }
        select option { background-color: #2c3e50; color: white; }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.3); }

        /* Admin Layout */
        .admin-container { display: flex; width: 100%; height: 100vh; position: fixed; top: 0; left: 0;}
        .admin-sidebar {
            width: 280px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            display: flex; flex-direction: column; padding: 25px;
        }
        .admin-content { flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; }
        .nav-link {
            display: flex; align-items: center; padding: 12px 15px;
            color: rgba(255, 255, 255, 0.7); text-decoration: none; border-radius: 10px;
            transition: all 0.3s ease; font-size: 14px; cursor: pointer; margin-bottom: 10px;
        }
        .nav-link:hover, .nav-link.active {
            background: linear-gradient(90deg, rgba(108, 92, 231, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%);
            color: white;
        }

        /* Table Styles */
        .table-dark { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        .table-dark th, .table-dark td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: center; }
        .table-dark th { background: rgba(0,0,0,0.3); font-weight: 600; color: #a29bfe; }
        .action-btn { padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 11px; margin: 0 2px; display: inline-block; cursor: pointer; border: none; font-weight: 600; }
        .btn-edit { background: #f39c12; color: white; }
        .btn-delete { background: #e74c3c; color: white; }
    </style>
"""

# --- 1. ACCESSORIES SEARCH PAGE ---
ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Find Booking</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1 style="text-align:center; margin-bottom:10px;"><i class="fas fa-search"></i> Booking Search</h1>
            <p style="text-align:center; color:#ccc; font-size:13px; margin-bottom:20px;">Enter Booking No to Manage Challan</p>
            
            <form action="/admin/accessories/input" method="post">
                <div class="input-group">
                    <label>Booking Reference No</label>
                    <input type="text" name="ref_no" placeholder="e.g. Booking-123..." required>
                </div>
                <button type="submit">Proceed</button>
            </form>
            <br>
            <a href="/" style="color:white; text-decoration:none; font-size:12px; text-align:center; display:block;">Back to Dashboard</a>
        </div>
    </div>
</body>
</html>
"""

# --- 2. ACCESSORIES INPUT & MANAGEMENT TEMPLATE ---
ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Manage Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container" style="flex-direction: column; padding-top: 50px;">
        <div class="glass-card" style="max-width: 700px; margin-bottom: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2 style="font-weight:600;"><i class="fas fa-edit"></i> Challan Entry</h2>
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" target="_blank" style="background:#27ae60; padding:8px 20px; border-radius:30px; color:white; text-decoration:none; font-size:13px; font-weight:bold;">Print Report <i class="fas fa-print"></i></a>
            </div>
            <div style="background:rgba(0,0,0,0.3); padding:10px; border-radius:8px; margin:15px 0; font-size:13px;">
                <strong>Booking:</strong> {{{{ ref }}}} &nbsp;|&nbsp; <strong>Buyer:</strong> {{{{ buyer }}}} &nbsp;|&nbsp; <strong>Style:</strong> {{{{ style }}}}
            </div>

            <form action="/admin/accessories/save" method="post">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <input type="hidden" name="id" value="{{{{ edit_data.id if edit_data else '' }}}}">
                
                <div style="display:flex; gap:15px;">
                    <div class="input-group" style="flex:1;">
                        <label>Store (From)</label>
                        <input type="text" value="Clothing General Store" readonly style="opacity:0.7; cursor:not-allowed; background:#333;">
                    </div>
                    <div class="input-group" style="flex:1;">
                        <label>Send To</label>
                        <input type="text" value="Cutting" readonly style="opacity:0.7; cursor:not-allowed; background:#333;">
                    </div>
                </div>

                <div style="display:flex; gap:15px;">
                    <div class="input-group" style="flex:1;">
                        <label>Item Type</label>
                        <select name="item_type">
                            <option value="" {{% if not edit_data or not edit_data.item_type %}}selected{{% endif %}}>-- Select (Top/Btm) --</option>
                            <option value="Top" {{% if edit_data and edit_data.item_type == 'Top' %}}selected{{% endif %}}>Top</option>
                            <option value="Btm" {{% if edit_data and edit_data.item_type == 'Btm' %}}selected{{% endif %}}>Btm</option>
                        </select>
                    </div>
                     <div class="input-group" style="flex:1;">
                        <label>Select Color</label>
                        <select name="color" required>
                            <option value="" disabled {{% if not edit_data %}}selected{{% endif %}}>-- Choose Color --</option>
                            {{% for color in colors %}}
                            <option value="{{{{ color }}}}" {{% if edit_data and edit_data.color == color %}}selected{{% endif %}}>{{{{ color }}}}</option>
                            {{% endfor %}}
                        </select>
                    </div>
                </div>

                <div style="display:flex; gap:15px;">
                    <div class="input-group" style="flex:1;">
                        <label>Line Number</label>
                        <input type="text" name="line_no" placeholder="e.g. 12" value="{{{{ edit_data.line if edit_data else '' }}}}" required>
                    </div>
                    <div class="input-group" style="flex:1;">
                        <label>Size (Optional)</label>
                        <input type="text" name="size" value="{{{{ edit_data.size if edit_data else '-' }}}}">
                    </div>
                    <div class="input-group" style="flex:1;">
                        <label>Quantity</label>
                        <input type="number" name="qty" placeholder="0" value="{{{{ edit_data.qty if edit_data else '' }}}}" required style="font-weight:bold; color:#f1c40f;">
                    </div>
                </div>

                <button type="submit">{{{{ 'Update Entry' if edit_data else 'Add to Challan' }}}}</button>
                {{% if edit_data %}}
                    <a href="/admin/accessories/input?ref_no={{{{ ref }}}}" style="display:block; text-align:center; margin-top:10px; color:#ff7675; font-size:12px;">Cancel Edit Mode</a>
                {{% endif %}}
            </form>
        </div>

        <div class="glass-card" style="max-width: 900px;">
            <h3 style="font-size:16px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:5px;">Existing Challan List</h3>
            <div style="overflow-x:auto;">
                <table class="table-dark">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Line</th>
                            <th>Color</th>
                            <th>Item</th>
                            <th>Qty</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for item in challans|reverse %}}
                        <tr>
                            <td>{{{{ item.date }}}}</td>
                            <td style="font-weight:bold;">{{{{ item.line }}}}</td>
                            <td>{{{{ item.color }}}}</td>
                            <td>{{{{ item.item_type }}}}</td>
                            <td style="color:#f1c40f; font-weight:bold;">{{{{ item.qty }}}}</td>
                            <td>
                                <a href="/admin/accessories/edit/{{{{ ref }}}}/{{{{ item.id }}}}" class="action-btn btn-edit"><i class="fas fa-edit"></i> Edit</a>
                                <a href="/admin/accessories/delete/{{{{ ref }}}}/{{{{ item.id }}}}" class="action-btn btn-delete" onclick="return confirm('Confirm delete?');"><i class="fas fa-trash"></i></a>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="6" style="color:#aaa;">No challan entries found. Add one above.</td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
            <div style="margin-top:20px;">
                <a href="/admin/accessories" style="color:white; text-decoration:none; font-size:13px;"><i class="fas fa-arrow-left"></i> Back to Search</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# --- 3. ACCESSORIES PRINT REPORT TEMPLATE ---
ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Challan Print</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Poppins', sans-serif; background: #555; padding: 20px; color: #000; margin: 0; }
        
        /* Print Page Layout */
        .page { 
            background: #fff; 
            width: 210mm; 
            min-height: 297mm; 
            margin: 0 auto 20px auto; 
            padding: 10mm; 
            position: relative; 
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }

        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 15px; position: relative; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; line-height: 1; }
        .company-addr { font-size: 11px; color: #333; margin-top: 5px; font-weight: 600; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 16px; border-radius: 4px; margin-top:8px; }
        
        .copy-label { 
            position: absolute; right: 0; top: 10px;
            font-size: 12px; font-weight: 900; 
            border: 2px solid #000; padding: 3px 10px; 
            text-transform: uppercase; background: #fff;
        }

        .info-section { display: flex; justify-content: space-between; margin-bottom: 15px; align-items: flex-start; }
        .info-grid { flex: 2; display: grid; grid-template-columns: auto 1fr; row-gap: 3px; column-gap: 15px; font-size: 14px; }
        .label { font-weight: 800; color: #333; width: 80px; }
        .val { font-weight: 700; color: #000; }

        .right-info-box {
            display: flex; flex-direction: column; gap: 8px; align-items: flex-end;
        }
        .booking-box { 
            border: 2px solid #000; padding: 5px 15px; text-align: center; min-width: 180px;
        }
        .booking-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
        .booking-num { font-size: 18px; font-weight: 900; }
        
        .store-info {
            border: 1px solid #777; padding: 5px 10px; font-size: 12px; width: 220px; background: #f9f9f9;
        }
        .store-row { display: flex; justify-content: space-between; margin-bottom: 2px; }
        .s-lbl { font-weight: 700; color: #555; }
        .s-val { font-weight: 800; color: #000; }

        .summary-box { 
            background: #eaeaea; border: 1px solid #000; padding: 8px; font-size: 12px; margin-bottom: 10px;
        }

        .main-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 12px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 8px; border: 1px solid #000; text-transform: uppercase; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; font-weight: 600; vertical-align: middle; }
        
        .footer-sig { margin-top: auto; display: flex; justify-content: space-between; padding-top: 40px; }
        .sig-box { text-align: center; width: 180px; }
        .sig-line { border-top: 2px solid #000; padding-top: 5px; font-weight: 800; font-size: 13px; }

        .controls { 
            position: fixed; top: 20px; right: 20px; background: white; padding: 15px; 
            border-radius: 8px; box-shadow: 0 5px 15px rgba(0,0,0,0.3); z-index: 1000; width: 200px;
        }
        .btn { display: block; width: 100%; margin-bottom: 10px; padding: 10px; cursor: pointer; background: #2c3e50; color: white; border: none; font-weight: bold; border-radius: 4px; text-align: center; text-decoration: none; font-size: 13px; }
        .btn-green { background: #27ae60; }
        .btn:hover { opacity: 0.9; }

        @media print {
            body { background: white; padding: 0; }
            .controls { display: none; }
            .page { margin: 0; box-shadow: none; page-break-after: always; width: 100%; height: 100%; padding: 10mm; }
            .page:last-child { page-break-after: auto; }
        }
    </style>
</head>
<body>

<div class="controls">
    <div style="font-weight:bold; margin-bottom:10px; text-align:center; border-bottom:1px solid #eee; padding-bottom:5px;">Print Options</div>
    <button onclick="printReport('both')" class="btn btn-green">🖨️ Print Both (2 Pages)</button>
    <button onclick="printReport('one')" class="btn">📄 Print 1 (Store Copy)</button>
    <a href="/admin/accessories/input?ref_no={{ ref }}" class="btn" style="background:#e74c3c;">Back to Edit</a>
</div>

<div id="print-container"></div>

<template id="page-template">
    <div class="page">
        <div class="header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div class="company-addr">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
            <div class="report-title">ACCESSORIES DELIVERY CHALLAN</div>
            <div class="copy-label"></div> 
        </div>

        <div class="info-section">
            <div class="info-grid">
                <div class="label">Buyer:</div> <div class="val">{{ buyer }}</div>
                <div class="label">Style:</div> <div class="val">{{ style }}</div>
                <div class="label">Date:</div> <div class="val">{{ today }}</div>
            </div>
            
            <div class="right-info-box">
                <div class="booking-box">
                    <div class="booking-title">Booking Ref No</div>
                    <div class="booking-num">{{ ref }}</div>
                </div>
                <div class="store-info">
                    <div class="store-row">
                        <span class="s-lbl">Store:</span> <span class="s-val">Clothing General Store</span>
                    </div>
                    <div class="store-row">
                        <span class="s-lbl">Send:</span> <span class="s-val">Cutting</span>
                    </div>
                    <div class="store-row">
                        <span class="s-lbl">Item:</span> <span class="s-val" id="item-val"></span>
                    </div>
                </div>
            </div>
        </div>

        <div class="summary-box">
            <div style="font-weight:800; border-bottom:1px solid #999; margin-bottom:5px; padding-bottom:2px;">SUMMARY (Total Qty Per Line)</div>
            <div style="display:flex; flex-wrap:wrap; gap:15px;">
                {% for line, qty in summary.items() %}
                    <span>Line <span style="font-weight:900">{{ line }}</span> : <span style="font-weight:800">{{ qty }}</span> pcs</span>
                    {% if not loop.last %} | {% endif %}
                {% endfor %}
            </div>
        </div>

        <table class="main-table">
            <thead>
                <tr>
                    <th width="12%">DATE</th>
                    <th width="12%">LINE NO</th>
                    <th width="20%">COLOR</th>
                    <th width="10%">ITEM</th>
                    <th width="15%">SIZE</th>
                    <th width="10%">STATUS</th>
                    <th width="15%">QTY</th>
                </tr>
            </thead>
            <tbody>
                {% set ns = namespace(grand_total=0) %}
                {% for item in challans %}
                    {% set ns.grand_total = ns.grand_total + item.qty|int %}
                    <tr>
                        <td>{{ item.date }}</td>
                        <td><span style="border:1px solid #000; padding:1px 5px; font-weight:800; border-radius:3px;">{{ item.line }}</span></td>
                        <td>{{ item.color }}</td>
                        <td>{{ item.item_type }}</td>
                        <td>{{ item.size }}</td>
                        <td style="font-size:16px; color:green; font-weight:bold;">✔</td>
                        <td style="font-size:14px; font-weight:800;">{{ item.qty }}</td>
                    </tr>
                {% endfor %}
                <tr style="background:#eee;">
                    <td colspan="6" style="text-align:right; padding-right:10px; font-weight:900;">GRAND TOTAL</td>
                    <td style="font-weight:900; font-size:16px;">{{ ns.grand_total }}</td>
                </tr>
            </tbody>
        </table>

        <div class="footer-sig">
            <div class="sig-box">
                <div class="sig-line">Cutting Incharge</div>
                <div style="font-size:10px;">(Receiver)</div>
            </div>
            <div class="sig-box">
                <div class="sig-line">Store Incharge</div>
                 <div style="font-size:10px;">(Sender)</div>
            </div>
            <div class="sig-box">
                <div class="sig-line">Authorized By</div>
            </div>
        </div>
        
        <div style="text-align:center; font-size:10px; margin-top:20px; color:#777;">System Generated Report | User: {{ session.get('user') }}</div>
    </div>
</template>

<script>
    // Extract Item type from first row for header summary if consistent, or just leave blank
    const lastItemType = "{{ challans[-1].item_type if challans else '' }}";

    function printReport(mode) {
        const container = document.getElementById('print-container');
        const template = document.getElementById('page-template').innerHTML;
        container.innerHTML = '';

        const createPage = (label) => {
            let div = document.createElement('div');
            div.innerHTML = template;
            div.querySelector('.copy-label').innerText = label;
            div.querySelector('#item-val').innerText = lastItemType; 
            return div;
        };

        if (mode === 'both') {
            container.appendChild(createPage('Store Copy'));
            container.appendChild(createPage('Sewing Copy'));
        } else {
            container.appendChild(createPage('Store Copy'));
        }

        setTimeout(() => { window.print(); }, 500);
    }
    
    // Initial Render
    printReport('one');
</script>

</body>
</html>
"""

# --- NEW: Report Preview Template for Closing Report ---
CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Closing Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 1.1rem; }
        .container { max-width: 1400px; }
        .company-header { text-align: center; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 10px; }
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; letter-spacing: 1px; line-height: 1; }
        .report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; margin-top: 5px; }
        .date-section { font-size: 1.2rem; font-weight: 800; color: #000; margin-top: 5px; }
        
        .info-container { margin-bottom: 15px; background: white; padding: 15px; display: flex; justify-content: space-between; align-items: flex-end;}
        .info-row { display: flex; flex-direction: column; gap: 5px; }
        .info-item { font-size: 1.2rem; font-weight: 600; color: #444; }
        .info-value { color: #000; font-weight: 800; }

        .booking-box { 
            background: #2c3e50; color: white; padding: 10px 20px; border-radius: 5px; 
            text-align: right; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); 
            display: flex; flex-direction: column; justify-content: center; min-width: 200px;
        }
        .booking-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
        .booking-value { font-size: 1.8rem; font-weight: 800; line-height: 1.1; }

        .table-card { background: white; border-radius: 0; margin-bottom: 30px; border: none; }
        .color-header { background-color: #2c3e50 !important; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; text-transform: uppercase; border: 1px solid #000;}
        
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; font-size: 1rem; }
        .table th { background-color: #fff !important; color: #000 !important; text-align: center; border: 1px solid #000; padding: 8px; vertical-align: middle; font-weight: 900; font-size: 1.2rem; }
        
        .table td { text-align: center; vertical-align: middle; border: 1px solid #000; padding: 6px; color: #000; font-weight: 600; font-size: 1.1rem; }
        
        .col-3pct { background-color: #B9C2DF !important; font-weight: 700; }
        .col-input { background-color: #C4D09D !important; font-weight: 700; }
        .col-balance { font-weight: 700; color: #c0392b; }

        .total-row td { background-color: #fff !important; color: #000 !important; font-weight: 900; font-size: 1.2rem; border-top: 2px solid #000; }
        
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 15px; position: sticky; top: 0; z-index: 1000; background: #f8f9fa; padding: 10px 0; }
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; }
        .btn-excel { background-color: #27ae60; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; text-decoration: none; display: inline-block; }
        .btn-excel:hover { color: white; background-color: #219150; }

        .footer-credit { text-align: center; margin-top: 40px; margin-bottom: 20px; font-size: 1rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #000; font-weight: 600;}

        @media print {
            @page { margin: 5mm; size: portrait; } 
            body { background-color: white; padding: 0; }
            .no-print { display: none !important; }
            .action-bar { display: none; }
            .table th, .table td { border: 1px solid #000 !important; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important;}
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            .booking-box { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important; border: 1px solid #000;}
            .total-row td { font-weight: 900 !important; color: #000 !important; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn btn-outline-secondary rounded-pill px-4">Back to Dashboard</a>
            <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-excel"><i class="fas fa-file-excel"></i> Download Excel</a>
            <button onclick="window.print()" class="btn btn-print">🖨️ Print Report</button>
        </div>

        <div class="company-header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div class="report-title">CLOSING REPORT [ INPUT SECTION ]</div>
            <div class="date-section">Date: <span id="date"></span></div>
        </div>

        {% if report_data %}
        <div class="info-container">
            <div class="info-row">
                <div class="info-item">Buyer: <span class="info-value">{{ report_data[0].buyer }}</span></div>
                <div class="info-item">Style: <span class="info-value">{{ report_data[0].style }}</span></div>
            </div>
            <div class="booking-box">
                <div class="booking-label">IR/IB NO</div>
                <div class="booking-value">{{ ref_no }}</div>
            </div>
        </div>

        {% for block in report_data %}
        <div class="table-card">
            <div class="color-header">COLOR: {{ block.color }}</div>
            <table class="table">
                <thead>
                    <tr>
                        <th>SIZE</th>
                        <th>ORDER QTY 3%</th>
                        <th>ACTUAL QTY</th>
                        <th>CUTTING QC</th>
                        <th>INPUT QTY</th>
                        <th>BALANCE</th>
                        <th>SHORT/PLUS</th>
                        <th>PERCENTAGE %</th>
                    </tr>
                </thead>
                <tbody>
                    {% set ns = namespace(tot_3=0, tot_act=0, tot_cut=0, tot_inp=0, tot_bal=0, tot_sp=0) %}
                    {% for i in range(block.headers|length) %}
                        {% set actual = block.gmts_qty[i]|replace(',', '')|int %}
                        {% set qty_3 = (actual * 1.03)|round|int %}
                        {% set cut_qc = 0 %}
                        {% if i < block.cutting_qc|length %}
                            {% set cut_qc = block.cutting_qc[i]|replace(',', '')|int %}
                        {% endif %}
                        {% set inp_qty = 0 %}
                        {% if i < block.sewing_input|length %}
                            {% set inp_qty = block.sewing_input[i]|replace(',', '')|int %}
                        {% endif %}
                        
                        {% set balance = cut_qc - inp_qty %}
                        {% set short_plus = inp_qty - qty_3 %}
                        {% set percentage = 0 %}
                        {% if qty_3 > 0 %}
                            {% set percentage = (short_plus / qty_3) * 100 %}
                        {% endif %}

                        {# Update Totals #}
                        {% set ns.tot_3 = ns.tot_3 + qty_3 %}
                        {% set ns.tot_act = ns.tot_act + actual %}
                        {% set ns.tot_cut = ns.tot_cut + cut_qc %}
                        {% set ns.tot_inp = ns.tot_inp + inp_qty %}
                        {% set ns.tot_bal = ns.tot_bal + balance %}
                        {% set ns.tot_sp = ns.tot_sp + short_plus %}

                        <tr>
                            <td>{{ block.headers[i] }}</td>
                            <td class="col-3pct">{{ qty_3 }}</td>
                            <td>{{ actual }}</td>
                            <td>{{ cut_qc }}</td>
                            <td class="col-input">{{ inp_qty }}</td>
                            <td class="col-balance">{{ balance }}</td>
                            <td style="color: {{ 'green' if short_plus >= 0 else 'red' }}">{{ short_plus }}</td>
                            <td>{{ "%.2f"|format(percentage) }}%</td>
                        </tr>
                    {% endfor %}
                    <tr class="total-row">
                        <td>TOTAL</td>
                        <td>{{ ns.tot_3 }}</td>
                        <td>{{ ns.tot_act }}</td>
                        <td>{{ ns.tot_cut }}</td>
                        <td>{{ ns.tot_inp }}</td>
                        <td>{{ ns.tot_bal }}</td>
                        <td>{{ ns.tot_sp }}</td>
                        <td>
                            {% if ns.tot_3 > 0 %}
                                {{ "%.2f"|format((ns.tot_sp / ns.tot_3) * 100) }}%
                            {% else %}
                                0.00%
                            {% endif %}
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endfor %}
        
        <div class="footer-credit">Report Generated By <span style="color: #000; font-weight: 900;">Mehedi Hasan</span></div>
        {% endif %}
    </div>
    <script>
        const dateObj = new Date();
        document.getElementById('date').innerText = dateObj.toLocaleDateString('en-GB');
    </script>
</body>
</html>
"""

# --- Report HTML Template for PO Sheet ---
PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PO Report - Cotton Clothing BD</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 1200px; }
        .company-header { text-align: center; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 10px; }
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; letter-spacing: 1px; line-height: 1; }
        .report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; margin-top: 5px; }
        .date-section { font-size: 1.2rem; font-weight: 800; color: #000; margin-top: 5px; }
        .info-container { display: flex; justify-content: space-between; margin-bottom: 15px; gap: 15px; }
        .info-box { background: white; border: 1px solid #ddd; border-left: 5px solid #2c3e50; padding: 10px 15px; border-radius: 5px; flex: 2; box-shadow: 0 2px 5px rgba(0,0,0,0.05); display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .total-box { background: #2c3e50; color: white; padding: 10px 15px; border-radius: 5px; width: 240px; text-align: right; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); }
        .info-item { margin-bottom: 6px; font-size: 1.3rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .info-label { font-weight: 800; color: #444; width: 90px; display: inline-block; }
        .info-value { font-weight: 800; color: #000; }
        .total-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
        .total-value { font-size: 2.5rem; font-weight: 800; line-height: 1.1; }
        .table-card { background: white; border-radius: 0; margin-bottom: 20px; overflow: hidden; border: 1px solid #dee2e6; }
        .color-header { background-color: #e9ecef; color: #2c3e50; padding: 10px 12px; font-size: 1.5rem; font-weight: 900; border-bottom: 1px solid #dee2e6; text-transform: uppercase; }
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; }
        .table th { background-color: #2c3e50; color: white; font-weight: 900; font-size: 1.2rem; text-align: center; border: 1px solid #34495e; padding: 8px 4px; vertical-align: middle; }
        .table td { text-align: center; vertical-align: middle; border: 1px solid #dee2e6; padding: 6px 3px; color: #000; font-weight: 800; font-size: 1.15rem; }
        .table-striped tbody tr:nth-of-type(odd) { background-color: #f8f9fa; }
        .order-col { font-weight: 900 !important; text-align: center !important; background-color: #fdfdfd; white-space: nowrap; width: 1%; }
        .total-col { font-weight: 900; background-color: #e8f6f3 !important; color: #16a085; border-left: 2px solid #1abc9c !important; }
        .total-col-header { background-color: #e8f6f3 !important; color: #000 !important; font-weight: 900 !important; border: 1px solid #34495e !important; }
        .table-striped tbody tr.summary-row, .table-striped tbody tr.summary-row td { background-color: #d1ecff !important; --bs-table-accent-bg: #d1ecff !important; color: #000 !important; font-weight: 900 !important; border-top: 2px solid #aaa !important; font-size: 1.2rem !important; }
        .summary-label { text-align: right !important; padding-right: 15px !important; color: #000 !important; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 10px; }
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 8px 30px; font-weight: 600; }
        .footer-credit { text-align: center; margin-top: 30px; margin-bottom: 20px; font-size: 0.8rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #ddd; }
        @media print {
            @page { margin: 5mm; size: portrait; }
            body { background-color: white; padding: 0; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }
            .container { max-width: 100% !important; width: 100% !important; padding: 0; margin: 0; }
            .no-print { display: none !important; }
            .company-header { border-bottom: 2px solid #000; margin-bottom: 5px; padding-bottom: 5px; }
            .company-name { font-size: 1.8rem; } 
            .info-container { margin-bottom: 10px; }
            .info-box { border: 1px solid #000 !important; border-left: 5px solid #000 !important; padding: 5px 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .total-box { border: 2px solid #000 !important; background: white !important; color: black !important; padding: 5px 10px; }
            .info-item { font-size: 13pt !important; font-weight: 800 !important; }
            .table th, .table td { border: 1px solid #000 !important; padding: 2px !important; font-size: 13pt !important; font-weight: 800 !important; }
            .table-striped tbody tr.summary-row td { background-color: #d1ecff !important; box-shadow: inset 0 0 0 9999px #d1ecff !important; color: #000 !important; font-weight: 900 !important; }
            .color-header { background-color: #f1f1f1 !important; border: 1px solid #000 !important; font-size: 1.4rem !important; font-weight: 900 !important; padding: 5px; margin-top: 10px; box-shadow: inset 0 0 0 9999px #f1f1f1 !important; }
            .total-col-header { background-color: #e8f6f3 !important; box-shadow: inset 0 0 0 9999px #e8f6f3 !important; color: #000 !important; }
            .table-card { border: none; margin-bottom: 10px; break-inside: avoid; }
            .footer-credit { display: block !important; color: black; border-top: 1px solid #000; margin-top: 10px; font-size: 8pt !important; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn btn-outline-secondary rounded-pill px-4">Back to Dashboard</a>
            <button onclick="window.print()" class="btn btn-print">🖨️ Print Report</button>
        </div>
        <div class="company-header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div class="report-title">Purchase Order Summary</div>
            <div class="date-section">Date: <span id="date"></span></div>
        </div>
        {% if message %}
            <div class="alert alert-warning text-center no-print">{{ message }}</div>
        {% endif %}
        {% if tables %}
            <div class="info-container">
                <div class="info-box">
                    <div>
                        <div class="info-item"><span class="info-label">Buyer:</span> <span class="info-value">{{ meta.buyer }}</span></div>
                        <div class="info-item"><span class="info-label">Booking:</span> <span class="info-value">{{ meta.booking }}</span></div>
                        <div class="info-item"><span class="info-label">Style:</span> <span class="info-value">{{ meta.style }}</span></div>
                    </div>
                    <div>
                        <div class="info-item"><span class="info-label">Season:</span> <span class="info-value">{{ meta.season }}</span></div>
                        <div class="info-item"><span class="info-label">Dept:</span> <span class="info-value">{{ meta.dept }}</span></div>
                        <div class="info-item"><span class="info-label">Item:</span> <span class="info-value">{{ meta.item }}</span></div>
                    </div>
                </div>
                <div class="total-box">
                    <div class="total-label">Grand Total</div>
                    <div class="total-value">{{ grand_total }}</div>
                    <small>Pieces</small>
                </div>
            </div>
            {% for item in tables %}
                <div class="table-card">
                    <div class="color-header">COLOR: {{ item.color }}</div>
                    <div class="table-responsive">{{ item.table | safe }}</div>
                </div>
            {% endfor %}
            <div class="footer-credit">Report Created By <strong>Mehedi Hasan</strong></div>
        {% endif %}
    </div>
    <script>
        const dateObj = new Date();
        const day = String(dateObj.getDate()).padStart(2, '0');
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();
        document.getElementById('date').innerText = `${day}-${month}-${year}`;
    </script>
</body>
</html>
"""

# --- USER MANAGEMENT DASHBOARD ---
ADMIN_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Console</title>
    {COMMON_STYLES}
    <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
</head>
<body>
    <div id="loading-overlay" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:999; justify-content:center; align-items:center; color:white;">
        <div>Processing...</div>
    </div>

    <div class="admin-container">
        <div class="admin-sidebar">
            <h2 style="color:white; text-align:center; margin-bottom:30px;">Admin Panel</h2>
            <div style="flex:1;">
                <a class="nav-link active" onclick="showSection('closing', this)"><i class="fas fa-file-export"></i> &nbsp; Closing Report</a>
                <a class="nav-link" href="/admin/accessories"><i class="fas fa-box-open"></i> &nbsp; Accessories Challan</a>
                <a class="nav-link" onclick="showSection('purchase-order', this)"><i class="fas fa-file-invoice"></i> &nbsp; PO Sheet</a>
                <a class="nav-link" onclick="showSection('user-manage', this)"><i class="fas fa-users-cog"></i> &nbsp; Users</a>
            </div>
            <a href="/logout" class="nav-link" style="color:#ff7675;"><i class="fas fa-sign-out-alt"></i> &nbsp; Logout</a>
        </div>

        <div class="admin-content">
            <div class="work-area">
                
                <div id="closing-section" class="work-section" style="width: 100%; max-width: 500px;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 20px;"><i class="fas fa-file-export"></i> Closing Report</h2>
                        <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                            <div class="input-group">
                                <label>Internal Reference No</label>
                                <input type="text" name="ref_no" placeholder="Enter Ref No (e.g. DFL/24/..)" required>
                            </div>
                            <button type="submit">Generate Report</button>
                        </form>
                    </div>
                </div>

                <div id="purchase-order-section" class="work-section" style="display:none; width: 100%; max-width: 500px;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 20px;"><i class="fas fa-file-invoice"></i> PDF Report Generator</h2>
                        <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                            <div class="input-group">
                                <label>Select PDF Files (Booking & PO)</label>
                                <input type="file" name="pdf_files" multiple accept=".pdf" required style="padding:10px;">
                            </div>
                            <button type="submit">Generate Report</button>
                        </form>
                    </div>
                </div>

                <div id="user-manage-section" class="work-section" style="display:none; width: 100%; max-width: 700px;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 20px;"><i class="fas fa-users-cog"></i> User Management</h2>
                        <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                            <h4 style="font-size: 14px; margin-bottom: 10px; color: #a29bfe;">Create / Update User</h4>
                            <form id="userForm">
                                <input type="hidden" id="action_type" name="action_type" value="create">
                                <div style="display: flex; gap: 10px;">
                                    <div class="input-group" style="flex: 1; margin-bottom: 10px;">
                                        <input type="text" id="new_username" name="username" placeholder="Username" required>
                                    </div>
                                    <div class="input-group" style="flex: 1; margin-bottom: 10px;">
                                        <input type="text" id="new_password" name="password" placeholder="Password" required>
                                    </div>
                                </div>
                                <div class="input-group" style="margin-bottom: 10px;">
                                    <label>Permissions:</label>
                                    <div style="display:flex; gap:10px;">
                                        <label><input type="checkbox" name="permissions" value="closing" checked style="width:auto;"> Closing</label>
                                        <label><input type="checkbox" name="permissions" value="po_sheet" style="width:auto;"> PO Sheet</label>
                                    </div>
                                </div>
                                <button type="button" onclick="handleUserSubmit(event)" id="saveUserBtn">Create User</button>
                            </form>
                        </div>
                        <div id="userListContainer"></div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
        function showSection(sectionId, element) {{
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
            document.querySelectorAll('.work-section').forEach(el => el.style.display = 'none');
            document.getElementById(sectionId + '-section').style.display = 'block';
            if(sectionId === 'user-manage') loadUsers();
        }}

        function loadUsers() {{
            fetch('/admin/get-users').then(res => res.json()).then(data => {{
                let html = '<table class="table-dark"><thead><tr><th>User</th><th>Role</th><th>Action</th></tr></thead><tbody>';
                for (const [user, details] of Object.entries(data)) {{
                    html += `<tr><td>${{user}}</td><td>${{details.role}}</td><td>
                    ${{details.role !== 'admin' ? `<button class="action-btn btn-delete" onclick="deleteUser('${{user}}')">Delete</button>` : 'Main Admin'}}
                    </td></tr>`;
                }}
                html += '</tbody></table>';
                document.getElementById('userListContainer').innerHTML = html;
            }});
        }}

        function handleUserSubmit(e) {{
            const username = document.getElementById('new_username').value;
            const password = document.getElementById('new_password').value;
            if(!username || !password) return;
            
            fetch('/admin/save-user', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ username, password, action_type: 'create', permissions: ['closing'] }})
            }}).then(res => res.json()).then(data => {{
                swal("Success", data.message, "success");
                loadUsers();
            }});
        }}

        function deleteUser(user) {{
            if(confirm("Delete user?")) {{
                fetch('/admin/delete-user', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ username: user }})
                }}).then(res => res.json()).then(data => {{ loadUsers(); }});
            }}
        }}
    </script>
</body>
</html>
"""

# --- Flask রুট ---

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        LOGIN_TEMPLATE = f"""
        <!doctype html><html lang="en"><head><meta charset="utf-8"><title>Login</title>{COMMON_STYLES}</head>
        <body><div class="center-container"><div class="glass-card" style="max-width:400px; text-align:center;">
        <h1 style="margin-bottom:20px;">SYSTEM ACCESS</h1>
        <form action="/login" method="post"><div class="input-group"><label>Username</label><input type="text" name="username" required></div>
        <div class="input-group"><label>Password</label><input type="password" name="password" required></div><button type="submit">Verify & Enter</button></form>
        </div></div></body></html>
        """
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, session=session)
        else:
            return "User Dashboard (Restricted View)" # Simplified for length

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    users_db = load_users()
    if username in users_db and users_db[username]['password'] == password:
        session['logged_in'] = True
        session['user'] = username
        session['role'] = users_db[username]['role']
        session['permissions'] = users_db[username].get('permissions', [])
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- USER MANAGEMENT API ---
@app.route('/admin/get-users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({})
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error'})
    data = request.json
    username, password = data.get('username'), data.get('password')
    users_db = load_users()
    users_db[username] = {"password": password, "role": "user", "permissions": data.get('permissions', [])}
    save_users(users_db)
    return jsonify({'status': 'success', 'message': 'User saved!'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error'})
    username = request.json.get('username')
    users_db = load_users()
    if username != 'Admin' and username in users_db:
        del users_db[username]
        save_users(users_db)
    return jsonify({'status': 'success'})

# --- CLOSING REPORT ROUTE ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref_no = request.form['ref_no']
    report_data = fetch_closing_report_data(ref_no)
    if not report_data:
        return "<h3>No Data Found</h3><a href='/'>Back</a>"
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=ref_no)

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref_no = request.args.get('ref_no')
    report_data = fetch_closing_report_data(ref_no)
    excel_stream = create_formatted_excel_report(report_data, ref_no)
    if excel_stream:
        update_stats(ref_no, session.get('user', 'Unknown'))
        return make_response(send_file(excel_stream, as_attachment=True, download_name=f"Report-{ref_no}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    return redirect(url_for('index'))

# --- PO SHEET ROUTE ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
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
    
    if not all_data: return "No data found in PDFs."

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
        actual_qty = pivot.sum(); actual_qty.name = 'Actual Qty'
        qty_plus_3 = (actual_qty * 1.03).round().astype(int); qty_plus_3.name = '3% Order Qty'
        pivot = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
        pivot = pivot.reset_index().rename(columns={'index': 'P.O NO'})
        
        table_html = pivot.to_html(classes='table table-bordered table-striped', index=False, border=0)
        table_html = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', table_html)
        table_html = table_html.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
        table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        table_html = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', table_html.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>').replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>'))
        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

# ==============================================================================
# ACCESSORIES ROUTES (UPDATED LOGIC)
# ==============================================================================

@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['GET', 'POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if request.method == 'POST':
        ref_no = request.form.get('ref_no', '').strip()
    else:
        ref_no = request.args.get('ref_no', '').strip()
        
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()
    
    # Load or Initialize Data
    if ref_no in db:
        data = db[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
        challans = data.get('challans', [])
    else:
        # Fetch from API
        try:
            api_data = fetch_closing_report_data(ref_no)
        except:
            api_data = None
            
        if api_data:
            colors = sorted(list(set([item['color'] for item in api_data])))
            style = api_data[0].get('style', 'N/A')
            buyer = api_data[0].get('buyer', 'N/A')
        else:
            # Fallback if API fails (Manual Entry Setup)
            colors = ["BLACK", "WHITE", "NAVY", "RED", "BLUE"] 
            style = "Manual Entry"
            buyer = "Manual Entry"
        
        db[ref_no] = {"style": style, "buyer": buyer, "colors": colors, "challans": []}
        save_accessories_db(db)
        challans = []

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer, challans=challans, edit_data=None)

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    entry_id = request.form.get('id')
    
    new_data = {
        "id": entry_id if entry_id else str(uuid.uuid4()),
        "date": datetime.now().strftime("%d-%m-%Y"),
        "line": request.form.get('line_no'),
        "color": request.form.get('color'),
        "item_type": request.form.get('item_type'),
        "size": request.form.get('size'),
        "qty": request.form.get('qty')
    }
    
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search_page'))
    
    history = db[ref]['challans']
    
    if entry_id:
        # Update Existing
        for idx, item in enumerate(history):
            if item['id'] == entry_id:
                new_data['date'] = item['date'] # Keep original date
                history[idx] = new_data
                break
    else:
        # Add New
        history.append(new_data)
        
    db[ref]['challans'] = history
    save_accessories_db(db)
    return redirect(url_for('accessories_input_page', ref_no=ref))

@app.route('/admin/accessories/edit/<ref>/<id>')
def accessories_edit(ref, id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search_page'))
    
    data = db[ref]
    target = next((item for item in data['challans'] if item['id'] == id), None)
    
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, 
                                  ref=ref, colors=data['colors'], style=data['style'], 
                                  buyer=data['buyer'], challans=data['challans'], edit_data=target)

@app.route('/admin/accessories/delete/<ref>/<id>')
def accessories_delete(ref, id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    db = load_accessories_db()
    if ref in db:
        db[ref]['challans'] = [item for item in db[ref]['challans'] if item['id'] != id]
        save_accessories_db(db)
    return redirect(url_for('accessories_input_page', ref_no=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref')
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search_page'))
    
    data = db[ref]
    challans = data['challans']
    
    # Summary Logic (Sum Qty per Line)
    summary = {}
    for c in challans:
        line = c['line']
        try: qty = int(c['qty'])
        except: qty = 0
        summary[line] = summary.get(line, 0) + qty
    
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref, buyer=data['buyer'], style=data['style'], 
                                  challans=challans, summary=dict(sorted(summary.items())), 
                                  today=datetime.now().strftime("%d-%m-%Y"), session=session)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
