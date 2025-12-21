import requests
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz 
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
from collections import defaultdict

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# ==============================================================================
# কনফিগারেশন এবং সেটআপ
# ==============================================================================

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60) 

bd_tz = pytz.timezone('Asia/Dhaka')

def get_bd_time():
    return datetime.now(bd_tz)

def get_bd_date_str():
    return get_bd_time().strftime('%d-%m-%Y')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ==============================================================================
# MongoDB কানেকশন
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
# CSS STYLES (UPDATED: Flash Top-Center, No Popup, English Tooltips Bottom)
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
    <style>
        :root {
            --bg-body: #0a0a0f;
            --bg-sidebar: #12121a;
            --bg-card: #16161f;
            --text-primary: #FFFFFF;
            --text-secondary: #8b8b9e;
            --accent-orange: #FF7A00;
            --accent-purple: #8B5CF6;
            --accent-green: #10B981;
            --accent-red: #EF4444;
            --border-color: rgba(255, 255, 255, 0.08);
            --gradient-orange: linear-gradient(135deg, #FF7A00 0%, #FF9A40 100%);
            --gradient-dark: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
            --gradient-card: linear-gradient(145deg, rgba(22, 22, 31, 0.9) 0%, rgba(16, 16, 22, 0.95) 100%);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background: var(--bg-body); color: var(--text-primary); min-height: 100vh; display: flex; overflow-x: hidden; }
        
        /* UPDATED: Flash Messages - Top Center, Visible */
        #flash-container {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10001;
            display: flex;
            flex-direction: column;
            gap: 15px;
            align-items: center;
            width: auto;
            min-width: 400px;
        }

        .flash-message {
            padding: 18px 30px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            animation: slideDown 0.4s ease-out;
            color: white;
        }

        @keyframes slideDown {
            from { transform: translateY(-100%); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .flash-error { background: rgba(220, 38, 38, 0.95); border-left: 5px solid #ff6b6b; }
        .flash-success { background: rgba(22, 163, 74, 0.95); border-left: 5px solid #4ade80; }
        .flash-info { background: rgba(37, 99, 235, 0.95); border-left: 5px solid #60a5fa; }

        /* Sidebar */
        .sidebar {
            width: 280px; height: 100vh; background: var(--gradient-dark); position: fixed; top: 0; left: 0;
            display: flex; flex-direction: column; padding: 30px 20px; border-right: 1px solid var(--border-color);
            z-index: 1000; transition: 0.4s;
        }
        .brand-logo { font-size: 26px; font-weight: 900; color: white; margin-bottom: 50px; display: flex; align-items: center; gap: 12px; }
        .brand-logo span { background: var(--gradient-orange); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .nav-menu { flex-grow: 1; display: flex; flex-direction: column; gap: 8px; }
        .nav-link {
            display: flex; align-items: center; padding: 14px 18px; color: var(--text-secondary); text-decoration: none;
            border-radius: 12px; transition: 0.4s; cursor: pointer; font-weight: 500;
        }
        .nav-link:hover, .nav-link.active { color: var(--accent-orange); background: rgba(255, 122, 0, 0.1); }
        .nav-link i { width: 24px; margin-right: 12px; font-size: 18px; }

        /* Main Content */
        .main-content { margin-left: 280px; width: calc(100% - 280px); padding: 30px 40px; min-height: 100vh; }
        
        /* UPDATED: Tooltips - English & Bottom Position */
        .tooltip { position: relative; }
        .tooltip::after {
            content: attr(data-tooltip);
            position: absolute;
            top: 130%; /* Shows below the element */
            left: 50%;
            transform: translateX(-50%);
            background: #222;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: 0.2s;
            border: 1px solid var(--border-color);
            z-index: 1000;
            pointer-events: none;
            box-shadow: 0 5px 15px rgba(0,0,0,0.4);
        }
        .tooltip:hover::after { opacity: 1; visibility: visible; top: 120%; }

        /* Cards & Inputs */
        .card { background: var(--gradient-card); border: 1px solid var(--border-color); border-radius: 16px; padding: 28px; margin-bottom: 24px; }
        input, select { width: 100%; padding: 14px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); color: white; border-radius: 12px; outline: none; }
        button { width: 100%; padding: 14px; background: var(--gradient-orange); color: white; border: none; border-radius: 12px; font-weight: 700; cursor: pointer; transition: 0.3s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px var(--accent-orange-glow); }
        
        /* Animations */
        .animated-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; background: radial-gradient(circle at 50% 50%, rgba(255,122,0,0.05), transparent 70%); }
        
        /* Tables */
        .dark-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .dark-table th { text-align: left; padding: 12px; color: var(--text-secondary); border-bottom: 1px solid var(--border-color); }
        .dark-table td { padding: 12px; color: white; border-bottom: 1px solid rgba(255,255,255,0.05); }

        /* Loading Overlay */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 9999; justify-content: center; align-items: center; flex-direction: column; backdrop-filter: blur(5px); }
        .spinner { width: 60px; height: 60px; border: 5px solid rgba(255,255,255,0.1); border-top-color: var(--accent-orange); border-radius: 50%; animation: spin 1s linear infinite; }
        .loading-text { margin-top: 20px; color: white; font-weight: 500; letter-spacing: 1px; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        @media (max-width: 1024px) {
            .sidebar { transform: translateX(-100%); }
            .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; }
            .mobile-toggle { display: block; position: fixed; top: 20px; right: 20px; z-index: 2000; color: white; background: #222; padding: 10px; border-radius: 8px; }
        }
        .mobile-toggle { display: none; }
    </style>
"""

# ==============================================================================
# হেল্পার ফাংশন
# ==============================================================================

def load_users():
    record = users_col.find_one({"_id": "global_users"})
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"],
            "created_at": "N/A",
            "last_login": "Never"
        }
    }
    if record: return record['data']
    else:
        users_col.insert_one({"_id": "global_users", "data": default_users})
        return default_users

def save_users(users_data):
    users_col.replace_one({"_id": "global_users"}, {"_id": "global_users", "data": users_data}, upsert=True)

def load_stats():
    record = stats_col.find_one({"_id": "dashboard_stats"})
    return record['data'] if record else {"downloads": [], "last_booking": "None"}

def save_stats(data):
    stats_col.replace_one({"_id": "dashboard_stats"}, {"_id": "dashboard_stats", "data": data}, upsert=True)

def update_stats(ref_no, username):
    data = load_stats()
    now = get_bd_time()
    data['downloads'].insert(0, {"ref": ref_no, "user": username, "date": now.strftime('%d-%m-%Y'), "time": now.strftime('%I:%M %p'), "type": "Closing Report"})
    if len(data['downloads']) > 3000: data['downloads'] = data['downloads'][:3000]
    save_stats(data)

def update_po_stats(username, file_count, booking_ref="N/A"):
    data = load_stats()
    now = get_bd_time()
    data['downloads'].insert(0, {"ref": booking_ref, "user": username, "file_count": file_count, "date": now.strftime('%d-%m-%Y'), "time": now.strftime('%I:%M %p'), "type": "PO Sheet"})
    if len(data['downloads']) > 3000: data['downloads'] = data['downloads'][:3000]
    save_stats(data)

def load_accessories_db():
    record = accessories_col.find_one({"_id": "accessories_data"})
    return record['data'] if record else {}

def save_accessories_db(data):
    accessories_col.replace_one({"_id": "accessories_data"}, {"_id": "accessories_data", "data": data}, upsert=True)

def get_all_accessories_bookings():
    db_acc = load_accessories_db()
    bookings = []
    for ref, data in db_acc.items():
        qty = sum([int(c.get('qty', 0)) for c in data.get('challans', [])])
        bookings.append({'ref': ref, 'buyer': data.get('buyer', 'N/A'), 'style': data.get('style', 'N/A'), 'challan_count': len(data.get('challans', [])), 'total_qty': qty})
    return sorted(bookings, key=lambda x: x['ref'], reverse=True)

def get_dashboard_summary_v2():
    stats = load_stats()
    acc_db = load_accessories_db()
    users = load_users()
    
    acc_count = sum(len(d.get('challans', [])) for d in acc_db.values())
    closing_count = sum(1 for x in stats['downloads'] if x['type'] == 'Closing Report')
    po_count = sum(1 for x in stats['downloads'] if x['type'] == 'PO Sheet')
    
    # Simple charts data
    chart_labels = ["Closing", "PO", "Accessories"]
    chart_data = [closing_count, po_count, acc_count]
    
    return {
        "users": {"count": len(users)},
        "accessories": {"count": acc_count},
        "closing": {"count": closing_count},
        "po": {"count": po_count},
        "history": stats['downloads'],
        "chart": {"labels": chart_labels, "data": chart_data}
    }

# ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (FIXED LOGIC - Layout Mode & Gap Handling)
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

def extract_metadata(first_page_text):
    meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    if "KIABI" in first_page_text.upper(): meta['buyer'] = "KIABI"
    else:
        buyer = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", first_page_text)
        if buyer: meta['buyer'] = buyer.group(1).strip()
    
    booking = re.search(r"(?:Internal )?Booking NO\. ?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking: meta['booking'] = booking.group(1).strip().replace('\n', '').split("System")[0]
    
    style = re.search(r"Style Ref\. ?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style: meta['style'] = style.group(1).strip()
    
    return meta

def extract_data_dynamic(file_path):
    extracted_data = []
    metadata = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    order_no = "Unknown"
    
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        
        if "Main Fabric Booking" in first_page_text or "Fabric Booking Sheet" in first_page_text:
            metadata = extract_metadata(first_page_text)
            return [], metadata

        order_match = re.search(r"Order no\D*(\d+)", first_page_text, re.IGNORECASE)
        if order_match: order_no = order_match.group(1)
        order_no = str(order_no).strip()
        if order_no.endswith("00"): order_no = order_no[:-2]

        for page in reader.pages:
            try:
                # Use layout mode to detect gaps/spacing correctly
                text = page.extract_text(extraction_mode="layout")
            except:
                text = page.extract_text()
                
            lines = text.split('\n')
            sizes = []
            capturing_data = False
            
            for line in lines:
                line_strip = line.strip()
                if not line_strip: continue

                if ("Colo" in line_strip or "Size" in line_strip) and "Total" in line_strip:
                    parts = line_strip.split()
                    try:
                        total_idx = [idx for idx, x in enumerate(parts) if 'Total' in x][0]
                        raw_sizes = parts[:total_idx]
                        temp_sizes = [s for s in raw_sizes if s not in ["Colo", "/", "Size"]]
                        valid = sum(1 for s in temp_sizes if is_potential_size(s))
                        if temp_sizes and valid >= len(temp_sizes) / 2:
                            sizes = temp_sizes
                            capturing_data = True
                        else:
                            sizes = []
                            capturing_data = False
                    except: pass
                    continue
                
                if capturing_data:
                    if line_strip.startswith("Total"):
                        capturing_data = False
                        continue
                    
                    if not re.search(r'[a-zA-Z]', line_strip.replace("Spec", "")): continue
                    if re.match(r'^[A-Z]\d+$', line_strip): continue

                    # Split by multiple spaces (layout preservation)
                    columns = re.split(r'\s{2,}', line.strip())
                    color_name = ""
                    quantities = []
                    
                    for col in columns:
                        col = col.strip()
                        if re.match(r'^\d+$', col):
                            quantities.append(int(col))
                        elif re.search(r'[a-zA-Z]', col) and not color_name:
                            color_name = col
                    
                    # Gap Fixing Logic:
                    # If quantities found (excl Total) < sizes, we have shifted data.
                    # We check if sum matches the last number (Total).
                    if len(quantities) > 1:
                        calc_sum = sum(quantities[:-1])
                        file_total = quantities[-1]
                        
                        if calc_sum == file_total:
                            data_qtys = quantities[:-1]
                            
                            # If length matches perfectly
                            if len(data_qtys) == len(sizes):
                                pass
                            # If gaps exist (less data than sizes), pad with 0s
                            # This fixes the issue where XL data shifts to L
                            elif len(data_qtys) < len(sizes):
                                # Assuming gaps are usually 0s at the end or begin, 
                                # but usually simple padding helps basic shifting.
                                data_qtys += [0] * (len(sizes) - len(data_qtys))
                            elif len(data_qtys) > len(sizes):
                                data_qtys = data_qtys[:len(sizes)]
                                
                            if color_name:
                                for idx, size in enumerate(sizes):
                                    extracted_data.append({'P.O NO': order_no, 'Color': color_name, 'Size': size, 'Quantity': data_qtys[idx]})

    except Exception as e: print(f"Error: {e}")
    return extracted_data, metadata

# ==============================================================================
# লজিক পার্ট: CLOSING REPORT API
# ==============================================================================

def fetch_closing_report_data(internal_ref_no):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': "input2.clothing-cutting", 'txt_password': "123456", 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    try:
        response = session_req.post(login_url, data=login_payload, timeout=30)
        if "dashboard.php" not in response.url and "Invalid" in response.text: return None
    except: return None

    report_url = 'http://180.92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload_template = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'txt_internal_ref_no': internal_ref_no, 'reportType': '3'}
    found_data = None
   
    for year in ['2025', '2024']: 
        for company_id in range(1, 6):
            payload = payload_template.copy()
            payload['cbo_year_selection'] = year
            payload['cbo_company_name'] = str(company_id)
            try:
                response = session_req.post(report_url, data=payload, timeout=30)
                if response.status_code == 200 and "Data not Found" not in response.text:
                    found_data = response.text
                    break
            except: continue
        if found_data: break
    
    if found_data: return parse_report_data(found_data)
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
                    criteria_main = cells[0].get_text(strip=True).lower()
                    criteria_sub = cells[2].get_text(strip=True).lower()
                    
                    if criteria_main == "style": style = cells[1].get_text(strip=True)
                    elif criteria_main == "color & gmts. item": color = cells[1].get_text(strip=True)
                    elif "buyer" in criteria_main: buyer_name = cells[1].get_text(strip=True)
                    
                    if criteria_sub == "gmts. color /country qty": gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in criteria_main: sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in criteria_sub: sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "cutting qc" in criteria_main and "balance" not in criteria_main: cutting_qc_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "cutting qc" in criteria_sub and "balance" not in criteria_sub: cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            
            if gmts_qty_data:  
                plus_3_percent_data = []
                for value in gmts_qty_data:  
                    try: plus_3_percent_data.append(str(round(int(value.replace(',', '')) * 1.03)))
                    except: plus_3_percent_data.append(value)
                all_report_data.append({
                    'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 
                    'gmts_qty': gmts_qty_data, 'plus_3_percent': plus_3_percent_data, 
                    'sewing_input': sewing_input_data if sewing_input_data else [], 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
        return all_report_data
    except: return None

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    
    bold_font = Font(bold=True)
    center = Alignment(horizontal='center')
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    ws['A1'] = "COTTON CLOTHING BD LTD"
    ws['A1'].font = Font(size=20, bold=True)
    ws.merge_cells('A1:I1')
    ws['A1'].alignment = center
    
    ws['A2'] = f"CLOSING REPORT - {internal_ref_no}"
    ws.merge_cells('A2:I2')
    ws['A2'].alignment = center
    
    row = 4
    for block in report_data:
        ws.cell(row=row, column=1, value=f"COLOR: {block['color']}").font = bold_font
        row += 1
        headers = ["SIZE", "ORDER 3%", "ACTUAL", "CUTTING", "INPUT", "BALANCE", "SHORT/PLUS", "%"]
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=row, column=c, value=h)
            cell.font = bold_font
            cell.border = border
        row += 1
        
        for i, size in enumerate(block['headers']):
            actual = int(block['gmts_qty'][i].replace(',', '') or 0)
            cut = int(block['cutting_qc'][i].replace(',', '') or 0) if i < len(block['cutting_qc']) else 0
            inp = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            
            ws.cell(row=row, column=1, value=size).border = border
            ws.cell(row=row, column=2, value=round(actual*1.03)).border = border
            ws.cell(row=row, column=3, value=actual).border = border
            ws.cell(row=row, column=4, value=cut).border = border
            ws.cell(row=row, column=5, value=inp).border = border
            ws.cell(row=row, column=6, value=cut-inp).border = border
            ws.cell(row=row, column=7, value=inp-round(actual*1.03)).border = border
            row += 1
        row += 2
        
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==============================================================================
# FLASK ROUTES (CONTROLLER LOGIC)
# ==============================================================================

@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
            stats = get_dashboard_summary_v2()
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
        
        now = get_bd_time()
        users_db[username]['last_login'] = now.strftime('%I:%M %p, %d %b')
        save_users(users_db)
        
        # Flash message welcome instead of popup
        flash(f"Welcome back, {username}!", "success")
        return redirect(url_for('index'))
    else:
        flash('Invalid Username or Password.', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully signed out.', 'info')
    return redirect(url_for('index'))

@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref_no = request.form['ref_no']
    report_data = fetch_closing_report_data(ref_no)
    if report_data:
        update_stats(ref_no, session.get('user'))
        return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=ref_no)
    flash(f"Booking {ref_no} not found!", "error")
    return redirect(url_for('index'))

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref_no')
    data = fetch_closing_report_data(ref)
    if data:
        f = create_formatted_excel_report(data, ref)
        return make_response(send_file(f, as_attachment=True, download_name=f"{ref}.xlsx"))
    flash("Data not found", "error")
    return redirect(url_for('index'))

@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    history = get_all_accessories_bookings()
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE, history_bookings=history, history_count=len(history))

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref_no = request.form.get('ref_no') or request.args.get('ref')
    if not ref_no: return redirect(url_for('accessories_search_page'))
    
    db_acc = load_accessories_db()
    if ref_no not in db_acc:
        api_data = fetch_closing_report_data(ref_no)
        colors = sorted(list(set([x['color'] for x in api_data]))) if api_data else []
        style = api_data[0]['style'] if api_data else "N/A"
        buyer = api_data[0]['buyer'] if api_data else "N/A"
        
        db_acc[ref_no] = {"style": style, "buyer": buyer, "colors": colors, "challans": []}
        save_accessories_db(db_acc)
    
    data = db_acc[ref_no]
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=data.get('colors', []), style=data.get('style'), buyer=data.get('buyer'), challans=data.get('challans'))

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    ref = request.args.get('ref')
    if not ref: return redirect(url_for('accessories_search_page'))
    db_acc = load_accessories_db()
    data = db_acc.get(ref, {})
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref, colors=data.get('colors', []), style=data.get('style'), buyer=data.get('buyer'), challans=data.get('challans'))

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form.get('ref')
    db_acc = load_accessories_db()
    if ref in db_acc:
        db_acc[ref]['challans'].append({
            "date": get_bd_date_str(),
            "line": request.form.get('line_no'),
            "color": request.form.get('color'),
            "qty": request.form.get('qty'),
            "status": "✔"
        })
        save_accessories_db(db_acc)
        flash("Challan Saved Successfully", "success")
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/refresh')
def accessories_refresh_data():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref')
    if not ref: return redirect(url_for('accessories_search_page'))
    
    db_acc = load_accessories_db()
    if ref in db_acc:
        api_data = fetch_closing_report_data(ref)
        if api_data:
            new_colors = sorted(list(set([x['color'] for x in api_data])))
            db_acc[ref]['colors'] = sorted(list(set(db_acc[ref]['colors'] + new_colors)))
            save_accessories_db(db_acc)
            flash("Data Refreshed", "success")
        else:
            flash("No new data found", "info")
            
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin': return redirect(url_for('index'))
    ref = request.form.get('ref')
    idx = int(request.form.get('index'))
    db_acc = load_accessories_db()
    if ref in db_acc:
        del db_acc[ref]['challans'][idx]
        save_accessories_db(db_acc)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref')
    db_acc = load_accessories_db()
    if ref not in db_acc: return redirect(url_for('accessories_search_page'))
    data = db_acc[ref]
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, ref=ref, buyer=data['buyer'], style=data['style'], challans=data['challans'], today=get_bd_date_str())

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    try:
        uploaded_files = request.files.getlist('pdf_files')
        all_data = []
        final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A'}
        
        for file in uploaded_files:
            if file.filename == '': continue
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            data, meta = extract_data_dynamic(file_path) # FIXED LOGIC USED HERE
            if meta['buyer'] != 'N/A': final_meta = meta
            if data: all_data.extend(data)
        
        if not all_data:
            return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found. (Check PDF format)")

        booking_ref = final_meta.get('booking', 'N/A')
        update_po_stats(session.get('user', 'Unknown'), len(uploaded_files), booking_ref)

        df = pd.DataFrame(all_data)
        df['Color'] = df['Color'].str.strip()
        df = df[df['Color'] != ""]
        unique_colors = df['Color'].unique()
        
        final_tables = []
        grand_total_qty = 0

        for color in unique_colors: 
            color_df = df[df['Color'] == color]
            pivot = color_df.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
            
            try:
                sorted_cols = sort_sizes(pivot.columns.tolist())
                pivot = pivot[sorted_cols]
            except: pass
            
            pivot['Total'] = pivot.sum(axis=1)
            grand_total_qty += pivot['Total'].sum()

            actual_qty = pivot.sum()
            actual_qty.name = 'Actual Qty'
            qty_plus_3 = (actual_qty * 1.03).round().astype(int)
            qty_plus_3.name = '3% Order Qty'
            
            pivot_final = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
            pivot_final = pivot_final.reset_index().rename(columns={'index': 'P.O NO'})
            
            html_table = pivot_final.to_html(classes='table table-bordered table-striped', index=False, border=0)
            final_tables.append({'color': color, 'table': html_table})
            
        return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")
    except Exception as e:
        flash(f"Error processing files: {str(e)}", "error")
        return redirect(url_for('index'))

# ==============================================================================
# HTML TEMPLATES (UPDATED)
# ==============================================================================

LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login - MNM Software</title>
    {COMMON_STYLES}
    <style>
        body {{ display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
        .login-card {{ width: 100%; max-width: 400px; padding: 40px; background: var(--gradient-card); border-radius: 24px; border: 1px solid var(--border-color); box-shadow: 0 25px 50px rgba(0,0,0,0.5); }}
    </style>
</head>
<body>
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category }}}}">{{{{ message }}}}</div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>
    <div class="login-card">
        <div class="brand-logo" style="justify-content: center;">MNM<span>Software</span></div>
        <form action="/login" method="post">
            <div style="margin-bottom: 20px;">
                <label style="display:block; color:var(--text-secondary); margin-bottom:8px; font-size:12px; font-weight:700;">USERNAME</label>
                <input type="text" name="username" required placeholder="Enter ID">
            </div>
            <div style="margin-bottom: 30px;">
                <label style="display:block; color:var(--text-secondary); margin-bottom:8px; font-size:12px; font-weight:700;">PASSWORD</label>
                <input type="password" name="password" required placeholder="Enter Password">
            </div>
            <button type="submit">Sign In <i class="fas fa-arrow-right" style="margin-left:8px;"></i></button>
        </form>
    </div>
    <script>
        setTimeout(() => document.getElementById('flash-container').style.display = 'none', 4000);
    </script>
</body>
</html>
"""

ADMIN_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Admin Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category }}}}">
                        <i class="fas fa-info-circle"></i> {{{{ message }}}}
                    </div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            <div class="nav-link" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-database"></i> Accessories</a>
            <div class="nav-link" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div id="section-dashboard">
            <div class="card" style="border:none; background:transparent; padding:0;">
                <h1 style="color:white;">Admin Dashboard</h1>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap:20px;">
                <div class="card">
                    <h3 style="color:var(--accent-orange); font-size:36px;">{{{{ stats.closing.count }}}}</h3>
                    <p style="color:var(--text-secondary);">Closing Reports</p>
                </div>
                <div class="card">
                    <h3 style="color:var(--accent-green); font-size:36px;">{{{{ stats.po.count }}}}</h3>
                    <p style="color:var(--text-secondary);">PO Generated</p>
                </div>
                <div class="card">
                    <h3 style="color:var(--accent-purple); font-size:36px;">{{{{ stats.accessories.count }}}}</h3>
                    <p style="color:var(--text-secondary);">Accessories</p>
                </div>
                <div class="card">
                    <h3 style="color:#3b82f6; font-size:36px;">{{{{ stats.users.count }}}}</h3>
                    <p style="color:var(--text-secondary);">Users</p>
                </div>
            </div>
        </div>
        
        <div id="section-analytics" style="display:none;">
            <div class="card" style="max-width: 500px; margin:0 auto;">
                <h3>Generate Closing Report</h3>
                <form action="/generate-report" method="post">
                    <label style="color:var(--text-secondary); font-size:12px;">INTERNAL REF NO</label>
                    <input type="text" name="ref_no" placeholder="e.g. IB-12345" required style="margin: 10px 0 20px;">
                    <button type="submit">Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="card" style="max-width: 600px; margin:0 auto;">
                <h3>PO Sheet Generator</h3>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                    <div style="border: 2px dashed var(--border-color); padding: 40px; text-align:center; border-radius:12px; margin-bottom:20px; cursor:pointer;" onclick="document.getElementById('file').click()">
                        <i class="fas fa-cloud-upload-alt" style="font-size: 40px; color: var(--accent-green);"></i>
                        <p style="color:var(--text-secondary); margin-top:10px;">Click to upload PDF files</p>
                        <input type="file" id="file" name="pdf_files" multiple accept=".pdf" style="display:none;">
                    </div>
                    <button type="submit" style="background:var(--accent-green);">Process Files</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        function showSection(id, el) {{
            document.querySelectorAll('.main-content > div').forEach(d => d.style.display = 'none');
            document.getElementById('section-' + id).style.display = 'block';
            if(el) {{
                document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));
                el.classList.add('active');
            }}
        }}
        setTimeout(() => document.getElementById('flash-container').style.display = 'none', 4000);
    </script>
