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

# কনফিগারেশন (PO ফাইলের জন্য)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ২ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

# --- নতুন: টাইমজোন কনফিগারেশন (বাংলাদেশ) ---
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
# DESIGN ASSETS: DARK THEME (Based on your Image)
# ==============================================================================
# এই CSS ভেরিয়েবলটি পুরো সিস্টেমের ডিজাইন চেঞ্জ করে দিবে।
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            /* Image Color Palette */
            --bg-body: #121212;
            --bg-sidebar: #1C1C1E;
            --bg-card: #1F1F23;
            --text-primary: #FFFFFF;
            --text-secondary: #A1A1AA;
            --accent-orange: #FF8C42; /* The orange from the chart/buttons */
            --accent-purple: #6C5CE7;
            --accent-green: #2ECC71;
            --border-color: #2D2D30;
            --card-radius: 12px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        
        body {
            background-color: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            font-size: 14px;
        }

        /* --- Sidebar --- */
        .sidebar {
            width: 260px;
            background-color: var(--bg-sidebar);
            height: 100vh;
            position: fixed;
            top: 0; left: 0;
            padding: 25px 20px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border-color);
            z-index: 100;
        }

        .brand {
            font-size: 20px;
            font-weight: 700;
            color: white;
            margin-bottom: 40px;
            display: flex; align-items: center; gap: 10px;
        }

        .nav-item {
            display: flex; align-items: center;
            padding: 12px 15px;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 8px;
            margin-bottom: 5px;
            transition: all 0.2s ease;
            cursor: pointer;
            font-weight: 500;
        }
        .nav-item:hover, .nav-item.active {
            background-color: #2C2C2E;
            color: white;
        }
        .nav-item i { width: 25px; font-size: 16px; margin-right: 8px; }

        /* --- Main Content --- */
        .main-content {
            margin-left: 260px;
            width: calc(100% - 260px);
            padding: 30px 40px;
        }

        .page-header { margin-bottom: 30px; }
        .page-title { font-size: 24px; font-weight: 700; color: white; margin-bottom: 5px; }
        .page-sub { font-size: 13px; color: var(--text-secondary); }

        /* --- Stats Row (Top 4 Cards) --- */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--bg-card);
            padding: 20px;
            border-radius: var(--card-radius);
            display: flex; align-items: center;
            border: 1px solid var(--border-color);
        }
        .stat-icon {
            width: 45px; height: 45px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            display: flex; justify-content: center; align-items: center;
            margin-right: 15px;
            font-size: 18px; color: var(--text-secondary);
        }
        .stat-info h3 { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
        .stat-info p { font-size: 22px; font-weight: 700; color: white; }

        /* --- Middle Section (Chart + Progress) --- */
        .dashboard-mid-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .content-card {
            background: var(--bg-card);
            padding: 25px;
            border-radius: var(--card-radius);
            border: 1px solid var(--border-color);
        }
        .card-title { font-size: 16px; font-weight: 600; margin-bottom: 20px; color: white; display: flex; justify-content: space-between; }

        /* Progress Bars */
        .progress-row { margin-bottom: 15px; }
        .progress-header { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
        .progress-bar-bg { width: 100%; height: 8px; background: #2D2D30; border-radius: 10px; overflow: hidden; }
        .progress-bar-fill { height: 100%; border-radius: 10px; background: var(--accent-orange); }

        /* --- Bottom Grid --- */
        .bottom-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }

        /* --- Forms & Inputs --- */
        input[type="text"], input[type="password"], input[type="number"], select {
            width: 100%; padding: 12px 15px;
            background: #121212; border: 1px solid #333;
            color: white; border-radius: 8px; margin-bottom: 15px;
            font-size: 14px; outline: none; transition: 0.3s;
        }
        input:focus { border-color: var(--accent-orange); }
        label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; font-weight: 600; }
        
        button {
            width: 100%; padding: 12px;
            background: var(--accent-orange); color: white;
            border: none; border-radius: 8px;
            font-weight: 600; cursor: pointer; transition: 0.3s;
        }
        button:hover { opacity: 0.9; transform: translateY(-2px); }

        /* --- Loading --- */
        #loading-overlay {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.85); z-index: 1000;
            flex-direction: column; justify-content: center; align-items: center;
        }
        .spinner {
            width: 50px; height: 50px; border: 3px solid rgba(255,255,255,0.1);
            border-top: 3px solid var(--accent-orange); border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        @media (max-width: 900px) {
            .sidebar { transform: translateX(-100%); transition: 0.3s; }
            .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; padding: 20px; }
            .dashboard-mid-grid { grid-template-columns: 1fr; }
            .mobile-toggle { display: block; position: fixed; top: 20px; right: 20px; z-index: 200; color: white; font-size: 24px; background: #333; padding: 5px 10px; border-radius: 5px; }
        }
        .mobile-toggle { display: none; }
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
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PDF)
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
# লজিক পার্ট: CLOSING REPORT API & EXCEL GENERATION
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
    <title>Login - CottonSolutions</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center;">
    <div class="card" style="width: 100%; max-width: 400px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="font-size: 24px; font-weight: 700; color: white;">Cotton<span style="color:var(--accent-orange)">Solutions</span></div>
            <div style="color: var(--text-secondary); font-size: 14px;">Secure Gateway</div>
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
                <div style="margin-top: 20px; color: #ff6b6b; font-size: 13px; text-align: center;">{{{{ messages[0] }}}}</div>
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
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div style="color: white; margin-top: 15px;">Processing...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand">
            <div style="width: 30px; height: 30px; background: var(--accent-orange); border-radius: 8px;"></div>
            CMSolutions
        </div>
        <div style="flex-grow: 1;">
            <div class="nav-item active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            <div class="nav-item" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-item"><i class="fas fa-database"></i> Accessories DB</a>
            <div class="nav-item" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Sheet</div>
            <div class="nav-item" onclick="showSection('settings', this)"><i class="fas fa-users-cog"></i> User Manage</div>
        </div>
        <a href="/logout" class="nav-item" style="color: #FF6B6B; margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>

    <div class="main-content">
        <div id="section-dashboard">
            <div class="page-header">
                <div class="page-title">Main Dashboard</div>
                <div class="page-sub">Overview of production & system status</div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info"><h3>Closing Reports</h3><p>{{{{ stats.closing.count }}}}</p></div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-boxes"></i></div>
                    <div class="stat-info"><h3>Accessories</h3><p>{{{{ stats.accessories.count }}}}</p></div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-file-pdf"></i></div>
                    <div class="stat-info"><h3>PO Generated</h3><p>{{{{ stats.po.count }}}}</p></div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-users"></i></div>
                    <div class="stat-info"><h3>Active Users</h3><p>{{{{ stats.users.count }}}}</p></div>
                </div>
            </div>

            <div class="dashboard-mid-grid">
                <div class="content-card">
                    <div class="card-title"><span>Activity Overview</span> <i class="fas fa-chart-line" style="color:var(--accent-orange)"></i></div>
                    <div style="height: 250px;"><canvas id="mainChart"></canvas></div>
                </div>
                <div class="content-card">
                    <div class="card-title"><span>Module Usage</span></div>
                    <div class="progress-row">
                        <div class="progress-header"><span>Closing Report</span><span>High</span></div>
                        <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 85%;"></div></div>
                    </div>
                    <div class="progress-row">
                        <div class="progress-header"><span>Accessories</span><span>Medium</span></div>
                        <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 60%; background: var(--accent-purple);"></div></div>
                    </div>
                    <div class="progress-row">
                        <div class="progress-header"><span>PO Sheet</span><span>Normal</span></div>
                        <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: 45%; background: var(--accent-green);"></div></div>
                    </div>
                </div>
            </div>

            <div class="bottom-grid">
                <div class="content-card">
                    <div class="card-title"><span>Recent History</span></div>
                    <div style="overflow-y: auto; max-height: 200px;">
                        <table style="width:100%;">
                            <thead><tr><th>Time</th><th>User</th><th>Action</th></tr></thead>
                            <tbody>
                                {{% for log in stats.history %}}
                                <tr>
                                    <td>{{{{ log.time }}}}</td>
                                    <td>{{{{ log.user }}}}</td>
                                    <td style="color:var(--accent-orange)">{{{{ log.type }}}}</td>
                                </tr>
                                {{% endfor %}}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div id="section-analytics" style="display:none;">
            <div class="content-card" style="max-width:600px; margin:0 auto;">
                <div class="card-title">Generate Closing Report</div>
                <p style="color:var(--text-secondary); margin-bottom:20px;">Enter Internal Reference No (e.g. DFL/24/...)</p>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>REF NO</label><input type="text" name="ref_no" placeholder="Booking-123" required></div>
                    <button type="submit">Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="content-card" style="max-width:600px; margin:0 auto;">
                <div class="card-title">PO Sheet Generator</div>
                <p style="color:var(--text-secondary); margin-bottom:20px;">Upload Booking PDF & PO PDFs together.</p>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group" style="border: 2px dashed #444; padding: 20px; text-align: center; border-radius: 10px;">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display:none;" id="file-upload">
                        <label for="file-upload" style="cursor:pointer; color:var(--accent-orange); font-size:16px;"><i class="fas fa-cloud-upload-alt"></i> Select Files</label>
                        <div id="file-count" style="margin-top:10px; color:#888;">No files selected</div>
                    </div>
                    <button type="submit" style="margin-top:15px;">Process Files</button>
                </form>
            </div>
        </div>

        <div id="section-settings" style="display:none;">
            <div class="dashboard-mid-grid">
                <div class="content-card">
                    <div class="card-title">User Directory</div>
                    <div id="userTableContainer">Loading...</div>
                </div>
                <div class="content-card">
                    <div class="card-title">Manage User</div>
                    <form id="userForm">
                        <input type="hidden" id="action_type" name="action_type" value="create">
                        <div class="input-group"><label>USERNAME</label><input type="text" id="new_username" name="username" required></div>
                        <div class="input-group"><label>PASSWORD</label><input type="text" id="new_password" name="password" required></div>
                        <div class="input-group">
                            <label>PERMISSIONS</label>
                            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                                <label style="background:#333; padding:5px 10px; border-radius:4px;"><input type="checkbox" name="permissions" value="closing" id="perm_closing" checked> Closing</label>
                                <label style="background:#333; padding:5px 10px; border-radius:4px;"><input type="checkbox" name="permissions" value="po_sheet" id="perm_po"> PO</label>
                                <label style="background:#333; padding:5px 10px; border-radius:4px;"><input type="checkbox" name="permissions" value="accessories" id="perm_acc"> Acc.</label>
                            </div>
                        </div>
                        <div style="display:flex; gap:10px; margin-top:15px;">
                            <button type="button" onclick="handleUserSubmit()" id="saveUserBtn">Save</button>
                            <button type="button" onclick="resetForm()" style="background:#444;">Reset</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showSection(id, el) {{
            ['dashboard','analytics','help','settings'].forEach(s => document.getElementById('section-'+s).style.display='none');
            document.getElementById('section-'+id).style.display='block';
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            if(el) el.classList.add('active');
            if(id === 'settings') loadUsers();
            if(window.innerWidth < 900) document.querySelector('.sidebar').classList.remove('active');
        }}

        // File Upload UI
        document.getElementById('file-upload')?.addEventListener('change', function(){{
            document.getElementById('file-count').innerText = this.files.length + " files selected";
        }});

        // Charts
        const ctx = document.getElementById('mainChart').getContext('2d');
        const grad = ctx.createLinearGradient(0,0,0,300);
        grad.addColorStop(0, 'rgba(255, 140, 66, 0.2)'); grad.addColorStop(1, 'rgba(255, 140, 66, 0)');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: ['Jan','Feb','Mar','Apr','May','Jun'],
                datasets: [{{
                    label: 'Reports', data: [12, 19, 3, 5, 2, 3], borderColor: '#FF8C42', backgroundColor: grad, tension: 0.4, fill: true, pointBackgroundColor:'#121212'
                }}]
            }},
            options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ grid: {{ display: false }} }}, y: {{ grid: {{ color: '#2d2d2d' }} }} }} }}
        }});

        // User Management AJAX
        function loadUsers() {{
            fetch('/admin/get-users').then(r=>r.json()).then(data => {{
                let html = '<table><thead><tr><th>User</th><th>Role</th><th>Action</th></tr></thead><tbody>';
                for(const [u, d] of Object.entries(data)) {{
                    html += `<tr><td>${{u}}</td><td><span style="color:#2ecc71">${{d.role}}</span></td>
                    <td>${{d.role!=='admin'?`<i class="fas fa-edit" style="color:#3498db; cursor:pointer;" onclick="editUser('${{u}}','${{d.password}}','${{d.permissions.join(',')}}')"></i> <i class="fas fa-trash" style="color:#e74c3c; cursor:pointer; margin-left:10px;" onclick="deleteUser('${{u}}')"></i>`:'-'}}</td></tr>`;
                }}
                document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
            }});
        }}
        function handleUserSubmit() {{
            const u = document.getElementById('new_username').value, p = document.getElementById('new_password').value, a = document.getElementById('action_type').value;
            if(!u || !p) return alert('Missing fields');
            let perms = [];
            ['closing','po_sheet','accessories'].forEach(id => {{ if(document.getElementById('perm_'+(id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked) perms.push(id); }});
            fetch('/admin/save-user', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u, password:p, permissions:perms, action_type:a}}) }})
            .then(r=>r.json()).then(d=>{{ if(d.status==='success'){{loadUsers(); resetForm();}} else alert(d.message); }});
        }}
        function editUser(u, p, perms) {{
            document.getElementById('new_username').value=u; document.getElementById('new_username').readOnly=true;
            document.getElementById('new_password').value=p; document.getElementById('action_type').value='update';
            document.getElementById('saveUserBtn').innerText='Update';
            let pArr = perms.split(',');
            ['closing','po_sheet','accessories'].forEach(id => document.getElementById('perm_'+(id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked = pArr.includes(id));
        }}
        function resetForm() {{
            document.getElementById('userForm').reset(); document.getElementById('action_type').value='create';
            document.getElementById('saveUserBtn').innerText='Save'; document.getElementById('new_username').readOnly=false;
        }}
        function deleteUser(u) {{ if(confirm('Delete?')) fetch('/admin/delete-user', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}}) }}).then(()=>loadUsers()); }}
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
        <div class="brand"><div style="width:30px; height:30px; background:var(--accent-orange); border-radius:8px;"></div>CMS</div>
        <div class="nav-item active"><i class="fas fa-home"></i> Home</div>
        <a href="/logout" class="nav-item" style="color:#FF6B6B; margin-top:20px;"><i class="fas fa-sign-out-alt"></i> Log Out</a>
    </div>
    <div class="main-content">
        <div class="page-header">
            <div class="page-title">Welcome, {{{{ session.user }}}}</div>
            <div class="page-sub">Select a module to proceed</div>
        </div>
        <div class="stats-grid">
            {{% if 'closing' in session.permissions %}}
            <div class="content-card">
                <div class="card-title">Closing Report</div>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>REF NO</label><input type="text" name="ref_no" required></div>
                    <button type="submit">Generate</button>
                </form>
            </div>
            {{% endif %}}
            {{% if 'po_sheet' in session.permissions %}}
            <div class="content-card">
                <div class="card-title">PO Sheet</div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>FILES</label><input type="file" name="pdf_files" multiple accept=".pdf" required></div>
                    <button type="submit" style="background:var(--accent-green)">Process</button>
                </form>
            </div>
            {{% endif %}}
            {{% if 'accessories' in session.permissions %}}
            <div class="content-card">
                <div class="card-title">Accessories</div>
                <p style="color:#888; margin-bottom:15px;">Manage Challans</p>
                <a href="/admin/accessories"><button style="background:var(--accent-purple)">Open Dashboard</button></a>
            </div>
            {{% endif %}}
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
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Acc. Search</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center;">
    <div class="content-card" style="width:100%; max-width:450px;">
        <div class="card-title" style="justify-content:center;">Accessories DB</div>
        <form action="/admin/accessories/input" method="post">
            <div class="input-group"><label>BOOKING REF</label><input type="text" name="ref_no" required></div>
            <button type="submit">Proceed</button>
        </form>
        <div style="margin-top:20px; text-align:center;">
            <a href="/" style="color:var(--text-secondary); font-size:12px;">Back to Home</a>
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
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Challan</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center; padding:20px;">
    <div class="content-card" style="width:100%; max-width:500px;">
        <div class="card-title">New Challan Entry</div>
        <div style="background:#2d2d2d; padding:15px; border-radius:8px; margin-bottom:20px;">
            <div style="font-size:16px; font-weight:700;">{{{{ ref }}}}</div>
            <div style="font-size:12px; color:#888;">{{{{ buyer }}}} | {{{{ style }}}}</div>
        </div>
        <form action="/admin/accessories/save" method="post">
            <input type="hidden" name="ref" value="{{{{ ref }}}}">
            <div class="input-group"><label>TYPE</label><select name="item_type"><option value="Top">Top</option><option value="Bottom">Bottom</option></select></div>
            <div class="input-group"><label>COLOR</label><select name="color" required><option value="" disabled selected>Select</option>{{% for c in colors %}}<option value="{{{{ c }}}}">{{{{ c }}}}</option>{{% endfor %}}</select></div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                <div class="input-group"><label>LINE</label><input type="text" name="line_no" required></div>
                <div class="input-group"><label>SIZE</label><input type="text" name="size" value="ALL"></div>
            </div>
            <div class="input-group"><label>QTY</label><input type="number" name="qty" required></div>
            <button type="submit">Save</button>
        </form>
        <div style="text-align:center; margin-top:15px;"><a href="/admin/accessories" style="color:#888; font-size:12px;">Cancel</a></div>
    </div>
