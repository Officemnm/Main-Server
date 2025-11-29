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
from pymongo import MongoClient 

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
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# ==============================================================================
# Browser Cache Control (ব্যাক বাটন ফিক্স)
# ==============================================================================
@app.after_request
def add_header(response):
    """
    লগআউট করার পর ব্যাক বাটন চাপলে যেন আগের পেজ না দেখায়,
    তার জন্য ব্রাউজার ক্যাশ ক্লিয়ার করার নির্দেশ।
    """
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ==============================================================================
# MongoDB কানেকশন সেটআপ (JSON ফাইলের পরিবর্তে)
# ==============================================================================
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/?appName=Office"

try:
    client = MongoClient(MONGO_URI)
    db = client['office_db']
    
    users_col = db['users']
    stats_col = db['stats']
    accessories_col = db['accessories']
    print("MongoDB Connected Successfully!")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (MongoDB ব্যবহার করে)
# ==============================================================================

def load_users():
    record = users_col.find_one({"_id": "global_users"})
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"]
        }
    }
    if record:
        return record['data']
    else:
        users_col.insert_one({"_id": "global_users", "data": default_users})
        return default_users

def save_users(users_data):
    users_col.replace_one(
        {"_id": "global_users"}, 
        {"_id": "global_users", "data": users_data}, 
        upsert=True
    )

def load_stats():
    record = stats_col.find_one({"_id": "dashboard_stats"})
    if record:
        return record['data']
    else:
        default_stats = {"downloads": [], "last_booking": "None"}
        stats_col.insert_one({"_id": "dashboard_stats", "data": default_stats})
        return default_stats

def save_stats(data):
    stats_col.replace_one(
        {"_id": "dashboard_stats"},
        {"_id": "dashboard_stats", "data": data},
        upsert=True
    )

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
    if len(data['downloads']) > 1000:
        data['downloads'] = data['downloads'][:1000]
        
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

def load_accessories_db():
    record = accessories_col.find_one({"_id": "accessories_data"})
    if record:
        return record['data']
    else:
        return {}

def save_accessories_db(data):
    accessories_col.replace_one(
        {"_id": "accessories_data"},
        {"_id": "accessories_data", "data": data},
        upsert=True
    )

# ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER
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
# CSS & HTML Templates (Updated with Modern Animations & Branding)
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary-grad: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --glass-bg: rgba(255, 255, 255, 0.15);
            --glass-border: rgba(255, 255, 255, 0.2);
            --dark-overlay: rgba(0, 0, 0, 0.4);
        }
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
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: var(--dark-overlay); z-index: -1;
        }
        
        /* Modern Glass Card */
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            color: white;
            animation: floatIn 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
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
            max-width: 420px;
            text-align: center;
        }

        @keyframes floatIn {
            from { opacity: 0; transform: translateY(40px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        h1 { color: #ffffff; font-size: 28px; font-weight: 700; margin-bottom: 5px; text-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        p.subtitle { color: #e0e0e0; font-size: 14px; margin-bottom: 30px; font-weight: 300; letter-spacing: 0.5px; }
        
        /* Inputs */
        .input-group { text-align: left; margin-bottom: 20px; }
        .input-group label {
            display: block; font-size: 12px; color: #f1f2f6; font-weight: 600;
            margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px;
        }
        
        input[type="password"], input[type="text"], input[type="file"], select, input[type="number"] {
            width: 100%; padding: 14px 18px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            font-size: 15px; color: #fff;
            transition: all 0.3s ease; outline: none;
        }
        input:focus, select:focus {
            background: rgba(255, 255, 255, 0.25);
            border-color: #a29bfe;
            box-shadow: 0 0 15px rgba(162, 155, 254, 0.3);
            transform: translateY(-2px);
        }
        
        /* Buttons */
        button {
            width: 100%; padding: 15px;
            background: var(--primary-grad);
            color: white; border: none;
            border-radius: 12px; font-size: 16px; font-weight: 600;
            cursor: pointer; transition: all 0.3s ease;
            margin-top: 15px; letter-spacing: 0.5px;
            box-shadow: 0 4px 15px rgba(108, 92, 231, 0.4);
            position: relative; overflow: hidden;
        }
        button:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(108, 92, 231, 0.5);
        }
        button:active { transform: scale(0.98); }

        /* Footer Credit */
        .footer-credit {
            margin-top: 25px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.5);
            text-align: center;
            font-weight: 400;
            letter-spacing: 1px;
        }

        /* Success & Loading Animation Overlay */
        #loading-overlay {
            display: none;
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(10px);
            z-index: 9999;
            flex-direction: column; justify-content: center; align-items: center;
            color: white; transition: opacity 0.4s ease;
        }
        
        /* Animated Spinner */
        .spinner {
            width: 70px; height: 70px;
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-left-color: #00cec9; border-right-color: #6c5ce7;
            border-radius: 50%;
            animation: spin 0.8s cubic-bezier(0.68, -0.55, 0.265, 1.55) infinite;
            margin-bottom: 25px;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }

        /* Success Checkmark Animation */
        .success-checkmark {
            display: none; width: 80px; height: 80px;
            border-radius: 50%; display: block;
            stroke-width: 2; stroke: #00b894; stroke-miterlimit: 10;
            box-shadow: inset 0px 0px 0px #00b894;
            animation: fill .4s ease-in-out .4s forwards, scale .3s ease-in-out .9s both;
            margin-bottom: 20px;
        }
        .checkmark__circle { stroke-dasharray: 166; stroke-dashoffset: 166; stroke-width: 2; stroke-miterlimit: 10; stroke: #00b894; fill: none; animation: stroke 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards; }
        .checkmark__check { transform-origin: 50% 50%; stroke-dasharray: 48; stroke-dashoffset: 48; animation: stroke 0.3s cubic-bezier(0.65, 0, 0.45, 1) 0.8s forwards; }
        @keyframes stroke { 100% { stroke-dashoffset: 0; } }
        @keyframes scale { 0%, 100% { transform: none; } 50% { transform: scale3d(1.1, 1.1, 1); } }
        @keyframes fill { 100% { box-shadow: inset 0px 0px 0px 30px rgba(0, 184, 148, 0.1); } }

        #loading-text { font-size: 20px; font-weight: 600; letter-spacing: 1px; text-align: center; opacity: 0.9; }
        .loader-success .spinner { display: none; }
        .loader-success .success-container { display: block; }
        .success-container { display: none; text-align: center; }

        /* Navigation & Sidebar (Admin) */
        .admin-container { display: flex; width: 100%; height: 100vh; position: fixed; top: 0; left: 0;}
        .admin-sidebar {
            width: 280px; background: rgba(30, 39, 46, 0.85);
            backdrop-filter: blur(20px); border-right: 1px solid rgba(255,255,255,0.05);
            display: flex; flex-direction: column; padding: 30px 20px;
        }
        .sidebar-header { margin-bottom: 40px; text-align: center; }
        .sidebar-header h2 { color: white; font-size: 20px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; }
        .nav-link {
            display: flex; align-items: center; padding: 14px 18px;
            color: rgba(255,255,255,0.7); text-decoration: none; border-radius: 12px;
            margin-bottom: 10px; transition: all 0.3s ease; font-weight: 500; font-size: 14px; cursor: pointer;
        }
        .nav-link:hover, .nav-link.active {
            background: var(--primary-grad); color: white;
            box-shadow: 0 4px 15px rgba(118, 75, 162, 0.3); transform: translateX(5px);
        }
        .nav-link i { width: 25px; text-align: center; margin-right: 10px; font-size: 16px; }

        .admin-content { flex: 1; padding: 30px; overflow-y: auto; }
        .work-section { animation: fadeIn 0.5s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
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
# --- NEW: ACCESSORIES SEARCH TEMPLATE (Updated with Logout) ---
ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1><i class="fas fa-boxes"></i> Accessories Dashboard</h1>
            <p class="subtitle">Find Booking to Manage Challan</p>
            
            <form action="/admin/accessories/input" method="post">
                <div class="input-group">
                    <label for="ref_no">Booking Reference No</label>
                    <input type="text" id="ref_no" name="ref_no" placeholder="e.g. Booking-123..." required>
                </div>
                <button type="submit">Proceed</button>
            </form>
            
            <div style="margin-top: 25px; display: flex; justify-content: center; gap: 20px; align-items: center;">
                {{% if session.role == 'admin' %}}
                <a href="/" style="color:white; text-decoration:none; font-size:13px; opacity:0.8;"><i class="fas fa-arrow-left"></i> Admin Dashboard</a>
                {{% endif %}}
                
                <a href="/logout" style="color:#ff7675; text-decoration:none; font-size:13px; border: 1px solid rgba(255, 118, 117, 0.5); padding: 8px 15px; border-radius: 20px; transition: all 0.3s ease;">
                    <i class="fas fa-sign-out-alt"></i> Sign Out
                </a>
            </div>

            <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

# --- NEW: ACCESSORIES INPUT TEMPLATE ---
ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Challan Entry</title>
    {COMMON_STYLES}
    <style>
        /* Fix for White Text on White Background in Select Dropdown */
        option {{
            color: #000;
            background: #fff;
        }}
    </style>
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-container">
             <svg class="success-checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
            </svg>
        </div>
        <div id="loading-text">Saving Record...</div>
    </div>

    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1><i class="fas fa-plus-circle"></i> New Challan</h1>
            <p class="subtitle">Booking: {{{{ ref }}}}</p>
            <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 12px; margin-bottom: 25px; font-size: 13px; border: 1px solid rgba(255,255,255,0.1);">
                <strong>Buyer:</strong> {{{{ buyer }}}} <br> <strong>Style:</strong> {{{{ style }}}}
            </div>

            <form action="/admin/accessories/save" method="post" onsubmit="showSuccessAnim()">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                
                <div class="input-group">
                    <label>Select Item Type</label>
                    <select name="item_type">
                        <option value="" disabled selected>-- Select Item (Top/Btm) --</option>
                        <option value="Top">Top</option>
                        <option value="Bottom">Bottom</option>
                    </select>
                </div>

                <div class="input-group">
                    <label>Select Color</label>
                    <select name="color" required>
                        <option value="" disabled selected>-- Choose Color --</option>
                        {{% for color in colors %}}
                        <option value="{{{{ color }}}}">{{{{ color }}}}</option>
                        {{% endfor %}}
                    </select>
                </div>

                <div class="input-group">
                    <label>Sewing Line Number</label>
                    <input type="text" name="line_no" placeholder="e.g. Line-12" required>
                </div>
                
                <div class="input-group">
                    <label>Size (Optional)</label>
                    <input type="text" name="size" placeholder="e.g. XL or ALL" value="-">
                </div>

                <div class="input-group">
                    <label>Quantity</label>
                    <input type="number" name="qty" placeholder="Enter Qty" required>
                </div>

                <button type="submit">Save & View Report</button>
            </form>
            <div style="margin-top: 15px;">
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:#a29bfe; font-size:12px; margin-right: 15px; font-weight:600;">View Report Only</a>
                <a href="/admin/accessories" style="color:white; text-decoration:none; font-size:12px;">Back</a>
            </div>
             <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
    <script>
        function showSuccessAnim() {{
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.querySelector('.spinner');
            const successContainer = document.querySelector('.success-container');
            const text = document.getElementById('loading-text');
            
            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            successContainer.style.display = 'none';
            text.innerText = 'Processing...';

            // Simulate slight delay then show success
            setTimeout(() => {{
                spinner.style.display = 'none';
                successContainer.style.display = 'block';
                overlay.classList.add('loader-success');
                text.innerText = 'Saved Successfully!';
            }}, 800);
            return true;
        }}
    </script>
</body>
</html>
"""

# --- NEW: ACCESSORIES EDIT TEMPLATE ---
ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1><i class="fas fa-edit"></i> Edit Challan</h1>
            <p class="subtitle">Update entry for {{{{ ref }}}}</p>

            <form action="/admin/accessories/update" method="post">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <input type="hidden" name="index" value="{{{{ index }}}}">

                <div class="input-group">
                    <label>Sewing Line Number</label>
                    <input type="text" name="line_no" value="{{{{ item.line }}}}" required>
                </div>
                
                <div class="input-group">
                    <label>Color</label>
                    <input type="text" name="color" value="{{{{ item.color }}}}" required>
                </div>

                <div class="input-group">
                    <label>Size</label>
                    <input type="text" name="size" value="{{{{ item.size }}}}" required>
                </div>

                <div class="input-group">
                    <label>Quantity</label>
                    <input type="number" name="qty" value="{{{{ item.qty }}}}" required>
                </div>

                <button type="submit">Update Entry</button>
            </form>
            <br>
            <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:white; text-decoration:none; font-size:12px;">Cancel</a>
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

# --- UPDATED: ACCESSORIES REPORT (PRINT VIEW - With User Restrictions) ---
ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessories Delivery Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { font-family: 'Poppins', sans-serif; background: #fff; padding: 20px; color: #000; }
        .container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; position: relative; }
        
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; position: relative; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; line-height: 1; }
        .company-address { font-size: 12px; font-weight: 600; color: #444; margin-top: 5px; margin-bottom: 10px; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 18px; border-radius: 4px; }
        
        .info-grid { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
        
        .info-left { flex: 2; border: 1px dashed #555; padding: 15px; margin-right: 15px; }
        .info-row { display: flex; margin-bottom: 5px; font-size: 14px; align-items: center; }
        .info-label { font-weight: 800; width: 80px; color: #444; }
        .info-val { font-weight: 700; font-size: 15px; color: #000; }
        
        .booking-border { border: 2px solid #000; padding: 2px 8px; display: inline-block; font-weight: 900; }

        .info-right { flex: 1; display: flex; flex-direction: column; justify-content: space-between; height: 100%; border-left: 1px solid #ddd; padding-left: 15px; }
        .right-item { font-size: 14px; margin-bottom: 8px; font-weight: 700; }
        .right-label { color: #555; }
        
        /* Summary Table */
        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .summary-header { font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px; text-transform: uppercase; }
        .summary-table { width: 100%; font-size: 13px; font-weight: 700; }
        .summary-table td { padding: 2px 5px; }
        
        /* The Main Table */
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 10px; border: 1px solid #000; font-size: 14px; text-transform: uppercase; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; vertical-align: middle; color: #000; font-weight: 600; }
        
        .line-card { 
            display: inline-block; padding: 4px 10px; 
            border: 2px solid #000; font-size: 16px; font-weight: 900; 
            border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff;
        }
        .line-text-bold { font-size: 14px; font-weight: 800; opacity: 0.7; }
        .status-cell { font-size: 20px; color: green; font-weight: 900; }
        .qty-cell { font-size: 16px; font-weight: 800; }
        
        /* Actions Column */
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; margin: 0 2px; display: inline-block; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }

        /* Footer Total */
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }

        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; }
        .btn-add { background: #27ae60; }
        
        /* Generator Signature */
        .generator-sig { text-align: right; font-size: 10px; margin-top: 5px; color: #555; }

        @media print {
            .no-print { display: none; }
            .action-col { display: none; }
            .container { border: none; padding: 0; margin: 0; max-width: 100%; }
            body { padding: 0; }
        }
    </style>
</head>
<body>

<div class="no-print">
    <a href="/admin/accessories" class="btn">Back</a>
    <form action="/admin/accessories/input" method="post" style="display:inline;">
        <input type="hidden" name="ref_no" value="{{ ref }}">
        <button type="submit" class="btn btn-add">Add New Challan</button>
    </form>
    <button onclick="window.print()" class="btn">🖨️ Print</button>
</div>

<div class="container">
    <div class="header">
        <div class="company-name">Cotton Clothing BD Limited</div>
        <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
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
            <div class="right-item"><span class="right-label">Store:</span> Clothing General Store</div>
            <div class="right-item"><span class="right-label">Send:</span> Cutting</div>
            <div class="right-item"><span class="right-label">Item:</span> <span style="border: 1px solid #000; padding: 0 5px;">{{ item_type if item_type else 'Top/Btm' }}</span></div>
        </div>
    </div>

    <div class="summary-container">
        <div class="summary-header">Line-wise Summary</div>
        <table class="summary-table">
            <tr>
            {% for line, qty in line_summary.items() %}
                <td>{{ line }}: {{ qty }} pcs</td>
                {% if loop.index % 4 == 0 %}</tr><tr>{% endif %}
            {% endfor %}
            </tr>
        </table>
        <div style="text-align: right; margin-top: 5px; font-weight: 800; border-top: 1px solid #ccc;">Total Deliveries: {{ count }}</div>
    </div>

    <table class="main-table">
        <thead>
            <tr>
                <th width="15%">DATE</th>
                <th width="15%">LINE NO</th>
                <th width="20%">COLOR</th>
                <th width="10%">SIZE</th>
                <th width="10%">STATUS</th>
                <th width="15%">QTY</th>
                {% if session.role == 'admin' %}
                <th width="15%" class="action-col">ACTION</th>
                {% endif %}
            </tr>
        </thead>
        <tbody>
            {% set ns = namespace(grand_total=0) %}
            {% for item in challans %}
                {% set ns.grand_total = ns.grand_total + item.qty|int %}
                <tr>
                    <td>{{ item.date }}</td>
                    <td>
                        {% if loop.index == count %}
                            <div class="line-card">{{ item.line }}</div>
                        {% else %}
                            <span class="line-text-bold">{{ item.line }}</span>
                        {% endif %}
                    </td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td class="status-cell">{{ item.status }}</td>
                    <td class="qty-cell">{{ item.qty }}</td>
                    {% if session.role == 'admin' %}
                    <td class="action-col">
                        <a href="/admin/accessories/edit?ref={{ ref }}&index={{ loop.index0 }}" class="action-btn btn-edit-row"><i class="fas fa-pencil-alt"></i></a>
                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete this challan?');">
                            <input type="hidden" name="ref" value="{{ ref }}">
                            <input type="hidden" name="index" value="{{ loop.index0 }}">
                            <button type="submit" class="action-btn btn-del-row" style="border:none; cursor:pointer;"><i class="fas fa-trash"></i></button>
                        </form>
                    </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="footer-total">
        <div class="total-box">
            TOTAL QTY: {{ ns.grand_total }}
        </div>
    </div>
    <div class="generator-sig">Report Generated By Mehedi Hasan</div>

    <div style="margin-top: 60px; display: flex; justify-content: space-between; text-align: center; font-weight: bold; padding: 0 50px;">
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Store Incharge</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Received By</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Cutting Incharge</div>
    </div>
</div>

</body>
</html>
"""

# --- Report HTML Template for PO Sheet (Print Friendly) ---
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
            .color-header { background-color: #f1f1f1 !important; border: 1px solid #000 !important; font-size: 1.4rem !important; font-weight: 900; padding: 5px; margin-top: 10px; box-shadow: inset 0 0 0 9999px #f1f1f1 !important; }
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

# --- LOGIN TEMPLATE ---
LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ERP Login</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <h1>System Access</h1>
            <p class="subtitle">Secure Gateway for ERP Reports</p>
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
                    <div class="flash" style="background: rgba(231, 76, 60, 0.8); padding: 10px; border-radius: 8px; margin-top: 15px; font-size: 13px;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            <div class="footer-credit">© Mehedi Hasan</div>
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
    <title>User Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-container">
             <svg class="success-checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
            </svg>
        </div>
        <div id="loading-text">Generating Report...</div>
    </div>

    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1>User Dashboard</h1>
            <p class="subtitle">Welcome, <span style="font-weight:600; color:#a29bfe;">{{{{ session.user }}}}</span></p>
            
            {{% if 'closing' in session.permissions %}}
            <div style="margin-bottom: 25px;">
                <h4 style="margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:5px; font-size: 16px;">Closing Report</h4>
                <form action="/generate-report" method="post" id="reportForm" onsubmit="startDownloadProcess()">
                    <div class="input-group">
                        <label for="ref_no">Internal Reference No</label>
                        <input type="text" id="ref_no" name="ref_no" placeholder="Booking-123/456.." required>
                        <input type="hidden" name="download_token" id="download_token">
                    </div>
                    <button type="submit">Generate Report</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'po_sheet' in session.permissions %}}
             <div style="margin-bottom: 25px;">
                <h4 style="margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:5px; font-size: 16px;">PO Sheet Generator</h4>
                 <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="startDownloadProcess()">
                    <div class="input-group">
                        <label for="pdf_files">Select PDF Files</label>
                        <input type="file" id="pdf_files" name="pdf_files" multiple accept=".pdf" required>
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">Generate Report</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'accessories' in session.permissions %}}
            <div style="margin-bottom: 25px;">
                <h4 style="margin-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.2); padding-bottom:5px; font-size: 16px;">Accessories</h4>
                <a href="/admin/accessories" style="display:block; width:100%; text-align:center; padding: 14px; background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%); color:white; border-radius:12px; text-decoration:none; font-weight:600; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                    <i class="fas fa-boxes"></i> Open Accessories Dashboard
                </a>
            </div>
            {{% endif %}}

            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash" style="background: rgba(231, 76, 60, 0.8); padding: 10px; border-radius: 8px; margin-top: 15px; font-size: 13px;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            
            <a href="/logout" style="display: inline-block; margin-top: 20px; color: rgba(255,255,255,0.7); text-decoration: none; font-size: 13px; padding: 5px 15px; border: 1px solid rgba(255,255,255,0.2); border-radius: 20px;">Sign Out</a>
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
    <script>
        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); 
            const spinner = document.querySelector('.spinner');
            const successContainer = document.querySelector('.success-container');
            const text = document.getElementById('loading-text');

            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            successContainer.style.display = 'none';
            text.innerText = 'Processing...';
            
            // Allow form to submit, but keep overlay for visual effect
            setTimeout(() => {{
                spinner.style.display = 'none';
                successContainer.style.display = 'block';
                overlay.classList.add('loader-success');
                text.innerText = 'Done!';
                setTimeout(() => {{ overlay.style.display = 'none'; overlay.classList.remove('loader-success'); }}, 1500);
            }}, 3000);
            return true;
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
    <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
    <style>
        /* Specific Styles for Admin Table */
        .user-table {{ width: 100%; border-collapse: separate; border-spacing: 0 8px; color: white; margin-top: 20px; }}
        .user-table th {{ padding: 15px; background: rgba(255,255,255,0.1); font-weight: 600; text-align: left; first-child: border-radius: 10px 0 0 10px; last-child: border-radius: 0 10px 10px 0; }}
        .user-table td {{ padding: 15px; background: rgba(255,255,255,0.05); text-align: left; }}
        .user-table tr:hover td {{ background: rgba(255,255,255,0.1); }}
        .user-btn {{ padding: 8px 12px; border-radius: 8px; border: none; font-size: 12px; cursor: pointer; color: white; margin-right: 5px; }}
        .btn-edit {{ background: #f39c12; }}
        .btn-delete {{ background: #e74c3c; }}
        .btn-reset {{ background: #95a5a6; width: auto; margin-top: 5px; }}
        .perm-group {{ display: flex; gap: 15px; margin-top: 5px; flex-wrap: wrap; }}
        .perm-item {{ display: flex; align-items: center; font-size: 13px; color: white; background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 20px; }}
        .perm-item input {{ width: auto; margin-right: 8px; accent-color: #6c5ce7; }}
    </style>
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-container">
             <svg class="success-checkmark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle class="checkmark__circle" cx="26" cy="26" r="25" fill="none"/>
                <path class="checkmark__check" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8"/>
            </svg>
        </div>
        <div id="loading-text">Processing...</div>
    </div>

    <div class="admin-container">
        <div class="admin-sidebar">
            <div class="sidebar-header">
                <h2>Admin Panel</h2>
                <p style="font-size: 11px; opacity: 0.6;">SUPER ADMIN ACCESS</p>
            </div>
            
            <ul class="nav-menu">
                <li class="nav-item">
                    <a class="nav-link active" onclick="showSection('closing', this)">
                        <i class="fas fa-file-export"></i> Closing Report
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/admin/accessories">
                        <i class="fas fa-box-open"></i> Accessories Dashboard
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showSection('purchase-order', this)">
                        <i class="fas fa-file-invoice"></i> PO Sheet Generator
                    </a>
                </li>
                 <li class="nav-item">
                    <a class="nav-link" onclick="showSection('user-manage', this)">
                        <i class="fas fa-users-cog"></i> User Management
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showSection('history', this)">
                        <i class="fas fa-history"></i> Closing History
                    </a>
                </li>
            </ul>
            
            <div style="margin-top: auto; border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 20px; text-align: center;">
                <a href="/logout" class="nav-link" style="color: #ff7675; justify-content: center;">
                    <i class="fas fa-sign-out-alt"></i> Sign Out
                </a>
                <div class="footer-credit">© Mehedi Hasan</div>
            </div>
        </div>

        <div class="admin-content">
            <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 25px; margin-bottom: 30px;">
                <div class="glass-card" style="padding: 25px; display: flex; align-items: center; min-height: 100px; animation-delay: 0.1s;">
                    <div style="font-size: 30px; margin-right: 20px; color: #a29bfe;"><i class="fas fa-calendar-day"></i></div>
                    <div>
                        <h3 style="font-size: 24px;">{{{{ stats.today }}}}</h3>
                        <p style="margin: 0; font-size: 12px; opacity: 0.7;">Today's Downloads</p>
                    </div>
                </div>
                <div class="glass-card" style="padding: 25px; display: flex; align-items: center; min-height: 100px; animation-delay: 0.2s;">
                    <div style="font-size: 30px; margin-right: 20px; color: #fab1a0;"><i class="fas fa-calendar-alt"></i></div>
                    <div>
                        <h3 style="font-size: 24px;">{{{{ stats.month }}}}</h3>
                        <p style="margin: 0; font-size: 12px; opacity: 0.7;">Monthly Downloads</p>
                    </div>
                </div>
                <div class="glass-card" style="padding: 25px; display: flex; align-items: center; min-height: 100px; animation-delay: 0.3s;">
                    <div style="font-size: 30px; margin-right: 20px; color: #55efc4;"><i class="fas fa-check-circle"></i></div>
                    <div style="width: 100%; overflow: hidden;">
                        <h3 style="font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{{{{ stats.last_booking }}}}">{{{{ stats.last_booking }}}}</h3>
                        <p style="margin: 0; font-size: 12px; opacity: 0.7;">Last Generated Booking</p>
                    </div>
                </div>
            </div>

            <div id="work-area" style="position: relative;">
                
                <div id="closing-section" class="work-section" style="width: 100%; max-width: 600px; margin: 0 auto;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 25px; font-weight: 600;"><i class="fas fa-file-export"></i> Closing Report</h2>
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

                <div id="purchase-order-section" class="work-section" style="display:none; width: 100%; max-width: 600px; margin: 0 auto;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 25px; font-weight: 600;"><i class="fas fa-file-invoice"></i> PDF Report Generator</h2>
                        <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="startDownloadProcess()">
                            <div class="input-group">
                                <label for="pdf_files">Select PDF Files (Booking & PO)</label>
                                <input type="file" id="pdf_files" name="pdf_files" multiple accept=".pdf" required style="height: auto;">
                            </div>
                            <button type="submit" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">Generate Report</button>
                        </form>
                         <div style="margin-top: 15px; font-size: 12px; color: #a29bfe; text-align: center;">
                            Select both Booking File & PO Files together
                        </div>
                    </div>
                </div>

                <div id="user-manage-section" class="work-section" style="display:none; width: 100%; max-width: 900px; margin: 0 auto;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 25px; font-weight: 600;"><i class="fas fa-users-cog"></i> User Management</h2>
                        
                        <div style="background: rgba(0,0,0,0.2); padding: 20px; border-radius: 15px; margin-bottom: 25px;">
                            <h4 style="font-size: 14px; margin-bottom: 15px; color: #a29bfe; text-transform: uppercase; letter-spacing: 1px;">Create / Update User</h4>
                            <form id="userForm">
                                <input type="hidden" id="action_type" name="action_type" value="create">
                                <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                                    <div class="input-group" style="flex: 1; min-width: 200px; margin-bottom: 15px;">
                                        <input type="text" id="new_username" name="username" placeholder="Username" required>
                                    </div>
                                    <div class="input-group" style="flex: 1; min-width: 200px; margin-bottom: 15px;">
                                        <input type="text" id="new_password" name="password" placeholder="Password" required>
                                    </div>
                                </div>
                                <div class="input-group" style="margin-bottom: 20px;">
                                    <label>Permissions:</label>
                                    <div class="perm-group">
                                        <div class="perm-item">
                                            <input type="checkbox" name="permissions" value="closing" id="perm_closing" checked> Closing Report
                                        </div>
                                        <div class="perm-item">
                                            <input type="checkbox" name="permissions" value="po_sheet" id="perm_po"> PO Sheet
                                        </div>
                                         <div class="perm-item">
                                            <input type="checkbox" name="permissions" value="accessories" id="perm_acc"> Accessories
                                        </div>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button type="button" onclick="handleUserSubmit(event)" id="saveUserBtn" style="flex: 2;">Create User</button>
                                    <button type="button" onclick="resetForm()" class="btn-reset" style="flex: 1; background: #636e72;">Reset</button>
                                </div>
                            </form>
                        </div>

                        <div style="overflow-x: auto;">
                            <table class="user-table">
                                <thead>
                                    <tr>
                                        <th>Username</th>
                                        <th>Role</th>
                                        <th>Permissions</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody id="userTableBody">
                                    </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="history-section" class="work-section" style="display:none; width: 100%; max-width: 800px; margin: 0 auto;">
                    <div class="glass-card">
                        <h2 style="margin-bottom: 25px; font-weight: 600;"><i class="fas fa-history"></i> Report Generation Log</h2>
                        <div style="overflow-y: auto; max-height: 500px;">
                            <table class="user-table">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Time</th>
                                        <th>User</th>
                                        <th>Booking Ref No</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {{% for log in stats.history %}}
                                    <tr>
                                        <td>{{{{ log.date }}}}</td>
                                        <td>{{{{ log.time }}}}</td>
                                        <td>{{{{ log.user }}}}</td>
                                        <td style="font-weight:bold; color:#a29bfe;">{{{{ log.ref }}}}</td>
                                    </tr>
                                    {{% endfor %}}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
        // --- Fetch Users ---
        function loadUsers() {{
            fetch('/admin/get-users')
                .then(response => response.json())
                .then(data => {{
                    const tbody = document.getElementById('userTableBody');
                    tbody.innerHTML = '';
                    for (const [user, details] of Object.entries(data)) {{
                        let perms = details.permissions ? details.permissions.join(', ') : '';
                        let row = `<tr>
                            <td>${{user}}</td>
                            <td>${{details.role}}</td>
                            <td>${{perms}}</td>
                            <td>
                                ${{details.role !== 'admin' ? 
                                    `<button class="user-btn btn-edit" onclick="editUser('${{user}}', '${{details.password}}', '${{perms}}')"><i class="fas fa-edit"></i></button>
                                     <button class="user-btn btn-delete" onclick="deleteUser('${{user}}')"><i class="fas fa-trash"></i></button>` : 
                                    '<span style="font-size:10px; opacity:0.7">System Admin</span>'}}
                            </td>
                        </tr>`;
                        tbody.innerHTML += row;
                    }}
                }});
        }}

        function handleUserSubmit(e) {{
            if(e) e.preventDefault();
            
            const username = document.getElementById('new_username').value;
            const password = document.getElementById('new_password').value;
            const action = document.getElementById('action_type').value;
            
            if(!username || !password) {{
                swal("Error", "Username and Password required!", "warning");
                return;
            }}
            
            let permissions = [];
            if(document.getElementById('perm_closing').checked) permissions.push('closing');
            if(document.getElementById('perm_po').checked) permissions.push('po_sheet');
            if(document.getElementById('perm_acc').checked) permissions.push('accessories');

            // Show Loading Animation
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.querySelector('.spinner');
            const successContainer = document.querySelector('.success-container');
            const text = document.getElementById('loading-text');

            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            successContainer.style.display = 'none';
            text.innerText = 'Saving User Data...';

            fetch('/admin/save-user', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ username, password, permissions, action_type: action }})
            }})
            .then(res => res.json())
            .then(data => {{
                if(data.status === 'success') {{
                    // Show Success Animation
                    spinner.style.display = 'none';
                    successContainer.style.display = 'block';
                    overlay.classList.add('loader-success');
                    text.innerText = 'Success!';
                    
                    setTimeout(() => {{
                        overlay.style.display = 'none';
                        overlay.classList.remove('loader-success');
                        loadUsers();
                        resetForm();
                    }}, 1000);
                }} else {{
                    overlay.style.display = 'none';
                    swal("Error", data.message, "error");
                }}
            }});
        }}

        function editUser(user, pass, permsStr) {{
            document.getElementById('new_username').value = user;
            document.getElementById('new_username').readOnly = true; 
            document.getElementById('new_password').value = pass;
            document.getElementById('action_type').value = 'update';
            document.getElementById('saveUserBtn').innerText = 'Update User';
            document.getElementById('saveUserBtn').style.background = 'linear-gradient(135deg, #f39c12 0%, #e67e22 100%)';
            
            let perms = permsStr.split(', ');
            document.getElementById('perm_closing').checked = perms.includes('closing');
            document.getElementById('perm_po').checked = perms.includes('po_sheet');
            document.getElementById('perm_acc').checked = perms.includes('accessories');
        }}

        function resetForm() {{
            document.getElementById('userForm').reset();
            document.getElementById('action_type').value = 'create';
            document.getElementById('saveUserBtn').innerText = 'Create User';
            document.getElementById('saveUserBtn').style.background = '';
            document.getElementById('new_username').readOnly = false;
            document.getElementById('perm_closing').checked = true; // Default
            document.getElementById('perm_po').checked = false;
            document.getElementById('perm_acc').checked = false;
        }}

        function deleteUser(user) {{
            swal({{
                title: "Are you sure?",
                text: "Once deleted, you will not be able to recover this user!",
                icon: "warning",
                buttons: true,
                dangerMode: true,
            }})
            .then((willDelete) => {{
                if (willDelete) {{
                    fetch('/admin/delete-user', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ username: user }})
                    }})
                    .then(res => res.json())
                    .then(data => {{
                        if(data.status === 'success') {{
                            swal("Deleted!", "User has been removed.", "success");
                            loadUsers();
                        }} else {{
                            swal("Error", data.message, "error");
                        }}
                    }});
                }}
            }});
        }}

        // --- Toggle Sections ---
        function showSection(sectionId, element) {{
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
            document.querySelectorAll('.work-section').forEach(el => el.style.display = 'none');

            if (sectionId === 'closing') {{
                document.getElementById('closing-section').style.display = 'block';
            }} else if (sectionId === 'purchase-order') {{
                document.getElementById('purchase-order-section').style.display = 'block';
            }} else if (sectionId === 'user-manage') {{
                document.getElementById('user-manage-section').style.display = 'block';
                loadUsers(); 
            }} else if (sectionId === 'history') {{
                document.getElementById('history-section').style.display = 'block';
            }}
        }}

        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); 
            const spinner = document.querySelector('.spinner');
            const successContainer = document.querySelector('.success-container');
            const text = document.getElementById('loading-text');

            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            successContainer.style.display = 'none';
            text.innerText = 'Processing Request...';
            
            setTimeout(() => {{
                spinner.style.display = 'none';
                successContainer.style.display = 'block';
                overlay.classList.add('loader-success');
                text.innerText = 'Done!';
                setTimeout(() => {{ overlay.style.display = 'none'; overlay.classList.remove('loader-success'); }}, 1500);
            }}, 3000);
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
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
            stats = get_dashboard_summary()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            # CHANGED: সাধারণ ইউজারদের সরাসরি Accessories Search পেজে নিয়ে যাওয়া হবে
            # ড্যাশবোর্ড টেমপ্লেট আর রেন্ডার হবে না
            return redirect(url_for('accessories_search_page'))

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
    flash('Session terminated.')
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
        flash("You do not have permission to access Closing Report.")
        return redirect(url_for('index'))

    internal_ref_no = request.form['ref_no']
    if not internal_ref_no: return redirect(url_for('index'))

    report_data = fetch_closing_report_data(internal_ref_no)

    if not report_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))

    # Render Preview Template instead of downloading
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)

