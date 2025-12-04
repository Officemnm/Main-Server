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

# --- Custom Filter for Numbers (To fix f-string errors) ---
@app.template_filter('comma')
def comma_filter(value):
    try:
        return "{:,.0f}".format(float(value))
    except:
        return value

# ==============================================================================
# কনফিগারেশন এবং সেটআপ
# ==============================================================================

# PO ফাইলের জন্য আপলোড ফোল্ডার
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# সেশন টাইমআউট কনফিগারেশন (2 মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2) 

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
    
    # Store related collections
    store_users_col = db['store_users']
    store_products_col = db['store_products']
    store_customers_col = db['store_customers']
    store_invoices_col = db['store_invoices']
    store_estimates_col = db['store_estimates']
    store_payments_col = db['store_payments']
    
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
    # Analytics এর জন্য ডাটা লিমিট বাড়ানো হয়েছে
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
# Store Helper Functions
# ==============================================================================

def load_store_users():
    record = store_users_col.find_one({"_id": "store_users_data"})
    default_users = {
        "StoreAdmin": {
            "password": "store123", 
            "role": "store_admin", 
            "permissions": ["products", "customers", "invoices", "estimates", "payments", "user_manage"],
            "created_at": get_bd_date_str(),
            "last_login": "Never"
        }
    }
    if record:
        return record['data']
    else:
        store_users_col.insert_one({"_id": "store_users_data", "data": default_users})
        return default_users

def save_store_users(users_data):
    store_users_col.replace_one(
        {"_id": "store_users_data"}, 
        {"_id": "store_users_data", "data": users_data}, 
        upsert=True
    )