</body>
</html>
"""

ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Challan</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center;">
    <div class="content-card" style="width:100%; max-width:400px;">
        <div class="card-title">Edit Entry</div>
        <form action="/admin/accessories/update" method="post">
            <input type="hidden" name="ref" value="{{{{ ref }}}}">
            <input type="hidden" name="index" value="{{{{ index }}}}">
            <div class="input-group"><label>LINE</label><input type="text" name="line_no" value="{{{{ item.line }}}}" required></div>
            <div class="input-group"><label>COLOR</label><input type="text" name="color" value="{{{{ item.color }}}}" required></div>
            <div class="input-group"><label>SIZE</label><input type="text" name="size" value="{{{{ item.size }}}}" required></div>
            <div class="input-group"><label>QTY</label><input type="number" name="qty" value="{{{{ item.qty }}}}" required></div>
            <button type="submit">Update</button>
        </form>
        <div style="text-align:center; margin-top:15px;"><a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:#888; font-size:12px;">Cancel</a></div>
    </div>
</body>
</html>
"""

# ==============================================================================
# PRINT TEMPLATES (ORIGINAL WHITE) - NO CHANGES
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
                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete?');">
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
# FLASK ROUTES (MAIN CONTROLLER LOGIC)
# ==============================================================================

@app.route('/')
def index():
    load_users() # Ensure users exist
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
            # নতুন ড্যাশবোর্ড লজিক কল করা হচ্ছে
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
        
        # --- Login Time Tracking (BD Time) ---
        now = get_bd_time()
        session['login_start'] = now.isoformat()
        
        # Update User in DB
        users_db[username]['last_login'] = now.strftime('%I:%M %p, %d %b')
        save_users(users_db)
        
        return redirect(url_for('index'))
    else:
        flash('Incorrect Username or Password.')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    # --- Duration Calculation ---
    if session.get('logged_in') and 'login_start' in session:
        try:
            start_time = datetime.fromisoformat(session['login_start'])
            end_time = get_bd_time()
            duration = end_time - start_time
            
            minutes = int(duration.total_seconds() / 60)
            if minutes < 60:
                dur_str = f"{minutes} mins"
            else:
                dur_str = f"{minutes // 60}h {minutes % 60}m"

            username = session.get('user')
            users_db = load_users()
            if username in users_db:
                users_db[username]['last_duration'] = dur_str
                save_users(users_db)
        except:
            pass

    session.clear()
    flash('Session terminated.')
    return redirect(url_for('index'))

