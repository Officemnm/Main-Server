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
# ==============================================================================
# CSS & HTML Templates (Part 2: UI & Reports)
# ==============================================================================

# --- GLOBAL MODERN STYLES (For Dashboard & Forms) ---
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        :root { --primary-color: #4e54c8; --secondary-color: #8f94fb; }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        
        body {
            background: #1a1a2e; /* Dark Modern Background */
            background-image: linear-gradient(160deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            overflow-x: hidden;
        }

        /* Glassmorphism Card Style */
        .glass-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        .center-container {
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 20px;
        }
        .center-container .glass-card { width: 100%; max-width: 450px; text-align: center; }

        h1 { font-weight: 700; margin-bottom: 5px; background: -webkit-linear-gradient(#fff, #a2a8d3); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { color: #a0a0a0; font-size: 13px; margin-bottom: 30px; }

        .input-group { margin-bottom: 20px; text-align: left; }
        .input-group label { display: block; font-size: 12px; color: #a2a8d3; margin-bottom: 8px; font-weight: 500; letter-spacing: 0.5px; }
        
        input, select {
            width: 100%; padding: 12px 15px;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px; color: #fff; outline: none; transition: 0.3s;
        }
        input:focus, select:focus { border-color: #8f94fb; background: rgba(0, 0, 0, 0.4); }

        button {
            width: 100%; padding: 14px;
            background: linear-gradient(135deg, #4e54c8, #8f94fb);
            border: none; border-radius: 10px;
            color: white; font-weight: 600; cursor: pointer;
            transition: 0.3s; box-shadow: 0 4px 15px rgba(78, 84, 200, 0.4);
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(78, 84, 200, 0.6); }

        /* Report Specific Styles Override (White Backgrounds) */
        .report-body { background: white !important; color: black !important; }
        
        /* Table Styles for Admin Dashboard */
        .user-table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        .user-table th { text-align: left; color: #a2a8d3; font-weight: 500; padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .user-table td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #ddd; }
        
        .footer-credit { margin-top: 20px; font-size: 11px; color: rgba(255,255,255,0.3); text-align: center; }
    </style>
"""

# --- PO SHEET TEMPLATE (Classic Design Preserved) ---
PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PO Summary Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        /* Force classic white paper look */
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', sans-serif; color: #000; }
        .container { max-width: 1200px; }
        
        /* Header Logic */
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 20px; }
        .title { font-size: 2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        
        /* Info Box - Classic Boxed Style */
        .info-box { background: white; padding: 15px; border: 1px solid #ddd; border-left: 5px solid #2c3e50; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .info-item { font-size: 1.1rem; font-weight: 600; color: #555; }
        .info-val { color: #000; font-weight: 800; }
        
        /* Tables - Keeping the Pandas Style structure */
        .table-card { background: white; margin-bottom: 30px; border: 1px solid #999; }
        .color-header { background: #2c3e50; color: white; padding: 8px 12px; font-weight: 800; font-size: 1.2rem; text-transform: uppercase; }
        
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th, td { border: 1px solid #000 !important; padding: 6px; text-align: center; vertical-align: middle; }
        th { background-color: #eee !important; font-weight: 700; }
        
        /* Specific Columns from Pandas Logic */
        .total-col { background-color: #d1ecff !important; font-weight: bold; }
        .summary-row td { background-color: #e2e6ea !important; font-weight: 800; border-top: 2px solid #000 !important; }
        
        @media print {
            .no-print { display: none; }
            body { background: white; }
            .color-header { background: #2c3e50 !important; color: white !important; -webkit-print-color-adjust: exact; }
            .total-col { background: #d1ecff !important; -webkit-print-color-adjust: exact; }
            .summary-row td { background: #e2e6ea !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-end mb-3 no-print">
            <a href="/" class="btn btn-secondary me-2">Back</a>
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
        
        <div class="text-center mt-5" style="border-top:1px solid #000; padding-top:10px; font-size:12px; width: 200px; margin-left: auto; margin-right: auto;">
            <strong>Mehedi Hasan</strong>
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
    <title>Closing Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        body { background-color: #fff; padding: 20px; font-family: 'Segoe UI', sans-serif; color: black; }
        .container { max-width: 1400px; }
        .company-name { font-size: 2.2rem; font-weight: 800; color: #7B261A; text-align: center; }
        .report-title { font-size: 1.2rem; font-weight: 700; text-align: center; margin-bottom: 20px; text-decoration: underline; }
        
        .table-card { margin-bottom: 30px; border: 1px solid #000; }
        .color-header { background-color: #DE7465; color: black; padding: 5px 10px; font-weight: bold; border-bottom: 1px solid #000; }
        
        .table-bordered th, .table-bordered td { border: 1px solid #000 !important; text-align: center; vertical-align: middle; padding: 4px; font-size: 0.9rem; font-weight: 600; }
        .col-3pct { background-color: #B9C2DF !important; }
        .col-input { background-color: #C4D09D !important; }
        
        @media print {
            .no-print { display: none !important; }
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            .color-header { background-color: #DE7465 !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-end mb-3 no-print" style="gap:10px;">
            <a href="/" class="btn btn-outline-dark btn-sm">Dashboard</a>
            <button onclick="downloadExcel()" class="btn btn-success btn-sm">Download Excel</button>
            <button onclick="window.print()" class="btn btn-dark btn-sm">Print</button>
        </div>

        <div class="company-name">COTTON CLOTHING BD LTD</div>
        <div class="report-title">CLOSING REPORT [ INPUT SECTION ]</div>

        {% if report_data %}
        <div style="border:1px solid #000; padding:10px; margin-bottom:15px; background:#f9f9f9;">
            <div class="row">
                <div class="col-md-4"><strong>Buyer:</strong> {{ report_data[0].buyer }}</div>
                <div class="col-md-4"><strong>Style:</strong> {{ report_data[0].style }}</div>
                <div class="col-md-4 text-end"><strong>Ref No:</strong> {{ ref_no }}</div>
            </div>
        </div>

        {% for block in report_data %}
        <div class="table-card">
            <div class="color-header">COLOR: {{ block.color }}</div>
            <table class="table table-bordered mb-0">
                <thead>
                    <tr style="background:#DE7465;">
                        <th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th><th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th>
                    </tr>
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
                            <td style="color: {{ 'red' if short_plus < 0 else 'black' }}">{{ short_plus }}</td>
                            <td>{{ "%.2f"|format((short_plus / qty_3)*100) if qty_3 > 0 else 0 }}%</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        
        <div style="margin-top: 40px; text-align: center; font-weight: bold; border-top: 1px solid #000; width: 200px; margin-left: auto; margin-right: auto; padding-top: 5px;">
            Mehedi Hasan
        </div>
        {% endif %}
    </div>
    <script>
        function downloadExcel() {
            Swal.fire({
                title: 'Downloading...',
                timer: 2000,
                didOpen: () => { Swal.showLoading() }
            }).then(() => {
                window.location.href = "/download-closing-excel?ref_no={{ ref_no }}";
            });
        }
    </script>
</body>
</html>
"""

# --- ACCESSORIES REPORT TEMPLATE (Specific Design Requirement) ---
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
        /* Classic White Paper Report Style */
        body { font-family: 'Poppins', sans-serif; background: #fff; padding: 20px; color: #000; }
        .container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; position: relative; }
        
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; line-height: 1; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 18px; border-radius: 4px; }
        
        .info-grid { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
        .info-left { flex: 2; border: 1px dashed #555; padding: 15px; margin-right: 15px; }
        .info-right { flex: 1; border-left: 1px solid #ddd; padding-left: 15px; }
        .info-row { margin-bottom: 5px; font-size: 14px; }
        .booking-border { border: 2px solid #000; padding: 2px 8px; font-weight: 900; }

        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 10px; border: 1px solid #000; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; font-weight: 600; color: black; }
        
        .status-cell { font-size: 18px; font-weight: 900; color: black !important; } /* Black Tick */
        
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-weight: 900; background: #fff; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }

        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; border-radius: 4px; }
        
        /* Action buttons */
        .action-btn { background: none; border: none; cursor: pointer; font-size: 14px; margin: 0 5px; }
        .edit-icon { color: orange; }
        .del-icon { color: red; }

        /* Signature Section */
        .signatures { margin-top: 80px; display: flex; justify-content: space-between; padding: 0 50px; text-align: center; font-weight: bold; }
        .sig-line { border-top: 2px solid #000; width: 180px; padding-top: 5px; }

        /* Generator Name at Bottom Center */
        .generator-name { position: absolute; bottom: 10px; width: 100%; text-align: center; font-size: 12px; font-weight: bold; color: #000; left: 0; }

        @media print {
            .no-print { display: none; }
            .action-col { display: none; }
            .container { border: none; padding: 0; margin: 0; max-width: 100%; min-height: auto; }
            .generator-name { position: static; margin-top: 30px; }
        }
    </style>
</head>
<body>

<div class="no-print">
    <a href="/admin/accessories" class="btn">Search Again</a>
    <form action="/admin/accessories/input" method="post" style="display:inline;">
        <input type="hidden" name="ref_no" value="{{ ref }}">
        <button type="submit" class="btn" style="background:#27ae60;">Add Item</button>
    </form>
    <button onclick="window.print()" class="btn">🖨️ Print</button>
</div>

<div class="container">
    <div class="header">
        <div class="company-name">Cotton Clothing BD Limited</div>
        <div style="font-size:12px; font-weight:600; margin:5px 0;">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
        <div class="report-title">ACCESSORIES DELIVERY REPORT</div>
    </div>

    <div class="info-grid">
        <div class="info-left">
            <div class="info-row"><strong>Booking:</strong> <span class="booking-border">{{ ref }}</span></div>
            <div class="info-row"><strong>Buyer:</strong> {{ buyer }}</div>
            <div class="info-row"><strong>Style:</strong> {{ style }}</div>
            <div class="info-row"><strong>Date:</strong> {{ today }}</div>
        </div>
        <div class="info-right">
            <div class="info-row"><strong>Store:</strong> Clothing General Store</div>
            <div class="info-row"><strong>Send To:</strong> Cutting Section</div>
            <div class="info-row"><strong>Item Type:</strong> {{ item_type if item_type else 'General' }}</div>
        </div>
    </div>

    <div class="summary-container">
        <div style="text-align:center; font-weight:900; border-bottom:1px solid #000; margin-bottom:5px;">LINE-WISE SUMMARY</div>
        <table style="width:100%; font-size:13px; font-weight:700;">
            <tr>
            {% for line, qty in line_summary.items() %}
                <td>{{ line }}: {{ qty }} pcs</td>
                {% if loop.index % 4 == 0 %}</tr><tr>{% endif %}
            {% endfor %}
            </tr>
        </table>
        <div style="text-align:right; font-weight:800; margin-top:5px;">Total Deliveries: {{ count }}</div>
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
                    <td class="status-cell">
                        {% if item.status == '✔' %}✔{% endif %}
                    </td>
                    <td style="font-size:16px; font-weight:800;">{{ item.qty }}</td>
                    
                    {% if session.role == 'admin' %}
                    <td class="action-col">
                        <a href="/admin/accessories/edit?ref={{ ref }}&index={{ loop.index0 }}" class="action-btn edit-icon"><i class="fas fa-pencil-alt"></i></a>
                        <button onclick="confirmDelete('{{ ref }}', {{ loop.index0 }})" class="action-btn del-icon"><i class="fas fa-trash"></i></button>
                    </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="footer-total"><div class="total-box">TOTAL: {{ ns.grand_total }}</div></div>

    <div class="signatures">
        <div class="sig-line">Store Incharge</div>
        <div class="sig-line">Received By</div>
        <div class="sig-line">Cutting Incharge</div>
    </div>

    <div class="generator-name">Mehedi Hasan</div>
</div>

<script>
    function confirmDelete(ref, index) {
        Swal.fire({
            title: 'Delete this entry?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            confirmButtonText: 'Yes, Delete'
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

# --- DASHBOARD & FORM TEMPLATES (MODERN UI) ---

LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ERP Access</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <div style="font-size: 40px; margin-bottom: 10px;">🔒</div>
            <h1>System Access</h1>
            <p class="subtitle">Cotton Clothing ERP Gateway</p>
            <form action="/login" method="post">
                <div class="input-group">
                    <label>User ID</label>
                    <input type="text" name="username" placeholder="Username" required>
                </div>
                <div class="input-group">
                    <label>Access Pin</label>
                    <input type="password" name="password" placeholder="Password" required>
                </div>
                <button type="submit">Authenticate</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top:15px; color:#ff7675; font-size:13px;"><i class="fas fa-exclamation-circle"></i> {{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

USER_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>User Workspace</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card" style="max-width: 500px; text-align: left;">
            <div style="text-align:center;">
                <h1>Workspace</h1>
                <p class="subtitle">Hello, {{{{ session.user }}}}</p>
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 15px;">
                {{% if 'closing' in session.permissions %}}
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 14px; font-weight: 600; color: #a2a8d3; margin-bottom: 10px;"><i class="fas fa-file-invoice"></i> Closing Report</div>
                    <form action="/generate-report" method="post" onsubmit="loadAlert()">
                        <div style="display:flex; gap:10px;">
                            <input type="text" name="ref_no" placeholder="Reference No" required>
                            <button type="submit" style="width: auto; padding: 0 20px;"><i class="fas fa-arrow-right"></i></button>
                        </div>
                    </form>
                </div>
                {{% endif %}}

                {{% if 'accessories' in session.permissions %}}
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); display:flex; align-items:center; justify-content:space-between;">
                    <div style="font-size: 14px; font-weight: 600; color: #a2a8d3;"><i class="fas fa-boxes"></i> Accessories Store</div>
                    <a href="/admin/accessories" style="text-decoration:none;">
                        <button style="width:auto; padding: 8px 15px; font-size:12px;">Open</button>
                    </a>
                </div>
                {{% endif %}}

                {{% if 'po_sheet' in session.permissions %}}
                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-size: 14px; font-weight: 600; color: #a2a8d3; margin-bottom: 10px;"><i class="fas fa-file-pdf"></i> PO Generator</div>
                    <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="loadAlert()">
                        <div style="display:flex; gap:10px;">
                            <input type="file" name="pdf_files" multiple accept=".pdf" required>
                            <button type="submit" style="width: auto;"><i class="fas fa-cog"></i></button>
                        </div>
                    </form>
                </div>
                {{% endif %}}
            </div>

            <div style="margin-top: 30px; text-align: center;">
                <a href="/logout" style="color: #ff7675; text-decoration: none; font-size: 14px; font-weight: 500;">
                    <i class="fas fa-sign-out-alt"></i> Sign Out
                </a>
                <div class="footer-credit">© Mehedi Hasan</div>
            </div>
        </div>
    </div>
    <script>
        function loadAlert() {{ Swal.fire({{ title: 'Processing...', didOpen: () => Swal.showLoading() }}); }}
    </script>
</body>
</html>
"""

ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Find Booking</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <h1>Accessories Hub</h1>
            <p class="subtitle">Search Booking to Manage Challans</p>
            <form action="/admin/accessories/input" method="post">
                <div class="input-group">
                    <label>Booking Reference</label>
                    <input type="text" name="ref_no" placeholder="e.g. Booking-123" required>
                </div>
                <button type="submit">Proceed <i class="fas fa-arrow-right"></i></button>
            </form>
            <div style="margin-top: 20px;">
                <a href="/" style="color: rgba(255,255,255,0.5); font-size: 12px; text-decoration: none;">Back to Dashboard</a>
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
    <title>New Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <h1>New Challan</h1>
            <p class="subtitle">Booking: {{{{ ref }}}}</p>
            
            <div style="text-align:left; background:rgba(0,0,0,0.2); padding:10px; border-radius:10px; margin-bottom:20px; font-size:13px; color:#ddd;">
                <div><strong style="color:#a2a8d3;">Buyer:</strong> {{{{ buyer }}}}</div>
                <div><strong style="color:#a2a8d3;">Style:</strong> {{{{ style }}}}</div>
            </div>

            <form action="/admin/accessories/save" method="post" id="form">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                
                <div class="input-group">
                    <label>Item Type</label>
                    <select name="item_type">
                        <option value="" disabled selected>Select Type</option>
                        <option value="Top">Top</option>
                        <option value="Bottom">Bottom</option>
                    </select>
                </div>

                <div class="input-group">
                    <label>Color</label>
                    <select name="color" required>
                        {{% for c in colors %}}<option value="{{{{ c }}}}">{{{{ c }}}}</option>{{% endfor %}}
                    </select>
                </div>

                <div style="display:flex; gap:10px;">
                    <div class="input-group"><label>Line</label><input type="text" name="line_no" required></div>
                    <div class="input-group"><label>Size</label><input type="text" name="size" value="-"></div>
                </div>

                <div class="input-group"><label>Qty</label><input type="number" name="qty" required></div>

                <button type="submit">Save & View</button>
            </form>
            
            <div style="margin-top:20px; display:flex; justify-content:space-between;">
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="font-size:12px; color:#8f94fb;">View Report</a>
                <a href="/admin/accessories" style="font-size:12px; color:#aaa;">Back</a>
            </div>
            <div class="footer-credit">© Mehedi Hasan</div>
        </div>
    </div>
    <script>
        document.getElementById('form').addEventListener('submit', function(e){{
            e.preventDefault(); Swal.fire({{title:'Saving...', didOpen:()=>Swal.showLoading()}}); e.target.submit();
        }});
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
    <div class="center-container">
        <div class="glass-card">
            <h1>Edit Challan</h1>
            <form action="/admin/accessories/update" method="post">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <input type="hidden" name="index" value="{{{{ index }}}}">
                <div class="input-group"><label>Line</label><input type="text" name="line_no" value="{{{{ item.line }}}}" required></div>
                <div class="input-group"><label>Color</label><input type="text" name="color" value="{{{{ item.color }}}}" required></div>
                <div class="input-group"><label>Size</label><input type="text" name="size" value="{{{{ item.size }}}}" required></div>
                <div class="input-group"><label>Qty</label><input type="number" name="qty" value="{{{{ item.qty }}}}" required></div>
                <button type="submit">Update</button>
            </form>
            <div style="margin-top:20px;"><a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:white; font-size:12px;">Cancel</a></div>
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
    <title>Admin Console</title>
    {COMMON_STYLES}
    <style>
        .sidebar {{ width: 260px; background: rgba(0,0,0,0.3); padding: 30px; display: flex; flex-direction: column; border-right: 1px solid rgba(255,255,255,0.1); }}
        .content {{ flex: 1; padding: 40px; overflow-y: auto; }}
        .nav-item {{ padding: 12px 15px; margin-bottom: 5px; color: #a2a8d3; cursor: pointer; border-radius: 10px; transition: 0.3s; font-size: 14px; display: flex; align-items: center; gap: 10px; }}
        .nav-item:hover, .nav-item.active {{ background: rgba(255,255,255,0.1); color: white; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.05); }}
    </style>
</head>
<body>
    <div style="display: flex; height: 100vh;">
        <div class="sidebar">
            <h2 style="color:white; font-size:20px; margin-bottom: 5px;">Admin Panel</h2>
            <div style="font-size:10px; color:#a2a8d3; margin-bottom:40px;">SUPER USER ACCESS</div>
            
            <div class="nav-item active" onclick="show('closing', this)"><i class="fas fa-chart-line"></i> Closing Report</div>
            <div class="nav-item" onclick="show('acc', this)"><i class="fas fa-boxes"></i> Accessories</div>
            <div class="nav-item" onclick="show('po', this)"><i class="fas fa-file-contract"></i> PO Sheet</div>
            <div class="nav-item" onclick="show('users', this)"><i class="fas fa-users"></i> Users</div>
            <div class="nav-item" onclick="show('logs', this)"><i class="fas fa-history"></i> Logs</div>
            
            <div style="margin-top:auto; text-align:center;">
                <a href="/logout" style="color:#ff7675; text-decoration:none; font-size:13px;">Sign Out</a>
                <div style="font-size:10px; color:#555; margin-top:10px;">© Mehedi Hasan</div>
            </div>
        </div>

        <div class="content">
            <div class="stat-grid">
                <div class="stat-card"><h3>{{{{ stats.today }}}}</h3><p style="font-size:12px; color:#aaa;">Today's Reports</p></div>
                <div class="stat-card"><h3>{{{{ stats.month }}}}</h3><p style="font-size:12px; color:#aaa;">Monthly Total</p></div>
            </div>

            <div id="closing-section" class="section">
                <div class="glass-card" style="text-align:left;">
                    <h2>Generate Closing Report</h2>
                    <form action="/generate-report" method="post" onsubmit="load()">
                        <div class="input-group"><input type="text" name="ref_no" placeholder="Ref No" required></div>
                        <button type="submit">Generate</button>
                    </form>
                </div>
            </div>

            <div id="acc-section" class="section" style="display:none;">
                <div class="glass-card" style="text-align:left;">
                    <h2>Accessories Hub</h2>
                    <a href="/admin/accessories"><button>Enter Accessories Store</button></a>
                </div>
            </div>

            <div id="po-section" class="section" style="display:none;">
                <div class="glass-card" style="text-align:left;">
                    <h2>PO Sheet Generator</h2>
                    <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="load()">
                        <div class="input-group"><input type="file" name="pdf_files" multiple accept=".pdf" required></div>
                        <button type="submit">Process PDFs</button>
                    </form>
                </div>
            </div>

            <div id="users-section" class="section" style="display:none;">
                <div class="glass-card" style="text-align:left; max-width: 800px;">
                    <h2>User Management</h2>
                    <div style="background:rgba(0,0,0,0.2); padding:20px; border-radius:10px; margin-bottom:20px;">
                        <form id="uForm">
                            <input type="hidden" id="action" value="create">
                            <div style="display:flex; gap:10px; margin-bottom:10px;">
                                <input type="text" id="uname" placeholder="Username" required>
                                <input type="text" id="upass" placeholder="Password" required>
                            </div>
                            <div style="color:#aaa; font-size:12px; margin-bottom:10px;">
                                <label><input type="checkbox" id="p_close" checked> Closing</label>
                                <label><input type="checkbox" id="p_acc"> Accessories</label>
                                <label><input type="checkbox" id="p_po"> PO Sheet</label>
                            </div>
                            <button type="button" onclick="saveUser()" id="sBtn">Create User</button>
                        </form>
                    </div>
                    <table class="user-table"><tbody id="uTable"></tbody></table>
                </div>
            </div>
            
            <div id="logs-section" class="section" style="display:none;">
                <div class="glass-card" style="text-align:left; max-width: 800px;">
                    <h2>System Logs</h2>
                    <table class="user-table">
                        <thead><tr><th>Time</th><th>User</th><th>Ref</th></tr></thead>
                        <tbody>{{% for l in stats.history %}}<tr><td>{{{{ l.date }}}} {{{{ l.time }}}}</td><td>{{{{ l.user }}}}</td><td>{{{{ l.ref }}}}</td></tr>{{% endfor %}}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <script>
        function load() {{ Swal.fire({{title:'Processing...', didOpen:()=>Swal.showLoading()}}); }}
        function show(id, el) {{
            document.querySelectorAll('.nav-item').forEach(e=>e.classList.remove('active')); el.classList.add('active');
            document.querySelectorAll('.section').forEach(e=>e.style.display='none');
            document.getElementById(id+'-section').style.display='block';
            if(id==='users') loadUsers();
        }}
        function loadUsers() {{
            fetch('/admin/get-users').then(r=>r.json()).then(d=>{{
                let h=''; for(let [u,v] of Object.entries(d)){{
                    h+=`<tr><td>${{u}}</td><td>${{v.role}}</td><td>${{v.permissions}}</td><td>${{v.role!=='admin'?`<i class="fas fa-trash" style="color:red;cursor:pointer;" onclick="delUser('${{u}}')"></i>`:''}}</td></tr>`;
                }} document.getElementById('uTable').innerHTML=h;
            }});
        }}
        function saveUser() {{
            let u=document.getElementById('uname').value, p=document.getElementById('upass').value, perms=[];
            if(document.getElementById('p_close').checked) perms.push('closing');
            if(document.getElementById('p_acc').checked) perms.push('accessories');
            if(document.getElementById('p_po').checked) perms.push('po_sheet');
            fetch('/admin/save-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u, password:p, permissions:perms, action_type:'create'}})}})
            .then(r=>r.json()).then(d=>{{ Swal.fire(d.status, d.message, d.status); loadUsers(); }});
        }}
        function delUser(u) {{
            fetch('/admin/delete-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}})}})
            .then(r=>r.json()).then(d=>{{ Swal.fire('Deleted', '', 'success'); loadUsers(); }});
        }}
    </script>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTES (Part 3: Logic & Connections)
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
        flash('Invalid Credentials')
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
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    permissions = data.get('permissions', [])
    
    if not username or not password:
         return jsonify({'status': 'error', 'message': 'Missing data'})

    users_db = load_users()
    if username in users_db:
        return jsonify({'status': 'error', 'message': 'User already exists'})
        
    users_db[username] = {
        "password": password,
        "role": "user",
        "permissions": permissions
    }
    save_users(users_db)
    return jsonify({'status': 'success', 'message': 'User created successfully'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    username = request.json.get('username')
    users_db = load_users()
    
    if username == 'Admin':
         return jsonify({'status': 'error', 'message': 'Cannot delete Super Admin'})

    if username in users_db:
        del users_db[username]
        save_users(users_db)
        return jsonify({'status': 'success', 'message': 'User deleted'})
    
    return jsonify({'status': 'error', 'message': 'User not found'})

# --- CLOSING REPORT ROUTES ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'closing' not in session.get('permissions', []):
        flash("Access Denied")
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

# --- ACCESSORIES ROUTES (Logic Updated) ---
@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions', []):
        flash("Access Denied")
        return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no').strip()
    db = load_accessories_db()

    if ref_no in db:
        data = db[ref_no]
        colors, style, buyer = data['colors'], data['style'], data['buyer']
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"Booking not found: {ref_no}")
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

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    db = load_accessories_db()
    
    if ref in db:
        if request.form.get('item_type'):
            db[ref]['item_type'] = request.form.get('item_type')

        # Logic: Previous items get a BLACK TICK (✔), new item stays empty
        for item in db[ref]['challans']:
            item['status'] = "✔"
        
        new_entry = {
            "date": datetime.now().strftime("%d-%m-%Y"),
            "line": request.form.get('line_no'),
            "color": request.form.get('color'),
            "size": request.form.get('size'),
            "qty": request.form.get('qty'),
            "status": "" # New item has no status initially
        }
        
        db[ref]['challans'].append(new_entry)
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
    
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref,
                                  buyer=data['buyer'],
                                  style=data['style'],
                                  item_type=data.get('item_type', ''),
                                  challans=data['challans'],
                                  line_summary=dict(sorted(line_summary.items())),
                                  count=len(data['challans']),
                                  today=datetime.now().strftime("%d-%m-%Y"))

# RESTRICTED ROUTES (Admin Only)
@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return "Unauthorized", 403
    
    ref = request.form.get('ref')
    try: index = int(request.form.get('index'))
    except: return redirect(url_for('accessories_search_page'))

    db = load_accessories_db()
    if ref in db:
        if 0 <= index < len(db[ref]['challans']):
            del db[ref]['challans'][index]
            save_accessories_db(db)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return "Unauthorized", 403
    
    ref = request.args.get('ref')
    try: index = int(request.args.get('index'))
    except: return redirect(url_for('accessories_search_page'))
    
    db = load_accessories_db()
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=db[ref]['challans'][index])

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return "Unauthorized", 403
        
    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db = load_accessories_db()
    
    if ref in db:
        db[ref]['challans'][index].update({
            'qty': request.form.get('qty'),
            'line': request.form.get('line_no'),
            'color': request.form.get('color'),
            'size': request.form.get('size')
        })
        save_accessories_db(db)
            
    return redirect(url_for('accessories_print_view', ref=ref))

# --- PO SHEET ROUTE ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'po_sheet' not in session.get('permissions', []):
         flash("Access Denied")
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
        return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found in files.")

    # Data Processing with Pandas
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
        
        # Rendering HTML Table with Classes for CSS Styling
        table_html = pivot.to_html(classes='table', index=False, border=0)
        
        # Injecting CSS Classes for specific cells
        table_html = table_html.replace('<th>Total</th>', '<th class="total-col">Total</th>')
        table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        table_html = re.sub(r'<tr>\s*<td[^>]*>Actual Qty</td>', '<tr class="summary-row"><td>Actual Qty</td>', table_html)
        table_html = re.sub(r'<tr>\s*<td[^>]*>3% Order Qty</td>', '<tr class="summary-row"><td>3% Order Qty</td>', table_html)

        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