# ==============================================================================
# UPDATED: ACCESSORIES CHALLAH ROUTES (Advanced Logic)
# ==============================================================================

# 1. Search Page (Entry Point)
@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    # Check permissions
    if 'accessories' not in session.get('permissions', []):
        flash("You do not have permission to access Accessories Dashboard.")
        return redirect(url_for('index'))
        
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

# 2. Input Form (Fetches Data from DB or API)
@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no').strip()
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()

    # লজিক: যদি ডাটাবেসে থাকে, সেখান থেকে লোড করো। না থাকলে API কল করো।
    if ref_no in db:
        data = db[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
    else:
        # API কল
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"No booking data found for {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        # ডাটা প্রসেস করে সেভ করো
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        
        db[ref_no] = {
            "style": style,
            "buyer": buyer,
            "colors": colors,
            "item_type": "", # Default empty
            "challans": [] 
        }
        save_accessories_db(db)

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer)

# 3. Save Logic & Status Update
@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    # Permission Check
    if 'accessories' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))

    ref = request.form.get('ref')
    color = request.form.get('color')
    line = request.form.get('line_no')
    size = request.form.get('size')
    qty = request.form.get('qty')
    item_type = request.form.get('item_type') # Top or Bottom
    
    db = load_accessories_db()
    
    if ref not in db:
        flash("Session Error. Please search again.")
        return redirect(url_for('accessories_search_page'))

    # Update global item type for this booking if selected
    if item_type:
        db[ref]['item_type'] = item_type

    # লজিক: নতুন চালান বানানোর আগে, পুরনো সব চালানের status টিক (✔) করে দেওয়া
    history = db[ref]['challans']
    for item in history:
        item['status'] = "✔"
    
    # নতুন এন্ট্রি (Status ফাঁকা থাকবে)
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

