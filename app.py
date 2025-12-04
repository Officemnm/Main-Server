import requests
import openpyxl
from openpyxl. styles import Font, Alignment, Border, Side, PatternFill
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz 
from io import BytesIO
from openpyxl. drawing.image import Image
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

# PO ফাইলের জন্য আপলোড ফোল্ডার
UPLOAD_FOLDER = 'uploads'
if not os.path. exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# সেশন টাইমআউট কনফিগারেশন (2 মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2) 

# টাইমজোন কনফিগারেশন (বাংলাদেশ)
bd_tz = pytz. timezone('Asia/Dhaka')

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
    response. headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ==============================================================================
# MongoDB কানেকশন সেটআপ
# ==============================================================================
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office. jxdnuaj.mongodb.net/? appName=Office"

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
    record = users_col. find_one({"_id": "global_users"})
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
    record = stats_col. find_one({"_id": "dashboard_stats"})
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
        "time": now. strftime('%I:%M %p'),
        "type": "PO Sheet",
        "iso_time": now. isoformat()
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
        store_users_col. insert_one({"_id": "store_users_data", "data": default_users})
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
    record = store_estimates_col. find_one({"_id": "estimates_data"})
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
            num = int(inv['invoice_no']. split('-')[1])
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
    for u, d in users_data. items():
        user_details.append({
            "username": u,
            "role": d. get('role', 'user'),
            "created_at": d. get('created_at', 'N/A'),
            "last_login": d.get('last_login', 'Never'),
            "last_duration": d. get('last_duration', 'N/A')
        })

    # 2.   Accessories Today & Analytics - LIFETIME COUNT
    acc_lifetime_count = 0
    acc_today_list = []
    
    # Analytics Container: {'YYYY-MM-DD': {'label': '01-Dec', 'closing': 0, 'po': 0, 'acc': 0}}
    daily_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0})

    for ref, data in acc_db. items():
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
                sort_key = dt_obj. strftime('%Y-%m-%d')
                daily_data[sort_key]['acc'] += 1
                daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
            except: pass

    # 3.   Closing & PO - LIFETIME COUNT & Analytics
    closing_lifetime_count = 0
    po_lifetime_count = 0
    closing_list = []
    po_list = []
    
    history = stats_data.get('downloads', [])
    for item in history:
        item_date = item. get('date', '')
        if item. get('type') == 'PO Sheet':
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
            chart_labels.append(d. get('label', k))
            chart_closing.append(d['closing'])
            chart_po.append(d['po'])
            chart_acc. append(d['acc'])

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
            if inv_date. split('-')[1] + '-' + inv_date.split('-')[2] == current_month:
                monthly_sales += inv. get('total', 0)
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
# API CACHING HELPER - নতুন ফাংশন যোগ করা হয়েছে
# ==============================================================================

def should_refresh_api_data(last_api_call_time):
    """২৪ ঘন্টা পরে API রিফ্রেশ করা উচিত কিনা চেক করে"""
    if not last_api_call_time:
        return True
    try:
        last_call = datetime.fromisoformat(last_api_call_time)
        now = get_bd_time()
        # টাইমজোন aware করা
        if last_call. tzinfo is None:
            last_call = bd_tz.localize(last_call)
        time_diff = now - last_call
        return time_diff.total_seconds() > 86400  # 24 hours = 86400 seconds
    except:
        return True

def get_colors_from_cached_data(ref, acc_db):
    """ক্যাশ থেকে কালার লিস্ট বের করে"""
    colors = []
    if ref in acc_db:
        cached_colors = acc_db[ref].get('colors', [])
        if cached_colors:
            return cached_colors
        # চালান থেকে কালার বের করা
        for challan in acc_db[ref].get('challans', []):
            color = challan.get('color', '')
            if color and color not in colors:
                colors.append(color)
    return colors
    # ==============================================================================