</body>
</html>
"""

USER_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>User Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category }}}}">{{{{ message }}}}</div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>
    
    <div class="sidebar">
        <div class="brand-logo">MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active"><i class="fas fa-home"></i> Home</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <h1 style="color:white; margin-bottom:30px;">Welcome, {{{{ session.user }}}}!</h1>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:25px;">
            <div class="card">
                <h3><i class="fas fa-file-export" style="color:var(--accent-orange); margin-right:10px;"></i>Closing Report</h3>
                <p style="color:var(--text-secondary); margin:15px 0;">Generate production closing reports.</p>
                <form action="/generate-report" method="post">
                    <input type="text" name="ref_no" placeholder="Ref No" required style="margin-bottom:15px;">
                    <button type="submit">Generate</button>
                </form>
            </div>
            <div class="card">
                <h3><i class="fas fa-file-pdf" style="color:var(--accent-green); margin-right:10px;"></i>PO Sheet</h3>
                <p style="color:var(--text-secondary); margin:15px 0;">Process PDF files for PO Summary.</p>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                    <input type="file" name="pdf_files" multiple required style="margin-bottom:15px; padding:10px;">
                    <button type="submit" style="background:var(--accent-green);">Process</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Accessories Search</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category }}}}">{{{{ message }}}}</div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>
    <div style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div class="card" style="width: 100%; max-width: 500px; padding: 50px;">
            <div style="text-align:center; margin-bottom:30px;">
                <i class="fas fa-boxes" style="font-size:50px; color:var(--accent-purple);"></i>
                <h2 style="color: white; margin-top:20px;">Accessories Challan</h2>
            </div>
            <form action="/admin/accessories/input" method="post">
                <label style="color: var(--text-secondary); font-size: 12px; font-weight: 700; margin-bottom:5px; display:block;">BOOKING REFERENCE</label>
                <input type="text" name="ref_no" required placeholder="e.g. IB-12345" style="margin-bottom: 25px;">
                <button type="submit" style="background:var(--accent-purple);">Proceed to Entry <i class="fas fa-arrow-right"></i></button>
            </form>
            <div style="margin-top: 30px; border-top: 1px solid var(--border-color); padding-top: 20px; text-align: center; display:flex; justify-content:space-between;">
                <a href="/" style="color: var(--text-secondary); text-decoration: none;"><i class="fas fa-arrow-left"></i> Dashboard</a>
                <a href="/logout" style="color: var(--accent-red); text-decoration: none;">Sign Out</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Accessories Input</title>
    {COMMON_STYLES}
    <style>
        .action-btn {{ padding: 10px 15px; border-radius: 8px; border: none; cursor: pointer; color: white; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; transition:0.3s; }}
        .btn-refresh {{ background: #3B82F6; }} .btn-refresh:hover {{ background: #2563eb; }}
        .btn-print {{ background: #10B981; }} .btn-print:hover {{ background: #059669; }}
        .btn-delete {{ background: #EF4444; }}
    </style>
</head>
<body>
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category }}}}">{{{{ message }}}}</div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-boxes"></i> Accessories</div>
        <div class="nav-menu">
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Home</a>
            <a href="/admin/accessories" class="nav-link active"><i class="fas fa-search"></i> Search</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <div>
                <h2 style="color: white; margin-bottom: 5px;">{{{{ ref }}}}</h2>
                <p style="color: var(--text-secondary); font-size:14px;">{{{{ buyer }}}} • {{{{ style }}}}</p>
            </div>
            <div style="display: flex; gap: 10px;">
                <a href="/admin/accessories/refresh?ref={{{{ ref }}}}" class="tooltip" data-tooltip="Reload Data">
                    <button class="action-btn btn-refresh" style="width: auto;"><i class="fas fa-sync-alt"></i></button>
                </a>
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" target="_blank" class="tooltip" data-tooltip="Print Report">
                    <button class="action-btn btn-print" style="width: auto;"><i class="fas fa-print"></i></button>
                </a>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
            <div class="card">
                <h3 style="color: white; margin-bottom: 25px; border-bottom:1px solid var(--border-color); padding-bottom:10px;">New Entry</h3>
                <form action="/admin/accessories/save" method="post">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    <div style="margin-bottom: 20px;">
                        <label style="color: var(--text-secondary); font-size: 12px; font-weight:700; display:block; margin-bottom:5px;">COLOR</label>
                        <select name="color" required>
                            <option value="">Select Color</option>
                            {{% for c in colors %}}<option value="{{{{ c }}}}">{{{{ c }}}}</option>{{% endfor %}}
                        </select>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                        <div>
                            <label style="color: var(--text-secondary); font-size: 12px; font-weight:700; display:block; margin-bottom:5px;">LINE NO</label>
                            <input type="text" name="line_no" required placeholder="L-01">
                        </div>
                        <div>
                            <label style="color: var(--text-secondary); font-size: 12px; font-weight:700; display:block; margin-bottom:5px;">QUANTITY</label>
                            <input type="number" name="qty" required>
                        </div>
                    </div>
                    <button type="submit" style="background:var(--accent-purple);">Save Entry</button>
                </form>
            </div>
            
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border-color); padding-bottom:10px;">
                    <h3 style="color: white;">Recent History</h3>
                    <span style="background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:10px; font-size:12px;">{{{{ challans|length }}}}</span>
                </div>
                <div style="max-height: 400px; overflow-y: auto; padding-right:5px;">
                    {{% if challans %}}
                        {{% for item in challans|reverse %}}
                        <div style="background: rgba(255,255,255,0.03); padding: 15px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border:1px solid var(--border-color);">
                            <div>
                                <span style="background: var(--accent-orange); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; color: white;">{{{{ item.line }}}}</span>
                                <span style="color: white; margin-left: 10px; font-weight:500;">{{{{ item.color }}}}</span>
                            </div>
                            <div style="font-weight: 800; color: var(--accent-green); font-size:18px;">{{{{ item.qty }}}}</div>
                            {{% if session.role == 'admin' %}}
                            <form action="/admin/accessories/delete" method="POST" style="margin:0;">
                                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                                <input type="hidden" name="index" value="{{{{ loop.revindex0 }}}}">
                                <button type="submit" class="action-btn btn-delete" style="width:auto; padding:5px 10px;"><i class="fas fa-trash"></i></button>
                            </form>
                            {{% endif %}}
                        </div>
                        {{% endfor %}}
                    {{% else %}}
                        <div style="text-align:center; color:var(--text-secondary); padding:40px;">No entries yet.</div>
                    {{% endif %}}
                </div>
            </div>
        </div>
    </div>
    <script>
        setTimeout(() => document.getElementById('flash-container').style.display = 'none', 4000);
    </script>
</body>
</html>
"""

CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 30px; background: #f4f4f4; }
        .container { background: white; padding: 40px; box-shadow: 0 0 20px rgba(0,0,0,0.1); }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="no-print mb-4 d-flex justify-content-between">
            <a href="/" class="btn btn-secondary">Back</a>
            <div>
                <button onclick="window.print()" class="btn btn-primary">Print</button>
                <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-success">Download Excel</a>
            </div>
        </div>
        <h2 class="text-center mb-4">CLOSING REPORT: {{ ref_no }}</h2>
        {% for block in report_data %}
        <div class="mb-4">
            <h4>COLOR: {{ block.color }}</h4>
            <table class="table table-bordered text-center">
                <thead class="table-dark">
                    <tr><th>SIZE</th><th>ORDER 3%</th><th>ACTUAL</th><th>CUTTING</th><th>INPUT</th><th>BALANCE</th><th>SHORT/PLUS</th></tr>
                </thead>
                <tbody>
                    {% for i in range(block.headers|length) %}
                    <tr>
                        <td>{{ block.headers[i] }}</td>
                        <td>{{ block.plus_3_percent[i] }}</td>
                        <td>{{ block.gmts_qty[i] }}</td>
                        <td>{{ block.cutting_qc[i] if i < block.cutting_qc|length else 0 }}</td>
                        <td>{{ block.sewing_input[i] if i < block.sewing_input|length else 0 }}</td>
                        <td>-</td><td>-</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PO Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 30px; background: #f8f9fa; }
        .container { background: white; padding: 40px; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="no-print mb-4">
            <a href="/" class="btn btn-secondary">Back to Dashboard</a>
            <button onclick="window.print()" class="btn btn-danger float-end">Print PDF</button>
        </div>
        <h2 class="text-center">COTTON CLOTHING BD LTD</h2>
        <h4 class="text-center text-muted">Purchase Order Summary</h4>
        <div class="alert alert-info mt-3">
            <strong>Buyer:</strong> {{ meta.buyer }} | <strong>Style:</strong> {{ meta.style }} | <strong>Total Qty:</strong> {{ grand_total }}
        </div>
        {% if message %}<div class="alert alert-warning">{{ message }}</div>{% endif %}
        {% if tables %}
            {% for item in tables %}
                <h5 class="mt-4">COLOR: {{ item.color }}</h5>
                {{ item.table | safe }}
            {% endfor %}
        {% endif %}
    </div>
</body>
</html>
"""

ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Challan Report</title>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid black; padding: 8px; text-align: center; }
        th { background: #eee; }
    </style>
</head>
<body>
    <div style="text-align:center;">
        <h2>COTTON CLOTHING BD LTD</h2>
        <h3>ACCESSORIES DELIVERY CHALLAN</h3>
        <p>Ref: {{ ref }} | Date: {{ today }}</p>
    </div>
    <table>
        <thead><tr><th>LINE</th><th>COLOR</th><th>QTY</th><th>STATUS</th></tr></thead>
        <tbody>
            {% for item in challans %}
            <tr>
                <td>{{ item.line }}</td>
                <td>{{ item.color }}</td>
                <td>{{ item.qty }}</td>
                <td>{{ item.status }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    <script>window.print();</script>
</body>
</html>
"""

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
