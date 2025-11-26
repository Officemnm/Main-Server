import requests
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from io import BytesIO
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

# সেশন টাইমআউট (২ মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)

# ==============================================================================
# ডেটা ম্যানেজমেন্ট (JSON Files)
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
# Helper Logic (PO Parser & Closing Report)
# ==============================================================================
# (লজিকগুলো অপরিবর্তিত রাখা হয়েছে কোড ছোট রাখার জন্য, কিন্তু ফাংশনালিটি সব আছে)

def is_potential_size(header):
    h = header.strip().upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P.O NO"]: return False
    if re.match(r'^\d+$', h) or re.match(r'^\d+[AMYT]$', h) or re.match(r'^(XXS|XS|S|M|L|XL|XXL|XXXL|TU|ONE\s*SIZE)$', h): return True
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
        m = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", text)
        if m: meta['buyer'] = m.group(1).strip()
    m = re.search(r"(?:Internal )?Booking NO\.?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", text, re.IGNORECASE)
    if m: meta['booking'] = m.group(1).strip().replace('\n','').replace(' ','').split("System")[0]
    m = re.search(r"Style Ref\.?[:\s]*([\w-]+)", text, re.IGNORECASE)
    if m: meta['style'] = m.group(1).strip()
    m = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", text, re.IGNORECASE)
    if m: meta['season'] = m.group(1).strip()
    m = re.search(r"Dept\.?[\s\n:]*([A-Za-z]+)", text, re.IGNORECASE)
    if m: meta['dept'] = m.group(1).strip()
    m = re.search(r"Garments? Item[\s\n:]*([^\n\r]+)", text, re.IGNORECASE)
    if m: meta['item'] = m.group(1).strip().split("Style")[0].strip()
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
        
        om = re.search(r"Order no\D*(\d+)", first_page_text, re.IGNORECASE) or re.search(r"Order\s*[:\.]?\s*(\d+)", first_page_text, re.IGNORECASE)
        if om: order_no = om.group(1).strip()
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
                        temp_sizes = [s for s in parts[:total_idx] if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/", "Size's"]]
                        if sum(1 for s in temp_sizes if is_potential_size(s)) >= len(temp_sizes)/2:
                            sizes = temp_sizes
                            capturing_data = True
                        else: capturing_data = False
                    except: pass
                    continue
                if capturing_data:
                    if line.startswith("Total") or "quantity" in line.lower(): 
                        capturing_data = False; continue
                    clean_line = line.replace("Spec. price", "").replace("Spec", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line) or re.match(r'^[A-Z]\d+$', clean_line): continue
                    
                    nums = [int(n) for n in re.findall(r'\b\d+\b', line)]
                    if not nums: continue
                    color = re.sub(r'\s\d+$', '', clean_line).strip()
                    qty_list = nums[:-1] if len(nums) == len(sizes) + 1 else nums[:len(sizes)]
                    
                    if len(nums) < len(sizes): # Handle multiline
                         for nl in lines[i+1:]:
                             if "Total" in nl or re.search(r'[a-zA-Z]', nl.replace("Spec","")): break
                             nums.extend([int(n) for n in re.findall(r'\b\d+\b', nl)])
                         qty_list = nums[:len(sizes)]

                    for idx, size in enumerate(sizes):
                        if idx < len(qty_list):
                            extracted_data.append({'P.O NO': order_no, 'Color': color, 'Size': size, 'Quantity': qty_list[idx]})
    except Exception as e: print(e)
    return extracted_data, metadata

def get_erp_session(username, password):
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        r = s.post('http://180.92.235.190:8022/erp/login.php', data={'txt_userid': username, 'txt_password': password, 'submit': 'Login'}, timeout=30)
        return s if "dashboard.php" in r.url or "Invalid" not in r.text else None
    except: return None

def parse_erp_html(html):
    data = []
    try:
        soup = BeautifulSoup(html, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row: return None
        headers = [th.get_text(strip=True) for th in header_row.find_all('th') if 'total' not in th.get_text(strip=True).lower()]
        
        current_block = []
        item_blocks = []
        for row in soup.select('div#scroll_body table tbody tr'):
            if row.get('bgcolor') == '#cddcdc':
                if current_block: item_blocks.append(current_block)
                current_block = []
            else: current_block.append(row)
        if current_block: item_blocks.append(current_block)

        for block in item_blocks:
            style, color, buyer = "N/A", "N/A", "N/A"
            gmts, sew, cut = None, None, None
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    main, sub = cells[0].get_text(strip=True).lower(), cells[2].get_text(strip=True).lower()
                    if main == "style": style = cells[1].get_text(strip=True)
                    elif main == "color & gmts. item": color = cells[1].get_text(strip=True)
                    elif "buyer" in main: buyer = cells[1].get_text(strip=True)
                    
                    if sub == "gmts. color /country qty": gmts = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
                    if "sewing input" in main: sew = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
                    elif "sewing input" in sub: sew = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
                    if "cutting qc" in main and "balance" not in main: cut = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
                    elif "cutting qc" in sub and "balance" not in sub: cut = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
            
            if gmts:
                p3 = []
                for v in gmts:
                    try: p3.append(str(round(int(v.replace(',', '')) * 1.03)))
                    except: p3.append(v)
                data.append({'style': style, 'buyer': buyer, 'color': color, 'headers': headers, 'gmts_qty': gmts, 'plus_3_percent': p3, 'sewing_input': sew or [], 'cutting_qc': cut or []})
        return data
    except: return None

def create_excel(data, ref_no):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    
    # Fonts & Styles
    bf, tf, wbf = Font(bold=True), Font(size=32, bold=True, color="7B261A"), Font(size=16.5, bold=True, color="FFFFFF")
    ca, la = Alignment(horizontal='center', vertical='center'), Alignment(horizontal='left', vertical='center')
    bd = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    mbd = Border(left=Side(style='medium'), right=Side(style='medium'), top=Side(style='medium'), bottom=Side(style='medium'))
    # Fills
    ir_fill = PatternFill(start_color="7B261A", end_color="7B261A", fill_type="solid")
    head_fill = PatternFill(start_color="DE7465", end_color="DE7465", fill_type="solid")
    lb_fill = PatternFill(start_color="B9C2DF", end_color="B9C2DF", fill_type="solid")
    lg_fill = PatternFill(start_color="C4D09D", end_color="C4D09D", fill_type="solid")
    dg_fill = PatternFill(start_color="f1f2e8", end_color="f1f2e8", fill_type="solid")

    ws.merge_cells('A1:I1'); ws['A1'].value = "COTTON CLOTHING BD LTD"; ws['A1'].font = tf; ws['A1'].alignment = ca
    ws.merge_cells('A2:I2'); ws['A2'].value = "CLOSING REPORT [ INPUT SECTION ]"; ws['A2'].font = Font(size=15, bold=True); ws['A2'].alignment = ca
    
    meta = {'A4': 'BUYER', 'B4': data[0].get('buyer', ''), 'A5': 'IR/IB NO', 'B5': ref_no.upper(), 'A6': 'STYLE NO', 'B6': data[0].get('style', '')}
    for k, v in meta.items():
        ws[k].value = v; ws[k].font = bf; ws[k].border = bd; ws[k].alignment = la
        if k == 'B5': ws[k].fill, ws[k].font = ir_fill, wbf
        else: ws[k].fill = dg_fill
    
    ws.merge_cells('B4:G4'); ws.merge_cells('B5:G5'); ws.merge_cells('B6:G6')
    dt = datetime.now().strftime("%d/%m/%Y")
    right_meta = {'H4': 'CLOSING DATE', 'I4': dt, 'H5': 'SHIPMENT', 'I5': 'ALL', 'H6': 'PO NO', 'I6': 'ALL'}
    for k, v in right_meta.items():
        ws[k].value = v; ws[k].font = bf; ws[k].border = bd; ws[k].fill = dg_fill

    cr = 8
    for block in data:
        th = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for i, h in enumerate(th, 1):
            c = ws.cell(cr, i, h); c.font = bf; c.alignment = ca; c.border = mbd; c.fill = head_fill
        cr += 1
        start_row = cr
        
        for i, size in enumerate(block['headers']):
            ws.cell(cr, 1, block['color'] if i==0 else "").alignment = ca
            ws.cell(cr, 2, size).alignment = ca
            aq = int(block['gmts_qty'][i].replace(',','') or 0)
            iq = int(block['sewing_input'][i].replace(',','') or 0) if i < len(block['sewing_input']) else 0
            cq = int(block.get('cutting_qc',[])[i].replace(',','') or 0) if i < len(block.get('cutting_qc',[])) else 0
            
            ws.cell(cr, 4, aq); ws.cell(cr, 5, cq); ws.cell(cr, 6, iq)
            ws.cell(cr, 3, value=f"=ROUND(D{cr}*1.03, 0)")
            ws.cell(cr, 7, value=f"=E{cr}-F{cr}")
            ws.cell(cr, 8, value=f"=F{cr}-C{cr}")
            ws.cell(cr, 9, value=f'=IF(C{cr}<>0, H{cr}/C{cr}, 0)')

            for c in range(1, 10):
                cell = ws.cell(cr, c); cell.border = mbd if c==2 else bd; cell.alignment = ca
                if c in [1,2,3,6,9]: cell.font = bf
                if c==3: cell.fill = lb_fill
                elif c==6: cell.fill = lg_fill
                else: cell.fill = dg_fill
                if c==9: cell.number_format = '0.00%'
            cr += 1
        
        ws.merge_cells(start_row=start_row, start_column=1, end_row=cr-1, end_column=1)
        ws.merge_cells(start_row=cr, start_column=1, end_row=cr, end_column=2)
        ws.cell(cr, 1, "TOTAL").font = bf
        cols = "CDEFGHI"
        for idx, col in enumerate(cols, 3):
            f = f"=IF(C{cr}<>0, H{cr}/C{cr}, 0)" if col == 'I' else f"=SUM({col}{start_row}:{col}{cr-1})"
            cell = ws.cell(cr, idx, value=f)
            cell.font = bf; cell.fill = head_fill; cell.border = mbd; cell.alignment = ca
            if col == 'I': cell.number_format = '0.00%'
        cr += 2

    # Signature & Image
    try:
        r = requests.get('https://i.ibb.co/v6bp0jQW/rockybilly-regular.webp')
        img = Image(BytesIO(r.content))
        img.width, img.height = 95, 25
        ws.add_image(img, f'A{cr}')
    except: pass
    
    cr += 1
    ws.merge_cells(start_row=cr, start_column=1, end_row=cr, end_column=9)
    ws.cell(cr, 1, "Prepared By                 Input Incharge                 Cutting Incharge                 IE & Planning                 Sewing Manager                 Cutting Manager").font = Font(bold=True, size=15)
    
    # Layout
    for col in ['A','C','H']: ws.column_dimensions[col].width = 23
    ws.column_dimensions['B'].width = 8.5
    ws.page_setup.fitToPage = True

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio

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
    </style>
"""

LOGIN_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head><title>Login</title>{COMMON_STYLES}</head>
<body>
    <div style="display:flex; justify-content:center; align-items:center; height:100vh;">
        <div class="glass-card" style="width: 400px; text-align: center;">
            <h2 style="margin-bottom: 20px;">System Login</h2>
            <form action="/login" method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}<div style="color: #ff7675; margin-top: 10px;">{{{{ messages[0] }}}}</div>{{% endif %}}
            {{% endwith %}}
        </div>
    </div>
</body>
</html>
"""

# PO Sheet Template (Print Friendly) - kept strictly separate from admin CSS
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
        <div class="sidebar">
            <div style="text-align: center; margin-bottom: 30px;">
                <h2>Admin Panel</h2>
                <small style="color: #a29bfe;">SUPER ADMIN</small>
            </div>
            <a onclick="showTab('dashboard')" class="nav-item active" id="link-dashboard"><i class="fas fa-home"></i> Dashboard</a>
            <a onclick="showTab('closing')" class="nav-item" id="link-closing"><i class="fas fa-file-export"></i> Closing Report</a>
            <a onclick="showTab('po')" class="nav-item" id="link-po"><i class="fas fa-file-invoice"></i> PO Sheet</a>
            <a onclick="showTab('users')" class="nav-item" id="link-users"><i class="fas fa-users-cog"></i> User Management</a>
            <div style="margin-top: auto;">
                <a href="/logout" class="nav-item" style="color: #ff7675;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        </div>
        
        <div class="content">
            <div id="dashboard" class="section active">
                <h1>Welcome, {{{{ session.user }}}}</h1>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px;">
                    <div class="glass-card" style="background: linear-gradient(135deg, #667eea, #764ba2);">
                        <h3>Today</h3>
                        <h1>{{{{ stats.today }}}}</h1>
                        <small>Downloads</small>
                    </div>
                    <div class="glass-card" style="background: linear-gradient(135deg, #ff9966, #ff5e62);">
                        <h3>Month</h3>
                        <h1>{{{{ stats.month }}}}</h1>
                        <small>Downloads</small>
                    </div>
                </div>
            </div>

            <div id="closing" class="section">
                <div class="glass-card" style="max-width: 500px; margin: 0 auto;">
                    <h2><i class="fas fa-file-export"></i> Closing Report</h2>
                    <form action="/generate-report" method="post" onsubmit="showLoader()">
                        <label>Internal Reference No</label>
                        <input type="text" name="ref_no" placeholder="e.g. DFL/24/..." required>
                        <input type="hidden" name="download_token" value="1">
                        <button type="submit">Generate Report</button>
                    </form>
                </div>
            </div>

            <div id="po" class="section">
                <div class="glass-card" style="max-width: 500px; margin: 0 auto;">
                    <h2><i class="fas fa-file-invoice"></i> PO Sheet Generator</h2>
                    <form action="/generate-po-report" method="post" enctype="multipart/form-data">
                        <label>Select PDF Files (Booking & PO)</label>
                        <input type="file" name="pdf_files" multiple accept=".pdf" required>
                        <button type="submit" style="background: linear-gradient(135deg, #11998e, #38ef7d);">Generate Report</button>
                    </form>
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
        function showTab(id) {{
            document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            document.getElementById('link-'+id).classList.add('active');
        }}
        function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; setTimeout(() => {{ location.reload(); }}, 3000); }}
        
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
                <form action="/generate-report" method="post" onsubmit="showLoader()">
                    <input type="text" name="ref_no" placeholder="Reference No" required>
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

    <script>function showLoader() {{ document.getElementById('loading-overlay').style.display = 'flex'; setTimeout(() => {{ location.reload(); }}, 3000); }}</script>
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
    if 'closing' not in user_perms and users.get(session['user'], {}).get('role') != 'admin':
        flash("Permission Denied"); return redirect('/')

    ref = request.form.get('ref_no')
    s = get_erp_session("input2.clothing-cutting", "123456")
    if not s: flash("ERP Connection Failed"); return redirect('/')

    # Fetch logic simplified for brevity but fully functional
    url = 'http://180.92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'txt_internal_ref_no': ref, 'reportType': '3'}
    
    html = None
    for y in ['2025', '2024']:
        for c in range(1, 6):
            payload.update({'cbo_year_selection': y, 'cbo_company_name': str(c)})
            try: 
                r = s.post(url, data=payload, timeout=60)
                if "Data not Found" not in r.text: html = r.text; break
            except: continue
        if html: break
    
    if not html: flash("No Data Found"); return redirect('/')
    data = parse_erp_html(html)
    if not data: flash("Parsing Error"); return redirect('/')
    
    excel = create_excel(data, ref)
    update_stats(ref)
    return send_file(excel, as_attachment=True, download_name=f"Closing_{ref.replace('/','_')}.xlsx")

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
        tables.append({'color': color, 'table': html})

    return render_template_string(PO_TEMPLATE, tables=tables, meta=meta, grand_total=f"{grand_total:,}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