def load_store_products():
    record = store_products_col.find_one({"_id": "products_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_products(products):
    store_products_col.replace_one(
        {"_id": "products_data"},
        {"_id": "products_data", "data": products},
        upsert=True
    )

def load_store_customers():
    record = store_customers_col.find_one({"_id": "customers_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_customers(customers):
    store_customers_col.replace_one(
        {"_id": "customers_data"},
        {"_id": "customers_data", "data": customers},
        upsert=True
    )

def load_store_invoices():
    record = store_invoices_col.find_one({"_id": "invoices_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_invoices(invoices):
    store_invoices_col.replace_one(
        {"_id": "invoices_data"},
        {"_id": "invoices_data", "data": invoices},
        upsert=True
    )

def load_store_estimates():
    record = store_estimates_col.find_one({"_id": "estimates_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_estimates(estimates):
    store_estimates_col.replace_one(
        {"_id": "estimates_data"},
        {"_id": "estimates_data", "data": estimates},
        upsert=True
    )

def load_store_payments():
    record = store_payments_col.find_one({"_id": "payments_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_payments(payments):
    store_payments_col.replace_one(
        {"_id": "payments_data"},
        {"_id": "payments_data", "data": payments},
        upsert=True
    )

def generate_invoice_number():
    invoices = load_store_invoices()
    if not invoices:
        return "INV-0001"
    last_num = 0
    for inv in invoices:
        try:
            num = int(inv['invoice_no'].split('-')[1])
            if num > last_num:
                last_num = num
        except:
            pass
    return f"INV-{str(last_num + 1).zfill(4)}"

def generate_estimate_number():
    estimates = load_store_estimates()
    if not estimates:
        return "EST-0001"
    last_num = 0
    for est in estimates:
        try:
            num = int(est['estimate_no'].split('-')[1])
            if num > last_num:
                last_num = num
        except:
            pass
    return f"EST-{str(last_num + 1).zfill(4)}"

# --- আপডেটেড: রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স ---
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

    # 2.  Accessories Today & Analytics - LIFETIME COUNT
    acc_lifetime_count = 0
    acc_today_list = []
    
    # Analytics Container: {'YYYY-MM-DD': {'label': '01-Dec', 'closing': 0, 'po': 0, 'acc': 0}}
    daily_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0})

    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            acc_lifetime_count += 1  # LIFETIME COUNT
            c_date = challan.get('date')
            if c_date == today_str:
                acc_today_list.append({
                    "ref": ref,
                    "buyer": data.get('buyer'),
                    "style": data.get('style'),
                    "time": "Today", 
                    "qty": challan.get('qty')
                })
            
            # Analytics Calculation - Daily basis
            try:
                dt_obj = datetime.strptime(c_date, '%d-%m-%Y')
                sort_key = dt_obj.strftime('%Y-%m-%d')
                daily_data[sort_key]['acc'] += 1
                daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
            except: pass

    # 3.  Closing & PO - LIFETIME COUNT & Analytics
    closing_lifetime_count = 0
    po_lifetime_count = 0
    closing_list = []
    po_list = []
    
    history = stats_data.get('downloads', [])
    for item in history:
        item_date = item.get('date', '')
        if item.get('type') == 'PO Sheet':
            po_lifetime_count += 1  # LIFETIME COUNT
            if item_date == today_str:
                po_list.append(item)
        else: 
            closing_lifetime_count += 1  # LIFETIME COUNT
            if item_date == today_str:
                closing_list.append(item)
        
        # Analytics Calculation - Daily basis
        try:
            dt_obj = datetime.strptime(item_date, '%d-%m-%Y')
            sort_key = dt_obj.strftime('%Y-%m-%d')
            
            if item.get('type') == 'PO Sheet':
                daily_data[sort_key]['po'] += 1
            else:
                daily_data[sort_key]['closing'] += 1
            daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
        except: pass

    # Get last month's 1st date to today
    first_of_last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    start_date = first_of_last_month.strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    # Filter and sort data from start_date to end_date
    sorted_keys = sorted([k for k in daily_data.keys() if start_date <= k <= end_date])
    
    chart_labels = []
    chart_closing = []
    chart_po = []
    chart_acc = []

    if not sorted_keys:
        curr_d = now.strftime('%d-%b')
        chart_labels = [curr_d]
        chart_closing = [0]
        chart_po = [0]
        chart_acc = [0]
    else:
        for k in sorted_keys:
            d = daily_data[k]
            chart_labels.append(d.get('label', k))
            chart_closing.append(d['closing'])
            chart_po.append(d['po'])
            chart_acc.append(d['acc'])

    return {
        "users": { "count": len(users_data), "details": user_details },
        "accessories": { "count": acc_lifetime_count, "details": acc_today_list },
        "closing": { "count": closing_lifetime_count, "details": closing_list },
        "po": { "count": po_lifetime_count, "details": po_list },
        "chart": {
            "labels": chart_labels,
            "closing": chart_closing,
            "po": chart_po,
            "acc": chart_acc
        },
        "history": history
    }

def get_store_dashboard_summary():
    products = load_store_products()
    customers = load_store_customers()
    invoices = load_store_invoices()
    estimates = load_store_estimates()
    
    # Calculate total sales this month
    now = get_bd_time()
    current_month = now.strftime('%m-%Y')
    monthly_sales = 0
    total_due = 0
    
    for inv in invoices:
        inv_date = inv.get('date', '')
        try:
            if inv_date.split('-')[1] + '-' + inv_date.split('-')[2] == current_month:
                monthly_sales += inv.get('total', 0)
        except:
            pass
        total_due += inv.get('due', 0)
    
    return {
        "products_count": len(products),
        "customers_count": len(customers),
        "invoices_count": len(invoices),
        "estimates_count": len(estimates),
        "monthly_sales": monthly_sales,
        "total_due": total_due
    }
    # ==============================================================================
# ENHANCED CSS STYLES - PREMIUM MODERN UI WITH ANIMATIONS
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
    <script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
    <style>
        :root {
            --bg-body: #0a0a0f;
            --bg-sidebar: #12121a;
            --bg-card: #16161f;
            --bg-card-hover: #1a1a25;
            --text-primary: #FFFFFF;
            --text-secondary: #8b8b9e;
            --accent-orange: #FF7A00;
            --accent-orange-light: #FF9A40;
            --accent-orange-dark: #E56D00;
            --accent-orange-glow: rgba(255, 122, 0, 0.3);
            --accent-purple: #8B5CF6;
            --accent-green: #10B981;
            --accent-red: #EF4444;
            --accent-blue: #3B82F6;
            --accent-cyan: #06B6D4;
            --border-color: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(255, 122, 0, 0.2);
            --card-radius: 16px;
            --transition-smooth: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
            --shadow-glow: 0 0 40px rgba(255, 122, 0, 0.15);
            --gradient-orange: linear-gradient(135deg, #FF7A00 0%, #FF9A40 100%);
            --gradient-dark: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
            --gradient-card: linear-gradient(145deg, rgba(22, 22, 31, 0.9) 0%, rgba(16, 16, 22, 0.95) 100%);
        }

        * { 
            margin: 0;
            padding: 0; 
            box-sizing: border-box; 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-body); }
        ::-webkit-scrollbar-thumb { background: var(--accent-orange); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-orange-light); }
        
        body {
            background: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
            position: relative;
        }

        /* Particle Background */
        #particles-js {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }

        /* Animated Gradient Background */
        .animated-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(255, 122, 0, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(16, 185, 129, 0.04) 0%, transparent 70%);
            z-index: 0;
            animation: bgPulse 15s ease-in-out infinite;
        }

        @keyframes bgPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.05); }
        }

        /* Glassmorphism Effect */
        .glass {
            background: rgba(22, 22, 31, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
        }

        /* Enhanced Sidebar Styling */
        .sidebar {
            width: 280px;
            height: 100vh; 
            background: var(--gradient-dark);
            position: fixed; 
            top: 0; 
            left: 0; 
            display: flex; 
            flex-direction: column;
            padding: 30px 20px;
            border-right: 1px solid var(--border-color); 
            z-index: 1000;
            transition: var(--transition-smooth);
            box-shadow: 4px 0 30px rgba(0, 0, 0, 0.3);
        }
        .sidebar::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 1px;
            height: 100%;
            background: linear-gradient(180deg, transparent, var(--accent-orange), transparent);
            opacity: 0.3;
        }

        .brand-logo { 
            font-size: 26px;
            font-weight: 900; 
            color: white; 
            margin-bottom: 50px; 
            display: flex; 
            align-items: center; 
            gap: 12px; 
            padding: 0 10px;
            position: relative;
        }

        .brand-logo span { 
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .brand-logo i {
            font-size: 28px;
            color: var(--accent-orange);
            filter: drop-shadow(0 0 10px var(--accent-orange-glow));
            animation: logoFloat 3s ease-in-out infinite;
        }

        @keyframes logoFloat {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-5px) rotate(5deg); }
        }
        
        .nav-menu { 
            flex-grow: 1; 
            display: flex; 
            flex-direction: column;
            gap: 8px; 
        }

        .nav-link {
            display: flex;
            align-items: center; 
            padding: 14px 18px; 
            color: var(--text-secondary);
            text-decoration: none; 
            border-radius: 12px; 
            transition: var(--transition-smooth);
            cursor: pointer; 
            font-weight: 500; 
            font-size: 14px;
            position: relative;
            overflow: hidden;
        }

        .nav-link::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            width: 0;
            height: 100%;
            background: linear-gradient(90deg, var(--accent-orange-glow), transparent);
            transition: var(--transition-smooth);
            z-index: -1;
        }
        .nav-link:hover::before, .nav-link.active::before { width: 100%; }

        .nav-link:hover, .nav-link.active { 
            color: var(--accent-orange); 
            transform: translateX(5px);
        }

        .nav-link.active {
            background: rgba(255, 122, 0, 0.1);
            border-left: 3px solid var(--accent-orange);
            box-shadow: 0 0 20px var(--accent-orange-glow);
        }

        .nav-link i { 
            width: 24px;
            margin-right: 12px; 
            font-size: 18px; 
            text-align: center;
            transition: var(--transition-smooth);
        }

        .nav-link:hover i {
            transform: scale(1.2);
            filter: drop-shadow(0 0 8px var(--accent-orange));
        }

        .nav-link .nav-badge {
            margin-left: auto;
            background: var(--accent-orange);
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 700;
            animation: badgePulse 2s ease-in-out infinite;
        }
        @keyframes badgePulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }

        .sidebar-footer {
            margin-top: auto;
            padding-top: 20px; 
            border-top: 1px solid var(--border-color);
            text-align: center; 
            font-size: 11px; 
            color: var(--text-secondary); 
            font-weight: 500; 
            opacity: 0.5;
            letter-spacing: 1px;
        }

        /* Main Content */
        .main-content { 
            margin-left: 280px;
            width: calc(100% - 280px); 
            padding: 30px 40px; 
            position: relative;
            z-index: 1;
            min-height: 100vh;
        }

        .header-section { 
            display: flex;
            justify-content: space-between; 
            align-items: flex-start; 
            margin-bottom: 35px;
            animation: fadeInDown 0.6s ease-out;
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .page-title { 
            font-size: 32px;
            font-weight: 800; 
            color: white; 
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, #ccc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .page-subtitle { 
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 400;
        }

        /* ============================================= */
        /* FIXED: Status Badge with Glowing Green Dot   */
        /* ============================================= */
        .status-badge {
            background: var(--bg-card);
            padding: 12px 24px;
            border-radius: 50px;
            border: 1px solid var(--border-color);
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: var(--shadow-card);
            transition: var(--transition-smooth);
        }
        
        .status-badge:hover {
            border-color: rgba(16, 185, 129, 0.3);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
        }
        
        /* FIXED: Glowing Green Status Dot */
        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            position: relative;
            animation: statusGlow 2s ease-in-out infinite;
            box-shadow: 
                0 0 5px var(--accent-green),
                0 0 10px var(--accent-green),
                0 0 20px var(--accent-green),
                0 0 30px rgba(16, 185, 129, 0.5);
        }
        
        .status-dot::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 100%;
            height: 100%;
            background: var(--accent-green);
            border-radius: 50%;
            animation: statusPulseRing 2s ease-out infinite;
        }
        
        .status-dot::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 6px;
            height: 6px;
            background: #fff;
            border-radius: 50%;
            opacity: 0.8;
        }
        
        @keyframes statusGlow {
            0%, 100% { 
                opacity: 1;
                box-shadow: 
                    0 0 5px var(--accent-green),
                    0 0 10px var(--accent-green),
                    0 0 20px var(--accent-green),
                    0 0 30px rgba(16, 185, 129, 0.5);
            }
            50% { 
                opacity: 0.8;
                box-shadow: 
                    0 0 10px var(--accent-green),
                    0 0 20px var(--accent-green),
                    0 0 40px var(--accent-green),
                    0 0 60px rgba(16, 185, 129, 0.6);
            }
        }
        
        @keyframes statusPulseRing {
            0% {
                transform: translate(-50%, -50%) scale(1);
                opacity: 0.8;
            }
            100% {
                transform: translate(-50%, -50%) scale(2.5);
                opacity: 0;
            }
        }
        /* ============================================= */
        
        /* Enhanced Cards & Grid */
        .stats-grid { 
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); 
            gap: 24px; 
            margin-bottom: 35px;
        }

        .dashboard-grid-2 { 
            display: grid;
            grid-template-columns: 2fr 1fr; 
            gap: 24px; 
            margin-bottom: 24px; 
        }

        .card { 
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 28px;
            backdrop-filter: blur(10px);
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent-orange-glow), transparent);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .card:hover {
            border-color: var(--border-glow);
            box-shadow: var(--shadow-glow);
            transform: translateY(-4px);
        }

        .card:hover::before { opacity: 1; }
        
        .section-header { 
            display: flex;
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 24px; 
            font-weight: 700;
            font-size: 16px; 
            color: white;
            letter-spacing: -0.3px;
        }

        .section-header i {
            font-size: 20px;
            opacity: 0.7;
            transition: var(--transition-smooth);
        }

        .card:hover .section-header i {
            opacity: 1;
            transform: rotate(10deg) scale(1.1);
        }
        
        /* Stat Cards with Animations */
        .stat-card { 
            display: flex;
            align-items: center; 
            gap: 24px; 
            transition: var(--transition-smooth);
            cursor: pointer;
        }

        .stat-card:hover { 
            transform: translateY(-6px) scale(1.02);
        }

        .stat-icon { 
            width: 64px;
            height: 64px; 
            background: linear-gradient(145deg, rgba(255, 122, 0, 0.15), rgba(255, 122, 0, 0.05));
            border-radius: 16px; 
            display: flex; 
            justify-content: center; 
            align-items: center;
            font-size: 26px; 
            color: var(--accent-orange);
            position: relative;
            overflow: hidden;
            transition: var(--transition-smooth);
        }

        .stat-icon::after {
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            background: var(--gradient-orange);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .stat-card:hover .stat-icon {
            transform: rotate(-10deg) scale(1.1);
            box-shadow: 0 0 30px var(--accent-orange-glow);
        }

        .stat-card:hover .stat-icon i {
            animation: iconBounce 0.5s ease-out;
        }

        @keyframes iconBounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.3); }
        }

        .stat-info h3 { 
            font-size: 36px;
            font-weight: 800; 
            margin: 0; 
            color: white;
            letter-spacing: -1px;
            line-height: 1;
            background: linear-gradient(135deg, #fff 0%, var(--accent-orange-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .stat-info p { 
            font-size: 13px;
            color: var(--text-secondary); 
            margin: 6px 0 0 0; 
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }

        /* Animated Counter */
        .count-up {
            display: inline-block;
        }
                /* Progress Bars with Animation */
        .progress-item { margin-bottom: 24px; }

        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 14px;
            color: white;
            font-weight: 500;
        }

        .progress-value {
            color: var(--text-secondary);
            font-weight: 600;
        }

        .progress-bar-container {
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .progress-bar-fill {
            height: 100%;
            border-radius: 10px;
            position: relative;
            animation: progressFill 1.5s ease-out forwards;
            transform-origin: left;
        }

        .progress-bar-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }

        @keyframes progressFill {
            from { transform: scaleX(0); }
            to { transform: scaleX(1); }
        }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .progress-orange { background: var(--gradient-orange); }
        .progress-purple { background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); }
        .progress-green { background: linear-gradient(135deg, #10B981 0%, #34D399 100%); }
        
        /* Enhanced Forms */
        .input-group { margin-bottom: 20px; }

        .input-group label { 
            display: block;
            font-size: 11px; 
            color: var(--text-secondary); 
            margin-bottom: 8px; 
            text-transform: uppercase; 
            font-weight: 700;
            letter-spacing: 1.5px;
        }

        input, select, textarea { 
            width: 100%;
            padding: 14px 18px; 
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 12px; 
            color: white; 
            font-size: 15px; 
            font-weight: 500;
            outline: none; 
            transition: var(--transition-smooth);
        }
        
        textarea {
            min-height: 100px;
            resize: vertical;
        }

        input::placeholder, textarea::placeholder {
            color: var(--text-secondary);
            opacity: 0.5;
        }

        input:focus, select:focus, textarea:focus { 
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
            box-shadow: 0 0 0 4px var(--accent-orange-glow), 0 0 20px var(--accent-orange-glow);
        }

        select {
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='%23FF7A00' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 24px;
            background-color: rgba(255, 255, 255, 0.03);
        }
        
        select option {
            background-color: #1a1a25;
            color: white;
            padding: 10px;
        }
        
        button, .btn-primary { 
            width: 100%;
            padding: 14px 24px; 
            background: var(--gradient-orange);
            color: white; 
            border: none; 
            border-radius: 12px; 
            font-weight: 700;
            font-size: 15px;
            cursor: pointer; 
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
            letter-spacing: 0.5px;
        }
        
        button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: 0.5s;
        }

        button:hover::before { left: 100%; }

        button:hover { 
            transform: translateY(-3px);
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }

        button:active {
            transform: translateY(0);
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--accent-orange);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
        }
        
        .btn-success:hover {
            box-shadow: 0 10px 30px rgba(16, 185, 129, 0.3);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #EF4444 0%, #F87171 100%);
        }
        
        .btn-danger:hover {
            box-shadow: 0 10px 30px rgba(239, 68, 68, 0.3);
        }
        
        .btn-purple {
            background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);
        }
        
        .btn-purple:hover {
            box-shadow: 0 10px 30px rgba(139, 92, 246, 0.3);
        }
        
        .btn-sm {
            padding: 8px 16px;
            font-size: 13px;
            width: auto;
        }

        /* Enhanced Tables */
        .dark-table { 
            width: 100%;
            border-collapse: collapse; 
            margin-top: 10px; 
        }

        .dark-table th { 
            text-align: left;
            padding: 14px 16px; 
            color: var(--text-secondary); 
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-bottom: 1px solid var(--border-color);
            font-weight: 700;
        }

        .dark-table td { 
            padding: 16px;
            color: white; 
            font-size: 14px; 
            border-bottom: 1px solid rgba(255,255,255,0.03);
            vertical-align: middle;
            transition: var(--transition-smooth);
        }

        .dark-table tr {
            transition: var(--transition-smooth);
        }

        .dark-table tr:hover td { 
            background: rgba(255, 122, 0, 0.03);
        }

        .table-badge {
            background: rgba(255,255,255,0.05);
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        /* Action Buttons */
        .action-cell { 
            display: flex;
            gap: 8px; 
            justify-content: flex-end; 
        }

        .action-btn { 
            padding: 8px 12px;
            border-radius: 8px; 
            text-decoration: none; 
            font-size: 12px; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            cursor: pointer; 
            border: none; 
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
        }

        .btn-edit { 
            background: rgba(139, 92, 246, 0.15);
            color: #A78BFA; 
        }

        .btn-edit:hover { 
            background: var(--accent-purple);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.4);
        }

        .btn-del { 
            background: rgba(239, 68, 68, 0.15);
            color: #F87171; 
        }

        .btn-del:hover { 
            background: var(--accent-red);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
        }
        
        .btn-view {
            background: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
        }
        
        .btn-view:hover {
            background: var(--accent-blue);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
        }
        
        .btn-print-sm {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
        }
        
        .btn-print-sm:hover {
            background: var(--accent-green);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
        }
        
        /* Enhanced Loading Overlay */
        #loading-overlay { 
            display: none;
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(10, 10, 15, 0.95);
            z-index: 9999; 
            flex-direction: column;
            justify-content: center; 
            align-items: center; 
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        
        /* Modern Spinner */
        .spinner-container {
            position: relative;
            width: 80px;
            height: 80px;
        }

        .spinner { 
            width: 80px;
            height: 80px; 
            border: 4px solid rgba(255, 122, 0, 0.1);
            border-top: 4px solid var(--accent-orange);
            border-right: 4px solid var(--accent-orange-light);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            box-shadow: 0 0 30px var(--accent-orange-glow);
        }

        .spinner-inner {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 3px solid rgba(139, 92, 246, 0.1);
            border-bottom: 3px solid var(--accent-purple);
            border-left: 3px solid var(--accent-purple);
            border-radius: 50%;
            animation: spin 1.2s linear infinite reverse;
        }

        @keyframes spin { 
            0% { transform: rotate(0deg); } 
            100% { transform: rotate(360deg); } 
        }

        /* Success Checkmark Animation */
        .checkmark-container { 
            display: none;
            text-align: center; 
        }

        .checkmark-circle {
            width: 100px;
            height: 100px; 
            position: relative; 
            display: inline-block;
            border-radius: 50%; 
            border: 3px solid var(--accent-green);
            margin-bottom: 24px;
            animation: success-anim 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            box-shadow: 0 0 40px rgba(16, 185, 129, 0.3);
        }

        .checkmark-circle::before {
            content: '';
            display: block; 
            width: 30px; 
            height: 50px;
            border: solid var(--accent-green); 
            border-width: 0 4px 4px 0;
            position: absolute; 
            top: 15px; 
            left: 35px;
            transform: rotate(45deg); 
            opacity: 0;
            animation: checkmark-anim 0.4s 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }
        
        /* Fail Cross Animation */
        .fail-container { 
            display: none; 
            text-align: center;
        }

        .fail-circle {
            width: 100px;
            height: 100px; 
            position: relative; 
            display: inline-block;
            border-radius: 50%; 
            border: 3px solid var(--accent-red);
            margin-bottom: 24px;
            animation: fail-anim 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.3);
        }

        .fail-circle::before, .fail-circle::after {
            content: '';
            position: absolute; 
            width: 4px; 
            height: 50px; 
            background: var(--accent-red);
            top: 23px; 
            left: 46px; 
            border-radius: 4px;
            animation: crossAnim 0.3s 0.4s ease-out forwards;
            opacity: 0;
        }

        .fail-circle::before { transform: rotate(45deg); }
        .fail-circle::after { transform: rotate(-45deg); }

        @keyframes success-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1.2); } 
            100% { transform: scale(1); opacity: 1; } 
        }

        @keyframes checkmark-anim { 
            0% { opacity: 0; height: 0; width: 0; } 
            100% { opacity: 1; height: 50px; width: 30px; } 
        }

        @keyframes fail-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1.2); } 
            100% { transform: scale(1); opacity: 1; } 
        }

        @keyframes crossAnim {
            0% { opacity: 0; transform: rotate(45deg) scale(0); }
            100% { opacity: 1; transform: rotate(45deg) scale(1); }
        }

        .anim-text { 
            font-size: 24px; 
            font-weight: 800; 
            color: white;
            margin-top: 10px; 
            letter-spacing: 1px;
        }

        .loading-text {
            color: var(--text-secondary);
            font-size: 15px;
            margin-top: 20px;
            font-weight: 500;
            letter-spacing: 2px;
            text-transform: uppercase;
            animation: textPulse 1.5s ease-in-out infinite;
        }

        @keyframes textPulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }
                /* Welcome Popup Modal */
        .welcome-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            z-index: 10000;
            justify-content: center;
            align-items: center;
            animation: modalFadeIn 0.3s ease-out;
        }

        @keyframes modalFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .welcome-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 50px 60px;
            text-align: center;
            max-width: 500px;
            width: 90%;
            animation: welcomeSlideIn 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            position: relative;
            overflow: hidden;
        }

        .welcome-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, var(--accent-orange-glow) 0%, transparent 60%);
            animation: welcomeGlow 3s ease-in-out infinite;
            opacity: 0.3;
        }
        
        @keyframes welcomeSlideIn {
            from { 
                opacity: 0;
                transform: translateY(-50px) scale(0.9);
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        @keyframes welcomeGlow {
            0%, 100% { transform: rotate(0deg); }
            50% { transform: rotate(180deg); }
        }

        .welcome-icon {
            font-size: 80px;
            margin-bottom: 20px;
            display: inline-block;
            animation: welcomeIconBounce 1s ease-out;
        }

        @keyframes welcomeIconBounce {
            0% { transform: scale(0) rotate(-180deg); }
            60% { transform: scale(1.2) rotate(10deg); }
            100% { transform: scale(1) rotate(0deg); }
        }

        .welcome-greeting {
            font-size: 16px;
            color: var(--accent-orange);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 10px;
        }

        .welcome-title {
            font-size: 36px;
            font-weight: 900;
            color: white;
            margin-bottom: 15px;
            line-height: 1.2;
        }

        .welcome-title span {
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .welcome-message {
            color: var(--text-secondary);
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 30px;
        }

        .welcome-close {
            background: var(--gradient-orange);
            color: white;
            border: none;
            padding: 14px 40px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: var(--transition-smooth);
            position: relative;
            z-index: 1;
        }

        .welcome-close:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px var(--accent-orange-glow);
        }

        /* Tooltip */
        .tooltip {
            position: relative;
        }

        .tooltip::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 120%;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-card);
            color: white;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: var(--transition-smooth);
            border: 1px solid var(--border-color);
            z-index: 1000;
        }

        .tooltip:hover::after {
            opacity: 1;
            visibility: visible;
            bottom: 130%;
        }
        
        /* File Upload Zone */
        .upload-zone {
            border: 2px dashed var(--border-color);
            padding: 50px;
            text-align: center;
            border-radius: 16px;
            transition: var(--transition-smooth);
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }

        .upload-zone::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--gradient-orange);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .upload-zone:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .upload-zone:hover::before {
            opacity: 0.03;
        }

        .upload-zone.dragover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 60px;
            color: var(--accent-orange);
            margin-bottom: 20px;
            display: inline-block;
            animation: uploadFloat 3s ease-in-out infinite;
        }

        @keyframes uploadFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        .upload-text {
            color: var(--accent-orange);
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 8px;
        }

        .upload-hint {
            color: var(--text-secondary);
            font-size: 13px;
        }

        #file-count {
            margin-top: 20px;
            font-size: 14px;
            color: var(--accent-green);
            font-weight: 600;
        }

        /* Flash Messages */
        .flash-message {
            margin-bottom: 20px;
            padding: 16px 20px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
            animation: flashSlideIn 0.4s ease-out;
        }

        @keyframes flashSlideIn {
            from { 
                opacity: 0;
                transform: translateY(-10px);
            }
            to { 
                opacity: 1;
                transform: translateY(0);
            }
        }

        .flash-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #F87171;
        }

        .flash-success {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #34D399;
        }
        
        .flash-warning {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            color: #FBBF24;
        }
        
        /* Ripple Effect */
        .ripple {
            position: relative;
            overflow: hidden;
        }

        .ripple-effect {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: scale(0);
            animation: rippleAnim 0.6s ease-out;
            pointer-events: none;
        }

        @keyframes rippleAnim {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        
        /* Mobile Toggle & Responsive */
        .mobile-toggle { 
            display: none; 
            position: fixed; 
            top: 20px;
            right: 20px; 
            z-index: 2000; 
            color: white; 
            background: var(--bg-card);
            padding: 12px 14px; 
            border-radius: 12px;
            border: 1px solid var(--border-color);
            cursor: pointer;
            transition: var(--transition-smooth);
        }

        .mobile-toggle:hover {
            background: var(--accent-orange);
        }

        @media (max-width: 1024px) {
            .sidebar { 
                transform: translateX(-100%);
                width: 280px;
            } 
            .sidebar.active { 
                transform: translateX(0);
            }
            .main-content { 
                margin-left: 0;
                width: 100%; 
                padding: 20px; 
            }
            .dashboard-grid-2 { 
                grid-template-columns: 1fr;
            }
            .mobile-toggle { 
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .header-section {
                flex-direction: column;
                gap: 15px;
            }
        }

        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .page-title {
                font-size: 24px;
            }
            .welcome-content {
                padding: 40px 30px;
            }
            .welcome-title {
                font-size: 28px;
            }
        }

        /* Skeleton Loading */
        .skeleton {
            background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%);
            background-size: 200% 100%;
            animation: skeletonLoad 1.5s infinite;
            border-radius: 8px;
        }

        @keyframes skeletonLoad {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        /* Notification Dot */
        .notification-dot {
            position: absolute;
            top: -2px;
            right: -2px;
            width: 10px;
            height: 10px;
            background: var(--accent-red);
            border-radius: 50%;
            border: 2px solid var(--bg-sidebar);
            animation: notifyPulse 2s infinite;
        }

        @keyframes notifyPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }

        /* Chart Container */
        .chart-container {
            position: relative;
            height: 280px;
            padding: 10px;
        }

        /* Real-time Indicator */
        .realtime-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-secondary);
            padding: 6px 12px;
            background: rgba(16, 185, 129, 0.1);
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .realtime-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: realtimePulse 1s infinite;
        }

        @keyframes realtimePulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        }

        /* Floating Action Button */
        .fab {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            background: var(--gradient-orange);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
            cursor: pointer;
            box-shadow: 0 8px 30px var(--accent-orange-glow);
            transition: var(--transition-smooth);
            z-index: 100;
        }

        .fab:hover {
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 12px 40px var(--accent-orange-glow);
        }
        
        /* Glow Text */
        .glow-text {
            text-shadow: 0 0 20px var(--accent-orange-glow);
        }

        /* Animated Border */
        .animated-border {
            position: relative;
        }

        .animated-border::after {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, var(--accent-orange), var(--accent-purple), var(--accent-green), var(--accent-orange));
            background-size: 400% 400%;
            border-radius: inherit;
            z-index: -1;
            animation: gradientBorder 3s ease infinite;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .animated-border:hover::after {
            opacity: 1;
        }

        @keyframes gradientBorder {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Permission Checkbox Styles */
        .perm-checkbox {
            background: rgba(255, 255, 255, 0.03);
            padding: 14px 18px;
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            border: 1px solid var(--border-color);
            transition: var(--transition-smooth);
            flex: 1;
            min-width: 100px;
        }

        .perm-checkbox:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .perm-checkbox input {
            width: auto;
            margin-right: 10px;
            accent-color: var(--accent-orange);
        }

        .perm-checkbox span {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }

        .perm-checkbox:has(input:checked) {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
        }

        .perm-checkbox:has(input:checked) span {
            color: var(--accent-orange);
        }

        /* Time Badge */
        .time-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.03);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .time-badge i {
            color: var(--accent-orange);
        }
        
        /* Grid Layouts for Store */
        .grid-2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }
        
        .grid-3 {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        
        .grid-4 {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }
        
        @media (max-width: 768px) {
            .grid-2, .grid-3, .grid-4 {
                grid-template-columns: 1fr;
            }
        }
        
        /* Modal Overlay */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            z-index: 9000;
            justify-content: center;
            align-items: center;
        }
        
        .modal-overlay.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            animation: modalSlideIn 0.3s ease-out;
        }
        
        @keyframes modalSlideIn {
            from {
                opacity: 0;
                transform: translateY(-30px) scale(0.95);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-title {
            font-size: 22px;
            font-weight: 700;
            color: white;
        }
        
        .modal-close {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition-smooth);
        }
        
        .modal-close:hover {
            background: var(--accent-red);
            color: white;
            border-color: var(--accent-red);
        }
        
        /* Search Box */
        .search-box {
            position: relative;
            margin-bottom: 20px;
        }
        
        .search-box input {
            padding-left: 45px;
        }
        
        .search-box i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }
        
        /* Tab Navigation */
        .tab-nav {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        
        .tab-btn {
            padding: 10px 20px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: var(--transition-smooth);
        }
        
        .tab-btn:hover {
            color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
        }
        
        .tab-btn.active {
            color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.15);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        /* Amount Display */
        .amount-display {
            font-size: 28px;
            font-weight: 800;
            color: var(--accent-green);
        }
        
        .amount-due {
            color: var(--accent-red);
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state i {
            font-size: 60px;
            opacity: 0.2;
            margin-bottom: 20px;
            display: block;
        }
        
        .empty-state p {
            font-size: 16px;
            margin-bottom: 20px;
        }
    </style>
"""
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

    booking_block_match = re.search(r"(?:Internal )?Booking NO\. ?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match: 
        raw_booking = booking_block_match.group(1).strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking: clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\. ?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match: meta['style'] = style_match.group(1).strip()
    else:
        style_match = re.search(r"Style Des\. ?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match: meta['style'] = style_match.group(1).strip()

    season_match = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re.IGNORECASE)
    if season_match: meta['season'] = season_match.group(1).strip()
    dept_match = re.search(r"Dept\. ?[\s\n:]*([A-Za-z]+)", first_page_text, re.IGNORECASE)
    if dept_match: meta['dept'] = dept_match.group(1).strip()

    item_match = re.search(r"Garments?    Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
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
                all_report_data.append({
                    'style': style, 'buyer': buyer_name, 'color': color, 
                    'headers': headers, 'gmts_qty': gmts_qty_data, 
                    'plus_3_percent': plus_3_percent_data, 
                    'sewing_input': sewing_input_data if sewing_input_data else [], 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
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
    
    left_sub_headers = {
        'A4': 'BUYER', 'B4': report_data[0].get('buyer', ''), 
        'A5': 'IR/IB NO', 'B5': formatted_ref_no, 
        'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')
    }
    
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
# ENHANCED CSS STYLES - PREMIUM MODERN UI WITH ANIMATIONS
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min.js"></script>
    <script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
    <style>
        :root {
            --bg-body: #0a0a0f;
            --bg-sidebar: #12121a;
            --bg-card: #16161f;
            --bg-card-hover: #1a1a25;
            --text-primary: #FFFFFF;
            --text-secondary: #8b8b9e;
            --accent-orange: #FF7A00;
            --accent-orange-light: #FF9A40;
            --accent-orange-dark: #E56D00;
            --accent-orange-glow: rgba(255, 122, 0, 0.3);
            --accent-purple: #8B5CF6;
            --accent-green: #10B981;
            --accent-red: #EF4444;
            --accent-blue: #3B82F6;
            --accent-cyan: #06B6D4;
            --border-color: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(255, 122, 0, 0.2);
            --card-radius: 16px;
            --transition-smooth: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
            --shadow-glow: 0 0 40px rgba(255, 122, 0, 0.15);
            --gradient-orange: linear-gradient(135deg, #FF7A00 0%, #FF9A40 100%);
            --gradient-dark: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
            --gradient-card: linear-gradient(145deg, rgba(22, 22, 31, 0.9) 0%, rgba(16, 16, 22, 0.95) 100%);
        }

        * { 
            margin: 0;
            padding: 0; 
            box-sizing: border-box; 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-body); }
        ::-webkit-scrollbar-thumb { background: var(--accent-orange); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-orange-light); }
        
        body {
            background: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
            position: relative;
        }

        /* Particle Background */
        #particles-js {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }

        /* Animated Gradient Background */
        .animated-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(255, 122, 0, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(16, 185, 129, 0.04) 0%, transparent 70%);
            z-index: 0;
            animation: bgPulse 15s ease-in-out infinite;
        }

        @keyframes bgPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.8; transform: scale(1.05); }
        }

        /* Glassmorphism Effect */
        .glass {
            background: rgba(22, 22, 31, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
        }

        /* Enhanced Sidebar Styling */
        .sidebar {
            width: 280px;
            height: 100vh; 
            background: var(--gradient-dark);
            position: fixed; 
            top: 0; 
            left: 0; 
            display: flex; 
            flex-direction: column;
            padding: 30px 20px;
            border-right: 1px solid var(--border-color); 
            z-index: 1000;
            transition: var(--transition-smooth);
            box-shadow: 4px 0 30px rgba(0, 0, 0, 0.3);
        }
        .sidebar::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 1px;
            height: 100%;
            background: linear-gradient(180deg, transparent, var(--accent-orange), transparent);
            opacity: 0.3;
        }

        .brand-logo { 
            font-size: 26px;
            font-weight: 900; 
            color: white; 
            margin-bottom: 50px; 
            display: flex; 
            align-items: center; 
            gap: 12px; 
            padding: 0 10px;
            position: relative;
        }

        .brand-logo span { 
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .brand-logo i {
            font-size: 28px;
            color: var(--accent-orange);
            filter: drop-shadow(0 0 10px var(--accent-orange-glow));
            animation: logoFloat 3s ease-in-out infinite;
        }

        @keyframes logoFloat {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-5px) rotate(5deg); }
        }
        
        .nav-menu { 
            flex-grow: 1; 
            display: flex; 
            flex-direction: column;
            gap: 8px; 
        }

        .nav-link {
            display: flex;
            align-items: center; 
            padding: 14px 18px; 
            color: var(--text-secondary);
            text-decoration: none; 
            border-radius: 12px; 
            transition: var(--transition-smooth);
            cursor: pointer; 
            font-weight: 500; 
            font-size: 14px;
            position: relative;
            overflow: hidden;
        }

        .nav-link::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            width: 0;
            height: 100%;
            background: linear-gradient(90deg, var(--accent-orange-glow), transparent);
            transition: var(--transition-smooth);
            z-index: -1;
        }
        .nav-link:hover::before, .nav-link.active::before { width: 100%; }

        .nav-link:hover, .nav-link.active { 
            color: var(--accent-orange); 
            transform: translateX(5px);
        }

        .nav-link.active {
            background: rgba(255, 122, 0, 0.1);
            border-left: 3px solid var(--accent-orange);
            box-shadow: 0 0 20px var(--accent-orange-glow);
        }

        .nav-link i { 
            width: 24px;
            margin-right: 12px; 
            font-size: 18px; 
            text-align: center;
            transition: var(--transition-smooth);
        }

        .nav-link:hover i {
            transform: scale(1.2);
            filter: drop-shadow(0 0 8px var(--accent-orange));
        }

        .nav-link .nav-badge {
            margin-left: auto;
            background: var(--accent-orange);
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 700;
            animation: badgePulse 2s ease-in-out infinite;
        }
        @keyframes badgePulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }

        .sidebar-footer {
            margin-top: auto;
            padding-top: 20px; 
            border-top: 1px solid var(--border-color);
            text-align: center; 
            font-size: 11px; 
            color: var(--text-secondary); 
            font-weight: 500; 
            opacity: 0.5;
            letter-spacing: 1px;
        }

        /* Main Content */
        .main-content { 
            margin-left: 280px;
            width: calc(100% - 280px); 
            padding: 30px 40px; 
            position: relative;
            z-index: 1;
            min-height: 100vh;
        }

        .header-section { 
            display: flex;
            justify-content: space-between; 
            align-items: flex-start; 
            margin-bottom: 35px;
            animation: fadeInDown 0.6s ease-out;
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .page-title { 
            font-size: 32px;
            font-weight: 800; 
            color: white; 
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, #ccc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .page-subtitle { 
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 400;
        }

        /* ============================================= */
        /* FIXED: Status Badge with Glowing Green Dot   */
        /* ============================================= */
        .status-badge {
            background: var(--bg-card);
            padding: 12px 24px;
            border-radius: 50px;
            border: 1px solid var(--border-color);
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: var(--shadow-card);
            transition: var(--transition-smooth);
        }
        
        .status-badge:hover {
            border-color: rgba(16, 185, 129, 0.3);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
        }
        
        /* FIXED: Glowing Green Status Dot */
        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            position: relative;
            animation: statusGlow 2s ease-in-out infinite;
            box-shadow: 
                0 0 5px var(--accent-green),
                0 0 10px var(--accent-green),
                0 0 20px var(--accent-green),
                0 0 30px rgba(16, 185, 129, 0.5);
        }
        
        .status-dot::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 100%;
            height: 100%;
            background: var(--accent-green);
            border-radius: 50%;
            animation: statusPulseRing 2s ease-out infinite;
        }
        
        .status-dot::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 6px;
            height: 6px;
            background: #fff;
            border-radius: 50%;
            opacity: 0.8;
        }
        
        @keyframes statusGlow {
            0%, 100% { 
                opacity: 1;
                box-shadow: 
                    0 0 5px var(--accent-green),
                    0 0 10px var(--accent-green),
                    0 0 20px var(--accent-green),
                    0 0 30px rgba(16, 185, 129, 0.5);
            }
            50% { 
                opacity: 0.8;
                box-shadow: 
                    0 0 10px var(--accent-green),
                    0 0 20px var(--accent-green),
                    0 0 40px var(--accent-green),
                    0 0 60px rgba(16, 185, 129, 0.6);
            }
        }
        
        @keyframes statusPulseRing {
            0% {
                transform: translate(-50%, -50%) scale(1);
                opacity: 0.8;
            }
            100% {
                transform: translate(-50%, -50%) scale(2.5);
                opacity: 0;
            }
        }
        /* ============================================= */
        
        /* Enhanced Cards & Grid */
        .stats-grid { 
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); 
            gap: 24px; 
            margin-bottom: 35px;
        }

        .dashboard-grid-2 { 
            display: grid;
            grid-template-columns: 2fr 1fr; 
            gap: 24px; 
            margin-bottom: 24px; 
        }

        .card { 
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: var(--card-radius);
            padding: 28px;
            backdrop-filter: blur(10px);
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent-orange-glow), transparent);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .card:hover {
            border-color: var(--border-glow);
            box-shadow: var(--shadow-glow);
            transform: translateY(-4px);
        }

        .card:hover::before { opacity: 1; }
        
        .section-header { 
            display: flex;
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 24px; 
            font-weight: 700;
            font-size: 16px; 
            color: white;
            letter-spacing: -0.3px;
        }

        .section-header i {
            font-size: 20px;
            opacity: 0.7;
            transition: var(--transition-smooth);
        }

        .card:hover .section-header i {
            opacity: 1;
            transform: rotate(10deg) scale(1.1);
        }
        
        /* Stat Cards with Animations */
        .stat-card { 
            display: flex;
            align-items: center; 
            gap: 24px; 
            transition: var(--transition-smooth);
            cursor: pointer;
        }

        .stat-card:hover { 
            transform: translateY(-6px) scale(1.02);
        }

        .stat-icon { 
            width: 64px;
            height: 64px; 
            background: linear-gradient(145deg, rgba(255, 122, 0, 0.15), rgba(255, 122, 0, 0.05));
            border-radius: 16px; 
            display: flex; 
            justify-content: center; 
            align-items: center;
            font-size: 26px; 
            color: var(--accent-orange);
            position: relative;
            overflow: hidden;
            transition: var(--transition-smooth);
        }

        .stat-icon::after {
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            background: var(--gradient-orange);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .stat-card:hover .stat-icon {
            transform: rotate(-10deg) scale(1.1);
            box-shadow: 0 0 30px var(--accent-orange-glow);
        }

        .stat-card:hover .stat-icon i {
            animation: iconBounce 0.5s ease-out;
        }

        @keyframes iconBounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.3); }
        }

        .stat-info h3 { 
            font-size: 36px;
            font-weight: 800; 
            margin: 0; 
            color: white;
            letter-spacing: -1px;
            line-height: 1;
            background: linear-gradient(135deg, #fff 0%, var(--accent-orange-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .stat-info p { 
            font-size: 13px;
            color: var(--text-secondary); 
            margin: 6px 0 0 0; 
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }

        /* Animated Counter */
        .count-up {
            display: inline-block;
        }
                /* Progress Bars with Animation */
        .progress-item { margin-bottom: 24px; }

        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 14px;
            color: white;
            font-weight: 500;
        }

        .progress-value {
            color: var(--text-secondary);
            font-weight: 600;
        }

        .progress-bar-container {
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .progress-bar-fill {
            height: 100%;
            border-radius: 10px;
            position: relative;
            animation: progressFill 1.5s ease-out forwards;
            transform-origin: left;
        }

        .progress-bar-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }

        @keyframes progressFill {
            from { transform: scaleX(0); }
            to { transform: scaleX(1); }
        }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .progress-orange { background: var(--gradient-orange); }
        .progress-purple { background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); }
        .progress-green { background: linear-gradient(135deg, #10B981 0%, #34D399 100%); }
        
        /* Enhanced Forms */
        .input-group { margin-bottom: 20px; }

        .input-group label { 
            display: block;
            font-size: 11px; 
            color: var(--text-secondary); 
            margin-bottom: 8px; 
            text-transform: uppercase; 
            font-weight: 700;
            letter-spacing: 1.5px;
        }

        input, select, textarea { 
            width: 100%;
            padding: 14px 18px; 
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 12px; 
            color: white; 
            font-size: 15px; 
            font-weight: 500;
            outline: none; 
            transition: var(--transition-smooth);
        }
        
        textarea {
            min-height: 100px;
            resize: vertical;
        }

        input::placeholder, textarea::placeholder {
            color: var(--text-secondary);
            opacity: 0.5;
        }

        input:focus, select:focus, textarea:focus { 
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
            box-shadow: 0 0 0 4px var(--accent-orange-glow), 0 0 20px var(--accent-orange-glow);
        }

        select {
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='%23FF7A00' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 24px;
            background-color: rgba(255, 255, 255, 0.03);
        }
        
        select option {
            background-color: #1a1a25;
            color: white;
            padding: 10px;
        }
        
        button, .btn-primary { 
            width: 100%;
            padding: 14px 24px; 
            background: var(--gradient-orange);
            color: white; 
            border: none; 
            border-radius: 12px; 
            font-weight: 700;
            font-size: 15px;
            cursor: pointer; 
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
            letter-spacing: 0.5px;
        }
        
        button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: 0.5s;
        }

        button:hover::before { left: 100%; }

        button:hover { 
            transform: translateY(-3px);
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }

        button:active {
            transform: translateY(0);
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--accent-orange);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
        }
        
        .btn-success:hover {
            box-shadow: 0 10px 30px rgba(16, 185, 129, 0.3);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #EF4444 0%, #F87171 100%);
        }
        
        .btn-danger:hover {
            box-shadow: 0 10px 30px rgba(239, 68, 68, 0.3);
        }
        
        .btn-purple {
            background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);
        }
        
        .btn-purple:hover {
            box-shadow: 0 10px 30px rgba(139, 92, 246, 0.3);
        }
        
        .btn-sm {
            padding: 8px 16px;
            font-size: 13px;
            width: auto;
        }

        /* Enhanced Tables */
        .dark-table { 
            width: 100%;
            border-collapse: collapse; 
            margin-top: 10px; 
        }

        .dark-table th { 
            text-align: left;
            padding: 14px 16px; 
            color: var(--text-secondary); 
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-bottom: 1px solid var(--border-color);
            font-weight: 700;
        }

        .dark-table td { 
            padding: 16px;
            color: white; 
            font-size: 14px; 
            border-bottom: 1px solid rgba(255,255,255,0.03);
            vertical-align: middle;
            transition: var(--transition-smooth);
        }

        .dark-table tr {
            transition: var(--transition-smooth);
        }

        .dark-table tr:hover td { 
            background: rgba(255, 122, 0, 0.03);
        }

        .table-badge {
            background: rgba(255,255,255,0.05);
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        /* Action Buttons */
        .action-cell { 
            display: flex;
            gap: 8px; 
            justify-content: flex-end; 
        }

        .action-btn { 
            padding: 8px 12px;
            border-radius: 8px; 
            text-decoration: none; 
            font-size: 12px; 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            cursor: pointer; 
            border: none; 
            transition: var(--transition-smooth);
            position: relative;
            overflow: hidden;
        }

        .btn-edit { 
            background: rgba(139, 92, 246, 0.15);
            color: #A78BFA; 
        }

        .btn-edit:hover { 
            background: var(--accent-purple);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.4);
        }

        .btn-del { 
            background: rgba(239, 68, 68, 0.15);
            color: #F87171; 
        }

        .btn-del:hover { 
            background: var(--accent-red);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.4);
        }
        
        .btn-view {
            background: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
        }
        
        .btn-view:hover {
            background: var(--accent-blue);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
        }
        
        .btn-print-sm {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
        }
        
        .btn-print-sm:hover {
            background: var(--accent-green);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
        }
        
        /* Enhanced Loading Overlay */
        #loading-overlay { 
            display: none;
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100%; 
            height: 100%; 
            background: rgba(10, 10, 15, 0.95);
            z-index: 9999; 
            flex-direction: column;
            justify-content: center; 
            align-items: center; 
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        
        /* Modern Spinner */
        .spinner-container {
            position: relative;
            width: 80px;
            height: 80px;
        }

        .spinner { 
            width: 80px;
            height: 80px; 
            border: 4px solid rgba(255, 122, 0, 0.1);
            border-top: 4px solid var(--accent-orange);
            border-right: 4px solid var(--accent-orange-light);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            box-shadow: 0 0 30px var(--accent-orange-glow);
        }

        .spinner-inner {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 3px solid rgba(139, 92, 246, 0.1);
            border-bottom: 3px solid var(--accent-purple);
            border-left: 3px solid var(--accent-purple);
            border-radius: 50%;
            animation: spin 1.2s linear infinite reverse;
        }

        @keyframes spin { 
            0% { transform: rotate(0deg); } 
            100% { transform: rotate(360deg); } 
        }

        /* Success Checkmark Animation */
        .checkmark-container { 
            display: none;
            text-align: center; 
        }

        .checkmark-circle {
            width: 100px;
            height: 100px; 
            position: relative; 
            display: inline-block;
            border-radius: 50%; 
            border: 3px solid var(--accent-green);
            margin-bottom: 24px;
            animation: success-anim 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            box-shadow: 0 0 40px rgba(16, 185, 129, 0.3);
        }

        .checkmark-circle::before {
            content: '';
            display: block; 
            width: 30px; 
            height: 50px;
            border: solid var(--accent-green); 
            border-width: 0 4px 4px 0;
            position: absolute; 
            top: 15px; 
            left: 35px;
            transform: rotate(45deg); 
            opacity: 0;
            animation: checkmark-anim 0.4s 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }
        
        /* Fail Cross Animation */
        .fail-container { 
            display: none; 
            text-align: center;
        }

        .fail-circle {
            width: 100px;
            height: 100px; 
            position: relative; 
            display: inline-block;
            border-radius: 50%; 
            border: 3px solid var(--accent-red);
            margin-bottom: 24px;
            animation: fail-anim 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.3);
        }

        .fail-circle::before, .fail-circle::after {
            content: '';
            position: absolute; 
            width: 4px; 
            height: 50px; 
            background: var(--accent-red);
            top: 23px; 
            left: 46px; 
            border-radius: 4px;
            animation: crossAnim 0.3s 0.4s ease-out forwards;
            opacity: 0;
        }

        .fail-circle::before { transform: rotate(45deg); }
        .fail-circle::after { transform: rotate(-45deg); }

        @keyframes success-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1.2); } 
            100% { transform: scale(1); opacity: 1; } 
        }

        @keyframes checkmark-anim { 
            0% { opacity: 0; height: 0; width: 0; } 
            100% { opacity: 1; height: 50px; width: 30px; } 
        }

        @keyframes fail-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1.2); } 
            100% { transform: scale(1); opacity: 1; } 
        }

        @keyframes crossAnim {
            0% { opacity: 0; transform: rotate(45deg) scale(0); }
            100% { opacity: 1; transform: rotate(45deg) scale(1); }
        }

        .anim-text { 
            font-size: 24px; 
            font-weight: 800; 
            color: white;
            margin-top: 10px; 
            letter-spacing: 1px;
        }

        .loading-text {
            color: var(--text-secondary);
            font-size: 15px;
            margin-top: 20px;
            font-weight: 500;
            letter-spacing: 2px;
            text-transform: uppercase;
            animation: textPulse 1.5s ease-in-out infinite;
        }

        @keyframes textPulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }
                /* Welcome Popup Modal */
        .welcome-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            z-index: 10000;
            justify-content: center;
            align-items: center;
            animation: modalFadeIn 0.3s ease-out;
        }

        @keyframes modalFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .welcome-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 50px 60px;
            text-align: center;
            max-width: 500px;
            width: 90%;
            animation: welcomeSlideIn 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            position: relative;
            overflow: hidden;
        }

        .welcome-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, var(--accent-orange-glow) 0%, transparent 60%);
            animation: welcomeGlow 3s ease-in-out infinite;
            opacity: 0.3;
        }
        
        @keyframes welcomeSlideIn {
            from { 
                opacity: 0;
                transform: translateY(-50px) scale(0.9);
            }
            to { 
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        @keyframes welcomeGlow {
            0%, 100% { transform: rotate(0deg); }
            50% { transform: rotate(180deg); }
        }

        .welcome-icon {
            font-size: 80px;
            margin-bottom: 20px;
            display: inline-block;
            animation: welcomeIconBounce 1s ease-out;
        }

        @keyframes welcomeIconBounce {
            0% { transform: scale(0) rotate(-180deg); }
            60% { transform: scale(1.2) rotate(10deg); }
            100% { transform: scale(1) rotate(0deg); }
        }

        .welcome-greeting {
            font-size: 16px;
            color: var(--accent-orange);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-bottom: 10px;
        }

        .welcome-title {
            font-size: 36px;
            font-weight: 900;
            color: white;
            margin-bottom: 15px;
            line-height: 1.2;
        }

        .welcome-title span {
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .welcome-message {
            color: var(--text-secondary);
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 30px;
        }

        .welcome-close {
            background: var(--gradient-orange);
            color: white;
            border: none;
            padding: 14px 40px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            transition: var(--transition-smooth);
            position: relative;
            z-index: 1;
        }

        .welcome-close:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px var(--accent-orange-glow);
        }

        /* Tooltip */
        .tooltip {
            position: relative;
        }

        .tooltip::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 120%;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-card);
            color: white;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 12px;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: var(--transition-smooth);
            border: 1px solid var(--border-color);
            z-index: 1000;
        }

        .tooltip:hover::after {
            opacity: 1;
            visibility: visible;
            bottom: 130%;
        }
        
        /* File Upload Zone */
        .upload-zone {
            border: 2px dashed var(--border-color);
            padding: 50px;
            text-align: center;
            border-radius: 16px;
            transition: var(--transition-smooth);
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }

        .upload-zone::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--gradient-orange);
            opacity: 0;
            transition: var(--transition-smooth);
        }

        .upload-zone:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .upload-zone:hover::before {
            opacity: 0.03;
        }

        .upload-zone.dragover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 60px;
            color: var(--accent-orange);
            margin-bottom: 20px;
            display: inline-block;
            animation: uploadFloat 3s ease-in-out infinite;
        }

        @keyframes uploadFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        .upload-text {
            color: var(--accent-orange);
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 8px;
        }

        .upload-hint {
            color: var(--text-secondary);
            font-size: 13px;
        }

        #file-count {
            margin-top: 20px;
            font-size: 14px;
            color: var(--accent-green);
            font-weight: 600;
        }

        /* Flash Messages */
        .flash-message {
            margin-bottom: 20px;
            padding: 16px 20px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
            animation: flashSlideIn 0.4s ease-out;
        }

        @keyframes flashSlideIn {
            from { 
                opacity: 0;
                transform: translateY(-10px);
            }
            to { 
                opacity: 1;
                transform: translateY(0);
            }
        }

        .flash-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #F87171;
        }

        .flash-success {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #34D399;
        }
        
        .flash-warning {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.2);
            color: #FBBF24;
        }
        
        /* Ripple Effect */
        .ripple {
            position: relative;
            overflow: hidden;
        }

        .ripple-effect {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: scale(0);
            animation: rippleAnim 0.6s ease-out;
            pointer-events: none;
        }

        @keyframes rippleAnim {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        
        /* Mobile Toggle & Responsive */
        .mobile-toggle { 
            display: none; 
            position: fixed; 
            top: 20px;
            right: 20px; 
            z-index: 2000; 
            color: white; 
            background: var(--bg-card);
            padding: 12px 14px; 
            border-radius: 12px;
            border: 1px solid var(--border-color);
            cursor: pointer;
            transition: var(--transition-smooth);
        }

        .mobile-toggle:hover {
            background: var(--accent-orange);
        }

        @media (max-width: 1024px) {
            .sidebar { 
                transform: translateX(-100%);
                width: 280px;
            } 
            .sidebar.active { 
                transform: translateX(0);
            }
            .main-content { 
                margin-left: 0;
                width: 100%; 
                padding: 20px; 
            }
            .dashboard-grid-2 { 
                grid-template-columns: 1fr;
            }
            .mobile-toggle { 
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .header-section {
                flex-direction: column;
                gap: 15px;
            }
        }

        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .page-title {
                font-size: 24px;
            }
            .welcome-content {
                padding: 40px 30px;
            }
            .welcome-title {
                font-size: 28px;
            }
        }

        /* Skeleton Loading */
        .skeleton {
            background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%);
            background-size: 200% 100%;
            animation: skeletonLoad 1.5s infinite;
            border-radius: 8px;
        }

        @keyframes skeletonLoad {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        /* Notification Dot */
        .notification-dot {
            position: absolute;
            top: -2px;
            right: -2px;
            width: 10px;
            height: 10px;
            background: var(--accent-red);
            border-radius: 50%;
            border: 2px solid var(--bg-sidebar);
            animation: notifyPulse 2s infinite;
        }

        @keyframes notifyPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }

        /* Chart Container */
        .chart-container {
            position: relative;
            height: 280px;
            padding: 10px;
        }

        /* Real-time Indicator */
        .realtime-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-secondary);
            padding: 6px 12px;
            background: rgba(16, 185, 129, 0.1);
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .realtime-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: realtimePulse 1s infinite;
        }

        @keyframes realtimePulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        }

        /* Floating Action Button */
        .fab {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            background: var(--gradient-orange);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
            cursor: pointer;
            box-shadow: 0 8px 30px var(--accent-orange-glow);
            transition: var(--transition-smooth);
            z-index: 100;
        }

        .fab:hover {
            transform: scale(1.1) rotate(90deg);
            box-shadow: 0 12px 40px var(--accent-orange-glow);
        }
        
        /* Glow Text */
        .glow-text {
            text-shadow: 0 0 20px var(--accent-orange-glow);
        }

        /* Animated Border */
        .animated-border {
            position: relative;
        }

        .animated-border::after {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, var(--accent-orange), var(--accent-purple), var(--accent-green), var(--accent-orange));
            background-size: 400% 400%;
            border-radius: inherit;
            z-index: -1;
            animation: gradientBorder 3s ease infinite;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .animated-border:hover::after {
            opacity: 1;
        }

        @keyframes gradientBorder {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Permission Checkbox Styles */
        .perm-checkbox {
            background: rgba(255, 255, 255, 0.03);
            padding: 14px 18px;
            border-radius: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            border: 1px solid var(--border-color);
            transition: var(--transition-smooth);
            flex: 1;
            min-width: 100px;
        }

        .perm-checkbox:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .perm-checkbox input {
            width: auto;
            margin-right: 10px;
            accent-color: var(--accent-orange);
        }

        .perm-checkbox span {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }

        .perm-checkbox:has(input:checked) {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
        }

        .perm-checkbox:has(input:checked) span {
            color: var(--accent-orange);
        }

        /* Time Badge */
        .time-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.03);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .time-badge i {
            color: var(--accent-orange);
        }
        
        /* Grid Layouts for Store */
        .grid-2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }
        
        .grid-3 {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        
        .grid-4 {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }
        
        @media (max-width: 768px) {
            .grid-2, .grid-3, .grid-4 {
                grid-template-columns: 1fr;
            }
        }
        
        /* Modal Overlay */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            z-index: 9000;
            justify-content: center;
            align-items: center;
        }
        
        .modal-overlay.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            animation: modalSlideIn 0.3s ease-out;
        }
        
        @keyframes modalSlideIn {
            from {
                opacity: 0;
                transform: translateY(-30px) scale(0.95);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-title {
            font-size: 22px;
            font-weight: 700;
            color: white;
        }
        
        .modal-close {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: var(--transition-smooth);
        }
        
        .modal-close:hover {
            background: var(--accent-red);
            color: white;
            border-color: var(--accent-red);
        }
        
        /* Search Box */
        .search-box {
            position: relative;
            margin-bottom: 20px;
        }
        
        .search-box input {
            padding-left: 45px;
        }
        
        .search-box i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }
        
        /* Tab Navigation */
        .tab-nav {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        
        .tab-btn {
            padding: 10px 20px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-weight: 600;
            cursor: pointer;
            border-radius: 8px;
            transition: var(--transition-smooth);
        }
        
        .tab-btn:hover {
            color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
        }
        
        .tab-btn.active {
            color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.15);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        /* Amount Display */
        .amount-display {
            font-size: 28px;
            font-weight: 800;
            color: var(--accent-green);
        }
        
        .amount-due {
            color: var(--accent-red);
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state i {
            font-size: 60px;
            opacity: 0.2;
            margin-bottom: 20px;
            display: block;
        }
        
        .empty-state p {
            font-size: 16px;
            margin-bottom: 20px;
        }
    </style>
"""
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

    booking_block_match = re.search(r"(?:Internal )?Booking NO\. ?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match: 
        raw_booking = booking_block_match.group(1).strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking: clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\. ?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match: meta['style'] = style_match.group(1).strip()
    else:
        style_match = re.search(r"Style Des\. ?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match: meta['style'] = style_match.group(1).strip()

    season_match = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re.IGNORECASE)
    if season_match: meta['season'] = season_match.group(1).strip()
    dept_match = re.search(r"Dept\. ?[\s\n:]*([A-Za-z]+)", first_page_text, re.IGNORECASE)
    if dept_match: meta['dept'] = dept_match.group(1).strip()

    item_match = re.search(r"Garments?    Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
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
                all_report_data.append({
                    'style': style, 'buyer': buyer_name, 'color': color, 
                    'headers': headers, 'gmts_qty': gmts_qty_data, 
                    'plus_3_percent': plus_3_percent_data, 
                    'sewing_input': sewing_input_data if sewing_input_data else [], 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
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
    
    left_sub_headers = {
        'A4': 'BUYER', 'B4': report_data[0].get('buyer', ''), 
        'A5': 'IR/IB NO', 'B5': formatted_ref_no, 
        'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')
    }
    
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
# STORE DASHBOARD TEMPLATE
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MEHEDI THAI ALUMINUM AND GLASS</title>
    {COMMON_STYLES}
    <style>
        .store-header {{
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 25px 30px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .store-brand {{ display: flex; align-items: center; gap: 15px; }}
        .store-brand-icon {{
            width: 60px; height: 60px; background: var(--gradient-orange); border-radius: 15px;
            display: flex; align-items: center; justify-content: center; font-size: 28px; color: white;
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }}
        .store-brand-text h1 {{ font-size: 22px; font-weight: 800; color: white; margin: 0; line-height: 1.2; }}
        .store-brand-text p {{ font-size: 12px; color: var(--text-secondary); margin: 5px 0 0 0; text-transform: uppercase; letter-spacing: 1px; }}
        .store-stats {{ display: flex; gap: 30px; flex-wrap: wrap; }}
        .store-stat-item {{ text-align: center; }}
        .store-stat-value {{ font-size: 28px; font-weight: 800; color: var(--accent-orange); }}
        .store-stat-label {{ font-size: 11px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; }}
        .quick-actions {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .quick-action-btn {{
            background: var(--gradient-card); border: 1px solid var(--border-color); border-radius: 16px;
            padding: 25px; text-align: center; cursor: pointer; transition: var(--transition-smooth);
            text-decoration: none; display: block;
        }}
        .quick-action-btn:hover {{ border-color: var(--accent-orange); transform: translateY(-5px); box-shadow: 0 15px 40px rgba(255, 122, 0, 0.15); }}
        .quick-action-btn i {{ font-size: 32px; margin-bottom: 15px; display: block; }}
        .quick-action-btn span {{ font-size: 14px; font-weight: 600; color: white; }}
        .qa-orange i {{ color: var(--accent-orange); }}
        .qa-green i {{ color: var(--accent-green); }}
        .qa-purple i {{ color: var(--accent-purple); }}
        .qa-blue i {{ color: var(--accent-blue); }}
        .qa-cyan i {{ color: var(--accent-cyan); }}
        .qa-red i {{ color: var(--accent-red); }}
        .section-tabs {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
        .section-tab {{
            padding: 12px 24px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--border-color);
            border-radius: 10px; color: var(--text-secondary); font-weight: 600; font-size: 13px;
            cursor: pointer; transition: var(--transition-smooth);
        }}
        .section-tab:hover {{ border-color: var(--accent-orange); color: var(--accent-orange); }}
        .section-tab.active {{ background: var(--accent-orange); border-color: var(--accent-orange); color: white; }}
        .tab-panel {{ display: none; }}
        .tab-panel.active {{ display: block; animation: fadeIn 0.3s ease-out; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .invoice-row {{
            display: grid; grid-template-columns: 100px 1fr 120px 120px 100px; gap: 15px; padding: 15px;
            background: rgba(255, 255, 255, 0.02); border-radius: 10px; margin-bottom: 10px; align-items: center;
            transition: var(--transition-smooth);
        }}
        .invoice-row:hover {{ background: rgba(255, 122, 0, 0.05); }}
        @media (max-width: 768px) {{
            .invoice-row {{ grid-template-columns: 1fr; gap: 10px; }}
            .store-header {{ flex-direction: column; text-align: center; }}
            .store-stats {{ justify-content: center; }}
        }}
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    <div id="loading-overlay">
        <div class="spinner-container"><div class="spinner"></div><div class="spinner-inner"></div></div>
        <div class="checkmark-container" id="success-anim"><div class="checkmark-circle"></div><div class="anim-text">Success!</div></div>
        <div class="loading-text" id="loading-text">Processing...</div>
    </div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/" class="nav-link"><i class="fas fa-arrow-left"></i> Back to Main</a>
            <div class="nav-link active"><i class="fas fa-th-large"></i> Dashboard</div>
            <a href="/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/estimates" class="nav-link"><i class="fas fa-file-alt"></i> Estimates</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-wallet"></i> Due Collection</a>
            <a href="/store/users" class="nav-link"><i class="fas fa-user-cog"></i> Store Users</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="store-header">
            <div class="store-brand">
                <div class="store-brand-icon"><i class="fas fa-store-alt"></i></div>
                <div class="store-brand-text"><h1>MEHEDI THAI ALUMINUM AND GLASS</h1><p>Store Management System</p></div>
            </div>
            <div class="status-badge"><div class="status-dot"></div><span>Online</span></div>
        </div>
        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon"><i class="fas fa-box"></i></div>
                <div class="stat-info"><h3 class="count-up" data-target="{{{{ store_stats.products_count }}}}">0</h3><p>Total Products</p></div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                    <i class="fas fa-users" style="color: var(--accent-purple);"></i>
                </div>
                <div class="stat-info"><h3 class="count-up" data-target="{{{{ store_stats.customers_count }}}}">0</h3><p>Customers</p></div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-file-invoice" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info"><h3 class="count-up" data-target="{{{{ store_stats.invoices_count }}}}">0</h3><p>Total Invoices</p></div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));">
                    <i class="fas fa-hand-holding-usd" style="color: var(--accent-red);"></i>
                </div>
                <div class="stat-info"><h3>৳{{{{ store_stats.total_due | comma }}}}</h3><p>Total Due</p></div>
            </div>
        </div>
        <div class="quick-actions">
            <a href="/store/products/add" class="quick-action-btn qa-orange"><i class="fas fa-plus-circle"></i><span>Add Product</span></a>
            <a href="/store/customers/add" class="quick-action-btn qa-purple"><i class="fas fa-user-plus"></i><span>Add Customer</span></a>
            <a href="/store/invoices/create" class="quick-action-btn qa-green"><i class="fas fa-file-invoice-dollar"></i><span>Create Invoice</span></a>
            <a href="/store/estimates/create" class="quick-action-btn qa-blue"><i class="fas fa-file-alt"></i><span>Create Estimate</span></a>
            <a href="/store/dues" class="quick-action-btn qa-red"><i class="fas fa-money-bill-wave"></i><span>Collect Due</span></a>
            <a href="/store/invoices" class="quick-action-btn qa-cyan"><i class="fas fa-search"></i><span>Search Invoice</span></a>
        </div>
        <div class="card">
            <div class="section-header"><span><i class="fas fa-chart-line" style="margin-right: 10px; color: var(--accent-orange);"></i>Quick Overview</span></div>
            <div class="section-tabs">
                <div class="section-tab active" onclick="showTab('recent-invoices', this)">Recent Invoices</div>
                <div class="section-tab" onclick="showTab('recent-estimates', this)">Recent Estimates</div>
                <div class="section-tab" onclick="showTab('pending-dues', this)">Pending Dues</div>
            </div>
            <div id="tab-recent-invoices" class="tab-panel active">
                {{% if recent_invoices %}}
                    {{% for inv in recent_invoices[:5] %}}
                    <div class="invoice-row">
                        <div style="font-weight: 700; color: var(--accent-orange);">{{{{ inv.invoice_no }}}}</div>
                        <div style="color: white;">{{{{ inv.customer_name }}}}</div>
                        <div style="color: var(--text-secondary);">{{{{ inv.date }}}}</div>
                        <div style="font-weight: 700; color: var(--accent-green);">৳{{{{ inv.total | comma }}}}</div>
                        <div>
                            <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            <a href="/store/invoices/print/{{{{ inv.invoice_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                        </div>
                    </div>
                    {{% endfor %}}
                {{% else %}}
                    <div class="empty-state"><i class="fas fa-file-invoice"></i><p>No invoices yet. Create your first invoice!</p></div>
                {{% endif %}}
            </div>
            <div id="tab-recent-estimates" class="tab-panel">
                {{% if recent_estimates %}}
                    {{% for est in recent_estimates[:5] %}}
                    <div class="invoice-row">
                        <div style="font-weight: 700; color: var(--accent-blue);">{{{{ est.estimate_no }}}}</div>
                        <div style="color: white;">{{{{ est.customer_name }}}}</div>
                        <div style="color: var(--text-secondary);">{{{{ est.date }}}}</div>
                        <div style="font-weight: 700; color: var(--accent-purple);">৳{{{{ est.total | comma }}}}</div>
                        <div>
                            <a href="/store/estimates/view/{{{{ est.estimate_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            <a href="/store/estimates/print/{{{{ est.estimate_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                        </div>
                    </div>
                    {{% endfor %}}
                {{% else %}}
                    <div class="empty-state"><i class="fas fa-file-alt"></i><p>No estimates yet.</p></div>
                {{% endif %}}
            </div>
            <div id="tab-pending-dues" class="tab-panel">
                {{% if pending_dues %}}
                    {{% for due in pending_dues[:5] %}}
                    <div class="invoice-row" style="border-left: 3px solid var(--accent-red);">
                        <div style="font-weight: 700; color: var(--accent-orange);">{{{{ due.invoice_no }}}}</div>
                        <div style="color: white;">{{{{ due.customer_name }}}}</div>
                        <div style="color: var(--text-secondary);">{{{{ due.date }}}}</div>
                        <div style="font-weight: 700; color: var(--accent-red);">৳{{{{ due.due | comma }}}} Due</div>
                        <div>
                            <a href="/store/dues/collect/{{{{ due.invoice_no }}}}" class="action-btn btn-edit"><i class="fas fa-money-bill"></i></a>
                        </div>
                    </div>
                    {{% endfor %}}
                {{% else %}}
                    <div class="empty-state"><i class="fas fa-check-circle" style="color: var(--accent-green);"></i><p>No pending dues!</p></div>
                {{% endif %}}
            </div>
        </div>
    </div>
    <script>
        function showTab(tabId, element) {{
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            element.classList.add('active');
        }}
        function animateCountUp() {{
            document.querySelectorAll('.count-up').forEach(counter => {{
                const target = parseInt(counter.getAttribute('data-target')) || 0;
                const duration = 1500; const step = target / (duration / 16); let current = 0;
                const updateCounter = () => {{ current += step; if (current < target) {{ counter.textContent = Math.floor(current); requestAnimationFrame(updateCounter); }} else {{ counter.textContent = target; }} }};
                if (target > 0) updateCounter();
            }});
        }}
        setTimeout(animateCountUp, 300);
        if (window.innerWidth < 1024) {{ document.querySelector('.sidebar').classList.remove('active'); }}
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE PRODUCTS TEMPLATE
# ==============================================================================
STORE_PRODUCTS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div id="loading-overlay">
        <div class="spinner-container"><div class="spinner"></div><div class="spinner-inner"></div></div>
        <div class="loading-text">Processing...</div>
    </div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-box"></i> Products</div>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/estimates" class="nav-link"><i class="fas fa-file-alt"></i> Estimates</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Product Management</div></div>
            <div class="status-badge"><div class="status-dot"></div><span>Online</span></div>
        </div>
        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}
        {{% endwith %}}
        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header"><span><i class="fas fa-plus-circle" style="margin-right: 10px; color: var(--accent-orange);"></i>Add New Product</span></div>
                <form action="/store/products/save" method="post" onsubmit="showLoading()">
                    <div class="input-group"><label>PRODUCT NAME</label><input type="text" name="name" required placeholder="e.g. Thai Glass 5mm"></div>
                    <div class="grid-2">
                        <div class="input-group"><label>SIZE (FEET)</label><input type="text" name="size_feet" placeholder="e.g. 4x6"></div>
                        <div class="input-group"><label>THICKNESS</label><input type="text" name="thickness" placeholder="e.g. 5mm"></div>
                    </div>
                    <div class="grid-2">
                        <div class="input-group"><label>CATEGORY</label>
                            <select name="category">
                                <option value="Glass">Glass</option><option value="Aluminum Profile">Aluminum Profile</option>
                                <option value="Thai Aluminum">Thai Aluminum</option><option value="Accessories">Accessories</option>
                                <option value="Mirror">Mirror</option><option value="Other">Other</option>
                            </select>
                        </div>
                        <div class="input-group"><label>PRICE</label><input type="number" name="price" placeholder="৳ Per Unit" step="0.01"></div>
                    </div>
                    <div class="input-group"><label>DESCRIPTION</label><textarea name="description" placeholder="Details..."></textarea></div>
                    <button type="submit"><i class="fas fa-save"></i> Save Product</button>
                </form>
            </div>
            <div class="card">
                <div class="section-header"><span>Product List</span><span class="table-badge">{{{{ products|length }}}} Items</span></div>
                <div class="search-box"><i class="fas fa-search"></i><input type="text" id="productSearch" placeholder="Search..." onkeyup="filterProducts()"></div>
                <div style="max-height: 500px; overflow-y: auto;" id="productList">
                    {{% if products %}}
                        {{% for p in products|reverse %}}
                        <div class="product-item" style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border: 1px solid var(--border-color);">
                            <div>
                                <div style="font-weight: 700; color: white;">{{{{ p.name }}}}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">{{{{ p.category }}}}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-weight: 800; color: var(--accent-green);">৳{{{{ p.price }}}}</div>
                                <div class="action-cell" style="margin-top: 5px;">
                                    <a href="/store/products/edit/{{{{ loop.index0 }}}}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                    <form action="/store/products/delete/{{{{ loop.index0 }}}}" method="post" style="display:inline;" onsubmit="return confirm('Delete?');">
                                        <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                    </form>
                                </div>
                            </div>
                        </div>
                        {{% endfor %}}
                    {{% else %}}<div class="empty-state"><i class="fas fa-box-open"></i><p>No products</p></div>{{% endif %}}
                </div>
            </div>
        </div>
    </div>
    <script>
        function showLoading() {{ document.getElementById('loading-overlay').style.display = 'flex'; return true; }}
        function filterProducts() {{
            const search = document.getElementById('productSearch').value.toLowerCase();
            document.querySelectorAll('.product-item').forEach(item => {{
                item.style.display = item.textContent.toLowerCase().includes(search) ? 'flex' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMERS TEMPLATE
# ==============================================================================
STORE_CUSTOMERS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div id="loading-overlay"><div class="spinner-container"><div class="spinner"></div><div class="spinner-inner"></div></div><div class="loading-text">Processing...</div></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <div class="nav-link active"><i class="fas fa-users"></i> Customers</div>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/estimates" class="nav-link"><i class="fas fa-file-alt"></i> Estimates</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section"><div><div class="page-title">Customer Management</div></div><div class="status-badge"><div class="status-dot"></div><span>Online</span></div></div>
        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}
        {{% endwith %}}
        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header"><span>Add Customer</span></div>
                <form action="/store/customers/save" method="post" onsubmit="showLoading()">
                    <div class="input-group"><label>CUSTOMER NAME</label><input type="text" name="name" required></div>
                    <div class="input-group"><label>PHONE</label><input type="text" name="phone" required></div>
                    <div class="input-group"><label>ADDRESS</label><textarea name="address"></textarea></div>
                    <button type="submit"><i class="fas fa-save"></i> Save Customer</button>
                </form>
            </div>
            <div class="card">
                <div class="section-header"><span>Customer List</span><span class="table-badge">{{{{ customers|length }}}}</span></div>
                <div class="search-box"><i class="fas fa-search"></i><input type="text" id="customerSearch" placeholder="Search..." onkeyup="filterCustomers()"></div>
                <div style="max-height: 500px; overflow-y: auto;" id="customerList">
                    {{% if customers %}}
                        {{% for c in customers|reverse %}}
                        <div class="customer-item" style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border: 1px solid var(--border-color);">
                            <div>
                                <div style="font-weight: 700; color: white;">{{{{ c.name }}}}</div>
                                <div style="font-size: 13px; color: var(--accent-orange);">{{{{ c.phone }}}}</div>
                            </div>
                            <div class="action-cell">
                                <a href="/store/customers/edit/{{{{ loop.index0 }}}}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                <form action="/store/customers/delete/{{{{ loop.index0 }}}}" method="post" style="display:inline;" onsubmit="return confirm('Delete?');">
                                    <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                </form>
                            </div>
                        </div>
                        {{% endfor %}}
                    {{% else %}}<div class="empty-state"><i class="fas fa-users"></i><p>No customers</p></div>{{% endif %}}
                </div>
            </div>
        </div>
    </div>
    <script>
        function showLoading() {{ document.getElementById('loading-overlay').style.display = 'flex'; return true; }}
        function filterCustomers() {{
            const search = document.getElementById('customerSearch').value.toLowerCase();
            document.querySelectorAll('.customer-item').forEach(item => {{
                item.style.display = item.textContent.toLowerCase().includes(search) ? 'flex' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE CREATE TEMPLATE
# ==============================================================================
STORE_INVOICE_CREATE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create Invoice - Store Panel</title>
    {COMMON_STYLES}
    <style>
        .invoice-items-table {{ width: 100%; border-collapse: collapse; }}
        .invoice-items-table th {{ background: rgba(255, 122, 0, 0.1); padding: 12px; text-align: left; font-size: 12px; color: var(--accent-orange); border-bottom: 1px solid var(--border-color); }}
        .invoice-items-table td {{ padding: 10px; border-bottom: 1px solid var(--border-color); }}
        .invoice-items-table input {{ padding: 10px; font-size: 14px; }}
        .total-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-color); }}
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    <div id="loading-overlay"><div class="spinner-container"><div class="spinner"></div><div class="spinner-inner"></div></div><div class="loading-text">Creating Invoice...</div></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-file-invoice-dollar"></i> Invoices</div>
            <a href="/logout" class="nav-link"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Create Invoice</div><div class="page-subtitle">Invoice No: <span style="color: var(--accent-orange);">{{{{ invoice_no }}}}</span></div></div>
            <a href="/store/invoices" class="btn-secondary" style="padding: 12px 24px; border-radius: 10px; text-decoration: none; color: var(--text-secondary);">Back</a>
        </div>
        <form action="/store/invoices/save" method="post" onsubmit="return validateAndSubmit()">
            <input type="hidden" name="invoice_no" value="{{{{ invoice_no }}}}">
            <div class="grid-2" style="margin-bottom: 30px;">
                <div class="card">
                    <div class="section-header"><span>Customer Info</span></div>
                    <div class="input-group">
                        <label>SELECT CUSTOMER</label>
                        <select name="customer_id" id="customerSelect" onchange="fillCustomerInfo()">
                            <option value="">-- Select --</option>
                            {{% for c in customers %}}
                            <option value="{{{{ loop.index0 }}}}" data-name="{{{{ c.name }}}}" data-phone="{{{{ c.phone }}}}" data-address="{{{{ c.address }}}}">{{{{ c.name }}}} - {{{{ c.phone }}}}</option>
                            {{% endfor %}}
                        </select>
                    </div>
                    <div class="input-group"><label>NAME</label><input type="text" name="customer_name" id="customerName" required></div>
                    <div class="input-group"><label>PHONE</label><input type="text" name="customer_phone" id="customerPhone"></div>
                    <div class="input-group"><label>ADDRESS</label><textarea name="customer_address" id="customerAddress"></textarea></div>
                </div>
                <div class="card">
                    <div class="section-header"><span>Details</span></div>
                    <div class="input-group"><label>DATE</label><input type="date" name="invoice_date" value="{{{{ today }}}}" required></div>
                    <div class="input-group"><label>NOTES</label><textarea name="notes"></textarea></div>
                </div>
            </div>
            <div class="card">
                <div class="section-header"><span>Items</span></div>
                <div style="overflow-x: auto;">
                    <table class="invoice-items-table">
                        <thead><tr><th>Description</th><th>Size</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead>
                        <tbody id="itemsBody">
                            <tr class="item-row">
                                <td><input type="text" name="items[0][description]" required></td>
                                <td><input type="text" name="items[0][size]"></td>
                                <td><input type="number" name="items[0][qty]" class="item-qty" value="1" onchange="calculateRow(this)" required></td>
                                <td><input type="number" name="items[0][price]" class="item-price" step="0.01" onchange="calculateRow(this)" required></td>
                                <td><input type="number" name="items[0][total]" class="item-total" readonly></td>
                                <td><button type="button" class="btn-del" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <button type="button" class="btn-secondary" style="margin-top: 15px; width: 100%;" onclick="addItemRow()">+ Add Item</button>
                <div class="card" style="margin-top: 20px; background: rgba(255,255,255,0.03);">
                    <div class="total-row"><span>Subtotal</span><span id="subtotal">0</span></div>
                    <div class="total-row"><span>Discount</span><input type="number" name="discount" id="discountInput" value="0" onchange="calculateTotals()" style="width: 100px;"></div>
                    <div class="total-row"><span>Paid</span><input type="number" name="paid" id="paidInput" value="0" onchange="calculateTotals()" style="width: 100px;"></div>
                    <div class="total-row" style="border:none; font-size: 18px; color: var(--accent-red);"><span>Due</span><span id="dueAmount">0</span></div>
                    <input type="hidden" name="total" id="totalInput"><input type="hidden" name="due" id="dueInput">
                </div>
            </div>
            <div style="margin-top: 30px; display: flex; gap: 15px; justify-content: flex-end;">
                <button type="submit" name="action" value="save">Save</button>
                <button type="submit" name="action" value="save_print" class="btn-success">Save & Print</button>
            </div>
        </form>
    </div>
    <script>
        let itemIndex = 1;
        function fillCustomerInfo() {{
            const sel = document.getElementById('customerSelect');
            const opt = sel.options[sel.selectedIndex];
            if(opt.value){{
                document.getElementById('customerName').value = opt.dataset.name;
                document.getElementById('customerPhone').value = opt.dataset.phone;
                document.getElementById('customerAddress').value = opt.dataset.address;
            }}
        }}
        function addItemRow() {{
            const row = document.createElement('tr'); row.className = 'item-row';
            row.innerHTML = `<td><input type="text" name="items[${{itemIndex}}][description]" required></td>
                <td><input type="text" name="items[${{itemIndex}}][size]"></td>
                <td><input type="number" name="items[${{itemIndex}}][qty]" class="item-qty" value="1" onchange="calculateRow(this)"></td>
                <td><input type="number" name="items[${{itemIndex}}][price]" class="item-price" onchange="calculateRow(this)"></td>
                <td><input type="number" name="items[${{itemIndex}}][total]" class="item-total" readonly></td>
                <td><button type="button" class="btn-del" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>`;
            document.getElementById('itemsBody').appendChild(row); itemIndex++;
        }}
        function removeRow(btn) {{ if(document.querySelectorAll('.item-row').length > 1) {{ btn.closest('tr').remove(); calculateTotals(); }} }}
        function calculateRow(input) {{
            const row = input.closest('tr');
            const total = (parseFloat(row.querySelector('.item-qty').value)||0) * (parseFloat(row.querySelector('.item-price').value)||0);
            row.querySelector('.item-total').value = total.toFixed(2);
            calculateTotals();
        }}
        function calculateTotals() {{
            let sub = 0; document.querySelectorAll('.item-total').forEach(i => sub += parseFloat(i.value)||0);
            const disc = parseFloat(document.getElementById('discountInput').value)||0;
            const paid = parseFloat(document.getElementById('paidInput').value)||0;
            const grand = sub - disc;
            document.getElementById('subtotal').innerText = sub.toFixed(2);
            document.getElementById('dueAmount').innerText = (grand - paid).toFixed(2);
            document.getElementById('totalInput').value = grand.toFixed(2);
            document.getElementById('dueInput').value = (grand - paid).toFixed(2);
        }}
        function validateAndSubmit() {{ calculateTotals(); document.getElementById('loading-overlay').style.display = 'flex'; return true; }}
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE PRINT TEMPLATE
# ==============================================================================
STORE_INVOICE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ invoice.invoice_no }}</title>
    <style>
        body { font-family: sans-serif; padding: 30px; color: #000; }
        .container { max-width: 800px; margin: 0 auto; border: 1px solid #000; padding: 20px; }
        .header { text-align: center; margin-bottom: 20px; border-bottom: 1px solid #000; padding-bottom: 10px; }
        .title { font-size: 24px; font-weight: bold; color: #2c3e50; }
        .info { display: flex; justify-content: space-between; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .totals { text-align: right; }
        .no-print { display: none; }
        @media print { .no-print { display: none; } button { display: none; } }
    </style>
</head>
<body>
    <button onclick="window.print()" style="margin-bottom: 20px; padding: 10px;">Print Invoice</button>
    <a href="/store/invoices" style="margin-left: 10px;">Back</a>
    <div class="container">
        <div class="header">
            <div class="title">MEHEDI THAI ALUMINUM AND GLASS</div>
            <div>Invoice / চালান</div>
        </div>
        <div class="info">
            <div>
                <strong>Customer:</strong> {{ invoice.customer_name }}<br>
                <strong>Phone:</strong> {{ invoice.customer_phone }}<br>
                <strong>Address:</strong> {{ invoice.customer_address }}
            </div>
            <div style="text-align: right;">
                <strong>Invoice No:</strong> {{ invoice.invoice_no }}<br>
                <strong>Date:</strong> {{ invoice.date }}
            </div>
        </div>
        <table>
            <thead><tr><th>Description</th><th>Size</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ item.description }}</td>
                    <td>{{ item.size }}</td>
                    <td>{{ item.qty }}</td>
                    <td>{{ item.price }}</td>
                    <td>{{ item.total }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <div class="totals">
            <p><strong>Total:</strong> {{ invoice.total }}</p>
            <p><strong>Paid:</strong> {{ invoice.paid }}</p>
            <p><strong>Due:</strong> {{ invoice.due }}</p>
        </div>
        {% if invoice.notes %}
        <div style="margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px;">
            <strong>Notes:</strong> {{ invoice.notes }}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATES LIST, CREATE & PRINT TEMPLATES
# ==============================================================================
STORE_ESTIMATES_LIST_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Estimates - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-file-alt"></i> Estimates</div>
            <a href="/logout" class="nav-link"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Estimates</div></div>
            <a href="/store/estimates/create" class="btn-primary" style="text-decoration: none;">New Estimate</a>
        </div>
        <div class="card">
            <table class="dark-table">
                <thead><tr><th>No</th><th>Customer</th><th>Date</th><th>Total</th><th>Action</th></tr></thead>
                <tbody>
                    {{% for est in estimates|reverse %}}
                    <tr>
                        <td>{{{{ est.estimate_no }}}}</td>
                        <td>{{{{ est.customer_name }}}}</td>
                        <td>{{{{ est.date }}}}</td>
                        <td>{{{{ est.total | comma }}}}</td>
                        <td>
                            <a href="/store/estimates/print/{{{{ est.estimate_no }}}}" class="action-btn btn-view" target="_blank"><i class="fas fa-print"></i></a>
                            <a href="/store/estimates/to-invoice/{{{{ est.estimate_no }}}}" class="action-btn btn-edit"><i class="fas fa-file-invoice"></i></a>
                        </td>
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

STORE_ESTIMATE_CREATE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create Estimate - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-file-alt"></i> Estimates</div>
            <a href="/logout" class="nav-link"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Create Estimate</div><div class="page-subtitle">No: {{{{ estimate_no }}}}</div></div>
            <a href="/store/estimates" class="btn-secondary">Back</a>
        </div>
        <form action="/store/estimates/save" method="post" onsubmit="return validate()">
            <input type="hidden" name="estimate_no" value="{{{{ estimate_no }}}}">
            <div class="grid-2">
                <div class="card">
                    <div class="input-group"><label>CUSTOMER NAME</label><input type="text" name="customer_name" required></div>
                    <div class="input-group"><label>PHONE</label><input type="text" name="customer_phone"></div>
                </div>
                <div class="card">
                    <div class="input-group"><label>DATE</label><input type="date" name="estimate_date" value="{{{{ today }}}}" required></div>
                    <div class="input-group"><label>VALID UNTIL</label><input type="date" name="valid_until"></div>
                </div>
            </div>
            <div class="card" style="margin-top: 20px;">
                <table class="dark-table">
                    <thead><tr><th>Desc</th><th>Size</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead>
                    <tbody id="estBody">
                        <tr class="item-row">
                            <td><input type="text" name="items[0][description]" required></td>
                            <td><input type="text" name="items[0][size]"></td>
                            <td><input type="number" name="items[0][qty]" class="qty" onchange="calc(this)"></td>
                            <td><input type="number" name="items[0][price]" class="price" onchange="calc(this)"></td>
                            <td><input type="number" name="items[0][total]" class="total" readonly></td>
                            <td><button type="button" onclick="del(this)">x</button></td>
                        </tr>
                    </tbody>
                </table>
                <button type="button" onclick="add()">+ Add</button>
                <div style="margin-top: 20px;">
                    Total: <span id="grand">0</span>
                    <input type="hidden" name="total" id="totalInput">
                    Discount: <input type="number" name="discount" id="disc" value="0" onchange="calcAll()">
                </div>
            </div>
            <button type="submit" style="margin-top: 20px;">Save Estimate</button>
        </form>
    </div>
    <script>
        let idx = 1;
        function add(){{
            const row = document.createElement('tr');
            row.innerHTML = `<td><input type="text" name="items[${{idx}}][description]" required></td><td><input type="text" name="items[${{idx}}][size]"></td><td><input type="number" name="items[${{idx}}][qty]" class="qty" onchange="calc(this)"></td><td><input type="number" name="items[${{idx}}][price]" class="price" onchange="calc(this)"></td><td><input type="number" name="items[${{idx}}][total]" class="total" readonly></td><td><button type="button" onclick="del(this)">x</button></td>`;
            document.getElementById('estBody').appendChild(row); idx++;
        }}
        function del(btn){{ btn.closest('tr').remove(); calcAll(); }}
        function calc(inp){{
            const row = inp.closest('tr');
            row.querySelector('.total').value = (row.querySelector('.qty').value * row.querySelector('.price').value).toFixed(2);
            calcAll();
        }}
        function calcAll(){{
            let sum = 0; document.querySelectorAll('.total').forEach(e => sum += parseFloat(e.value)||0);
            const disc = parseFloat(document.getElementById('disc').value)||0;
            document.getElementById('grand').innerText = (sum - disc).toFixed(2);
            document.getElementById('totalInput').value = (sum - disc).toFixed(2);
        }}
        function validate(){{ calcAll(); return true; }}
    </script>
</body>
</html>
"""

STORE_ESTIMATE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Estimate {{ estimate.estimate_no }}</title>
    <style>body{font-family:sans-serif;padding:20px;} .header{text-align:center;border-bottom:1px solid #000;margin-bottom:20px;} table{width:100%;border-collapse:collapse;} th,td{border:1px solid #ddd;padding:8px;}</style>
</head>
<body>
    <div class="header"><h1>ESTIMATE</h1><h3>{{ estimate.estimate_no }}</h3></div>
    <div>Customer: {{ estimate.customer_name }}</div>
    <div>Date: {{ estimate.date }}</div>
    <table style="margin-top:20px;">
        <thead><tr><th>Description</th><th>Size</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
        <tbody>
            {% for item in estimate.items %}
            <tr><td>{{ item.description }}</td><td>{{ item.size }}</td><td>{{ item.qty }}</td><td>{{ item.price }}</td><td>{{ item.total }}</td></tr>
            {% endfor %}
        </tbody>
    </table>
    <div style="text-align:right; margin-top:20px;"><strong>Total: {{ estimate.total }}</strong></div>
    <div style="margin-top:50px;">Authorized Signature</div>
    <button onclick="window.print()" style="margin-top:20px;">Print</button>
</body>
</html>
"""

# ==============================================================================
# STORE DUE & INVOICE LIST TEMPLATES
# ==============================================================================
STORE_DUE_COLLECTION_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due Collection - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-wallet"></i> Due Collection</div>
            <a href="/logout" class="nav-link"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section"><div><div class="page-title">Due Collection</div></div></div>
        <div class="card">
            <form action="/store/dues/search" method="get">
                <input type="text" name="invoice_no" placeholder="Invoice No" value="{{{{ search_invoice }}}}">
                <button type="submit">Search</button>
            </form>
        </div>
        {{% if invoice %}}
        <div class="card" style="margin-top: 20px;">
            <h3>Invoice: {{{{ invoice.invoice_no }}}}</h3>
            <p>Customer: {{{{ invoice.customer_name }}}}</p>
            <p>Total: {{{{ invoice.total | comma }}}} | Paid: {{{{ invoice.paid | comma }}}} | <span style="color:red">Due: {{{{ invoice.due | comma }}}}</span></p>
            {{% if invoice.due > 0 %}}
            <form action="/store/dues/collect" method="post" style="margin-top: 20px; background: rgba(255,255,255,0.05); padding: 20px;">
                <input type="hidden" name="invoice_no" value="{{{{ invoice.invoice_no }}}}">
                <input type="number" name="amount" placeholder="Amount" max="{{{{ invoice.due }}}}" required>
                <input type="date" name="payment_date" value="{{{{ today }}}}" required>
                <input type="text" name="notes" placeholder="Notes">
                <button type="submit">Collect Payment</button>
            </form>
            {{% else %}}<p style="color:green">Fully Paid</p>{{% endif %}}
        </div>
        {{% endif %}}
    </div>
</body>
</html>
"""

STORE_INVOICES_LIST_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <div class="nav-link active"><i class="fas fa-file-invoice-dollar"></i> Invoices</div>
            <a href="/logout" class="nav-link"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Invoices</div></div>
            <a href="/store/invoices/create" class="btn-primary" style="text-decoration:none;">New Invoice</a>
        </div>
        <div class="card">
            <div class="search-box"><form><input type="text" name="search" placeholder="Search..." value="{{{{ search_query }}}}"><button type="submit">Go</button></form></div>
            <table class="dark-table">
                <thead><tr><th>No</th><th>Customer</th><th>Date</th><th>Total</th><th>Due</th><th>Action</th></tr></thead>
                <tbody>
                    {{% for inv in invoices|reverse %}}
                    <tr>
                        <td>{{{{ inv.invoice_no }}}}</td>
                        <td>{{{{ inv.customer_name }}}}</td>
                        <td>{{{{ inv.date }}}}</td>
                        <td>{{{{ inv.total | comma }}}}</td>
                        <td style="color: {{{{ 'red' if inv.due > 0 else 'green' }}}}">{{{{ inv.due | comma }}}}</td>
                        <td>
                            <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            <a href="/store/invoices/print/{{{{ inv.invoice_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                        </td>
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# REPORT TEMPLATES & EDIT/USER TEMPLATES (Included from Patch)
# ==============================================================================
STORE_PRODUCT_EDIT_TEMPLATE = f"""<!doctype html><html lang="en"><head><title>Edit</title>{COMMON_STYLES}</head><body><div class="animated-bg"></div><div style="max-width:500px;margin:50px auto;" class="card"><h3>Edit Product</h3><form action="/store/products/update" method="post"><input type="hidden" name="index" value="{{{{ index }}}}"><input type="text" name="name" value="{{{{ product.name }}}}" required><input type="text" name="size_feet" value="{{{{ product.size_feet }}}}"><input type="text" name="thickness" value="{{{{ product.thickness }}}}"><input type="number" name="price" value="{{{{ product.price }}}}" step="0.01"><button type="submit">Update</button></form></div></body></html>"""
STORE_CUSTOMER_EDIT_TEMPLATE = f"""<!doctype html><html lang="en"><head><title>Edit</title>{COMMON_STYLES}</head><body><div class="animated-bg"></div><div style="max-width:500px;margin:50px auto;" class="card"><h3>Edit Customer</h3><form action="/store/customers/update" method="post"><input type="hidden" name="index" value="{{{{ index }}}}"><input type="text" name="name" value="{{{{ customer.name }}}}" required><input type="text" name="phone" value="{{{{ customer.phone }}}}"><input type="text" name="address" value="{{{{ customer.address }}}}"><button type="submit">Update</button></form></div></body></html>"""
STORE_USERS_TEMPLATE = f"""<!doctype html><html lang="en"><head><title>Users</title>{COMMON_STYLES}</head><body><div class="animated-bg"></div><div class="sidebar"><div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div><div class="nav-menu"><a href="/admin/store" class="nav-link">Dashboard</a></div></div><div class="main-content"><div class="card"><h3>Store Users</h3><form action="/store/users/save" method="post"><input type="text" name="username" placeholder="Username" required><input type="text" name="password" placeholder="Password" required><button type="submit">Add</button></form><br><table>{{% for u,d in users.items() %}}<tr><td>{{{{ u }}}}</td><td><form action="/store/users/delete/{{{{ u }}}}" method="post"><button>Del</button></form></td></tr>{{% endfor %}}</table></div></div></body></html>"""

CLOSING_REPORT_PREVIEW_TEMPLATE = """<!DOCTYPE html><html><head><title>Report</title></head><body><h1>Closing Report: {{ ref_no }}</h1>{% for b in report_data %}<h3>{{ b.color }}</h3><table><tr><th>Size</th><th>Qty</th></tr>{% for i in range(b.headers|length) %}<tr><td>{{ b.headers[i] }}</td><td>{{ b.gmts_qty[i] }}</td></tr>{% endfor %}</table>{% endfor %}</body></html>"""
PO_REPORT_TEMPLATE = """<!DOCTYPE html><html><head><title>PO</title></head><body><h1>PO Report</h1>{% for t in tables %}<h3>{{ t.color }}</h3>{{ t.table|safe }}{% endfor %}</body></html>"""

ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessories Delivery Report</title>
    <style>body{font-family:sans-serif;} table{width:100%;border-collapse:collapse;} th,td{border:1px solid #000;padding:5px;text-align:center;}</style>
</head>
<body>
    <button onclick="window.print()">Print</button>
    <h2>COTTON CLOTHING BD LTD</h2>
    <h3>ACCESSORIES DELIVERY CHALLAN</h3>
    <div>Booking: {{ ref }} | Buyer: {{ buyer }} | Style: {{ style }} | Date: {{ today }}</div>
    <div style="margin-top:20px;border:1px solid #000;padding:10px;">
        <strong>Summary:</strong>
        {% for line, qty in line_summary.items() %}
            <span>{{ line }}: {{ qty }} | </span>
        {% endfor %}
        <strong>Total: {{ count }} Entries</strong>
    </div>
    <table style="margin-top:20px;">
        <thead><tr><th>DATE</th><th>LINE NO</th><th>COLOR</th><th>SIZE</th><th>QTY</th></tr></thead>
        <tbody>
            {% for item in challans %}
            <tr>
                <td>{{ item.date }}</td>
                <td>{{ item.line }}</td>
                <td>{{ item.color }}</td>
                <td>{{ item.size }}</td>
                <td>{{ item.qty }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# ==============================================================================
# FLASK ROUTES
# ==============================================================================

@app.route('/')
def home():
    if 'user' not in session: return render_template_string(LOGIN_TEMPLATE)
    if session.get('role') == 'admin':
        return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=get_dashboard_summary_v2())
    else: return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    users = load_users()
    if username in users and users[username]['password'] == password:
        session.permanent = True
        session['user'] = username
        session['role'] = users[username].get('role', 'user')
        session['permissions'] = users[username].get('permissions', [])
        session['login_time'] = get_bd_time().isoformat()
        users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
        save_users(users)
        return redirect(url_for('home'))
    flash('Invalid Credentials!')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin/get-users')
def get_users(): return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    data = request.get_json()
    users = load_users()
    users[data['username']] = {"password": data['password'], "role": "user", "permissions": data.get('permissions', []), "created_at": get_bd_date_str()}
    save_users(users)
    return jsonify({"status": "success"})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    data = request.get_json()
    users = load_users()
    if data['username'] in users: del users[data['username']]
    save_users(users)
    return jsonify({"status": "success"})

@app.route('/generate-report', methods=['POST'])
def generate_report():
    ref = request.form.get('ref_no', '').strip()
    data = fetch_closing_report_data(ref)
    if data:
        update_stats(ref, session['user'])
        return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=data, ref_no=ref)
    flash('No data found!')
    return redirect(url_for('home'))

@app.route('/download-closing-excel')
def download_closing_excel():
    ref = request.args.get('ref_no', '')
    data = fetch_closing_report_data(ref)
    if data:
        f = create_formatted_excel_report(data, ref)
        return send_file(f, as_attachment=True, download_name=f"{ref}.xlsx")
    return "Error"

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if 'pdf_files' not in request.files: return "No files"
    files = request.files.getlist('pdf_files')
    all_data, meta = [], {}
    for f in files:
        if f.filename.endswith('.pdf'):
            path = os.path.join(app.config['UPLOAD_FOLDER'], f.filename)
            f.save(path)
            d, m = extract_data_dynamic(path)
            all_data.extend(d)
            if m.get('buyer') != 'N/A': meta = m
            os.remove(path)
    if not all_data: return "No Data"
    update_po_stats(session['user'], len(files))
    
    # Process PO Data
    df = pd.DataFrame(all_data)
    sizes = sort_sizes(df['Size'].unique().tolist())
    tables = []
    grand = 0
    for color in df['Color'].unique():
        cdf = df[df['Color'] == color]
        piv = cdf.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        piv = piv.reindex(columns=[s for s in sizes if s in piv.columns], fill_value=0)
        piv['Total'] = piv.sum(axis=1)
        grand += piv['Total'].sum()
        html = piv.to_html(classes='table')
        tables.append({'color': color, 'table': html})
    
    return render_template_string(PO_REPORT_TEMPLATE, tables=tables, meta=meta, grand_total=grand)

@app.route('/admin/accessories')
def accessories_home(): return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input():
    ref = request.form.get('ref_no', '').strip().upper()
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    ref = request.args.get('ref', '').strip().upper()
    db = load_accessories_db()
    if ref not in db: db[ref] = {'buyer': 'N/A', 'style': 'N/A', 'challans': []}
    save_accessories_db(db)
    
    # Get colors
    colors = []
    api_data = fetch_closing_report_data(ref)
    if api_data:
        db[ref]['buyer'] = api_data[0].get('buyer', 'N/A')
        db[ref]['style'] = api_data[0].get('style', 'N/A')
        save_accessories_db(db)
        for b in api_data: 
            if b['color'] not in colors: colors.append(b['color'])
            
    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref, buyer=db[ref]['buyer'], style=db[ref]['style'], colors=colors, challans=db[ref]['challans'])

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    ref = request.form.get('ref')
    db = load_accessories_db()
    db[ref]['challans'].append({
        'date': get_bd_date_str(),
        'line': request.form.get('line_no'),
        'color': request.form.get('color'),
        'size': request.form.get('size'),
        'qty': int(request.form.get('qty')),
        'status': '✔',
        'item_type': request.form.get('item_type')
    })
    save_accessories_db(db)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/edit')
def accessories_edit():
    ref = request.args.get('ref')
    idx = int(request.args.get('index'))
    db = load_accessories_db()
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=idx, item=db[ref]['challans'][idx])

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    ref = request.form.get('ref')
    idx = int(request.form.get('index'))
    db = load_accessories_db()
    db[ref]['challans'][idx]['line'] = request.form.get('line_no')
    db[ref]['challans'][idx]['color'] = request.form.get('color')
    db[ref]['challans'][idx]['size'] = request.form.get('size')
    db[ref]['challans'][idx]['qty'] = int(request.form.get('qty'))
    save_accessories_db(db)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    ref = request.form.get('ref')
    idx = int(request.form.get('index'))
    db = load_accessories_db()
    del db[ref]['challans'][idx]
    save_accessories_db(db)
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/print')
def accessories_print():
    ref = request.args.get('ref')
    db = load_accessories_db()
    data = db.get(ref, {})
    challans = data.get('challans', [])
    line_sum = {}
    for c in challans:
        qty = int(c.get('qty', 0)) # Fixed: Ensure int for calculation
        line_sum[c['line']] = line_sum.get(c['line'], 0) + qty
        
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, ref=ref, buyer=data.get('buyer'), style=data.get('style'), challans=challans, count=len(challans), line_summary=line_sum, today=get_bd_date_str())

# --- Store Routes ---
@app.route('/admin/store')
def store_dashboard():
    return render_template_string(STORE_DASHBOARD_TEMPLATE, store_stats=get_store_dashboard_summary(), recent_invoices=load_store_invoices()[-5:][::-1], pending_dues=[], recent_estimates=load_store_estimates()[-5:][::-1])

@app.route('/store/products')
def store_products(): return render_template_string(STORE_PRODUCTS_TEMPLATE, products=load_store_products())

@app.route('/store/products/save', methods=['POST'])
def store_products_save():
    prods = load_store_products()
    prods.append({
        "name": request.form.get('name'), "size_feet": request.form.get('size_feet'),
        "thickness": request.form.get('thickness'), "category": request.form.get('category'),
        "price": float(request.form.get('price') or 0), "description": request.form.get('description')
    })
    save_store_products(prods)
    return redirect(url_for('store_products'))

@app.route('/store/products/edit/<int:index>')
def store_products_edit(index):
    return render_template_string(STORE_PRODUCT_EDIT_TEMPLATE, product=load_store_products()[index], index=index)

@app.route('/store/products/update', methods=['POST'])
def store_products_update():
    idx = int(request.form.get('index'))
    prods = load_store_products()
    prods[idx]['name'] = request.form.get('name')
    prods[idx]['price'] = float(request.form.get('price') or 0)
    save_store_products(prods)
    return redirect(url_for('store_products'))

@app.route('/store/products/delete/<int:index>', methods=['POST'])
def store_products_delete(index):
    prods = load_store_products()
    del prods[index]
    save_store_products(prods)
    return redirect(url_for('store_products'))

@app.route('/store/customers')
def store_customers(): return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=load_store_customers())

@app.route('/store/customers/save', methods=['POST'])
def store_customers_save():
    custs = load_store_customers()
    custs.append({"name": request.form.get('name'), "phone": request.form.get('phone'), "address": request.form.get('address')})
    save_store_customers(custs)
    return redirect(url_for('store_customers'))

@app.route('/store/customers/edit/<int:index>')
def store_customers_edit(index):
    return render_template_string(STORE_CUSTOMER_EDIT_TEMPLATE, customer=load_store_customers()[index], index=index)

@app.route('/store/customers/update', methods=['POST'])
def store_customers_update():
    idx = int(request.form.get('index'))
    custs = load_store_customers()
    custs[idx]['name'] = request.form.get('name')
    custs[idx]['phone'] = request.form.get('phone')
    custs[idx]['address'] = request.form.get('address')
    save_store_customers(custs)
    return redirect(url_for('store_customers'))

@app.route('/store/customers/delete/<int:index>', methods=['POST'])
def store_customers_delete(index):
    custs = load_store_customers()
    del custs[index]
    save_store_customers(custs)
    return redirect(url_for('store_customers'))

@app.route('/store/invoices/create')
def store_invoices_create():
    return render_template_string(STORE_INVOICE_CREATE_TEMPLATE, invoice_no=generate_invoice_number(), customers=load_store_customers(), today=get_bd_time().strftime('%Y-%m-%d'))

@app.route('/store/invoices/save', methods=['POST'])
def store_invoices_save():
    invs = load_store_invoices()
    items = []
    i = 0
    while f'items[{i}][description]' in request.form:
        items.append({
            "description": request.form.get(f'items[{i}][description]'),
            "size": request.form.get(f'items[{i}][size]'),
            "qty": int(request.form.get(f'items[{i}][qty]')),
            "price": float(request.form.get(f'items[{i}][price]')),
            "total": float(request.form.get(f'items[{i}][total]'))
        })
        i += 1
    
    new_inv = {
        "invoice_no": request.form.get('invoice_no'),
        "customer_name": request.form.get('customer_name'),
        "customer_phone": request.form.get('customer_phone'),
        "customer_address": request.form.get('customer_address'),
        "date": request.form.get('invoice_date'),
        "items": items,
        "total": float(request.form.get('total')),
        "paid": float(request.form.get('paid')),
        "due": float(request.form.get('due')),
        "notes": request.form.get('notes'),
        "payments": []
    }
    invs.append(new_inv)
    save_store_invoices(invs)
    
    if request.form.get('action') == 'save_print':
        return redirect(url_for('store_invoices_print', invoice_no=new_inv['invoice_no']))
    return redirect(url_for('store_invoices'))

@app.route('/store/invoices')
def store_invoices():
    invs = load_store_invoices()
    q = request.args.get('search', '').lower()
    if q: invs = [i for i in invs if q in i['invoice_no'].lower() or q in i['customer_name'].lower()]
    return render_template_string(STORE_INVOICES_LIST_TEMPLATE, invoices=invs, search_query=q)

@app.route('/store/invoices/view/<invoice_no>')
def store_invoices_view(invoice_no):
    inv = next((i for i in load_store_invoices() if i['invoice_no'] == invoice_no), None)
    if inv: return render_template_string(STORE_INVOICE_PRINT_TEMPLATE, invoice=inv)
    return "Not Found"

@app.route('/store/invoices/print/<invoice_no>')
def store_invoices_print(invoice_no):
    return store_invoices_view(invoice_no)

@app.route('/store/estimates')
def store_estimates(): return render_template_string(STORE_ESTIMATES_LIST_TEMPLATE, estimates=load_store_estimates())

@app.route('/store/estimates/create')
def store_estimates_create(): return render_template_string(STORE_ESTIMATE_CREATE_TEMPLATE, estimate_no=generate_estimate_number(), today=get_bd_time().strftime('%Y-%m-%d'))

@app.route('/store/estimates/save', methods=['POST'])
def store_estimates_save():
    ests = load_store_estimates()
    items = []
    i = 0
    while f'items[{i}][description]' in request.form:
        items.append({
            "description": request.form.get(f'items[{i}][description]'),
            "size": request.form.get(f'items[{i}][size]'),
            "qty": int(request.form.get(f'items[{i}][qty]')),
            "price": float(request.form.get(f'items[{i}][price]')),
            "total": float(request.form.get(f'items[{i}][total]'))
        })
        i += 1
    
    ests.append({
        "estimate_no": request.form.get('estimate_no'),
        "customer_name": request.form.get('customer_name'),
        "customer_phone": request.form.get('customer_phone'),
        "date": request.form.get('estimate_date'),
        "valid_until": request.form.get('valid_until'),
        "items": items,
        "total": float(request.form.get('total')),
        "discount": float(request.form.get('discount'))
    })
    save_store_estimates(ests)
    return redirect(url_for('store_estimates'))

@app.route('/store/estimates/print/<estimate_no>')
def store_estimates_print(estimate_no):
    est = next((e for e in load_store_estimates() if e['estimate_no'] == estimate_no), None)
    if est: return render_template_string(STORE_ESTIMATE_PRINT_TEMPLATE, estimate=est)
    return "Not Found"

@app.route('/store/estimates/to-invoice/<estimate_no>')
def store_estimate_to_invoice(estimate_no):
    return redirect(url_for('store_invoices_create'))

@app.route('/store/dues')
def store_dues(): return render_template_string(STORE_DUE_COLLECTION_TEMPLATE, invoice=None)

@app.route('/store/dues/search')
def store_dues_search():
    inv_no = request.args.get('invoice_no')
    inv = next((i for i in load_store_invoices() if i['invoice_no'] == inv_no), None)
    return render_template_string(STORE_DUE_COLLECTION_TEMPLATE, invoice=inv, search_invoice=inv_no)

@app.route('/store/dues/collect', methods=['POST'])
def store_dues_collect():
    inv_no = request.form.get('invoice_no')
    amt = float(request.form.get('amount'))
    invs = load_store_invoices()
    for i in invs:
        if i['invoice_no'] == inv_no:
            i['paid'] += amt
            i['due'] = i['total'] - i['paid']
            i['payments'].append({'date': request.form.get('payment_date'), 'amount': amt, 'notes': request.form.get('notes')})
            break
    save_store_invoices(invs)
    return redirect(url_for('store_dues_search', invoice_no=inv_no))

@app.route('/store/users')
def store_users_manage(): return render_template_string(STORE_USERS_TEMPLATE, users=load_store_users())

@app.route('/store/users/save', methods=['POST'])
def store_users_save():
    users = load_store_users()
    users[request.form.get('username')] = {"password": request.form.get('password'), "role": "store_staff", "permissions": []}
    save_store_users(users)
    return redirect(url_for('store_users_manage'))

@app.route('/store/users/delete/<username>', methods=['POST'])
def store_users_delete(username):
    users = load_store_users()
    if username in users: del users[username]
    save_store_users(users)
    return redirect(url_for('store_users_manage'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