# ENHANCED CSS STYLES - PREMIUM MODERN UI WITH ANIMATIONS
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all. min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4. 1.1/animate.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/particles.js@2.0.0/particles.min. js"></script>
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
            --transition-smooth: all 0. 4s cubic-bezier(0.4, 0, 0.2, 1);
            --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
            --shadow-glow: 0 0 40px rgba(255, 122, 0, 0.15);
            --gradient-orange: linear-gradient(135deg, #FF7A00 0%, #FF9A40 100%);
            --gradient-dark: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
            --gradient-card: linear-gradient(145deg, rgba(22, 22, 31, 0.9) 0%, rgba(16, 16, 22, 0. 95) 100%);
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
        . animated-bg {
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
            background: rgba(22, 22, 31, 0. 7);
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
        . sidebar::before {
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
        
        . nav-menu { 
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

        . nav-link::before {
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
        . nav-link:hover::before, .nav-link. active::before { width: 100%; }

        .nav-link:hover, .nav-link. active { 
            color: var(--accent-orange); 
            transform: translateX(5px);
        }

        .nav-link.active {
            background: rgba(255, 122, 0, 0.1);
            border-left: 3px solid var(--accent-orange);
            box-shadow: 0 0 20px var(--accent-orange-glow);
        }

        . nav-link i { 
            width: 24px;
            margin-right: 12px; 
            font-size: 18px; 
            text-align: center;
            transition: var(--transition-smooth);
        }

        .nav-link:hover i {
            transform: scale(1. 2);
            filter: drop-shadow(0 0 8px var(--accent-orange));
        }

        . nav-link . nav-badge {
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
            border-color: rgba(16, 185, 129, 0. 3);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
        }
        
        /* FIXED: Glowing Green Status Dot */
        . status-dot {
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
                0 0 30px rgba(16, 185, 129, 0. 5);
        }
        
        . status-dot::before {
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
        
        . status-dot::after {
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
                opacity: 0. 8;
                box-shadow: 
                    0 0 10px var(--accent-green),
                    0 0 20px var(--accent-green),
                    0 0 40px var(--accent-green),
                    0 0 60px rgba(16, 185, 129, 0. 6);
            }
        }
        
        @keyframes statusPulseRing {
            0% {
                transform: translate(-50%, -50%) scale(1);
                opacity: 0.8;
            }
            100% {
                transform: translate(-50%, -50%) scale(2. 5);
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

        .stat-card:hover . stat-icon i {
            animation: iconBounce 0.5s ease-out;
        }

        @keyframes iconBounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1. 3); }
        }

        . stat-info h3 { 
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
            letter-spacing: 1. 5px;
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

        . progress-bar-fill::after {
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

        . progress-orange { background: var(--gradient-orange); }
        .progress-purple { background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); }
        . progress-green { background: linear-gradient(135deg, #10B981 0%, #34D399 100%); }
        
        /* Enhanced Forms */
        .input-group { margin-bottom: 20px; }

        .input-group label { 
            display: block;
            font-size: 11px; 
            color: var(--text-secondary); 
            margin-bottom: 8px; 
            text-transform: uppercase; 
            font-weight: 700;
            letter-spacing: 1. 5px;
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
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3. org/2000/svg' fill='%23FF7A00' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
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
        
        button, . btn-primary { 
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
            box-shadow: 0 10px 30px rgba(16, 185, 129, 0. 3);
        }
        
        . btn-danger {
            background: linear-gradient(135deg, #EF4444 0%, #F87171 100%);
        }
        
        .btn-danger:hover {
            box-shadow: 0 10px 30px rgba(239, 68, 68, 0. 3);
        }
        
        . btn-purple {
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

        . btn-edit { 
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
            background: rgba(239, 68, 68, 0. 15);
            color: #F87171; 
        }

        . btn-del:hover { 
            background: var(--accent-red);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(239, 68, 68, 0. 4);
        }
        
        .btn-view {
            background: rgba(59, 130, 246, 0. 15);
            color: #60A5FA;
        }
        
        .btn-view:hover {
            background: var(--accent-blue);
            color: white;
            transform: scale(1. 1);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
        }
        
        .btn-print-sm {
            background: rgba(16, 185, 129, 0. 15);
            color: #34D399;
        }
        
        .btn-print-sm:hover {
            background: var(--accent-green);
            color: white;
            transform: scale(1. 1);
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

        . spinner-inner {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 3px solid rgba(139, 92, 246, 0. 1);
            border-bottom: 3px solid var(--accent-purple);
            border-left: 3px solid var(--accent-purple);
            border-radius: 50%;
            animation: spin 1. 2s linear infinite reverse;
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
            box-shadow: 0 0 40px rgba(16, 185, 129, 0. 3);
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
            animation: checkmark-anim 0.4s 0. 4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }
        
        /* Fail Cross Animation */
        . fail-container { 
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
            animation: fail-anim 0.6s cubic-bezier(0. 4, 0, 0.2, 1) forwards;
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

        . fail-circle::before { transform: rotate(45deg); }
        .fail-circle::after { transform: rotate(-45deg); }

        @keyframes success-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1. 2); } 
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

        . anim-text { 
            font-size: 24px; 
            font-weight: 800; 
            color: white;
            margin-top: 10px; 
            letter-spacing: 1px;
        }

        . loading-text {
            color: var(--text-secondary);
            font-size: 15px;
            margin-top: 20px;
            font-weight: 500;
            letter-spacing: 2px;
            text-transform: uppercase;
            animation: textPulse 1. 5s ease-in-out infinite;
        }

        @keyframes textPulse {
            0%, 100% { opacity: 0. 5; }
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
            background: rgba(10, 10, 15, 0. 9);
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
        
        . welcome-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 50px 60px;
            text-align: center;
            max-width: 500px;
            width: 90%;
            animation: welcomeSlideIn 0. 5s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            position: relative;
            overflow: hidden;
        }

        . welcome-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, var(--accent-orange-glow) 0%, transparent 60%);
            animation: welcomeGlow 3s ease-in-out infinite;
            opacity: 0. 3;
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

        . welcome-greeting {
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

        . upload-zone::before {
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

        . upload-zone:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .upload-zone:hover::before {
            opacity: 0.03;
        }

        .upload-zone. dragover {
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
        . flash-message {
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

        . flash-error {
            background: rgba(239, 68, 68, 0. 1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #F87171;
        }

        .flash-success {
            background: rgba(16, 185, 129, 0. 1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #34D399;
        }
        
        . flash-warning {
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
        . mobile-toggle { 
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
            . sidebar. active { 
                transform: translateX(0);
            }
            . main-content { 
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
            . stats-grid {
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
        . skeleton {
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
            background: rgba(16, 185, 129, 0. 1);
            border-radius: 20px;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }

        . realtime-dot {
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
            transition: opacity 0. 3s;
        }

        . animated-border:hover::after {
            opacity: 1;
        }

        @keyframes gradientBorder {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Permission Checkbox Styles */
        . perm-checkbox {
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

        . perm-checkbox input {
            width: auto;
            margin-right: 10px;
            accent-color: var(--accent-orange);
        }

        .perm-checkbox span {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }

        . perm-checkbox:has(input:checked) {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.1);
        }

        . perm-checkbox:has(input:checked) span {
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

        . time-badge i {
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
            background: rgba(10, 10, 15, 0. 9);
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
            animation: modalSlideIn 0. 3s ease-out;
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
        
        . modal-header {
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
        
        . search-box input {
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
        . tab-nav {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }
        
        . tab-btn {
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
            background: rgba(255, 122, 0, 0. 15);
        }
        
        . tab-content {
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
        
        . amount-due {
            color: var(--accent-red);
        }
        
        /* Empty State */
        . empty-state {
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
        
        . empty-state p {
            font-size: 16px;
            margin-bottom: 20px;
        }
        
        /* Current Entry Indicator - নতুন যোগ করা হয়েছে */
        . current-entry {
            background: rgba(255, 122, 0, 0.1) !important;
            border-left: 3px solid var(--accent-orange) !important;
        }
        
        . current-entry . status-cell {
            color: var(--accent-orange) !important;
        }
        
        /* API Cache Indicator */
        . cache-indicator {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }
        
        . cache-fresh {
            background: rgba(16, 185, 129, 0. 1);
            color: var(--accent-green);
        }
        
        .cache-stale {
            background: rgba(245, 158, 11, 0. 1);
            color: #FBBF24;
        }
    </style>
"""
# ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PDF)
# ==============================================================================

def is_potential_size(header):
    h = header.strip(). upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P. O NO"]:
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
        buyer_match = re. search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(? :\n|$)", first_page_text)
        if buyer_match: meta['buyer'] = buyer_match.group(1).strip()

    booking_block_match = re.search(r"(? :Internal )?Booking NO\.  ?  [:\s]*([\s\S]*?)(? :System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match: 
        raw_booking = booking_block_match.group(1).strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking: clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\. ? [:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match: meta['style'] = style_match.group(1).strip()
    else:
        style_match = re.search(r"Style Des\. ?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match: meta['style'] = style_match.group(1).strip()

    season_match = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re. IGNORECASE)
    if season_match: meta['season'] = season_match.group(1). strip()
    dept_match = re. search(r"Dept\.  ?[\s\n:]*([A-Za-z]+)", first_page_text, re. IGNORECASE)
    if dept_match: meta['dept'] = dept_match. group(1).strip()

    item_match = re.search(r"Garments?     Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
    if item_match: 
        item_text = item_match.group(1).strip()
        if "Style" in item_text: item_text = item_text.split("Style")[0]. strip()
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
            alt_match = re.search(r"Order\s*[:\.]?\s*(\d+)", first_page_text, re. IGNORECASE)
            if alt_match: order_no = alt_match.group(1)
        
        order_no = str(order_no).strip()
        if order_no. endswith("00"): order_no = order_no[:-2]

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
                    lower_line = line. lower()
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line:
                        continue
                        
                    clean_line = line. replace("Spec.  price", ""). replace("Spec", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line): continue
                    if re.match(r'^[A-Z]\d+$', clean_line) or "Assortment" in clean_line: continue

                    numbers_in_line = re. findall(r'\b\d+\b', line)
                    quantities = [int(n) for n in numbers_in_line]
                    color_name = clean_line
                    final_qtys = []

                    if len(quantities) >= len(sizes):
                        if len(quantities) == len(sizes) + 1: final_qtys = quantities[:-1] 
                        else: final_qtys = quantities[:len(sizes)]
                        color_name = re.sub(r'\s\d+$', '', color_name). strip()
                    elif len(quantities) < len(sizes): 
                        vertical_qtys = []
                        for next_line in lines[i+1:]:
                            next_line = next_line.strip()
                            if "Total" in next_line or re.search(r'[a-zA-Z]', next_line. replace("Spec", "").replace("price", "")): break
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
    login_url = 'http://180.92.235.190:8022/erp/login. php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    try:
        response = session_req.post(login_url, data=login_payload, timeout=300)
        if "dashboard. php" in response. url or "Invalid" not in response.text:
            return session_req
        else:
            return None
    except requests. exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def fetch_closing_report_data(internal_ref_no):
    """API থেকে ক্লোজিং রিপোর্ট ডাটা ফেচ করে"""
    active_session = get_authenticated_session("input2. clothing-cutting", "123456")
    if not active_session: return None

    report_url = 'http://180. 92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload_template = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'cbo_floor_id': '0', 'cbo_buyer_name': '0', 'txt_internal_ref_no': internal_ref_no, 'reportType': '3'}
    found_data = None
   
    for year in ['2025', '2024']:
        for company_id in range(1, 6):
            payload = payload_template.copy()
            payload['cbo_year_selection'] = year
            payload['cbo_company_name'] = str(company_id)
            try:
                response = active_session.post(report_url, data=payload, timeout=300)
                if response.status_code == 200 and "Data not Found" not in response. text:
                    found_data = response.text
                    break
            except: continue
        if found_data: break
    
    if found_data:
        return parse_report_data(found_data)
    return None

def fetch_closing_report_data_with_cache(internal_ref_no):
    """
    ক্যাশিং সহ API থেকে ডাটা ফেচ করে।
    - যদি ডাটা ক্যাশে থাকে এবং ২৪ ঘন্টার মধ্যে ফেচ করা হয়েছে, ক্যাশ থেকে রিটার্ন করে
    - অন্যথায় নতুন API কল করে এবং ক্যাশ আপডেট করে
    """
    acc_db = load_accessories_db()
    ref = internal_ref_no. upper()
    
    # চেক করা যে ডাটা ক্যাশে আছে কিনা এবং ২৪ ঘন্টার মধ্যে আপডেট হয়েছে কিনা
    if ref in acc_db:
        last_api_call = acc_db[ref]. get('last_api_call')
        cached_colors = acc_db[ref].get('colors', [])
        
        # যদি ২৪ ঘন্টার মধ্যে API কল হয়ে থাকে এবং কালার ক্যাশ আছে
        if not should_refresh_api_data(last_api_call) and cached_colors:
            print(f"[CACHE HIT] Using cached data for {ref}")
            return {
                'colors': cached_colors,
                'buyer': acc_db[ref].get('buyer', 'N/A'),
                'style': acc_db[ref].get('style', 'N/A'),
                'from_cache': True,
                'last_updated': last_api_call
            }
    
    # নতুন API কল করা
    print(f"[API CALL] Fetching fresh data for {ref}")
    report_data = fetch_closing_report_data(ref)
    
    colors = []
    buyer = "N/A"
    style = "N/A"
    
    if report_data:
        for block in report_data:
            color_name = block.get('color', '')
            if color_name and color_name not in colors:
                colors.append(color_name)
            if block.get('buyer') != 'N/A':
                buyer = block.get('buyer')
            if block. get('style') != 'N/A':
                style = block.get('style')
    
    # ক্যাশ আপডেট করা
    if ref not in acc_db:
        acc_db[ref] = {
            "buyer": buyer,
            "style": style,
            "colors": colors,
            "challans": [],
            "last_api_call": get_bd_time(). isoformat()
        }
    else:
        acc_db[ref]['buyer'] = buyer if buyer != 'N/A' else acc_db[ref]. get('buyer', 'N/A')
        acc_db[ref]['style'] = style if style != 'N/A' else acc_db[ref].get('style', 'N/A')
        acc_db[ref]['colors'] = colors if colors else acc_db[ref].get('colors', [])
        acc_db[ref]['last_api_call'] = get_bd_time().isoformat()
    
    save_accessories_db(acc_db)
    
    return {
        'colors': colors,
        'buyer': buyer,
        'style': style,
        'from_cache': False,
        'last_updated': get_bd_time().isoformat()
    }

def parse_report_data(html_content):
    all_report_data = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row: return None
        all_th = header_row. find_all('th')
        headers = [th.get_text(strip=True) for th in all_th if 'total' not in th.get_text(strip=True).lower()]
        data_rows = soup. select('div#scroll_body table tbody tr')
        item_blocks = []
        current_block = []
        for row in data_rows:
            if row.get('bgcolor') == '#cddcdc':
                if current_block: item_blocks.append(current_block)
                current_block = []
            else:
                current_block. append(row)
        if current_block: item_blocks. append(current_block)
        
        for block in item_blocks:
            style, color, buyer_name, gmts_qty_data, sewing_input_data, cutting_qc_data = "N/A", "N/A", "N/A", None, None, None
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0]. get_text(strip=True)
                    criteria_sub = cells[2].get_text(strip=True)
                    main_lower, sub_lower = criteria_main.lower(), criteria_sub.lower()
                    
                    if main_lower == "style": style = cells[1].get_text(strip=True)
                    elif main_lower == "color & gmts.  item": color = cells[1].get_text(strip=True)
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
                        new_qty = round(int(value. replace(',', '')) * 1.03)
                        plus_3_percent_data.append(str(new_qty))
                    except (ValueError, TypeError):
                        plus_3_percent_data. append(value)
                all_report_data. append({
                    'style': style, 'buyer': buyer_name, 'color': color, 
                    'headers': headers, 'gmts_qty': gmts_qty_data, 
                    'plus_3_percent': plus_3_percent_data, 
                    'sewing_input': sewing_input_data if sewing_input_data else [], 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
        return all_report_data
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl. Workbook()
    ws = wb. active
    ws. title = "Closing Report"
    # Styles
    bold_font = Font(bold=True)
    title_font = Font(size=32, bold=True, color="7B261A") 
    white_bold_font = Font(size=16. 5, bold=True, color="FFFFFF")
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

    ws. merge_cells(start_row=2, start_column=1, end_row=2, end_column=NUM_COLUMNS)
    ws['A2'].value = "CLOSING REPORT [ INPUT SECTION ]"
    ws['A2'].font = Font(size=15, bold=True) 
    ws['A2'].alignment = center_align
    ws. row_dimensions[3].height = 6

    formatted_ref_no = internal_ref_no.upper()
    current_date = get_bd_time().strftime("%d/%m/%Y")
    
    left_sub_headers = {
        'A4': 'BUYER', 'B4': report_data[0]. get('buyer', ''), 
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
            cell. fill = dark_green_fill 

    ws.merge_cells('B4:G4'); ws. merge_cells('B5:G5'); ws.merge_cells('B6:G6')
    
    right_sub_headers = {'H4': 'CLOSING DATE', 'I4': current_date, 'H5': 'SHIPMENT', 'I5': 'ALL', 'H6': 'PO NO', 'I6': 'ALL'}
    for cell_ref, value in right_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell. font = bold_font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = dark_green_fill 

    for row in range(4, 7):
        for col in range(3, 8): 
            cell = ws. cell(row=row, column=col)
            cell.border = thin_border
       
    current_row = TABLE_START_ROW
    for block in report_data:
        table_headers = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for col_idx, header in enumerate(table_headers, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=header)
            cell.font = bold_font
            cell.alignment = center_align
            cell. border = medium_border
            cell.fill = header_row_fill 

        current_row += 1
        start_merge_row = current_row
        full_color_name = block. get('color', 'N/A')

        for i, size in enumerate(block['headers']):
            color_to_write = full_color_name if i == 0 else ""
            actual_qty = int(block['gmts_qty'][i]. replace(',', '') or 0)
            input_qty = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cutting_qc_val = int(block. get('cutting_qc', [])[i].replace(',', '') or 0) if i < len(block.get('cutting_qc', [])) else 0
            
            ws.cell(row=current_row, column=1, value=color_to_write)
            ws.cell(row=current_row, column=2, value=size)
            ws.cell(row=current_row, column=4, value=actual_qty)
            ws.cell(row=current_row, column=5, value=cutting_qc_val)
            ws.cell(row=current_row, column=6, value=input_qty)
            
            ws.cell(row=current_row, column=3, value=f"=ROUND(D{current_row}*1.03, 0)")      
            ws.cell(row=current_row, column=7, value=f"=E{current_row}-F{current_row}")      
            ws.cell(row=current_row, column=8, value=f"=F{current_row}-C{current_row}")      
            ws. cell(row=current_row, column=9, value=f'=IF(C{current_row}<>0, H{current_row}/C{current_row}, 0)') 
            
            for col_idx in range(1, NUM_COLUMNS + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = medium_border if col_idx == 2 else thin_border
                cell.alignment = center_align
    
                if col_idx in [1, 2, 3, 6, 9]: cell.font = bold_font
                
                if col_idx == 3: cell.fill = light_blue_fill      
                elif col_idx == 6: cell.fill = light_green_fill   
                else: cell.fill = dark_green_fill 

                if col_idx == 9:
                    cell. number_format = '0.00%' 
            current_row += 1
            
        end_merge_row = current_row - 1
        if start_merge_row <= end_merge_row:
            ws. merge_cells(start_row=start_merge_row, start_column=1, end_row=end_merge_row, end_column=1)
            merged_cell = ws. cell(row=start_merge_row, column=1)
            merged_cell. alignment = color_align
            if not merged_cell.font. bold: merged_cell.font = bold_font
        
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
            cell = ws. cell(row=current_row, column=col_idx)
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
        padded_img = PILImage.new('RGBA', (original_img.width + 400, original_img. height), (0, 0, 0, 0))
        padded_img.paste(original_img, (400, 0))
        padded_image_io = BytesIO()
        padded_img.save(padded_image_io, format='PNG')
        img = Image(padded_image_io)
        aspect_ratio = padded_img.height / padded_img.width
        img.width = 95
        img.height = int(img.width * aspect_ratio)
        ws. row_dimensions[image_row].height = img.height * 0.90
        ws.add_image(img, f'A{image_row}')
    except Exception:
        pass

    signature_row = image_row + 1
    ws.merge_cells(start_row=signature_row, start_column=1, end_row=signature_row, end_column=NUM_COLUMNS)
    titles = ["Prepared By", "Input Incharge", "Cutting Incharge", "IE & Planning", "Sewing Manager", "Cutting Manager"]
    signature_cell = ws. cell(row=signature_row, column=1)
    signature_cell.value = "                 ". join(titles)
    signature_cell. font = Font(bold=True, size=15)
    signature_cell.alignment = Alignment(horizontal='center', vertical='center')

    last_data_row = current_row - 2
    for row in ws.iter_rows(min_row=4, max_row=last_data_row):
        for cell in row:
            if cell.coordinate == 'B5': continue
            if cell. font:
                existing_font = cell.font
                if cell.row != 1: 
                    new_font = Font(name=existing_font. name, size=16. 5, bold=existing_font.bold, italic=existing_font. italic, vertAlign=existing_font.vertAlign, underline=existing_font.underline, strike=existing_font. strike, color=existing_font.color)
                    cell.font = new_font
    ws.column_dimensions['A'].width = 23
    ws.column_dimensions['B']. width = 8. 5
    ws. column_dimensions['C'].width = 20
    ws.column_dimensions['D']. width = 17
    ws.column_dimensions['E']. width = 17
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G']. width = 13. 5
    ws. column_dimensions['H'].width = 23
    ws.column_dimensions['I']. width = 18
   
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.fitToPage = True
    ws.page_setup. fitToWidth = 1
    ws.page_setup.fitToHeight = 1 
    ws.page_setup.horizontalCentered = True
    ws.page_setup.verticalCentered = False 
    ws.page_setup.left = 0. 25
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
# HTML TEMPLATES: LOGIN PAGE - FIXED RESPONSIVE & CENTERED
# ==============================================================================

LOGIN_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0, maximum-scale=1. 0, user-scalable=no">
    <title>Login - MNM Software</title>
    """ + COMMON_STYLES + """
    <style>
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }
        
        body {
            background: var(--bg-body);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            overflow-y: auto;
        }
        
        /* Animated Background Orbs */
        . bg-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: orbFloat 20s ease-in-out infinite;
            pointer-events: none;
        }
        
        . orb-1 {
            width: 300px;
            height: 300px;
            background: var(--accent-orange);
            top: -100px;
            left: -100px;
            animation-delay: 0s;
        }
        
        .orb-2 {
            width: 250px;
            height: 250px;
            background: var(--accent-purple);
            bottom: -50px;
            right: -50px;
            animation-delay: -5s;
        }
        
        . orb-3 {
            width: 150px;
            height: 150px;
            background: var(--accent-green);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            animation-delay: -10s;
        }
        
        @keyframes orbFloat {
            0%, 100% { transform: translate(0, 0) scale(1); }
            25% { transform: translate(30px, -30px) scale(1.05); }
            50% { transform: translate(-20px, 20px) scale(0.95); }
            75% { transform: translate(15px, 30px) scale(1.02); }
        }
        
        . login-container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 420px;
            padding: 20px;
            margin: auto;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 100vh;
        }
        
        . login-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px 35px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            animation: loginCardAppear 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        @keyframes loginCardAppear {
            from {
                opacity: 0;
                transform: translateY(30px) scale(0.95);
            }
            to {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        .brand-section {
            text-align: center;
            margin-bottom: 35px;
        }
        
        . brand-icon {
            width: 70px;
            height: 70px;
            background: var(--gradient-orange);
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 32px;
            color: white;
            margin-bottom: 18px;
            box-shadow: 0 15px 40px var(--accent-orange-glow);
            animation: brandIconPulse 3s ease-in-out infinite;
        }
        
        @keyframes brandIconPulse {
            0%, 100% { transform: scale(1) rotate(0deg); box-shadow: 0 15px 40px var(--accent-orange-glow); }
            50% { transform: scale(1.05) rotate(5deg); box-shadow: 0 20px 50px var(--accent-orange-glow); }
        }
        
        .brand-name {
            font-size: 28px;
            font-weight: 900;
            color: white;
            letter-spacing: -1px;
        }
        
        .brand-name span {
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .brand-tagline {
            color: var(--text-secondary);
            font-size: 11px;
            letter-spacing: 2px;
            margin-top: 6px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .login-form . input-group {
            margin-bottom: 20px;
        }
        
        .login-form .input-group label {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .login-form . input-group label i {
            color: var(--accent-orange);
            font-size: 13px;
        }
        
        . login-form input {
            padding: 14px 18px;
            font-size: 14px;
            border-radius: 12px;
        }
        
        .login-btn {
            margin-top: 8px;
            padding: 14px 24px;
            font-size: 15px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        .login-btn i {
            transition: transform 0.3s;
        }
        
        .login-btn:hover i {
            transform: translateX(5px);
        }
        
        . error-box {
            margin-top: 20px;
            padding: 14px 18px;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 10px;
            color: #F87171;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: errorShake 0.5s ease-out;
        }
        
        @keyframes errorShake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-5px); }
            40%, 80% { transform: translateX(5px); }
        }
        
        .footer-credit {
            text-align: center;
            margin-top: 25px;
            color: var(--text-secondary);
            font-size: 11px;
            opacity: 0. 5;
            font-weight: 500;
        }
        
        .footer-credit a {
            color: var(--accent-orange);
            text-decoration: none;
        }
        
        /* Responsive Fixes */
        @media (max-width: 480px) {
            .login-container {
                padding: 15px;
            }
            
            .login-card {
                padding: 30px 25px;
                border-radius: 20px;
            }
            
            .brand-icon {
                width: 60px;
                height: 60px;
                font-size: 28px;
            }
            
            . brand-name {
                font-size: 24px;
            }
            
            . brand-tagline {
                font-size: 10px;
            }
            
            .login-form input {
                padding: 12px 16px;
                font-size: 14px;
            }
            
            . login-btn {
                padding: 12px 20px;
                font-size: 14px;
            }
        }
        
        @media (max-height: 700px) {
            .login-container {
                min-height: auto;
                padding-top: 30px;
                padding-bottom: 30px;
            }
            
            .brand-section {
                margin-bottom: 25px;
            }
            
            . brand-icon {
                width: 60px;
                height: 60px;
                font-size: 26px;
                margin-bottom: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>
    
    <div class="login-container">
        <div class="login-card">
            <div class="brand-section">
                <div class="brand-icon">
                    <i class="fas fa-layer-group"></i>
                </div>
                <div class="brand-name">MNM<span>Software</span></div>
                <div class="brand-tagline">Secure Access Portal</div>
            </div>
            
            <form action="/login" method="post" class="login-form">
                <div class="input-group">
                    <label><i class="fas fa-user"></i> USERNAME</label>
                    <input type="text" name="username" required placeholder="Enter your ID" autocomplete="off">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-lock"></i> PASSWORD</label>
                    <input type="password" name="password" required placeholder="Enter your Password">
                </div>
                <button type="submit" class="login-btn">
                    Sign In <i class="fas fa-arrow-right"></i>
                </button>
            </form>
            
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="error-box">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{ messages[0] }}</span>
                    </div>
                {% endif %}
            {% endwith %}
            
            <div class="footer-credit">
                © 2025 <a href="#">Mehedi Hasan</a> • All Rights Reserved
            </div>
        </div>
    </div>
    
    <script>
        // Add ripple effect to button
        document.querySelector('.login-btn'). addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.classList. add('ripple-effect');
            const rect = this.getBoundingClientRect();
            ripple.style.left = (e.clientX - rect.left) + 'px';
            ripple.style. top = (e. clientY - rect. top) + 'px';
            this.appendChild(ripple);
            setTimeout(() => ripple. remove(), 600);
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# ADMIN DASHBOARD TEMPLATE - MODERN UI WITH DEW STYLE CHART
# ==============================================================================

ADMIN_DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Dashboard - MNM Software</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    <div id="particles-js"></div>

    <div class="welcome-modal" id="welcomeModal">
        <div class="welcome-content">
            <div class="welcome-icon" id="welcomeIcon"><i class="fas fa-hand-sparkles"></i></div>
            <div class="welcome-greeting" id="greetingText">Good Morning</div>
            <div class="welcome-title">Welcome Back, <span>{{ session.user }}</span>!</div>
            <div class="welcome-message">
                You're now logged into the MNM Software Dashboard. 
                All systems are operational and ready for your commands.
            </div>
            <button class="welcome-close" onclick="closeWelcome()">
                <i class="fas fa-rocket" style="margin-right: 8px;"></i> Let's Go! 
            </button>
        </div>
    </div>

    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner" id="spinner-anim"></div>
            <div class="spinner-inner"></div>
        </div>
        
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Successful! </div>
        </div>

        <div class="fail-container" id="fail-anim">
            <div class="fail-circle"></div>
            <div class="anim-text">Action Failed! </div>
            <div style="font-size:13px; color:#F87171; margin-top:8px;">Please check server or inputs</div>
        </div>
        
        <div class="loading-text" id="loading-text">Processing Request...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('. sidebar'). classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-layer-group"></i> 
            MNM<span>Software</span>
        </div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)">
                <i class="fas fa-home"></i> Dashboard
                <span class="nav-badge">Live</span>
            </div>
            <div class="nav-link" onclick="showSection('analytics', this)">
                <i class="fas fa-chart-pie"></i> Closing Report
            </div>
            <a href="/admin/accessories" class="nav-link">
                <i class="fas fa-database"></i> Accessories Challan
            </a>
            <div class="nav-link" onclick="showSection('help', this)">
                <i class="fas fa-file-invoice"></i> PO Generator
            </div>
            <div class="nav-link" onclick="showSection('settings', this)">
                <i class="fas fa-users-cog"></i> User Manage
            </div>
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-store"></i> Store
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">
            <i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan
        </div>
    </div>

    <div class="main-content">
        
        <div id="section-dashboard">
            <div class="header-section">
                <div>
                    <div class="page-title">Main Dashboard</div>
                    <div class="page-subtitle">Lifetime Overview & Analytics</div>
                </div>
                <div class="status-badge">
                    <div class="status-dot"></div>
                    <span>Online</span>
                </div>
            </div>
            
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="flash-message flash-error">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{ messages[0] }}</span>
                    </div>
                {% endif %}
            {% endwith %}

            <div class="stats-grid">
                <div class="card stat-card" style="animation-delay: 0. 1s;">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats.closing. count }}">0</h3>
                        <p>Lifetime Closing</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.2s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                        <i class="fas fa-boxes" style="color: var(--accent-purple);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats.accessories.count }}">0</h3>
                        <p>Lifetime Accessories</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.3s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                        <i class="fas fa-file-pdf" style="color: var(--accent-green);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats.po. count }}">0</h3>
                        <p>Lifetime PO Sheets</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.4s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0. 15), rgba(59, 130, 246, 0. 05));">
                        <i class="fas fa-users" style="color: var(--accent-blue);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats. users.count }}">0</h3>
                        <p>Total Users</p>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span>Daily Activity Chart</span>
                        <div class="realtime-indicator">
                            <div class="realtime-dot"></div>
                            <span>Real-time</span>
                        </div>
                    </div>
                    <div class="chart-container" style="height: 320px;">
                        <canvas id="mainChart"></canvas>
                    </div>
                </div>
                <div class="card">
                    <div class="section-header">
                        <span>Module Usage</span>
                        <i class="fas fa-chart-bar" style="color: var(--accent-orange);"></i>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-header">
                            <span>Closing Report</span>
                            <span class="progress-value">{{ stats.closing.count }} Lifetime</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill progress-orange" style="width: 85%;"></div>
                        </div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-header">
                            <span>Accessories</span>
                            <span class="progress-value">{{ stats. accessories.count }} Challans</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill progress-purple" style="width: 65%;"></div>
                        </div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-header">
                            <span>PO Generator</span>
                            <span class="progress-value">{{ stats.po.count }} Files</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill progress-green" style="width: 45%;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Recent Activity Log</span>
                    <i class="fas fa-history" style="color: var(--text-secondary);"></i>
                </div>
                <div style="overflow-x: auto;">
                    <table class="dark-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>User</th>
                                <th>Action</th>
                                <th>Reference</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for log in stats.history[:10] %}
                            <tr style="animation: fadeInUp 0. 5s ease-out {{ loop.index * 0.05 }}s backwards;">
                                <td>
                                    <div class="time-badge">
                                        <i class="far fa-clock"></i>
                                        {{ log.time }}
                                    </div>
                                </td>
                                <td style="font-weight: 600; color: white;">{{ log.user }}</td>
                                <td>
                                    <span class="table-badge" style="
                                        {% if log.type == 'Closing Report' %}
                                        background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);
                                        {% elif log.type == 'PO Sheet' %}
                                        background: rgba(16, 185, 129, 0. 1); color: var(--accent-green);
                                        {% else %}
                                        background: rgba(139, 92, 246, 0. 1); color: var(--accent-purple);
                                        {% endif %}
                                    ">{{ log.type }}</span>
                                </td>
                                <td style="color: var(--text-secondary);">{{ log.ref if log.ref else '-' }}</td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="4" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                    <i class="fas fa-inbox" style="font-size: 40px; opacity: 0.3; margin-bottom: 15px; display: block;"></i>
                                    No activity recorded yet.
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="section-analytics" style="display:none;">
            <div class="header-section">
                <div>
                    <div class="page-title">Closing Report</div>
                    <div class="page-subtitle">Generate production closing reports</div>
                </div>
            </div>
            <div class="card" style="max-width: 550px; margin: 0 auto; margin-top: 30px;">
                <div class="section-header">
                    <span><i class="fas fa-magic" style="margin-right: 10px; color: var(--accent-orange);"></i>Generate Report</span>
                </div>
                <form action="/generate-report" method="post" onsubmit="return showLoading()">
                    <div class="input-group">
                        <label><i class="fas fa-bookmark" style="margin-right: 5px;"></i> INTERNAL REF NO</label>
                        <input type="text" name="ref_no" placeholder="e.g.  IB-12345 or Booking-123" required>
                    </div>
                    <button type="submit">
                        <i class="fas fa-bolt" style="margin-right: 10px;"></i> Generate Report
                    </button>
                </form>
            </div>
        </div>

        <div id="section-help" style="display:none;">
            <div class="header-section">
                <div>
                    <div class="page-title">PO Sheet Generator</div>
                    <div class="page-subtitle">Process and generate PO summary sheets</div>
                </div>
            </div>
            <div class="card" style="max-width: 650px; margin: 0 auto; margin-top: 30px;">
                <div class="section-header">
                    <span><i class="fas fa-file-pdf" style="margin-right: 10px; color: var(--accent-green);"></i>Upload PDF Files</span>
                </div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="return showLoading()">
                    <div class="upload-zone" id="uploadZone" onclick="document.getElementById('file-upload').click()">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display: none;" id="file-upload">
                        <div class="upload-icon">
                            <i class="fas fa-cloud-upload-alt"></i>
                        </div>
                        <div class="upload-text">Click or Drag to Upload PDF Files</div>
                        <div class="upload-hint">Supports multiple PDF files</div>
                        <div id="file-count">No files selected</div>
                    </div>
                    <button type="submit" style="margin-top: 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-cogs" style="margin-right: 10px;"></i> Process Files
                    </button>
                </form>
            </div>
        </div>

        <div id="section-settings" style="display:none;">
            <div class="header-section">
                <div>
                    <div class="page-title">User Management</div>
                    <div class="page-subtitle">Manage user accounts and permissions</div>
                </div>
            </div>
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span>User Directory</span>
                        <span class="table-badge" style="background: var(--accent-orange); color: white;">{{ stats.users.count }} Users</span>
                    </div>
                    <div id="userTableContainer" style="max-height: 450px; overflow-y: auto;">
                        <div class="skeleton" style="height: 50px; margin-bottom: 10px;"></div>
                        <div class="skeleton" style="height: 50px; margin-bottom: 10px;"></div>
                        <div class="skeleton" style="height: 50px;"></div>
                    </div>
                </div>
                <div class="card">
                    <div class="section-header">
                        <span>Create / Edit User</span>
                        <i class="fas fa-user-plus" style="color: var(--accent-orange);"></i>
                    </div>
                    <form id="userForm">
                        <input type="hidden" id="action_type" value="create">
                        <div class="input-group">
                            <label><i class="fas fa-user" style="margin-right: 5px;"></i> USERNAME</label>
                            <input type="text" id="new_username" required placeholder="Enter username">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-key" style="margin-right: 5px;"></i> PASSWORD</label>
                            <input type="text" id="new_password" required placeholder="Enter password">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-shield-alt" style="margin-right: 5px;"></i> PERMISSIONS</label>
                            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 5px;">
                                <label class="perm-checkbox">
                                    <input type="checkbox" id="perm_closing" checked>
                                    <span>Closing</span>
                                </label>
                                <label class="perm-checkbox">
                                    <input type="checkbox" id="perm_po">
                                    <span>PO Sheet</span>
                                </label>
                                <label class="perm-checkbox">
                                    <input type="checkbox" id="perm_acc">
                                    <span>Accessories</span>
                                </label>
                            </div>
                        </div>
                        <button type="button" onclick="handleUserSubmit()" id="saveUserBtn">
                            <i class="fas fa-save" style="margin-right: 10px;"></i> Save User
                        </button>
                        <button type="button" onclick="resetForm()" style="margin-top: 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                            <i class="fas fa-undo" style="margin-right: 10px;"></i> Reset Form
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // ===== WELCOME POPUP WITH TIME-BASED GREETING =====
        function showWelcomePopup() {
            const hour = new Date().getHours();
            let greeting, icon;
            
            if (hour >= 5 && hour < 12) {
                greeting = "Good Morning";
                icon = '<i class="fas fa-sun"></i>';
            } else if (hour >= 12 && hour < 17) {
                greeting = "Good Afternoon";
                icon = '<i class="fas fa-sun"></i>';
            } else if (hour >= 17 && hour < 21) {
                greeting = "Good Evening";
                icon = '<i class="fas fa-city"></i>';
            } else {
                greeting = "Good Night";
                icon = '<i class="fas fa-moon"></i>';
            }
            
            document.getElementById('greetingText').textContent = greeting;
            document.getElementById('welcomeIcon').innerHTML = icon;
            document.getElementById('welcomeModal').style.display = 'flex';
        }
        
        function closeWelcome() {
            const modal = document.getElementById('welcomeModal');
            modal.style.animation = 'modalFadeOut 0.3s ease-out forwards';
            setTimeout(() => {
                modal.style.display = 'none';
                sessionStorage.setItem('welcomeShown', 'true');
            }, 300);
        }
        
        if (! sessionStorage.getItem('welcomeShown')) {
            setTimeout(showWelcomePopup, 500);
        }
        
        // ===== SECTION NAVIGATION =====
        function showSection(id, element) {
            ['dashboard', 'analytics', 'help', 'settings'].forEach(sid => {
                document.getElementById('section-' + sid).style.display = 'none';
            });
            document.getElementById('section-' + id).style.display = 'block';
            
            if (element) {
                document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
                element.classList.add('active');
            }
            
            if (id === 'settings') loadUsers();
            if (window.innerWidth < 1024) document.querySelector('.sidebar').classList. remove('active');
        }
        
        // ===== FILE UPLOAD HANDLER =====
        const fileUpload = document.getElementById('file-upload');
        const uploadZone = document. getElementById('uploadZone');
        
        if (fileUpload) {
            fileUpload.addEventListener('change', function() {
                const count = this.files. length;
                document.getElementById('file-count').innerHTML = count > 0 
                    ? `<i class="fas fa-check-circle" style="margin-right: 5px;"></i>${count} file(s) selected`
                    : 'No files selected';
            });
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });
            uploadZone. addEventListener('dragleave', () => {
                uploadZone.classList. remove('dragover');
            });
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone. classList.remove('dragover');
                fileUpload.files = e.dataTransfer. files;
                fileUpload.dispatchEvent(new Event('change'));
            });
        }
        
        // ===== DEW STYLE DAILY CHART =====
        const ctx = document.getElementById('mainChart').getContext('2d');
        const gradientOrange = ctx.createLinearGradient(0, 0, 0, 300);
        gradientOrange.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
        gradientOrange.addColorStop(1, 'rgba(255, 122, 0, 0. 0)');
        const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300);
        gradientPurple.addColorStop(0, 'rgba(139, 92, 246, 0.5)');
        gradientPurple.addColorStop(1, 'rgba(139, 92, 246, 0.0)');
        const gradientGreen = ctx.createLinearGradient(0, 0, 0, 300);
        gradientGreen.addColorStop(0, 'rgba(16, 185, 129, 0. 5)');
        gradientGreen. addColorStop(1, 'rgba(16, 185, 129, 0.0)');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ stats.chart.labels | tojson }},
                datasets: [
                    {
                        label: 'Closing',
                        data: {{ stats.chart. closing | tojson }},
                        borderColor: '#FF7A00',
                        backgroundColor: gradientOrange,
                        tension: 0. 4,
                        fill: true,
                        pointBackgroundColor: '#FF7A00',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 3
                    },
                    {
                        label: 'Accessories',
                        data: {{ stats.chart.acc | tojson }},
                        borderColor: '#8B5CF6',
                        backgroundColor: gradientPurple,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#8B5CF6',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 3
                    },
                    {
                        label: 'PO Sheets',
                        data: {{ stats. chart.po | tojson }},
                        borderColor: '#10B981',
                        backgroundColor: gradientGreen,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#10B981',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        borderWidth: 3
                    }
                ]
            },
            options: {
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#8b8b9e',
                            font: { size: 11, weight: 500 },
                            usePointStyle: true,
                            padding: 15,
                            boxWidth: 8
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(22, 22, 31, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#8b8b9e',
                        borderColor: 'rgba(255, 122, 0, 0.3)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 10,
                        displayColors: true
                    }
                },
                scales: {
                    x: {
                        grid: { 
                            display: false 
                        },
                        ticks: { 
                            color: '#8b8b9e', 
                            font: { size: 10 },
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        grid: { 
                            color: 'rgba(255,255,255,0.03)',
                            drawBorder: false
                        },
                        ticks: { 
                            color: '#8b8b9e', 
                            font: { size: 10 },
                            stepSize: 1
                        },
                        beginAtZero: true
                    }
                },
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                animation: {
                    duration: 2000,
                    easing: 'easeOutQuart'
                }
            }
        });

        // ===== COUNT UP ANIMATION =====
        function animateCountUp() {
            document.querySelectorAll('.count-up'). forEach(counter => {
                const target = parseInt(counter.getAttribute('data-target'));
                const duration = 2000;
                const step = target / (duration / 16);
                let current = 0;
                
                const updateCounter = () => {
                    current += step;
                    if (current < target) {
                        counter.textContent = Math.floor(current);
                        requestAnimationFrame(updateCounter);
                    } else {
                        counter.textContent = target;
                    }
                };
                
                updateCounter();
            });
        }
        
        setTimeout(animateCountUp, 500);

        // ===== LOADING ANIMATION =====
        function showLoading() {
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim'). parentElement;
            const success = document.getElementById('success-anim');
            const fail = document.getElementById('fail-anim');
            const text = document.getElementById('loading-text');
            
            overlay. style.display = 'flex';
            spinner. style.display = 'block';
            success.style.display = 'none';
            fail.style.display = 'none';
            text.style.display = 'block';
            text.textContent = 'Processing Request...';
            
            return true;
        }

        function showSuccess() {
            const overlay = document.getElementById('loading-overlay');
            const spinner = document. getElementById('spinner-anim').parentElement;
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            spinner.style.display = 'none';
            success.style. display = 'block';
            text. style.display = 'none';
            
            setTimeout(() => { overlay.style.display = 'none'; }, 1500);
        }

        // ===== USER MANAGEMENT =====
        function loadUsers() {
            fetch('/admin/get-users')
                .then(res => res.json())
                .then(data => {
                    let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
                    
                    for (const [u, d] of Object.entries(data)) {
                        const roleClass = d.role === 'admin' ?  'background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);' : 'background: rgba(139, 92, 246, 0. 1); color: var(--accent-purple);';
                        
                        html += `<tr>
                            <td style="font-weight: 600;">${u}</td>
                            <td><span class="table-badge" style="${roleClass}">${d. role}</span></td>
                            <td style="text-align:right;">
                                ${d.role !== 'admin' ?  `
                                    <div class="action-cell">
                                        <button class="action-btn btn-edit" onclick="editUser('${u}', '${d.password}', '${d.permissions. join(',')}')">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        <button class="action-btn btn-del" onclick="deleteUser('${u}')">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </div>
                                ` : '<i class="fas fa-shield-alt" style="color: var(--accent-orange); opacity: 0.5;"></i>'}
                            </td>
                        </tr>`;
                    }
                    
                    document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
                });
        }
        
        function handleUserSubmit() {
            const u = document.getElementById('new_username').value;
            const p = document.getElementById('new_password').value;
            const a = document.getElementById('action_type').value;
            
            let perms = [];
            if (document.getElementById('perm_closing').checked) perms.push('closing');
            if (document.getElementById('perm_po'). checked) perms. push('po_sheet');
            if (document.getElementById('perm_acc'). checked) perms. push('accessories');
            
            showLoading();
            
            fetch('/admin/save-user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username: u, password: p, permissions: perms, action_type: a })
            })
            .then(r => r.json())
            .then(d => {
                if (d.status === 'success') {
                    showSuccess();
                    loadUsers();
                    resetForm();
                } else {
                    alert(d.message);
                    document.getElementById('loading-overlay').style. display = 'none';
                }
            });
        }
        
        function editUser(u, p, permsStr) {
            document.getElementById('new_username').value = u;
            document. getElementById('new_username').readOnly = true;
            document.getElementById('new_password').value = p;
            document.getElementById('action_type').value = 'update';
            document. getElementById('saveUserBtn').innerHTML = '<i class="fas fa-sync" style="margin-right: 10px;"></i> Update User';
            const pArr = permsStr.split(',');
            document. getElementById('perm_closing').checked = pArr.includes('closing');
            document.getElementById('perm_po').checked = pArr.includes('po_sheet');
            document.getElementById('perm_acc').checked = pArr.includes('accessories');
        }
        
        function resetForm() {
            document.getElementById('userForm').reset();
            document.getElementById('action_type').value = 'create';
            document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-save" style="margin-right: 10px;"></i> Save User';
            document.getElementById('new_username').readOnly = false;
            document.getElementById('perm_closing').checked = true;
        }
        
        function deleteUser(u) {
            if (confirm('Are you sure you want to delete "' + u + '"?')) {
                fetch('/admin/delete-user', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username: u })
                }). then(() => loadUsers());
            }
        }
        
        // ===== PARTICLES. JS INITIALIZATION =====
        if (typeof particlesJS !== 'undefined') {
            particlesJS('particles-js', {
                particles: {
                    number: { value: 50, density: { enable: true, value_area: 800 } },
                    color: { value: '#FF7A00' },
                    shape: { type: 'circle' },
                    opacity: { value: 0.3, random: true },
                    size: { value: 3, random: true },
                    line_linked: { enable: true, distance: 150, color: '#FF7A00', opacity: 0.1, width: 1 },
                    move: { enable: true, speed: 1, direction: 'none', random: true, out_mode: 'out' }
                },
                interactivity: {
                    events: { onhover: { enable: true, mode: 'grab' } },
                    modes: { grab: { distance: 140, line_linked: { opacity: 0.3 } } }
                }
            });
        }
        
        // Add CSS for fadeInUp animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            @keyframes modalFadeOut {
                to { opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""
# ==============================================================================
# USER DASHBOARD TEMPLATE - MODERN UI
# ==============================================================================

USER_DASHBOARD_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard - MNM Software</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="welcome-modal" id="welcomeModal">
        <div class="welcome-content">
            <div class="welcome-icon" id="welcomeIcon"><i class="fas fa-hand-sparkles"></i></div>
            <div class="welcome-greeting" id="greetingText">Good Morning</div>
            <div class="welcome-title">Welcome, <span>{{ session.user }}</span>!</div>
            <div class="welcome-message">
                Your workspace is ready.  
                Access your assigned modules below.
            </div>
            <button class="welcome-close" onclick="closeWelcome()">
                <i class="fas fa-rocket" style="margin-right: 8px;"></i> Get Started
            </button>
        </div>
    </div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Processing...</div>
    </div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-layer-group"></i> 
            MNM<span>Software</span>
        </div>
        <div class="nav-menu">
            <div class="nav-link active">
                <i class="fas fa-home"></i> Home
            </div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">
            <i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan
        </div>
    </div>
    
    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Welcome, {{ session.user }}!</div>
                <div class="page-subtitle">Your assigned production modules</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="stats-grid">
            {% if 'closing' in session. permissions %}
            <div class="card" style="animation: fadeInUp 0.5s ease-out 0.1s backwards;">
                <div class="section-header">
                    <span><i class="fas fa-file-export" style="margin-right: 10px; color: var(--accent-orange);"></i>Closing Report</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                    Generate production closing reports with real-time data. 
                </p>
                <form action="/generate-report" method="post" onsubmit="showLoading()">
                    <div class="input-group">
                        <label>BOOKING REF NO</label>
                        <input type="text" name="ref_no" required placeholder="Enter Booking Reference">
                    </div>
                    <button type="submit">
                        <i class="fas fa-magic" style="margin-right: 8px;"></i> Generate
                    </button>
                </form>
            </div>
            {% endif %}
            
            {% if 'po_sheet' in session. permissions %}
            <div class="card" style="animation: fadeInUp 0. 5s ease-out 0.2s backwards;">
                <div class="section-header">
                    <span><i class="fas fa-file-pdf" style="margin-right: 10px; color: var(--accent-green);"></i>PO Sheet</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                    Process PDF files and generate PO summary reports.
                </p>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="showLoading()">
                    <div class="input-group">
                        <label>PDF FILES</label>
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="padding: 12px;">
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-cogs" style="margin-right: 8px;"></i> Process Files
                    </button>
                </form>
            </div>
            {% endif %}
            
            {% if 'accessories' in session.permissions %}
            <div class="card" style="animation: fadeInUp 0.5s ease-out 0.3s backwards;">
                <div class="section-header">
                    <span><i class="fas fa-boxes" style="margin-right: 10px; color: var(--accent-purple);"></i>Accessories</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                    Manage challans, entries and delivery history for accessories.
                </p>
                <a href="/admin/accessories">
                    <button type="button" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-external-link-alt" style="margin-right: 8px;"></i> Open Dashboard
                    </button>
                </a>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        // Welcome Popup
        function showWelcomePopup() {
            const hour = new Date().getHours();
            let greeting, icon;
            
            if (hour >= 5 && hour < 12) {
                greeting = "Good Morning";
                icon = '<i class="fas fa-sun"></i>';
            } else if (hour >= 12 && hour < 17) {
                greeting = "Good Afternoon";
                icon = '<i class="fas fa-sun"></i>';
            } else if (hour >= 17 && hour < 21) {
                greeting = "Good Evening";
                icon = '<i class="fas fa-city"></i>';
            } else {
                greeting = "Good Night";
                icon = '<i class="fas fa-moon"></i>';
            }
            
            document. getElementById('greetingText').textContent = greeting;
            document.getElementById('welcomeIcon').innerHTML = icon;
            document.getElementById('welcomeModal').style. display = 'flex';
        }
        
        function closeWelcome() {
            const modal = document.getElementById('welcomeModal');
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.style.display = 'none';
                sessionStorage.setItem('welcomeShown', 'true');
            }, 300);
        }
        
        if (! sessionStorage.getItem('welcomeShown')) {
            setTimeout(showWelcomePopup, 500);
        }
        
        function showLoading() {
            document.getElementById('loading-overlay'). style.display = 'flex';
            return true;
        }
        
        // Add fadeInUp animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES TEMPLATES - FIXED WITH CACHING AND STATUS LOGIC
# ==============================================================================

ACCESSORIES_SEARCH_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Search - MNM Software</title>
    """ + COMMON_STYLES + """
    <style>
        body {
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        
        .search-container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 480px;
            padding: 20px;
        }
        
        .search-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 50px 45px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            animation: cardAppear 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        @keyframes cardAppear {
            from { opacity: 0; transform: translateY(20px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        . search-header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .search-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(145deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05));
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            color: var(--accent-purple);
            margin-bottom: 20px;
            animation: iconFloat 3s ease-in-out infinite;
        }
        
        @keyframes iconFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        
        . search-title {
            font-size: 28px;
            font-weight: 800;
            color: white;
            margin-bottom: 8px;
        }
        
        .search-subtitle {
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        .nav-links {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }
        
        .nav-links a {
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: var(--transition-smooth);
        }
        
        .nav-links a:hover {
            color: var(--accent-orange);
        }
        
        .nav-links a.logout {
            color: var(--accent-red);
        }
        
        .nav-links a.logout:hover {
            color: #ff6b6b;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="search-container">
        <div class="search-card">
            <div class="search-header">
                <div class="search-icon">
                    <i class="fas fa-boxes"></i>
                </div>
                <div class="search-title">Accessories Challan</div>
                <div class="search-subtitle">Enter booking reference to continue</div>
            </div>
            
            <form action="/admin/accessories/input" method="post">
                <div class="input-group">
                    <label><i class="fas fa-search" style="margin-right: 5px;"></i> BOOKING REFERENCE</label>
                    <input type="text" name="ref_no" required placeholder="e.g. IB-12345" autocomplete="off">
                </div>
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    Proceed to Entry <i class="fas fa-arrow-right" style="margin-left: 10px;"></i>
                </button>
            </form>
            
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="flash-message flash-error" style="margin-top: 20px;">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{ messages[0] }}</span>
                    </div>
                {% endif %}
            {% endwith %}
            
            <div class="nav-links">
                <a href="/"><i class="fas fa-arrow-left"></i> Back to Dashboard</a>
                <a href="/logout" class="logout">Sign Out <i class="fas fa-sign-out-alt"></i></a>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 25px; color: var(--text-secondary); font-size: 11px; opacity: 0.4;">
            © 2025 Mehedi Hasan
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES INPUT TEMPLATE - FIXED: STATUS LOGIC AND CACHING INDICATOR
# ==============================================================================

ACCESSORIES_INPUT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Entry - MNM Software</title>
    """ + COMMON_STYLES + """
    <style>
        . ref-badge {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 122, 0, 0.1);
            border: 1px solid rgba(255, 122, 0, 0.2);
            padding: 10px 20px;
            border-radius: 12px;
            margin-top: 10px;
        }
        
        .ref-badge . ref-no {
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        
        .ref-badge .ref-info {
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
        }
        
        . history-scroll {
            max-height: 500px;
            overflow-y: auto;
            padding-right: 5px;
        }
        
        . challan-row {
            display: grid;
            grid-template-columns: 60px 1fr 80px 60px 80px;
            gap: 10px;
            padding: 14px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 8px;
            align-items: center;
            transition: var(--transition-smooth);
            border: 1px solid transparent;
        }
        
        .challan-row:hover {
            background: rgba(255, 122, 0, 0.05);
            border-color: var(--border-glow);
        }
        
        /* FIXED: Current entry styling - বর্তমান এন্ট্রি হাইলাইট */
        .challan-row.current-entry {
            background: rgba(255, 122, 0, 0.1);
            border: 2px solid var(--accent-orange);
            box-shadow: 0 0 15px rgba(255, 122, 0, 0.2);
        }
        
        .line-badge {
            background: var(--gradient-orange);
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            text-align: center;
        }
        
        /* FIXED: Current entry line badge - আলাদা স্টাইল */
        .current-entry .line-badge {
            background: linear-gradient(135deg, #FF7A00 0%, #FF5500 100%);
            box-shadow: 0 4px 15px rgba(255, 122, 0, 0.4);
            animation: pulseBadge 2s ease-in-out infinite;
        }
        
        @keyframes pulseBadge {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .qty-value {
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-green);
        }
        
        /* FIXED: Status cell - পুরাতন এন্ট্রিতে টিক, বর্তমানে ফাঁকা */
        . status-cell {
            font-size: 20px;
            color: var(--accent-green);
            font-weight: 900;
        }
        
        . status-cell.empty {
            color: var(--accent-orange);
            opacity: 0.5;
        }
        
        . print-btn {
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%) !important;
        }
        
        . empty-state {
            text-align: center;
            padding: 50px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state i {
            font-size: 50px;
            opacity: 0.2;
            margin-bottom: 15px;
        }
        
        . grid-2-cols {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        .count-badge {
            background: var(--accent-purple);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            margin-left: 10px;
        }
        
        /* Fixed Select Styling */
        select {
            background-color: #1a1a25 !important;
            color: white ! important;
        }
        
        select option {
            background-color: #1a1a25 ! important;
            color: white !important;
            padding: 10px;
        }
        
        /* Cache indicator styling */
        .cache-info {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 11px;
            font-weight: 600;
            margin-left: auto;
        }
        
        .cache-info. from-cache {
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        
        .cache-info.from-api {
            background: rgba(59, 130, 246, 0. 1);
            color: var(--accent-blue);
            border: 1px solid rgba(59, 130, 246, 0.2);
        }
        
        .header-row {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner" id="spinner-anim"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Saved! </div>
        </div>
        <div class="loading-text" id="loading-text">Saving Entry...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-boxes"></i> 
            Accessories
        </div>
        <div class="nav-menu">
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Dashboard</a>
            <a href="/admin/accessories" class="nav-link active"><i class="fas fa-search"></i> Search</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>
    
    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Accessories Entry</div>
                <div class="header-row">
                    <div class="ref-badge">
                        <span class="ref-no">{{ ref }}</span>
                        <span class="ref-info">{{ buyer }} • {{ style }}</span>
                    </div>
                    {% if from_cache %}
                    <div class="cache-info from-cache">
                        <i class="fas fa-database"></i> Cached Data
                    </div>
                    {% else %}
                    <div class="cache-info from-api">
                        <i class="fas fa-cloud-download-alt"></i> Fresh API Data
                    </div>
                    {% endif %}
                </div>
            </div>
            <a href="/admin/accessories/print? ref={{ ref }}" target="_blank" onclick="openPrintPreview(event)">
                <button class="print-btn" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-print" style="margin-right: 10px;"></i> Print Report
                </button>
            </a>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-plus-circle" style="margin-right: 10px; color: var(--accent-orange);"></i>New Challan Entry</span>
                </div>
                <form action="/admin/accessories/save" method="post" onsubmit="return showLoading()">
                    <input type="hidden" name="ref" value="{{ ref }}">
                    
                    <div class="grid-2-cols">
                        <div class="input-group">
                            <label><i class="fas fa-tag" style="margin-right: 5px;"></i> TYPE</label>
                            <select name="item_type">
                                <option value="Top">Top</option>
                                <option value="Bottom">Bottom</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-palette" style="margin-right: 5px;"></i> COLOR</label>
                            <select name="color" required>
                                <option value="" disabled selected>Select Color</option>
                                {% for c in colors %}
                                <option value="{{ c }}">{{ c }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    
                    <div class="grid-2-cols">
                        <div class="input-group">
                            <label><i class="fas fa-industry" style="margin-right: 5px;"></i> LINE NO</label>
                            <input type="text" name="line_no" required placeholder="e.g. L-01">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> SIZE</label>
                            <input type="text" name="size" value="ALL" placeholder="Size">
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-sort-numeric-up" style="margin-right: 5px;"></i> QUANTITY</label>
                        <input type="number" name="qty" required placeholder="Enter Quantity" min="1">
                    </div>
                    
                    <button type="submit">
                        <i class="fas fa-save" style="margin-right: 10px;"></i> Save Entry
                    </button>
                </form>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Recent History</span>
                    <span class="count-badge">{{ challans|length }}</span>
                </div>
                <div class="history-scroll">
                    {% if challans %}
                        {% set total_count = challans|length %}
                        {% for item in challans|reverse %}
                        {% set is_current = loop.index == 1 %}
                        <div class="challan-row {% if is_current %}current-entry{% endif %}" style="animation: fadeInUp 0.3s ease-out {{ loop.index * 0.05 }}s backwards;">
                            <div class="line-badge">{{ item.line }}</div>
                            <div style="color: white; font-weight: 500; font-size: 13px;">{{ item. color }}</div>
                            <div class="qty-value">{{ item.qty }}</div>
                            <div class="status-cell {% if is_current %}empty{% endif %}">
                                {% if is_current %}
                                    ○
                                {% else %}
                                    ✔
                                {% endif %}
                            </div>
                            <div class="action-cell">
                                {% if session.role == 'admin' %}
                                <a href="/admin/accessories/edit?ref={{ ref }}&index={{ total_count - loop.index }}" class="action-btn btn-edit">
                                    <i class="fas fa-pen"></i>
                                </a>
                                <form action="/admin/accessories/delete" method="POST" style="display: inline;" onsubmit="return confirm('Delete this entry?');">
                                    <input type="hidden" name="ref" value="{{ ref }}">
                                    <input type="hidden" name="index" value="{{ total_count - loop.index }}">
                                    <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                </form>
                                {% else %}
                                <span style="font-size: 10px; color: var(--text-secondary); opacity: 0.5;">🔒</span>
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state">
                            <i class="fas fa-inbox"></i>
                            <div>No challans added yet</div>
                            <div style="font-size: 12px; margin-top: 5px;">Add your first entry using the form</div>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showLoading() {
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim'). parentElement;
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            overlay. style.display = 'flex';
            spinner.style.display = 'block';
            success.style.display = 'none';
            text.style. display = 'block';
            text.textContent = 'Saving Entry...';
            
            return true;
        }
        
        // FIXED: Print Preview Function - নতুন উইন্ডোতে প্রিন্ট প্রিভিউ খোলা
        function openPrintPreview(event) {
            event.preventDefault();
            const url = event.currentTarget.href;
            const printWindow = window.open(url, '_blank', 'width=1000,height=800,scrollbars=yes,resizable=yes');
            if (printWindow) {
                printWindow. focus();
            } else {
                // Popup blocked হলে সরাসরি নেভিগেট
                window.location.href = url;
            }
        }
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES EDIT TEMPLATE
# ==============================================================================

ACCESSORIES_EDIT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Entry - MNM Software</title>
    """ + COMMON_STYLES + """
    <style>
        body {
            justify-content: center;
            align-items: center;
        }
        
        .edit-container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 450px;
            padding: 20px;
        }
        
        .edit-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 45px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
            animation: cardAppear 0. 5s ease-out;
        }
        
        @keyframes cardAppear {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }
        
        . edit-header {
            text-align: center;
            margin-bottom: 35px;
        }
        
        . edit-icon {
            width: 70px;
            height: 70px;
            background: linear-gradient(145deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05));
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: var(--accent-purple);
            margin-bottom: 15px;
        }
        
        .edit-title {
            font-size: 24px;
            font-weight: 800;
            color: white;
        }
        
        .cancel-link {
            display: block;
            text-align: center;
            margin-top: 20px;
            color: var(--text-secondary);
            font-size: 13px;
            text-decoration: none;
            transition: var(--transition-smooth);
        }
        
        .cancel-link:hover {
            color: var(--accent-orange);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="edit-container">
        <div class="edit-card">
            <div class="edit-header">
                <div class="edit-icon">
                    <i class="fas fa-edit"></i>
                </div>
                <div class="edit-title">Edit Entry</div>
            </div>
            
            <form action="/admin/accessories/update" method="post">
                <input type="hidden" name="ref" value="{{ ref }}">
                <input type="hidden" name="index" value="{{ index }}">
                
                <div class="input-group">
                    <label><i class="fas fa-industry" style="margin-right: 5px;"></i> LINE NO</label>
                    <input type="text" name="line_no" value="{{ item.line }}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-palette" style="margin-right: 5px;"></i> COLOR</label>
                    <input type="text" name="color" value="{{ item.color }}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> SIZE</label>
                    <input type="text" name="size" value="{{ item. size }}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sort-numeric-up" style="margin-right: 5px;"></i> QUANTITY</label>
                    <input type="number" name="qty" value="{{ item.qty }}" required>
                </div>
                
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync-alt" style="margin-right: 10px;"></i> Update Entry
                </button>
            </form>
            
            <a href="/admin/accessories/input_direct? ref={{ ref }}" class="cancel-link">
                <i class="fas fa-times" style="margin-right: 5px;"></i> Cancel
            </a>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES PRINT REPORT TEMPLATE - FIXED: AUTO PRINT PREVIEW
# ==============================================================================

ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessories Delivery Report</title>
    <link href="https://fonts. googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0. 0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: #fff; padding: 20px; color: #000; }
        . container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; position: relative; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; position: relative; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; line-height: 1; }
        .company-address { font-size: 12px; font-weight: 600; color: #444; margin-top: 5px; margin-bottom: 10px; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 18px; border-radius: 4px; }
        .info-grid { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
        .info-left { flex: 2; border: 1px dashed #555; padding: 15px; margin-right: 15px; }
        .info-row { display: flex; margin-bottom: 5px; font-size: 14px; align-items: center; }
        .info-label { font-weight: 800; width: 80px; color: #444; }
        . info-val { font-weight: 700; font-size: 15px; color: #000; }
        . booking-border { border: 2px solid #000; padding: 2px 8px; display: inline-block; font-weight: 900; }
        .info-right { flex: 1; display: flex; flex-direction: column; justify-content: space-between; height: 100%; border-left: 1px solid #ddd; padding-left: 15px; }
        .right-item { font-size: 14px; margin-bottom: 8px; font-weight: 700; }
        .right-label { color: #555; }
        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .summary-header { font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px; text-transform: uppercase; }
        .summary-table { width: 100%; font-size: 13px; font-weight: 700; }
        .summary-table td { padding: 2px 5px; }
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white ! important; padding: 10px; border: 1px solid #000; font-size: 14px; text-transform: uppercase; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; vertical-align: middle; color: #000; font-weight: 600; }
        
        /* FIXED: Current entry styling - বর্তমান এন্ট্রি হাইলাইট */
        . main-table tr. current-row {
            background: #fff3cd ! important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        
        . main-table tr. current-row td {
            border: 2px solid #ff9800;
        }
        
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-size: 16px; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff; }
        . line-text-bold { font-size: 14px; font-weight: 800; opacity: 0.7; }
        . status-cell { font-size: 20px; color: green; font-weight: 900; }
        .status-cell.empty { color: #ff9800; }
        .qty-cell { font-size: 16px; font-weight: 800; }
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; margin: 0 2px; display: inline-block; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .no-print { margin-bottom: 20px; text-align: right; }
        . btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; margin-left: 10px; }
        .btn-print { background: #27ae60; }
        .btn:hover { opacity: 0.9; }
        . generator-sig { text-align: right; font-size: 10px; margin-top: 5px; color: #555; }
        
        @media print {
            .no-print { display: none ! important; }
            .action-col { display: none ! important; }
            .container { border: none; padding: 0; margin: 0; max-width: 100%; }
            body { padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .main-table th { background: #2c3e50 !important; color: white !important; }
            .main-table tr.current-row { background: #fff3cd !important; }
        }
    </style>
</head>
<body>
<div class="no-print">
    <a href="/admin/accessories/input_direct?ref={{ ref }}" class="btn">← Back</a>
    <button onclick="window.print()" class="btn btn-print">🖨️ Print</button>
</div>
<div class="container">
    <div class="header">
        <div class="company-name">COTTON CLOTHING BD LTD</div>
        <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur. </div>
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
            {% set total_items = challans|length %}
            {% for item in challans %}
                {% set ns.grand_total = ns.grand_total + item.qty|int %}
                {% set is_current = loop. index == total_items %}
                <tr class="{% if is_current %}current-row{% endif %}">
                    <td>{{ item.date }}</td>
                    <td>
                        {% if is_current %}
                            <div class="line-card">{{ item.line }}</div>
                        {% else %}
                            <span class="line-text-bold">{{ item.line }}</span>
                        {% endif %}
                    </td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td class="status-cell {% if is_current %}empty{% endif %}">
                        {% if is_current %}
                            ○
                        {% else %}
                            ✔
                        {% endif %}
                    </td>
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

<script>
    // FIXED: Auto print dialog - পেজ লোড হলে অটো প্রিন্ট ডায়ালগ দেখাবে
    window.onload = function() {
        // Small delay to ensure page is fully rendered
        setTimeout(function() {
            window.print();
        }, 500);
    };
</script>
</body>
</html>
"""
# ==============================================================================
# STORE DASHBOARD TEMPLATE - MAIN STORE MANAGEMENT
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MNM Software</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Success! </div>
        </div>
        <div class="loading-text">Processing... </div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link active">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            {% if session.role == 'admin' or session.role == 'store_admin' %}
            <a href="/admin/store/users" class="nav-link">
                <i class="fas fa-users-cog"></i> User Management
            </a>
            {% endif %}
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Store Dashboard</div>
                <div class="page-subtitle">Overview of store operations</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>{{ session.user }}</span>
            </div>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0. 15), rgba(59, 130, 246, 0.05));">
                    <i class="fas fa-box" style="color: var(--accent-blue);"></i>
                </div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ stats.products_count }}">0</h3>
                    <p>Total Products</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                    <i class="fas fa-users" style="color: var(--accent-purple);"></i>
                </div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ stats.customers_count }}">0</h3>
                    <p>Total Customers</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-file-invoice-dollar" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ stats. invoices_count }}">0</h3>
                    <p>Total Invoices</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{ "{:,.0f}".format(stats.monthly_sales) }}</h3>
                    <p>Monthly Sales</p>
                </div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span>Quick Actions</span>
                    <i class="fas fa-bolt" style="color: var(--accent-orange);"></i>
                </div>
                <div class="grid-2" style="gap: 15px;">
                    <a href="/admin/store/invoices/new" style="text-decoration: none;">
                        <button class="btn-primary" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                            <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
                        </button>
                    </a>
                    <a href="/admin/store/estimates/new" style="text-decoration: none;">
                        <button class="btn-primary" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                            <i class="fas fa-plus" style="margin-right: 8px;"></i> New Estimate
                        </button>
                    </a>
                    <a href="/admin/store/products/new" style="text-decoration: none;">
                        <button class="btn-primary btn-secondary">
                            <i class="fas fa-box" style="margin-right: 8px;"></i> Add Product
                        </button>
                    </a>
                    <a href="/admin/store/customers/new" style="text-decoration: none;">
                        <button class="btn-primary btn-secondary">
                            <i class="fas fa-user-plus" style="margin-right: 8px;"></i> Add Customer
                        </button>
                    </a>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Due Summary</span>
                    <i class="fas fa-exclamation-triangle" style="color: var(--accent-red);"></i>
                </div>
                <div style="text-align: center; padding: 20px;">
                    <div class="amount-display amount-due" style="font-size: 36px;">
                        ৳{{ "{:,.0f}". format(stats.total_due) }}
                    </div>
                    <p style="color: var(--text-secondary); margin-top: 10px;">Total Outstanding</p>
                </div>
                <a href="/admin/store/payments/new" style="text-decoration: none;">
                    <button class="btn-primary" style="margin-top: 15px;">
                        <i class="fas fa-money-bill-wave" style="margin-right: 8px;"></i> Receive Payment
                    </button>
                </a>
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <span>Recent Invoices</span>
                <a href="/admin/store/invoices" style="color: var(--accent-orange); text-decoration: none; font-size: 13px;">View All →</a>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Due</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in recent_invoices[:5] %}
                        <tr>
                            <td style="font-weight: 700;">{{ inv.invoice_no }}</td>
                            <td>{{ inv.customer_name }}</td>
                            <td>{{ inv.date }}</td>
                            <td style="font-weight: 600;">৳{{ "{:,.0f}".format(inv. total) }}</td>
                            <td style="color: {% if inv.due > 0 %}var(--accent-red){% else %}var(--accent-green){% endif %}; font-weight: 700;">
                                ৳{{ "{:,.0f}". format(inv.due) }}
                            </td>
                            <td>
                                {% if inv.due == 0 %}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0. 1); color: var(--accent-green);">Paid</span>
                                {% elif inv.due < inv.total %}
                                <span class="table-badge" style="background: rgba(245, 158, 11, 0.1); color: #FBBF24;">Partial</span>
                                {% else %}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0. 1); color: var(--accent-red);">Unpaid</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="empty-state">
                                <i class="fas fa-file-invoice"></i>
                                <p>No invoices yet</p>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Count up animation
        function animateCountUp() {
            document.querySelectorAll('.count-up'). forEach(counter => {
                const target = parseInt(counter.getAttribute('data-target')) || 0;
                const duration = 1500;
                const step = target / (duration / 16);
                let current = 0;
                
                const updateCounter = () => {
                    current += step;
                    if (current < target) {
                        counter.textContent = Math.floor(current);
                        requestAnimationFrame(updateCounter);
                    } else {
                        counter.textContent = target;
                    }
                };
                
                if (target > 0) updateCounter();
            });
        }
        
        setTimeout(animateCountUp, 300);
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE PRODUCTS TEMPLATE
# ==============================================================================

STORE_PRODUCTS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Products</div>
                <div class="page-subtitle">Manage your product inventory</div>
            </div>
            <a href="/admin/store/products/new">
                <button class="btn-primary" style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Product
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Products ({{ products|length }})</span>
                <div class="search-box" style="width: 300px; margin: 0;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchProduct" placeholder="Search products..." onkeyup="filterProducts()">
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table" id="productsTable">
                    <thead>
                        <tr>
                            <th>Code</th>
                            <th>Name</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th>Price</th>
                            <th>Stock</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in products %}
                        <tr>
                            <td style="font-weight: 700;">{{ p.code }}</td>
                            <td>{{ p.name }}</td>
                            <td><span class="table-badge">{{ p.category }}</span></td>
                            <td>{{ p.unit }}</td>
                            <td style="font-weight: 600;">৳{{ "{:,.0f}".format(p. price) }}</td>
                            <td>
                                {% if p.stock <= 10 %}
                                <span style="color: var(--accent-red); font-weight: 700;">{{ p.stock }}</span>
                                {% else %}
                                {{ p.stock }}
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/products/edit/{{ loop.index0 }}" class="action-btn btn-edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <form action="/admin/store/products/delete/{{ loop.index0 }}" method="POST" style="display: inline;" onsubmit="return confirm('Delete this product?');">
                                        <button type="submit" class="action-btn btn-del">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" class="empty-state">
                                <i class="fas fa-box-open"></i>
                                <p>No products added yet</p>
                                <a href="/admin/store/products/new">
                                    <button class="btn-primary btn-sm" style="margin-top: 15px;">Add First Product</button>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterProducts() {
            const input = document.getElementById('searchProduct'). value.toLowerCase();
            const rows = document.querySelectorAll('#productsTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE PRODUCT FORM TEMPLATE (ADD/EDIT)
# ==============================================================================

STORE_PRODUCT_FORM_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ 'Edit' if product else 'Add' }} Product - Store</title>
    """ + COMMON_STYLES + """
    <style>
        .form-container {
            max-width: 600px;
            margin: 0 auto;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList. toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ 'Edit' if product else 'Add New' }} Product</div>
                <div class="page-subtitle">{{ 'Update product details' if product else 'Add a new product to inventory' }}</div>
            </div>
        </div>

        <div class="form-container">
            <div class="card">
                <form action="{{ '/admin/store/products/update/' ~ index if product else '/admin/store/products/save' }}" method="POST">
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Product Code</label>
                            <input type="text" name="code" value="{{ product.code if product else '' }}" required placeholder="e.g.  PRD001">
                        </div>
                        <div class="input-group">
                            <label>Product Name</label>
                            <input type="text" name="name" value="{{ product.name if product else '' }}" required placeholder="Product name">
                        </div>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Category</label>
                            <select name="category" required>
                                <option value="">Select Category</option>
                                <option value="Accessories" {{ 'selected' if product and product.category == 'Accessories' }}>Accessories</option>
                                <option value="Fabric" {{ 'selected' if product and product.category == 'Fabric' }}>Fabric</option>
                                <option value="Thread" {{ 'selected' if product and product.category == 'Thread' }}>Thread</option>
                                <option value="Button" {{ 'selected' if product and product.category == 'Button' }}>Button</option>
                                <option value="Zipper" {{ 'selected' if product and product.category == 'Zipper' }}>Zipper</option>
                                <option value="Label" {{ 'selected' if product and product.category == 'Label' }}>Label</option>
                                <option value="Packaging" {{ 'selected' if product and product.category == 'Packaging' }}>Packaging</option>
                                <option value="Other" {{ 'selected' if product and product.category == 'Other' }}>Other</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Unit</label>
                            <select name="unit" required>
                                <option value="">Select Unit</option>
                                <option value="Pcs" {{ 'selected' if product and product.unit == 'Pcs' }}>Pcs</option>
                                <option value="Kg" {{ 'selected' if product and product.unit == 'Kg' }}>Kg</option>
                                <option value="Meter" {{ 'selected' if product and product.unit == 'Meter' }}>Meter</option>
                                <option value="Yard" {{ 'selected' if product and product.unit == 'Yard' }}>Yard</option>
                                <option value="Dozen" {{ 'selected' if product and product. unit == 'Dozen' }}>Dozen</option>
                                <option value="Gross" {{ 'selected' if product and product.unit == 'Gross' }}>Gross</option>
                                <option value="Set" {{ 'selected' if product and product.unit == 'Set' }}>Set</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Price (৳)</label>
                            <input type="number" name="price" value="{{ product.price if product else '' }}" required placeholder="0.00" step="0.01" min="0">
                        </div>
                        <div class="input-group">
                            <label>Stock Quantity</label>
                            <input type="number" name="stock" value="{{ product.stock if product else '0' }}" placeholder="0" min="0">
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label>Description (Optional)</label>
                        <textarea name="description" placeholder="Product description..." rows="3">{{ product.description if product else '' }}</textarea>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 10px;">
                        <button type="submit" class="btn-success">
                            <i class="fas fa-save" style="margin-right: 8px;"></i> 
                            {{ 'Update' if product else 'Save' }} Product
                        </button>
                        <a href="/admin/store/products" style="flex: 1; text-decoration: none;">
                            <button type="button" class="btn-secondary" style="width: 100%;">
                                Cancel
                            </button>
                        </a>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMERS TEMPLATE
# ==============================================================================

STORE_CUSTOMERS_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar'). classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Customers</div>
                <div class="page-subtitle">Manage your customer database</div>
            </div>
            <a href="/admin/store/customers/new">
                <button class="btn-primary" style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-user-plus" style="margin-right: 8px;"></i> Add Customer
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Customers ({{ customers|length }})</span>
                <div class="search-box" style="width: 300px; margin: 0;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchCustomer" placeholder="Search customers..." onkeyup="filterCustomers()">
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table" id="customersTable">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Email</th>
                            <th>Address</th>
                            <th>Total Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for c in customers %}
                        <tr>
                            <td style="font-weight: 600;">{{ c.name }}</td>
                            <td>{{ c.phone }}</td>
                            <td>{{ c. email if c.email else '-' }}</td>
                            <td>{{ c.address[:30] ~ '...' if c.address and c.address|length > 30 else c.address if c.address else '-' }}</td>
                            <td style="color: {% if c. due > 0 %}var(--accent-red){% else %}var(--accent-green){% endif %}; font-weight: 700;">
                                ৳{{ "{:,.0f}". format(c.due if c.due else 0) }}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/customers/view/{{ loop.index0 }}" class="action-btn btn-view">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/admin/store/customers/edit/{{ loop.index0 }}" class="action-btn btn-edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <form action="/admin/store/customers/delete/{{ loop.index0 }}" method="POST" style="display: inline;" onsubmit="return confirm('Delete this customer?');">
                                        <button type="submit" class="action-btn btn-del">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="empty-state">
                                <i class="fas fa-users"></i>
                                <p>No customers added yet</p>
                                <a href="/admin/store/customers/new">
                                    <button class="btn-primary btn-sm" style="margin-top: 15px;">Add First Customer</button>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterCustomers() {
            const input = document.getElementById('searchCustomer').value. toLowerCase();
            const rows = document.querySelectorAll('#customersTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMER FORM TEMPLATE (ADD/EDIT)
# ==============================================================================

STORE_CUSTOMER_FORM_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ 'Edit' if customer else 'Add' }} Customer - Store</title>
    """ + COMMON_STYLES + """
    <style>
        .form-container {
            max-width: 600px;
            margin: 0 auto;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('. sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ 'Edit' if customer else 'Add New' }} Customer</div>
                <div class="page-subtitle">{{ 'Update customer details' if customer else 'Add a new customer to database' }}</div>
            </div>
        </div>

        <div class="form-container">
            <div class="card">
                <form action="{{ '/admin/store/customers/update/' ~ index if customer else '/admin/store/customers/save' }}" method="POST">
                    <div class="input-group">
                        <label><i class="fas fa-user" style="margin-right: 5px;"></i> Customer Name</label>
                        <input type="text" name="name" value="{{ customer.name if customer else '' }}" required placeholder="Full name">
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label><i class="fas fa-phone" style="margin-right: 5px;"></i> Phone Number</label>
                            <input type="tel" name="phone" value="{{ customer. phone if customer else '' }}" required placeholder="01XXXXXXXXX">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-envelope" style="margin-right: 5px;"></i> Email (Optional)</label>
                            <input type="email" name="email" value="{{ customer.email if customer else '' }}" placeholder="email@example.com">
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> Address</label>
                        <textarea name="address" placeholder="Full address..." rows="3">{{ customer.address if customer else '' }}</textarea>
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-sticky-note" style="margin-right: 5px;"></i> Notes (Optional)</label>
                        <textarea name="notes" placeholder="Additional notes..." rows="2">{{ customer.notes if customer else '' }}</textarea>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 10px;">
                        <button type="submit" class="btn-success">
                            <i class="fas fa-save" style="margin-right: 8px;"></i> 
                            {{ 'Update' if customer else 'Save' }} Customer
                        </button>
                        <a href="/admin/store/customers" style="flex: 1; text-decoration: none;">
                            <button type="button" class="btn-secondary" style="width: 100%;">
                                Cancel
                            </button>
                        </a>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMER VIEW TEMPLATE
# ==============================================================================

STORE_CUSTOMER_VIEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customer Details - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ customer.name }}</div>
                <div class="page-subtitle">Customer Details & Transaction History</div>
            </div>
            <a href="/admin/store/customers/edit/{{ index }}">
                <button class="btn-primary" style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-edit" style="margin-right: 8px;"></i> Edit
                </button>
            </a>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span>Contact Information</span>
                    <i class="fas fa-address-card" style="color: var(--accent-purple);"></i>
                </div>
                <div style="padding: 10px 0;">
                    <div style="margin-bottom: 15px;">
                        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 5px;">PHONE</div>
                        <div style="font-size: 16px; font-weight: 600;">{{ customer.phone }}</div>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 5px;">EMAIL</div>
                        <div style="font-size: 16px;">{{ customer.email if customer.email else '-' }}</div>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 5px;">ADDRESS</div>
                        <div style="font-size: 14px; line-height: 1.5;">{{ customer.address if customer.address else '-' }}</div>
                    </div>
                    {% if customer.notes %}
                    <div>
                        <div style="color: var(--text-secondary); font-size: 12px; margin-bottom: 5px;">NOTES</div>
                        <div style="font-size: 14px; color: var(--text-secondary);">{{ customer.notes }}</div>
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Account Summary</span>
                    <i class="fas fa-chart-pie" style="color: var(--accent-orange);"></i>
                </div>
                <div style="text-align: center; padding: 20px;">
                    <div class="amount-display amount-due" style="font-size: 40px;">
                        ৳{{ "{:,. 0f}".format(customer.due if customer.due else 0) }}
                    </div>
                    <p style="color: var(--text-secondary); margin-top: 10px;">Total Due Amount</p>
                </div>
                <a href="/admin/store/payments/new? customer={{ index }}">
                    <button class="btn-success" style="margin-top: 15px;">
                        <i class="fas fa-money-bill-wave" style="margin-right: 8px;"></i> Receive Payment
                    </button>
                </a>
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <span>Invoice History</span>
            </div>
            <table class="dark-table">
                <thead>
                    <tr>
                        <th>Invoice #</th>
                        <th>Date</th>
                        <th>Total</th>
                        <th>Paid</th>
                        <th>Due</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for inv in customer_invoices %}
                    <tr>
                        <td style="font-weight: 700;">{{ inv.invoice_no }}</td>
                        <td>{{ inv.date }}</td>
                        <td>৳{{ "{:,. 0f}".format(inv.total) }}</td>
                        <td>৳{{ "{:,. 0f}".format(inv.paid) }}</td>
                        <td style="color: {% if inv.due > 0 %}var(--accent-red){% else %}var(--accent-green){% endif %}; font-weight: 700;">
                            ৳{{ "{:,.0f}".format(inv. due) }}
                        </td>
                        <td>
                            {% if inv.due == 0 %}
                            <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">Paid</span>
                            {% else %}
                            <span class="table-badge" style="background: rgba(239, 68, 68, 0. 1); color: var(--accent-red);">Due</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 30px;">
                            No invoices found for this customer
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICES LIST TEMPLATE
# ==============================================================================

STORE_INVOICES_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar'). classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoices</div>
                <div class="page-subtitle">Manage sales invoices</div>
            </div>
            <a href="/admin/store/invoices/new">
                <button class="btn-primary" style="width: auto; padding: 12px 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Invoices ({{ invoices|length }})</span>
                <div class="search-box" style="width: 300px; margin: 0;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInvoice" placeholder="Search invoices..." onkeyup="filterInvoices()">
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table" id="invoicesTable">
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in invoices|reverse %}
                        <tr>
                            <td style="font-weight: 700;">{{ inv.invoice_no }}</td>
                            <td>{{ inv.customer_name }}</td>
                            <td>{{ inv.date }}</td>
                            <td style="font-weight: 600;">৳{{ "{:,. 0f}".format(inv.total) }}</td>
                            <td style="color: var(--accent-green);">৳{{ "{:,. 0f}".format(inv.paid) }}</td>
                            <td style="color: {% if inv.due > 0 %}var(--accent-red){% else %}var(--accent-green){% endif %}; font-weight: 700;">
                                ৳{{ "{:,.0f}".format(inv. due) }}
                            </td>
                            <td>
                                {% if inv.due == 0 %}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">Paid</span>
                                {% elif inv.due < inv.total %}
                                <span class="table-badge" style="background: rgba(245, 158, 11, 0.1); color: #FBBF24;">Partial</span>
                                {% else %}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0. 1); color: var(--accent-red);">Unpaid</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/invoices/view/{{ loop.revindex0 }}" class="action-btn btn-view" title="View">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/admin/store/invoices/print/{{ loop.revindex0 }}" target="_blank" class="action-btn btn-print-sm" title="Print" onclick="openPrintWindow(event, this. href)">
                                        <i class="fas fa-print"></i>
                                    </a>
                                    <a href="/admin/store/invoices/edit/{{ loop. revindex0 }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <form action="/admin/store/invoices/delete/{{ loop.revindex0 }}" method="POST" style="display: inline;" onsubmit="return confirm('Delete this invoice?');">
                                        <button type="submit" class="action-btn btn-del" title="Delete">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="8" class="empty-state">
                                <i class="fas fa-file-invoice"></i>
                                <p>No invoices created yet</p>
                                <a href="/admin/store/invoices/new">
                                    <button class="btn-primary btn-sm" style="margin-top: 15px;">Create First Invoice</button>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterInvoices() {
            const input = document.getElementById('searchInvoice'). value.toLowerCase();
            const rows = document.querySelectorAll('#invoicesTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }
        
        // FIXED: Print window function
        function openPrintWindow(event, url) {
            event.preventDefault();
            const printWin = window.open(url, '_blank', 'width=900,height=700,scrollbars=yes,resizable=yes');
            if (printWin) {
                printWin.focus();
            } else {
                window.location.href = url;
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE FORM TEMPLATE (NEW/EDIT)
# ==============================================================================

STORE_INVOICE_FORM_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ 'Edit' if invoice else 'New' }} Invoice - Store</title>
    """ + COMMON_STYLES + """
    <style>
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .items-table th {
            background: rgba(255, 255, 255, 0. 05);
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
        }
        .items-table td {
            padding: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        . items-table input, .items-table select {
            width: 100%;
            padding: 10px;
            font-size: 14px;
        }
        .item-row {
            transition: all 0. 3s;
        }
        .item-row:hover {
            background: rgba(255, 122, 0, 0.03);
        }
        .remove-item-btn {
            background: var(--accent-red);
            color: white;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .remove-item-btn:hover {
            transform: scale(1. 1);
        }
        .totals-section {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }
        . total-row:last-child {
            border-bottom: none;
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        .total-label {
            color: var(--text-secondary);
        }
        .total-value {
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList. toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ 'Edit' if invoice else 'Create New' }} Invoice</div>
                <div class="page-subtitle">{{ invoice.invoice_no if invoice else 'Fill in the details below' }}</div>
            </div>
        </div>

        <form action="{{ '/admin/store/invoices/update/' ~ index if invoice else '/admin/store/invoices/save' }}" method="POST" id="invoiceForm">
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span>Invoice Details</span>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Invoice Number</label>
                            <input type="text" name="invoice_no" value="{{ invoice.invoice_no if invoice else next_invoice_no }}" readonly style="background: rgba(255,255,255,0.02);">
                        </div>
                        <div class="input-group">
                            <label>Date</label>
                            <input type="date" name="date" value="{{ invoice. date if invoice else today }}" required>
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label>Customer</label>
                        <select name="customer_index" id="customerSelect" required onchange="updateCustomerInfo()">
                            <option value="">Select Customer</option>
                            {% for c in customers %}
                            <option value="{{ loop.index0 }}" data-name="{{ c.name }}" data-phone="{{ c.phone }}" data-address="{{ c.address }}"
                                {{ 'selected' if invoice and invoice.customer_index == loop.index0 }}>
                                {{ c. name }} - {{ c.phone }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <input type="hidden" name="customer_name" id="customerNameInput" value="{{ invoice.customer_name if invoice else '' }}">
                    
                    <div class="input-group">
                        <label>Notes (Optional)</label>
                        <textarea name="notes" rows="2" placeholder="Additional notes... ">{{ invoice.notes if invoice else '' }}</textarea>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span>Payment Info</span>
                    </div>
                    
                    <div class="totals-section">
                        <div class="total-row">
                            <span class="total-label">Subtotal</span>
                            <span class="total-value" id="subtotalDisplay">৳0</span>
                        </div>
                        <div class="total-row">
                            <span class="total-label">Discount</span>
                            <input type="number" name="discount" id="discountInput" value="{{ invoice.discount if invoice else 0 }}" min="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                        </div>
                        <div class="total-row">
                            <span class="total-label">Grand Total</span>
                            <span class="total-value" id="grandTotalDisplay">৳0</span>
                        </div>
                        <div class="total-row">
                            <span class="total-label">Paid Amount</span>
                            <input type="number" name="paid" id="paidInput" value="{{ invoice.paid if invoice else 0 }}" min="0" step="0. 01" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                        </div>
                        <div class="total-row" style="color: var(--accent-red);">
                            <span class="total-label">Due Amount</span>
                            <span class="total-value" id="dueDisplay">৳0</span>
                        </div>
                    </div>
                    
                    <input type="hidden" name="subtotal" id="subtotalInput" value="0">
                    <input type="hidden" name="total" id="totalInput" value="0">
                    <input type="hidden" name="due" id="dueInput" value="0">
                </div>
            </div>

            <div class="card" style="margin-top: 20px;">
                <div class="section-header">
                    <span>Invoice Items</span>
                    <button type="button" onclick="addItemRow()" class="btn-primary btn-sm" style="width: auto;">
                        <i class="fas fa-plus" style="margin-right: 5px;"></i> Add Item
                    </button>
                </div>
                
                <table class="items-table">
                    <thead>
                        <tr>
                            <th style="width: 40%;">Product</th>
                            <th style="width: 15%;">Qty</th>
                            <th style="width: 15%;">Price</th>
                            <th style="width: 20%;">Amount</th>
                            <th style="width: 10%;"></th>
                        </tr>
                    </thead>
                    <tbody id="itemsTableBody">
                        {% if invoice and invoice.items %}
                            {% for item in invoice.items %}
                            <tr class="item-row">
                                <td>
                                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                                        <option value="">Select Product</option>
                                        {% for p in products %}
                                        <option value="{{ loop.index0 }}" data-price="{{ p.price }}" data-name="{{ p.name }}"
                                            {{ 'selected' if item.product_index == loop.index0 }}>
                                            {{ p.code }} - {{ p.name }}
                                        </option>
                                        {% endfor %}
                                    </select>
                                </td>
                                <td>
                                    <input type="number" name="items[][qty]" class="item-qty" value="{{ item.qty }}" min="1" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][price]" class="item-price" value="{{ item.price }}" min="0" step="0.01" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][amount]" class="item-amount" value="{{ item.amount }}" readonly style="background: rgba(255,255,255,0.02);">
                                </td>
                                <td>
                                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr class="item-row">
                                <td>
                                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                                        <option value="">Select Product</option>
                                        {% for p in products %}
                                        <option value="{{ loop.index0 }}" data-price="{{ p.price }}" data-name="{{ p.name }}">
                                            {{ p.code }} - {{ p.name }}
                                        </option>
                                        {% endfor %}
                                    </select>
                                </td>
                                <td>
                                    <input type="number" name="items[][qty]" class="item-qty" value="1" min="1" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][price]" class="item-price" value="0" min="0" step="0.01" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][amount]" class="item-amount" value="0" readonly style="background: rgba(255,255,255,0.02);">
                                </td>
                                <td>
                                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>

            <div style="display: flex; gap: 15px; margin-top: 20px;">
                <button type="submit" class="btn-success" style="flex: 2;">
                    <i class="fas fa-save" style="margin-right: 8px;"></i> 
                    {{ 'Update' if invoice else 'Save' }} Invoice
                </button>
                <a href="/admin/store/invoices" style="flex: 1; text-decoration: none;">
                    <button type="button" class="btn-secondary" style="width: 100%;">
                        Cancel
                    </button>
                </a>
            </div>
        </form>
    </div>

    <script>
        const productsData = {{ products | tojson }};
        
        function updateCustomerInfo() {
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            document.getElementById('customerNameInput').value = option.dataset.name || '';
        }
        
        function addItemRow() {
            const tbody = document.getElementById('itemsTableBody');
            const productOptions = productsData.map((p, i) => 
                `<option value="${i}" data-price="${p. price}" data-name="${p.name}">${p.code} - ${p.name}</option>`
            ). join('');
            
            const newRow = document.createElement('tr');
            newRow. className = 'item-row';
            newRow.innerHTML = `
                <td>
                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                        <option value="">Select Product</option>
                        ${productOptions}
                    </select>
                </td>
                <td>
                    <input type="number" name="items[][qty]" class="item-qty" value="1" min="1" onchange="calculateRowAmount(this)">
                </td>
                <td>
                    <input type="number" name="items[][price]" class="item-price" value="0" min="0" step="0. 01" onchange="calculateRowAmount(this)">
                </td>
                <td>
                    <input type="number" name="items[][amount]" class="item-amount" value="0" readonly style="background: rgba(255,255,255,0.02);">
                </td>
                <td>
                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            tbody. appendChild(newRow);
        }
        
        function removeItemRow(btn) {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length > 1) {
                btn.closest('tr'). remove();
                calculateTotals();
            }
        }
        
        function updateItemPrice(select) {
            const row = select.closest('tr');
            const option = select.options[select.selectedIndex];
            const price = parseFloat(option.dataset.price) || 0;
            row.querySelector('.item-price').value = price;
            calculateRowAmount(select);
        }
        
        function calculateRowAmount(element) {
            const row = element.closest('tr');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const price = parseFloat(row.querySelector('.item-price').value) || 0;
            const amount = qty * price;
            row.querySelector('.item-amount').value = amount. toFixed(2);
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('.item-amount').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            const paid = parseFloat(document.getElementById('paidInput'). value) || 0;
            const due = grandTotal - paid;
            
            document. getElementById('subtotalDisplay').textContent = '৳' + subtotal.toLocaleString();
            document.getElementById('grandTotalDisplay').textContent = '৳' + grandTotal. toLocaleString();
            document.getElementById('dueDisplay'). textContent = '৳' + due. toLocaleString();
            
            document.getElementById('subtotalInput').value = subtotal;
            document.getElementById('totalInput').value = grandTotal;
            document.getElementById('dueInput').value = due;
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            updateCustomerInfo();
            calculateTotals();
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE VIEW TEMPLATE
# ==============================================================================

STORE_INVOICE_VIEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoice {{ invoice.invoice_no }} - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList. toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ invoice.invoice_no }}</div>
                <div class="page-subtitle">Invoice Details</div>
            </div>
            <div style="display: flex; gap: 10px;">
                <a href="/admin/store/invoices/print/{{ index }}" target="_blank" onclick="openPrintWindow(event, this. href)">
                    <button class="btn-success" style="width: auto; padding: 12px 25px;">
                        <i class="fas fa-print" style="margin-right: 8px;"></i> Print
                    </button>
                </a>
                <a href="/admin/store/invoices/edit/{{ index }}">
                    <button class="btn-primary" style="width: auto; padding: 12px 25px;">
                        <i class="fas fa-edit" style="margin-right: 8px;"></i> Edit
                    </button>
                </a>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span>Customer Details</span>
                </div>
                <div style="padding: 10px 0;">
                    <div style="margin-bottom: 15px;">
                        <div style="color: var(--text-secondary); font-size: 12px;">CUSTOMER</div>
                        <div style="font-size: 18px; font-weight: 700;">{{ invoice.customer_name }}</div>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <div style="color: var(--text-secondary); font-size: 12px;">DATE</div>
                        <div style="font-size: 16px;">{{ invoice. date }}</div>
                    </div>
                    {% if invoice.notes %}
                    <div>
                        <div style="color: var(--text-secondary); font-size: 12px;">NOTES</div>
                        <div style="font-size: 14px;">{{ invoice. notes }}</div>
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Payment Summary</span>
                </div>
                <div style="padding: 10px 0;">
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-color);">
                        <span style="color: var(--text-secondary);">Subtotal</span>
                        <span style="font-weight: 600;">৳{{ "{:,.0f}".format(invoice.subtotal) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-color);">
                        <span style="color: var(--text-secondary);">Discount</span>
                        <span style="font-weight: 600;">৳{{ "{:,.0f}".format(invoice. discount) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-color);">
                        <span style="color: var(--text-secondary);">Total</span>
                        <span style="font-weight: 700; font-size: 18px;">৳{{ "{:,.0f}".format(invoice.total) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-color);">
                        <span style="color: var(--text-secondary);">Paid</span>
                        <span style="font-weight: 600; color: var(--accent-green);">৳{{ "{:,.0f}".format(invoice.paid) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 15px 0;">
                        <span style="font-weight: 700; font-size: 16px;">Due</span>
                        <span style="font-weight: 800; font-size: 24px; color: {% if invoice.due > 0 %}var(--accent-red){% else %}var(--accent-green){% endif %};">
                            ৳{{ "{:,.0f}".format(invoice.due) }}
                        </span>
                    </div>
                </div>
                {% if invoice.due > 0 %}
                <a href="/admin/store/payments/new? invoice={{ index }}">
                    <button class="btn-primary" style="margin-top: 10px;">
                        <i class="fas fa-money-bill-wave" style="margin-right: 8px;"></i> Receive Payment
                    </button>
                </a>
                {% endif %}
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <div class="section-header">
                <span>Invoice Items</span>
            </div>
            <table class="dark-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Product</th>
                        <th>Qty</th>
                        <th>Price</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in invoice.items %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td style="font-weight: 600;">{{ item.product_name }}</td>
                        <td>{{ item.qty }}</td>
                        <td>৳{{ "{:,. 0f}".format(item.price) }}</td>
                        <td style="font-weight: 700;">৳{{ "{:,. 0f}".format(item.amount) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function openPrintWindow(event, url) {
            event.preventDefault();
            const printWin = window.open(url, '_blank', 'width=900,height=700,scrollbars=yes,resizable=yes');
            if (printWin) {
                printWin.focus();
            } else {
                window.location.href = url;
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE PRINT TEMPLATE - FIXED: PROPER PRINT STYLING
# ==============================================================================

STORE_INVOICE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Invoice {{ invoice.invoice_no }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Poppins', sans-serif; 
            background: #fff; 
            padding: 20px; 
            color: #000; 
            font-size: 14px;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            border: 2px solid #000; 
            padding: 30px; 
        }
        .header { 
            text-align: center; 
            border-bottom: 2px solid #000; 
            padding-bottom: 15px; 
            margin-bottom: 25px; 
        }
        .company-name { 
            font-size: 28px; 
            font-weight: 800; 
            text-transform: uppercase; 
            color: #2c3e50; 
        }
        .company-address { 
            font-size: 12px; 
            color: #555; 
            margin-top: 5px; 
        }
        .invoice-title { 
            background: #2c3e50; 
            color: white; 
            padding: 8px 30px; 
            display: inline-block; 
            font-weight: 700; 
            font-size: 18px; 
            margin-top: 15px; 
            border-radius: 4px;
        }
        .info-section {
            display: flex;
            justify-content: space-between;
            margin-bottom: 25px;
        }
        .info-box {
            flex: 1;
        }
        .info-box h4 {
            font-size: 12px;
            color: #777;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .info-box p {
            font-size: 14px;
            margin-bottom: 5px;
        }
        .info-box . highlight {
            font-size: 16px;
            font-weight: 700;
        }
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .items-table th {
            background: #2c3e50 !important;
            color: white ! important;
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .items-table td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        .items-table tr:nth-child(even) {
            background: #f9f9f9;
        }
        .items-table . amount {
            text-align: right;
            font-weight: 600;
        }
        .totals-section {
            margin-top: 20px;
            margin-left: auto;
            width: 300px;
        }
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .total-row. grand {
            border-top: 2px solid #000;
            border-bottom: none;
            font-size: 18px;
            font-weight: 800;
            padding-top: 15px;
        }
        .total-row.due {
            color: {% if invoice.due > 0 %}#e74c3c{% else %}#27ae60{% endif %};
            font-weight: 700;
        }
        .footer {
            margin-top: 50px;
            display: flex;
            justify-content: space-between;
            text-align: center;
        }
        .signature-box {
            width: 200px;
            border-top: 2px solid #000;
            padding-top: 10px;
            font-weight: 600;
        }
        . no-print {
            margin-bottom: 20px;
            text-align: right;
        }
        .btn {
            padding: 10px 25px;
            background: #2c3e50;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 5px;
            font-size: 14px;
            margin-left: 10px;
            text-decoration: none;
            display: inline-block;
        }
        .btn-print {
            background: #27ae60;
        }
        .notes-section {
            margin-top: 20px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 5px;
        }
        .notes-section h4 {
            font-size: 12px;
            color: #777;
            margin-bottom: 5px;
        }
        
        @media print {
            . no-print { display: none ! important; }
            body { padding: 0; }
            .container { border: none; padding: 0; max-width: 100%; }
            .items-table th { 
                background: #2c3e50 !important; 
                color: white ! important; 
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
</head>
<body>
    <div class="no-print">
        <a href="/admin/store/invoices" class="btn">← Back to Invoices</a>
        <button onclick="window.print()" class="btn btn-print">🖨️ Print Invoice</button>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="company-name">COTTON CLOTHING BD LTD</div>
            <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur</div>
            <div class="invoice-title">INVOICE</div>
        </div>
        
        <div class="info-section">
            <div class="info-box">
                <h4>Bill To</h4>
                <p class="highlight">{{ invoice.customer_name }}</p>
            </div>
            <div class="info-box" style="text-align: right;">
                <h4>Invoice Details</h4>
                <p><strong>Invoice #:</strong> {{ invoice. invoice_no }}</p>
                <p><strong>Date:</strong> {{ invoice. date }}</p>
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 10%;">#</th>
                    <th style="width: 45%;">Description</th>
                    <th style="width: 15%;">Qty</th>
                    <th style="width: 15%;">Rate</th>
                    <th style="width: 15%;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.product_name }}</td>
                    <td>{{ item.qty }}</td>
                    <td>৳{{ "{:,. 0f}".format(item.price) }}</td>
                    <td class="amount">৳{{ "{:,.0f}".format(item.amount) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-section">
            <div class="total-row">
                <span>Subtotal</span>
                <span>৳{{ "{:,.0f}".format(invoice.subtotal) }}</span>
            </div>
            {% if invoice.discount > 0 %}
            <div class="total-row">
                <span>Discount</span>
                <span>-৳{{ "{:,.0f}". format(invoice.discount) }}</span>
            </div>
            {% endif %}
            <div class="total-row grand">
                <span>Total</span>
                <span>৳{{ "{:,.0f}". format(invoice.total) }}</span>
            </div>
            <div class="total-row">
                <span>Paid</span>
                <span>৳{{ "{:,.0f}". format(invoice.paid) }}</span>
            </div>
            <div class="total-row due">
                <span>Due</span>
                <span>৳{{ "{:,. 0f}".format(invoice.due) }}</span>
            </div>
        </div>
        
        {% if invoice.notes %}
        <div class="notes-section">
            <h4>Notes</h4>
            <p>{{ invoice. notes }}</p>
        </div>
        {% endif %}
        
        <div class="footer">
            <div class="signature-box">Customer Signature</div>
            <div class="signature-box">Authorized Signature</div>
        </div>
    </div>
    
    <script>
        // FIXED: Auto print on page load
        window.onload = function() {
            setTimeout(function() {
                window.print();
            }, 500);
        };
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATES LIST TEMPLATE
# ==============================================================================

STORE_ESTIMATES_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Estimates - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link active">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Estimates</div>
                <div class="page-subtitle">Manage quotations and estimates</div>
            </div>
            <a href="/admin/store/estimates/new">
                <button class="btn-primary" style="width: auto; padding: 12px 25px; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> New Estimate
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Estimates ({{ estimates|length }})</span>
                <div class="search-box" style="width: 300px; margin: 0;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchEstimate" placeholder="Search estimates..." onkeyup="filterEstimates()">
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table" id="estimatesTable">
                    <thead>
                        <tr>
                            <th>Estimate #</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Valid Until</th>
                            <th>Total</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for est in estimates|reverse %}
                        <tr>
                            <td style="font-weight: 700;">{{ est.estimate_no }}</td>
                            <td>{{ est.customer_name }}</td>
                            <td>{{ est.date }}</td>
                            <td>{{ est.valid_until }}</td>
                            <td style="font-weight: 600;">৳{{ "{:,.0f}".format(est. total) }}</td>
                            <td>
                                {% if est.status == 'converted' %}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">Converted</span>
                                {% elif est.status == 'expired' %}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0. 1); color: var(--accent-red);">Expired</span>
                                {% else %}
                                <span class="table-badge" style="background: rgba(59, 130, 246, 0. 1); color: var(--accent-blue);">Pending</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/estimates/print/{{ loop.revindex0 }}" target="_blank" class="action-btn btn-print-sm" title="Print" onclick="openPrintWindow(event, this. href)">
                                        <i class="fas fa-print"></i>
                                    </a>
                                    {% if est.status != 'converted' %}
                                    <a href="/admin/store/estimates/convert/{{ loop.revindex0 }}" class="action-btn btn-view" title="Convert to Invoice" onclick="return confirm('Convert this estimate to invoice?');">
                                        <i class="fas fa-exchange-alt"></i>
                                    </a>
                                    {% endif %}
                                    <a href="/admin/store/estimates/edit/{{ loop.revindex0 }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <form action="/admin/store/estimates/delete/{{ loop.revindex0 }}" method="POST" style="display: inline;" onsubmit="return confirm('Delete this estimate?');">
                                        <button type="submit" class="action-btn btn-del" title="Delete">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" class="empty-state">
                                <i class="fas fa-file-alt"></i>
                                <p>No estimates created yet</p>
                                <a href="/admin/store/estimates/new">
                                    <button class="btn-primary btn-sm" style="margin-top: 15px;">Create First Estimate</button>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterEstimates() {
            const input = document.getElementById('searchEstimate'). value. toLowerCase();
            const rows = document.querySelectorAll('#estimatesTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }
        
        function openPrintWindow(event, url) {
            event.preventDefault();
            const printWin = window.open(url, '_blank', 'width=900,height=700,scrollbars=yes,resizable=yes');
            if (printWin) {
                printWin.focus();
            } else {
                window.location. href = url;
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATE FORM TEMPLATE
# ==============================================================================

STORE_ESTIMATE_FORM_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ 'Edit' if estimate else 'New' }} Estimate - Store</title>
    """ + COMMON_STYLES + """
    <style>
        . items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .items-table th {
            background: rgba(255, 255, 255, 0. 05);
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-color);
        }
        .items-table td {
            padding: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        . items-table input, .items-table select {
            width: 100%;
            padding: 10px;
            font-size: 14px;
        }
        .remove-item-btn {
            background: var(--accent-red);
            color: white;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
        }
        .totals-section {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }
        .total-row:last-child {
            border-bottom: none;
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-purple);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList. toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/estimates" class="nav-link active">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ 'Edit' if estimate else 'Create New' }} Estimate</div>
                <div class="page-subtitle">{{ estimate.estimate_no if estimate else 'Fill in the details below' }}</div>
            </div>
        </div>

        <form action="{{ '/admin/store/estimates/update/' ~ index if estimate else '/admin/store/estimates/save' }}" method="POST" id="estimateForm">
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span>Estimate Details</span>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Estimate Number</label>
                            <input type="text" name="estimate_no" value="{{ estimate.estimate_no if estimate else next_estimate_no }}" readonly style="background: rgba(255,255,255,0.02);">
                        </div>
                        <div class="input-group">
                            <label>Date</label>
                            <input type="date" name="date" value="{{ estimate. date if estimate else today }}" required>
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label>Valid Until</label>
                        <input type="date" name="valid_until" value="{{ estimate.valid_until if estimate else valid_until }}" required>
                    </div>
                    
                    <div class="input-group">
                        <label>Customer</label>
                        <select name="customer_index" id="customerSelect" required onchange="updateCustomerInfo()">
                            <option value="">Select Customer</option>
                            {% for c in customers %}
                            <option value="{{ loop.index0 }}" data-name="{{ c.name }}"
                                {{ 'selected' if estimate and estimate.customer_index == loop.index0 }}>
                                {{ c.name }} - {{ c.phone }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <input type="hidden" name="customer_name" id="customerNameInput" value="{{ estimate.customer_name if estimate else '' }}">
                    
                    <div class="input-group">
                        <label>Notes (Optional)</label>
                        <textarea name="notes" rows="2" placeholder="Terms & conditions... ">{{ estimate.notes if estimate else '' }}</textarea>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span>Summary</span>
                    </div>
                    
                    <div class="totals-section">
                        <div class="total-row">
                            <span>Subtotal</span>
                            <span id="subtotalDisplay">৳0</span>
                        </div>
                        <div class="total-row">
                            <span>Discount</span>
                            <input type="number" name="discount" id="discountInput" value="{{ estimate.discount if estimate else 0 }}" min="0" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                        </div>
                        <div class="total-row">
                            <span>Total</span>
                            <span id="grandTotalDisplay">৳0</span>
                        </div>
                    </div>
                    
                    <input type="hidden" name="subtotal" id="subtotalInput" value="0">
                    <input type="hidden" name="total" id="totalInput" value="0">
                </div>
            </div>

            <div class="card" style="margin-top: 20px;">
                <div class="section-header">
                    <span>Estimate Items</span>
                    <button type="button" onclick="addItemRow()" class="btn-primary btn-sm" style="width: auto;">
                        <i class="fas fa-plus" style="margin-right: 5px;"></i> Add Item
                    </button>
                </div>
                
                <table class="items-table">
                    <thead>
                        <tr>
                            <th style="width: 40%;">Product</th>
                            <th style="width: 15%;">Qty</th>
                            <th style="width: 15%;">Price</th>
                            <th style="width: 20%;">Amount</th>
                            <th style="width: 10%;"></th>
                        </tr>
                    </thead>
                    <tbody id="itemsTableBody">
                        {% if estimate and estimate.items %}
                            {% for item in estimate.items %}
                            <tr class="item-row">
                                <td>
                                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                                        <option value="">Select Product</option>
                                        {% for p in products %}
                                        <option value="{{ loop.index0 }}" data-price="{{ p.price }}" data-name="{{ p.name }}"
                                            {{ 'selected' if item.product_index == loop.index0 }}>
                                            {{ p. code }} - {{ p. name }}
                                        </option>
                                        {% endfor %}
                                    </select>
                                </td>
                                <td>
                                    <input type="number" name="items[][qty]" class="item-qty" value="{{ item.qty }}" min="1" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][price]" class="item-price" value="{{ item.price }}" min="0" step="0.01" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][amount]" class="item-amount" value="{{ item.amount }}" readonly style="background: rgba(255,
                                    # ==============================================================================
# STORE ESTIMATE FORM TEMPLATE (CONTINUED)
# ==============================================================================

STORE_ESTIMATE_FORM_TEMPLATE_CONTINUED = """
255,255,0. 02);">
                                </td>
                                <td>
                                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr class="item-row">
                                <td>
                                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                                        <option value="">Select Product</option>
                                        {% for p in products %}
                                        <option value="{{ loop.index0 }}" data-price="{{ p. price }}" data-name="{{ p.name }}">
                                            {{ p. code }} - {{ p.name }}
                                        </option>
                                        {% endfor %}
                                    </select>
                                </td>
                                <td>
                                    <input type="number" name="items[][qty]" class="item-qty" value="1" min="1" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][price]" class="item-price" value="0" min="0" step="0.01" onchange="calculateRowAmount(this)">
                                </td>
                                <td>
                                    <input type="number" name="items[][amount]" class="item-amount" value="0" readonly style="background: rgba(255,255,255,0.02);">
                                </td>
                                <td>
                                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                                        <i class="fas fa-times"></i>
                                    </button>
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>

            <div style="display: flex; gap: 15px; margin-top: 20px;">
                <button type="submit" class="btn-purple" style="flex: 2;">
                    <i class="fas fa-save" style="margin-right: 8px;"></i> 
                    {{ 'Update' if estimate else 'Save' }} Estimate
                </button>
                <a href="/admin/store/estimates" style="flex: 1; text-decoration: none;">
                    <button type="button" class="btn-secondary" style="width: 100%;">
                        Cancel
                    </button>
                </a>
            </div>
        </form>
    </div>

    <script>
        const productsData = {{ products | tojson }};
        
        function updateCustomerInfo() {
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            document.getElementById('customerNameInput').value = option.dataset.name || '';
        }
        
        function addItemRow() {
            const tbody = document.getElementById('itemsTableBody');
            const productOptions = productsData.map((p, i) => 
                `<option value="${i}" data-price="${p. price}" data-name="${p.name}">${p.code} - ${p.name}</option>`
            ). join('');
            
            const newRow = document.createElement('tr');
            newRow. className = 'item-row';
            newRow.innerHTML = `
                <td>
                    <select name="items[][product_index]" class="product-select" onchange="updateItemPrice(this)">
                        <option value="">Select Product</option>
                        ${productOptions}
                    </select>
                </td>
                <td>
                    <input type="number" name="items[][qty]" class="item-qty" value="1" min="1" onchange="calculateRowAmount(this)">
                </td>
                <td>
                    <input type="number" name="items[][price]" class="item-price" value="0" min="0" step="0.01" onchange="calculateRowAmount(this)">
                </td>
                <td>
                    <input type="number" name="items[][amount]" class="item-amount" value="0" readonly style="background: rgba(255,255,255,0.02);">
                </td>
                <td>
                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(newRow);
        }
        
        function removeItemRow(btn) {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length > 1) {
                btn.closest('tr'). remove();
                calculateTotals();
            }
        }
        
        function updateItemPrice(select) {
            const row = select.closest('tr');
            const option = select.options[select.selectedIndex];
            const price = parseFloat(option. dataset.price) || 0;
            row.querySelector('.item-price').value = price;
            calculateRowAmount(select);
        }
        
        function calculateRowAmount(element) {
            const row = element.closest('tr');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const price = parseFloat(row.querySelector('.item-price').value) || 0;
            const amount = qty * price;
            row.querySelector('.item-amount').value = amount.toFixed(2);
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('.item-amount').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput'). value) || 0;
            const grandTotal = subtotal - discount;
            
            document.getElementById('subtotalDisplay').textContent = '৳' + subtotal.toLocaleString();
            document.getElementById('grandTotalDisplay').textContent = '৳' + grandTotal. toLocaleString();
            
            document.getElementById('subtotalInput').value = subtotal;
            document.getElementById('totalInput').value = grandTotal;
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            updateCustomerInfo();
            calculateTotals();
        });
    </script>
</body>
</html>
"""

# Combine estimate form template
STORE_ESTIMATE_FORM_TEMPLATE = STORE_ESTIMATE_FORM_TEMPLATE + STORE_ESTIMATE_FORM_TEMPLATE_CONTINUED

# ==============================================================================
# STORE ESTIMATE PRINT TEMPLATE - FIXED
# ==============================================================================

STORE_ESTIMATE_PRINT_TEMPLATE = """
<! DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estimate {{ estimate.estimate_no }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Poppins', sans-serif; 
            background: #fff; 
            padding: 20px; 
            color: #000; 
            font-size: 14px;
        }
        .container { 
            max-width: 800px; 
            margin: 0 auto; 
            border: 2px solid #000; 
            padding: 30px; 
        }
        .header { 
            text-align: center; 
            border-bottom: 2px solid #000; 
            padding-bottom: 15px; 
            margin-bottom: 25px; 
        }
        .company-name { 
            font-size: 28px; 
            font-weight: 800; 
            text-transform: uppercase; 
            color: #2c3e50; 
        }
        .company-address { 
            font-size: 12px; 
            color: #555; 
            margin-top: 5px; 
        }
        .estimate-title { 
            background: #8B5CF6; 
            color: white; 
            padding: 8px 30px; 
            display: inline-block; 
            font-weight: 700; 
            font-size: 18px; 
            margin-top: 15px; 
            border-radius: 4px;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .info-section {
            display: flex;
            justify-content: space-between;
            margin-bottom: 25px;
        }
        .info-box {
            flex: 1;
        }
        .info-box h4 {
            font-size: 12px;
            color: #777;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .info-box p {
            font-size: 14px;
            margin-bottom: 5px;
        }
        .info-box . highlight {
            font-size: 16px;
            font-weight: 700;
        }
        .validity-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 10px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 600;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .items-table th {
            background: #8B5CF6 !important;
            color: white ! important;
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .items-table td {
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        .items-table tr:nth-child(even) {
            background: #f9f9f9;
        }
        .items-table . amount {
            text-align: right;
            font-weight: 600;
        }
        .totals-section {
            margin-top: 20px;
            margin-left: auto;
            width: 300px;
        }
        .total-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .total-row. grand {
            border-top: 2px solid #000;
            border-bottom: none;
            font-size: 18px;
            font-weight: 800;
            padding-top: 15px;
            color: #8B5CF6;
        }
        .footer {
            margin-top: 50px;
            display: flex;
            justify-content: space-between;
            text-align: center;
        }
        .signature-box {
            width: 200px;
            border-top: 2px solid #000;
            padding-top: 10px;
            font-weight: 600;
        }
        . no-print {
            margin-bottom: 20px;
            text-align: right;
        }
        .btn {
            padding: 10px 25px;
            background: #2c3e50;
            color: white;
            border: none;
            cursor: pointer;
            border-radius: 5px;
            font-size: 14px;
            margin-left: 10px;
            text-decoration: none;
            display: inline-block;
        }
        .btn-print {
            background: #8B5CF6;
        }
        .notes-section {
            margin-top: 20px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 5px;
        }
        .notes-section h4 {
            font-size: 12px;
            color: #777;
            margin-bottom: 5px;
        }
        
        @media print {
            .no-print { display: none ! important; }
            body { padding: 0; }
            .container { border: none; padding: 0; max-width: 100%; }
            .estimate-title, .items-table th { 
                background: #8B5CF6 !important; 
                color: white ! important; 
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            .validity-box {
                background: #fff3cd ! important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
</head>
<body>
    <div class="no-print">
        <a href="/admin/store/estimates" class="btn">← Back to Estimates</a>
        <button onclick="window.print()" class="btn btn-print">🖨️ Print Estimate</button>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="company-name">COTTON CLOTHING BD LTD</div>
            <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur</div>
            <div class="estimate-title">ESTIMATE / QUOTATION</div>
        </div>
        
        <div class="validity-box">
            ⏰ Valid Until: {{ estimate.valid_until }}
        </div>
        
        <div class="info-section">
            <div class="info-box">
                <h4>Prepared For</h4>
                <p class="highlight">{{ estimate.customer_name }}</p>
            </div>
            <div class="info-box" style="text-align: right;">
                <h4>Estimate Details</h4>
                <p><strong>Estimate #:</strong> {{ estimate. estimate_no }}</p>
                <p><strong>Date:</strong> {{ estimate.date }}</p>
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 10%;">#</th>
                    <th style="width: 45%;">Description</th>
                    <th style="width: 15%;">Qty</th>
                    <th style="width: 15%;">Rate</th>
                    <th style="width: 15%;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in estimate.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.product_name }}</td>
                    <td>{{ item.qty }}</td>
                    <td>৳{{ "{:,.0f}".format(item.price) }}</td>
                    <td class="amount">৳{{ "{:,. 0f}".format(item.amount) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-section">
            <div class="total-row">
                <span>Subtotal</span>
                <span>৳{{ "{:,.0f}".format(estimate.subtotal) }}</span>
            </div>
            {% if estimate.discount > 0 %}
            <div class="total-row">
                <span>Discount</span>
                <span>-৳{{ "{:,.0f}". format(estimate.discount) }}</span>
            </div>
            {% endif %}
            <div class="total-row grand">
                <span>Total</span>
                <span>৳{{ "{:,.0f}".format(estimate.total) }}</span>
            </div>
        </div>
        
        {% if estimate.notes %}
        <div class="notes-section">
            <h4>Terms & Conditions</h4>
            <p>{{ estimate. notes }}</p>
        </div>
        {% endif %}
        
        <div class="footer">
            <div class="signature-box">Customer Signature</div>
            <div class="signature-box">Authorized Signature</div>
        </div>
    </div>
    
    <script>
        // FIXED: Auto print on page load
        window. onload = function() {
            setTimeout(function() {
                window.print();
            }, 500);
        };
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE PAYMENTS LIST TEMPLATE
# ==============================================================================

STORE_PAYMENTS_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Payments - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar'). classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link active">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Payments</div>
                <div class="page-subtitle">Track all payment transactions</div>
            </div>
            <a href="/admin/store/payments/new">
                <button class="btn-primary" style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Receive Payment
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Payments ({{ payments|length }})</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Invoice #</th>
                            <th>Customer</th>
                            <th>Method</th>
                            <th>Amount</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in payments|reverse %}
                        <tr>
                            <td>{{ p.date }}</td>
                            <td style="font-weight: 700;">{{ p.invoice_no }}</td>
                            <td>{{ p.customer_name }}</td>
                            <td>
                                <span class="table-badge" style="
                                    {% if p.method == 'Cash' %}
                                    background: rgba(16, 185, 129, 0.1); color: var(--accent-green);
                                    {% elif p.method == 'Bank' %}
                                    background: rgba(59, 130, 246, 0. 1); color: var(--accent-blue);
                                    {% else %}
                                    background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);
                                    {% endif %}
                                ">{{ p.method }}</span>
                            </td>
                            <td style="font-weight: 700; color: var(--accent-green);">৳{{ "{:,. 0f}".format(p.amount) }}</td>
                            <td style="color: var(--text-secondary);">{{ p. notes if p.notes else '-' }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" class="empty-state">
                                <i class="fas fa-money-bill-wave"></i>
                                <p>No payments recorded yet</p>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE PAYMENT FORM TEMPLATE
# ==============================================================================

STORE_PAYMENT_FORM_TEMPLATE = """
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Receive Payment - Store</title>
    """ + COMMON_STYLES + """
    <style>
        .form-container {
            max-width: 550px;
            margin: 0 auto;
        }
        .invoice-info {
            background: rgba(255, 122, 0, 0.1);
            border: 1px solid rgba(255, 122, 0, 0.2);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
        }
        .invoice-info-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .invoice-info-row:last-child {
            border-bottom: none;
            font-weight: 700;
            font-size: 18px;
            color: var(--accent-red);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/payments" class="nav-link active">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Receive Payment</div>
                <div class="page-subtitle">Record a new payment transaction</div>
            </div>
        </div>

        <div class="form-container">
            <div class="card">
                <form action="/admin/store/payments/save" method="POST">
                    <div class="input-group">
                        <label><i class="fas fa-file-invoice" style="margin-right: 5px;"></i> Invoice</label>
                        <select name="invoice_index" id="invoiceSelect" required onchange="updateInvoiceInfo()">
                            <option value="">Select Invoice</option>
                            {% for inv in invoices %}
                            {% if inv.due > 0 %}
                            <option value="{{ loop.index0 }}" 
                                data-no="{{ inv.invoice_no }}"
                                data-customer="{{ inv.customer_name }}"
                                data-total="{{ inv.total }}"
                                data-paid="{{ inv.paid }}"
                                data-due="{{ inv. due }}"
                                {{ 'selected' if selected_invoice == loop. index0 }}>
                                {{ inv.invoice_no }} - {{ inv.customer_name }} (Due: ৳{{ "{:,.0f}". format(inv.due) }})
                            </option>
                            {% endif %}
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="invoice-info" id="invoiceInfo" style="display: none;">
                        <div class="invoice-info-row">
                            <span style="color: var(--text-secondary);">Invoice</span>
                            <span id="infoInvoiceNo">-</span>
                        </div>
                        <div class="invoice-info-row">
                            <span style="color: var(--text-secondary);">Customer</span>
                            <span id="infoCustomer">-</span>
                        </div>
                        <div class="invoice-info-row">
                            <span style="color: var(--text-secondary);">Total</span>
                            <span id="infoTotal">৳0</span>
                        </div>
                        <div class="invoice-info-row">
                            <span style="color: var(--text-secondary);">Already Paid</span>
                            <span id="infoPaid" style="color: var(--accent-green);">৳0</span>
                        </div>
                        <div class="invoice-info-row">
                            <span>Due Amount</span>
                            <span id="infoDue">৳0</span>
                        </div>
                    </div>
                    
                    <input type="hidden" name="invoice_no" id="invoiceNoInput">
                    <input type="hidden" name="customer_name" id="customerNameInput">
                    
                    <div class="input-group">
                        <label><i class="fas fa-calendar" style="margin-right: 5px;"></i> Payment Date</label>
                        <input type="date" name="date" value="{{ today }}" required>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label><i class="fas fa-money-bill" style="margin-right: 5px;"></i> Amount</label>
                            <input type="number" name="amount" id="amountInput" required placeholder="0" min="1" step="0.01">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-credit-card" style="margin-right: 5px;"></i> Method</label>
                            <select name="method" required>
                                <option value="Cash">Cash</option>
                                <option value="Bank">Bank Transfer</option>
                                <option value="bKash">bKash</option>
                                <option value="Nagad">Nagad</option>
                                <option value="Check">Check</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-sticky-note" style="margin-right: 5px;"></i> Notes (Optional)</label>
                        <textarea name="notes" rows="2" placeholder="Payment reference, check number, etc... "></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 10px;">
                        <button type="submit" class="btn-success">
                            <i class="fas fa-check" style="margin-right: 8px;"></i> Record Payment
                        </button>
                        <a href="/admin/store/payments" style="flex: 1; text-decoration: none;">
                            <button type="button" class="btn-secondary" style="width: 100%;">
                                Cancel
                            </button>
                        </a>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
        function updateInvoiceInfo() {
            const select = document.getElementById('invoiceSelect');
            const option = select.options[select. selectedIndex];
            const infoDiv = document. getElementById('invoiceInfo');
            
            if (option. value) {
                document.getElementById('infoInvoiceNo'). textContent = option. dataset.no;
                document.getElementById('infoCustomer').textContent = option.dataset.customer;
                document.getElementById('infoTotal').textContent = '৳' + parseFloat(option.dataset.total).toLocaleString();
                document.getElementById('infoPaid').textContent = '৳' + parseFloat(option.dataset.paid). toLocaleString();
                document.getElementById('infoDue'). textContent = '৳' + parseFloat(option.dataset. due).toLocaleString();
                
                document.getElementById('invoiceNoInput').value = option.dataset.no;
                document. getElementById('customerNameInput').value = option. dataset.customer;
                document.getElementById('amountInput').max = option.dataset. due;
                document.getElementById('amountInput').value = option.dataset. due;
                
                infoDiv.style.display = 'block';
            } else {
                infoDiv.style. display = 'none';
            }
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            updateInvoiceInfo();
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE USER MANAGEMENT TEMPLATE - FIXED: NEW ROUTE ADDED
# ==============================================================================

STORE_USER_MANAGEMENT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>User Management - Store</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Success! </div>
        </div>
        <div class="loading-text">Processing...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            <span>Store</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/admin/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/admin/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            <a href="/admin/store/users" class="nav-link active">
                <i class="fas fa-users-cog"></i> User Management
            </a>
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">User Management</div>
                <div class="page-subtitle">Manage store user accounts</div>
            </div>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{ messages[0] }}</span>
                </div>
            {% endif %}
        {% endwith %}

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span>Store Users</span>
                    <span class="table-badge" style="background: var(--accent-purple); color: white;">{{ users|length }} Users</span>
                </div>
                <div style="max-height: 450px; overflow-y: auto;">
                    <table class="dark-table">
                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Role</th>
                                <th style="text-align: right;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for username, data in users.items() %}
                            <tr>
                                <td style="font-weight: 600;">{{ username }}</td>
                                <td>
                                    <span class="table-badge" style="
                                        {% if data.role == 'store_admin' %}
                                        background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);
                                        {% else %}
                                        background: rgba(139, 92, 246, 0. 1); color: var(--accent-purple);
                                        {% endif %}
                                    ">{{ data.role }}</span>
                                </td>
                                <td>
                                    <div class="action-cell">
                                        {% if data.role != 'store_admin' %}
                                        <button class="action-btn btn-edit" onclick="editUser('{{ username }}', '{{ data.password }}', '{{ data.permissions|join(',') }}')">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        <form action="/admin/store/users/delete" method="POST" style="display: inline;" onsubmit="return confirm('Delete this user?');">
                                            <input type="hidden" name="username" value="{{ username }}">
                                            <button type="submit" class="action-btn btn-del">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                        {% else %}
                                        <i class="fas fa-shield-alt" style="color: var(--accent-orange); opacity: 0.5;"></i>
                                        {% endif %}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span id="formTitle">Create New User</span>
                    <i class="fas fa-user-plus" style="color: var(--accent-orange);"></i>
                </div>
                <form action="/admin/store/users/save" method="POST" id="userForm">
                    <input type="hidden" name="action_type" id="actionType" value="create">
                    <input type="hidden" name="original_username" id="originalUsername" value="">
                    
                    <div class="input-group">
                        <label><i class="fas fa-user" style="margin-right: 5px;"></i> USERNAME</label>
                        <input type="text" name="username" id="usernameInput" required placeholder="Enter username">
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-key" style="margin-right: 5px;"></i> PASSWORD</label>
                        <input type="text" name="password" id="passwordInput" required placeholder="Enter password">
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-shield-alt" style="margin-right: 5px;"></i> PERMISSIONS</label>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 5px;">
                            <label class="perm-checkbox">
                                <input type="checkbox" name="perm_products" id="permProducts" checked>
                                <span>Products</span>
                            </label>
                            <label class="perm-checkbox">
                                <input type="checkbox" name="perm_customers" id="permCustomers" checked>
                                <span>Customers</span>
                            </label>
                            <label class="perm-checkbox">
                                <input type="checkbox" name="perm_invoices" id="permInvoices" checked>
                                <span>Invoices</span>
                            </label>
                            <label class="perm-checkbox">
                                <input type="checkbox" name="perm_estimates" id="permEstimates">
                                <span>Estimates</span>
                            </label>
                            <label class="perm-checkbox">
                                <input type="checkbox" name="perm_payments" id="permPayments">
                                <span>Payments</span>
                            </label>
                        </div>
                    </div>
                    
                    <button type="submit" id="submitBtn">
                        <i class="fas fa-save" style="margin-right: 10px;"></i> Save User
                    </button>
                    <button type="button" onclick="resetForm()" style="margin-top: 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                        <i class="fas fa-undo" style="margin-right: 10px;"></i> Reset Form
                    </button>
                </form>
            </div>
        </div>
    </div>

    <script>
        function editUser(username, password, permsStr) {
            document.getElementById('formTitle').textContent = 'Edit User';
            document.getElementById('actionType').value = 'update';
            document.getElementById('originalUsername').value = username;
            document.getElementById('usernameInput').value = username;
            document.getElementById('usernameInput').readOnly = true;
            document.getElementById('passwordInput').value = password;
            document.getElementById('submitBtn').innerHTML = '<i class="fas fa-sync" style="margin-right: 10px;"></i> Update User';
            
            const perms = permsStr.split(',');
            document.getElementById('permProducts').checked = perms.includes('products');
            document.getElementById('permCustomers'). checked = perms. includes('customers');
            document.getElementById('permInvoices'). checked = perms. includes('invoices');
            document.getElementById('permEstimates').checked = perms.includes('estimates');
            document.getElementById('permPayments'). checked = perms. includes('payments');
        }
        
        function resetForm() {
            document. getElementById('formTitle').textContent = 'Create New User';
            document. getElementById('actionType'). value = 'create';
            document. getElementById('originalUsername'). value = '';
            document.getElementById('usernameInput').value = '';
            document.getElementById('usernameInput').readOnly = false;
            document.getElementById('passwordInput').value = '';
            document. getElementById('submitBtn').innerHTML = '<i class="fas fa-save" style="margin-right: 10px;"></i> Save User';
            
            document. getElementById('permProducts'). checked = true;
            document. getElementById('permCustomers').checked = true;
            document.getElementById('permInvoices').checked = true;
            document.getElementById('permEstimates').checked = false;
            document. getElementById('permPayments').checked = false;
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTES: AUTHENTICATION & SESSION MANAGEMENT
# ==============================================================================

@app.route('/')
def index():
    if 'user' in session:
        if session. get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        if username in users and users[username]['password'] == password:
            session. permanent = True
            session['user'] = username
            session['role'] = users[username]['role']
            session['permissions'] = users[username]. get('permissions', [])
            session['login_time'] = get_bd_time(). isoformat()
            
            # Update last login time
            users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
            save_users(users)
            
            if users[username]['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password!')
            return redirect(url_for('login'))
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    # Calculate session duration
    if 'login_time' in session and 'user' in session:
        try:
            login_time = datetime. fromisoformat(session['login_time'])
            now = get_bd_time()
            if login_time. tzinfo is None:
                login_time = bd_tz.localize(login_time)
            duration = now - login_time
            
            minutes = int(duration.total_seconds() // 60)
            hours = minutes // 60
            mins = minutes % 60
            
            if hours > 0:
                duration_str = f"{hours}h {mins}m"
            else:
                duration_str = f"{mins} minutes"
            
            users = load_users()
            if session['user'] in users:
                users[session['user']]['last_duration'] = duration_str
                save_users(users)
        except:
            pass
    
    session.clear()
    return redirect(url_for('login'))

# ==============================================================================
# FLASK ROUTES: ADMIN DASHBOARD
# ==============================================================================

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access Denied!  Admin privileges required.')
        return redirect(url_for('login'))
    
    stats = get_dashboard_summary_v2()
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)

@app.route('/dashboard')
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    return render_template_string(USER_DASHBOARD_TEMPLATE)

# ==============================================================================
# FLASK ROUTES: USER MANAGEMENT (ADMIN)
# ==============================================================================

@app.route('/admin/get-users')
def get_users():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    users = load_users()
    return jsonify(users)

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    permissions = data.get('permissions', [])
    action_type = data.get('action_type', 'create')
    
    users = load_users()
    
    if action_type == 'create':
        if username in users:
            return jsonify({"status": "error", "message": "Username already exists!"})
        
        users[username] = {
            "password": password,
            "role": "user",
            "permissions": permissions,
            "created_at": get_bd_date_str(),
            "last_login": "Never",
            "last_duration": "N/A"
        }
    else:  # update
        if username in users:
            users[username]['password'] = password
            users[username]['permissions'] = permissions
    
    save_users(users)
    return jsonify({"status": "success"})

@app. route('/admin/delete-user', methods=['POST'])
def delete_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request. get_json()
    username = data. get('username')
    
    users = load_users()
    
    if username in users and users[username]. get('role') != 'admin':
        del users[username]
        save_users(users)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Cannot delete admin or user not found"})

# ==============================================================================
# FLASK ROUTES: CLOSING REPORT GENERATION
# ==============================================================================

@app. route('/generate-report', methods=['POST'])
def generate_report():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check permission
    if session. get('role') != 'admin' and 'closing' not in session. get('permissions', []):
        flash('Access Denied!  You do not have permission for Closing Reports.')
        return redirect(url_for('user_dashboard'))
    
    ref_no = request.form. get('ref_no', '').strip(). upper()
    
    if not ref_no:
        flash('Please enter a valid reference number!')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    # Fetch report data from API
    report_data = fetch_closing_report_data(ref_no)
    
    if not report_data:
        flash(f'No data found for reference: {ref_no}')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    # Create Excel file
    excel_file = create_formatted_excel_report(report_data, ref_no)
    
    if not excel_file:
        flash('Error generating report!')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    # Update statistics
    update_stats(ref_no, session['user'])
    
    # Generate filename
    filename = f"Closing_Report_{ref_no}_{get_bd_date_str()}. xlsx"
    
    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# ==============================================================================
# FLASK ROUTES: PO SHEET GENERATION
# ==============================================================================

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check permission
    if session.get('role') != 'admin' and 'po_sheet' not in session.get('permissions', []):
        flash('Access Denied!  You do not have permission for PO Sheets.')
        return redirect(url_for('user_dashboard'))
    
    if 'pdf_files' not in request. files:
        flash('No files uploaded!')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    files = request.files. getlist('pdf_files')
    
    if not files or files[0].filename == '':
        flash('No files selected!')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    all_data = []
    metadata = {}
    
    # Process each PDF file
    for file in files:
        if file and file.filename.endswith('.pdf'):
            # Save temporarily
            filepath = os.path. join(app.config['UPLOAD_FOLDER'], file.filename)
            file. save(filepath)
            
            try:
                data, meta = extract_data_dynamic(filepath)
                if data:
                    all_data.extend(data)
                if meta and meta.get('buyer') != 'N/A':
                    metadata = meta
            finally:
                # Clean up temp file
                if os.path.exists(filepath):
                    os.remove(filepath)
    
    if not all_data:
        flash('No valid data extracted from PDFs!')
        return redirect(url_for('admin_dashboard') if session.get('role') == 'admin' else url_for('user_dashboard'))
    
    # Create Excel workbook
    wb = openpyxl. Workbook()
    ws = wb. active
    ws.title = "PO Summary"
    
    # Styles
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Metadata header
    ws. merge_cells('A1:D1')
    ws['A1'] = f"PO Summary Report - {get_bd_date_str()}"
    ws['A1'].font = Font(bold=True, size=16)
    ws['A1'].alignment = center_align
    
    if metadata:
        ws['A2'] = f"Buyer: {metadata.get('buyer', 'N/A')}"
        ws['A3'] = f"Booking: {metadata.get('booking', 'N/A')}"
        ws['A4'] = f"Style: {metadata.get('style', 'N/A')}"
    
    # Data headers
    headers = ['P. O NO', 'Color', 'Size', 'Quantity']
    header_row = 6
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    
    # Data rows
    for row_idx, item in enumerate(all_data, header_row + 1):
        ws.cell(row=row_idx, column=1, value=item. get('P.O NO', '')).border = thin_border
        ws.cell(row=row_idx, column=2, value=item.get('Color', '')). border = thin_border
        ws.cell(row=row_idx, column=3, value=item. get('Size', '')).border = thin_border
        qty_cell = ws. cell(row=row_idx, column=4, value=item.get('Quantity', 0))
        qty_cell.border = thin_border
        qty_cell.alignment = center_align
    
    # Total row
    total_row = header_row + len(all_data) + 1
    ws.cell(row=total_row, column=3, value="TOTAL").font = Font(bold=True)
    ws.cell(row=total_row, column=4, value=f"=SUM(D{header_row+1}:D{total_row-1})").font = Font(bold=True)
    
    # Column widths
    ws. column_dimensions['A'].width = 15
    ws.column_dimensions['B']. width = 30
    ws.column_dimensions['C']. width = 12
    ws.column_dimensions['D']. width = 15
    
    # Update statistics
    update_po_stats(session['user'], len(files))
    
    # Save and send
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    
    filename = f"PO_Summary_{get_bd_date_str()}. xlsx"
    
    return send_file(
        file_stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# ==============================================================================
# FLASK ROUTES: ACCESSORIES MANAGEMENT - FIXED WITH CACHING
# ==============================================================================

@app. route('/admin/accessories')
def accessories_search():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check permission
    if session.get('role') != 'admin' and 'accessories' not in session. get('permissions', []):
        flash('Access Denied! You do not have permission for Accessories.')
        return redirect(url_for('user_dashboard'))
    
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.form.get('ref_no', '').strip().upper()
    
    if not ref:
        flash('Please enter a valid reference number!')
        return redirect(url_for('accessories_search'))
    
    # FIXED: Use cached API call
    api_data = fetch_closing_report_data_with_cache(ref)
    
    colors = api_data.get('colors', [])
    buyer = api_data.get('buyer', 'N/A')
    style = api_data. get('style', 'N/A')
    from_cache = api_data. get('from_cache', False)
    
    # Load existing challans
    acc_db = load_accessories_db()
    challans = acc_db.get(ref, {}).get('challans', [])
    
    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref,
        buyer=buyer,
        style=style,
        colors=colors,
        challans=challans,
        from_cache=from_cache
    )

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    """Direct access to accessories input page (for redirects)"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.args.get('ref', '').strip().upper()
    
    if not ref:
        return redirect(url_for('accessories_search'))
    
    # FIXED: Use cached API call
    api_data = fetch_closing_report_data_with_cache(ref)
    
    colors = api_data.get('colors', [])
    buyer = api_data.get('buyer', 'N/A')
    style = api_data.get('style', 'N/A')
    from_cache = api_data.get('from_cache', False)
    
    # Load existing challans
    acc_db = load_accessories_db()
    challans = acc_db.get(ref, {}).get('challans', [])
    
    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref,
        buyer=buyer,
        style=style,
        colors=colors,
        challans=challans,
        from_cache=from_cache
    )

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.form. get('ref', '').strip().upper()
    item_type = request.form.get('item_type', 'Top')
    color = request.form. get('color', '')
    line_no = request.form. get('line_no', '')
    size = request.form. get('size', 'ALL')
    qty = request.form. get('qty', '0')
    
    try:
        qty = int(qty)
    except:
        qty = 0
    
    if not ref or not color or not line_no or qty <= 0:
        flash('Please fill all required fields!')
        return redirect(url_for('accessories_input_direct', ref=ref))
    
    acc_db = load_accessories_db()
    
    # Initialize if not exists
    if ref not in acc_db:
        acc_db[ref] = {
            "buyer": "N/A",
            "style": "N/A",
            "colors": [],
            "challans": [],
            "last_api_call": None
        }
    
    # Add new challan
    new_challan = {
        "date": get_bd_date_str(),
        "item_type": item_type,
        "color": color,
        "line": line_no,
        "size": size,
        "qty": qty,
        "added_by": session['user'],
        "added_at": get_bd_time(). isoformat()
    }
    
    acc_db[ref]['challans'].append(new_challan)
    save_accessories_db(acc_db)
    
    flash(f'Challan saved successfully! Line: {line_no}, Qty: {qty}')
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/edit')
def accessories_edit():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access Denied!  Admin privileges required.')
        return redirect(url_for('login'))
    
    ref = request.args.get('ref', '').strip().upper()
    index = request.args. get('index', type=int)
    
    if not ref or index is None:
        return redirect(url_for('accessories_search'))
    
    acc_db = load_accessories_db()
    
    if ref not in acc_db or index >= len(acc_db[ref]. get('challans', [])):
        flash('Entry not found!')
        return redirect(url_for('accessories_input_direct', ref=ref))
    
    item = acc_db[ref]['challans'][index]
    
    return render_template_string(
        ACCESSORIES_EDIT_TEMPLATE,
        ref=ref,
        index=index,
        item=item
    )

@app. route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access Denied!')
        return redirect(url_for('login'))
    
    ref = request.form.get('ref', '').strip().upper()
    index = request.form.get('index', type=int)
    line_no = request. form.get('line_no', '')
    color = request.form. get('color', '')
    size = request.form.get('size', 'ALL')
    qty = request.form.get('qty', '0')
    
    try:
        qty = int(qty)
    except:
        qty = 0
    
    acc_db = load_accessories_db()
    
    if ref in acc_db and index is not None and index < len(acc_db[ref]. get('challans', [])):
        acc_db[ref]['challans'][index]['line'] = line_no
        acc_db[ref]['challans'][index]['color'] = color
        acc_db[ref]['challans'][index]['size'] = size
        acc_db[ref]['challans'][index]['qty'] = qty
        acc_db[ref]['challans'][index]['updated_by'] = session['user']
        acc_db[ref]['challans'][index]['updated_at'] = get_bd_time().isoformat()
        
        save_accessories_db(acc_db)
        flash('Entry updated successfully!')
    else:
        flash('Entry not found!')
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app. route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access Denied!')
        return redirect(url_for('login'))
    
    ref = request.form.get('ref', ''). strip().upper()
    index = request. form.get('index', type=int)
    
    acc_db = load_accessories_db()
    
    if ref in acc_db and index is not None and index < len(acc_db[ref]. get('challans', [])):
        deleted_item = acc_db[ref]['challans']. pop(index)
        save_accessories_db(acc_db)
        flash(f'Entry deleted: Line {deleted_item. get("line")}, Qty {deleted_item.get("qty")}')
    else:
        flash('Entry not found!')
    
    return redirect(url_for('accessories_input_direct', ref=ref))

# ==============================================================================
# FLASK ROUTES: ACCESSORIES PRINT REPORT - FIXED
# ==============================================================================

@app.route('/admin/accessories/print')
def accessories_print():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.args.get('ref', '').strip().upper()
    
    if not ref:
        return redirect(url_for('accessories_search'))
    
    acc_db = load_accessories_db()
    
    if ref not in acc_db:
        flash('No data found for this reference!')
        return redirect(url_for('accessories_search'))
    
    data = acc_db[ref]
    challans = data.get('challans', [])
    buyer = data.get('buyer', 'N/A')
    style = data.get('style', 'N/A')
    
    # Calculate line-wise summary
    line_summary = {}
    for challan in challans:
        line = challan.get('line', 'Unknown')
        qty = challan.get('qty', 0)
        if line in line_summary:
            line_summary[line] += qty
        else:
            line_summary[line] = qty
    
    # Get item type (use the most common one or first one)
    item_type = challans[0].get('item_type', 'Top') if challans else 'Top'
    
    return render_template_string(
        ACCESSORIES_REPORT_TEMPLATE,
        ref=ref,
        buyer=buyer,
        style=style,
        challans=challans,
        count=len(challans),
        line_summary=line_summary,
        item_type=item_type,
        today=get_bd_date_str()
    )
    # ==============================================================================
# FLASK ROUTES: STORE DASHBOARD
# ==============================================================================

@app.route('/admin/store')
def store_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    stats = get_store_dashboard_summary()
    invoices = load_store_invoices()
    
    return render_template_string(
        STORE_DASHBOARD_TEMPLATE,
        stats=stats,
        recent_invoices=invoices[-10:] if invoices else []
    )

# ==============================================================================
# FLASK ROUTES: STORE PRODUCTS
# ==============================================================================

@app.route('/admin/store/products')
def store_products():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = load_store_products()
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products)

@app.route('/admin/store/products/new')
def store_product_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    return render_template_string(STORE_PRODUCT_FORM_TEMPLATE, product=None, index=None)

@app. route('/admin/store/products/save', methods=['POST'])
def store_product_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = load_store_products()
    
    new_product = {
        "code": request.form. get('code', ''),
        "name": request.form.get('name', ''),
        "category": request.form. get('category', ''),
        "unit": request.form.get('unit', ''),
        "price": float(request.form.get('price', 0)),
        "stock": int(request.form.get('stock', 0)),
        "description": request.form. get('description', ''),
        "created_at": get_bd_date_str()
    }
    
    products.append(new_product)
    save_store_products(products)
    
    flash('Product added successfully!')
    return redirect(url_for('store_products'))

@app.route('/admin/store/products/edit/<int:index>')
def store_product_edit(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = load_store_products()
    
    if index >= len(products):
        flash('Product not found!')
        return redirect(url_for('store_products'))
    
    return render_template_string(STORE_PRODUCT_FORM_TEMPLATE, product=products[index], index=index)

@app.route('/admin/store/products/update/<int:index>', methods=['POST'])
def store_product_update(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = load_store_products()
    
    if index >= len(products):
        flash('Product not found!')
        return redirect(url_for('store_products'))
    
    products[index]['code'] = request. form.get('code', '')
    products[index]['name'] = request.form.get('name', '')
    products[index]['category'] = request.form.get('category', '')
    products[index]['unit'] = request.form.get('unit', '')
    products[index]['price'] = float(request.form.get('price', 0))
    products[index]['stock'] = int(request.form.get('stock', 0))
    products[index]['description'] = request.form.get('description', '')
    
    save_store_products(products)
    
    flash('Product updated successfully!')
    return redirect(url_for('store_products'))

@app.route('/admin/store/products/delete/<int:index>', methods=['POST'])
def store_product_delete(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = load_store_products()
    
    if index < len(products):
        deleted = products.pop(index)
        save_store_products(products)
        flash(f'Product "{deleted["name"]}" deleted!')
    
    return redirect(url_for('store_products'))

# ==============================================================================
# FLASK ROUTES: STORE CUSTOMERS
# ==============================================================================

@app.route('/admin/store/customers')
def store_customers():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)

@app.route('/admin/store/customers/new')
def store_customer_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    return render_template_string(STORE_CUSTOMER_FORM_TEMPLATE, customer=None, index=None)

@app.route('/admin/store/customers/save', methods=['POST'])
def store_customer_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    
    new_customer = {
        "name": request. form.get('name', ''),
        "phone": request.form. get('phone', ''),
        "email": request.form. get('email', ''),
        "address": request.form. get('address', ''),
        "notes": request.form. get('notes', ''),
        "due": 0,
        "created_at": get_bd_date_str()
    }
    
    customers.append(new_customer)
    save_store_customers(customers)
    
    flash('Customer added successfully!')
    return redirect(url_for('store_customers'))

@app.route('/admin/store/customers/edit/<int:index>')
def store_customer_edit(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    
    if index >= len(customers):
        flash('Customer not found!')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_CUSTOMER_FORM_TEMPLATE, customer=customers[index], index=index)

@app.route('/admin/store/customers/update/<int:index>', methods=['POST'])
def store_customer_update(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    
    if index >= len(customers):
        flash('Customer not found!')
        return redirect(url_for('store_customers'))
    
    customers[index]['name'] = request. form.get('name', '')
    customers[index]['phone'] = request.form. get('phone', '')
    customers[index]['email'] = request.form.get('email', '')
    customers[index]['address'] = request.form.get('address', '')
    customers[index]['notes'] = request.form.get('notes', '')
    
    save_store_customers(customers)
    
    flash('Customer updated successfully!')
    return redirect(url_for('store_customers'))

@app.route('/admin/store/customers/delete/<int:index>', methods=['POST'])
def store_customer_delete(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    
    if index < len(customers):
        deleted = customers. pop(index)
        save_store_customers(customers)
        flash(f'Customer "{deleted["name"]}" deleted!')
    
    return redirect(url_for('store_customers'))

@app.route('/admin/store/customers/view/<int:index>')
def store_customer_view(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    invoices = load_store_invoices()
    
    if index >= len(customers):
        flash('Customer not found!')
        return redirect(url_for('store_customers'))
    
    customer = customers[index]
    
    # Get customer's invoices
    customer_invoices = [inv for inv in invoices if inv. get('customer_index') == index]
    
    return render_template_string(
        STORE_CUSTOMER_VIEW_TEMPLATE,
        customer=customer,
        index=index,
        customer_invoices=customer_invoices
    )

# ==============================================================================
# FLASK ROUTES: STORE INVOICES - FIXED
# ==============================================================================

@app.route('/admin/store/invoices')
def store_invoices():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    return render_template_string(STORE_INVOICES_TEMPLATE, invoices=invoices)

@app. route('/admin/store/invoices/new')
def store_invoice_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    products = load_store_products()
    next_no = generate_invoice_number()
    today = get_bd_time(). strftime('%Y-%m-%d')
    
    return render_template_string(
        STORE_INVOICE_FORM_TEMPLATE,
        invoice=None,
        index=None,
        customers=customers,
        products=products,
        next_invoice_no=next_no,
        today=today
    )

@app.route('/admin/store/invoices/save', methods=['POST'])
def store_invoice_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    customers = load_store_customers()
    products = load_store_products()
    
    customer_index = int(request.form. get('customer_index', 0))
    customer_name = request.form.get('customer_name', '')
    
    # Parse items from form
    items = []
    form_data = request.form. to_dict(flat=False)
    
    product_indices = form_data.get('items[][product_index]', [])
    qtys = form_data.get('items[][qty]', [])
    prices = form_data. get('items[][price]', [])
    amounts = form_data. get('items[][amount]', [])
    
    for i in range(len(product_indices)):
        if product_indices[i]:
            prod_idx = int(product_indices[i])
            item = {
                "product_index": prod_idx,
                "product_name": products[prod_idx]['name'] if prod_idx < len(products) else 'Unknown',
                "qty": int(float(qtys[i])) if i < len(qtys) else 1,
                "price": float(prices[i]) if i < len(prices) else 0,
                "amount": float(amounts[i]) if i < len(amounts) else 0
            }
            items.append(item)
    
    new_invoice = {
        "invoice_no": request.form.get('invoice_no', generate_invoice_number()),
        "date": request.form.get('date', get_bd_date_str()),
        "customer_index": customer_index,
        "customer_name": customer_name,
        "items": items,
        "subtotal": float(request.form.get('subtotal', 0)),
        "discount": float(request. form.get('discount', 0)),
        "total": float(request. form.get('total', 0)),
        "paid": float(request.form. get('paid', 0)),
        "due": float(request. form.get('due', 0)),
        "notes": request.form. get('notes', ''),
        "created_at": get_bd_time(). isoformat(),
        "created_by": session['user']
    }
    
    invoices.append(new_invoice)
    save_store_invoices(invoices)
    
    # Update customer due
    if customer_index < len(customers):
        customers[customer_index]['due'] = customers[customer_index]. get('due', 0) + new_invoice['due']
        save_store_customers(customers)
    
    flash(f'Invoice {new_invoice["invoice_no"]} created successfully!')
    return redirect(url_for('store_invoices'))

@app. route('/admin/store/invoices/view/<int:index>')
def store_invoice_view(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    
    if index >= len(invoices):
        flash('Invoice not found!')
        return redirect(url_for('store_invoices'))
    
    return render_template_string(STORE_INVOICE_VIEW_TEMPLATE, invoice=invoices[index], index=index)

@app.route('/admin/store/invoices/edit/<int:index>')
def store_invoice_edit(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    customers = load_store_customers()
    products = load_store_products()
    
    if index >= len(invoices):
        flash('Invoice not found!')
        return redirect(url_for('store_invoices'))
    
    return render_template_string(
        STORE_INVOICE_FORM_TEMPLATE,
        invoice=invoices[index],
        index=index,
        customers=customers,
        products=products,
        next_invoice_no=invoices[index]['invoice_no'],
        today=invoices[index]['date']
    )

@app.route('/admin/store/invoices/update/<int:index>', methods=['POST'])
def store_invoice_update(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    customers = load_store_customers()
    products = load_store_products()
    
    if index >= len(invoices):
        flash('Invoice not found!')
        return redirect(url_for('store_invoices'))
    
    old_invoice = invoices[index]
    old_due = old_invoice. get('due', 0)
    customer_index = int(request.form. get('customer_index', 0))
    
    # Parse items
    items = []
    form_data = request.form.to_dict(flat=False)
    
    product_indices = form_data.get('items[][product_index]', [])
    qtys = form_data.get('items[][qty]', [])
    prices = form_data.get('items[][price]', [])
    amounts = form_data.get('items[][amount]', [])
    
    for i in range(len(product_indices)):
        if product_indices[i]:
            prod_idx = int(product_indices[i])
            item = {
                "product_index": prod_idx,
                "product_name": products[prod_idx]['name'] if prod_idx < len(products) else 'Unknown',
                "qty": int(float(qtys[i])) if i < len(qtys) else 1,
                "price": float(prices[i]) if i < len(prices) else 0,
                "amount": float(amounts[i]) if i < len(amounts) else 0
            }
            items.append(item)
    
    new_due = float(request. form.get('due', 0))
    
    invoices[index]. update({
        "date": request.form.get('date', get_bd_date_str()),
        "customer_index": customer_index,
        "customer_name": request.form.get('customer_name', ''),
        "items": items,
        "subtotal": float(request.form.get('subtotal', 0)),
        "discount": float(request.form. get('discount', 0)),
        "total": float(request.form.get('total', 0)),
        "paid": float(request.form.get('paid', 0)),
        "due": new_due,
        "notes": request.form.get('notes', ''),
        "updated_at": get_bd_time().isoformat(),
        "updated_by": session['user']
    })
    
    save_store_invoices(invoices)
    
    # Update customer due
    if customer_index < len(customers):
        due_diff = new_due - old_due
        customers[customer_index]['due'] = customers[customer_index]. get('due', 0) + due_diff
        save_store_customers(customers)
    
    flash('Invoice updated successfully!')
    return redirect(url_for('store_invoices'))

@app.route('/admin/store/invoices/delete/<int:index>', methods=['POST'])
def store_invoice_delete(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    customers = load_store_customers()
    
    if index < len(invoices):
        deleted = invoices.pop(index)
        
        # Update customer due
        customer_index = deleted.get('customer_index', 0)
        if customer_index < len(customers):
            customers[customer_index]['due'] = max(0, customers[customer_index].get('due', 0) - deleted. get('due', 0))
            save_store_customers(customers)
        
        save_store_invoices(invoices)
        flash(f'Invoice {deleted["invoice_no"]} deleted!')
    
    return redirect(url_for('store_invoices'))

# FIXED: Invoice Print Route
@app.route('/admin/store/invoices/print/<int:index>')
def store_invoice_print(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    
    if index >= len(invoices):
        flash('Invoice not found!')
        return redirect(url_for('store_invoices'))
    
    return render_template_string(STORE_INVOICE_PRINT_TEMPLATE, invoice=invoices[index], index=index)

# ==============================================================================
# FLASK ROUTES: STORE ESTIMATES - FIXED
# ==============================================================================

@app.route('/admin/store/estimates')
def store_estimates():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    return render_template_string(STORE_ESTIMATES_TEMPLATE, estimates=estimates)

@app. route('/admin/store/estimates/new')
def store_estimate_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customers = load_store_customers()
    products = load_store_products()
    next_no = generate_estimate_number()
    today = get_bd_time().strftime('%Y-%m-%d')
    valid_until = (get_bd_time() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    return render_template_string(
        STORE_ESTIMATE_FORM_TEMPLATE,
        estimate=None,
        index=None,
        customers=customers,
        products=products,
        next_estimate_no=next_no,
        today=today,
        valid_until=valid_until
    )

@app.route('/admin/store/estimates/save', methods=['POST'])
def store_estimate_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    products = load_store_products()
    
    customer_index = int(request.form.get('customer_index', 0))
    customer_name = request.form. get('customer_name', '')
    
    # Parse items
    items = []
    form_data = request.form.to_dict(flat=False)
    
    product_indices = form_data.get('items[][product_index]', [])
    qtys = form_data.get('items[][qty]', [])
    prices = form_data.get('items[][price]', [])
    amounts = form_data.get('items[][amount]', [])
    
    for i in range(len(product_indices)):
        if product_indices[i]:
            prod_idx = int(product_indices[i])
            item = {
                "product_index": prod_idx,
                "product_name": products[prod_idx]['name'] if prod_idx < len(products) else 'Unknown',
                "qty": int(float(qtys[i])) if i < len(qtys) else 1,
                "price": float(prices[i]) if i < len(prices) else 0,
                "amount": float(amounts[i]) if i < len(amounts) else 0
            }
            items.append(item)
    
    new_estimate = {
        "estimate_no": request. form.get('estimate_no', generate_estimate_number()),
        "date": request.form.get('date', get_bd_date_str()),
        "valid_until": request. form.get('valid_until', ''),
        "customer_index": customer_index,
        "customer_name": customer_name,
        "items": items,
        "subtotal": float(request.form.get('subtotal', 0)),
        "discount": float(request.form. get('discount', 0)),
        "total": float(request.form.get('total', 0)),
        "notes": request.form. get('notes', ''),
        "status": "pending",
        "created_at": get_bd_time().isoformat(),
        "created_by": session['user']
    }
    
    estimates.append(new_estimate)
    save_store_estimates(estimates)
    
    flash(f'Estimate {new_estimate["estimate_no"]} created successfully!')
    return redirect(url_for('store_estimates'))

@app.route('/admin/store/estimates/edit/<int:index>')
def store_estimate_edit(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    customers = load_store_customers()
    products = load_store_products()
    
    if index >= len(estimates):
        flash('Estimate not found!')
        return redirect(url_for('store_estimates'))
    
    return render_template_string(
        STORE_ESTIMATE_FORM_TEMPLATE,
        estimate=estimates[index],
        index=index,
        customers=customers,
        products=products,
        next_estimate_no=estimates[index]['estimate_no'],
        today=estimates[index]['date'],
        valid_until=estimates[index]. get('valid_until', '')
    )

@app.route('/admin/store/estimates/update/<int:index>', methods=['POST'])
def store_estimate_update(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    products = load_store_products()
    
    if index >= len(estimates):
        flash('Estimate not found!')
        return redirect(url_for('store_estimates'))
    
    # Parse items
    items = []
    form_data = request.form.to_dict(flat=False)
    
    product_indices = form_data.get('items[][product_index]', [])
    qtys = form_data.get('items[][qty]', [])
    prices = form_data.get('items[][price]', [])
    amounts = form_data. get('items[][amount]', [])
    
    for i in range(len(product_indices)):
        if product_indices[i]:
            prod_idx = int(product_indices[i])
            item = {
                "product_index": prod_idx,
                "product_name": products[prod_idx]['name'] if prod_idx < len(products) else 'Unknown',
                "qty": int(float(qtys[i])) if i < len(qtys) else 1,
                "price": float(prices[i]) if i < len(prices) else 0,
                "amount": float(amounts[i]) if i < len(amounts) else 0
            }
            items.append(item)
    
    estimates[index].update({
        "date": request.form.get('date', get_bd_date_str()),
        "valid_until": request. form.get('valid_until', ''),
        "customer_index": int(request.form.get('customer_index', 0)),
        "customer_name": request.form.get('customer_name', ''),
        "items": items,
        "subtotal": float(request.form. get('subtotal', 0)),
        "discount": float(request.form.get('discount', 0)),
        "total": float(request. form.get('total', 0)),
        "notes": request.form.get('notes', ''),
        "updated_at": get_bd_time().isoformat(),
        "updated_by": session['user']
    })
    
    save_store_estimates(estimates)
    
    flash('Estimate updated successfully!')
    return redirect(url_for('store_estimates'))

@app.route('/admin/store/estimates/delete/<int:index>', methods=['POST'])
def store_estimate_delete(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    
    if index < len(estimates):
        deleted = estimates.pop(index)
        save_store_estimates(estimates)
        flash(f'Estimate {deleted["estimate_no"]} deleted!')
    
    return redirect(url_for('store_estimates'))

# FIXED: Estimate Print Route
@app.route('/admin/store/estimates/print/<int:index>')
def store_estimate_print(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    
    if index >= len(estimates):
        flash('Estimate not found!')
        return redirect(url_for('store_estimates'))
    
    return render_template_string(STORE_ESTIMATE_PRINT_TEMPLATE, estimate=estimates[index], index=index)

# Convert Estimate to Invoice
@app.route('/admin/store/estimates/convert/<int:index>')
def store_estimate_convert(index):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    estimates = load_store_estimates()
    invoices = load_store_invoices()
    customers = load_store_customers()
    
    if index >= len(estimates):
        flash('Estimate not found!')
        return redirect(url_for('store_estimates'))
    
    estimate = estimates[index]
    
    # Create new invoice from estimate
    new_invoice = {
        "invoice_no": generate_invoice_number(),
        "date": get_bd_date_str(),
        "customer_index": estimate. get('customer_index', 0),
        "customer_name": estimate.get('customer_name', ''),
        "items": estimate.get('items', []),
        "subtotal": estimate.get('subtotal', 0),
        "discount": estimate.get('discount', 0),
        "total": estimate. get('total', 0),
        "paid": 0,
        "due": estimate.get('total', 0),
        "notes": f"Converted from {estimate. get('estimate_no', '')}",
        "created_at": get_bd_time().isoformat(),
        "created_by": session['user']
    }
    
    invoices.append(new_invoice)
    save_store_invoices(invoices)
    
    # Update estimate status
    estimates[index]['status'] = 'converted'
    estimates[index]['converted_to'] = new_invoice['invoice_no']
    save_store_estimates(estimates)
    
    # Update customer due
    customer_index = estimate. get('customer_index', 0)
    if customer_index < len(customers):
        customers[customer_index]['due'] = customers[customer_index]. get('due', 0) + new_invoice['due']
        save_store_customers(customers)
    
    flash(f'Estimate converted to Invoice {new_invoice["invoice_no"]}!')
    return redirect(url_for('store_invoices'))

# ==============================================================================
# FLASK ROUTES: STORE PAYMENTS
# ==============================================================================

@app.route('/admin/store/payments')
def store_payments():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    payments = load_store_payments()
    return render_template_string(STORE_PAYMENTS_TEMPLATE, payments=payments)

@app.route('/admin/store/payments/new')
def store_payment_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = load_store_invoices()
    today = get_bd_time().strftime('%Y-%m-%d')
    
    # Get pre-selected invoice if passed
    selected_invoice = request.args.get('invoice', type=int)
    
    return render_template_string(
        STORE_PAYMENT_FORM_TEMPLATE,
        invoices=invoices,
        today=today,
        selected_invoice=selected_invoice
    )

@app.route('/admin/store/payments/save', methods=['POST'])
def store_payment_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    payments = load_store_payments()
    invoices = load_store_invoices()
    customers = load_store_customers()
    
    invoice_index = int(request.form.get('invoice_index', 0))
    amount = float(request. form.get('amount', 0))
    
    if invoice_index >= len(invoices):
        flash('Invoice not found!')
        return redirect(url_for('store_payments'))
    
    invoice = invoices[invoice_index]
    
    # Create payment record
    new_payment = {
        "date": request.form. get('date', get_bd_date_str()),
        "invoice_no": request.form.get('invoice_no', ''),
        "invoice_index": invoice_index,
        "customer_name": request.form. get('customer_name', ''),
        "amount": amount,
        "method": request.form. get('method', 'Cash'),
        "notes": request.form. get('notes', ''),
        "created_at": get_bd_time().isoformat(),
        "created_by": session['user']
    }
    
    payments.append(new_payment)
    save_store_payments(payments)
    
    # Update invoice
    invoices[invoice_index]['paid'] = invoice. get('paid', 0) + amount
    invoices[invoice_index]['due'] = max(0, invoice.get('due', 0) - amount)
    save_store_invoices(invoices)
    
    # Update customer due
    customer_index = invoice.get('customer_index', 0)
    if customer_index < len(customers):
        customers[customer_index]['due'] = max(0, customers[customer_index].get('due', 0) - amount)
        save_store_customers(customers)
    
    flash(f'Payment of ৳{amount:,.0f} recorded successfully!')
    return redirect(url_for('store_payments'))

# ==============================================================================
# FLASK ROUTES: STORE USER MANAGEMENT - FIXED: NEW ROUTES
# ==============================================================================

@app.route('/admin/store/users')
def store_users():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin or store_admin
    if session. get('role') not in ['admin', 'store_admin']:
        flash('Access Denied!  Admin privileges required.')
        return redirect(url_for('store_dashboard'))
    
    users = load_store_users()
    return render_template_string(STORE_USER_MANAGEMENT_TEMPLATE, users=users)

@app. route('/admin/store/users/save', methods=['POST'])
def store_user_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'store_admin']:
        flash('Access Denied!')
        return redirect(url_for('store_dashboard'))
    
    users = load_store_users()
    
    action_type = request.form.get('action_type', 'create')
    username = request.form. get('username', ''). strip()
    password = request.form. get('password', '')
    original_username = request.form. get('original_username', '')
    
    # Collect permissions
    permissions = []
    if request.form.get('perm_products'):
        permissions. append('products')
    if request.form.get('perm_customers'):
        permissions.append('customers')
    if request.form.get('perm_invoices'):
        permissions.append('invoices')
    if request.form.get('perm_estimates'):
        permissions. append('estimates')
    if request.form.get('perm_payments'):
        permissions. append('payments')
    
    if action_type == 'create':
        if username in users:
            flash('Username already exists!')
            return redirect(url_for('store_users'))
        
        users[username] = {
            "password": password,
            "role": "store_user",
            "permissions": permissions,
            "created_at": get_bd_date_str(),
            "last_login": "Never"
        }
        flash(f'User "{username}" created successfully!')
    else:  # update
        if original_username in users:
            users[original_username]['password'] = password
            users[original_username]['permissions'] = permissions
            flash(f'User "{original_username}" updated successfully!')
        else:
            flash('User not found!')
    
    save_store_users(users)
    return redirect(url_for('store_users'))

@app.route('/admin/store/users/delete', methods=['POST'])
def store_user_delete():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') not in ['admin', 'store_admin']:
        flash('Access Denied!')
        return redirect(url_for('store_dashboard'))
    
    users = load_store_users()
    username = request.form. get('username', '')
    
    if username in users and users[username]. get('role') != 'store_admin':
        del users[username]
        save_store_users(users)
        flash(f'User "{username}" deleted!')
    else:
        flash('Cannot delete admin or user not found!')
    
    return redirect(url_for('store_users'))

# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string("""
    <! DOCTYPE html>
    <html>
    <head>
        <title>404 - Page Not Found</title>
        """ + COMMON_STYLES + """
        <style>
            body { justify-content: center; align-items: center; min-height: 100vh; }
            .error-container { text-align: center; padding: 50px; }
            .error-code { font-size: 120px; font-weight: 900; color: var(--accent-orange); opacity: 0.3; }
            . error-message { font-size: 24px; color: white; margin: 20px 0; }
            . error-hint { color: var(--text-secondary); margin-bottom: 30px; }
        </style>
    </head>
    <body>
        <div class="animated-bg"></div>
        <div class="error-container">
            <div class="error-code">404</div>
            <div class="error-message">Page Not Found</div>
            <div class="error-hint">The page you're looking for doesn't exist or has been moved.</div>
            <a href="/">
                <button class="btn-primary" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-home" style="margin-right: 10px;"></i> Go Home
                </button>
            </a>
        </div>
    </body>
    </html>
    """), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>500 - Server Error</title>
        """ + COMMON_STYLES + """
        <style>
            body { justify-content: center; align-items: center; min-height: 100vh; }
            .error-container { text-align: center; padding: 50px; }
            .error-code { font-size: 120px; font-weight: 900; color: var(--accent-red); opacity: 0.3; }
            .error-message { font-size: 24px; color: white; margin: 20px 0; }
            . error-hint { color: var(--text-secondary); margin-bottom: 30px; }
        </style>
    </head>
    <body>
        <div class="animated-bg"></div>
        <div class="error-container">
            <div class="error-code">500</div>
            <div class="error-message">Internal Server Error</div>
            <div class="error-hint">Something went wrong.  Please try again later. </div>
            <a href="/">
                <button class="btn-primary" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-home" style="margin-right: 10px;"></i> Go Home
                </button>
            </a>
        </div>
    </body>
    </html>
    """), 500

# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  MNM SOFTWARE - Production Management System")
    print("  Version: 2.0 (Fixed)")
    print("  Developer: Mehedi Hasan")
    print("=" * 60)
    print("\n  Starting server...")
    print("  Access URL: http://127.0.0. 1:5000")
    print("  Admin Login: Admin / @Nijhum@12")
    print("\n  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(debug=True, host='0.0. 0.0', port=5000)
