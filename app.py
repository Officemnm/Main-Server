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

# --- টাইমজোন কনফিগারেশন (বাংলাদেশ) ---
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

        /* Sidebar - Perfected Layout */
        .sidebar {
            width: 260px; height: 100vh; background-color: var(--bg-sidebar);
            position: fixed; top: 0; left: 0; display: flex; flex-direction: column;
            padding: 30px 20px; border-right: 1px solid var(--border-color); z-index: 1000;
            transition: 0.3s;
        }
        .brand-logo { font-size: 24px; font-weight: 800; color: white; margin-bottom: 40px; display: flex; align-items: center; gap: 10px; }
        .brand-logo span { color: var(--accent-orange); }
        
        .nav-menu { flex-grow: 1; display: flex; flex-direction: column; gap: 5px; }

        .nav-link {
            display: flex; align-items: center; padding: 14px 16px; color: var(--text-secondary);
            text-decoration: none; border-radius: 10px; transition: 0.3s;
            cursor: pointer; font-weight: 500; font-size: 14px; letter-spacing: 0.3px;
        }
        .nav-link:hover, .nav-link.active { 
            background-color: rgba(255, 140, 66, 0.1); 
            color: var(--accent-orange); 
            transform: translateX(5px);
        }
        .nav-link i { width: 24px; margin-right: 12px; font-size: 18px; text-align: center; }

        .sidebar-footer {
            margin-top: auto; padding-top: 20px; border-top: 1px solid var(--border-color);
            text-align: center; font-size: 12px; color: var(--text-secondary); font-weight: 500; opacity: 0.7;
        }

        /* Main Content */
        .main-content { margin-left: 260px; width: calc(100% - 260px); padding: 40px; }
        .header-section { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 35px; }
        .page-title { font-size: 28px; font-weight: 700; color: white; margin-bottom: 5px; letter-spacing: -0.5px; }
        .page-subtitle { color: var(--text-secondary); font-size: 14px; }

        /* Cards & Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 25px; margin-bottom: 35px; }
        .dashboard-grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 25px; margin-bottom: 25px; }
        .card { background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--card-radius); padding: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
        
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; font-size: 16px; font-weight: 600; color: white; border-bottom: 1px solid var(--border-color); padding-bottom: 15px; }

        .stat-card { display: flex; align-items: center; gap: 25px; transition: transform 0.3s ease; }
        .stat-card:hover { transform: translateY(-5px); border-color: var(--accent-orange); }
        .stat-icon { width: 60px; height: 60px; background: rgba(255,255,255,0.05); border-radius: 12px; display: flex; justify-content: center; align-items: center; font-size: 24px; color: var(--text-secondary); transition: 0.3s; }
        .stat-card:hover .stat-icon { background: var(--accent-orange); color: white; }
        
        .stat-info h3 { font-size: 28px; font-weight: 800; margin: 0; color: white; line-height: 1.2; }
        .stat-info p { font-size: 13px; color: var(--text-secondary); margin: 0; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }

        /* Forms */
        .input-group { margin-bottom: 20px; }
        .input-group label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; }
        input, select { width: 100%; padding: 14px; background: #262626; border: 1px solid #333; border-radius: 10px; color: white; font-size: 14px; outline: none; transition: 0.3s; }
        input:focus, select:focus { border-color: var(--accent-orange); background: #2D2D2D; box-shadow: 0 0 0 2px rgba(255, 140, 66, 0.1); }
        
        button { width: 100%; padding: 14px; background: var(--accent-orange); color: white; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; transition: 0.3s; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        button:hover { background: #e67e22; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(230, 126, 34, 0.3); }

        /* Tables */
        .dark-table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 10px; }
        .dark-table th { text-align: left; padding: 15px; color: var(--text-secondary); font-size: 12px; font-weight: 700; text-transform: uppercase; border-bottom: 1px solid #333; letter-spacing: 0.5px; }
        .dark-table td { padding: 15px; color: white; font-size: 14px; border-bottom: 1px solid #2D2D2D; vertical-align: middle; }
        .dark-table tr:last-child td { border-bottom: none; }
        .dark-table tr:hover td { background: rgba(255,255,255,0.03); }
        
        .action-btn { padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; margin-right: 8px; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; border: none; transition: 0.2s; }
        .btn-edit { background: rgba(108, 92, 231, 0.15); color: var(--accent-purple); }
        .btn-edit:hover { background: var(--accent-purple); color: white; }
        .btn-del { background: rgba(255, 118, 117, 0.15); color: var(--accent-red); }
        .btn-del:hover { background: var(--accent-red); color: white; }

        /* Loading */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 9999; flex-direction: column; justify-content: center; align-items: center; backdrop-filter: blur(5px); }
        .spinner { width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid var(--accent-orange); border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* Mobile */
        .mobile-toggle { display: none; position: fixed; top: 20px; right: 20px; z-index: 2000; color: white; background: #333; padding: 10px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        @media (max-width: 900px) {
            .sidebar { transform: translateX(-100%); box-shadow: 5px 0 15px rgba(0,0,0,0.5); } 
            .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; padding: 20px; padding-top: 70px; }
            .dashboard-grid-2 { grid-template-columns: 1fr; }
            .mobile-toggle { display: block; }
        }
    </style>
"""
# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (MongoDB ব্যবহার করে)
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

# ড্যাশবোর্ড সামারি (Admin Dashboard এর জন্য ডাটা প্রিপারেশন)
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
    # UPDATED: Using BD Timezone function
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
# HTML TEMPLATES: LOGIN, DASHBOARD & UI (REFINED DARK THEME)
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
        <div style="text-align: center; margin-bottom: 40px;">
            <div style="font-size: 26px; font-weight: 800; color: white; letter-spacing: -0.5px;">MNM<span style="color:var(--accent-orange)">Development</span></div>
            <div style="color: var(--text-secondary); font-size: 12px; letter-spacing: 2px; margin-top: 5px; font-weight: 600;">SECURE ACCESS</div>
        </div>
        <form action="/login" method="post">
            <div class="input-group">
                <label><i class="fas fa-user" style="margin-right:5px;"></i> USERNAME</label>
                <input type="text" name="username" required placeholder="Enter your ID">
            </div>
            <div class="input-group">
                <label><i class="fas fa-lock" style="margin-right:5px;"></i> PASSWORD</label>
                <input type="password" name="password" required placeholder="Enter your Password">
            </div>
            <button type="submit" style="margin-top: 10px;">Sign In <i class="fas fa-arrow-right" style="margin-left:5px;"></i></button>
        </form>
        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div style="margin-top: 25px; color: #ff7675; font-size: 13px; text-align: center; background: rgba(255, 118, 117, 0.1); padding: 10px; border-radius: 8px; border: 1px solid rgba(255, 118, 117, 0.2);"><i class="fas fa-exclamation-circle"></i> {{{{ messages[0] }}}}</div>
            {{% endif %}}
        {{% endwith %}}
        <div style="text-align: center; margin-top: 30px; color: var(--text-secondary); font-size: 12px; opacity: 0.6;">
            © Mehedi Hasan
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
    <title>Admin Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay"><div class="spinner"></div><div style="color:white; margin-top:15px; font-weight:600;">Processing...</div></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Development</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            <div class="nav-link" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-database"></i> Accessories DB</a>
            <div class="nav-link" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            <div class="nav-link" onclick="showSection('settings', this)"><i class="fas fa-users-cog"></i> User Manage</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 10px;"><i class="fas fa-sign-out-alt"></i> Log Out</a>
        </div>
        <div class="sidebar-footer">© Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div id="section-dashboard">
            <div class="header-section">
                <div><div class="page-title">Main Dashboard</div><div class="page-subtitle">Overview & Statistics</div></div>
                <div style="background:var(--bg-card); padding:10px 20px; border-radius:30px; border:1px solid var(--border-color); font-size:13px; font-weight:600; display:flex; align-items:center; gap:8px;"><span style="color:var(--accent-green); font-size:10px;">●</span> System Online</div>
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
                    <div class="section-header"><span>Module Usage</span></div>
                    <div class="progress-item" style="margin-bottom: 20px;"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>Closing Report</span><span style="color:var(--text-secondary);">High</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 85%; height:100%; background:var(--accent-orange); border-radius:3px;"></div></div></div>
                    <div class="progress-item" style="margin-bottom: 20px;"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>Accessories</span><span style="color:var(--text-secondary);">Medium</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 60%; height:100%; background:var(--accent-purple); border-radius:3px;"></div></div></div>
                    <div class="progress-item"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>PO Generator</span><span style="color:var(--text-secondary);">Normal</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 45%; height:100%; background:var(--accent-green); border-radius:3px;"></div></div></div>
                </div>
            </div>

            <div class="card">
                <div class="section-header"><span>Recent Activity Log</span><i class="fas fa-history" style="color:var(--text-secondary)"></i></div>
                <div style="overflow-x: auto;">
                    <table class="dark-table">
                        <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Reference / Type</th></tr></thead>
                        <tbody>
                            {{% for log in stats.history %}}
                            <tr>
                                <td><i class="far fa-clock" style="margin-right:5px; color:var(--text-secondary);"></i> {{{{ log.time }}}}</td>
                                <td style="font-weight:600; color:white;">{{{{ log.user }}}}</td>
                                <td><span style="background:rgba(255,255,255,0.05); padding:4px 10px; border-radius:4px; font-size:11px;">{{{{ log.type }}}}</span></td>
                                <td>{{{{ log.ref if log.ref else '-' }}}}</td>
                            </tr>
                            {{% else %}}
                            <tr><td colspan="4" style="text-align:center; padding:30px; color:var(--text-secondary);">No activity recorded today.</td></tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="section-analytics" style="display:none;">
            <div class="card" style="max-width:500px; margin:0 auto; margin-top:50px;">
                <div class="section-header">Generate Closing Report</div>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>INTERNAL REF NO</label><input type="text" name="ref_no" placeholder="e.g. Booking-123" required></div>
                    <button type="submit"><i class="fas fa-magic" style="margin-right:8px;"></i> Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="card" style="max-width:600px; margin:0 auto; margin-top:50px;">
                <div class="section-header">PO Sheet Generator</div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group" style="border: 2px dashed var(--border-color); padding: 40px; text-align: center; border-radius: 12px; transition:0.3s;" onmouseover="this.style.borderColor='var(--accent-orange)'" onmouseout="this.style.borderColor='var(--border-color)'">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display:none;" id="file-upload">
                        <label for="file-upload" style="cursor:pointer; color:var(--accent-orange); margin-bottom:0;"><i class="fas fa-cloud-upload-alt" style="font-size:40px; margin-bottom:15px;"></i><br>Click to Upload PDF Files</label>
                        <div id="file-count" style="margin-top:15px; font-size:13px; color:var(--text-secondary);">No files selected</div>
                    </div>
                    <button type="submit" style="margin-top:25px; background:var(--accent-green);"><i class="fas fa-cogs" style="margin-right:8px;"></i> Process Files</button>
                </form>
            </div>
        </div>

        <div id="section-settings" style="display:none;">
            <div class="dashboard-grid-2">
                <div class="card"><div class="section-header">User Directory</div><div id="userTableContainer">Loading...</div></div>
                <div class="card"><div class="section-header">Manage User</div>
                    <form id="userForm">
                        <input type="hidden" id="action_type" value="create">
                        <div class="input-group"><label>USERNAME</label><input type="text" id="new_username" required></div>
                        <div class="input-group"><label>PASSWORD</label><input type="text" id="new_password" required></div>
                        <div class="input-group"><label>PERMISSIONS</label>
                            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                                <label style="background:#2D2D2D; padding:10px; border-radius:8px; cursor:pointer; display:flex; align-items:center; border:1px solid #333;"><input type="checkbox" id="perm_closing" checked style="width:auto; margin-right:8px;"> Closing</label>
                                <label style="background:#2D2D2D; padding:10px; border-radius:8px; cursor:pointer; display:flex; align-items:center; border:1px solid #333;"><input type="checkbox" id="perm_po" style="width:auto; margin-right:8px;"> PO</label>
                                <label style="background:#2D2D2D; padding:10px; border-radius:8px; cursor:pointer; display:flex; align-items:center; border:1px solid #333;"><input type="checkbox" id="perm_acc" style="width:auto; margin-right:8px;"> Acc</label>
                            </div>
                        </div>
                        <button type="button" onclick="handleUserSubmit()" id="saveUserBtn"><i class="fas fa-save" style="margin-right:8px;"></i> Save User</button>
                        <button type="button" onclick="resetForm()" style="margin-top:10px; background:#2D2D2D; color:white; border:1px solid #333;">Reset Form</button>
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
                let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th>Actions</th></tr></thead><tbody>';
                for(const [u, d] of Object.entries(data)) {{
                    html += `<tr><td>${{u}}</td><td><span style="background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:4px; font-size:11px;">${{d.role}}</span></td><td>${{d.role !== 'admin' ? `<button class="action-btn btn-edit" onclick="editUser('${{u}}', '${{d.password}}', '${{d.permissions.join(',')}}')"><i class="fas fa-edit"></i></button> <button class="action-btn btn-del" onclick="deleteUser('${{u}}')"><i class="fas fa-trash"></i></button>` : '<i class="fas fa-shield-alt" style="color:var(--text-secondary); margin-left:10px;"></i>'}}</td></tr>`;
                }}
                document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
            }});
        }}
        function handleUserSubmit() {{
            const u = document.getElementById('new_username').value, p = document.getElementById('new_password').value, a = document.getElementById('action_type').value;
            let perms = []; ['closing', 'po_sheet', 'accessories'].forEach(id => {{ if(document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked) perms.push(id); }});
            fetch('/admin/save-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u, password: p, permissions: perms, action_type: a }}) }}).then(r => r.json()).then(d => {{ if(d.status === 'success') {{ loadUsers(); resetForm(); }} else alert(d.message); }});
        }}
        function editUser(u, p, permsStr) {{ document.getElementById('new_username').value = u; document.getElementById('new_username').readOnly = true; document.getElementById('new_password').value = p; document.getElementById('action_type').value = 'update'; document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-sync"></i> Update User'; let pArr = permsStr.split(','); ['closing', 'po_sheet', 'accessories'].forEach(id => {{ document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked = pArr.includes(id); }}); }}
        function resetForm() {{ document.getElementById('userForm').reset(); document.getElementById('action_type').value = 'create'; document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-save"></i> Save User'; document.getElementById('new_username').readOnly = false; }}
        function deleteUser(u) {{ if(confirm('Are you sure you want to delete this user?')) fetch('/admin/delete-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u }}) }}).then(() => loadUsers()); }}
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
    <div id="loading-overlay"><div class="spinner"></div><div style="color:white; margin-top:15px; font-weight:600;">Generating...</div></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i>MNM<span>Development</span></div>
        <div class="nav-menu"><div class="nav-link active"><i class="fas fa-home"></i> Home</div></div>
        <a href="/logout" class="nav-link logout-btn" style="color:var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Log Out</a>
        <div class="sidebar-footer">© Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section"><div><div class="page-title">Welcome, {{{{ session.user }}}}</div><div class="page-subtitle">Your assigned production modules.</div></div></div>
        <div class="stats-grid">
            {{% if 'closing' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Closing Report</span><i class="fas fa-file-export" style="color:var(--accent-orange)"></i></div>
            <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>REF NO</label><input type="text" name="ref_no" required placeholder="Booking Ref"></div><button>Generate</button></form></div>{{% endif %}}
            {{% if 'po_sheet' in session.permissions %}}
            <div class="card"><div class="section-header"><span>PO Sheet</span><i class="fas fa-file-pdf" style="color:var(--accent-green)"></i></div>
            <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>FILES</label><input type="file" name="pdf_files" multiple accept=".pdf" required style="padding:10px;"></div><button style="background:var(--accent-green)">Process Files</button></form></div>{{% endif %}}
            {{% if 'accessories' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Accessories</span><i class="fas fa-boxes" style="color:var(--accent-purple)"></i></div><p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px; line-height:1.5;">Manage Challans, entries and history for accessories.</p><a href="/admin/accessories"><button style="background:var(--accent-purple)">Open Dashboard</button></a></div>{{% endif %}}
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html><html lang="en"><head><title>Search</title>{COMMON_STYLES}</head><body style="justify-content:center; align-items:center;">
<div class="card" style="width:100%; max-width:450px; padding:40px;">
    <div class="section-header" style="justify-content:center; margin-bottom:30px; border-bottom:none;">Accessories DB</div>
    <form action="/admin/accessories/input" method="post"><div class="input-group"><label><i class="fas fa-search"></i> BOOKING REFERENCE</label><input type="text" name="ref_no" required placeholder="Enter Booking No"></div><button style="background:var(--accent-purple);">Proceed to Entry <i class="fas fa-arrow-right"></i></button></form>
    <div style="display:flex; justify-content:space-between; margin-top:25px; align-items:center;">
        <a href="/" style="color:var(--text-secondary); text-decoration:none; font-size:13px;"><i class="fas fa-arrow-left"></i> Back to Dashboard</a>
        <a href="/logout" style="color:var(--accent-red); text-decoration:none; font-size:13px; font-weight:600;">Sign Out <i class="fas fa-sign-out-alt"></i></a>
    </div>
    <div style="text-align: center; margin-top: 30px; color: var(--text-secondary); font-size: 11px; opacity: 0.5;">© Mehedi Hasan</div>
</div></body></html>
"""

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
        <div class="brand-logo"><i class="fas fa-boxes"></i> Accessories</div>
        <div class="nav-menu">
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Home</a>
            <a href="/admin/accessories" class="nav-link active"><i class="fas fa-search"></i> Search</a>
            <a href="/logout" class="nav-link" style="color:var(--accent-red); margin-top:10px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer">© Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Accessories Entry</div>
                <div style="color:var(--accent-orange); font-weight:700; font-size:16px;">{{{{ ref }}}} <span style="color:var(--text-secondary); font-weight:400; margin-left:10px; font-size:14px;">{{{{ buyer }}}} | {{{{ style }}}}</span></div>
            </div>
            <a href="/admin/accessories/print?ref={{{{ ref }}}}" target="_blank"><button style="width:auto; padding:12px 25px; background:var(--accent-green);"> <i class="fas fa-print" style="margin-right:8px;"></i> Print Report</button></a>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header"><span>New Challan Entry</span><i class="fas fa-plus-circle" style="color:var(--accent-orange)"></i></div>
                <form action="/admin/accessories/save" method="post">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    <div class="input-group"><label>TYPE</label><select name="item_type"><option value="Top">Top</option><option value="Bottom">Bottom</option></select></div>
                    <div class="input-group"><label>COLOR</label><select name="color" required><option value="" disabled selected>Select Color</option>{{% for c in colors %}}<option value="{{{{ c }}}}">{{{{ c }}}}</option>{{% endfor %}}</select></div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                        <div class="input-group"><label>LINE NO</label><input type="text" name="line_no" required placeholder="Line"></div>
                        <div class="input-group"><label>SIZE</label><input type="text" name="size" value="ALL"></div>
                    </div>
                    <div class="input-group"><label>QUANTITY</label><input type="number" name="qty" required placeholder="0"></div>
                    <button type="submit"><i class="fas fa-save" style="margin-right:8px;"></i> Save Entry</button>
                </form>
            </div>

            <div class="card">
                <div class="section-header">Recent History <span style="background:var(--accent-purple); padding:2px 8px; border-radius:4px; font-size:11px; margin-left:10px;">{{{{ challans|length }}}}</span></div>
                <div style="overflow-y:auto; max-height:450px; padding-right:5px;">
                    <table class="dark-table">
                        <thead><tr><th>Ln</th><th>Color</th><th>Qty</th><th>Act</th></tr></thead>
                        <tbody>
                            {{% for item in challans|reverse %}}
                            <tr>
                                <td>{{{{ item.line }}}}</td>
                                <td>{{{{ item.color }}}}</td>
                                <td style="font-weight:700; color:var(--accent-green);">{{{{ item.qty }}}}</td>
                                <td>
                                    {{% if session.role == 'admin' %}}
                                    <div style="display:flex;">
                                        <a href="/admin/accessories/edit?ref={{{{ ref }}}}&index={{{{ (challans|length) - loop.index }}}}" class="action-btn btn-edit"><i class="fas fa-pen"></i></a>
                                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete this entry?');">
                                            <input type="hidden" name="ref" value="{{{{ ref }}}}">
                                            <input type="hidden" name="index" value="{{{{ (challans|length) - loop.index }}}}">
                                            <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                        </form>
                                    </div>
                                    {{% else %}}<span style="font-size:10px; opacity:0.5;">Locked</span>{{% endif %}}
                                </td>
                            </tr>
                            {{% else %}}
                            <tr><td colspan="4" style="text-align:center; padding:30px; color:var(--text-secondary); font-size:12px;">No challans added yet.</td></tr>
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
<div class="card" style="width:100%; max-width:400px; padding:40px;"><div class="section-header" style="justify-content:center; border-bottom:none; margin-bottom:20px;">Edit Entry</div>
<form action="/admin/accessories/update" method="post"><input type="hidden" name="ref" value="{{{{ ref }}}}"><input type="hidden" name="index" value="{{{{ index }}}}">
<div class="input-group"><label>LINE NO</label><input type="text" name="line_no" value="{{{{ item.line }}}}" required></div>
<div class="input-group"><label>COLOR</label><input type="text" name="color" value="{{{{ item.color }}}}" required></div>
<div class="input-group"><label>SIZE</label><input type="text" name="size" value="{{{{ item.size }}}}" required></div>
<div class="input-group"><label>QUANTITY</label><input type="number" name="qty" value="{{{{ item.qty }}}}" required></div>
<button type="submit" style="background:var(--accent-purple); margin-top:10px;"><i class="fas fa-sync-alt"></i> Update</button></form>
<div style="text-align:center; margin-top:20px;"><a href="/admin/accessories/input_direct?ref={{{{ ref }}}}" style="color:var(--text-secondary); font-size:13px; text-decoration:none;">Cancel</a></div></div></body></html>"""

# ==============================================================================
# REPORT TEMPLATES (ORIGINAL WHITE DESIGN - PRINT FRIENDLY)
# ==============================================================================

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
        .booking-box { background: #2c3e50; color: white; padding: 10px 20px; border-radius: 5px; text-align: right; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); display: flex; flex-direction: column; justify-content: center; min-width: 200px; }
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
        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .summary-header { font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px; text-transform: uppercase; }
        .summary-table { width: 100%; font-size: 13px; font-weight: 700; }
        .summary-table td { padding: 2px 5px; }
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white !important; padding: 10px; border: 1px solid #000; font-size: 14px; text-transform: uppercase; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; vertical-align: middle; color: #000; font-weight: 600; }
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-size: 16px; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff; }
        .line-text-bold { font-size: 14px; font-weight: 800; opacity: 0.7; }
        .status-cell { font-size: 20px; color: green; font-weight: 900; }
        .qty-cell { font-size: 16px; font-weight: 800; }
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; margin: 0 2px; display: inline-block; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }
        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; }
        .btn-add { background: #27ae60; }
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
    <a href="/admin/accessories/input_direct?ref={{ ref }}" class="btn">Back</a>
    <button onclick="window.print()" class="btn">🖨️ Print</button>
</div>
<div class="container">
    <div class="header">
        <div class="company-name">Cotton Clothing BD Limited</div>
        <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
        <div class="report-title">ACCESSORIES DELIVERY CHALLAN</div>
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
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Received By</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Input Incharge</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Store</div>
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
            # ড্যাশবোর্ড ডাটা লোড (চার্ট এবং স্ট্যাটাস এর জন্য)
            stats = get_dashboard_summary_v2()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            # User Dashboard Logic
            perms = session.get('permissions', [])
            if len(perms) == 1 and 'accessories' in perms:
                return redirect(url_for('accessories_search_page'))
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
    
    # Update Stats
    update_stats(internal_ref_no, session.get('user', 'Unknown'))
    
    # Render Preview (Using the White Template from Step 4)
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

# --- ACCESSORIES ROUTES ---
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
    
    # ref_no রিসিভ করা (form থেকে বা args থেকে)
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
        challans = data['challans'] # হিস্ট্রি টেবিলের জন্য ডাটা
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"Booking not found: {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        challans = [] # নতুন এন্ট্রি তাই খালি লিস্ট
        
        db_acc[ref_no] = {
            "style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": challans
        }
        save_accessories_db(db_acc)

    # challans লিস্ট টেমপ্লেটে পাঠানো হচ্ছে যাতে নিচে টেবিল শো করে (Step 3 Template ব্যবহার করে)
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
            "qty": request.form.get('qty'),
            "status": "✔" 
        }
        db_acc[ref]['challans'].append(new_entry)
        save_accessories_db(db_acc)
    
    # সেভ করার পর রিপোর্ট পেজে পাঠানো (অরিজিনাল ডিজাইন)
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.args.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref not in db_acc: return redirect(url_for('accessories_search_page'))
    
    data = db_acc[ref]
    challans = data['challans']
    
    # লাইন সামারি তৈরি (রিপোর্টের জন্য)
    line_summary = {}
    for c in challans:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        line_summary[ln] = line_summary.get(ln, 0) + q
    sorted_line_summary = dict(sorted(line_summary.items()))

    # Render with ORIGINAL White Template from Step 4
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref, buyer=data['buyer'], style=data['style'],
                                  item_type=data.get('item_type', ''), challans=challans,
                                  line_summary=sorted_line_summary, count=len(challans),
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

# --- PO SHEET ROUTE ---
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
        return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found.")

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
        
        # Add summary rows manually for cleaner HTML
        actual_qty = pivot.sum()
        actual_qty.name = 'Actual Qty'
        qty_plus_3 = (actual_qty * 1.03).round().astype(int)
        qty_plus_3.name = '3% Order Qty'
        
        pivot_final = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
        pivot_final = pivot_final.reset_index()
        pivot_final = pivot_final.rename(columns={'index': 'P.O NO'})
        
        pd.set_option('colheader_justify', 'center')
        html_table = pivot_final.to_html(classes='table table-bordered table-striped', index=False, border=0)
        
        # Inject styles for summary rows (Matching Main Code Logic)
        html_table = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', html_table)
        html_table = html_table.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
        html_table = html_table.replace('<td>Total</td>', '<td class="total-col">Total</td>')
        html_table = html_table.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
        html_table = html_table.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
        html_table = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', html_table)

        final_tables.append({'color': color, 'table': html_table})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)