# 4. Print View (With Edit/Delete & Summary Logic)
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

    # --- Line-wise Summary Logic (Summing Qty) ---
    line_summary = {}
    for c in challans:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        
        if ln in line_summary:
            line_summary[ln] += q
        else:
            line_summary[ln] = q
    
    # Sort lines
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
    
    # Strict Admin Check
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

# 6. Edit Page (GET) (RESTRICTED TO ADMIN)
@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in'): return redirect(url_for('index'))

    # Strict Admin Check
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

# 7. Update Logic (POST) (RESTRICTED TO ADMIN)
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
        flash(f"Error fetching data for download: {internal_ref_no}")
        return redirect(url_for('index'))

    excel_file_stream = create_formatted_excel_report(report_data, internal_ref_no)
    
    if excel_file_stream:
        # Update stats with USERNAME here
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        return make_response(send_file(excel_file_stream, as_attachment=True, download_name=f"Closing-Report-{internal_ref_no.replace('/', '_')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
    else:
        return redirect(url_for('index'))

# --- PO SHEET GENERATOR ROUTE ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'):
        flash('Unauthorized Access')
        return redirect(url_for('index'))

    if 'po_sheet' not in session.get('permissions', []):
         flash("You do not have permission to access PO Sheet.")
         return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    uploaded_files = request.files.getlist('pdf_files')
    all_data = []
    final_meta = {
        'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A',
        'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'
    }
    
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
        pivot.columns.name = None

        pd.set_option('colheader_justify', 'center')
        table_html = pivot.to_html(classes='table table-bordered table-striped', index=False, border=0)
        
        # HTML Injections for Styling
        table_html = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', table_html)
        table_html = table_html.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
        table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        table_html = table_html.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
        table_html = table_html.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
        table_html = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', table_html)

        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(debug=True)
