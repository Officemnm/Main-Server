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

# কনফিগারেশন
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ২ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও ডাটাবেস
# ==============================================================================
STATS_FILE = 'stats.json'
USERS_FILE = 'users.json'
ACCESSORIES_DB_FILE = 'accessories_db.json' 

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
    today_count = sum(1 for d in downloads if d.get('iso_time', '').startswith(today_str))
    month_count = sum(1 for d in downloads if d.get('iso_time', '').startswith(month_str))
    return {"today": today_count, "month": month_count, "last_booking": last_booking, "history": downloads}

def load_accessories_db():
    if not os.path.exists(ACCESSORIES_DB_FILE): return {}
    try:
        with open(ACCESSORIES_DB_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_accessories_db(data):
    with open(ACCESSORIES_DB_FILE, 'w') as f: json.dump(data, f, indent=4)

# ==============================================================================
# লজিক পার্ট: PDF PARSER & CLOSING REPORT
# ==============================================================================
# (এই অংশটি আপনার আগের কোড থেকে অপরিবর্তিত রাখা হয়েছে ফাংশনালিটির জন্য)
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
        m = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", first_page_text)
        if m: meta['buyer'] = m.group(1).strip()
    m = re.search(r"(?:Internal )?Booking NO\.?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if m: meta['booking'] = m.group(1).strip().replace('\n', '').replace(' ', '').split("System")[0]
    m = re.search(r"Style Ref\.?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE) or re.search(r"Style Des\.?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
    if m: meta['style'] = m.group(1).strip()
    m = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re.IGNORECASE)
    if m: meta['season'] = m.group(1).strip()
    m = re.search(r"Dept\.?[\s\n:]*([A-Za-z]+)", first_page_text, re.IGNORECASE)
    if m: meta['dept'] = m.group(1).strip()
    m = re.search(r"Garments? Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
    if m: meta['item'] = m.group(1).strip().split("Style")[0].strip()
    return meta

def extract_data_dynamic(file_path):
    extracted_data = []
    metadata = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        if "Main Fabric Booking" in first_page_text or "Fabric Booking Sheet" in first_page_text:
            return [], extract_metadata(first_page_text)
        
        order_no = "Unknown"
        om = re.search(r"Order no\D*(\d+)", first_page_text, re.IGNORECASE) or re.search(r"Order\s*[:\.]?\s*(\d+)", first_page_text, re.IGNORECASE)
        if om: order_no = om.group(1).strip()
        if order_no.endswith("00"): order_no = order_no[:-2]

        for page in reader.pages:
            lines = page.extract_text().split('\n')
            sizes = []
            capturing_data = False
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue
                if ("Colo" in line or "Size" in line) and "Total" in line:
                    parts = line.split()
                    try:
                        total_idx = [idx for idx, x in enumerate(parts) if 'Total' in x][0]
                        temp_sizes = [s for s in parts[:total_idx] if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/", "Size's"]]
                        if temp_sizes and sum(1 for s in temp_sizes if is_potential_size(s)) >= len(temp_sizes)/2:
                            sizes = temp_sizes
                            capturing_data = True
                        else: capturing_data = False
                    except: pass
                    continue
                if capturing_data:
                    if line.startswith("Total") or "quantity" in line.lower() or "currency" in line.lower(): continue
                    clean_line = line.replace("Spec. price", "").replace("Spec", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line) or re.match(r'^[A-Z]\d+$', clean_line): continue
                    
                    nums = [int(n) for n in re.findall(r'\b\d+\b', line)]
                    color_name = re.sub(r'\s\d+$', '', clean_line).strip()
                    final_qtys = []
                    
                    if len(nums) >= len(sizes): final_qtys = nums[:len(sizes)]
                    elif len(nums) < len(sizes):
                        v_qtys = []
                        for nl in lines[i+1:]:
                            if "Total" in nl or re.search(r'[a-zA-Z]', nl.replace("Spec", "")): break
                            if re.match(r'^\d+$', nl.strip()): v_qtys.append(int(nl.strip()))
                        if len(v_qtys) >= len(sizes): final_qtys = v_qtys[:len(sizes)]
                    
                    if final_qtys and color_name:
                        for idx, s in enumerate(sizes):
                            extracted_data.append({'P.O NO': order_no, 'Color': color_name, 'Size': s, 'Quantity': final_qtys[idx]})
    except Exception as e: print(f"Error: {e}")
    return extracted_data, metadata

def get_authenticated_session(username, password):
    try:
        session_req = requests.Session()
        session_req.headers.update({'User-Agent': 'Mozilla/5.0'})
        res = session_req.post('http://180.92.235.190:8022/erp/login.php', data={'txt_userid': username, 'txt_password': password, 'submit': 'Login'}, timeout=30)
        return session_req if "dashboard.php" in res.url or "Invalid" not in res.text else None
    except: return None

def fetch_closing_report_data(internal_ref_no):
    s = get_authenticated_session("input2.clothing-cutting", "123456")
    if not s: return None
    url = 'http://180.92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'cbo_floor_id': '0', 'cbo_buyer_name': '0', 'txt_internal_ref_no': internal_ref_no, 'reportType': '3'}
    
    for y in ['2025', '2024']:
        for c in range(1, 6):
            payload.update({'cbo_year_selection': y, 'cbo_company_name': str(c)})
            try:
                r = s.post(url, data=payload, timeout=60)
                if r.status_code == 200 and "Data not Found" not in r.text: return parse_report_data(r.text)
            except: continue
    return None

def parse_report_data(html):
    data = []
    try:
        soup = BeautifulSoup(html, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row: return None
        headers = [th.get_text(strip=True) for th in header_row.find_all('th') if 'total' not in th.get_text(strip=True).lower()]
        
        current_block = []
        for row in soup.select('div#scroll_body table tbody tr'):
            if row.get('bgcolor') == '#cddcdc':
                if current_block: data.append(process_block(current_block, headers)); current_block = []
            else: current_block.append(row)
        if current_block: data.append(process_block(current_block, headers))
        return [d for d in data if d]
    except: return None

def process_block(rows, headers):
    style, color, buyer, gmts, inp, cut = "N/A", "N/A", "N/A", None, None, None
    for row in rows:
        cells = row.find_all('td')
        if len(cells) > 2:
            main, sub = cells[0].get_text(strip=True).lower(), cells[2].get_text(strip=True).lower()
            if main == "style": style = cells[1].get_text(strip=True)
            elif main == "color & gmts. item": color = cells[1].get_text(strip=True)
            elif "buyer" in main: buyer = cells[1].get_text(strip=True)
            
            if sub == "gmts. color /country qty": gmts = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
            if "sewing input" in main: inp = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
            elif "sewing input" in sub: inp = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
            if "cutting qc" in main and "balance" not in main: cut = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
            elif "cutting qc" in sub and "balance" not in sub: cut = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
    
    if gmts:
        plus3 = []
        for v in gmts:
            try: plus3.append(str(round(int(v.replace(',', '')) * 1.03)))
            except: plus3.append(v)
        return {'style': style, 'buyer': buyer, 'color': color, 'headers': headers, 'gmts_qty': gmts, 'plus_3_percent': plus3, 'sewing_input': inp or [], 'cutting_qc': cut or []}
    return None

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    
    # Fonts & Fills
    bold = Font(bold=True)
    title_f = Font(size=32, bold=True, color="7B261A")
    white_f = Font(size=16.5, bold=True, color="FFFFFF")
    align = Alignment(horizontal='center', vertical='center')
    thin = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
    med = Border(left=Side('medium'), right=Side('medium'), top=Side('medium'), bottom=Side('medium'))
    
    fills = {
        'red': PatternFill('solid', start_color="7B261A"),
        'header': PatternFill('solid', start_color="DE7465"),
        'blue': PatternFill('solid', start_color="B9C2DF"),
        'green': PatternFill('solid', start_color="C4D09D"),
        'dark_green': PatternFill('solid', start_color="f1f2e8"),
        'brown': PatternFill('solid', start_color="DE7465")
    }

    ws.merge_cells('A1:I1'); ws['A1'] = "COTTON CLOTHING BD LTD"; ws['A1'].font = title_f; ws['A1'].alignment = align
    ws.merge_cells('A2:I2'); ws['A2'] = "CLOSING REPORT [ INPUT SECTION ]"; ws['A2'].font = Font(size=15, bold=True); ws['A2'].alignment = align
    
    # Metadata
    ws['A4'] = 'BUYER'; ws['B4'] = report_data[0]['buyer']
    ws['A5'] = 'IR/IB NO'; ws['B5'] = internal_ref_no.upper(); ws['B5'].fill = fills['red']; ws['B5'].font = white_f
    ws['A6'] = 'STYLE NO'; ws['B6'] = report_data[0]['style']
    ws['H4'] = 'CLOSING DATE'; ws['I4'] = datetime.now().strftime("%d/%m/%Y")
    
    curr_row = 8
    for block in report_data:
        headers = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for i, h in enumerate(headers, 1):
            c = ws.cell(curr_row, i, h); c.font = bold; c.alignment = align; c.border = med; c.fill = fills['header']
        
        curr_row += 1
        start = curr_row
        for i, size in enumerate(block['headers']):
            act = int(block['gmts_qty'][i].replace(',', '') or 0)
            inp = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cut = int(block['cutting_qc'][i].replace(',', '') or 0) if i < len(block['cutting_qc']) else 0
            
            ws.cell(curr_row, 1, block['color'] if i == 0 else "")
            ws.cell(curr_row, 2, size)
            ws.cell(curr_row, 4, act)
            ws.cell(curr_row, 5, cut)
            ws.cell(curr_row, 6, inp)
            ws.cell(curr_row, 3, f"=ROUND(D{curr_row}*1.03, 0)").fill = fills['blue']
            ws.cell(curr_row, 7, f"=E{curr_row}-F{curr_row}")
            ws.cell(curr_row, 8, f"=F{curr_row}-C{curr_row}")
            ws.cell(curr_row, 9, f'=IF(C{curr_row}<>0, H{curr_row}/C{curr_row}, 0)').number_format = '0.00%'
            
            for c in range(1, 10): 
                cell = ws.cell(curr_row, c)
                cell.border = thin; cell.alignment = align
                if c not in [3]: cell.fill = fills['dark_green']
                if c == 6: cell.fill = fills['green']
            curr_row += 1
        
        ws.merge_cells(start_row=start, start_column=1, end_row=curr_row-1, end_column=1)
        ws.cell(start, 1).alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        # Totals
        ws.merge_cells(f"A{curr_row}:B{curr_row}"); ws[f"A{curr_row}"] = "TOTAL"
        for c, char in enumerate(['C', 'D', 'E', 'F', 'G', 'H'], 3):
            ws[f"{char}{curr_row}"] = f"=SUM({char}{start}:{char}{curr_row-1})"
        ws[f"I{curr_row}"] = f"=IF(C{curr_row}<>0, H{curr_row}/C{curr_row}, 0)"
        
        for c in range(1, 10):
            cell = ws.cell(curr_row, c)
            cell.font = bold; cell.fill = fills['brown']; cell.border = med; cell.alignment = align
            if c == 9: cell.number_format = '0.00%'
        curr_row += 2

    # Signature & Footer
    curr_row += 2
    ws.merge_cells(f"A{curr_row}:I{curr_row}")
    ws[f"A{curr_row}"] = "Prepared By                 Input Incharge                 Cutting Incharge                 IE & Planning                 Sewing Manager                 Cutting Manager"
    ws[f"A{curr_row}"].font = Font(bold=True, size=11); ws[f"A{curr_row}"].alignment = align

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==============================================================================
# CSS & TEMPLATES (MODERNIZED)
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
            content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.5); z-index: -1; position: fixed;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
            color: white;
            animation: floatIn 0.8s ease-out forwards;
            width: 100%; max-width: 450px;
        }

        .center-container {
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; width: 100%; padding: 20px;
        }

        @keyframes floatIn {
            from { opacity: 0; transform: translateY(40px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 { font-size: 24px; font-weight: 700; margin-bottom: 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.3); }
        p.subtitle { color: #dcdcdc; font-size: 13px; margin-bottom: 25px; font-weight: 300; }
        
        .input-group { text-align: left; margin-bottom: 18px; }
        .input-group label {
            display: block; font-size: 12px; color: #f1f2f6;
            font-weight: 600; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;
        }
        
        input[type="text"], input[type="password"], input[type="number"], input[type="file"], select {
            width: 100%; padding: 12px 15px;
            background: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.25);
            border-radius: 10px; color: #fff; font-size: 14px;
            outline: none; transition: 0.3s;
        }
        input:focus, select:focus {
            background: rgba(255, 255, 255, 0.25); border-color: #fff;
            box-shadow: 0 0 15px rgba(255,255,255,0.1);
        }
        
        button {
            width: 100%; padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 10px;
            font-size: 15px; font-weight: 600; cursor: pointer;
            transition: all 0.3s; box-shadow: 0 5px 15px rgba(118, 75, 162, 0.4);
            margin-top: 10px;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(118, 75, 162, 0.6); }
        
        .footer-copyright {
            margin-top: 25px; font-size: 11px; color: rgba(255,255,255,0.5);
            text-align: center; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;
        }

        /* Modern Loader Overlay */
        #loading-overlay {
            display: none; position: fixed; inset: 0;
            background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px);
            z-index: 9999; flex-direction: column; justify-content: center; align-items: center;
        }
        .modern-spinner {
            width: 60px; height: 60px;
            border: 4px solid rgba(255, 255, 255, 0.1);
            border-left-color: #38ef7d; border-radius: 50%;
            animation: spin 0.8s linear infinite; margin-bottom: 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        #loading-text { color: white; font-size: 18px; font-weight: 500; letter-spacing: 1px; }

        /* Admin Layout */
        .admin-container { display: flex; height: 100vh; position: fixed; top: 0; left: 0; width: 100%; }
        .admin-sidebar {
            width: 260px; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255,255,255,0.1); padding: 30px 20px;
            display: flex; flex-direction: column;
        }
        .admin-content { flex: 1; padding: 30px; overflow-y: auto; }
        .nav-item { margin-bottom: 10px; }
        .nav-link {
            display: flex; align-items: center; padding: 12px 15px; color: rgba(255,255,255,0.7);
            text-decoration: none; border-radius: 8px; transition: 0.3s; cursor: pointer;
        }
        .nav-link:hover, .nav-link.active {
            background: rgba(255,255,255,0.15); color: #fff;
        }
        .nav-link i { width: 25px; margin-right: 10px; }

        /* Tables */
        .user-table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }
        .user-table th { text-align: left; padding: 10px; background: rgba(255,255,255,0.1); color: #a29bfe; }
        .user-table td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #eee; }
        
        .user-btn { padding: 5px 10px; border-radius: 4px; font-size: 11px; margin-right: 5px; cursor: pointer; border: none; color: white;}
        .btn-edit { background: #f39c12; }
        .btn-delete { background: #e74c3c; }
    </style>
"""

# --- USER DASHBOARD (UPDATED) ---
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
        <div class="modern-spinner"></div>
        <div id="loading-text">Processing Request...</div>
    </div>

    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1>Operations Dashboard</h1>
            <p class="subtitle">Welcome, <span style="color:#a29bfe; font-weight:600;">{{{{ session.user }}}}</span></p>
            
            {{% if 'closing' in session.permissions %}}
            <div style="margin-bottom: 25px;">
                <h4 style="font-size:14px; margin-bottom:10px; color:#fab1a0;"><i class="fas fa-file-export"></i> Closing Report</h4>
                <form action="/generate-report" method="post" onsubmit="showLoader()">
                    <div class="input-group">
                        <input type="text" name="ref_no" placeholder="Enter Ref No (e.g. Booking-123)" required>
                    </div>
                    <button type="submit">Generate</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'accessories' in session.permissions %}}
            <div style="margin-bottom: 25px;">
                <h4 style="font-size:14px; margin-bottom:10px; color:#a29bfe;"><i class="fas fa-box-open"></i> Accessories Challan</h4>
                <a href="/admin/accessories" onclick="showLoader()" style="display:block; text-align:center; padding:12px; background:rgba(255,255,255,0.1); border-radius:10px; color:white; text-decoration:none; border:1px solid rgba(255,255,255,0.2); transition:0.3s;">
                    Go to Accessories Dashboard
                </a>
            </div>
            {{% endif %}}

            {{% if 'po_sheet' in session.permissions %}}
             <div style="margin-bottom: 25px;">
                <h4 style="font-size:14px; margin-bottom:10px; color:#55efc4;"><i class="fas fa-file-invoice"></i> PO Sheet Generator</h4>
                 <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoader()">
                    <div class="input-group">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required>
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, #00b894, #00cec9);">Generate Report</button>
                </form>
            </div>
            {{% endif %}}

            <a href="/logout" style="display:block; text-align:center; color:#ff7675; text-decoration:none; font-size:13px; margin-top:10px;">Sign Out</a>
            
            <div class="footer-copyright">
                &copy; Mehedi Hasan
            </div>
        </div>
    </div>

    <script>
        function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; }}
        
        // Flash Messages via SweetAlert2
        {{% with messages = get_flashed_messages() %}}
          {{% if messages %}}
            Swal.fire({{
              icon: 'info',
              title: 'Notification',
              text: '{{{{ messages[0] }}}}',
              confirmButtonColor: '#6c5ce7',
              background: '#2d3436',
              color: '#fff'
            }});
          {{% endif %}}
        {{% endwith %}}
    </script>
</body>
</html>
"""

# --- ADMIN DASHBOARD (UPDATED) ---
ADMIN_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay">
        <div class="modern-spinner"></div>
        <div id="loading-text">Processing...</div>
    </div>

    <div class="admin-container">
        <div class="admin-sidebar">
            <div style="text-align:center; margin-bottom:40px;">
                <h2 style="color:white; font-size:20px;">Admin Panel</h2>
                <p style="color:#a29bfe; font-size:12px;">Welcome, {{{{ session.user }}}}</p>
            </div>
            
            <div class="nav-item"><a class="nav-link active" onclick="showSection('closing', this)"><i class="fas fa-file-export"></i> Closing Report</a></div>
            <div class="nav-item"><a class="nav-link" href="/admin/accessories"><i class="fas fa-box-open"></i> Accessories</a></div>
            <div class="nav-item"><a class="nav-link" onclick="showSection('po', this)"><i class="fas fa-file-invoice"></i> PO Sheet</a></div>
            <div class="nav-item"><a class="nav-link" onclick="showSection('users', this)"><i class="fas fa-users-cog"></i> User Manage</a></div>
            <div class="nav-item"><a class="nav-link" onclick="showSection('history', this)"><i class="fas fa-history"></i> History</a></div>
            
            <div style="margin-top:auto;">
                <a href="/logout" class="nav-link" style="color:#ff7675;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
                <div class="footer-copyright" style="text-align:left; padding-left:15px;">&copy; Mehedi Hasan</div>
            </div>
        </div>

        <div class="admin-content">
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:20px; margin-bottom:30px;">
                <div class="glass-card" style="padding:20px;">
                    <h3 style="font-size:30px; margin-bottom:5px;">{{{{ stats.today }}}}</h3>
                    <p style="font-size:12px; color:#dcdcdc;">Today's Reports</p>
                </div>
                <div class="glass-card" style="padding:20px;">
                    <h3 style="font-size:30px; margin-bottom:5px;">{{{{ stats.month }}}}</h3>
                    <p style="font-size:12px; color:#dcdcdc;">Monthly Reports</p>
                </div>
            </div>

            <div id="closing-section">
                <div class="glass-card" style="max-width:500px;">
                    <h2>Generate Closing Report</h2>
                    <form action="/generate-report" method="post" onsubmit="showLoader()">
                        <div class="input-group">
                            <label>Ref No</label>
                            <input type="text" name="ref_no" required>
                        </div>
                        <button type="submit">Generate</button>
                    </form>
                </div>
            </div>

            <div id="po-section" style="display:none;">
                <div class="glass-card" style="max-width:500px;">
                    <h2>PO Sheet Generator</h2>
                    <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoader()">
                        <div class="input-group">
                            <label>Select PDF Files</label>
                            <input type="file" name="pdf_files" multiple accept=".pdf" required>
                        </div>
                        <button type="submit">Generate</button>
                    </form>
                </div>
            </div>

            <div id="users-section" style="display:none;">
                <div class="glass-card" style="max-width:800px;">
                    <h2>User Management</h2>
                    <form id="userForm" style="margin-top:20px; background:rgba(0,0,0,0.2); padding:20px; border-radius:10px;">
                        <input type="hidden" id="action_type" value="create">
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                            <input type="text" id="username" placeholder="Username">
                            <input type="text" id="password" placeholder="Password">
                        </div>
                        <div style="margin:15px 0;">
                            <label style="font-size:12px; display:block; margin-bottom:5px;">Permissions</label>
                            <label style="margin-right:10px;"><input type="checkbox" id="perm_closing" checked> Closing</label>
                            <label style="margin-right:10px;"><input type="checkbox" id="perm_acc"> Accessories</label>
                            <label><input type="checkbox" id="perm_po"> PO Sheet</label>
                        </div>
                        <button type="button" onclick="handleUser()">Save User</button>
                    </form>
                    
                    <table class="user-table">
                        <thead><tr><th>User</th><th>Role</th><th>Permissions</th><th>Action</th></tr></thead>
                        <tbody id="userTableBody"></tbody>
                    </table>
                </div>
            </div>

            <div id="history-section" style="display:none;">
                <div class="glass-card" style="max-width:800px;">
                    <h2>History Log</h2>
                    <table class="user-table">
                        <thead><tr><th>Date</th><th>User</th><th>Ref</th></tr></thead>
                        <tbody>
                            {{% for log in stats.history %}}
                            <tr><td>{{{{ log.date }}}} {{{{ log.time }}}}</td><td>{{{{ log.user }}}}</td><td>{{{{ log.ref }}}}</td></tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    </div>

    <script>
        function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; }}
        
        function showSection(id, el) {{
            document.querySelectorAll('.admin-content > div[id$="-section"]').forEach(d => d.style.display = 'none');
            document.getElementById(id + '-section').style.display = 'block';
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            el.classList.add('active');
            if(id === 'users') loadUsers();
        }}

        function loadUsers() {{
            fetch('/admin/get-users').then(r=>r.json()).then(data => {{
                let html = '';
                for(let u in data) {{
                    html += `<tr><td>${{u}}</td><td>${{data[u].role}}</td><td>${{data[u].permissions}}</td>
                    <td>${{data[u].role!=='admin' ? `<button class="user-btn btn-delete" onclick="delUser('${{u}}')">Delete</button>` : ''}}</td></tr>`;
                }}
                document.getElementById('userTableBody').innerHTML = html;
            }});
        }}

        function handleUser() {{
            const u = document.getElementById('username').value;
            const p = document.getElementById('password').value;
            if(!u || !p) return Swal.fire('Error', 'Fields cannot be empty', 'error');
            
            let perms = [];
            if(document.getElementById('perm_closing').checked) perms.push('closing');
            if(document.getElementById('perm_acc').checked) perms.push('accessories');
            if(document.getElementById('perm_po').checked) perms.push('po_sheet');

            fetch('/admin/save-user', {{
                method: 'POST', headers: {{'Content-Type':'application/json'}},
                body: JSON.stringify({{username:u, password:p, permissions:perms, action_type:'create'}})
            }}).then(r=>r.json()).then(res => {{
                if(res.status === 'success') {{
                    Swal.fire({{
                        icon: 'success', title: 'User Created', text: 'New user added successfully!',
                        background: '#2d3436', color: '#fff', confirmButtonColor: '#2ecc71'
                    }});
                    loadUsers();
                    document.getElementById('userForm').reset();
                }} else {{
                    Swal.fire('Error', res.message, 'error');
                }}
            }});
        }}

        function delUser(u) {{
            Swal.fire({{
                title: 'Are you sure?', text: "User will be deleted permanently", icon: 'warning',
                showCancelButton: true, confirmButtonColor: '#e74c3c', cancelButtonColor: '#3085d6', confirmButtonText: 'Yes, delete it!'
            }}).then((result) => {{
                if (result.isConfirmed) {{
                    fetch('/admin/delete-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}})}})
                    .then(r=>r.json()).then(res => {{
                        if(res.status==='success') {{ Swal.fire('Deleted!', 'User has been deleted.', 'success'); loadUsers(); }}
                    }});
                }}
            }})
        }}
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
    <title>Login</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 400px; text-align: center;">
            <h1 style="margin-bottom: 30px;">System Login</h1>
            <form action="/login" method="post">
                <div class="input-group"><input type="text" name="username" placeholder="Username" required></div>
                <div class="input-group"><input type="password" name="password" placeholder="Password" required></div>
                <button type="submit">Access System</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top:15px; color:#ff7675; font-size:13px;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            <div class="footer-copyright">&copy; Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

# --- ACCESSORIES TEMPLATES ---
ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Find Booking</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay"><div class="modern-spinner"></div><div id="loading-text">Fetching Data...</div></div>
    <div class="center-container">
        <div class="glass-card" style="max-width: 450px;">
            <h1>Accessories Dashboard</h1>
            <p class="subtitle">Enter Booking Number to Proceed</p>
            <form action="/admin/accessories/input" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                <div class="input-group">
                    <input type="text" name="ref_no" placeholder="e.g. Booking-123..." required>
                </div>
                <button type="submit">Proceed</button>
            </form>
            <a href="/" style="display:block; text-align:center; color:#fff; font-size:12px; margin-top:20px; text-decoration:none;">Back to Home</a>
            <div class="footer-copyright">&copy; Mehedi Hasan</div>
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
    <title>New Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay"><div class="modern-spinner"></div><div id="loading-text">Saving...</div></div>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px;">
            <h1>New Challan</h1>
            <p class="subtitle">Booking: {{{{ ref }}}}</p>
            <div style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px; margin-bottom: 20px; font-size: 13px;">
                <strong>Buyer:</strong> {{{{ buyer }}}} <br> <strong>Style:</strong> {{{{ style }}}}
            </div>

            <form action="/admin/accessories/save" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <div class="input-group">
                    <select name="item_type">
                        <option value="" disabled selected>-- Select Item Type --</option>
                        <option value="Top">Top</option>
                        <option value="Bottom">Bottom</option>
                    </select>
                </div>
                <div class="input-group">
                    <select name="color" required>
                        <option value="" disabled selected>-- Choose Color --</option>
                        {{% for color in colors %}}
                        <option value="{{{{ color }}}}">{{{{ color }}}}</option>
                        {{% endfor %}}
                    </select>
                </div>
                <div class="input-group"><input type="text" name="line_no" placeholder="Sewing Line No" required></div>
                <div class="input-group"><input type="text" name="size" placeholder="Size (Optional)" value="-"></div>
                <div class="input-group"><input type="number" name="qty" placeholder="Quantity" required></div>
                <button type="submit">Save & View</button>
            </form>
            <div style="margin-top: 15px; text-align:center;">
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:#a29bfe; font-size:12px;">View Report Only</a> | 
                <a href="/" style="color:#fff; font-size:12px;">Back</a>
            </div>
            <div class="footer-copyright">&copy; Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

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
        .container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; position: relative; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
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
        
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 10px; border: 1px solid #000; text-transform: uppercase; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; vertical-align: middle; color: #000; font-weight: 600; }
        
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-size: 16px; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }
        
        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; }
        .btn-add { background: #27ae60; }
        
        @media print {
            .no-print, .action-col { display: none !important; }
            .container { border: none; padding: 0; margin: 0; max-width: 100%; }
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
            <div class="right-item">Store: Clothing General Store</div>
            <div class="right-item">Send: Cutting</div>
            <div class="right-item">Item: {{ item_type if item_type else 'Top/Btm' }}</div>
        </div>
    </div>

    <div style="margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9;">
        <div style="font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px;">LINE SUMMARY</div>
        <div style="font-size: 13px; font-weight: 700; display:flex; flex-wrap:wrap; gap:10px; justify-content:center;">
            {% for line, qty in line_summary.items() %}
                <span style="border:1px solid #ccc; padding:2px 5px;">{{ line }}: {{ qty }}</span>
            {% endfor %}
        </div>
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
                        {% if loop.index == count %} <div class="line-card">{{ item.line }}</div>
                        {% else %} {{ item.line }} {% endif %}
                    </td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td style="color:green; font-weight:900; font-size:20px;">{{ item.status }}</td>
                    <td style="font-size:16px; font-weight:800;">{{ item.qty }}</td>
                    {% if session.role == 'admin' %}
                    <td class="action-col">
                        <form action="/admin/accessories/delete" method="POST" onsubmit="return confirm('Delete?');">
                            <input type="hidden" name="ref" value="{{ ref }}">
                            <input type="hidden" name="index" value="{{ loop.index0 }}">
                            <button type="submit" style="background:#e74c3c; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;"><i class="fas fa-trash"></i></button>
                        </form>
                    </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="footer-total">
        <div class="total-box">TOTAL QTY: {{ ns.grand_total }}</div>
    </div>

    <div style="margin-top: 60px; display: flex; justify-content: space-between; text-align: center; font-weight: bold; padding: 0 50px;">
        <div style="border-top: 2px solid #000; width: 180px;">Store Incharge</div>
        <div style="border-top: 2px solid #000; width: 180px;">Received By</div>
        <div style="border-top: 2px solid #000; width: 180px;">Cutting Incharge</div>
    </div>
    
    <div style="text-align:center; font-size:10px; margin-top:30px; border-top:1px solid #ddd; padding-top:5px;">
        Prepared By: Mehedi Hasan
    </div>
</div>

<script>
    // Show Success animation if redirected from Save
    const urlParams = new URLSearchParams(window.location.search);
    if(urlParams.get('saved') === 'true') {
        Swal.fire({
            icon: 'success',
            title: 'Challan Created!',
            showConfirmButton: false,
            timer: 1500,
            backdrop: `rgba(0,0,123,0.4)`
        });
        // Clear param
        window.history.replaceState({}, document.title, window.location.pathname + "?ref={{ ref }}");
    }
</script>
</body>
</html>
"""

# --- FLASK ROUTES ---

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    if session.get('role') == 'admin':
        return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=get_dashboard_summary())
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
    flash('Incorrect credentials.')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

# --- USER MANAGEMENT API ---
@app.route('/admin/get-users', methods=['GET'])
def get_users():
    if session.get('role') != 'admin': return jsonify({})
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if session.get('role') != 'admin': return jsonify({'status':'error'})
    data = request.json
    username, password = data.get('username'), data.get('password')
    users = load_users()
    if username in users: return jsonify({'status':'error', 'message':'User exists'})
    
    users[username] = {
        "password": password,
        "role": "user",
        "permissions": data.get('permissions', [])
    }
    save_users(users)
    return jsonify({'status': 'success'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if session.get('role') != 'admin': return jsonify({'status':'error'})
    username = request.json.get('username')
    users = load_users()
    if username in users and username != 'Admin':
        del users[username]
        save_users(users)
        return jsonify({'status':'success'})
    return jsonify({'status':'error'})

# --- REPORT ROUTES ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form['ref_no']
    data = fetch_closing_report_data(ref)
    if not data:
        flash(f'No data found for {ref}')
        return redirect(url_for('index'))
    # Use existing template, just replacing for brevity as requested
    from __main__ import CLOSING_REPORT_PREVIEW_TEMPLATE 
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=data, ref_no=ref)

# --- ACCESSORIES LOGIC ---
@app.route('/admin/accessories')
def accessories_search():
    if not session.get('logged_in'): return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form.get('ref_no')
    db = load_accessories_db()
    
    if ref in db:
        d = db[ref]
        return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref, colors=d['colors'], style=d['style'], buyer=d['buyer'])
    
    api_data = fetch_closing_report_data(ref)
    if not api_data:
        flash("Booking not found in ERP")
        return redirect(url_for('accessories_search'))
    
    colors = sorted(list(set([i['color'] for i in api_data])))
    db[ref] = {"style": api_data[0]['style'], "buyer": api_data[0]['buyer'], "colors": colors, "item_type": "", "challans": []}
    save_accessories_db(db)
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref, colors=colors, style=api_data[0]['style'], buyer=api_data[0]['buyer'])

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    ref = request.form.get('ref')
    db = load_accessories_db()
    
    # Mark old as done
    for c in db[ref]['challans']: c['status'] = "✔"
    
    if request.form.get('item_type'): db[ref]['item_type'] = request.form.get('item_type')
    
    db[ref]['challans'].append({
        "date": datetime.now().strftime("%d-%m-%Y"),
        "line": request.form.get('line_no'),
        "color": request.form.get('color'),
        "size": request.form.get('size'),
        "qty": request.form.get('qty'),
        "status": ""
    })
    save_accessories_db(db)
    return redirect(url_for('accessories_print', ref=ref, saved='true'))

@app.route('/admin/accessories/print')
def accessories_print():
    ref = request.args.get('ref')
    db = load_accessories_db()
    if ref not in db: return redirect(url_for('accessories_search'))
    
    data = db[ref]
    line_sum = {}
    for c in data['challans']:
        try: line_sum[c['line']] = line_sum.get(c['line'], 0) + int(c['qty'])
        except: pass
        
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
        ref=ref, buyer=data['buyer'], style=data['style'], item_type=data.get('item_type',''),
        challans=data['challans'], count=len(data['challans']),
        line_summary=dict(sorted(line_sum.items())), today=datetime.now().strftime("%d-%m-%Y"))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if session.get('role') != 'admin': return "Unauthorized"
    ref = request.form.get('ref')
    idx = int(request.form.get('index'))
    db = load_accessories_db()
    del db[ref]['challans'][idx]
    save_accessories_db(db)
    return redirect(url_for('accessories_print', ref=ref))

# --- PO REPORT (Existing Logic Wrapper) ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report_route():
    if not session.get('logged_in'): return redirect(url_for('index'))
    uploaded_files = request.files.getlist('pdf_files')
    all_data = []
    final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    
    for file in uploaded_files:
        if file.filename == '': continue
        path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(path)
        data, meta = extract_data_dynamic(path)
        if meta['buyer'] != 'N/A': final_meta = meta
        if data: all_data.extend(data)
    
    # Simple HTML generation (Inline for brevity as per instructions to keep functionality)
    if not all_data: return "No Data Found in PDFs"
    
    df = pd.DataFrame(all_data)
    df = df[df['Color'].str.strip() != ""]
    tables = []
    grand_total = 0
    
    for color in df['Color'].unique():
        cdf = df[df['Color'] == color]
        piv = cdf.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        piv = piv[sort_sizes(piv.columns.tolist())]
        piv['Total'] = piv.sum(axis=1)
        grand_total += piv['Total'].sum()
        
        act = piv.sum(); act.name = 'Actual Qty'
        ord3 = (act * 1.03).round().astype(int); ord3.name = '3% Order Qty'
        piv = pd.concat([piv, act.to_frame().T, ord3.to_frame().T]).reset_index().rename(columns={'index': 'P.O NO'})
        
        html = piv.to_html(classes='table table-bordered', index=False, border=1)
        tables.append({'color': color, 'table': html})

    # Use the PO_REPORT_TEMPLATE defined in previous code (Simplified here)
    from __main__ import PO_REPORT_TEMPLATE
    return render_template_string(PO_REPORT_TEMPLATE, tables=tables, meta=final_meta, grand_total=f"{grand_total:,}")

# Need to include the missing templates variables for the final exec
CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f8f9fa; padding: 30px; }
        .table th { background: #2c3e50 !important; color: white; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-end mb-3 no-print">
            <a href="/" class="btn btn-secondary me-2">Back</a>
            <button onclick="window.print()" class="btn btn-primary">Print</button>
            <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-success ms-2">Download Excel</a>
        </div>
        <h2 class="text-center mb-4">CLOSING REPORT - {{ ref_no }}</h2>
        {% for block in report_data %}
        <div class="card mb-4 shadow-sm">
            <div class="card-header bg-dark text-white fw-bold">COLOR: {{ block.color }}</div>
            <div class="card-body p-0">
                <table class="table table-bordered mb-0 text-center">
                    <thead>
                        <tr>
                            <th>SIZE</th><th>ORDER 3%</th><th>ACTUAL</th><th>CUTTING</th><th>INPUT</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for i in range(block.headers|length) %}
                        {% set act = block.gmts_qty[i]|replace(',','')|int %}
                        {% set ord = (act * 1.03)|round|int %}
                        {% set inp = block.sewing_input[i]|replace(',','')|int if i < block.sewing_input|length else 0 %}
                        {% set cut = block.cutting_qc[i]|replace(',','')|int if i < block.cutting_qc|length else 0 %}
                        <tr>
                            <td>{{ block.headers[i] }}</td>
                            <td style="background:#dfe6e9">{{ ord }}</td>
                            <td>{{ act }}</td>
                            <td>{{ cut }}</td>
                            <td style="background:#55efc4">{{ inp }}</td>
                            <td>{{ cut - inp }}</td>
                            <td style="color:{{ 'red' if (inp-ord) < 0 else 'green' }}">{{ inp - ord }}</td>
                            <td>{{ "%.2f"|format(((inp-ord)/ord)*100) if ord > 0 else 0 }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
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
    <style>@media print { .no-print { display: none; } body { background: white; } }</style>
</head>
<body>
    <div class="container mt-4">
        <div class="d-flex justify-content-between no-print mb-3">
            <a href="/" class="btn btn-secondary">Back</a>
            <button onclick="window.print()" class="btn btn-primary">Print</button>
        </div>
        <div class="text-center border-bottom pb-3 mb-3">
            <h2>Cotton Clothing BD Limited</h2>
            <h5>PO Summary Report</h5>
        </div>
        <div class="row mb-4">
            <div class="col-md-8">
                <strong>Buyer:</strong> {{ meta.buyer }} <br>
                <strong>Style:</strong> {{ meta.style }} <br>
                <strong>Booking:</strong> {{ meta.booking }}
            </div>
            <div class="col-md-4 text-end">
                <div class="p-3 bg-dark text-white rounded">
                    <small>GRAND TOTAL</small><br>
                    <span class="h2">{{ grand_total }}</span> Pcs
                </div>
            </div>
        </div>
        {% for t in tables %}
            <div class="mb-4">
                <h5 class="bg-light p-2 border">COLOR: {{ t.color }}</h5>
                {{ t.table | safe }}
            </div>
        {% endfor %}
        <div class="text-center mt-5 pt-3 border-top small">Report Generated By Mehedi Hasan</div>
    </div>
</body>
</html>
"""

# Excel Download
@app.route('/download-closing-excel')
def dl_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.args.get('ref_no')
    data = fetch_closing_report_data(ref)
    update_stats(ref, session.get('user'))
    f = create_formatted_excel_report(data, ref)
    return send_file(f, as_attachment=True, download_name=f"Report-{ref}.xlsx")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