# --- USER MANAGEMENT API ---
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
            "permissions": permissions,
            "created_at": get_bd_date_str(), # Save Creation Date
            "last_login": "Never",
            "last_duration": "N/A"
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
    
    internal_ref_no = request.form['ref_no']
    if not internal_ref_no: return redirect(url_for('index'))

    # লজিক ফাংশন কল করা হচ্ছে (Part 2 তে ডিফাইন করা)
    report_data = fetch_closing_report_data(internal_ref_no)

    if not report_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))
    
    # স্ট্যাটাস আপডেট
    update_stats(internal_ref_no, session.get('user', 'Unknown'))

    return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)

# --- ACCESSORIES ROUTES ---

@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    # Check permissions
    if 'accessories' not in session.get('permissions', []):
        flash("You do not have permission to access Accessories Dashboard.")
        return redirect(url_for('index'))
        
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no').strip().upper()
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db_acc = load_accessories_db()

    if ref_no in db_acc:
        data = db_acc[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
    else:
        # ERP থেকে ডাটা ফেচ করা
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"No booking data found for {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        
        db_acc[ref_no] = {
            "style": style,
            "buyer": buyer,
            "colors": colors,
            "item_type": "", 
            "challans": [] 
        }
        save_accessories_db(db_acc)

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer)

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if 'accessories' not in session.get('permissions', []):
        flash("Permission Denied")
        return redirect(url_for('index'))

    ref = request.form.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref not in db_acc:
        flash("Session Error. Please search again.")
        return redirect(url_for('accessories_search_page'))

    if request.form.get('item_type'): 
        db_acc[ref]['item_type'] = request.form.get('item_type')

    # Mark previous as checked (অরিজিনাল লজিক)
    for item in db_acc[ref]['challans']: 
        item['status'] = "✔"
    
    new_entry = {
        "date": get_bd_date_str(), # Using BD Date
        "line": request.form.get('line_no'),
        "color": request.form.get('color'),
        "size": request.form.get('size'),
        "qty": request.form.get('qty'),
        "status": "" 
    }
    
    db_acc[ref]['challans'].append(new_entry)
    save_accessories_db(db_acc)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.args.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref not in db_acc: return redirect(url_for('accessories_search_page'))
    
    data = db_acc[ref]
    challans = data['challans']
    item_type = data.get('item_type', '')

    line_summary = {}
    for c in challans:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        line_summary[ln] = line_summary.get(ln, 0) + q
    
    sorted_line_summary = dict(sorted(line_summary.items()))

    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref,
                                  buyer=data['buyer'],
                                  style=data['style'],
                                  item_type=item_type,
                                  challans=challans,
                                  line_summary=sorted_line_summary,
                                  count=len(challans),
                                  today=get_bd_date_str())

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if session.get('role') != 'admin':
        flash("Only Admin can delete records.")
        return redirect(url_for('index'))
    
    ref = request.form.get('ref').strip().upper()
    try: index = int(request.form.get('index'))
    except: return redirect(url_for('accessories_search_page'))

    db_acc = load_accessories_db()
    if ref in db_acc:
        if 0 <= index < len(db_acc[ref]['challans']):
            del db_acc[ref]['challans'][index]
            save_accessories_db(db_acc)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in'): return redirect(url_for('index'))

    if session.get('role') != 'admin':
        flash("Only Admin can edit records.")
        return redirect(url_for('index'))
    
    ref = request.args.get('ref').strip().upper()
    try: index = int(request.args.get('index'))
    except: return redirect(url_for('accessories_search_page'))
        
    db_acc = load_accessories_db()
    if ref not in db_acc: return redirect(url_for('accessories_search_page'))
    
    if index < 0 or index >= len(db_acc[ref]['challans']):
         return redirect(url_for('accessories_print_view', ref=ref))
         
    item_to_edit = db_acc[ref]['challans'][index]
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item_to_edit)

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    if session.get('role') != 'admin':
        return redirect(url_for('index'))

    ref = request.form.get('ref').strip().upper()
    try:
        index = int(request.form.get('index'))
        qty = request.form.get('qty')
        line = request.form.get('line_no')
        color = request.form.get('color')
        size = request.form.get('size')
    except: return redirect(url_for('accessories_search_page'))

    db_acc = load_accessories_db()
    if ref in db_acc:
        if 0 <= index < len(db_acc[ref]['challans']):
            db_acc[ref]['challans'][index]['qty'] = qty
            db_acc[ref]['challans'][index]['line'] = line
            db_acc[ref]['challans'][index]['color'] = color
            db_acc[ref]['challans'][index]['size'] = size
            save_accessories_db(db_acc)
            
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
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        return make_response(send_file(
            excel_file_stream, 
            as_attachment=True, 
            download_name=f"Closing-Report-{internal_ref_no.replace('/', '_')}.xlsx", 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
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
        # এখানে টেমপ্লেট রেন্ডার হবে মেসেজ সহ
        return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO table data found in files.")

    # Update PO Stats
    update_po_stats(session.get('user', 'Unknown'), len(uploaded_files))

    # PANDAS PIVOT LOGIC (HUNDRED PERCENT ORIGINAL)
    df = pd.DataFrame(all_data)
    df['Color'] = df['Color'].str.strip()
    df = df[df['Color'] != ""]
    unique_colors = df['Color'].unique()
    
    final_tables = []
    grand_total_qty = 0

    for color in unique_colors:
        color_df = df[df['Color'] == color]
        pivot = color_df.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        
        # Sort Columns
        existing_sizes = pivot.columns.tolist()
        sorted_sizes = sort_sizes(existing_sizes)
        pivot = pivot[sorted_sizes]
        
        # Calculate Row Totals
        pivot['Total'] = pivot.sum(axis=1)
        grand_total_qty += pivot['Total'].sum()

        # Calculate Summary Rows
        actual_qty = pivot.sum()
        actual_qty.name = 'Actual Qty'
        qty_plus_3 = (actual_qty * 1.03).round().astype(int)
        qty_plus_3.name = '3% Order Qty'
        
        # Add Summary Rows to DataFrame
        pivot = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
        pivot = pivot.reset_index()
        pivot = pivot.rename(columns={'index': 'P.O NO'})
        pivot.columns.name = None

        # Convert to HTML with Classes
        pd.set_option('colheader_justify', 'center')
        table_html = pivot.to_html(classes='table table-bordered table-striped', index=False, border=0)
        
        # HTML Injections for Styling (অরিজিনাল কোডের মতো হুবহু)
        table_html = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', table_html)
        table_html = table_html.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
        table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        table_html = table_html.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
        table_html = table_html.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
        table_html = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', table_html)

        final_tables.append({'color': color, 'table': table_html})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
