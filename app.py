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
import traceback

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# কনফিগারেশন
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) # সেশন টাইমআউট ৩০ মিনিট করা হলো

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (JSON) - CRASH PROOF VERSION
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'

def load_users():
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories_challan"]
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
    default_stats = {"downloads": [], "last_booking": "None"}
    if not os.path.exists(STATS_FILE):
        return default_stats
    try:
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
            # --- Fix for 500 Error: Validate Data Structure ---
            if not isinstance(data, dict): 
                return default_stats
            if 'downloads' not in data:
                data['downloads'] = []
            return data
    except:
        return default_stats

def save_stats(data):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving stats: {e}")

def update_stats(ref_no, username):
    try:
        data = load_stats()
        now = datetime.now()
        new_record = {
            "ref": ref_no,
            "user": username,
            "date": now.strftime('%Y-%m-%d'),
            "time": now.strftime('%I:%M %p'),
            "iso_time": now.isoformat()
        }
        if 'downloads' not in data: data['downloads'] = []
        data['downloads'].insert(0, new_record)
        data['last_booking'] = ref_no
        save_stats(data)
    except Exception as e:
        print(f"Stats update failed: {e}")

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
            # Handle old format records gracefully
            if isinstance(d, dict) and 'iso_time' in d:
                dt = datetime.fromisoformat(d['iso_time'])
                if dt.strftime('%Y-%m-%d') == today_str: today_count += 1
                if dt.strftime('%Y-%m') == month_str: month_count += 1
        except: pass
            
    return {
        "today": today_count,
        "month": month_count,
        "last_booking": last_booking,
        "history": downloads 
    }

# ==============================================================================
# লজিক পার্ট: PDF PARSER (PO SHEET)
# ==============================================================================
def is_potential_size(header):
    h = header.strip().upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P.O NO"]: return False
    if re.match(r'^\d+$', h): return True
    if re.match(r'^\d+[AMYT]$', h): return True
    if re.match(r'^(XXS|XS|S|M|L|XL|XXL|XXXL|TU|ONE\s*SIZE)$', h): return True
    return False

def sort_sizes(size_list):
    STANDARD_ORDER = ['0M', '1M', '3M', '6M', '9M', '12M', '18M', '24M', '36M', '2A', '3A', '4A', '5A', '6A', '8A', '10A', '12A', '14A', '16A', '18A', 'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL', 'TU', 'One Size']
    def sort_key(s):
        s = s.strip()
        if s in STANDARD_ORDER: return (0, STANDARD_ORDER.index(s))
        if s.isdigit(): return (1, int(s))
        match = re.match(r'^(\d+)([A-Z]+)$', s)
        if match: return (2, int(match.group(1)), match.group(2))
        return (3, s)
    return sorted(size_list, key=sort_key)

def extract_metadata(text):
    meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    if "KIABI" in text.upper(): meta['buyer'] = "KIABI"
    else:
        bm = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", text)
        if bm: meta['buyer'] = bm.group(1).strip()
    bbm = re.search(r"(?:Internal )?Booking NO\.?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", text, re.IGNORECASE)
    if bbm: 
        raw = bbm.group(1).strip().replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in raw: raw = raw.split("System")[0]
        meta['booking'] = raw
    sm = re.search(r"Style Ref\.?[:\s]*([\w-]+)", text, re.IGNORECASE)
    if sm: meta['style'] = sm.group(1).strip()
    else:
        sm2 = re.search(r"Style Des\.?[\s\S]*?([\w-]+)", text, re.IGNORECASE)
        if sm2: meta['style'] = sm2.group(1).strip()
    return meta

def extract_data_dynamic(file_path):
    extracted_data = []
    metadata = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    order_no = "Unknown"
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        if "Main Fabric Booking" in first_page_text or "Fabric Booking Sheet" in first_page_text:
            return [], extract_metadata(first_page_text)

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
                            sizes = []; capturing_data = False
                    except: pass
                    continue
                
                if capturing_data:
                    if line.startswith("Total Quantity") or line.startswith("Total Amount"):
                        capturing_data = False; continue
                    
                    lower_line = line.lower()
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line: continue
                        
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
                            extracted_data.append({'P.O NO': order_no, 'Color': color_name, 'Size': size, 'Quantity': final_qtys[idx]})
    except Exception as e: print(f"PDF Error: {e}")
    return extracted_data, metadata

