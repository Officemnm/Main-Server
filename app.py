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

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# ==============================================================================
# কনফিগারেশন এবং সেটআপ
# ==============================================================================

# PO ফাইলের জন্য আপলোড ফোল্ডার
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# সেশন টাইমআউট কনফিগারেশন (৩০ মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# টাইমজোন কনফিগারেশন (বাংলাদেশ)
bd_tz = pytz.timezone('Asia/Dhaka')

def get_bd_time():
    return datetime.now(bd_tz)

def get_bd_date_str():
    return get_bd_time().strftime('%d-%m-%Y')

# ==============================================================================
# Browser Cache Control (ব্যাক বাটন ফিক্স)
# ==============================================================================
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ==============================================================================
# MongoDB কানেকশন সেটআপ
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
# CSS STYLES (DASHBOARD ONLY - DARK THEME)
# ==============================================================================
# এই স্টাইলটি শুধুমাত্র ড্যাশবোর্ড এবং ইনপুট পেজের জন্য। রিপোর্টের জন্য নয়।
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-body: #121212;
            --bg-sidebar: #1E1E1E;
            --bg-card: #1F1F1F;
            --text-primary: #FFFFFF;
            --text-secondary: #A0A0A0;
            --accent-orange: #FF8C42;
            --accent-purple: #6C5CE7;
            --accent-green: #00b894;
            --accent-red: #ff7675;
            --border-color: #333333;
            --card-radius: 12px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        
        body {
            background-color: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* Sidebar */
        .sidebar {
            width: 260px; height: 100vh; background-color: var(--bg-sidebar);
            position: fixed; top: 0; left: 0; display: flex; flex-direction: column;
            padding: 30px 20px; border-right: 1px solid var(--border-color); z-index: 1000;
            transition: 0.3s;
        }
        .brand-logo { font-size: 22px; font-weight: 800; color: white; margin-bottom: 40px; }
        .brand-logo span { color: var(--accent-orange); }
        .nav-link {
            display: flex; align-items: center; padding: 12px 15px; color: var(--text-secondary);
            text-decoration: none; border-radius: 8px; margin-bottom: 5px; transition: 0.3s;
            cursor: pointer; font-weight: 500; font-size: 14px;
        }
        .nav-link:hover, .nav-link.active { background-color: rgba(255, 140, 66, 0.1); color: var(--accent-orange); }
        .nav-link i { width: 25px; margin-right: 10px; font-size: 16px; }

        /* Main Content */
        .main-content { margin-left: 260px; width: calc(100% - 260px); padding: 30px; }
        .page-title { font-size: 24px; font-weight: 700; color: white; margin-bottom: 20px; }

        /* Cards & Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .dashboard-grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--card-radius); padding: 25px; }
        
        .stat-card { display: flex; align-items: center; gap: 20px; }
        .stat-icon { width: 50px; height: 50px; background: rgba(255,255,255,0.05); border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 20px; color: var(--text-secondary); }
        .stat-info h3 { font-size: 24px; font-weight: 700; margin: 0; color: white; }
        .stat-info p { font-size: 12px; color: var(--text-secondary); margin: 0; text-transform: uppercase; }

        /* Forms */
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 5px; text-transform: uppercase; font-weight: 600; }
        input, select { width: 100%; padding: 12px; background: #2D2D2D; border: 1px solid #333; border-radius: 8px; color: white; font-size: 14px; outline: none; }
        input:focus { border-color: var(--accent-orange); }
        button { width: 100%; padding: 12px; background: var(--accent-orange); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.3s; }
        button:hover { background: #e67e22; transform: translateY(-2px); }

        /* Tables (Dashboard Style) */
        .dark-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .dark-table th { text-align: left; padding: 12px; color: var(--text-secondary); font-size: 12px; border-bottom: 1px solid #333; }
        .dark-table td { padding: 12px; color: white; font-size: 13px; border-bottom: 1px solid #2D2D2D; }
        .dark-table tr:hover td { background: rgba(255,255,255,0.02); }
        .action-btn { padding: 5px 10px; border-radius: 4px; text-decoration: none; font-size: 11px; margin-right: 5px; display: inline-block; cursor: pointer; border: none; }
        .btn-edit { background: var(--accent-purple); color: white; }
        .btn-del { background: var(--accent-red); color: white; }

        /* Loading */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; flex-direction: column; justify-content: center; align-items: center; }
        .spinner { width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid var(--accent-orange); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* Mobile */
        .mobile-toggle { display: none; position: fixed; top: 20px; right: 20px; z-index: 2000; color: white; background: #333; padding: 8px; border-radius: 5px; }
        @media (max-width: 900px) {
            .sidebar { transform: translateX(-100%); } .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; padding: 20px; }
            .dashboard-grid-2 { grid-template-columns: 1fr; }
            .mobile-toggle { display: block; }
        }
    </style>
"""
# ==============================================================================
# হেল্পার ফাংশন: ডাটাবেস ও ড্যাশবোর্ড লজিক
# ==============================================================================

def load_users():
    record = users_col.find_one({"_id": "global_users"})
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"],
            "created_at": "N/A",
            "last_login": "Never",
            "last_duration": "N/A"
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
    now = get_bd_time() # BD Time
    new_record = {
        "ref": ref_no,
        "user": username,
        "date": now.strftime('%d-%m-%Y'),
        "time": now.strftime('%I:%M %p'),
        "type": "Closing Report",
        "iso_time": now.isoformat()
    }
    data['downloads'].insert(0, new_record)
    if len(data['downloads']) > 1000:
        data['downloads'] = data['downloads'][:1000]
        
    data['last_booking'] = ref_no
    save_stats(data)

def update_po_stats(username, file_count):
    data = load_stats()
    now = get_bd_time()
    new_record = {
        "user": username,
        "file_count": file_count,
        "date": now.strftime('%d-%m-%Y'),
        "time": now.strftime('%I:%M %p'),
        "type": "PO Sheet",
        "iso_time": now.isoformat()
    }
    if 'downloads' not in data: data['downloads'] = []
    data['downloads'].insert(0, new_record)
    if len(data['downloads']) > 1000:
        data['downloads'] = data['downloads'][:1000]
    save_stats(data)

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

# ড্যাশবোর্ডের চার্ট এবং স্ট্যাটাস ডাটা তৈরি করার লজিক
def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    now = get_bd_time()
    today_str = now.strftime('%d-%m-%Y')
    
    # 1. User Stats
    user_details = []
    for u, d in users_data.items():
        user_details.append({
            "username": u,
            "role": d.get('role', 'user'),
            "created_at": d.get('created_at', 'N/A'),
            "last_login": d.get('last_login', 'Never'),
            "last_duration": d.get('last_duration', 'N/A')
        })

    # 2. Accessories Today
    acc_today_count = 0
    acc_today_list = []
    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            if challan.get('date') == today_str:
                acc_today_count += 1
                acc_today_list.append({
                    "ref": ref,
                    "buyer": data.get('buyer'),
                    "style": data.get('style'),
                    "time": "Today", 
                    "qty": challan.get('qty')
                })

    # 3. Closing & PO Today (From History)
    closing_today_count = 0
    po_today_count = 0
    closing_list = []
    po_list = []
    
    history = stats_data.get('downloads', [])
    for item in history:
        item_date = item.get('date', '')
        if item_date == today_str:
            if item.get('type') == 'PO Sheet':
                po_today_count += 1
                po_list.append(item)
            else: # Defaults to Closing Report
                closing_today_count += 1
                closing_list.append(item)

    return {
        "users": {
            "count": len(users_data),
            "details": user_details
        },
        "accessories": {
            "count": acc_today_count,
            "details": acc_today_list
        },
        "closing": {
            "count": closing_today_count,
            "details": closing_list
        },
        "po": {
            "count": po_today_count,
            "details": po_list
        },
        "chart_data": [closing_today_count, acc_today_count, po_today_count],
        "history": history
    }

# ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PDF) - FULL LOGIC
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
# লজিক পার্ট: CLOSING REPORT API & EXCEL GENERATION - FULL LOGIC
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
    current_date = get_bd_time().strftime("%d/%m/%Y")
    
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
# HTML TEMPLATES: LOGIN, DASHBOARD & UI (DARK THEME)
# ==============================================================================

LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center;">
    <div class="card" style="width: 100%; max-width: 400px; padding: 40px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="font-size: 24px; font-weight: 800; color: white;">Cotton<span style="color:var(--accent-orange)">Solutions</span></div>
            <div style="color: var(--text-secondary); font-size: 13px; letter-spacing: 1px;">SECURE ACCESS</div>
        </div>
        <form action="/login" method="post">
            <div class="input-group">
                <label>USERNAME</label>
                <input type="text" name="username" required>
            </div>
            <div class="input-group">
                <label>PASSWORD</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Sign In</button>
        </form>
        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div style="margin-top: 20px; color: #ff7675; font-size: 13px; text-align: center;">{{{{ messages[0] }}}}</div>
            {{% endif %}}
        {{% endwith %}}
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
    <title>Admin Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay"><div class="spinner"></div><div style="color:white; margin-top:15px;">Processing...</div></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo">Cotton<span>Solutions</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            <div class="nav-link" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-database"></i> Accessories DB</a>
            <div class="nav-link" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            <div class="nav-link" onclick="showSection('settings', this)"><i class="fas fa-users-cog"></i> User Manage</div>
        </div>
        <a href="/logout" class="nav-link logout-btn"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>

    <div class="main-content">
        <div id="section-dashboard">
            <div class="header-section">
                <div><div class="page-title">Main Dashboard</div><div class="page-subtitle">Welcome back, Admin.</div></div>
                <div style="background:var(--bg-card); padding:8px 15px; border-radius:30px; border:1px solid var(--border-color); font-size:13px; font-weight:600;"><span style="color:var(--accent-green)">●</span> System Online</div>
            </div>

            <div class="stats-grid">
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-file-export"></i></div><div class="stat-info"><h3>{{{{ stats.closing.count }}}}</h3><p>Closing</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-boxes"></i></div><div class="stat-info"><h3>{{{{ stats.accessories.count }}}}</h3><p>Accessories</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-file-pdf"></i></div><div class="stat-info"><h3>{{{{ stats.po.count }}}}</h3><p>PO Sheets</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-users"></i></div><div class="stat-info"><h3>{{{{ stats.users.count }}}}</h3><p>Users</p></div></div>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header"><span>Analytics</span><i class="fas fa-chart-line" style="color:var(--accent-orange)"></i></div>
                    <div style="height: 250px;"><canvas id="mainChart"></canvas></div>
                </div>
                <div class="card">
                    <div class="section-header"><span>Usage</span></div>
                    <div class="progress-item"><div class="progress-labels"><span>Closing</span><span>High</span></div><div class="progress-bg"><div class="progress-fill" style="width: 85%;"></div></div></div>
                    <div class="progress-item"><div class="progress-labels"><span>Accessories</span><span>Medium</span></div><div class="progress-bg"><div class="progress-fill" style="width: 60%; background: var(--accent-purple);"></div></div></div>
                    <div class="progress-item"><div class="progress-labels"><span>PO</span><span>Normal</span></div><div class="progress-bg"><div class="progress-fill" style="width: 45%; background: var(--accent-green);"></div></div></div>
                </div>
            </div>

            <div class="card">
                <div class="section-header"><span>Recent History</span></div>
                <div style="overflow-x: auto;">
                    <table class="dark-table">
                        <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Status</th></tr></thead>
                        <tbody>
                            {{% for log in stats.history %}}
                            <tr><td>{{{{ log.time }}}}</td><td style="font-weight:600;">{{{{ log.user }}}}</td><td>{{{{ log.type }}}}</td><td><span style="color:var(--accent-green)">Completed</span></td></tr>
                            {{% else %}}<tr><td colspan="4" style="text-align:center; padding:20px; color:var(--text-secondary);">No activity found.</td></tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="section-analytics" style="display:none;">
            <div class="card" style="max-width:600px; margin:0 auto;">
                <div class="section-header">Generate Closing Report</div>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>INTERNAL REF NO</label><input type="text" name="ref_no" placeholder="e.g. Booking-123" required></div>
                    <button type="submit">Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="card" style="max-width:600px; margin:0 auto;">
                <div class="section-header">PO Sheet Generator</div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group" style="border: 2px dashed var(--border-color); padding: 30px; text-align: center; border-radius: 12px;">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display:none;" id="file-upload">
                        <label for="file-upload" style="cursor:pointer; color:var(--accent-orange); margin-bottom:0;"><i class="fas fa-cloud-upload-alt" style="font-size:30px;"></i><br>Click to Upload Files</label>
                        <div id="file-count" style="margin-top:10px; font-size:12px; color:var(--text-secondary);">No files selected</div>
                    </div>
                    <button type="submit" style="margin-top:20px;">Process Files</button>
                </form>
            </div>
        </div>

        <div id="section-settings" style="display:none;">
            <div class="dashboard-grid-2">
                <div class="card"><div class="section-header">Directory</div><div id="userTableContainer">Loading...</div></div>
                <div class="card"><div class="section-header">Manage User</div>
                    <form id="userForm">
                        <input type="hidden" id="action_type" value="create">
                        <div class="input-group"><label>USER</label><input type="text" id="new_username" required></div>
                        <div class="input-group"><label>PASS</label><input type="text" id="new_password" required></div>
                        <div class="input-group"><label>PERMS</label>
                            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                                <label style="background:#2D2D2D; padding:8px; border-radius:6px;"><input type="checkbox" id="perm_closing" checked> Closing</label>
                                <label style="background:#2D2D2D; padding:8px; border-radius:6px;"><input type="checkbox" id="perm_po"> PO</label>
                                <label style="background:#2D2D2D; padding:8px; border-radius:6px;"><input type="checkbox" id="perm_acc"> Acc</label>
                            </div>
                        </div>
                        <button type="button" onclick="handleUserSubmit()" id="saveUserBtn">Save User</button>
                        <button type="button" onclick="resetForm()" style="margin-top:10px; background:#2D2D2D; color:white;">Reset</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showSection(id, element) {{
            ['dashboard', 'analytics', 'help', 'settings'].forEach(sid => document.getElementById('section-' + sid).style.display = 'none');
            document.getElementById('section-' + id).style.display = 'block';
            if(element) {{ document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active')); element.classList.add('active'); }}
            if(id === 'settings') loadUsers();
            if(window.innerWidth < 992) document.querySelector('.sidebar').classList.remove('active');
        }}
        document.getElementById('file-upload')?.addEventListener('change', function() {{ document.getElementById('file-count').innerText = this.files.length + " files selected"; }});
        const ctx = document.getElementById('mainChart').getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 300); gradient.addColorStop(0, 'rgba(255, 140, 66, 0.2)'); gradient.addColorStop(1, 'rgba(255, 140, 66, 0)');
        new Chart(ctx, {{ type: 'line', data: {{ labels: ['Jan','Feb','Mar','Apr','May','Jun'], datasets: [{{ data: [{{{{ stats.chart_data[0] }}}}+10, {{{{ stats.chart_data[1] }}}}+15, {{{{ stats.chart_data[2] }}}}+5, 25, 30, 40], borderColor: '#FF8C42', backgroundColor: gradient, tension: 0.4, fill: true }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ grid: {{ display: false, color: '#333' }} }}, y: {{ grid: {{ color: '#2D2D2D' }} }} }} }} }});
        
        function loadUsers() {{
            fetch('/admin/get-users').then(res => res.json()).then(data => {{
                let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th>Act</th></tr></thead><tbody>';
                for(const [u, d] of Object.entries(data)) {{
                    html += `<tr><td>${{u}}</td><td>${{d.role}}</td><td>${{d.role !== 'admin' ? `<i class="fas fa-edit" style="color:#3498db; cursor:pointer; margin-right:10px;" onclick="editUser('${{u}}', '${{d.password}}', '${{d.permissions.join(',')}}')"></i> <i class="fas fa-trash" style="color:#ff7675; cursor:pointer;" onclick="deleteUser('${{u}}')"></i>` : '-'}}</td></tr>`;
                }}
                document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
            }});
        }}
        function handleUserSubmit() {{
            const u = document.getElementById('new_username').value, p = document.getElementById('new_password').value, a = document.getElementById('action_type').value;
            let perms = []; ['closing', 'po_sheet', 'accessories'].forEach(id => {{ if(document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked) perms.push(id); }});
            fetch('/admin/save-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u, password: p, permissions: perms, action_type: a }}) }}).then(r => r.json()).then(d => {{ if(d.status === 'success') {{ loadUsers(); resetForm(); }} else alert(d.message); }});
        }}
        function editUser(u, p, permsStr) {{ document.getElementById('new_username').value = u; document.getElementById('new_username').readOnly = true; document.getElementById('new_password').value = p; document.getElementById('action_type').value = 'update'; document.getElementById('saveUserBtn').innerText = 'Update User'; let pArr = permsStr.split(','); ['closing', 'po_sheet', 'accessories'].forEach(id => {{ document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked = pArr.includes(id); }}); }}
        function resetForm() {{ document.getElementById('userForm').reset(); document.getElementById('action_type').value = 'create'; document.getElementById('saveUserBtn').innerText = 'Save User'; document.getElementById('new_username').readOnly = false; }}
        function deleteUser(u) {{ if(confirm('Delete user?')) fetch('/admin/delete-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u }}) }}).then(() => loadUsers()); }}
    </script>
</body>
</html>
"""

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
    <div id="loading-overlay"><div class="spinner"></div></div>
    <div class="sidebar">
        <div class="brand-logo">Cotton<span>Solutions</span></div>
        <div class="nav-menu"><div class="nav-link active"><i class="fas fa-home"></i> Home</div></div>
        <a href="/logout" class="nav-link logout-btn"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>
    <div class="main-content">
        <div class="header-section"><div><div class="page-title">Welcome, {{{{ session.user }}}}</div><div class="page-subtitle">Your assigned modules.</div></div></div>
        <div class="stats-grid">
            {{% if 'closing' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Closing Report</span><i class="fas fa-file-export" style="color:var(--accent-orange)"></i></div>
            <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>REF NO</label><input type="text" name="ref_no" required></div><button>Generate</button></form></div>{{% endif %}}
            {{% if 'po_sheet' in session.permissions %}}
            <div class="card"><div class="section-header"><span>PO Sheet</span><i class="fas fa-file-pdf" style="color:var(--accent-green)"></i></div>
            <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>FILES</label><input type="file" name="pdf_files" multiple accept=".pdf" required></div><button style="background:var(--accent-green)">Process</button></form></div>{{% endif %}}
            {{% if 'accessories' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Accessories</span><i class="fas fa-boxes" style="color:var(--accent-purple)"></i></div><p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px;">Manage Challans</p><a href="/admin/accessories"><button style="background:var(--accent-purple)">Open Dashboard</button></a></div>{{% endif %}}
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES PAGES (DARK THEME) WITH HISTORY TABLE
# ==============================================================================

ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html><html lang="en"><head><title>Search</title>{COMMON_STYLES}</head><body style="justify-content:center; align-items:center;">
<div class="card" style="width:100%; max-width:450px; padding:30px;"><div class="section-header" style="justify-content:center; margin-bottom:30px;">Accessories DB</div>
<form action="/admin/accessories/input" method="post"><div class="input-group"><label>BOOKING REFERENCE</label><input type="text" name="ref_no" required></div><button>Proceed</button></form>
<div style="text-align:center; margin-top:20px;"><a href="/" style="color:var(--text-secondary); text-decoration:none; font-size:13px;">&larr; Back</a></div></div></body></html>
"""

# Updated Input Template: Contains Input Form AND Previous Challans Table
ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Input</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="sidebar">
        <div class="brand-logo">Cotton<span>Solutions</span></div>
        <div class="nav-menu"><a href="/admin/accessories" class="nav-link active"><i class="fas fa-arrow-left"></i> Back</a></div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Accessories Entry</div>
                <div style="color:var(--accent-orange); font-weight:700;">{{{{ ref }}}} <span style="color:var(--text-secondary); font-weight:400; margin-left:10px;">{{{{ buyer }}}} | {{{{ style }}}}</span></div>
            </div>
            <a href="/admin/accessories/print?ref={{{{ ref }}}}" target="_blank"><button style="width:auto; padding:10px 20px; background:var(--accent-green);"> <i class="fas fa-print"></i> Print Report</button></a>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">New Challan</div>
                <form action="/admin/accessories/save" method="post">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    <div class="input-group"><label>TYPE</label><select name="item_type"><option value="Top">Top</option><option value="Bottom">Bottom</option></select></div>
                    <div class="input-group"><label>COLOR</label><select name="color" required><option value="" disabled selected>Select</option>{{% for c in colors %}}<option value="{{{{ c }}}}">{{{{ c }}}}</option>{{% endfor %}}</select></div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">
                        <div class="input-group"><label>LINE</label><input type="text" name="line_no" required></div>
                        <div class="input-group"><label>SIZE</label><input type="text" name="size" value="ALL"></div>
                    </div>
                    <div class="input-group"><label>QTY</label><input type="number" name="qty" required></div>
                    <button type="submit">Save Entry</button>
                </form>
            </div>

            <div class="card">
                <div class="section-header">Recent Challans <span style="font-size:12px; color:var(--text-secondary);">{{{{ challans|length }}}} Total</span></div>
                <div style="overflow-y:auto; max-height:400px;">
                    <table class="dark-table">
                        <thead><tr><th>Date</th><th>Line</th><th>Color</th><th>Qty</th><th>Action</th></tr></thead>
                        <tbody>
                            {{% for item in challans|reverse %}}
                            <tr>
                                <td>{{{{ item.date }}}}</td>
                                <td>{{{{ item.line }}}}</td>
                                <td>{{{{ item.color }}}}</td>
                                <td style="font-weight:700;">{{{{ item.qty }}}}</td>
                                <td>
                                    {{% if session.role == 'admin' %}}
                                    <a href="/admin/accessories/edit?ref={{{{ ref }}}}&index={{{{ (challans|length) - loop.index }}}}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                    <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete?');">
                                        <input type="hidden" name="ref" value="{{{{ ref }}}}">
                                        <input type="hidden" name="index" value="{{{{ (challans|length) - loop.index }}}}">
                                        <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                    </form>
                                    {{% endif %}}
                                </td>
                            </tr>
                            {{% else %}}
                            <tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-secondary);">No challans found.</td></tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_EDIT_TEMPLATE = f"""<!doctype html><html lang="en"><head><title>Edit</title>{COMMON_STYLES}</head><body style="justify-content:center; align-items:center;">
<div class="card" style="width:100%; max-width:400px;"><div class="section-header">Edit Entry</div>
<form action="/admin/accessories/update" method="post"><input type="hidden" name="ref" value="{{{{ ref }}}}"><input type="hidden" name="index" value="{{{{ index }}}}">
<div class="input-group"><label>LINE</label><input type="text" name="line_no" value="{{{{ item.line }}}}" required></div>
<div class="input-group"><label>COLOR</label><input type="text" name="color" value="{{{{ item.color }}}}" required></div>
<div class="input-group"><label>SIZE</label><input type="text" name="size" value="{{{{ item.size }}}}" required></div>
<div class="input-group"><label>QTY</label><input type="number" name="qty" value="{{{{ item.qty }}}}" required></div>
<button type="submit" style="background:var(--accent-purple)">Update</button></form>
<div style="text-align:center; margin-top:15px;"><a href="/admin/accessories/input_direct?ref={{{{ ref }}}}" style="color:white; font-size:13px; text-decoration:none;">Cancel</a></div></div></body></html>"""

# ==============================================================================
# REPORT TEMPLATES (ORIGINAL WHITE DESIGN - AS REQUESTED)
# ==============================================================================

CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Closing Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #fff; padding: 20px; color: #000; font-family: sans-serif; }
        .container { max-width: 100%; }
        .company-header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .company-name { font-size: 24px; font-weight: 800; text-transform: uppercase; }
        .table th, .table td { border: 1px solid #000 !important; text-align: center; vertical-align: middle; padding: 5px; font-weight: 600; font-size: 14px; }
        .table th { background-color: #eee !important; color: #000; }
        .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
        .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
        .no-print { margin-bottom: 20px; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="no-print text-end">
            <a href="/" class="btn btn-secondary">Back</a>
            <button onclick="window.print()" class="btn btn-primary">Print</button>
            <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-success">Excel</a>
        </div>
        <div class="company-header">
            <div class="company-name">Cotton Clothing BD Limited</div>
            <div>CLOSING REPORT [ INPUT SECTION ]</div>
            <div>Date: <span id="date"></span></div>
        </div>
        {% if report_data %}
        <div style="display:flex; justify-content:space-between; margin-bottom:15px; border:1px solid #000; padding:10px;">
            <div><strong>Buyer:</strong> {{ report_data[0].buyer }} <br> <strong>Style:</strong> {{ report_data[0].style }}</div>
            <div style="text-align:right;"><strong>IR/IB NO:</strong> {{ ref_no }}</div>
        </div>
        {% for block in report_data %}
        <div style="margin-bottom:20px;">
            <div style="background:#333; color:white; padding:5px; font-weight:bold; -webkit-print-color-adjust: exact;">COLOR: {{ block.color }}</div>
            <table class="table table-sm">
                <thead>
                    <tr><th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th><th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th></tr>
                </thead>
                <tbody>
                    {% for i in range(block.headers|length) %}
                        {% set actual = block.gmts_qty[i]|replace(',', '')|int %}
                        {% set qty_3 = (actual * 1.03)|round|int %}
                        {% set cut_qc = block.cutting_qc[i]|replace(',', '')|int if i < block.cutting_qc|length else 0 %}
                        {% set inp_qty = block.sewing_input[i]|replace(',', '')|int if i < block.sewing_input|length else 0 %}
                        <tr>
                            <td>{{ block.headers[i] }}</td>
                            <td class="col-3pct">{{ qty_3 }}</td>
                            <td>{{ actual }}</td>
                            <td>{{ cut_qc }}</td>
                            <td class="col-input">{{ inp_qty }}</td>
                            <td>{{ cut_qc - inp_qty }}</td>
                            <td>{{ inp_qty - qty_3 }}</td>
                            <td>{{ "%.2f"|format((inp_qty - qty_3)/qty_3*100) if qty_3 > 0 else 0 }}%</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        {% endif %}
    </div>
    <script>document.getElementById('date').innerText = new Date().toLocaleDateString('en-GB');</script>
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
        body { background: #fff; padding: 20px; font-family: 'Courier New', monospace; color: #000; }
        .container { border: 2px solid #000; padding: 20px; max-width: 800px; margin: 0 auto; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .title { font-size: 20px; font-weight: 900; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .table th, .table td { border: 1px solid #000; padding: 5px; text-align: center; }
        .table th { background: #ddd; -webkit-print-color-adjust: exact; }
        .no-print { text-align: right; margin-bottom: 20px; }
        @media print { .no-print { display: none; } .container { border: none; } }
    </style>
</head>
<body>
    <div class="no-print">
        <a href="/admin/accessories" style="margin-right:10px;">Back</a>
        <form action="/admin/accessories/input" method="post" style="display:inline;">
            <input type="hidden" name="ref_no" value="{{ ref }}">
            <button>Add New</button>
        </form>
        <button onclick="window.print()">Print</button>
    </div>
    <div class="container">
        <div class="header">
            <div class="title">ACCESSORIES DELIVERY CHALLAN</div>
            <div>Cotton Clothing BD Limited</div>
        </div>
        <div class="info-grid">
            <div>
                <strong>Booking:</strong> {{ ref }}<br>
                <strong>Buyer:</strong> {{ buyer }}<br>
                <strong>Style:</strong> {{ style }}
            </div>
            <div style="text-align:right;">
                <strong>Date:</strong> {{ today }}<br>
                <strong>Item:</strong> {{ item_type if item_type else 'General' }}
            </div>
        </div>
        <table class="table">
            <thead>
                <tr><th>DATE</th><th>LINE</th><th>COLOR</th><th>SIZE</th><th>QTY</th>
                {% if session.role == 'admin' %}<th class="no-print">ACTION</th>{% endif %}
                </tr>
            </thead>
            <tbody>
                {% set ns = namespace(total=0) %}
                {% for item in challans %}
                {% set ns.total = ns.total + item.qty|int %}
                <tr>
                    <td>{{ item.date }}</td>
                    <td>{{ item.line }}</td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td>{{ item.qty }}</td>
                    {% if session.role == 'admin' %}
                    <td class="no-print">
                        <a href="/admin/accessories/edit?ref={{ ref }}&index={{ loop.index0 }}">Edit</a>
                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Del?');">
                            <input type="hidden" name="ref" value="{{ ref }}">
                            <input type="hidden" name="index" value="{{ loop.index0 }}">
                            <button type="submit">Del</button>
                        </form>
                    </td>
                    {% endif %}
                </tr>
                {% endfor %}
                <tr style="font-weight:bold; background:#eee;">
                    <td colspan="4">TOTAL</td>
                    <td>{{ ns.total }}</td>
                    {% if session.role == 'admin' %}<td class="no-print"></td>{% endif %}
                </tr>
            </tbody>
        </table>
        <div style="margin-top: 50px; display: flex; justify-content: space-between;">
            <div style="border-top:1px solid #000; width:150px; text-align:center;">Received By</div>
            <div style="border-top:1px solid #000; width:150px; text-align:center;">Authorized By</div>
        </div>
    </div>
</body>
</html>
"""

PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PO Summary</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 20px; background: white; color: black; }
        .header { text-align: center; border-bottom: 2px solid #000; margin-bottom: 20px; }
        .table th { background: #333 !important; color: white !important; -webkit-print-color-adjust: exact; }
        .summary-row { background: #d1ecff !important; font-weight: bold; -webkit-print-color-adjust: exact; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="no-print mb-3">
            <a href="/" class="btn btn-secondary">Back</a>
            <button onclick="window.print()" class="btn btn-primary">Print</button>
        </div>
        <div class="header">
            <h3>Cotton Clothing BD Limited</h3>
            <h5>Purchase Order Summary</h5>
        </div>
        {% if tables %}
            <div class="row mb-3 border p-2">
                <div class="col-md-4"><strong>Buyer:</strong> {{ meta.buyer }}</div>
                <div class="col-md-4"><strong>Booking:</strong> {{ meta.booking }}</div>
                <div class="col-md-4"><strong>Total Qty:</strong> {{ grand_total }}</div>
            </div>
            {% for item in tables %}
                <div class="mb-4">
                    <h5 style="background:#eee; padding:5px; border:1px solid #000;">COLOR: {{ item.color }}</h5>
                    {{ item.table | safe }}
                </div>
            {% endfor %}
        {% endif %}
    </div>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTES (CONTROLLER LOGIC)
# ==============================================================================

@app.route('/')
def index():
    load_users() # Ensure users exist
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
        
        # Login Time Tracking
        now = get_bd_time()
        session['login_start'] = now.isoformat()
        
        users_db[username]['last_login'] = now.strftime('%I:%M %p, %d %b')
        save_users(users_db)
        
        return redirect(url_for('index'))
    else:
        flash('Invalid Username or Password.')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    if session.get('logged_in') and 'login_start' in session:
        try:
            start_time = datetime.fromisoformat(session['login_start'])
            end_time = get_bd_time()
            duration = end_time - start_time
            minutes = int(duration.total_seconds() / 60)
            dur_str = f"{minutes} mins" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"

            username = session.get('user')
            users_db = load_users()
            if username in users_db:
                users_db[username]['last_duration'] = dur_str
                save_users(users_db)
        except: pass

    session.clear()
    flash('Session terminated.')
    return redirect(url_for('index'))

# --- USER MANAGEMENT ROUTES ---
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
        users_db[username] = {
            "password": password, "role": "user", "permissions": permissions,
            "created_at": get_bd_date_str(), "last_login": "Never", "last_duration": "N/A"
        }
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

# --- CLOSING REPORT ROUTES ---
@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    internal_ref_no = request.form['ref_no']
    if not internal_ref_no: return redirect(url_for('index'))

    report_data = fetch_closing_report_data(internal_ref_no)

    if not report_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))
    
    update_stats(internal_ref_no, session.get('user', 'Unknown'))
    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    internal_ref_no = request.args.get('ref_no')
    
    report_data = fetch_closing_report_data(internal_ref_no)
    if report_data:
        excel_file = create_formatted_excel_report(report_data, internal_ref_no)
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        return make_response(send_file(
            excel_file, as_attachment=True, 
            download_name=f"Report-{internal_ref_no.replace('/', '_')}.xlsx", 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
    return redirect(url_for('index'))

# --- ACCESSORIES ROUTES (FIXED: SHOW HISTORY BELOW INPUT) ---
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
    
    # ref_no রিসিভ করা (form থেকে বা args থেকে - এডিট ক্যানসেল করলে args থেকে আসবে)
    ref_no = request.form.get('ref_no') or request.args.get('ref')
    if ref_no: ref_no = ref_no.strip().upper()
    
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db_acc = load_accessories_db()

    # ডাটাবেসে থাকলে লোড করুন, না থাকলে ERP থেকে আনুন
    if ref_no in db_acc:
        data = db_acc[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
        challans = data['challans'] # হিস্ট্রি দেখানোর জন্য
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"Booking not found: {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        challans = []
        
        db_acc[ref_no] = {
            "style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": challans
        }
        save_accessories_db(db_acc)

    # challans লিস্ট টেমপ্লেটে পাঠানো হচ্ছে যাতে নিচে টেবিল শো করে
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer, challans=challans)

# ডাইরেক্ট ইনপুট পেজে যাওয়ার জন্য (এডিট ক্যানসেল করার পর)
@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    return accessories_input_page() 

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.form.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref in db_acc:
        if request.form.get('item_type'): db_acc[ref]['item_type'] = request.form.get('item_type')
        
        new_entry = {
            "date": get_bd_date_str(),
            "line": request.form.get('line_no'),
            "color": request.form.get('color'),
            "size": request.form.get('size'),
            "qty": request.form.get('qty')
        }
        db_acc[ref]['challans'].append(new_entry)
        save_accessories_db(db_acc)
    
    # সেভ করার পর রিপোর্ট পেজে পাঠানো হবে (আপনার অরিজিনাল ফ্লো অনুযায়ী)
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.args.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref not in db_acc: return redirect(url_for('accessories_search_page'))
    
    data = db_acc[ref]
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref, buyer=data['buyer'], style=data['style'],
                                  item_type=data.get('item_type', ''), challans=data['challans'],
                                  today=get_bd_date_str())

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.args.get('ref')
    try: index = int(request.args.get('index'))
    except: return redirect(url_for('accessories_search_page'))
    
    db_acc = load_accessories_db()
    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        item = db_acc[ref]['challans'][index]
        # এডিট পেজে পাঠানো
        return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db_acc = load_accessories_db()

    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        db_acc[ref]['challans'][index]['line'] = request.form.get('line_no')
        db_acc[ref]['challans'][index]['color'] = request.form.get('color')
        db_acc[ref]['challans'][index]['size'] = request.form.get('size')
        db_acc[ref]['challans'][index]['qty'] = request.form.get('qty')
        save_accessories_db(db_acc)
    
    # আপডেট শেষে আবার ইনপুট পেজে ফেরত পাঠানো (যাতে হিস্ট্রি দেখা যায়)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db_acc = load_accessories_db()

    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        del db_acc[ref]['challans'][index]
        save_accessories_db(db_acc)
    
    # ডিলিট শেষে ইনপুট পেজে ফেরত (হিস্ট্রি আপডেট হবে)
    return redirect(url_for('accessories_input_direct', ref=ref))

# --- PO SHEET ROUTE (ORIGINAL LOGIC PRESERVED) ---
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    uploaded_files = request.files.getlist('pdf_files')
    all_data = []
    final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A'}
    
    for file in uploaded_files:
        if file.filename == '': continue
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        data, meta = extract_data_dynamic(file_path)
        if meta['buyer'] != 'N/A': final_meta = meta
        if data: all_data.extend(data)
    
    if not all_data:
        return render_template_string(PO_REPORT_TEMPLATE, tables=None)

    update_po_stats(session.get('user', 'Unknown'), len(uploaded_files))

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

        actual = pivot.sum()
        plus_3 = (actual * 1.03).round().astype(int)
        
        pivot.loc['Actual Qty'] = actual
        pivot.loc['3% Order Qty'] = plus_3
        
        pivot = pivot.reset_index()
        html_table = pivot.to_html(classes='table table-bordered table-striped', index=False)
        html_table = html_table.replace('<td>Actual Qty</td>', '<td class="summary-row">Actual Qty</td>')
        html_table = html_table.replace('<td>3% Order Qty</td>', '<td class="summary-row">3% Order Qty</td>')

        final_tables.append({'color': color, 'table': html_table})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
