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
import uuid

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

# সেশন টাইমআউট কনফিগারেশন (2 মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) # কাজের সুবিধার্থে বাড়িয়ে ৩০ মিনিট করা হলো

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
# MongoDB কানেকশন সেটআপ (Store এর জন্য নতুন কালেকশন যুক্ত করা হয়েছে)
# ==============================================================================
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/?appName=Office"

try:
    client = MongoClient(MONGO_URI)
    db = client['office_db']
    
    users_col = db['users']
    stats_col = db['stats']
    accessories_col = db['accessories']
    
    # --- NEW STORE COLLECTIONS ---
    store_products_col = db['store_products']
    store_customers_col = db['store_customers']
    store_invoices_col = db['store_invoices']
    
    print("MongoDB Connected Successfully!")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")


# ==============================================================================
# CSS STYLES (UPDATED: Online Indicator Pulse & Store Styles)
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
            --accent-blue: #0984e3;
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

        /* Glowing Online Indicator Animation */
        @keyframes pulse-green {
            0% { box-shadow: 0 0 0 0 rgba(0, 184, 148, 0.7); }
            70% { box-shadow: 0 0 0 6px rgba(0, 184, 148, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 184, 148, 0); }
        }
        
        .status-online-glow {
            width: 10px; height: 10px; 
            background-color: var(--accent-green); 
            border-radius: 50%; 
            display: inline-block; 
            animation: pulse-green 2s infinite;
        }

        /* Sidebar Styling */
        .sidebar {
            width: 260px; height: 100vh; background-color: var(--bg-sidebar);
            position: fixed; top: 0; left: 0; display: flex; flex-direction: column;
            padding: 30px 20px; border-right: 1px solid var(--border-color); z-index: 1000;
            transition: 0.3s;
        }
        .brand-logo { font-size: 22px; font-weight: 800; color: white; margin-bottom: 40px; display: flex; align-items: center; gap: 10px; }
        .brand-logo span { color: var(--accent-orange); }
        
        .nav-menu { flex-grow: 1; display: flex; flex-direction: column; gap: 5px; overflow-y: auto; }

        .nav-link {
            display: flex; align-items: center; padding: 12px 15px; color: var(--text-secondary);
            text-decoration: none; border-radius: 8px; margin-bottom: 5px; transition: 0.3s;
            cursor: pointer; font-weight: 500; font-size: 14px;
        }
        .nav-link:hover, .nav-link.active { background-color: rgba(255, 140, 66, 0.1); color: var(--accent-orange); }
        .nav-link i { width: 25px; margin-right: 10px; font-size: 16px; text-align: center; }
        
        /* Sub-menu indentation */
        .nav-sub-link { padding-left: 45px; font-size: 13px; }

        .sidebar-footer {
            margin-top: auto; padding-top: 20px; border-top: 1px solid var(--border-color);
            text-align: center; font-size: 12px; color: var(--text-secondary); font-weight: 500; opacity: 0.6;
        }

        /* Main Content */
        .main-content { margin-left: 260px; width: calc(100% - 260px); padding: 30px; }
        .header-section { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; }
        .page-title { font-size: 24px; font-weight: 700; color: white; margin-bottom: 5px; }
        .page-subtitle { color: var(--text-secondary); font-size: 13px; }

        /* Cards & Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .dashboard-grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 20px; }
        .dashboard-grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--card-radius); padding: 25px; }
        
        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; font-weight: 600; color: white; }

        .stat-card { display: flex; align-items: center; gap: 20px; transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-icon { width: 50px; height: 50px; background: rgba(255,255,255,0.05); border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 20px; color: var(--text-secondary); }
        .stat-info h3 { font-size: 24px; font-weight: 700; margin: 0; color: white; }
        .stat-info p { font-size: 12px; color: var(--text-secondary); margin: 0; text-transform: uppercase; }

        /* Forms */
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 5px; text-transform: uppercase; font-weight: 600; }
        input, select, textarea { width: 100%; padding: 12px; background: #2D2D2D; border: 1px solid #333; border-radius: 8px; color: white; font-size: 14px; outline: none; transition: 0.3s; }
        input:focus, select:focus, textarea:focus { border-color: var(--accent-orange); box-shadow: 0 0 0 2px rgba(255, 140, 66, 0.1); }
        
        button { width: 100%; padding: 12px; background: var(--accent-orange); color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.3s; }
        button:hover { background: #e67e22; transform: translateY(-2px); }
        
        .btn-secondary { background: #2d3436; border: 1px solid #333; }
        .btn-secondary:hover { background: #333; }

        /* Tables (Dashboard Style) */
        .dark-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .dark-table th { text-align: left; padding: 12px; color: var(--text-secondary); font-size: 12px; border-bottom: 1px solid #333; }
        .dark-table td { padding: 12px; color: white; font-size: 13px; border-bottom: 1px solid #2D2D2D; vertical-align: middle; }
        .dark-table tr:hover td { background: rgba(255,255,255,0.02); }
        
        /* Action Buttons (Perfected) */
        .action-cell { display: flex; gap: 8px; justify-content: flex-end; }
        .action-btn { 
            padding: 6px 10px; 
            border-radius: 6px; 
            text-decoration: none; 
            font-size: 12px; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            cursor: pointer; 
            border: none; 
            transition: 0.2s; 
        }
        .btn-edit { background: rgba(108, 92, 231, 0.2); color: #a29bfe; }
        .btn-edit:hover { background: var(--accent-purple); color: white; }
        .btn-del { background: rgba(255, 118, 117, 0.2); color: #ff7675; }
        .btn-del:hover { background: var(--accent-red); color: white; }
        .btn-view { background: rgba(9, 132, 227, 0.2); color: #74b9ff; }
        .btn-view:hover { background: var(--accent-blue); color: white; }

        /* Loading & Animations */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 9999; flex-direction: column; justify-content: center; align-items: center; backdrop-filter: blur(8px); transition: 0.3s; }
        
        .spinner { width: 60px; height: 60px; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid var(--accent-orange); border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        /* Success Checkmark Animation */
        .checkmark-container { display: none; text-align: center; }
        .checkmark-circle {
            width: 80px; height: 80px; position: relative; display: inline-block; vertical-align: top;
            border-radius: 50%; border: 2px solid var(--accent-green); margin-bottom: 20px;
            animation: success-anim 0.5s forwards;
        }
        .checkmark-circle::before {
            content: ''; display: block; width: 25px; height: 45px;
            border: solid var(--accent-green); border-width: 0 4px 4px 0;
            position: absolute; top: 10px; left: 26px;
            transform: rotate(45deg); opacity: 0;
            animation: checkmark-anim 0.3s 0.4s forwards;
        }
        
        /* Fail Cross Animation */
        .fail-container { display: none; text-align: center; }
        .fail-circle {
            width: 80px; height: 80px; position: relative; display: inline-block; vertical-align: top;
            border-radius: 50%; border: 2px solid var(--accent-red); margin-bottom: 20px;
            animation: fail-anim 0.5s forwards;
        }
        .fail-circle::before, .fail-circle::after {
            content: ''; position: absolute; width: 4px; height: 50px; background: var(--accent-red);
            top: 13px; left: 36px; border-radius: 2px;
        }
        .fail-circle::before { transform: rotate(45deg); }
        .fail-circle::after { transform: rotate(-45deg); }

        @keyframes success-anim { 0% { transform: scale(0); } 80% { transform: scale(1.1); } 100% { transform: scale(1); } }
        @keyframes checkmark-anim { 0% { opacity: 0; height: 0; width: 0; } 100% { opacity: 1; height: 45px; width: 25px; } }
        @keyframes fail-anim { 0% { transform: scale(0); } 80% { transform: scale(1.1); } 100% { transform: scale(1); } }

        .anim-text { font-size: 20px; font-weight: 700; color: white; margin-top: 10px; letter-spacing: 1px; }

        /* Mobile */
        .mobile-toggle { display: none; position: fixed; top: 20px; right: 20px; z-index: 2000; color: white; background: #333; padding: 8px; border-radius: 5px; }
        @media (max-width: 900px) {
            .sidebar { transform: translateX(-100%); } .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; padding: 20px; }
            .dashboard-grid-2, .dashboard-grid-3 { grid-template-columns: 1fr; }
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
            # Updated permissions to include 'store_manage'
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store_manage"],
            "created_at": "N/A",
            "last_login": "Never",
            "last_duration": "N/A"
        }
    }
    if record:
        # Ensure Admin always has all permissions (legacy fix)
        if "Admin" in record['data']:
             record['data']["Admin"]["permissions"] = ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store_manage"]
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
    # Analytics এর জন্য ডাটা লিমিট বাড়ানো হয়েছে
    if len(data['downloads']) > 3000:
        data['downloads'] = data['downloads'][:3000]
        
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
    if len(data['downloads']) > 3000:
        data['downloads'] = data['downloads'][:3000]
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

# ==============================================================================
# হেল্পার ফাংশন: STORE MANAGEMENT (NEW)
# ==============================================================================

def get_all_products():
    return list(store_products_col.find({}))

def get_product(product_id):
    return store_products_col.find_one({"_id": product_id})

def save_product_db(product_data):
    # product_data must have '_id'
    store_products_col.replace_one(
        {"_id": product_data['_id']},
        product_data,
        upsert=True
    )

def delete_product_db(product_id):
    store_products_col.delete_one({"_id": product_id})

def get_all_customers():
    return list(store_customers_col.find({}))

def get_customer(customer_id):
    return store_customers_col.find_one({"_id": customer_id})

def save_customer_db(customer_data):
    store_customers_col.replace_one(
        {"_id": customer_data['_id']},
        customer_data,
        upsert=True
    )

def get_next_invoice_number():
    # Simple auto-increment logic based on count
    # In production, a dedicated counter collection is safer for concurrency
    count = store_invoices_col.count_documents({})
    return f"INV-{1001 + count}"

def save_invoice_db(invoice_data):
    store_invoices_col.insert_one(invoice_data)

def get_all_invoices():
    return list(store_invoices_col.find({}).sort("date_iso", -1))

def get_invoice(invoice_id):
    return store_invoices_col.find_one({"invoice_no": invoice_id})

def update_customer_due_db(customer_id, amount_change):
    # amount_change positive adds to due, negative subtracts
    customer = get_customer(customer_id)
    if customer:
        current_due = float(customer.get('due', 0))
        new_due = current_due + float(amount_change)
        store_customers_col.update_one(
            {"_id": customer_id},
            {"$set": {"due": new_due}}
        )

# --- আপডেটেড: রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স ---
def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    # Store Stats
    store_products_count = store_products_col.count_documents({})
    store_invoices_count = store_invoices_col.count_documents({})
    
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

    # 2. Accessories Today & Analytics
    acc_today_count = 0
    acc_today_list = []
    
    # Analytics Container
    monthly_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0, 'inv': 0})

    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            c_date = challan.get('date')
            if c_date == today_str:
                acc_today_count += 1
                acc_today_list.append({
                    "ref": ref,
                    "buyer": data.get('buyer'),
                    "style": data.get('style'),
                    "time": "Today", 
                    "qty": challan.get('qty')
                })
            
            try:
                dt_obj = datetime.strptime(c_date, '%d-%m-%Y')
                m_key = dt_obj.strftime('%b-%y')
                sort_key = dt_obj.strftime('%Y-%m')
                monthly_data[sort_key]['acc'] += 1
                monthly_data[sort_key]['label'] = m_key
            except: pass

    # 3. Closing, PO & Store Invoices
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
            else: 
                closing_today_count += 1
                closing_list.append(item)
        
        try:
            dt_obj = datetime.strptime(item_date, '%d-%m-%Y')
            m_key = dt_obj.strftime('%b-%y')
            sort_key = dt_obj.strftime('%Y-%m')
            
            if item.get('type') == 'PO Sheet':
                monthly_data[sort_key]['po'] += 1
            else:
                monthly_data[sort_key]['closing'] += 1
            monthly_data[sort_key]['label'] = m_key
        except: pass
        
    # Invoice Analytics
    invoices = list(store_invoices_col.find({}, {"date": 1}))
    for inv in invoices:
        try:
            dt_obj = datetime.strptime(inv['date'], '%Y-%m-%d')
            m_key = dt_obj.strftime('%b-%y')
            sort_key = dt_obj.strftime('%Y-%m')
            monthly_data[sort_key]['inv'] += 1
            monthly_data[sort_key]['label'] = m_key
        except: pass

    # Sort and filter last 6 months
    sorted_keys = sorted(monthly_data.keys())[-6:]
    
    chart_labels = []
    chart_closing = []
    chart_po = []
    chart_acc = []
    chart_inv = []

    if not sorted_keys:
        curr_m = now.strftime('%b-%y')
        chart_labels = [curr_m]
        chart_closing = [0]; chart_po = [0]; chart_acc = [0]; chart_inv = [0]
    else:
        for k in sorted_keys:
            d = monthly_data[k]
            chart_labels.append(d.get('label', k))
            chart_closing.append(d['closing'])
            chart_po.append(d['po'])
            chart_acc.append(d['acc'])
            chart_inv.append(d['inv'])

    return {
        "users": { "count": len(users_data), "details": user_details },
        "accessories": { "count": acc_today_count, "details": acc_today_list },
        "closing": { "count": closing_today_count, "details": closing_list },
        "po": { "count": po_today_count, "details": po_list },
        "store": { "products": store_products_count, "invoices": store_invoices_count },
        "chart": {
            "labels": chart_labels,
            "closing": chart_closing,
            "po": chart_po,
            "acc": chart_acc,
            "inv": chart_inv
        },
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
    # UPDATED BRANDING
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
# HTML TEMPLATES: LOGIN, DASHBOARD & UI (REFINED DARK THEME)
# ==============================================================================

LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login - MNM Software</title>
    {COMMON_STYLES}
</head>
<body style="justify-content:center; align-items:center;">
    <div class="card" style="width: 100%; max-width: 400px; padding: 40px;">
        <div style="text-align: center; margin-bottom: 40px;">
            <div style="font-size: 26px; font-weight: 800; color: white; letter-spacing: -0.5px;">MNM<span style="color:var(--accent-orange)">Software</span></div>
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
    <div id="loading-overlay">
        <div class="spinner" id="spinner-anim"></div>
        
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Successful!</div>
        </div>

        <div class="fail-container" id="fail-anim">
            <div class="fail-circle"></div>
            <div class="anim-text">Action Failed!</div>
            <div style="font-size:12px; color:#ff7675; margin-top:5px;">Please check server or inputs</div>
        </div>
        
        <div style="color:white; margin-top:15px; font-weight:600;" id="loading-text">Processing...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            <div class="nav-link" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-database"></i> Accessories Challan</a>
            <div class="nav-link" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            
            <!-- STORE MENU -->
            <div style="margin-top:10px; margin-bottom:5px; font-size:11px; color:var(--text-secondary); padding-left:15px; text-transform:uppercase; font-weight:700;">Store Management</div>
            <div class="nav-link" onclick="showSection('store-dashboard', this)"><i class="fas fa-store"></i> Store Overview</div>
            <div class="nav-link" onclick="showSection('store-products', this)"><i class="fas fa-box-open"></i> Products</div>
            <div class="nav-link" onclick="showSection('store-invoice', this)"><i class="fas fa-file-invoice-dollar"></i> Invoice & Quotation</div>
            <div class="nav-link" onclick="showSection('store-customers', this)"><i class="fas fa-users"></i> Customers & Due</div>
            
            <div style="margin-top:10px; margin-bottom:5px; font-size:11px; color:var(--text-secondary); padding-left:15px; text-transform:uppercase; font-weight:700;">System</div>
            <div class="nav-link" onclick="showSection('settings', this)"><i class="fas fa-users-cog"></i> User Manage</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 10px;"><i class="fas fa-sign-out-alt"></i> Log Out</a>
        </div>
        <div class="sidebar-footer">© Mehedi Hasan</div>
    </div>

    <div class="main-content">
        
        <!-- Main Dashboard Section -->
        <div id="section-dashboard">
            <div class="header-section">
                <div><div class="page-title">Main Dashboard</div><div class="page-subtitle">Overview & Real-time Statistics</div></div>
                <div style="background:var(--bg-card); padding:10px 20px; border-radius:30px; border:1px solid var(--border-color); font-size:13px; font-weight:600; display:flex; align-items:center; gap:8px;">
                    <span class="status-online-glow"></span> Online
                </div>
            </div>
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-bottom: 20px; color: #ff7675; font-size: 13px; text-align: center; background: rgba(255, 118, 117, 0.1); padding: 10px; border-radius: 8px; border: 1px solid rgba(255, 118, 117, 0.2);"><i class="fas fa-exclamation-circle"></i> {{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}

            <div class="stats-grid">
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-file-export"></i></div><div class="stat-info"><h3>{{{{ stats.closing.count }}}}</h3><p>Closing</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-boxes"></i></div><div class="stat-info"><h3>{{{{ stats.accessories.count }}}}</h3><p>Accessories</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-file-pdf"></i></div><div class="stat-info"><h3>{{{{ stats.po.count }}}}</h3><p>PO Sheets</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-users"></i></div><div class="stat-info"><h3>{{{{ stats.users.count }}}}</h3><p>Users</p></div></div>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header"><span>Analytics (Last 6 Months)</span><i class="fas fa-chart-line" style="color:var(--accent-orange)"></i></div>
                    <div style="height: 250px;"><canvas id="mainChart"></canvas></div>
                </div>
                <div class="card">
                    <div class="section-header"><span>Module Usage Today</span></div>
                    <div class="progress-item" style="margin-bottom: 20px;"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>Closing Report</span><span style="color:var(--text-secondary);">{{{{ stats.closing.count }}}} Generated</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 85%; height:100%; background:var(--accent-orange); border-radius:3px;"></div></div></div>
                    <div class="progress-item" style="margin-bottom: 20px;"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>Accessories</span><span style="color:var(--text-secondary);">{{{{ stats.accessories.count }}}} Challans</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 60%; height:100%; background:var(--accent-purple); border-radius:3px;"></div></div></div>
                    <div class="progress-item"><div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:white;"><span>PO Generator</span><span style="color:var(--text-secondary);">{{{{ stats.po.count }}}} Files</span></div><div style="height:6px; background:#333; border-radius:3px;"><div style="width: 45%; height:100%; background:var(--accent-green); border-radius:3px;"></div></div></div>
                </div>
            </div>

            <div class="card">
                <div class="section-header"><span>Recent Activity Log</span><i class="fas fa-history" style="color:var(--text-secondary)"></i></div>
                <div style="overflow-x: auto;">
                    <table class="dark-table">
                        <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Reference / Type</th></tr></thead>
                        <tbody>
                            {{% for log in stats.history[:10] %}}
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
                <form action="/generate-report" method="post" onsubmit="return showLoading()">
                    <div class="input-group"><label>INTERNAL REF NO</label><input type="text" name="ref_no" placeholder="e.g. Booking-123" required></div>
                    <button type="submit"><i class="fas fa-magic" style="margin-right:8px;"></i> Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="card" style="max-width:600px; margin:0 auto; margin-top:50px;">
                <div class="section-header">PO Sheet Generator</div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="return showLoading()">
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
                                <!-- New Permission for Store -->
                                <label style="background:#2D2D2D; padding:10px; border-radius:8px; cursor:pointer; display:flex; align-items:center; border:1px solid #333;"><input type="checkbox" id="perm_store" style="width:auto; margin-right:8px;"> Store</label>
                            </div>
                        </div>
                        <button type="button" onclick="handleUserSubmit()" id="saveUserBtn"><i class="fas fa-save" style="margin-right:8px;"></i> Save User</button>
                        <button type="button" onclick="resetForm()" style="margin-top:10px; background:#2D2D2D; color:white; border:1px solid #333;">Reset Form</button>
                    </form>
                </div>
            </div>
        </div>
        
        <!-- NEW: STORE DASHBOARD SECTION -->
        <div id="section-store-dashboard" style="display:none;">
            <div class="header-section">
                <div><div class="page-title">Store Overview</div><div class="page-subtitle">MEHEDI THAI ALUMINUM AND GLASS</div></div>
            </div>
            <div class="stats-grid">
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-box-open"></i></div><div class="stat-info"><h3>{{{{ stats.store.products }}}}</h3><p>Total Products</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-file-invoice-dollar"></i></div><div class="stat-info"><h3>{{{{ stats.store.invoices }}}}</h3><p>Total Invoices</p></div></div>
                <div class="card stat-card"><div class="stat-icon"><i class="fas fa-exclamation-circle" style="color:var(--accent-red)"></i></div><div class="stat-info"><h3>Due</h3><p>Collection Pending</p></div></div>
            </div>
             <div class="card" style="text-align:center; padding:50px;">
                <i class="fas fa-store" style="font-size:50px; color:var(--accent-orange); margin-bottom:20px;"></i>
                <h3>Store Management System</h3>
                <p style="color:var(--text-secondary); max-width:500px; margin:0 auto;">Manage your products, generate professional quotations/invoices, and track customer dues efficiently from the sidebar menu.</p>
            </div>
        </div>
        
        <!-- NEW: STORE PRODUCTS SECTION -->
        <div id="section-store-products" style="display:none;">
            <div class="header-section">
                 <div><div class="page-title">Product Inventory</div><div class="page-subtitle">Add or Manage Items</div></div>
                 <button onclick="openProductModal()" style="width:auto;"><i class="fas fa-plus"></i> Add New Product</button>
            </div>
            <div class="card">
                 <div id="productTableContainer">Loading Products...</div>
            </div>
        </div>

        <!-- Product Modal -->
        <div id="productModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:2000; align-items:center; justify-content:center;">
            <div class="card" style="width:400px;">
                <div class="section-header">Product Details <i class="fas fa-times" onclick="closeProductModal()" style="cursor:pointer;"></i></div>
                <form id="productForm">
                    <input type="hidden" id="prod_id">
                    <div class="input-group"><label>Product Name</label><input type="text" id="prod_name" required></div>
                    <div class="input-group"><label>Size / Dimensions (e.g. 5ft)</label><input type="text" id="prod_size" placeholder="Optional"></div>
                    <div class="input-group"><label>Price (Optional)</label><input type="number" id="prod_price" placeholder="0.00"></div>
                    <button type="button" onclick="saveProduct()">Save Product</button>
                </form>
            </div>
        </div>
                <!-- NEW: STORE INVOICE SECTION -->
        <div id="section-store-invoice" style="display:none;">
             <div class="header-section">
                 <div><div class="page-title">Invoices & Quotations</div><div class="page-subtitle">Generate Bills or Estimates</div></div>
                 <button onclick="window.location.href='/store/create-invoice'" style="width:auto; background:var(--accent-green);"><i class="fas fa-plus"></i> New Invoice / Quotation</button>
            </div>
            <div class="card">
                 <div class="section-header">Recent Invoices</div>
                 <div id="invoiceListContainer">Loading...</div>
            </div>
        </div>
        
        <!-- NEW: STORE CUSTOMER SECTION -->
        <div id="section-store-customers" style="display:none;">
            <div class="header-section">
                 <div><div class="page-title">Customer Management</div><div class="page-subtitle">Track Dues & Payments</div></div>
                 <button onclick="openCustomerModal()" style="width:auto;"><i class="fas fa-user-plus"></i> Add Customer</button>
            </div>
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">Customer List</div>
                    <div id="customerListContainer">Loading...</div>
                </div>
                <div class="card">
                     <div class="section-header">Due Payment Collection</div>
                     <div class="input-group"><label>Search by Challan No</label><input type="text" id="due_search_challan" placeholder="INV-XXXX"></div>
                     <button onclick="searchDueInvoice()">Search</button>
                     <div id="dueResult" style="margin-top:20px;"></div>
                </div>
            </div>
        </div>

        <!-- Customer Modal -->
        <div id="customerModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:2000; align-items:center; justify-content:center;">
            <div class="card" style="width:400px;">
                <div class="section-header">Add Customer <i class="fas fa-times" onclick="closeCustomerModal()" style="cursor:pointer;"></i></div>
                <form id="customerForm">
                    <input type="hidden" id="cust_id">
                    <div class="input-group"><label>Customer Name</label><input type="text" id="cust_name" required></div>
                    <div class="input-group"><label>Phone / Contact</label><input type="text" id="cust_phone"></div>
                    <div class="input-group"><label>Address</label><textarea id="cust_address" rows="2" style="background:#2D2D2D; border:1px solid #333; width:100%; color:white; padding:10px;"></textarea></div>
                    <button type="button" onclick="saveCustomer()">Save Customer</button>
                </form>
            </div>
        </div>

    </div>

    <script>
        function showSection(id, element) {{
            ['dashboard', 'analytics', 'help', 'settings', 'store-dashboard', 'store-products', 'store-invoice', 'store-customers'].forEach(sid => document.getElementById('section-' + sid).style.display = 'none');
            document.getElementById('section-' + id).style.display = 'block';
            if(element) {{ document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active')); element.classList.add('active'); }}
            
            if(id === 'settings') loadUsers();
            if(id === 'store-products') loadProducts();
            if(id === 'store-customers') loadCustomers();
            if(id === 'store-invoice') loadInvoices();
            
            if(window.innerWidth < 992) document.querySelector('.sidebar').classList.remove('active');
        }}
        document.getElementById('file-upload')?.addEventListener('change', function() {{ document.getElementById('file-count').innerText = this.files.length + " files selected"; }});
        
        // --- REAL-TIME WAVY CHART INITIALIZATION ---
        const ctx = document.getElementById('mainChart').getContext('2d');
        const gradientOrange = ctx.createLinearGradient(0, 0, 0, 300); gradientOrange.addColorStop(0, 'rgba(255, 140, 66, 0.4)'); gradientOrange.addColorStop(1, 'rgba(255, 140, 66, 0)');
        const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300); gradientPurple.addColorStop(0, 'rgba(108, 92, 231, 0.4)'); gradientPurple.addColorStop(1, 'rgba(108, 92, 231, 0)');
        
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {{{{ stats.chart.labels | tojson }}}}, // Real-time Labels
                datasets: [
                    {{
                        label: 'Closing',
                        data: {{{{ stats.chart.closing | tojson }}}},
                        borderColor: '#FF8C42',
                        backgroundColor: gradientOrange,
                        tension: 0.4, // Wavy
                        fill: true
                    }},
                    {{
                        label: 'Accessories',
                        data: {{{{ stats.chart.acc | tojson }}}},
                        borderColor: '#6C5CE7',
                        backgroundColor: gradientPurple,
                        tension: 0.4, // Wavy
                        fill: true
                    }},
                    {{
                        label: 'PO Sheets',
                        data: {{{{ stats.chart.po | tojson }}}},
                        borderColor: '#00b894',
                        borderDash: [5, 5],
                        tension: 0.4, // Wavy
                        fill: false
                    }}
                ]
            }},
            options: {{
                plugins: {{ legend: {{ display: true, labels: {{ color: '#A0A0A0', font: {{ size: 11 }} }} }} }},
                scales: {{
                    x: {{ grid: {{ display: false, color: '#333' }}, ticks: {{ color: '#A0A0A0' }} }},
                    y: {{ grid: {{ color: '#2D2D2D' }}, ticks: {{ color: '#A0A0A0' }} }}
                }},
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
        
        // --- ANIMATION CONTROLLER ---
        function showLoading() {{
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim');
            const success = document.getElementById('success-anim');
            const fail = document.getElementById('fail-anim');
            const text = document.getElementById('loading-text');
            
            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            success.style.display = 'none';
            fail.style.display = 'none';
            text.innerText = 'Processing...';
            return true;
        }}

        function showSuccess() {{
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim');
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            overlay.style.display = 'flex';
            spinner.style.display = 'none';
            success.style.display = 'block';
            text.innerText = '';
            
            setTimeout(() => {{ overlay.style.display = 'none'; }}, 1500);
        }}

        function loadUsers() {{
            fetch('/admin/get-users').then(res => res.json()).then(data => {{
                let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
                for(const [u, d] of Object.entries(data)) {{
                    html += `<tr><td>${{u}}</td><td><span style="background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:4px; font-size:11px;">${{d.role}}</span></td><td style="text-align:right;">${{d.role !== 'admin' ? 
                        `<div class="action-cell">
                            <button class="action-btn btn-edit" onclick="editUser('${{u}}', '${{d.password}}', '${{d.permissions.join(',')}}')"><i class="fas fa-edit"></i></button> 
                            <button class="action-btn btn-del" onclick="deleteUser('${{u}}')"><i class="fas fa-trash"></i></button>
                        </div>` : 
                        '<i class="fas fa-shield-alt" style="color:var(--text-secondary); margin-right:10px;"></i>'}}</td></tr>`;
                }}
                document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
            }});
        }}
        
        function handleUserSubmit() {{
            const u = document.getElementById('new_username').value, p = document.getElementById('new_password').value, a = document.getElementById('action_type').value;
            let perms = []; 
            ['closing', 'po_sheet', 'accessories', 'store'].forEach(id => {{ 
                if(document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked) perms.push(id); 
            }});
            
            showLoading();
            fetch('/admin/save-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u, password: p, permissions: perms, action_type: a }}) }}).then(r => r.json()).then(d => {{ 
                if(d.status === 'success') {{ showSuccess(); loadUsers(); resetForm(); }} else {{ alert(d.message); document.getElementById('loading-overlay').style.display = 'none'; }}
            }});
        }}
        
        function editUser(u, p, permsStr) {{ document.getElementById('new_username').value = u; document.getElementById('new_username').readOnly = true; document.getElementById('new_password').value = p; document.getElementById('action_type').value = 'update'; document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-sync"></i> Update User'; let pArr = permsStr.split(','); ['closing', 'po_sheet', 'accessories', 'store'].forEach(id => {{ document.getElementById('perm_' + (id==='po_sheet'?'po':(id==='accessories'?'acc':id))).checked = pArr.includes(id); }}); }}
        function resetForm() {{ document.getElementById('userForm').reset(); document.getElementById('action_type').value = 'create'; document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-save"></i> Save User'; document.getElementById('new_username').readOnly = false; }}
        function deleteUser(u) {{ if(confirm('Are you sure you want to delete this user?')) fetch('/admin/delete-user', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ username: u }}) }}).then(() => loadUsers()); }}

        // --- STORE JS LOGIC ---
        function openProductModal() {{ document.getElementById('productModal').style.display = 'flex'; document.getElementById('prod_id').value = ''; document.getElementById('prod_name').value=''; document.getElementById('prod_size').value=''; document.getElementById('prod_price').value=''; }}
        function closeProductModal() {{ document.getElementById('productModal').style.display = 'none'; }}
        
        function saveProduct() {{
            const id = document.getElementById('prod_id').value;
            const name = document.getElementById('prod_name').value;
            const size = document.getElementById('prod_size').value;
            const price = document.getElementById('prod_price').value;
            if(!name) return alert("Name required");
            
            showLoading();
            fetch('/store/save-product', {{ method:'POST', headers: {{'Content-Type':'application/json'}}, body: JSON.stringify({{id, name, size, price}}) }})
            .then(r=>r.json()).then(d=>{{ showSuccess(); closeProductModal(); loadProducts(); }});
        }}

        function loadProducts() {{
             fetch('/store/get-products').then(r=>r.json()).then(data=>{{
                 let h = '<table class="dark-table"><thead><tr><th>Name</th><th>Size</th><th>Price</th><th>Action</th></tr></thead><tbody>';
                 data.forEach(p=>{{
                     h+=`<tr><td>${{p.name}}</td><td>${{p.size||'-'}}</td><td>${{p.price||'-'}}</td>
                     <td><button class="action-btn btn-del" onclick="deleteProduct('${{p._id}}')"><i class="fas fa-trash"></i></button></td></tr>`;
                 }});
                 document.getElementById('productTableContainer').innerHTML = h + '</tbody></table>';
             }});
        }}
        
        function deleteProduct(id) {{ if(confirm("Delete?")) fetch('/store/delete-product',{{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id}})}}).then(()=>loadProducts()); }}

        function openCustomerModal() {{ document.getElementById('customerModal').style.display='flex'; document.getElementById('cust_name').value=''; document.getElementById('cust_phone').value=''; document.getElementById('cust_address').value=''; }}
        function closeCustomerModal() {{ document.getElementById('customerModal').style.display='none'; }}

        function saveCustomer() {{
             const name = document.getElementById('cust_name').value;
             const phone = document.getElementById('cust_phone').value;
             const address = document.getElementById('cust_address').value;
             if(!name) return alert("Name required");
             showLoading();
             fetch('/store/save-customer', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{name,phone,address}})}})
             .then(r=>r.json()).then(d=>{{ showSuccess(); closeCustomerModal(); loadCustomers(); }});
        }}

        function loadCustomers() {{
            fetch('/store/get-customers').then(r=>r.json()).then(data=>{{
                 let h = '<table class="dark-table"><thead><tr><th>Name</th><th>Phone</th><th>Due</th></tr></thead><tbody>';
                 data.forEach(c=>{{
                     h+=`<tr><td>${{c.name}}</td><td>${{c.phone||'-'}}</td><td style="color:${{c.due>0?'var(--accent-red)':'var(--accent-green)'}}">${{c.due||0}}</td></tr>`;
                 }});
                 document.getElementById('customerListContainer').innerHTML = h + '</tbody></table>';
            }});
        }}
        
        function loadInvoices() {{
             fetch('/store/get-invoices').then(r=>r.json()).then(data=>{{
                 let h = '<table class="dark-table"><thead><tr><th>Inv No</th><th>Date</th><th>Customer</th><th>Total</th><th>Type</th><th>Action</th></tr></thead><tbody>';
                 data.forEach(i=>{{
                     h+=`<tr><td>${{i.invoice_no}}</td><td>${{i.date}}</td><td>${{i.customer_name}}</td><td>${{i.grand_total}}</td>
                     <td><span style="background:${{i.type==='invoice'?'rgba(0,184,148,0.2)':'rgba(255,140,66,0.2)'}}; padding:2px 6px; border-radius:4px; font-size:11px;">${{i.type.toUpperCase()}}</span></td>
                     <td><a href="/store/print-invoice?inv=${{i.invoice_no}}" target="_blank" class="action-btn btn-view"><i class="fas fa-print"></i></a></td></tr>`;
                 }});
                 document.getElementById('invoiceListContainer').innerHTML = h + '</tbody></table>';
             }});
        }}
        
        function searchDueInvoice() {{
             const inv = document.getElementById('due_search_challan').value;
             if(!inv) return;
             fetch('/store/get-invoice-due?inv='+inv).then(r=>r.json()).then(d=>{{
                 const res = document.getElementById('dueResult');
                 if(d.status === 'found') {{
                     res.innerHTML = `<div style="background:#222; padding:15px; border-radius:8px; margin-top:10px;">
                        <div style="color:var(--accent-orange); font-weight:bold;">${{d.data.invoice_no}}</div>
                        <div style="font-size:13px;">Customer: ${{d.data.customer_name}}</div>
                        <div style="font-size:13px;">Total Due: <span style="color:var(--accent-red)">${{d.data.due}}</span></div>
                        <div style="margin-top:10px;">
                             <input type="number" id="pay_amount" placeholder="Amount to Pay" style="width:120px; padding:5px;">
                             <button onclick="payDue('${{d.data.invoice_no}}')" style="padding:5px 10px; width:auto;">Pay</button>
                        </div>
                     </div>`;
                 }} else {{ res.innerHTML = '<div style="color:var(--accent-red)">Not Found</div>'; }}
             }});
        }}
        
        function payDue(inv) {{
             const amt = document.getElementById('pay_amount').value;
             if(!amt) return alert("Enter Amount");
             showLoading();
             fetch('/store/pay-due', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{inv, amount:amt}})}})
             .then(r=>r.json()).then(d=>{{ showSuccess(); document.getElementById('dueResult').innerHTML = '<div style="color:green">Payment Added!</div>'; loadCustomers(); }});
        }}

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
    <div id="loading-overlay"><div class="spinner"></div><div style="color:white; margin-top:15px; font-weight:600;">Processing...</div></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active"><i class="fas fa-home"></i> Home</div>
            <a href="/logout" class="nav-link" style="color:var(--accent-red); margin-top:auto;"><i class="fas fa-sign-out-alt"></i> Log Out</a>
        </div>
        <div class="sidebar-footer">© Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Welcome, {{{{ session.user }}}}</div><div class="page-subtitle">Your assigned production modules.</div></div>
            <div style="background:var(--bg-card); padding:10px 20px; border-radius:30px; border:1px solid var(--border-color); font-size:13px; font-weight:600; display:flex; align-items:center; gap:8px;">
                    <span class="status-online-glow"></span> Online
            </div>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div style="margin-bottom: 20px; color: #ff7675; font-size: 13px; text-align: center; background: rgba(255, 118, 117, 0.1); padding: 10px; border-radius: 8px; border: 1px solid rgba(255, 118, 117, 0.2);"><i class="fas fa-exclamation-circle"></i> {{{{ messages[0] }}}}</div>
            {{% endif %}}
        {{% endwith %}}

        <div class="stats-grid">
            {{% if 'closing' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Closing Report</span><i class="fas fa-file-export" style="color:var(--accent-orange)"></i></div>
            <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>REF NO</label><input type="text" name="ref_no" required placeholder="Booking Ref"></div><button>Generate</button></form></div>{{% endif %}}
            
            {{% if 'po_sheet' in session.permissions %}}
            <div class="card"><div class="section-header"><span>PO Sheet</span><i class="fas fa-file-pdf" style="color:var(--accent-green)"></i></div>
            <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'"><div class="input-group"><label>FILES</label><input type="file" name="pdf_files" multiple accept=".pdf" required style="padding:10px;"></div><button style="background:var(--accent-green)">Process Files</button></form></div>{{% endif %}}
            
            {{% if 'accessories' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Accessories</span><i class="fas fa-boxes" style="color:var(--accent-purple)"></i></div><p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px; line-height:1.5;">Manage Challans, entries and history for accessories.</p><a href="/admin/accessories"><button style="background:var(--accent-purple)">Open Dashboard</button></a></div>{{% endif %}}
            
            {{% if 'store' in session.permissions %}}
            <div class="card"><div class="section-header"><span>Store Manage</span><i class="fas fa-store" style="color:var(--accent-blue)"></i></div><p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px; line-height:1.5;">Manage Products, Invoices & Customers.</p><a href="/store/dashboard"><button style="background:var(--accent-blue)">Access Store</button></a></div>{{% endif %}}
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html><html lang="en"><head><title>Search</title>{COMMON_STYLES}</head><body style="justify-content:center; align-items:center;">
<div class="card" style="width:100%; max-width:450px; padding:40px;">
    <div class="section-header" style="justify-content:center; margin-bottom:30px; border-bottom:none;">Accessories Challan</div>
    <form action="/admin/accessories/input" method="post"><div class="input-group"><label><i class="fas fa-search"></i> BOOKING REFERENCE</label><input type="text" name="ref_no" required placeholder="Enter Booking No"></div>
    <button style="background:var(--accent-orange);">Proceed to Entry <i class="fas fa-arrow-right"></i></button>
    </form>
    {{% with messages = get_flashed_messages() %}}
        {{% if messages %}}
            <div style="margin-top: 15px; color: #ff7675; font-size: 13px; text-align: center; background: rgba(255, 118, 117, 0.1); padding: 10px; border-radius: 8px;"><i class="fas fa-exclamation-circle"></i> {{{{ messages[0] }}}}</div>
        {{% endif %}}
    {{% endwith %}}
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
    <div id="loading-overlay">
        <div class="spinner" id="spinner-anim"></div>
        <div class="checkmark-container" id="success-anim"><div class="checkmark-circle"></div><div class="anim-text">Done!</div></div>
        <div style="color:white; margin-top:15px; font-weight:600;" id="loading-text">Saving...</div>
    </div>

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
                <form action="/admin/accessories/save" method="post" onsubmit="showLoading()">
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
                        <thead><tr><th>Ln</th><th>Color</th><th>Qty</th><th>St</th><th style="text-align:right;">Act</th></tr></thead>
                        <tbody>
                            {{% for item in challans|reverse %}}
                            <tr>
                                <td>{{{{ item.line }}}}</td>
                                <td>{{{{ item.color }}}}</td>
                                <td style="font-weight:700; color:var(--accent-green);">{{{{ item.qty }}}}</td>
                                <td style="color:var(--accent-green); font-weight:bold;">{{{{ item.status }}}}</td>
                                <td style="text-align:right;">
                                    {{% if session.role == 'admin' %}}
                                    <div class="action-cell">
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
                            <tr><td colspan="5" style="text-align:center; padding:30px; color:var(--text-secondary); font-size:12px;">No challans added yet.</td></tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <script>
        function showLoading() {{
            document.getElementById('loading-overlay').style.display = 'flex';
            document.getElementById('spinner-anim').style.display = 'block';
            document.getElementById('success-anim').style.display = 'none';
            return true;
        }}
    </script>
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
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; border: none; }
        .btn-excel { background-color: #27ae60; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; text-decoration: none; display: inline-block; }
        .btn-excel:hover { color: white; background-color: #219150; }
        .footer-credit { text-align: center; margin-top: 40px; margin-bottom: 20px; font-size: 1rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #000; font-weight: 600;}
        @media print {
            @page { margin: 5mm; size: portrait; } 
            body { background-color: white; padding: 0; }
            .container { max-width: 100% !important; width: 100%; }
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
            <button onclick="window.print()" class="btn btn-print"><i class="fas fa-print"></i> Print Report</button>
            <a href="/download-closing-excel?ref_no={{ ref_no }}" class="btn btn-excel"><i class="fas fa-file-excel"></i> Download Excel</a>
        </div>
        <div class="company-header">
            <div class="company-name">COTTON CLOTHING BD LTD</div>
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
        <div class="company-name">COTTON CLOTHING BD LTD</div>
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
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
        .table th:empty { background-color: white !important; border: none; } /* Fix for Empty Blue Cell */
        .table td { text-align: center; vertical-align: middle; border: 1px solid #dee2e6; padding: 6px 3px; color: #000; font-weight: 800; font-size: 1.15rem; }
        .table-striped tbody tr:nth-of-type(odd) { background-color: #f8f9fa; }
        .order-col { font-weight: 900 !important; text-align: center !important; background-color: #fdfdfd; white-space: nowrap; width: 1%; }
        .total-col { font-weight: 900; background-color: #e8f6f3 !important; color: #16a085; border-left: 2px solid #1abc9c !important; }
        .total-col-header { background-color: #e8f6f3 !important; color: #000 !important; font-weight: 900 !important; border: 1px solid #34495e !important; }
        .table-striped tbody tr.summary-row, .table-striped tbody tr.summary-row td { background-color: #d1ecff !important; --bs-table-accent-bg: #d1ecff !important; color: #000 !important; font-weight: 900 !important; border-top: 2px solid #aaa !important; font-size: 1.2rem !important; }
        .summary-label { text-align: right !important; padding-right: 15px !important; color: #000 !important; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 10px; }
        .btn-print { background-color: #e74c3c; color: white; border-radius: 50px; padding: 8px 30px; font-weight: 600; border: none; }
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
            .table th:empty { background-color: white !important; border: none !important; } /* Print Fix Empty Cell */
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
            <button onclick="window.print()" class="btn btn-print"><i class="fas fa-file-pdf"></i>Print</button>
        </div>
        <div class="company-header">
            <div class="company-name">COTTON CLOTHING BD LTD</div>
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

STORE_INVOICE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Invoice</title>
    <style>
        body { font-family: 'Inter', sans-serif; padding: 40px; color: #333; background: #fff; }
        .container { max-width: 800px; margin: 0 auto; border: 1px solid #ddd; padding: 40px; }
        
        .header { display: flex; justify-content: space-between; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }
        .brand { font-size: 28px; font-weight: 800; color: #2c3e50; text-transform: uppercase; line-height: 1.2; }
        .brand span { color: #e67e22; }
        .meta { text-align: right; font-size: 14px; }
        .meta div { margin-bottom: 5px; }

        .title { text-align: center; font-size: 20px; font-weight: 700; text-transform: uppercase; margin-bottom: 30px; border: 2px solid #333; display: inline-block; padding: 5px 20px; }
        .center-box { text-align: center; }
        
        .info-section { display: flex; justify-content: space-between; margin-bottom: 30px; font-size: 14px; }
        .to-section { border-left: 3px solid #e67e22; padding-left: 15px; }
        .to-title { font-weight: 700; color: #e67e22; margin-bottom: 5px; }
        
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        th { background: #2c3e50; color: white; padding: 12px; text-align: left; font-size: 13px; }
        td { padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
        .amount-col { text-align: right; }
        
        .total-section { display: flex; justify-content: flex-end; }
        .total-table { width: 300px; }
        .total-table td { border-bottom: 1px solid #eee; padding: 8px; }
        .grand-total { font-size: 18px; font-weight: 800; color: #2c3e50; border-top: 2px solid #333; }

        .footer { margin-top: 60px; border-top: 1px solid #eee; padding-top: 20px; text-align: center; font-size: 12px; color: #888; }
        
        @media print {
            body { padding: 0; } .container { border: none; padding: 0; }
            .no-print { display: none; }
        }
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="padding: 10px 20px; background: #2c3e50; color: white; border: none; cursor: pointer;">Print Invoice</button>
    </div>

    <div class="container">
        <div class="header">
            <div class="brand">MEHEDI THAI<br><span>ALUMINUM AND GLASS</span></div>
            <div class="meta">
                <div><strong>Invoice No:</strong> {{ invoice.invoice_no }}</div>
                <div><strong>Date:</strong> {{ invoice.date }}</div>
                <div><strong>Status:</strong> {{ invoice.status|upper }}</div>
            </div>
        </div>

        <div class="center-box">
            <div class="title">{{ invoice.type|upper }}</div>
        </div>

        <div class="info-section">
            <div class="to-section">
                <div class="to-title">BILL TO</div>
                <div style="font-weight: 700; font-size: 16px;">{{ invoice.customer_name }}</div>
                <div>{{ invoice.customer_phone }}</div>
                <div>{{ invoice.customer_address }}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>SL</th>
                    <th>DESCRIPTION / ITEM</th>
                    <th>SIZE / DIMENSION</th>
                    <th class="amount-col">UNIT PRICE</th>
                    <th class="amount-col">QTY</th>
                    <th class="amount-col">TOTAL</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.name }}</td>
                    <td>{{ item.size }}</td>
                    <td class="amount-col">{{ item.price }}</td>
                    <td class="amount-col">{{ item.qty }}</td>
                    <td class="amount-col">{{ item.total }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="total-section">
            <table class="total-table">
                <tr>
                    <td>Sub Total:</td>
                    <td class="amount-col">{{ invoice.sub_total }}</td>
                </tr>
                <tr>
                    <td>Discount:</td>
                    <td class="amount-col">- {{ invoice.discount }}</td>
                </tr>
                <tr class="grand-total">
                    <td>GRAND TOTAL:</td>
                    <td class="amount-col">{{ invoice.grand_total }} Tk</td>
                </tr>
                {% if invoice.type == 'invoice' %}
                <tr>
                    <td>Paid:</td>
                    <td class="amount-col">{{ invoice.paid }}</td>
                </tr>
                <tr>
                    <td style="color: #e74c3c; font-weight: 700;">Due:</td>
                    <td class="amount-col" style="color: #e74c3c; font-weight: 700;">{{ invoice.due }}</td>
                </tr>
                {% endif %}
            </table>
        </div>
        
        <div style="margin-top: 40px; font-size: 13px;">
            <strong>In Words:</strong> <span style="text-transform: capitalize;">{{ invoice.in_words }} Taka Only.</span>
        </div>

        <div class="footer">
            Thank you for your business!<br>
            This is a computer generated invoice.
        </div>
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
            # ড্যাশবোর্ড ডাটা লোড (রিয়েল-টাইম চার্ট এবং স্ট্যাটাস)
            stats = get_dashboard_summary_v2()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            # User Dashboard Logic
            perms = session.get('permissions', [])
            
            # Redirect based on permission if user has only one module access
            if len(perms) == 1:
                if 'accessories' in perms: return redirect(url_for('accessories_search_page'))
                if 'store' in perms: return redirect('/store/dashboard') # Direct Store Link (Route below)
                
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

    try:
        report_data = fetch_closing_report_data(internal_ref_no)
        if not report_data:
            flash(f"Booking Not Found: {internal_ref_no}")
            return redirect(url_for('index'))
        
        update_stats(internal_ref_no, session.get('user', 'Unknown'))
        return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=internal_ref_no)
    except Exception as e:
        flash(f"System Error: {str(e)}")
        return redirect(url_for('index'))

@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    if not session.get('logged_in'): return redirect(url_for('index'))
    internal_ref_no = request.args.get('ref_no')
    
    try:
        report_data = fetch_closing_report_data(internal_ref_no)
        if report_data:
            excel_file = create_formatted_excel_report(report_data, internal_ref_no)
            update_stats(internal_ref_no, session.get('user', 'Unknown'))
            return make_response(send_file(
                excel_file, as_attachment=True, 
                download_name=f"Report-{internal_ref_no.replace('/', '_')}.xlsx", 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ))
        else:
            flash("Data source returned empty.")
            return redirect(url_for('index'))
    except Exception as e:
        flash("Failed to generate Excel.")
        return redirect(url_for('index'))

# --- ACCESSORIES ROUTES ---
@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref_no = request.form.get('ref_no') or request.args.get('ref')
    if ref_no: ref_no = ref_no.strip().upper()
    if not ref_no: return redirect(url_for('accessories_search_page'))

    db_acc = load_accessories_db()
    if ref_no in db_acc:
        data = db_acc[ref_no]
        colors, style, buyer, challans = data['colors'], data['style'], data['buyer'], data['challans']
    else:
        try:
            api_data = fetch_closing_report_data(ref_no)
            if not api_data:
                flash(f"Booking not found: {ref_no}")
                return redirect(url_for('accessories_search_page'))
            colors = sorted(list(set([item['color'] for item in api_data])))
            style = api_data[0].get('style', 'N/A')
            buyer = api_data[0].get('buyer', 'N/A')
            challans = []
            db_acc[ref_no] = { "style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": challans }
            save_accessories_db(db_acc)
        except:
            flash("Connection Error with ERP")
            return redirect(url_for('accessories_search_page'))

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer, challans=challans)

@app.route('/admin/accessories/input_direct')
def accessories_input_direct(): return accessories_input_page() 

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    ref = request.form.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref in db_acc:
        if request.form.get('item_type'): db_acc[ref]['item_type'] = request.form.get('item_type')
        for item in db_acc[ref]['challans']: item['status'] = "✔"
        new_entry = { "date": get_bd_date_str(), "line": request.form.get('line_no'), "color": request.form.get('color'), "size": request.form.get('size'), "qty": request.form.get('qty'), "status": "" }
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
    line_summary = {}
    for c in challans:
        ln = c['line']
        try: q = int(c['qty'])
        except: q = 0
        line_summary[ln] = line_summary.get(ln, 0) + q
    sorted_line_summary = dict(sorted(line_summary.items()))

    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, ref=ref, buyer=data['buyer'], style=data['style'], item_type=data.get('item_type', ''), challans=challans, line_summary=sorted_line_summary, count=len(challans), today=get_bd_date_str())

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
        db_acc[ref]['challans'][index].update({'line': request.form.get('line_no'), 'color': request.form.get('color'), 'size': request.form.get('size'), 'qty': request.form.get('qty')})
        save_accessories_db(db_acc)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin': return redirect(url_for('index'))
    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db_acc = load_accessories_db()
    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        del db_acc[ref]['challans'][index]
        save_accessories_db(db_acc)
    return redirect(url_for('accessories_input_direct', ref=ref))

# --- PO SHEET ROUTE ---
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
            data, meta = extract_data_dynamic(file_path)
            if meta['buyer'] != 'N/A': final_meta = meta
            if data: all_data.extend(data)
        
        if not all_data: return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found in uploaded files.")
        update_po_stats(session.get('user', 'Unknown'), len(uploaded_files))

        df = pd.DataFrame(all_data)
        df['Color'] = df['Color'].str.strip()
        df = df[df['Color'] != ""]
        final_tables, grand_total_qty = [], 0
        
        for color in df['Color'].unique():
            color_df = df[df['Color'] == color]
            pivot = color_df.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
            pivot.columns.name = None
            try: pivot = pivot[sort_sizes(pivot.columns.tolist())]
            except: pass
            
            pivot['Total'] = pivot.sum(axis=1)
            grand_total_qty += pivot['Total'].sum()
            actual_qty = pivot.sum(); actual_qty.name = 'Actual Qty'
            qty_plus_3 = (actual_qty * 1.03).round().astype(int); qty_plus_3.name = '3% Order Qty'
            
            pivot_final = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T]).reset_index().rename(columns={'index': 'P.O NO'})
            pd.set_option('colheader_justify', 'center')
            html_table = pivot_final.to_html(classes='table table-bordered table-striped', index=False, border=0)
            html_table = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', html_table).replace('<th>Total</th>', '<th class="total-col-header">Total</th>').replace('<td>Total</td>', '<td class="total-col">Total</td>').replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>').replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
            html_table = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', html_table)
            final_tables.append({'color': color, 'table': html_table})
            
        return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")
    except Exception as e:
        flash(f"Error processing files: {str(e)}")
        return redirect(url_for('index'))

# ==============================================================================
# NEW: STORE MANAGEMENT CONTROLLERS
# ==============================================================================

# --- Product Routes ---
@app.route('/store/get-products', methods=['GET'])
def store_get_products():
    if not session.get('logged_in'): return jsonify([])
    return jsonify(get_all_products())

@app.route('/store/save-product', methods=['POST'])
def store_save_product():
    if not session.get('logged_in'): return jsonify({'status': 'error'})
    data = request.json
    if not data.get('id'): data['_id'] = str(uuid.uuid4())
    else: data['_id'] = data.pop('id')
    save_product_db(data)
    return jsonify({'status': 'success'})

@app.route('/store/delete-product', methods=['POST'])
def store_delete_product():
    if not session.get('logged_in'): return jsonify({'status': 'error'})
    delete_product_db(request.json.get('id'))
    return jsonify({'status': 'success'})

# --- Customer Routes ---
@app.route('/store/get-customers', methods=['GET'])
def store_get_customers():
    if not session.get('logged_in'): return jsonify([])
    return jsonify(get_all_customers())

@app.route('/store/save-customer', methods=['POST'])
def store_save_customer():
    if not session.get('logged_in'): return jsonify({'status': 'error'})
    data = request.json
    data['_id'] = str(uuid.uuid4())
    data['due'] = 0.0
    save_customer_db(data)
    return jsonify({'status': 'success'})

# --- Invoice Routes ---
@app.route('/store/get-invoices', methods=['GET'])
def store_get_invoices():
    if not session.get('logged_in'): return jsonify([])
    return jsonify(get_all_invoices())

@app.route('/store/create-invoice')
def store_create_invoice_page():
    if not session.get('logged_in'): return redirect('/')
    # Simple inline template for creating invoice
    products = get_all_products()
    customers = get_all_customers()
    
    HTML = f"""
    <!doctype html><html lang="en"><head><title>New Invoice</title>{COMMON_STYLES}</head><body>
    <div class="card" style="width:90%; max-width:900px; margin:30px auto; padding:30px;">
        <div class="section-header">Create New Invoice / Quotation</div>
        <form id="invForm">
            <div class="dashboard-grid-2">
                <div class="input-group"><label>Customer</label>
                    <select id="cust_id" onchange="fillCustInfo()">
                        <option value="">Select Customer</option>
                        <option value="new">+ New Customer (Walk-in)</option>
                        {''.join([f'<option value="{c["_id"]}" data-phone="{c.get("phone","")}" data-addr="{c.get("address","")}">{c["name"]}</option>' for c in customers])}
                    </select>
                </div>
                <div class="input-group"><label>Type</label><select id="inv_type"><option value="invoice">Final Invoice (Sale)</option><option value="quotation">Quotation / Estimate</option></select></div>
            </div>
            <div class="dashboard-grid-3">
                <div class="input-group"><label>Customer Name</label><input type="text" id="c_name"></div>
                <div class="input-group"><label>Phone</label><input type="text" id="c_phone"></div>
                <div class="input-group"><label>Address</label><input type="text" id="c_address"></div>
            </div>
            
            <div style="margin-top:20px; border-top:1px solid #333; padding-top:20px;">
                <table class="dark-table" id="itemTable">
                    <thead><tr><th>Product</th><th>Size</th><th>Price</th><th>Qty</th><th>Total</th><th>X</th></tr></thead>
                    <tbody></tbody>
                </table>
                <button type="button" onclick="addRow()" style="width:auto; margin-top:10px; background:#333;">+ Add Item</button>
            </div>

            <div style="margin-top:30px; display:flex; justify-content:flex-end;">
                <div style="width:300px;">
                    <div class="input-group" style="display:flex; justify-content:space-between; align-items:center;"><label>Sub Total:</label><span id="sub_total">0.00</span></div>
                    <div class="input-group"><label>Discount</label><input type="number" id="discount" value="0" onkeyup="calcTotal()"></div>
                    <div class="input-group" style="border-top:1px solid #555; padding-top:10px;"><label style="font-size:16px; color:white;">Grand Total:</label><span id="grand_total" style="font-size:18px; font-weight:bold; color:var(--accent-orange);">0.00</span></div>
                    <div class="input-group"><label>Paid Amount</label><input type="number" id="paid" value="0" onkeyup="calcTotal()"></div>
                    <div class="input-group"><label>Due</label><span id="due_amount" style="color:var(--accent-red);">0.00</span></div>
                </div>
            </div>
            
            <button type="button" onclick="submitInvoice()" style="margin-top:20px; font-size:16px;">Generate & Print <i class="fas fa-arrow-right"></i></button>
        </form>
    </div>
    <script>
        let products = {json.dumps(products, default=str)};
        function fillCustInfo() {{
            let sel = document.getElementById('cust_id');
            let opt = sel.options[sel.selectedIndex];
            if(sel.value === 'new') {{ document.getElementById('c_name').value=''; }}
            else if(sel.value) {{
                document.getElementById('c_name').value = opt.text;
                document.getElementById('c_phone').value = opt.getAttribute('data-phone');
                document.getElementById('c_address').value = opt.getAttribute('data-addr');
            }}
        }}
        
        function addRow() {{
            let tr = document.createElement('tr');
            let opts = products.map(p=>`<option value='${{JSON.stringify(p)}}'>${{p.name}}</option>`).join('');
            tr.innerHTML = `
                <td><select onchange="setProd(this)" style="padding:8px;">${{opts}}</select></td>
                <td><input type="text" class="i-size" style="padding:8px;"></td>
                <td><input type="number" class="i-price" onkeyup="calcRow(this)" style="padding:8px;"></td>
                <td><input type="number" class="i-qty" value="1" onkeyup="calcRow(this)" style="padding:8px;"></td>
                <td class="i-total">0</td>
                <td><button type="button" onclick="this.parentElement.parentElement.remove();calcTotal()" style="padding:5px; background:red;">x</button></td>
            `;
            document.querySelector('#itemTable tbody').appendChild(tr);
            // Trigger first calc
            setProd(tr.querySelector('select'));
        }}
        
        function setProd(sel) {{
            let row = sel.parentElement.parentElement;
            let p = JSON.parse(sel.value);
            row.querySelector('.i-size').value = p.size || '';
            row.querySelector('.i-price').value = p.price || 0;
            calcRow(sel);
        }}
        
        function calcRow(el) {{
            let row = el.parentElement.parentElement;
            let p = parseFloat(row.querySelector('.i-price').value) || 0;
            let q = parseFloat(row.querySelector('.i-qty').value) || 0;
            row.querySelector('.i-total').innerText = (p*q).toFixed(2);
            calcTotal();
        }}
        
        function calcTotal() {{
            let sub = 0;
            document.querySelectorAll('.i-total').forEach(e => sub += parseFloat(e.innerText));
            document.getElementById('sub_total').innerText = sub.toFixed(2);
            
            let dis = parseFloat(document.getElementById('discount').value) || 0;
            let grand = sub - dis;
            document.getElementById('grand_total').innerText = grand.toFixed(2);
            
            let paid = parseFloat(document.getElementById('paid').value) || 0;
            document.getElementById('due_amount').innerText = (grand - paid).toFixed(2);
        }}
        
        function submitInvoice() {{
            let items = [];
            document.querySelectorAll('#itemTable tbody tr').forEach(r => {{
                items.push({{
                    name: r.querySelector('select').options[r.querySelector('select').selectedIndex].text,
                    size: r.querySelector('.i-size').value,
                    price: r.querySelector('.i-price').value,
                    qty: r.querySelector('.i-qty').value,
                    total: r.querySelector('.i-total').innerText
                }});
            }});
            
            let data = {{
                cust_id: document.getElementById('cust_id').value,
                c_name: document.getElementById('c_name').value,
                c_phone: document.getElementById('c_phone').value,
                c_address: document.getElementById('c_address').value,
                type: document.getElementById('inv_type').value,
                items: items,
                discount: document.getElementById('discount').value,
                paid: document.getElementById('paid').value,
                grand_total: document.getElementById('grand_total').innerText
            }};
            
            fetch('/store/save-invoice', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}})
            .then(r=>r.json()).then(d => {{
                if(d.status === 'success') window.location.href = '/store/print-invoice?inv=' + d.inv_no;
                else alert('Error saving');
            }});
        }}
    </script>
    </body></html>
    """
    return render_template_string(HTML)

@app.route('/store/save-invoice', methods=['POST'])
def store_save_invoice():
    if not session.get('logged_in'): return jsonify({'status': 'error'})
    data = request.json
    
    inv_no = get_next_invoice_number()
    
    # Calculate Due
    grand = float(data['grand_total'])
    paid = float(data.get('paid', 0))
    due = grand - paid
    
    # If New Customer, Save first
    cust_id = data.get('cust_id')
    if cust_id == 'new' or not cust_id:
        cust_id = str(uuid.uuid4())
        save_customer_db({
            "_id": cust_id,
            "name": data['c_name'],
            "phone": data['c_phone'],
            "address": data['c_address'],
            "due": 0.0
        })
    
    # Update Customer Due if it's a FINAL Invoice (Not Quotation)
    if data['type'] == 'invoice':
        update_customer_due_db(cust_id, due)

    invoice_record = {
        "invoice_no": inv_no,
        "date": get_bd_date_str(),
        "date_iso": datetime.now().strftime('%Y-%m-%d'),
        "customer_id": cust_id,
        "customer_name": data['c_name'],
        "customer_phone": data['c_phone'],
        "customer_address": data['c_address'],
        "type": data['type'],
        "items": data['items'],
        "sub_total": float(data['grand_total']) + float(data['discount']), # Approx reverse
        "discount": data['discount'],
        "grand_total": grand,
        "paid": paid,
        "due": due,
        "status": "Paid" if due <= 0 else "Due",
        "created_by": session.get('user')
    }
    save_invoice_db(invoice_record)
    
    return jsonify({'status': 'success', 'inv_no': inv_no})

@app.route('/store/print-invoice')
def store_print_invoice():
    inv_no = request.args.get('inv')
    inv = get_invoice(inv_no)
    if not inv: return "Invoice Not Found"
    
    # Simple Number to Words (Basic implementation)
    try:
        # Just a placeholder, for real production use 'num2words' library
        inv['in_words'] = f"{int(inv['grand_total'])} Taka" 
    except: pass
    
    return render_template_string(STORE_INVOICE_TEMPLATE, invoice=inv)

@app.route('/store/get-invoice-due')
def store_get_invoice_due():
    inv_no = request.args.get('inv')
    inv = get_invoice(inv_no)
    if inv and inv['due'] > 0 and inv['type'] == 'invoice':
        return jsonify({'status': 'found', 'data': {'invoice_no': inv['invoice_no'], 'customer_name': inv['customer_name'], 'due': inv['due']}})
    return jsonify({'status': 'not_found'})

@app.route('/store/pay-due', methods=['POST'])
def store_pay_due():
    if not session.get('logged_in'): return jsonify({'status': 'error'})
    data = request.json
    inv_no = data.get('inv')
    amount = float(data.get('amount'))
    
    inv = get_invoice(inv_no)
    if inv:
        # Update Invoice
        new_paid = inv['paid'] + amount
        new_due = inv['due'] - amount
        store_invoices_col.update_one({"invoice_no": inv_no}, {"$set": {"paid": new_paid, "due": new_due, "status": "Paid" if new_due <= 0 else "Due"}})
        
        # Update Customer Total Due (Subtract payment)
        update_customer_due_db(inv['customer_id'], -amount)
        
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