# ==============================================================================
# লজিক পার্ট: CLOSING REPORT & FETCHING
# ==============================================================================
def get_authenticated_session(username, password):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        response = session_req.post(login_url, data=login_payload, timeout=120)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            return session_req
        return None
    except: return None

def fetch_closing_report_data(internal_ref_no):
    try:
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
                    response = active_session.post(report_url, data=payload, timeout=120)
                    if response.status_code == 200 and "Data not Found" not in response.text:
                        found_data = response.text
                        break
                except: continue
            if found_data: break
        
        if found_data:
            return parse_report_data(found_data)
        return None
    except Exception as e:
        print(f"Fetch Error: {e}")
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
            style, color, buyer_name = "N/A", "N/A", "N/A"
            gmts_qty_data, sewing_input_data, cutting_qc_data = [], [], []
            
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0].get_text(strip=True).lower()
                    criteria_sub = cells[2].get_text(strip=True).lower()
                    
                    if criteria_main == "style": style = cells[1].get_text(strip=True)
                    elif criteria_main == "color & gmts. item": color = cells[1].get_text(strip=True)
                    elif "buyer" in criteria_main: buyer_name = cells[1].get_text(strip=True)
                    
                    if "gmts. color /country qty" in criteria_sub: 
                        gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in criteria_main: 
                        sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in criteria_sub: 
                        sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "cutting qc" in criteria_main and "balance" not in criteria_main:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "cutting qc" in criteria_sub and "balance" not in criteria_sub:
                        cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            
            if gmts_qty_data:
                all_report_data.append({
                    'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 
                    'gmts_qty': gmts_qty_data, 
                    'sewing_input': sewing_input_data if sewing_input_data else ['0']*len(headers), 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else ['0']*len(headers)
                })
        return all_report_data
    except Exception as e:
        print(f"Parse Error: {e}")
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
            try:
                actual_qty = int(str(block['gmts_qty'][i]).replace(',', '') or 0)
            except: actual_qty = 0
            
            try:
                input_qty = int(str(block['sewing_input'][i]).replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            except: input_qty = 0
            
            try:
                cutting_qc_val = int(str(block['cutting_qc'][i]).replace(',', '') or 0) if i < len(block['cutting_qc']) else 0
            except: cutting_qc_val = 0
            
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
# HTML TEMPLATES
# ==============================================================================
COMMON_STYLES = """
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
    body { background-color: #2c3e50; background-image: url('https://i.ibb.co.com/v64Lz1gj/Picsart-25-11-19-15-49-43-423.jpg'); background-size: cover; background-attachment: fixed; height: 100vh; overflow: hidden; }
    body::before { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.4); z-index: -1; }
    .glass-card { background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.2); padding: 45px 40px; border-radius: 16px; color: white; box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37); }
    .center-container { display: flex; justify-content: center; align-items: center; height: 100%; width: 100%; }
    .center-container .glass-card { width: 100%; max-width: 400px; text-align: center; }
    h1 { color: white; font-size: 26px; margin-bottom: 8px; }
    .input-group { text-align: left; margin-bottom: 20px; }
    .input-group label { display: block; font-size: 12px; color: white; margin-bottom: 8px; text-transform: uppercase; }
    input[type="password"], input[type="text"], input[type="file"], input[type="number"], select { width: 100%; padding: 12px; background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 8px; color: white; outline: none; }
    button { width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; margin-top: 10px; }
    button:hover { transform: translateY(-2px); }
    .flash { margin-top: 15px; padding: 10px; background: rgba(231, 76, 60, 0.8); border-radius: 8px; color: white; font-size: 13px; }
    a.logout { display: inline-block; margin-top: 20px; color: rgba(255,255,255,0.7); text-decoration: none; border: 1px solid rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 20px; }
    /* Loader */
    #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); backdrop-filter: blur(8px); z-index: 9999; flex-direction: column; justify-content: center; align-items: center; color: white; }
    .spinner { width: 60px; height: 60px; border: 5px solid rgba(255,255,255,0.2); border-top: 5px solid #a29bfe; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    /* Admin Styles */
    .admin-container { display: flex; width: 100%; height: 100vh; }
    .admin-sidebar { width: 280px; background: rgba(255,255,255,0.1); backdrop-filter: blur(15px); border-right: 1px solid rgba(255,255,255,0.1); display: flex; flex-direction: column; padding: 25px; }
    .nav-menu { list-style: none; }
    .nav-item { margin-bottom: 15px; }
    .nav-link { display: flex; align-items: center; padding: 12px; color: rgba(255,255,255,0.7); text-decoration: none; border-radius: 10px; cursor: pointer; transition: 0.3s; }
    .nav-link:hover, .nav-link.active { background: linear-gradient(90deg, rgba(108,92,231,0.8), rgba(118,75,162,0.8)); color: white; }
    .nav-link i { margin-right: 10px; width: 20px; text-align: center; }
    .admin-content { flex: 1; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
    .stat-card { background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; display: flex; align-items: center; backdrop-filter: blur(10px); }
    .stat-icon { width: 50px; height: 50px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; color: white; margin-right: 15px; background: rgba(255,255,255,0.1); }
    .bg-purple { background: linear-gradient(135deg, #667eea, #764ba2); }
    .bg-orange { background: linear-gradient(135deg, #ff9966, #ff5e62); }
    .bg-green { background: linear-gradient(135deg, #11998e, #38ef7d); }
    .stat-info h3 { font-size: 24px; color: white; margin-bottom: 5px; }
    .stat-info p { font-size: 13px; color: #ddd; }
    .work-area { flex: 1; background: rgba(0,0,0,0.2); border-radius: 20px; padding: 30px; display: flex; justify-content: center; align-items: flex-start; }
    /* Table */
    .user-table { width: 100%; border-collapse: collapse; color: white; margin-top: 20px; }
    .user-table th, .user-table td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); text-align: left; }
    .user-table th { background: rgba(255,255,255,0.1); }
    .user-btn { padding: 5px 10px; border-radius: 5px; border: none; font-size: 12px; cursor: pointer; color: white; margin-right: 5px; }
    .btn-edit { background: #f39c12; } .btn-delete { background: #e74c3c; } .btn-reset { background: #95a5a6; width: 100%; margin-top: 5px; }
    .swal-modal { background-color: #2d3436; border: 1px solid rgba(255,255,255,0.1); } .swal-title { color: white; } .swal-text { color: #b2bec3; }
</style>
"""

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
        .info-container { margin-bottom: 15px; background: white; padding: 15px; display: flex; justify-content: space-between; align-items: flex-end; }
        .info-row { display: flex; flex-direction: column; gap: 5px; }
        .info-item { font-size: 1.2rem; font-weight: 600; color: #444; }
        .info-value { color: #000; font-weight: 800; }
        .booking-box { background: #2c3e50; color: white; padding: 10px 20px; border-radius: 5px; text-align: right; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); min-width: 200px; }
        .booking-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
        .booking-value { font-size: 1.8rem; font-weight: 800; line-height: 1.1; }
        .table-card { background: white; border-radius: 0; margin-bottom: 30px; border: none; }
        .color-header { background-color: #2c3e50 !important; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; text-transform: uppercase; border: 1px solid #000; }
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
        .footer-credit { text-align: center; margin-top: 40px; margin-bottom: 20px; font-size: 1rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #000; font-weight: 600; }
        @media print {
            @page { margin: 5mm; size: portrait; }
            body { background-color: white; padding: 0; }
            .no-print { display: none !important; }
            .action-bar { display: none; }
            .table th, .table td { border: 1px solid #000 !important; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important; }
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            .booking-box { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important; border: 1px solid #000; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn btn-outline-secondary rounded-pill px-4">Back to Dashboard</a>
            <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-excel">Download Excel</a>
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
                        <th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th><th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>PERCENTAGE %</th>
                    </tr>
                </thead>
                <tbody>
                    {% set ns = namespace(tot_3=0, tot_act=0, tot_cut=0, tot_inp=0, tot_bal=0, tot_sp=0) %}
                    {% for i in range(block.headers|length) %}
                        {% set actual = (block.gmts_qty[i]|replace(',', '') or 0)|int %}
                        {% set qty_3 = (actual * 1.03)|round|int %}
                        {% set cut_qc = 0 %}
                        {% if i < block.cutting_qc|length %}{% set cut_qc = (block.cutting_qc[i]|replace(',', '') or 0)|int %}{% endif %}
                        {% set inp_qty = 0 %}
                        {% if i < block.sewing_input|length %}{% set inp_qty = (block.sewing_input[i]|replace(',', '') or 0)|int %}{% endif %}
                        {% set balance = cut_qc - inp_qty %}
                        {% set short_plus = inp_qty - qty_3 %}
                        {% set percentage = 0 %}
                        {% if qty_3 > 0 %}{% set percentage = (short_plus / qty_3) * 100 %}{% endif %}
                        {% set ns.tot_3 = ns.tot_3 + qty_3 %}{% set ns.tot_act = ns.tot_act + actual %}{% set ns.tot_cut = ns.tot_cut + cut_qc %}{% set ns.tot_inp = ns.tot_inp + inp_qty %}{% set ns.tot_bal = ns.tot_bal + balance %}{% set ns.tot_sp = ns.tot_sp + short_plus %}
                        <tr>
                            <td>{{ block.headers[i] }}</td><td class="col-3pct">{{ qty_3 }}</td><td>{{ actual }}</td><td>{{ cut_qc }}</td><td class="col-input">{{ inp_qty }}</td><td class="col-balance">{{ balance }}</td><td style="color: {{ 'green' if short_plus >= 0 else 'red' }}">{{ short_plus }}</td><td>{{ "%.2f"|format(percentage) }}%</td>
                        </tr>
                    {% endfor %}
                    <tr class="total-row">
                        <td>TOTAL</td><td>{{ ns.tot_3 }}</td><td>{{ ns.tot_act }}</td><td>{{ ns.tot_cut }}</td><td>{{ ns.tot_inp }}</td><td>{{ ns.tot_bal }}</td><td>{{ ns.tot_sp }}</td><td>{% if ns.tot_3 > 0 %}{{ "%.2f"|format((ns.tot_sp / ns.tot_3) * 100) }}%{% else %}0.00%{% endif %}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endfor %}
        <div class="footer-credit">Report Generated By <span style="color: #000; font-weight: 900;">Mehedi Hasan</span></div>
        {% endif %}
    </div>
    <script>document.getElementById('date').innerText = new Date().toLocaleDateString('en-GB');</script>
</body>
</html>
"""

ACCESSORIES_CHALLAN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accessories Challan</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 40px; background: #f9f9f9; font-family: 'Segoe UI', sans-serif; }
        .challan-container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; border: 1px solid #ddd; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
        .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }
        .company-name { font-size: 28px; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        .address { font-size: 14px; color: #666; margin-bottom: 10px; }
        .challan-title { background: #2c3e50; color: white; display: inline-block; padding: 8px 30px; font-weight: 700; border-radius: 20px; text-transform: uppercase; font-size: 16px; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .info-box { border: 1px solid #eee; padding: 15px; background: #fdfdfd; }
        .info-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
        .info-val { font-size: 16px; font-weight: 700; color: #333; margin-top: 5px; }
        .item-table { width: 100%; border-collapse: collapse; margin-bottom: 40px; }
        .item-table th { background: #2c3e50; color: white; padding: 12px; text-align: left; font-weight: 600; }
        .item-table td { border-bottom: 1px solid #eee; padding: 12px; font-weight: 500; }
        .item-table tr:last-child td { border-bottom: 2px solid #333; }
        .signatures { display: flex; justify-content: space-between; margin-top: 80px; padding-top: 20px; }
        .sig-block { text-align: center; border-top: 1px solid #333; width: 200px; padding-top: 10px; font-weight: 600; font-size: 14px; }
        .no-print { text-align: right; margin-bottom: 20px; }
        .btn-print { background: #2c3e50; color: white; padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer; font-weight: 600; }
        @media print { body { background: white; padding: 0; } .challan-container { border: none; box-shadow: none; padding: 0; } .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="no-print">
            <a href="/" class="btn btn-outline-secondary me-2">Back to Dashboard</a>
            <button onclick="window.print()" class="btn-print">Print Challan</button>
        </div>
        <div class="challan-container">
            <div class="header">
                <div class="company-name">Cotton Clothing BD Limited</div>
                <div class="address">Plot # 24, Road # 04, Sector # 03, Uttara, Dhaka-1230</div>
                <div class="challan-title">Accessories Delivery Challan</div>
            </div>
            <div class="info-grid">
                <div class="info-box"><div class="info-label">Date</div><div class="info-val">{{ date }}</div></div>
                <div class="info-box"><div class="info-label">Booking Ref No</div><div class="info-val">{{ ref_no }}</div></div>
                <div class="info-box"><div class="info-label">Buyer</div><div class="info-val">{{ buyer }}</div></div>
                <div class="info-box"><div class="info-label">Style No</div><div class="info-val">{{ style }}</div></div>
                <div class="info-box"><div class="info-label">Sewing Line</div><div class="info-val">Line # {{ line_no }}</div></div>
            </div>
            <table class="item-table">
                <thead><tr><th style="width: 10%;">SL</th><th style="width: 40%;">Item Description</th><th style="width: 25%;">Color</th><th style="width: 15%; text-align: center;">UOM</th><th style="width: 10%; text-align: center;">Quantity</th></tr></thead>
                <tbody><tr><td>01</td><td>Main Label / Size Label</td><td>{{ color }}</td><td style="text-align: center;">Pcs</td><td style="text-align: center;">{{ qty }}</td></tr></tbody>
            </table>
            <div class="signatures"><div class="sig-block">Store Incharge</div><div class="sig-block">Receiver Signature</div><div class="sig-block">Authorized By</div></div>
            <div style="text-align: center; margin-top: 40px; font-size: 12px; color: #aaa;">System Generated Report | Created By Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

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
    <div id="loading-overlay"><div class="spinner"></div><div id="loading-text">Processing...</div></div>
    <div class="admin-container">
        <div class="admin-sidebar">
            <div class="sidebar-header"><h2>Admin Panel</h2><p>SUPER ADMIN ACCESS</p></div>
            <ul class="nav-menu">
                <li class="nav-item"><a class="nav-link active" onclick="showSection('closing', this)"><i class="fas fa-file-export"></i> Closing Report</a></li>
                <li class="nav-item"><a class="nav-link" onclick="showSection('purchase-order', this)"><i class="fas fa-file-invoice"></i> PURCHASE ORDER SHEET</a></li>
                <li class="nav-item"><a class="nav-link" onclick="showSection('accessories', this)"><i class="fas fa-tags"></i> Accessories Challan</a></li>
                <li class="nav-item"><a class="nav-link" onclick="showSection('user-manage', this)"><i class="fas fa-users-cog"></i> User Management</a></li>
                <li class="nav-item"><a class="nav-link" onclick="showSection('history', this)"><i class="fas fa-history"></i> Closing History</a></li>
            </ul>
            <div class="admin-footer"><a href="/logout" class="nav-link" style="color: #ff7675;"><i class="fas fa-sign-out-alt"></i> Logout</a></div>
        </div>
        <div class="admin-content">
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-icon bg-purple"><i class="fas fa-calendar-day"></i></div><div class="stat-info"><h3>{{{{ stats.today }}}}</h3><p>Today's Downloads</p></div></div>
                <div class="stat-card"><div class="stat-icon bg-orange"><i class="fas fa-calendar-alt"></i></div><div class="stat-info"><h3>{{{{ stats.month }}}}</h3><p>Monthly Downloads</p></div></div>
                <div class="stat-card"><div class="stat-icon bg-green"><i class="fas fa-history"></i></div><div class="stat-info"><h3 style="font-size: 16px;">{{{{ stats.last_booking }}}}</h3><p>Last Booking</p></div></div>
            </div>
            <div class="work-area">
                <div id="closing-section" class="work-section" style="width: 100%; max-width: 500px;">
                    <div class="glass-card"><h2><i class="fas fa-file-export"></i> Generate Closing Report</h2>
                        <form action="/generate-report" method="post" onsubmit="startDownloadProcess()"><div class="input-group"><label>Internal Reference No</label><input type="text" name="ref_no" placeholder="Enter Ref No" required><input type="hidden" name="download_token" id="download_token"></div><button type="submit">Generate Report</button></form>
                    </div>
                </div>
                <div id="purchase-order-section" class="work-section" style="display:none; width: 100%; max-width: 500px;">
                    <div class="glass-card"><h2><i class="fas fa-file-invoice"></i> PDF Report Generator</h2>
                        <form action="/generate-po-report" method="post" enctype="multipart/form-data"><div class="input-group"><label>Select PDF Files</label><input type="file" name="pdf_files" multiple accept=".pdf" required></div><button type="submit">Generate Report</button></form>
                    </div>
                </div>
                <div id="accessories-section" class="work-section" style="display:none; width: 100%; max-width: 600px;">
                    <div class="glass-card"><h2><i class="fas fa-tags"></i> Accessories Challan</h2>
                        <div id="step1-booking"><div class="input-group"><label>Booking Reference No</label><input type="text" id="challan_ref" placeholder="Enter Booking No"></div><button onclick="fetchBookingColors()" style="background: #e67e22;">Fetch Colors</button></div>
                        <div id="step2-details" style="display:none; margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                            <form action="/generate-accessories-challan" method="post" target="_blank"><input type="hidden" name="ref_no" id="hidden_ref_no"><input type="hidden" name="buyer" id="hidden_buyer"><input type="hidden" name="style" id="hidden_style">
                                <div class="input-group"><label>Select Color</label><div id="color-options" style="display: flex; flex-wrap: wrap; gap: 10px;"></div></div>
                                <div class="input-group"><label>Sewing Line No</label><input type="text" name="line_no" placeholder="e.g. 15" required></div>
                                <div class="input-group"><label>Label Quantity (Pcs)</label><input type="number" name="qty" placeholder="e.g. 500" required></div>
                                <button type="submit" style="background: #27ae60;">Generate Challan</button>
                            </form>
                        </div>
                    </div>
                </div>
                <div id="user-manage-section" class="work-section" style="display:none; width: 100%; max-width: 700px;">
                    <div class="glass-card"><h2><i class="fas fa-users-cog"></i> User Management</h2>
                        <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                            <form id="userForm"><input type="hidden" id="action_type" name="action_type" value="create">
                                <div style="display: flex; gap: 10px;"><div class="input-group" style="flex: 1;"><input type="text" id="new_username" name="username" placeholder="Username" required></div><div class="input-group" style="flex: 1;"><input type="text" id="new_password" name="password" placeholder="Password" required></div></div>
                                <div class="input-group"><label>Permissions:</label><div class="perm-group"><div class="perm-item"><input type="checkbox" name="permissions" value="closing" id="perm_closing" checked> Closing</div><div class="perm-item"><input type="checkbox" name="permissions" value="po_sheet" id="perm_po"> PO Sheet</div></div></div>
                                <button type="button" onclick="handleUserSubmit(event)" id="saveUserBtn">Create User</button><button type="button" onclick="resetForm()" class="user-btn btn-reset">Reset Form</button>
                            </form>
                        </div>
                        <div style="overflow-x: auto;"><table class="user-table"><thead><tr><th>Username</th><th>Role</th><th>Action</th></tr></thead><tbody id="userTableBody"></tbody></table></div>
                    </div>
                </div>
                <div id="history-section" class="work-section" style="display:none; width: 100%; max-width: 800px;">
                    <div class="glass-card"><h2><i class="fas fa-history"></i> History Log</h2>
                        <div style="overflow-y: auto; max-height: 500px;"><table class="user-table"><thead><tr><th>Date</th><th>Time</th><th>User</th><th>Booking</th></tr></thead><tbody>{{% for log in stats.history %}}<tr><td>{{{{ log.date }}}}</td><td>{{{{ log.time }}}}</td><td>{{{{ log.user }}}}</td><td style="color:#a29bfe;">{{{{ log.ref }}}}</td></tr>{{% endfor %}}</tbody></table></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        function showSection(id, el) {{ document.querySelectorAll('.nav-link').forEach(e => e.classList.remove('active')); el.classList.add('active'); document.querySelectorAll('.work-section').forEach(e => e.style.display = 'none'); document.getElementById(id+'-section').style.display = 'block'; if(id==='user-manage') loadUsers(); }}
        function startDownloadProcess() {{ const o=document.getElementById('loading-overlay'); o.style.display='flex'; setTimeout(()=>o.style.display='none', 3000); }}
        
        function fetchBookingColors() {{
            const ref = document.getElementById('challan_ref').value;
            if(!ref) return swal("Error","Enter Booking No","error");
            document.getElementById('loading-overlay').style.display='flex';
            fetch('/admin/get-booking-colors', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{ref_no:ref}})}})
            .then(r=>r.json()).then(d=>{{
                document.getElementById('loading-overlay').style.display='none';
                if(d.status==='success'){{
                    document.getElementById('step2-details').style.display='block';
                    document.getElementById('hidden_ref_no').value = ref;
                    document.getElementById('hidden_buyer').value = d.meta.buyer;
                    document.getElementById('hidden_style').value = d.meta.style;
                    const cDiv = document.getElementById('color-options'); cDiv.innerHTML='';
                    d.colors.forEach(c=>{{ cDiv.innerHTML += `<label style="background:rgba(255,255,255,0.1); padding:5px 10px; border-radius:5px; cursor:pointer; display:flex; align-items:center; gap:5px; border:1px solid rgba(255,255,255,0.2);"><input type="radio" name="color" value="${{c}}" required> ${{c}}</label>`; }});
                }} else swal("Error", d.message, "error");
            }}).catch(()=>{{ document.getElementById('loading-overlay').style.display='none'; swal("Error", "Failed to fetch", "error"); }});
        }}

        function loadUsers() {{
            fetch('/admin/get-users').then(r=>r.json()).then(d=>{{
                const t=document.getElementById('userTableBody'); t.innerHTML='';
                for(const [u,v] of Object.entries(d)){{
                    t.innerHTML += `<tr><td>${{u}}</td><td>${{v.role}}</td><td>${{v.role!=='admin'?`<button class="user-btn btn-edit" onclick="editUser('${{u}}','${{v.password}}','${{v.permissions.join(',')}}')">Edit</button><button class="user-btn btn-delete" onclick="deleteUser('${{u}}')">Del</button>`:''}}</td></tr>`;
                }}
            }});
        }}
        
        function handleUserSubmit(e) {{
            e.preventDefault(); const u=document.getElementById('new_username').value, p=document.getElementById('new_password').value;
            let perms=[]; if(document.getElementById('perm_closing').checked) perms.push('closing'); if(document.getElementById('perm_po').checked) perms.push('po_sheet');
            fetch('/admin/save-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u, password:p, permissions:perms, action_type:document.getElementById('action_type').value}})}})
            .then(r=>r.json()).then(d=>{{ swal(d.status, d.message, d.status); loadUsers(); resetForm(); }});
        }}
        function editUser(u,p,permStr) {{ document.getElementById('new_username').value=u; document.getElementById('new_username').readOnly=true; document.getElementById('new_password').value=p; document.getElementById('action_type').value='update'; const perms=permStr.split(','); document.getElementById('perm_closing').checked=perms.includes('closing'); document.getElementById('perm_po').checked=perms.includes('po_sheet'); document.getElementById('saveUserBtn').innerText='Update'; }}
        function deleteUser(u) {{ swal({{title:"Delete?", icon:"warning", buttons:true, dangerMode:true}}).then(ok=>{{ if(ok) fetch('/admin/delete-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}})}}).then(r=>r.json()).then(d=>{{ swal(d.status, d.message, d.status); loadUsers(); }}); }}); }}
        function resetForm() {{ document.getElementById('userForm').reset(); document.getElementById('action_type').value='create'; document.getElementById('new_username').readOnly=false; document.getElementById('saveUserBtn').innerText='Create User'; }}
    </script>
</body>
</html>
"""

# --- FLASK ROUTES ---
@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(LOGIN_TEMPLATE)
    stats = get_dashboard_summary()
    if session.get('role') == 'admin': return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
    return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    u, p = request.form.get('username'), request.form.get('password')
    users = load_users()
    if u in users and users[u]['password'] == p:
        session['logged_in'] = True; session['user'] = u; session['role'] = users[u]['role']; session['permissions'] = users[u].get('permissions', [])
        return redirect(url_for('index'))
    flash('Invalid Credentials'); return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); flash('Logged out'); return redirect(url_for('index'))

# --- CLOSING REPORT ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form.get('ref_no')
    data = fetch_closing_report_data(ref)
    if not data: flash(f"No data found for {ref}"); return redirect(url_for('index'))
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=data, ref_no=ref)

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref_no')
    data = fetch_closing_report_data(ref)
    if not data: return "Data error"
    f = create_formatted_excel_report(data, ref)
    if f: 
        update_stats(ref, session.get('user','Unknown'))
        return make_response(send_file(f, as_attachment=True, download_name=f"Closing_{ref.replace('/','_')}.xlsx"))
    return "File error"

# --- ACCESSORIES CHALLAN ---
@app.route('/admin/get-booking-colors', methods=['POST'])
def get_booking_colors():
    if not session.get('logged_in'): return jsonify({'status':'error','message':'Login required'})
    try:
        ref = request.json.get('ref_no')
        data = fetch_closing_report_data(ref)
        if not data: return jsonify({'status':'error', 'message':'Booking not found in ERP'})
        colors = sorted(list(set([b['color'] for b in data if b.get('color')])))
        meta = {'buyer': data[0].get('buyer','N/A'), 'style': data[0].get('style','N/A')}
        return jsonify({'status':'success', 'colors': colors, 'meta': meta})
    except Exception as e: return jsonify({'status':'error', 'message': str(e)})

@app.route('/generate-accessories-challan', methods=['POST'])
def generate_accessories_challan():
    if not session.get('logged_in'): return "Unauthorized"
    return render_template_string(ACCESSORIES_CHALLAN_TEMPLATE, 
                                  ref_no=request.form.get('ref_no'), 
                                  buyer=request.form.get('buyer'), 
                                  style=request.form.get('style'),
                                  color=request.form.get('color'), 
                                  line_no=request.form.get('line_no'), 
                                  qty=request.form.get('qty'), 
                                  date=datetime.now().strftime('%d-%b-%Y'))

# --- USER & PO ROUTES ---
@app.route('/admin/get-users')
def get_users_route(): return jsonify(load_users()) if session.get('role')=='admin' else "Unauthorized"

@app.route('/admin/save-user', methods=['POST'])
def save_user_route():
    if session.get('role')!='admin': return jsonify({'status':'error'})
    d=request.json; users=load_users(); u=d['username']
    if d['action_type']=='create' and u in users: return jsonify({'status':'error','message':'Exists'})
    users[u]={'password':d['password'], 'role':'user', 'permissions':d['permissions']}
    save_users(users); return jsonify({'status':'success','message':'Saved'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user_route():
    if session.get('role')!='admin': return jsonify({'status':'error'})
    u=request.json['username']; users=load_users()
    if u=='Admin': return jsonify({'status':'error','message':'Cannot delete Admin'})
    if u in users: del users[u]; save_users(users); return jsonify({'status':'success','message':'Deleted'})
    return jsonify({'status':'error'})

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    shutil.rmtree(UPLOAD_FOLDER, ignore_errors=True); os.makedirs(UPLOAD_FOLDER)
    files = request.files.getlist('pdf_files'); all_data = []; meta = {}
    for f in files:
        p = os.path.join(UPLOAD_FOLDER, f.filename); f.save(p)
        d, m = extract_data_dynamic(p)
        if d: all_data.extend(d)
        if m['buyer']!='N/A': meta=m
    if not all_data: return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No Data Found")
    
    df = pd.DataFrame(all_data)
    tables = []
    grand_total = 0
    for color in df['Color'].unique():
        cdf = df[df['Color']==color]
        piv = cdf.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        piv = piv[sort_sizes(piv.columns.tolist())]
        piv['Total'] = piv.sum(axis=1)
        grand_total += piv['Total'].sum()
        
        # Totals Row
        act = piv.sum(); act.name='Actual Qty'
        plus3 = (act * 1.03).round().astype(int); plus3.name='3% Order Qty'
        piv = pd.concat([piv, act.to_frame().T, plus3.to_frame().T]).reset_index().rename(columns={'index':'P.O NO'})
        
        html = piv.to_html(classes='table table-bordered table-striped', index=False, border=0)
        # Inject Classes
        html = html.replace('<th>Total</th>','<th class="total-col-header">Total</th>').replace('<td>Total</td>','<td class="total-col">Total</td>')
        html = html.replace('<td>Actual Qty</td>','<td class="summary-label">Actual Qty</td>').replace('<td>3% Order Qty</td>','<td class="summary-label">3% Order Qty</td>')
        tables.append({'color': color, 'table': html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=tables, meta=meta, grand_total=f"{grand_total:,}")

if __name__ == '__main__':
    app.run(debug=True)
