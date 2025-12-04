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

    booking_block_match = re.search(r"(?:Internal )?Booking NO\. ? [:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
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
# HTML TEMPLATES: LOGIN PAGE - FIXED RESPONSIVE & CENTERED
# ==============================================================================

LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
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
        .bg-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: orbFloat 20s ease-in-out infinite;
            pointer-events: none;
        }
        
        .orb-1 {
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
        
        .orb-3 {
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
        
        .login-container {
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
        
        .login-card {
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
        
        .brand-icon {
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
        
        .login-form .input-group {
            margin-bottom: 20px;
        }
        
        .login-form .input-group label {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .login-form .input-group label i {
            color: var(--accent-orange);
            font-size: 13px;
        }
        
        .login-form input {
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
        
        .error-box {
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
            opacity: 0.5;
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
            
            .brand-name {
                font-size: 24px;
            }
            
            .brand-tagline {
                font-size: 10px;
            }
            
            .login-form input {
                padding: 12px 16px;
                font-size: 14px;
            }
            
            .login-btn {
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
            
            .brand-icon {
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
        document.querySelector('.login-btn').addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.classList.add('ripple-effect');
            const rect = this.getBoundingClientRect();
            ripple.style.left = (e.clientX - rect.left) + 'px';
            ripple.style.top = (e.clientY - rect.top) + 'px';
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
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

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
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
                <div class="card stat-card" style="animation-delay: 0.1s;">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats.closing.count }}">0</h3>
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
                        <h3 class="count-up" data-target="{{ stats.po.count }}">0</h3>
                        <p>Lifetime PO Sheets</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.4s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));">
                        <i class="fas fa-users" style="color: var(--accent-blue);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{ stats.users.count }}">0</h3>
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
                            <span class="progress-value">{{ stats.accessories.count }} Challans</span>
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
                            <tr style="animation: fadeInUp 0.5s ease-out {{ loop.index * 0.05 }}s backwards;">
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
                                        background: rgba(16, 185, 129, 0.1); color: var(--accent-green);
                                        {% else %}
                                        background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);
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
        
        if (!sessionStorage.getItem('welcomeShown')) {
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
            if (window.innerWidth < 1024) document.querySelector('.sidebar').classList.remove('active');
        }
        
        // ===== FILE UPLOAD HANDLER =====
        const fileUpload = document.getElementById('file-upload');
        const uploadZone = document.getElementById('uploadZone');
        
        if (fileUpload) {
            fileUpload.addEventListener('change', function() {
                const count = this.files.length;
                document.getElementById('file-count').innerHTML = count > 0 
                    ? `<i class="fas fa-check-circle" style="margin-right: 5px;"></i>${count} file(s) selected`
                    : 'No files selected';
            });
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });
            uploadZone.addEventListener('dragleave', () => {
                uploadZone.classList.remove('dragover');
            });
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                fileUpload.files = e.dataTransfer.files;
                fileUpload.dispatchEvent(new Event('change'));
            });
        }
        
        // ===== DEW STYLE DAILY CHART =====
        const ctx = document.getElementById('mainChart').getContext('2d');
        const gradientOrange = ctx.createLinearGradient(0, 0, 0, 300);
        gradientOrange.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
        gradientOrange.addColorStop(1, 'rgba(255, 122, 0, 0.0)');
        const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300);
        gradientPurple.addColorStop(0, 'rgba(139, 92, 246, 0.5)');
        gradientPurple.addColorStop(1, 'rgba(139, 92, 246, 0.0)');
        const gradientGreen = ctx.createLinearGradient(0, 0, 0, 300);
        gradientGreen.addColorStop(0, 'rgba(16, 185, 129, 0.5)');
        gradientGreen.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ stats.chart.labels | tojson }},
                datasets: [
                    {
                        label: 'Closing',
                        data: {{ stats.chart.closing | tojson }},
                        borderColor: '#FF7A00',
                        backgroundColor: gradientOrange,
                        tension: 0.4,
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
                        data: {{ stats.chart.po | tojson }},
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
            document.querySelectorAll('.count-up').forEach(counter => {
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
            const spinner = document.getElementById('spinner-anim').parentElement;
            const success = document.getElementById('success-anim');
            const fail = document.getElementById('fail-anim');
            const text = document.getElementById('loading-text');
            
            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            success.style.display = 'none';
            fail.style.display = 'none';
            text.style.display = 'block';
            text.textContent = 'Processing Request...';
            
            return true;
        }

        function showSuccess() {
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim').parentElement;
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            spinner.style.display = 'none';
            success.style.display = 'block';
            text.style.display = 'none';
            
            setTimeout(() => { overlay.style.display = 'none'; }, 1500);
        }

        // ===== USER MANAGEMENT =====
        function loadUsers() {
            fetch('/admin/get-users')
                .then(res => res.json())
                .then(data => {
                    let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
                    
                    for (const [u, d] of Object.entries(data)) {
                        const roleClass = d.role === 'admin' ? 'background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);' : 'background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);';
                        
                        html += `<tr>
                            <td style="font-weight: 600;">${u}</td>
                            <td><span class="table-badge" style="${roleClass}">${d.role}</span></td>
                            <td style="text-align:right;">
                                ${d.role !== 'admin' ?  `
                                    <div class="action-cell">
                                        <button class="action-btn btn-edit" onclick="editUser('${u}', '${d.password}', '${d.permissions.join(',')}')">
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
            if (document.getElementById('perm_po').checked) perms.push('po_sheet');
            if (document.getElementById('perm_acc').checked) perms.push('accessories');
            
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
                    document.getElementById('loading-overlay').style.display = 'none';
                }
            });
        }
        
        function editUser(u, p, permsStr) {
            document.getElementById('new_username').value = u;
            document.getElementById('new_username').readOnly = true;
            document.getElementById('new_password').value = p;
            document.getElementById('action_type').value = 'update';
            document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-sync" style="margin-right: 10px;"></i> Update User';
            const pArr = permsStr.split(',');
            document.getElementById('perm_closing').checked = pArr.includes('closing');
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
                }).then(() => loadUsers());
            }
        }
        
        // ===== PARTICLES.JS INITIALIZATION =====
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
<!doctype html>
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
        <div class="loading-text">Processing... </div>
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
            {% if 'closing' in session.permissions %}
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
            
            {% if 'po_sheet' in session.permissions %}
            <div class="card" style="animation: fadeInUp 0.5s ease-out 0.2s backwards;">
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
                    <button style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
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
            
            document.getElementById('greetingText').textContent = greeting;
            document.getElementById('welcomeIcon').innerHTML = icon;
            document.getElementById('welcomeModal').style.display = 'flex';
        }
        
        function closeWelcome() {
            const modal = document.getElementById('welcomeModal');
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.style.display = 'none';
                sessionStorage.setItem('welcomeShown', 'true');
            }, 300);
        }
        
        if (!sessionStorage.getItem('welcomeShown')) {
            setTimeout(showWelcomePopup, 500);
        }
        
        function showLoading() {
            document.getElementById('loading-overlay').style.display = 'flex';
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
# ACCESSORIES TEMPLATES
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
        
        .search-header {
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
        
        .search-title {
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
                    <input type="text" name="ref_no" required placeholder="e.g.  IB-12345" autocomplete="off">
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
ACCESSORIES_INPUT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Entry - MNM Software</title>
    """ + COMMON_STYLES + """
    <style>
        .ref-badge {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 122, 0, 0.1);
            border: 1px solid rgba(255, 122, 0, 0.2);
            padding: 10px 20px;
            border-radius: 12px;
            margin-top: 10px;
        }
        
        .ref-badge .ref-no {
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        
        .ref-badge .ref-info {
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
        }
        
        .history-scroll {
            max-height: 500px;
            overflow-y: auto;
            padding-right: 5px;
        }
        
        .challan-row {
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
        
        .line-badge {
            background: var(--gradient-orange);
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            text-align: center;
        }
        
        .qty-value {
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-green);
        }
        
        .status-check {
            color: var(--accent-green);
            font-size: 20px;
        }
        
        .print-btn {
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%) !important;
        }
        
        .empty-state {
            text-align: center;
            padding: 50px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state i {
            font-size: 50px;
            opacity: 0.2;
            margin-bottom: 15px;
        }
        
        .grid-2-cols {
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
            color: white !important;
        }
        
        select option {
            background-color: #1a1a25 !important;
            color: white !important;
            padding: 10px;
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
                <div class="ref-badge">
                    <span class="ref-no">{{ ref }}</span>
                    <span class="ref-info">{{ buyer }} • {{ style }}</span>
                </div>
            </div>
            <a href="/admin/accessories/print?ref={{ ref }}" target="_blank">
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
                            <input type="text" name="line_no" required placeholder="e.g.  L-01">
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
                        {% for item in challans|reverse %}
                        <div class="challan-row" style="animation: fadeInUp 0.3s ease-out {{ loop.index * 0.05 }}s backwards;">
                            <div class="line-badge">{{ item.line }}</div>
                            <div style="color: white; font-weight: 500; font-size: 13px;">{{ item.color }}</div>
                            <div class="qty-value">{{ item.qty }}</div>
                            <div class="status-check">{{ item.status if item.status else '●' }}</div>
                            <div class="action-cell">
                                {% if session.role == 'admin' %}
                                <a href="/admin/accessories/edit?ref={{ ref }}&index={{ (challans|length) - loop.index }}" class="action-btn btn-edit">
                                    <i class="fas fa-pen"></i>
                                </a>
                                <form action="/admin/accessories/delete" method="POST" style="display: inline;" onsubmit="return confirm('Delete this entry?');">
                                    <input type="hidden" name="ref" value="{{ ref }}">
                                    <input type="hidden" name="index" value="{{ (challans|length) - loop.index }}">
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
            const spinner = document.getElementById('spinner-anim').parentElement;
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            overlay.style.display = 'flex';
            spinner.style.display = 'block';
            success.style.display = 'none';
            text.style.display = 'block';
            text.textContent = 'Saving Entry...';
            
            return true;
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
            animation: cardAppear 0.5s ease-out;
        }
        
        @keyframes cardAppear {
            from { opacity: 0; transform: scale(0.95); }
            to { opacity: 1; transform: scale(1); }
        }
        
        .edit-header {
            text-align: center;
            margin-bottom: 35px;
        }
        
        .edit-icon {
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
                    <input type="text" name="size" value="{{ item.size }}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sort-numeric-up" style="margin-right: 5px;"></i> QUANTITY</label>
                    <input type="number" name="qty" value="{{ item.qty }}" required>
                </div>
                
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync-alt" style="margin-right: 10px;"></i> Update Entry
                </button>
            </form>
            
            <a href="/admin/accessories/input_direct?ref={{ ref }}" class="cancel-link">
                <i class="fas fa-times" style="margin-right: 5px;"></i> Cancel
            </a>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE DASHBOARD TEMPLATE - FUNCTIONAL (ALUMINUM SHOP)
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
    <style>
        .store-header {
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
        }
        
        .store-brand {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .store-brand-icon {
            width: 60px;
            height: 60px;
            background: var(--gradient-orange);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            color: white;
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }
        
        .store-brand-text h1 {
            font-size: 22px;
            font-weight: 800;
            color: white;
            margin: 0;
            line-height: 1.2;
        }
        
        .store-brand-text p {
            font-size: 12px;
            color: var(--text-secondary);
            margin: 5px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .store-stats {
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }
        
        .store-stat-item {
            text-align: center;
        }
        
        .store-stat-value {
            font-size: 28px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        
        .store-stat-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .quick-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .quick-action-btn {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            cursor: pointer;
            transition: var(--transition-smooth);
            text-decoration: none;
            display: block;
        }
        
        .quick-action-btn:hover {
            border-color: var(--accent-orange);
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(255, 122, 0, 0.15);
        }
        
        .quick-action-btn i {
            font-size: 32px;
            margin-bottom: 15px;
            display: block;
        }
        
        .quick-action-btn span {
            font-size: 14px;
            font-weight: 600;
            color: white;
        }
        
        .qa-orange i { color: var(--accent-orange); }
        .qa-green i { color: var(--accent-green); }
        .qa-purple i { color: var(--accent-purple); }
        .qa-blue i { color: var(--accent-blue); }
        .qa-cyan i { color: var(--accent-cyan); }
        .qa-red i { color: var(--accent-red); }
        
        .data-section {
            margin-top: 30px;
        }
        
        .section-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .section-tab {
            padding: 12px 24px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .section-tab:hover {
            border-color: var(--accent-orange);
            color: var(--accent-orange);
        }
        
        .section-tab.active {
            background: var(--accent-orange);
            border-color: var(--accent-orange);
            color: white;
        }
        
        .tab-panel {
            display: none;
        }
        
        .tab-panel.active {
            display: block;
            animation: fadeIn 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        
        .product-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 20px;
            transition: var(--transition-smooth);
        }
        
        .product-card:hover {
            border-color: var(--accent-orange);
            transform: translateY(-3px);
        }
        
        .product-name {
            font-size: 16px;
            font-weight: 700;
            color: white;
            margin-bottom: 8px;
        }
        
        .product-details {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 15px;
        }
        
        .product-price {
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-green);
        }
        
        .product-actions {
            display: flex;
            gap: 8px;
            margin-top: 15px;
        }
        
        .due-card {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 16px;
            padding: 20px;
        }
        
        .due-amount {
            font-size: 24px;
            font-weight: 800;
            color: var(--accent-red);
        }
        
        .invoice-row {
            display: grid;
            grid-template-columns: 100px 1fr 120px 120px 100px;
            gap: 15px;
            padding: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 10px;
            align-items: center;
            transition: var(--transition-smooth);
        }
        
        .invoice-row:hover {
            background: rgba(255, 122, 0, 0.05);
        }
        
        @media (max-width: 768px) {
            .invoice-row {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            
            .store-header {
                flex-direction: column;
                text-align: center;
            }
            
            .store-stats {
                justify-content: center;
            }
        }
    </style>
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
            <div class="anim-text">Success!</div>
        </div>
        <div class="loading-text" id="loading-text">Processing...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <div class="nav-link active">
                <i class="fas fa-th-large"></i> Dashboard
            </div>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/store/users" class="nav-link">
                <i class="fas fa-user-cog"></i> Store Users
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
        <div class="store-header">
            <div class="store-brand">
                <div class="store-brand-icon">
                    <i class="fas fa-store-alt"></i>
                </div>
                <div class="store-brand-text">
                    <h1>MEHEDI THAI ALUMINUM AND GLASS</h1>
                    <p>Store Management System</p>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>
        </div>

        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon"><i class="fas fa-box"></i></div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ store_stats.products_count }}">0</h3>
                    <p>Total Products</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                    <i class="fas fa-users" style="color: var(--accent-purple);"></i>
                </div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ store_stats.customers_count }}">0</h3>
                    <p>Customers</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-file-invoice" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info">
                    <h3 class="count-up" data-target="{{ store_stats.invoices_count }}">0</h3>
                    <p>Total Invoices</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));">
                    <i class="fas fa-hand-holding-usd" style="color: var(--accent-red);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{ "{:,.0f}".format(store_stats.total_due) }}</h3>
                    <p>Total Due</p>
                </div>
            </div>
        </div>

        <div class="quick-actions">
            <a href="/store/products/add" class="quick-action-btn qa-orange">
                <i class="fas fa-plus-circle"></i>
                <span>Add Product</span>
            </a>
            <a href="/store/customers/add" class="quick-action-btn qa-purple">
                <i class="fas fa-user-plus"></i>
                <span>Add Customer</span>
            </a>
            <a href="/store/invoices/create" class="quick-action-btn qa-green">
                <i class="fas fa-file-invoice-dollar"></i>
                <span>Create Invoice</span>
            </a>
            <a href="/store/estimates/create" class="quick-action-btn qa-blue">
                <i class="fas fa-file-alt"></i>
                <span>Create Estimate</span>
            </a>
            <a href="/store/dues" class="quick-action-btn qa-red">
                <i class="fas fa-money-bill-wave"></i>
                <span>Collect Due</span>
            </a>
            <a href="/store/invoices" class="quick-action-btn qa-cyan">
                <i class="fas fa-search"></i>
                <span>Search Invoice</span>
            </a>
        </div>

        <div class="card">
            <div class="section-header">
                <span><i class="fas fa-chart-line" style="margin-right: 10px; color: var(--accent-orange);"></i>Quick Overview</span>
            </div>
            
            <div class="section-tabs">
                <div class="section-tab active" onclick="showTab('recent-invoices', this)">Recent Invoices</div>
                <div class="section-tab" onclick="showTab('recent-estimates', this)">Recent Estimates</div>
                <div class="section-tab" onclick="showTab('pending-dues', this)">Pending Dues</div>
            </div>
            
            <div id="tab-recent-invoices" class="tab-panel active">
                {% if recent_invoices %}
                    {% for inv in recent_invoices[:5] %}
                    <div class="invoice-row">
                        <div style="font-weight: 700; color: var(--accent-orange);">{{ inv.invoice_no }}</div>
                        <div style="color: white;">{{ inv.customer_name }}</div>
                        <div style="color: var(--text-secondary);">{{ inv.date }}</div>
                        <div style="font-weight: 700; color: var(--accent-green);">৳{{ "{:,.0f}".format(inv.total) }}</div>
                        <div>
                            <a href="/store/invoices/view/{{ inv.invoice_no }}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            <a href="/store/invoices/print/{{ inv.invoice_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <i class="fas fa-file-invoice"></i>
                        <p>No invoices yet. Create your first invoice!</p>
                    </div>
                {% endif %}
            </div>
            
            <div id="tab-recent-estimates" class="tab-panel">
                {% if recent_estimates %}
                    {% for est in recent_estimates[:5] %}
                    <div class="invoice-row">
                        <div style="font-weight: 700; color: var(--accent-blue);">{{ est.estimate_no }}</div>
                        <div style="color: white;">{{ est.customer_name }}</div>
                        <div style="color: var(--text-secondary);">{{ est.date }}</div>
                        <div style="font-weight: 700; color: var(--accent-purple);">৳{{ "{:,.0f}".format(est.total) }}</div>
                        <div>
                            <a href="/store/estimates/view/{{ est.estimate_no }}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            <a href="/store/estimates/print/{{ est.estimate_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <i class="fas fa-file-alt"></i>
                        <p>No estimates yet. Create quotations for your customers!</p>
                    </div>
                {% endif %}
            </div>
            
            <div id="tab-pending-dues" class="tab-panel">
                {% if pending_dues %}
                    {% for due in pending_dues[:5] %}
                    <div class="invoice-row" style="border-left: 3px solid var(--accent-red);">
                        <div style="font-weight: 700; color: var(--accent-orange);">{{ due.invoice_no }}</div>
                        <div style="color: white;">{{ due.customer_name }}</div>
                        <div style="color: var(--text-secondary);">{{ due.date }}</div>
                        <div style="font-weight: 700; color: var(--accent-red);">৳{{ "{:,.0f}".format(due.due) }} Due</div>
                        <div>
                            <a href="/store/dues/collect/{{ due.invoice_no }}" class="action-btn btn-edit"><i class="fas fa-money-bill"></i></a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <i class="fas fa-check-circle" style="color: var(--accent-green);"></i>
                        <p>No pending dues!  All payments collected.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function showTab(tabId, element) {
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.section-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            element.classList.add('active');
        }
        
        // Count up animation
        function animateCountUp() {
            document.querySelectorAll('.count-up').forEach(counter => {
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
        
        // Mobile sidebar
        if (window.innerWidth < 1024) {
            document.querySelector('.sidebar').classList.remove('active');
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE PRODUCT ADD/LIST TEMPLATE
# ==============================================================================

STORE_PRODUCTS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - MEHEDI THAI ALUMINUM AND GLASS</title>
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
            <div class="anim-text">Saved! </div>
        </div>
        <div class="loading-text">Processing... </div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <div class="nav-link active">
                <i class="fas fa-box"></i> Products
            </div>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Product Management</div>
                <div class="page-subtitle">Add and manage aluminum & glass products</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
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
                    <span><i class="fas fa-plus-circle" style="margin-right: 10px; color: var(--accent-orange);"></i>Add New Product</span>
                </div>
                <form action="/store/products/save" method="post" onsubmit="showLoading()">
                    <div class="input-group">
                        <label><i class="fas fa-cube" style="margin-right: 5px;"></i> PRODUCT NAME</label>
                        <input type="text" name="name" required placeholder="e.g.  Thai Glass 5mm">
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> SIZE (FEET)</label>
                            <input type="text" name="size_feet" placeholder="e.g.  4x6 or 3x4">
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-layer-group" style="margin-right: 5px;"></i> THICKNESS</label>
                            <input type="text" name="thickness" placeholder="e.g. 5mm, 8mm">
                        </div>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label><i class="fas fa-tag" style="margin-right: 5px;"></i> CATEGORY</label>
                            <select name="category">
                                <option value="Glass">Glass</option>
                                <option value="Aluminum Profile">Aluminum Profile</option>
                                <option value="Thai Aluminum">Thai Aluminum</option>
                                <option value="Accessories">Accessories</option>
                                <option value="Mirror">Mirror</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label><i class="fas fa-money-bill" style="margin-right: 5px;"></i> PRICE (Optional)</label>
                            <input type="number" name="price" placeholder="৳ Per Unit" step="0.01">
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-info-circle" style="margin-right: 5px;"></i> DESCRIPTION (Optional)</label>
                        <textarea name="description" placeholder="Additional details about the product... "></textarea>
                    </div>
                    
                    <button type="submit">
                        <i class="fas fa-save" style="margin-right: 10px;"></i> Save Product
                    </button>
                </form>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Product List</span>
                    <span class="table-badge" style="background: var(--accent-orange); color: white;">{{ products|length }} Items</span>
                </div>
                
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="productSearch" placeholder="Search products..." onkeyup="filterProducts()">
                </div>
                
                <div style="max-height: 500px; overflow-y: auto;" id="productList">
                    {% if products %}
                        {% for p in products|reverse %}
                        <div class="product-item" style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border: 1px solid var(--border-color);">
                            <div>
                                <div style="font-weight: 700; color: white; margin-bottom: 5px;">{{ p.name }}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">
                                    {% if p.size_feet %}{{ p.size_feet }} ft | {% endif %}
                                    {% if p.thickness %}{{ p.thickness }} | {% endif %}
                                    {{ p.category }}
                                </div>
                            </div>
                            <div style="text-align: right;">
                                {% if p.price %}
                                <div style="font-weight: 800; color: var(--accent-green); font-size: 18px;">৳{{ p.price }}</div>
                                {% else %}
                                <div style="color: var(--text-secondary); font-size: 12px;">No price set</div>
                                {% endif %}
                                <div class="action-cell" style="margin-top: 8px;">
                                    <a href="/store/products/edit/{{ loop.index0 }}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                    <form action="/store/products/delete/{{ loop.index0 }}" method="post" style="display:inline;" onsubmit="return confirm('Delete this product?');">
                                        <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                    </form>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state">
                            <i class="fas fa-box-open"></i>
                            <p>No products added yet</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showLoading() {
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
        
        function filterProducts() {
            const search = document.getElementById('productSearch').value.toLowerCase();
            document.querySelectorAll('.product-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(search) ?  'flex' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMERS TEMPLATE
# ==============================================================================

STORE_CUSTOMERS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Processing... </div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <div class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </div>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Customer Management</div>
                <div class="page-subtitle">Add and manage your customers</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
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
                    <span><i class="fas fa-user-plus" style="margin-right: 10px; color: var(--accent-purple);"></i>Add New Customer</span>
                </div>
                <form action="/store/customers/save" method="post" onsubmit="showLoading()">
                    <div class="input-group">
                        <label><i class="fas fa-user" style="margin-right: 5px;"></i> CUSTOMER NAME</label>
                        <input type="text" name="name" required placeholder="Full Name">
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-phone" style="margin-right: 5px;"></i> PHONE NUMBER</label>
                        <input type="text" name="phone" required placeholder="01XXXXXXXXX">
                    </div>
                    
                    <div class="input-group">
                        <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> ADDRESS</label>
                        <textarea name="address" placeholder="Full Address (Optional)"></textarea>
                    </div>
                    
                    <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-save" style="margin-right: 10px;"></i> Save Customer
                    </button>
                </form>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Customer List</span>
                    <span class="table-badge" style="background: var(--accent-purple); color: white;">{{ customers|length }} Customers</span>
                </div>
                
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="customerSearch" placeholder="Search customers..." onkeyup="filterCustomers()">
                </div>
                
                <div style="max-height: 500px; overflow-y: auto;" id="customerList">
                    {% if customers %}
                        {% for c in customers|reverse %}
                        <div class="customer-item" style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border: 1px solid var(--border-color);">
                            <div>
                                <div style="font-weight: 700; color: white; margin-bottom: 5px;">{{ c.name }}</div>
                                <div style="font-size: 13px; color: var(--accent-orange);">
                                    <i class="fas fa-phone" style="margin-right: 5px;"></i>{{ c.phone }}
                                </div>
                                {% if c.address %}
                                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 3px;">
                                    <i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i>{{ c.address[:50] }}... 
                                </div>
                                {% endif %}
                            </div>
                            <div class="action-cell">
                                <a href="/store/customers/edit/{{ loop.index0 }}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                <form action="/store/customers/delete/{{ loop.index0 }}" method="post" style="display:inline;" onsubmit="return confirm('Delete this customer?');">
                                    <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                </form>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state">
                            <i class="fas fa-users"></i>
                            <p>No customers added yet</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showLoading() {
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
        
        function filterCustomers() {
            const search = document.getElementById('customerSearch').value.toLowerCase();
            document.querySelectorAll('.customer-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(search) ? 'flex' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE CREATE TEMPLATE
# ==============================================================================

STORE_INVOICE_CREATE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create Invoice - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
    <style>
        .invoice-items-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .invoice-items-table th {
            background: rgba(255, 122, 0, 0.1);
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--accent-orange);
            border-bottom: 1px solid var(--border-color);
        }
        
        .invoice-items-table td {
            padding: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .invoice-items-table input, .invoice-items-table select {
            padding: 10px;
            font-size: 14px;
        }
        
        .item-row {
            transition: var(--transition-smooth);
        }
        
        .item-row:hover {
            background: rgba(255, 122, 0, 0.03);
        }
        
        .add-item-btn {
            background: rgba(16, 185, 129, 0.1);
            border: 1px dashed var(--accent-green);
            color: var(--accent-green);
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: var(--transition-smooth);
            width: 100%;
            margin-top: 15px;
        }
        
        .add-item-btn:hover {
            background: var(--accent-green);
            color: white;
        }
        
        .remove-item-btn {
            background: rgba(239, 68, 68, 0.1);
            border: none;
            color: var(--accent-red);
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .remove-item-btn:hover {
            background: var(--accent-red);
            color: white;
        }
        
        .totals-section {
            background: rgba(255, 255, 255, 0.03);
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
            color: var(--accent-green);
        }
        
        .total-label {
            color: var(--text-secondary);
        }
        
        .total-value {
            font-weight: 700;
            color: white;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Creating Invoice...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </div>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create Invoice</div>
                <div class="page-subtitle">Invoice No: <span style="color: var(--accent-orange); font-weight: 700;">{{ invoice_no }}</span></div>
            </div>
            <a href="/store/invoices" class="btn-secondary" style="padding: 12px 24px; border-radius: 10px; text-decoration: none; color: var(--text-secondary);">
                <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
            </a>
        </div>

        <form action="/store/invoices/save" method="post" onsubmit="return validateAndSubmit()">
            <input type="hidden" name="invoice_no" value="{{ invoice_no }}">
            
            <div class="grid-2" style="margin-bottom: 30px;">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Info</span>
                    </div>
                    
                    <div class="input-group">
                        <label>SELECT CUSTOMER</label>
                        <select name="customer_id" id="customerSelect" onchange="fillCustomerInfo()">
                            <option value="">-- Select Existing Customer --</option>
                            {% for c in customers %}
                            <option value="{{ loop.index0 }}" data-name="{{ c.name }}" data-phone="{{ c.phone }}" data-address="{{ c.address }}">{{ c.name }} - {{ c.phone }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="input-group">
                        <label>CUSTOMER NAME</label>
                        <input type="text" name="customer_name" id="customerName" required placeholder="Customer Name">
                    </div>
                    
                    <div class="input-group">
                        <label>PHONE</label>
                        <input type="text" name="customer_phone" id="customerPhone" placeholder="Phone Number">
                    </div>
                    
                    <div class="input-group">
                        <label>ADDRESS</label>
                        <textarea name="customer_address" id="customerAddress" placeholder="Address"></textarea>
                    </div>
                </div>
                
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calendar" style="margin-right: 10px; color: var(--accent-blue);"></i>Invoice Details</span>
                    </div>
                    
                    <div class="input-group">
                        <label>INVOICE DATE</label>
                        <input type="date" name="invoice_date" value="{{ today }}" required>
                    </div>
                    
                    <div class="input-group">
                        <label>NOTES (Optional)</label>
                        <textarea name="notes" placeholder="Any additional notes..."></textarea>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-green);"></i>Invoice Items</span>
                </div>
                
                <div style="overflow-x: auto;">
                    <table class="invoice-items-table">
                        <thead>
                            <tr>
                                <th style="width: 30%;">Product/Description</th>
                                <th style="width: 15%;">Size (ft)</th>
                                <th style="width: 12%;">Quantity</th>
                                <th style="width: 15%;">Unit Price</th>
                                <th style="width: 18%;">Total</th>
                                <th style="width: 10%;"></th>
                            </tr>
                        </thead>
                        <tbody id="itemsBody">
                            <tr class="item-row">
                                <td>
                                    <input type="text" name="items[0][description]" placeholder="Product name" required>
                                </td>
                                <td>
                                    <input type="text" name="items[0][size]" placeholder="e.g.  4x6">
                                </td>
                                <td>
                                    <input type="number" name="items[0][qty]" class="item-qty" value="1" min="1" onchange="calculateRow(this)" required>
                                </td>
                                <td>
                                    <input type="number" name="items[0][price]" class="item-price" placeholder="৳" step="0.01" onchange="calculateRow(this)" required>
                                </td>
                                <td>
                                    <input type="number" name="items[0][total]" class="item-total" readonly placeholder="৳ 0">
                                </td>
                                <td>
                                    <button type="button" class="remove-item-btn" onclick="removeRow(this)"><i class="fas fa-times"></i></button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <button type="button" class="add-item-btn" onclick="addItemRow()">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Another Item
                </button>
                
                <div class="totals-section">
                    <div class="total-row">
                        <span class="total-label">Subtotal</span>
                        <span class="total-value" id="subtotal">৳ 0</span>
                    </div>
                    <div class="total-row">
                        <span class="total-label">Discount</span>
                        <input type="number" name="discount" id="discountInput" value="0" min="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                    </div>
                    <div class="total-row">
                        <span class="total-label">Paid Amount</span>
                        <input type="number" name="paid" id="paidInput" value="0" min="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                    </div>
                    <div class="total-row" style="background: rgba(239, 68, 68, 0.1); margin: 10px -20px -20px -20px; padding: 15px 20px; border-radius: 0 0 12px 12px;">
                        <span style="color: var(--accent-red);">Due Amount</span>
                        <span style="color: var(--accent-red);" id="dueAmount">৳ 0</span>
                    </div>
                    <input type="hidden" name="total" id="totalInput">
                    <input type="hidden" name="due" id="dueInput">
                </div>
            </div>
            
            <div style="margin-top: 30px; display: flex; gap: 15px; justify-content: flex-end;">
                <button type="submit" name="action" value="save" style="width: auto; padding: 15px 40px;">
                    <i class="fas fa-save" style="margin-right: 10px;"></i> Save Invoice
                </button>
                <button type="submit" name="action" value="save_print" style="width: auto; padding: 15px 40px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                    <i class="fas fa-print" style="margin-right: 10px;"></i> Save & Print
                </button>
            </div>
        </form>
    </div>
    
    <script>
        let itemIndex = 1;
        
        function fillCustomerInfo() {
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            if (option.value) {
                document.getElementById('customerName').value = option.dataset.name || '';
                document.getElementById('customerPhone').value = option.dataset.phone || '';
                document.getElementById('customerAddress').value = option.dataset.address || '';
            }
        }
        
        function addItemRow() {
            const tbody = document.getElementById('itemsBody');
            const row = document.createElement('tr');
            row.className = 'item-row';
            row.innerHTML = `
                <td><input type="text" name="items[${itemIndex}][description]" placeholder="Product name" required></td>
                <td><input type="text" name="items[${itemIndex}][size]" placeholder="e.g. 4x6"></td>
                <td><input type="number" name="items[${itemIndex}][qty]" class="item-qty" value="1" min="1" onchange="calculateRow(this)" required></td>
                <td><input type="number" name="items[${itemIndex}][price]" class="item-price" placeholder="৳" step="0.01" onchange="calculateRow(this)" required></td>
                <td><input type="number" name="items[${itemIndex}][total]" class="item-total" readonly placeholder="৳ 0"></td>
                <td><button type="button" class="remove-item-btn" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
            `;
            tbody.appendChild(row);
            itemIndex++;
        }
        
        function removeRow(btn) {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length > 1) {
                btn.closest('tr').remove();
                calculateTotals();
            }
        }
        
        function calculateRow(input) {
            const row = input.closest('tr');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const price = parseFloat(row.querySelector('.item-price').value) || 0;
            const total = qty * price;
            row.querySelector('.item-total').value = total.toFixed(2);
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('.item-total').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const paid = parseFloat(document.getElementById('paidInput').value) || 0;
            const grandTotal = subtotal - discount;
            const due = grandTotal - paid;
            
            document.getElementById('subtotal').textContent = '৳ ' + subtotal.toFixed(2);
            document.getElementById('dueAmount').textContent = '৳ ' + due.toFixed(2);
            document.getElementById('totalInput').value = grandTotal.toFixed(2);
            document.getElementById('dueInput').value = due.toFixed(2);
        }
        
        function validateAndSubmit() {
            calculateTotals();
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
        
        function showLoading() {
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATE CREATE TEMPLATE
# ==============================================================================

STORE_ESTIMATE_CREATE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create Estimate - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
    <style>
        .invoice-items-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .invoice-items-table th {
            background: rgba(59, 130, 246, 0.1);
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--accent-blue);
            border-bottom: 1px solid var(--border-color);
        }
        
        .invoice-items-table td {
            padding: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .invoice-items-table input, .invoice-items-table select {
            padding: 10px;
            font-size: 14px;
        }
        
        .item-row {
            transition: var(--transition-smooth);
        }
        
        .item-row:hover {
            background: rgba(59, 130, 246, 0.03);
        }
        
        .add-item-btn {
            background: rgba(59, 130, 246, 0.1);
            border: 1px dashed var(--accent-blue);
            color: var(--accent-blue);
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            transition: var(--transition-smooth);
            width: 100%;
            margin-top: 15px;
        }
        
        .add-item-btn:hover {
            background: var(--accent-blue);
            color: white;
        }
        
        .remove-item-btn {
            background: rgba(239, 68, 68, 0.1);
            border: none;
            color: var(--accent-red);
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .remove-item-btn:hover {
            background: var(--accent-red);
            color: white;
        }
        
        .totals-section {
            background: rgba(255, 255, 255, 0.03);
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
            color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.1);
            margin: 10px -20px -20px -20px;
            padding: 15px 20px;
            border-radius: 0 0 12px 12px;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Creating Estimate...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-alt"></i> Estimates
            </div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create Estimate / Quotation</div>
                <div class="page-subtitle">Estimate No: <span style="color: var(--accent-blue); font-weight: 700;">{{ estimate_no }}</span></div>
            </div>
            <a href="/store/estimates" style="padding: 12px 24px; border-radius: 10px; text-decoration: none; color: var(--text-secondary); background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back
            </a>
        </div>

        <form action="/store/estimates/save" method="post" onsubmit="return validateAndSubmit()">
            <input type="hidden" name="estimate_no" value="{{ estimate_no }}">
            
            <div class="grid-2" style="margin-bottom: 30px;">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Info</span>
                    </div>
                    
                    <div class="input-group">
                        <label>CUSTOMER NAME</label>
                        <input type="text" name="customer_name" id="customerName" required placeholder="Customer Name">
                    </div>
                    
                    <div class="input-group">
                        <label>PHONE</label>
                        <input type="text" name="customer_phone" id="customerPhone" placeholder="Phone Number">
                    </div>
                    
                    <div class="input-group">
                        <label>ADDRESS</label>
                        <textarea name="customer_address" id="customerAddress" placeholder="Address"></textarea>
                    </div>
                </div>
                
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calendar" style="margin-right: 10px; color: var(--accent-blue);"></i>Estimate Details</span>
                    </div>
                    
                    <div class="input-group">
                        <label>ESTIMATE DATE</label>
                        <input type="date" name="estimate_date" value="{{ today }}" required>
                    </div>
                    
                    <div class="input-group">
                        <label>VALID UNTIL (Optional)</label>
                        <input type="date" name="valid_until">
                    </div>
                    
                    <div class="input-group">
                        <label>NOTES / TERMS</label>
                        <textarea name="notes" placeholder="Terms & Conditions..."></textarea>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-blue);"></i>Estimate Items</span>
                </div>
                
                <div style="overflow-x: auto;">
                    <table class="invoice-items-table">
                        <thead>
                            <tr>
                                <th style="width: 30%;">Product/Description</th>
                                <th style="width: 15%;">Size (ft)</th>
                                <th style="width: 12%;">Quantity</th>
                                <th style="width: 15%;">Unit Price</th>
                                <th style="width: 18%;">Total</th>
                                <th style="width: 10%;"></th>
                            </tr>
                        </thead>
                        <tbody id="itemsBody">
                            <tr class="item-row">
                                <td><input type="text" name="items[0][description]" placeholder="Product/Work description" required></td>
                                <td><input type="text" name="items[0][size]" placeholder="e.g.  4x6"></td>
                                <td><input type="number" name="items[0][qty]" class="item-qty" value="1" min="1" onchange="calculateRow(this)" required></td>
                                <td><input type="number" name="items[0][price]" class="item-price" placeholder="৳" step="0.01" onchange="calculateRow(this)" required></td>
                                <td><input type="number" name="items[0][total]" class="item-total" readonly placeholder="৳ 0"></td>
                                <td><button type="button" class="remove-item-btn" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <button type="button" class="add-item-btn" onclick="addItemRow()">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Another Item
                </button>
                
                <div class="totals-section">
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Subtotal</span>
                        <span style="font-weight: 700; color: white;" id="subtotal">৳ 0</span>
                    </div>
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Discount</span>
                        <input type="number" name="discount" id="discountInput" value="0" min="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotals()">
                    </div>
                    <div class="total-row">
                        <span>Estimated Total</span>
                        <span id="grandTotal">৳ 0</span>
                    </div>
                    <input type="hidden" name="total" id="totalInput">
                </div>
            </div>
            
            <div style="margin-top: 30px; display: flex; gap: 15px; justify-content: flex-end;">
                <button type="submit" name="action" value="save" style="width: auto; padding: 15px 40px; background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);">
                    <i class="fas fa-save" style="margin-right: 10px;"></i> Save Estimate
                </button>
                <button type="submit" name="action" value="save_print" style="width: auto; padding: 15px 40px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                    <i class="fas fa-print" style="margin-right: 10px;"></i> Save & Print
                </button>
            </div>
        </form>
    </div>
    
    <script>
        let itemIndex = 1;
        
        function addItemRow() {
            const tbody = document.getElementById('itemsBody');
            const row = document.createElement('tr');
            row.className = 'item-row';
            row.innerHTML = `
                <td><input type="text" name="items[${itemIndex}][description]" placeholder="Product/Work description" required></td>
                <td><input type="text" name="items[${itemIndex}][size]" placeholder="e.g. 4x6"></td>
                <td><input type="number" name="items[${itemIndex}][qty]" class="item-qty" value="1" min="1" onchange="calculateRow(this)" required></td>
                <td><input type="number" name="items[${itemIndex}][price]" class="item-price" placeholder="৳" step="0.01" onchange="calculateRow(this)" required></td>
                <td><input type="number" name="items[${itemIndex}][total]" class="item-total" readonly placeholder="৳ 0"></td>
                <td><button type="button" class="remove-item-btn" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
            `;
            tbody.appendChild(row);
            itemIndex++;
        }
        
        function removeRow(btn) {
            const rows = document.querySelectorAll('.item-row');
            if (rows.length > 1) {
                btn.closest('tr').remove();
                calculateTotals();
            }
        }
        
        function calculateRow(input) {
            const row = input.closest('tr');
            const qty = parseFloat(row.querySelector('.item-qty').value) || 0;
            const price = parseFloat(row.querySelector('.item-price').value) || 0;
            const total = qty * price;
            row.querySelector('.item-total').value = total.toFixed(2);
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('.item-total').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            
            document.getElementById('subtotal').textContent = '৳ ' + subtotal.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳ ' + grandTotal.toFixed(2);
            document.getElementById('totalInput').value = grandTotal.toFixed(2);
        }
        
        function validateAndSubmit() {
            calculateTotals();
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE DUE COLLECTION TEMPLATE
# ==============================================================================

STORE_DUE_COLLECTION_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due Collection - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
    <style>
        .due-card {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
        }
        
        .due-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .due-invoice-no {
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        
        .due-amount {
            font-size: 24px;
            font-weight: 800;
            color: var(--accent-red);
        }
        
        .due-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .due-detail-item {
            background: rgba(255, 255, 255, 0.03);
            padding: 12px;
            border-radius: 10px;
        }
        
        .due-detail-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        
        .due-detail-value {
            font-size: 15px;
            font-weight: 600;
            color: white;
        }
        
        .payment-form {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 12px;
            padding: 20px;
        }
        
        .payment-history {
            margin-top: 20px;
        }
        
        .payment-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .payment-date {
            color: var(--text-secondary);
            font-size: 13px;
        }
        
        .payment-amount {
            font-weight: 700;
            color: var(--accent-green);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Processing Payment...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <div class="nav-link active">
                <i class="fas fa-wallet"></i> Due Collection
            </div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Due Collection</div>
                <div class="page-subtitle">Manage pending payments</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
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

        <div class="card" style="margin-bottom: 30px;">
            <div class="section-header">
                <span><i class="fas fa-search" style="margin-right: 10px; color: var(--accent-orange);"></i>Search Invoice</span>
            </div>
            <form action="/store/dues/search" method="get" style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px;">
                    <input type="text" name="invoice_no" placeholder="Enter Invoice Number (e.g.  INV-0001)" value="{{ search_invoice }}">
                </div>
                <button type="submit" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-search" style="margin-right: 8px;"></i> Search
                </button>
            </form>
        </div>

        {% if invoice %}
        <div class="due-card">
            <div class="due-header">
                <div class="due-invoice-no">{{ invoice.invoice_no }}</div>
                <div class="due-amount">Due: ৳{{ "{:,.0f}".format(invoice.due) }}</div>
            </div>
            
            <div class="due-details">
                <div class="due-detail-item">
                    <div class="due-detail-label">Customer</div>
                    <div class="due-detail-value">{{ invoice.customer_name }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Phone</div>
                    <div class="due-detail-value">{{ invoice.customer_phone }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Invoice Date</div>
                    <div class="due-detail-value">{{ invoice.date }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Total Amount</div>
                    <div class="due-detail-value">৳{{ "{:,.0f}".format(invoice.total) }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Already Paid</div>
                    <div class="due-detail-value" style="color: var(--accent-green);">৳{{ "{:,.0f}".format(invoice.paid) }}</div>
                </div>
            </div>
            
            {% if invoice.due > 0 %}
            <div class="payment-form">
                <h4 style="margin-bottom: 15px; color: var(--accent-green);"><i class="fas fa-money-bill-wave" style="margin-right: 10px;"></i>Record Payment</h4>
                <form action="/store/dues/collect" method="post" onsubmit="return validatePayment()">
                    <input type="hidden" name="invoice_no" value="{{ invoice.invoice_no }}">
                    <div class="grid-2">
                        <div class="input-group">
                            <label>PAYMENT AMOUNT</label>
                            <input type="number" name="amount" id="paymentAmount" required placeholder="৳" step="0.01" max="{{ invoice.due }}">
                        </div>
                        <div class="input-group">
                            <label>PAYMENT DATE</label>
                            <input type="date" name="payment_date" value="{{ today }}" required>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>NOTES (Optional)</label>
                        <input type="text" name="notes" placeholder="Payment notes... ">
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-check" style="margin-right: 10px;"></i> Record Payment
                    </button>
                </form>
            </div>
            {% else %}
            <div style="text-align: center; padding: 30px; background: rgba(16, 185, 129, 0.1); border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.2);">
                <i class="fas fa-check-circle" style="font-size: 50px; color: var(--accent-green); margin-bottom: 15px;"></i>
                <h3 style="color: var(--accent-green);">Fully Paid! </h3>
                <p style="color: var(--text-secondary);">This invoice has no pending dues.</p>
            </div>
            {% endif %}
            
            {% if invoice.payments %}
            <div class="payment-history">
                <h4 style="margin-bottom: 15px; color: var(--text-secondary);"><i class="fas fa-history" style="margin-right: 10px;"></i>Payment History</h4>
                {% for p in invoice.payments %}
                <div class="payment-item">
                    <div>
                        <div class="payment-date">{{ p.date }}</div>
                        {% if p.notes %}<div style="font-size: 12px; color: var(--text-secondary);">{{ p.notes }}</div>{% endif %}
                    </div>
                    <div class="payment-amount">+ ৳{{ "{:,.0f}".format(p.amount) }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% elif search_invoice %}
        <div class="empty-state">
            <i class="fas fa-search"></i>
            <p>Invoice "{{ search_invoice }}" not found</p>
        </div>
        {% endif %}

        <div class="card">
            <div class="section-header">
                <span><i class="fas fa-exclamation-triangle" style="margin-right: 10px; color: var(--accent-red);"></i>All Pending Dues</span>
                <span class="table-badge" style="background: var(--accent-red); color: white;">{{ pending_dues|length }} Invoices</span>
            </div>
            
            <div style="max-height: 400px; overflow-y: auto;">
                {% if pending_dues %}
                    {% for due in pending_dues %}
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border-left: 3px solid var(--accent-red);">
                        <div>
                            <div style="font-weight: 700; color: var(--accent-orange);">{{ due.invoice_no }}</div>
                            <div style="font-size: 13px; color: white;">{{ due.customer_name }}</div>
                            <div style="font-size: 12px; color: var(--text-secondary);">{{ due.date }}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 18px; font-weight: 800; color: var(--accent-red);">৳{{ "{:,.0f}".format(due.due) }}</div>
                            <a href="/store/dues/search?invoice_no={{ due.invoice_no }}" class="action-btn btn-edit" style="margin-top: 8px;">
                                <i class="fas fa-money-bill"></i> Collect
                            </a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <i class="fas fa-check-circle" style="color: var(--accent-green);"></i>
                        <p>No pending dues!  All payments collected.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function validatePayment() {
            const amount = parseFloat(document.getElementById('paymentAmount').value);
            if (amount <= 0) {
                alert('Please enter a valid amount');
                return false;
            }
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICES LIST TEMPLATE
# ==============================================================================

STORE_INVOICES_LIST_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - MEHEDI THAI ALUMINUM AND GLASS</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </div>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoice Management</div>
                <div class="page-subtitle">View and manage all invoices</div>
            </div>
            <a href="/store/invoices/create" style="padding: 14px 30px; background: var(--gradient-orange); border-radius: 12px; text-decoration: none; color: white; font-weight: 600;">
                <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
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

        <div class="card" style="margin-bottom: 20px;">
            <div class="section-header">
                <span><i class="fas fa-search" style="margin-right: 10px; color: var(--accent-orange);"></i>Search Invoice</span>
            </div>
            <form action="/store/invoices" method="get" style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px;">
                    <input type="text" name="search" placeholder="Search by Invoice No or Customer Name..." value="{{ search_query }}">
                </div>
                <button type="submit" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-search" style="margin-right: 8px;"></i> Search
                </button>
                {% if search_query %}
                <a href="/store/invoices" style="padding: 14px 20px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); border-radius: 12px; text-decoration: none; color: var(--text-secondary);">
                    <i class="fas fa-times"></i> Clear
                </a>
                {% endif %}
            </form>
        </div>

        <div class="card">
            <div class="section-header">
                <span>All Invoices</span>
                <span class="table-badge" style="background: var(--accent-green); color: white;">{{ invoices|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if invoices %}
                            {% for inv in invoices|reverse %}
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-orange);">{{ inv.invoice_no }}</td>
                                <td style="color: white;">{{ inv.customer_name }}</td>
                                <td style="color: var(--text-secondary);">{{ inv.date }}</td>
                                <td style="font-weight: 700; color: var(--accent-green);">৳{{ "{:,.0f}".format(inv.total) }}</td>
                                <td style="color: var(--accent-green);">৳{{ "{:,.0f}".format(inv.paid) }}</td>
                                <td>
                                    {% if inv.due > 0 %}
                                    <span style="color: var(--accent-red); font-weight: 700;">৳{{ "{:,.0f}".format(inv.due) }}</span>
                                    {% else %}
                                    <span style="color: var(--accent-green);"><i class="fas fa-check-circle"></i> Paid</span>
                                    {% endif %}
                                </td>
                                <td>
                                    <div class="action-cell">
                                        <a href="/store/invoices/print/{{ inv.invoice_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                        {% if inv.due > 0 %}
                                        <a href="/store/dues/search?invoice_no={{ inv.invoice_no }}" class="action-btn btn-edit"><i class="fas fa-money-bill"></i></a>
                                        {% endif %}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="7" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                    <i class="fas fa-file-invoice" style="font-size: 50px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                    {% if search_query %}
                                    No invoices found for "{{ search_query }}"
                                    {% else %}
                                    No invoices created yet.  Create your first invoice! 
                                    {% endif %}
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATES LIST TEMPLATE
# ==============================================================================

STORE_ESTIMATES_LIST_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Estimates - MEHEDI THAI ALUMINUM AND GLASS</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-alt"></i> Estimates
            </div>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Estimates / Quotations</div>
                <div class="page-subtitle">View and manage all estimates</div>
            </div>
            <a href="/store/estimates/create" style="padding: 14px 30px; background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%); border-radius: 12px; text-decoration: none; color: white; font-weight: 600;">
                <i class="fas fa-plus" style="margin-right: 8px;"></i> New Estimate
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
                <span>All Estimates</span>
                <span class="table-badge" style="background: var(--accent-blue); color: white;">{{ estimates|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Estimate No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Valid Until</th>
                            <th>Total</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if estimates %}
                            {% for est in estimates|reverse %}
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-blue);">{{ est.estimate_no }}</td>
                                <td style="color: white;">{{ est.customer_name }}</td>
                                <td style="color: var(--text-secondary);">{{ est.date }}</td>
                                <td style="color: var(--text-secondary);">{{ est.valid_until if est.valid_until else '-' }}</td>
                                <td style="font-weight: 700; color: var(--accent-purple);">৳{{ "{:,.0f}".format(est.total) }}</td>
                                <td>
                                    <div class="action-cell">
                                        <a href="/store/estimates/print/{{ est.estimate_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                        <a href="/store/estimates/to-invoice/{{ est.estimate_no }}" class="action-btn btn-view" title="Convert to Invoice"><i class="fas fa-file-invoice"></i></a>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="6" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                    <i class="fas fa-file-alt" style="font-size: 50px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                    No estimates created yet. Create your first estimate! 
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICE PRINT TEMPLATE - PROFESSIONAL PRINT LAYOUT
# ==============================================================================

STORE_INVOICE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice {{ invoice.invoice_no }} - MEHEDI THAI ALUMINUM AND GLASS</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #fff;
            color: #000;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .invoice-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 30px;
            border: 2px solid #000;
            min-height: 100vh;
            position: relative;
        }
        
        /* Header */
        .invoice-header {
            text-align: center;
            border-bottom: 3px double #000;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }
        
        .company-name {
            font-size: 28px;
            font-weight: 900;
            color: #1a5f2a;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 5px;
        }
        
        .company-tagline {
            font-size: 14px;
            color: #555;
            margin-bottom: 8px;
        }
        
        .company-contact {
            font-size: 12px;
            color: #333;
        }
        
        .invoice-title {
            display: inline-block;
            background: #1a5f2a;
            color: white;
            padding: 8px 40px;
            font-size: 20px;
            font-weight: 700;
            margin-top: 15px;
            letter-spacing: 3px;
        }
        
        /* Info Section */
        .info-section {
            display: flex;
            justify-content: space-between;
            margin-bottom: 25px;
            gap: 20px;
        }
        
        .customer-info, .invoice-info {
            flex: 1;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background: #f9f9f9;
        }
        
        .info-title {
            font-weight: 800;
            font-size: 13px;
            text-transform: uppercase;
            color: #1a5f2a;
            border-bottom: 2px solid #1a5f2a;
            padding-bottom: 5px;
            margin-bottom: 10px;
        }
        
        .info-row {
            display: flex;
            margin-bottom: 5px;
            font-size: 13px;
        }
        
        .info-label {
            font-weight: 700;
            width: 80px;
            color: #555;
        }
        
        .info-value {
            flex: 1;
            color: #000;
            font-weight: 600;
        }
        
        .invoice-no-box {
            background: #1a5f2a;
            color: white;
            padding: 10px 20px;
            text-align: center;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        
        .invoice-no-box .label {
            font-size: 11px;
            opacity: 0.9;
        }
        
        .invoice-no-box .value {
            font-size: 22px;
            font-weight: 900;
        }
        
        /* Items Table */
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }
        
        .items-table th {
            background: #1a5f2a;
            color: white;
            padding: 12px 10px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 700;
        }
        
        .items-table th:last-child,
        .items-table td:last-child {
            text-align: right;
        }
        
        .items-table td {
            padding: 12px 10px;
            border-bottom: 1px solid #ddd;
            font-size: 13px;
        }
        
        .items-table tr:nth-child(even) {
            background: #f5f5f5;
        }
        
        .items-table .item-name {
            font-weight: 700;
        }
        
        .items-table .item-size {
            color: #666;
            font-size: 12px;
        }
        
        /* Totals Section */
        .totals-container {
            display: flex;
            justify-content: flex-end;
        }
        
        .totals-box {
            width: 300px;
            border: 2px solid #1a5f2a;
            border-radius: 5px;
            overflow: hidden;
        }
        
        .totals-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 15px;
            border-bottom: 1px solid #ddd;
            font-size: 14px;
        }
        
        .totals-row:last-child {
            border-bottom: none;
        }
        
        .totals-row.subtotal {
            background: #f5f5f5;
        }
        
        .totals-row.grand-total {
            background: #1a5f2a;
            color: white;
            font-size: 18px;
            font-weight: 800;
        }
        
        .totals-row.paid {
            background: #d4edda;
            color: #155724;
        }
        
        .totals-row.due {
            background: #f8d7da;
            color: #721c24;
            font-weight: 800;
            font-size: 16px;
        }
        
        /* Notes */
        .notes-section {
            margin-top: 25px;
            padding: 15px;
            background: #f9f9f9;
            border: 1px dashed #ccc;
            border-radius: 5px;
        }
        
        .notes-title {
            font-weight: 700;
            color: #555;
            margin-bottom: 5px;
        }
        
        /* Footer */
        .invoice-footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }
        
        .signatures {
            display: flex;
            justify-content: space-between;
            margin-top: 60px;
            padding: 0 30px;
        }
        
        .signature-box {
            text-align: center;
            width: 150px;
        }
        
        .signature-line {
            border-top: 2px solid #000;
            padding-top: 8px;
            font-weight: 700;
            font-size: 13px;
        }
        
        .thank-you {
            text-align: center;
            margin-top: 30px;
            font-size: 16px;
            font-weight: 700;
            color: #1a5f2a;
        }
        
        .powered-by {
            text-align: center;
            margin-top: 15px;
            font-size: 10px;
            color: #999;
        }
        
        /* Print Styles */
        @media print {
            body {
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            
            .invoice-container {
                border: none;
                padding: 20px;
                max-width: 100%;
            }
            
            .no-print {
                display: none !important;
            }
            
            .items-table th {
                background: #1a5f2a !important;
                -webkit-print-color-adjust: exact;
            }
            
            .totals-row.grand-total {
                background: #1a5f2a !important;
                -webkit-print-color-adjust: exact;
            }
        }
        
        /* Action Buttons */
        .action-buttons {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }
        
        .action-btn {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
        }
        
        .btn-print {
            background: #1a5f2a;
            color: white;
        }
        
        .btn-back {
            background: #6c757d;
            color: white;
        }
    </style>
</head>
<body>
    <div class="action-buttons no-print">
        <a href="/store/invoices" class="action-btn btn-back">← Back</a>
        <button onclick="window.print()" class="action-btn btn-print">🖨️ Print Invoice</button>
    </div>

    <div class="invoice-container">
        <div class="invoice-header">
            <div class="company-name">MEHEDI THAI ALUMINUM AND GLASS</div>
            <div class="company-tagline">Quality Aluminum & Glass Solutions</div>
            <div class="company-contact">
                📞 01XXXXXXXXX | 📍 Your Address Here
            </div>
            <div class="invoice-title">INVOICE / চালান</div>
        </div>
        
        <div class="info-section">
            <div class="customer-info">
                <div class="info-title">Customer Details / ক্রেতার তথ্য</div>
                <div class="info-row">
                    <span class="info-label">Name:</span>
                    <span class="info-value">{{ invoice.customer_name }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Phone:</span>
                    <span class="info-value">{{ invoice.customer_phone }}</span>
                </div>
                {% if invoice.customer_address %}
                <div class="info-row">
                    <span class="info-label">Address:</span>
                    <span class="info-value">{{ invoice.customer_address }}</span>
                </div>
                {% endif %}
            </div>
            
            <div class="invoice-info">
                <div class="invoice-no-box">
                    <div class="label">Invoice No / চালান নং</div>
                    <div class="value">{{ invoice.invoice_no }}</div>
                </div>
                <div class="info-row">
                    <span class="info-label">Date:</span>
                    <span class="info-value">{{ invoice.date }}</span>
                </div>
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 5%;">SL</th>
                    <th style="width: 40%;">Description / বিবরণ</th>
                    <th style="width: 15%;">Size (ft)</th>
                    <th style="width: 10%;">Qty</th>
                    <th style="width: 15%;">Rate</th>
                    <th style="width: 15%;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td class="item-name">{{ item.description }}</td>
                    <td class="item-size">{{ item.size if item.size else '-' }}</td>
                    <td>{{ item.qty }}</td>
                    <td>৳{{ "{:,.2f}".format(item.price) }}</td>
                    <td>৳{{ "{:,.2f}".format(item.total) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-container">
            <div class="totals-box">
                <div class="totals-row subtotal">
                    <span>Subtotal / উপমোট</span>
                    <span>৳{{ "{:,.2f}".format(invoice.total + invoice.discount) }}</span>
                </div>
                {% if invoice.discount > 0 %}
                <div class="totals-row">
                    <span>Discount / ছাড়</span>
                    <span>- ৳{{ "{:,.2f}".format(invoice.discount) }}</span>
                </div>
                {% endif %}
                <div class="totals-row grand-total">
                    <span>Grand Total / সর্বমোট</span>
                    <span>৳{{ "{:,.2f}".format(invoice.total) }}</span>
                </div>
                <div class="totals-row paid">
                    <span>Paid / পরিশোধিত</span>
                    <span>৳{{ "{:,.2f}".format(invoice.paid) }}</span>
                </div>
                {% if invoice.due > 0 %}
                <div class="totals-row due">
                    <span>Due / বাকি</span>
                    <span>৳{{ "{:,.2f}".format(invoice.due) }}</span>
                </div>
                {% endif %}
            </div>
        </div>
        
        {% if invoice.notes %}
        <div class="notes-section">
            <div class="notes-title">Notes / নোট:</div>
            <div>{{ invoice.notes }}</div>
        </div>
        {% endif %}
        
        <div class="invoice-footer">
            <div class="signatures">
                <div class="signature-box">
                    <div class="signature-line">Customer Signature<br>ক্রেতার স্বাক্ষর</div>
                </div>
                <div class="signature-box">
                    <div class="signature-line">Authorized Signature<br>বিক্রেতার স্বাক্ষর</div>
                </div>
            </div>
            
            <div class="thank-you">Thank You For Your Business!  / ব্যবসায় আপনাকে ধন্যবাদ!</div>
            <div class="powered-by">Powered by Mehedi Hasan | MNM Software</div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATES LIST TEMPLATE
# ==============================================================================

STORE_ESTIMATES_LIST_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Estimates - MEHEDI THAI ALUMINUM AND GLASS</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-alt"></i> Estimates
            </div>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Estimates / Quotations</div>
                <div class="page-subtitle">View and manage all estimates</div>
            </div>
            <a href="/store/estimates/create" style="padding: 14px 30px; background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%); border-radius: 12px; text-decoration: none; color: white; font-weight: 600;">
                <i class="fas fa-plus" style="margin-right: 8px;"></i> New Estimate
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
                <span>All Estimates</span>
                <span class="table-badge" style="background: var(--accent-blue); color: white;">{{ estimates|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Estimate No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Valid Until</th>
                            <th>Total</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if estimates %}
                            {% for est in estimates|reverse %}
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-blue);">{{ est.estimate_no }}</td>
                                <td style="color: white;">{{ est.customer_name }}</td>
                                <td style="color: var(--text-secondary);">{{ est.date }}</td>
                                <td style="color: var(--text-secondary);">{{ est.valid_until if est.valid_until else '-' }}</td>
                                <td style="font-weight: 700; color: var(--accent-purple);">৳{{ "{:,.0f}".format(est.total) }}</td>
                                <td>
                                    <div class="action-cell">
                                        <a href="/store/estimates/print/{{ est.estimate_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                        <a href="/store/estimates/to-invoice/{{ est.estimate_no }}" class="action-btn btn-view" title="Convert to Invoice"><i class="fas fa-file-invoice"></i></a>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="6" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                    <i class="fas fa-file-alt" style="font-size: 50px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                    No estimates created yet. Create your first estimate! 
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ESTIMATE PRINT TEMPLATE - PROFESSIONAL QUOTATION
# ==============================================================================

STORE_ESTIMATE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estimate {{ estimate.estimate_no }} - MEHEDI THAI ALUMINUM AND GLASS</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #fff; color: #000; font-size: 14px; }
        .container { max-width: 800px; margin: 0 auto; padding: 30px; border: 2px solid #000; min-height: 100vh; }
        .header { text-align: center; border-bottom: 3px double #000; padding-bottom: 20px; margin-bottom: 25px; }
        .company-name { font-size: 28px; font-weight: 900; color: #2563eb; text-transform: uppercase; letter-spacing: 2px; }
        .company-tagline { font-size: 14px; color: #555; margin: 5px 0 8px; }
        .estimate-title { display: inline-block; background: #2563eb; color: white; padding: 8px 40px; font-size: 20px; font-weight: 700; margin-top: 15px; letter-spacing: 3px; }
        .info-section { display: flex; justify-content: space-between; margin-bottom: 25px; gap: 20px; }
        .customer-info, .estimate-info { flex: 1; padding: 15px; border: 1px solid #ddd; background: #f9f9f9; }
        .info-title { font-weight: 800; color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 5px; margin-bottom: 10px; text-transform: uppercase; font-size: 13px; }
        .info-row { display: flex; margin-bottom: 5px; font-size: 13px; }
        .info-label { font-weight: 700; width: 80px; color: #555; }
        .info-value { flex: 1; color: #000; font-weight: 600; }
        .estimate-no-box { background: #2563eb; color: white; padding: 10px 20px; text-align: center; margin-bottom: 10px; }
        .estimate-no-box .label { font-size: 11px; opacity: 0.9; }
        .estimate-no-box .value { font-size: 22px; font-weight: 900; }
        .items-table { width: 100%; border-collapse: collapse; margin-bottom: 25px; }
        .items-table th { background: #2563eb; color: white; padding: 12px 10px; text-align: left; font-size: 12px; text-transform: uppercase; }
        .items-table th:last-child, .items-table td:last-child { text-align: right; }
        .items-table td { padding: 12px 10px; border-bottom: 1px solid #ddd; font-size: 13px; }
        .items-table tr:nth-child(even) { background: #f5f5f5; }
        .totals-container { display: flex; justify-content: flex-end; }
        .totals-box { width: 300px; border: 2px solid #2563eb; overflow: hidden; }
        .totals-row { display: flex; justify-content: space-between; padding: 10px 15px; border-bottom: 1px solid #ddd; font-size: 14px; }
        .totals-row:last-child { border-bottom: none; }
        .totals-row.grand-total { background: #2563eb; color: white; font-size: 18px; font-weight: 800; }
        .terms-section { margin-top: 30px; padding: 15px; background: #f0f7ff; border: 1px solid #2563eb; border-radius: 5px; }
        .terms-title { font-weight: 700; color: #2563eb; margin-bottom: 10px; }
        .terms-list { margin-left: 20px; font-size: 12px; color: #555; }
        .terms-list li { margin-bottom: 5px; }
        .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; }
        .signatures { display: flex; justify-content: space-between; margin-top: 60px; padding: 0 30px; }
        .signature-box { text-align: center; width: 150px; }
        .signature-line { border-top: 2px solid #000; padding-top: 8px; font-weight: 700; font-size: 13px; }
        .validity-notice { text-align: center; margin-top: 20px; padding: 10px; background: #fff3cd; border: 1px solid #ffc107; font-weight: 600; color: #856404; }
        .powered-by { text-align: center; margin-top: 15px; font-size: 10px; color: #999; }
        .action-buttons { position: fixed; top: 20px; right: 20px; display: flex; gap: 10px; z-index: 1000; }
        .action-btn { padding: 12px 25px; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; font-size: 14px; }
        .btn-print { background: #2563eb; color: white; }
        .btn-back { background: #6c757d; color: white; }
        @media print {
            .action-buttons { display: none !important; }
            .container { border: none; padding: 20px; }
            .items-table th, .totals-row.grand-total { background: #2563eb !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="action-buttons">
        <a href="/store/estimates" class="action-btn btn-back">← Back</a>
        <button onclick="window.print()" class="action-btn btn-print">🖨️ Print Estimate</button>
    </div>

    <div class="container">
        <div class="header">
            <div class="company-name">MEHEDI THAI ALUMINUM AND GLASS</div>
            <div class="company-tagline">Quality Aluminum & Glass Solutions</div>
            <div class="estimate-title">ESTIMATE / কোটেশন</div>
        </div>
        
        <div class="info-section">
            <div class="customer-info">
                <div class="info-title">Customer Details / ক্রেতার তথ্য</div>
                <div class="info-row">
                    <span class="info-label">Name:</span>
                    <span class="info-value">{{ estimate.customer_name }}</span>
                </div>
                {% if estimate.customer_phone %}
                <div class="info-row">
                    <span class="info-label">Phone:</span>
                    <span class="info-value">{{ estimate.customer_phone }}</span>
                </div>
                {% endif %}
                {% if estimate.customer_address %}
                <div class="info-row">
                    <span class="info-label">Address:</span>
                    <span class="info-value">{{ estimate.customer_address }}</span>
                </div>
                {% endif %}
            </div>
            
            <div class="estimate-info">
                <div class="estimate-no-box">
                    <div class="label">Estimate No / কোটেশন নং</div>
                    <div class="value">{{ estimate.estimate_no }}</div>
                </div>
                <div class="info-row">
                    <span class="info-label">Date:</span>
                    <span class="info-value">{{ estimate.date }}</span>
                </div>
                {% if estimate.valid_until %}
                <div class="info-row">
                    <span class="info-label">Valid Until:</span>
                    <span class="info-value">{{ estimate.valid_until }}</span>
                </div>
                {% endif %}
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th style="width: 5%;">SL</th>
                    <th style="width: 40%;">Description / বিবরণ</th>
                    <th style="width: 15%;">Size (ft)</th>
                    <th style="width: 10%;">Qty</th>
                    <th style="width: 15%;">Rate</th>
                    <th style="width: 15%;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in estimate.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.description }}</td>
                    <td>{{ item.size if item.size else '-' }}</td>
                    <td>{{ item.qty }}</td>
                    <td>৳{{ "{:,.2f}".format(item.price) }}</td>
                    <td>৳{{ "{:,.2f}".format(item.total) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-container">
            <div class="totals-box">
                <div class="totals-row" style="background: #f5f5f5;">
                    <span>Subtotal / উপমোট</span>
                    <span>৳{{ "{:,.2f}".format(estimate.total + estimate.discount) }}</span>
                </div>
                {% if estimate.discount > 0 %}
                <div class="totals-row">
                    <span>Discount / ছাড়</span>
                    <span>- ৳{{ "{:,.2f}".format(estimate.discount) }}</span>
                </div>
                {% endif %}
                <div class="totals-row grand-total">
                    <span>Estimated Total / সর্বমোট</span>
                    <span>৳{{ "{:,.2f}".format(estimate.total) }}</span>
                </div>
            </div>
        </div>

        {% if estimate.valid_until %}
        <div class="validity-notice">
            ⚠️ This quotation is valid until {{ estimate.valid_until }}.  Prices may change after this date.
        </div>
        {% endif %}
        
        {% if estimate.notes %}
        <div class="terms-section">
            <div class="terms-title">Terms & Conditions / শর্তাবলী:</div>
            <div>{{ estimate.notes }}</div>
        </div>
        {% endif %}
        
        <div class="footer">
            <div class="signatures">
                <div class="signature-box">
                    <div class="signature-line">Customer Signature<br>ক্রেতার স্বাক্ষর</div>
                </div>
                <div class="signature-box">
                    <div class="signature-line">Authorized Signature<br>বিক্রেতার স্বাক্ষর</div>
                </div>
            </div>
            <div class="powered-by">Powered by Mehedi Hasan | MNM Software</div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE DUE COLLECTION TEMPLATE
# ==============================================================================

STORE_DUE_COLLECTION_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due Collection - MEHEDI THAI ALUMINUM AND GLASS</title>
    """ + COMMON_STYLES + """
    <style>
        .due-card {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
        }
        
        .due-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .due-invoice-no {
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-orange);
        }
        
        .due-amount {
            font-size: 24px;
            font-weight: 800;
            color: var(--accent-red);
        }
        
        .due-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .due-detail-item {
            background: rgba(255, 255, 255, 0.03);
            padding: 12px;
            border-radius: 10px;
        }
        
        .due-detail-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        
        .due-detail-value {
            font-size: 15px;
            font-weight: 600;
            color: white;
        }
        
        .payment-form {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 12px;
            padding: 20px;
        }
        
        .payment-history {
            margin-top: 20px;
        }
        
        .payment-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        
        .payment-date {
            color: var(--text-secondary);
            font-size: 13px;
        }
        
        .payment-amount {
            font-weight: 700;
            color: var(--accent-green);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="loading-text">Processing Payment...</div>
    </div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <div class="nav-link active">
                <i class="fas fa-wallet"></i> Due Collection
            </div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Due Collection</div>
                <div class="page-subtitle">Manage pending payments</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
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

        <div class="card" style="margin-bottom: 30px;">
            <div class="section-header">
                <span><i class="fas fa-search" style="margin-right: 10px; color: var(--accent-orange);"></i>Search Invoice</span>
            </div>
            <form action="/store/dues/search" method="get" style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px;">
                    <input type="text" name="invoice_no" placeholder="Enter Invoice Number (e.g.  INV-0001)" value="{{ search_invoice }}">
                </div>
                <button type="submit" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-search" style="margin-right: 8px;"></i> Search
                </button>
            </form>
        </div>

        {% if invoice %}
        <div class="due-card">
            <div class="due-header">
                <div class="due-invoice-no">{{ invoice.invoice_no }}</div>
                <div class="due-amount">Due: ৳{{ "{:,.0f}".format(invoice.due) }}</div>
            </div>
            
            <div class="due-details">
                <div class="due-detail-item">
                    <div class="due-detail-label">Customer</div>
                    <div class="due-detail-value">{{ invoice.customer_name }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Phone</div>
                    <div class="due-detail-value">{{ invoice.customer_phone }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Invoice Date</div>
                    <div class="due-detail-value">{{ invoice.date }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Total Amount</div>
                    <div class="due-detail-value">৳{{ "{:,.0f}".format(invoice.total) }}</div>
                </div>
                <div class="due-detail-item">
                    <div class="due-detail-label">Already Paid</div>
                    <div class="due-detail-value" style="color: var(--accent-green);">৳{{ "{:,.0f}".format(invoice.paid) }}</div>
                </div>
            </div>
            
            {% if invoice.due > 0 %}
            <div class="payment-form">
                <h4 style="margin-bottom: 15px; color: var(--accent-green);"><i class="fas fa-money-bill-wave" style="margin-right: 10px;"></i>Record Payment</h4>
                <form action="/store/dues/collect" method="post" onsubmit="return validatePayment()">
                    <input type="hidden" name="invoice_no" value="{{ invoice.invoice_no }}">
                    <div class="grid-2">
                        <div class="input-group">
                            <label>PAYMENT AMOUNT</label>
                            <input type="number" name="amount" id="paymentAmount" required placeholder="৳" step="0.01" max="{{ invoice.due }}">
                        </div>
                        <div class="input-group">
                            <label>PAYMENT DATE</label>
                            <input type="date" name="payment_date" value="{{ today }}" required>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>NOTES (Optional)</label>
                        <input type="text" name="notes" placeholder="Payment notes... ">
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-check" style="margin-right: 10px;"></i> Record Payment
                    </button>
                </form>
            </div>
            {% else %}
            <div style="text-align: center; padding: 30px; background: rgba(16, 185, 129, 0.1); border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.2);">
                <i class="fas fa-check-circle" style="font-size: 50px; color: var(--accent-green); margin-bottom: 15px;"></i>
                <h3 style="color: var(--accent-green);">Fully Paid! </h3>
                <p style="color: var(--text-secondary);">This invoice has no pending dues.</p>
            </div>
            {% endif %}
            
            {% if invoice.payments %}
            <div class="payment-history">
                <h4 style="margin-bottom: 15px; color: var(--text-secondary);"><i class="fas fa-history" style="margin-right: 10px;"></i>Payment History</h4>
                {% for p in invoice.payments %}
                <div class="payment-item">
                    <div>
                        <div class="payment-date">{{ p.date }}</div>
                        {% if p.notes %}<div style="font-size: 12px; color: var(--text-secondary);">{{ p.notes }}</div>{% endif %}
                    </div>
                    <div class="payment-amount">+ ৳{{ "{:,.0f}".format(p.amount) }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% elif search_invoice %}
        <div class="empty-state">
            <i class="fas fa-search"></i>
            <p>Invoice "{{ search_invoice }}" not found</p>
        </div>
        {% endif %}

        <div class="card">
            <div class="section-header">
                <span><i class="fas fa-exclamation-triangle" style="margin-right: 10px; color: var(--accent-red);"></i>All Pending Dues</span>
                <span class="table-badge" style="background: var(--accent-red); color: white;">{{ pending_dues|length }} Invoices</span>
            </div>
            
            <div style="max-height: 400px; overflow-y: auto;">
                {% if pending_dues %}
                    {% for due in pending_dues %}
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 10px; border-left: 3px solid var(--accent-red);">
                        <div>
                            <div style="font-weight: 700; color: var(--accent-orange);">{{ due.invoice_no }}</div>
                            <div style="font-size: 13px; color: white;">{{ due.customer_name }}</div>
                            <div style="font-size: 12px; color: var(--text-secondary);">{{ due.date }}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 18px; font-weight: 800; color: var(--accent-red);">৳{{ "{:,.0f}".format(due.due) }}</div>
                            <a href="/store/dues/search?invoice_no={{ due.invoice_no }}" class="action-btn btn-edit" style="margin-top: 8px;">
                                <i class="fas fa-money-bill"></i> Collect
                            </a>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <i class="fas fa-check-circle" style="color: var(--accent-green);"></i>
                        <p>No pending dues!  All payments collected.</p>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function validatePayment() {
            const amount = parseFloat(document.getElementById('paymentAmount').value);
            if (amount <= 0) {
                alert('Please enter a valid amount');
                return false;
            }
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICES LIST TEMPLATE
# ==============================================================================

STORE_INVOICES_LIST_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - MEHEDI THAI ALUMINUM AND GLASS</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <div class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </div>
            <a href="/store/estimates" class="nav-link">
                <i class="fas fa-file-alt"></i> Estimates
            </a>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoice Management</div>
                <div class="page-subtitle">View and manage all invoices</div>
            </div>
            <a href="/store/invoices/create" style="padding: 14px 30px; background: var(--gradient-orange); border-radius: 12px; text-decoration: none; color: white; font-weight: 600;">
                <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
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

        <div class="card" style="margin-bottom: 20px;">
            <div class="section-header">
                <span><i class="fas fa-search" style="margin-right: 10px; color: var(--accent-orange);"></i>Search Invoice</span>
            </div>
            <form action="/store/invoices" method="get" style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 200px;">
                    <input type="text" name="search" placeholder="Search by Invoice No or Customer Name..." value="{{ search_query }}">
                </div>
                <button type="submit" style="width: auto; padding: 14px 30px;">
                    <i class="fas fa-search" style="margin-right: 8px;"></i> Search
                </button>
                {% if search_query %}
                <a href="/store/invoices" style="padding: 14px 20px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); border-radius: 12px; text-decoration: none; color: var(--text-secondary);">
                    <i class="fas fa-times"></i> Clear
                </a>
                {% endif %}
            </form>
        </div>

        <div class="card">
            <div class="section-header">
                <span>All Invoices</span>
                <span class="table-badge" style="background: var(--accent-green); color: white;">{{ invoices|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if invoices %}
                            {% for inv in invoices|reverse %}
                            <tr>
                                <td style="font-weight: 700; color: var(--accent-orange);">{{ inv.invoice_no }}</td>
                                <td style="color: white;">{{ inv.customer_name }}</td>
                                <td style="color: var(--text-secondary);">{{ inv.date }}</td>
                                <td style="font-weight: 700; color: var(--accent-green);">৳{{ "{:,.0f}".format(inv.total) }}</td>
                                <td style="color: var(--accent-green);">৳{{ "{:,.0f}".format(inv.paid) }}</td>
                                <td>
                                    {% if inv.due > 0 %}
                                    <span style="color: var(--accent-red); font-weight: 700;">৳{{ "{:,.0f}".format(inv.due) }}</span>
                                    {% else %}
                                    <span style="color: var(--accent-green);"><i class="fas fa-check-circle"></i> Paid</span>
                                    {% endif %}
                                </td>
                                <td>
                                    <div class="action-cell">
                                        <a href="/store/invoices/print/{{ inv.invoice_no }}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                        {% if inv.due > 0 %}
                                        <a href="/store/dues/search?invoice_no={{ inv.invoice_no }}" class="action-btn btn-edit"><i class="fas fa-money-bill"></i></a>
                                        {% endif %}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="7" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                    <i class="fas fa-file-invoice" style="font-size: 50px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                    {% if search_query %}
                                    No invoices found for "{{ search_query }}"
                                    {% else %}
                                    No invoices created yet.  Create your first invoice! 
                                    {% endif %}
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# REPORT TEMPLATES (ORIGINAL - CLOSING, ACCESSORIES, PO)
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
        .info-label { font-weight: 800; color: #444; width: 90px; display: inline-block; }
        .info-value { font-weight: 800; color: #000; }
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
                <div class="info-item"><span class="info-label">Buyer:</span> <span class="info-value">{{ report_data[0].buyer }}</span></div>
                <div class="info-item"><span class="info-label">Style:</span> <span class="info-value">{{ report_data[0].style }}</span></div>
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
        .table th:empty { background-color: white !important; border: none; }
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
            .table th:empty { background-color: white !important; border: none !important; }
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
            <button onclick="window.print()" class="btn btn-print"><i class="fas fa-file-pdf"></i> Print</button>
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
# ==============================================================================
# FLASK ROUTES - AUTHENTICATION
# ==============================================================================

@app.route('/')
def home():
    if 'user' not in session:
        return render_template_string(LOGIN_TEMPLATE)
    
    if session.get('role') == 'admin':
        stats = get_dashboard_summary_v2()
        return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
    else:
        return render_template_string(USER_DASHBOARD_TEMPLATE)

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
        
        # Update last login time
        users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
        save_users(users)
        
        return redirect(url_for('home'))
    else:
        flash('Invalid Username or Password!')
        return redirect(url_for('home'))

@app.route('/logout')
def logout():
    # Calculate session duration before clearing
    users = load_users()
    username = session.get('user')
    
    if username and username in users:
        login_time_str = session.get('login_time')
        if login_time_str:
            try:
                login_time = datetime.fromisoformat(login_time_str)
                now = get_bd_time()
                duration = now - login_time
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                users[username]['last_duration'] = f"{minutes}m {seconds}s"
                save_users(users)
            except:
                pass
    
    session.clear()
    return redirect(url_for('home'))

# ==============================================================================
# FLASK ROUTES - ADMIN USER MANAGEMENT
# ==============================================================================

@app.route('/admin/get-users')
def get_users():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.get_json()
    users = load_users()
    username = data.get('username')
    password = data.get('password')
    permissions = data.get('permissions', [])
    action = data.get('action_type', 'create')
    
    if action == 'create' and username in users:
        return jsonify({"status": "error", "message": "User already exists!"})
    
    if action == 'create':
        users[username] = {
            "password": password,
            "role": "user",
            "permissions": permissions,
            "created_at": get_bd_date_str(),
            "last_login": "Never",
            "last_duration": "N/A"
        }
    else:
        users[username]['password'] = password
        users[username]['permissions'] = permissions
    
    save_users(users)
    return jsonify({"status": "success"})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.get_json()
    users = load_users()
    username = data.get('username')
    
    if username in users and users[username].get('role') != 'admin':
        del users[username]
        save_users(users)
    
    return jsonify({"status": "success"})

# ==============================================================================
# FLASK ROUTES - CLOSING REPORT
# ==============================================================================

@app.route('/generate-report', methods=['POST'])
def generate_report():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref_no = request.form.get('ref_no', '').strip()
    if not ref_no:
        flash('Please enter a valid Reference Number.')
        return redirect(url_for('home'))
    
    report_data = fetch_closing_report_data(ref_no)
    
    if report_data:
        update_stats(ref_no, session['user'])
        return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=ref_no.upper())
    else:
        flash(f'No data found for "{ref_no}".  Please check the reference number.')
        return redirect(url_for('home'))

@app.route('/download-closing-excel')
def download_closing_excel():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref_no = request.args.get('ref_no', '').strip()
    if not ref_no:
        flash('Reference number is required.')
        return redirect(url_for('home'))
    
    report_data = fetch_closing_report_data(ref_no)
    if not report_data:
        flash('No data found for the given reference.')
        return redirect(url_for('home'))
    
    excel_file = create_formatted_excel_report(report_data, ref_no)
    if excel_file:
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f"Closing_Report_{ref_no.upper()}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    flash('Failed to generate Excel file.')
    return redirect(url_for('home'))

# ==============================================================================
# FLASK ROUTES - PO SHEET GENERATOR
# ==============================================================================

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    if 'pdf_files' not in request.files:
        flash('No files uploaded.')
        return redirect(url_for('home'))
    
    files = request.files.getlist('pdf_files')
    valid_files = [f for f in files if f and f.filename.endswith('.pdf')]
    
    if not valid_files:
        flash('Please upload valid PDF files.')
        return redirect(url_for('home'))
    
    all_data = []
    metadata = {}
    
    for file in valid_files:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        try:
            extracted, meta = extract_data_dynamic(filepath)
            if extracted:
                all_data.extend(extracted)
            if meta and meta.get('buyer') != 'N/A':
                metadata = meta
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    if not all_data:
        flash('No valid data could be extracted from the uploaded files.')
        return redirect(url_for('home'))
    
    # Update stats
    update_po_stats(session['user'], len(valid_files))
    
    # Process data and create tables
    df = pd.DataFrame(all_data)
    
    # Sort sizes
    unique_sizes = df['Size'].unique().tolist()
    sorted_sizes = sort_sizes(unique_sizes)
    
    # Group by color
    tables = []
    grand_total = 0
    
    for color in df['Color'].unique():
        color_df = df[df['Color'] == color]
        
        pivot = color_df.pivot_table(
            index='P.O NO',
            columns='Size',
            values='Quantity',
            aggfunc='sum',
            fill_value=0
        )
        
        # Reorder columns
        pivot = pivot.reindex(columns=[s for s in sorted_sizes if s in pivot.columns], fill_value=0)
        
        # Add Total column
        pivot['Total'] = pivot.sum(axis=1)
        grand_total += pivot['Total'].sum()
        
        # Add summary row
        summary = pivot.sum().to_frame().T
        summary.index = ['COLOR TOTAL']
        pivot = pd.concat([pivot, summary])
        
        # Convert to HTML
        html_table = pivot.to_html(classes='table table-striped', border=0)
        html_table = html_table.replace('<th></th>', '<th class="order-col">P.O NO</th>')
        html_table = html_table.replace('>Total<', ' class="total-col-header">Total<')
        html_table = html_table.replace('<tr>\n      <th>COLOR TOTAL</th>', '<tr class="summary-row">\n      <th class="summary-label">COLOR TOTAL</th>')
        
        tables.append({
            'color': color,
            'table': html_table
        })
    
    return render_template_string(
        PO_REPORT_TEMPLATE,
        tables=tables,
        meta=metadata,
        grand_total=f"{grand_total:,}",
        message=None
    )

# ==============================================================================
# FLASK ROUTES - ACCESSORIES
# ==============================================================================

@app.route('/admin/accessories')
def accessories_home():
    if 'user' not in session:
        return redirect(url_for('home'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref = request.form.get('ref_no', '').strip().upper()
    if not ref:
        flash('Please enter a valid Reference Number.')
        return redirect(url_for('accessories_home'))
    
    # Fetch color data from API
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
            if block.get('style') != 'N/A':
                style = block.get('style')
    
    # Load existing data
    acc_db = load_accessories_db()
    if ref not in acc_db:
        acc_db[ref] = {
            "buyer": buyer,
            "style": style,
            "challans": []
        }
        save_accessories_db(acc_db)
    
    challans = acc_db[ref].get('challans', [])
    
    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref,
        buyer=acc_db[ref].get('buyer', buyer),
        style=acc_db[ref].get('style', style),
        colors=colors,
        challans=challans
    )

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref = request.args.get('ref', '').strip().upper()
    if not ref:
        return redirect(url_for('accessories_home'))
    
    acc_db = load_accessories_db()
    if ref not in acc_db:
        flash('Reference not found.  Please search first.')
        return redirect(url_for('accessories_home'))
    
    # Get colors from API
    report_data = fetch_closing_report_data(ref)
    colors = []
    if report_data:
        for block in report_data:
            color_name = block.get('color', '')
            if color_name and color_name not in colors:
                colors.append(color_name)
    
    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref,
        buyer=acc_db[ref].get('buyer', 'N/A'),
        style=acc_db[ref].get('style', 'N/A'),
        colors=colors,
        challans=acc_db[ref].get('challans', [])
    )

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref = request.form.get('ref', '').strip().upper()
    line_no = request.form.get('line_no', '').strip()
    color = request.form.get('color', '').strip()
    size = request.form.get('size', 'ALL').strip()
    qty = request.form.get('qty', '0').strip()
    item_type = request.form.get('item_type', 'Top')
    
    acc_db = load_accessories_db()
    
    if ref not in acc_db:
        acc_db[ref] = {"buyer": "N/A", "style": "N/A", "challans": []}
    
    new_challan = {
        "date": get_bd_date_str(),
        "line": line_no,
        "color": color,
        "size": size,
        "qty": int(qty),
        "status": "✔",
        "item_type": item_type
    }
    
    acc_db[ref]['challans'].append(new_challan)
    save_accessories_db(acc_db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/edit')
def accessories_edit():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    ref = request.args.get('ref', '').strip().upper()
    index = int(request.args.get('index', 0))
    
    acc_db = load_accessories_db()
    
    if ref not in acc_db or index >= len(acc_db[ref].get('challans', [])):
        flash('Entry not found.')
        return redirect(url_for('accessories_home'))
    
    item = acc_db[ref]['challans'][index]
    
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item)

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    ref = request.form.get('ref', '').strip().upper()
    index = int(request.form.get('index', 0))
    
    acc_db = load_accessories_db()
    
    if ref in acc_db and index < len(acc_db[ref].get('challans', [])):
        acc_db[ref]['challans'][index]['line'] = request.form.get('line_no', '').strip()
        acc_db[ref]['challans'][index]['color'] = request.form.get('color', '').strip()
        acc_db[ref]['challans'][index]['size'] = request.form.get('size', 'ALL').strip()
        acc_db[ref]['challans'][index]['qty'] = int(request.form.get('qty', 0))
        save_accessories_db(acc_db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    ref = request.form.get('ref', '').strip().upper()
    index = int(request.form.get('index', 0))
    
    acc_db = load_accessories_db()
    
    if ref in acc_db and index < len(acc_db[ref].get('challans', [])):
        del acc_db[ref]['challans'][index]
        save_accessories_db(acc_db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/print')
def accessories_print():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    ref = request.args.get('ref', '').strip().upper()
    acc_db = load_accessories_db()
    
    if ref not in acc_db:
        flash('Reference not found.')
        return redirect(url_for('accessories_home'))
    
    data = acc_db[ref]
    challans = data.get('challans', [])
    
    # Calculate line summary
    line_summary = {}
    item_type = "Top"
    for c in challans:
        line = c.get('line', 'N/A')
        # FIX: Ensure qty is an integer before adding
        try:
            qty = int(c.get('qty', 0))
        except (ValueError, TypeError):
            qty = 0
            
        line_summary[line] = line_summary.get(line, 0) + qty
        if c.get('item_type'):
            item_type = c.get('item_type')
    
    return render_template_string(
        ACCESSORIES_REPORT_TEMPLATE,
        ref=ref,
        buyer=data.get('buyer', 'N/A'),
        style=data.get('style', 'N/A'),
        challans=challans,
        count=len(challans),
        line_summary=line_summary,
        item_type=item_type,
        today=get_bd_date_str()
    )

# ==============================================================================
# FLASK ROUTES - STORE MANAGEMENT
# ==============================================================================

@app.route('/admin/store')
def store_dashboard():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    store_stats = get_store_dashboard_summary()
    invoices = load_store_invoices()
    estimates = load_store_estimates()
    
    # Get pending dues
    pending_dues = [inv for inv in invoices if inv.get('due', 0) > 0]
    
    return render_template_string(
        STORE_DASHBOARD_TEMPLATE,
        store_stats=store_stats,
        recent_invoices=invoices[-10:][::-1] if invoices else [],
        recent_estimates=estimates[-10:][::-1] if estimates else [],
        pending_dues=pending_dues
    )

# --- Products ---
@app.route('/store/products')
def store_products():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    products = load_store_products()
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products)

@app.route('/store/products/save', methods=['POST'])
def store_products_save():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    products = load_store_products()
    
    new_product = {
        "name": request.form.get('name', '').strip(),
        "size_feet": request.form.get('size_feet', '').strip(),
        "thickness": request.form.get('thickness', '').strip(),
        "category": request.form.get('category', 'Other'),
        "price": float(request.form.get('price', 0) or 0),
        "description": request.form.get('description', '').strip(),
        "created_at": get_bd_date_str()
    }
    
    products.append(new_product)
    save_store_products(products)
    
    flash('Product saved successfully!')
    return redirect(url_for('store_products'))

@app.route('/store/products/delete/<int:index>', methods=['POST'])
def store_products_delete(index):
    if 'user' not in session:
        return redirect(url_for('home'))
    
    products = load_store_products()
    if 0 <= index < len(products):
        del products[index]
        save_store_products(products)
        flash('Product deleted!')
    
    return redirect(url_for('store_products'))

# --- Customers ---
@app.route('/store/customers')
def store_customers():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    customers = load_store_customers()
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)

@app.route('/store/customers/save', methods=['POST'])
def store_customers_save():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    customers = load_store_customers()
    
    new_customer = {
        "name": request.form.get('name', '').strip(),
        "phone": request.form.get('phone', '').strip(),
        "address": request.form.get('address', '').strip(),
        "created_at": get_bd_date_str()
    }
    
    customers.append(new_customer)
    save_store_customers(customers)
    
    flash('Customer saved successfully!')
    return redirect(url_for('store_customers'))

@app.route('/store/customers/delete/<int:index>', methods=['POST'])
def store_customers_delete(index):
    if 'user' not in session:
        return redirect(url_for('home'))
    
    customers = load_store_customers()
    if 0 <= index < len(customers):
        del customers[index]
        save_store_customers(customers)
        flash('Customer deleted!')
    
    return redirect(url_for('store_customers'))

# --- Invoices ---
@app.route('/store/invoices')
def store_invoices():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoices = load_store_invoices()
    search_query = request.args.get('search', '').strip()
    
    if search_query:
        invoices = [inv for inv in invoices if search_query.lower() in inv.get('invoice_no', '').lower() or search_query.lower() in inv.get('customer_name', '').lower()]
    
    return render_template_string(STORE_INVOICES_LIST_TEMPLATE, invoices=invoices, search_query=search_query)

@app.route('/store/invoices/create')
def store_invoices_create():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoice_no = generate_invoice_number()
    customers = load_store_customers()
    today = get_bd_time().strftime('%Y-%m-%d')
    
    return render_template_string(STORE_INVOICE_CREATE_TEMPLATE, invoice_no=invoice_no, customers=customers, today=today)

@app.route('/store/invoices/save', methods=['POST'])
def store_invoices_save():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoices = load_store_invoices()
    
    # Parse items
    items = []
    i = 0
    while f'items[{i}][description]' in request.form:
        item = {
            "description": request.form.get(f'items[{i}][description]', ''),
            "size": request.form.get(f'items[{i}][size]', ''),
            "qty": int(request.form.get(f'items[{i}][qty]', 1) or 1),
            "price": float(request.form.get(f'items[{i}][price]', 0) or 0),
            "total": float(request.form.get(f'items[{i}][total]', 0) or 0)
        }
        items.append(item)
        i += 1
    
    invoice_date = request.form.get('invoice_date', '')
    formatted_date = invoice_date
    try:
        dt = datetime.strptime(invoice_date, '%Y-%m-%d')
        formatted_date = dt.strftime('%d-%m-%Y')
    except:
        pass
    
    new_invoice = {
        "invoice_no": request.form.get('invoice_no', ''),
        "customer_name": request.form.get('customer_name', ''),
        "customer_phone": request.form.get('customer_phone', ''),
        "customer_address": request.form.get('customer_address', ''),
        "date": formatted_date,
        "items": items,
        "discount": float(request.form.get('discount', 0) or 0),
        "total": float(request.form.get('total', 0) or 0),
        "paid": float(request.form.get('paid', 0) or 0),
        "due": float(request.form.get('due', 0) or 0),
        "notes": request.form.get('notes', ''),
        "payments": [],
        "created_at": get_bd_date_str()
    }
    
    invoices.append(new_invoice)
    save_store_invoices(invoices)
    
    flash('Invoice created successfully!')
    
    action = request.form.get('action', 'save')
    if action == 'save_print':
        return redirect(url_for('store_invoices_print', invoice_no=new_invoice['invoice_no']))
    
    return redirect(url_for('store_invoices'))

@app.route('/store/invoices/print/<invoice_no>')
def store_invoices_print(invoice_no):
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoices = load_store_invoices()
    invoice = next((inv for inv in invoices if inv.get('invoice_no') == invoice_no), None)
    
    if not invoice:
        flash('Invoice not found!')
        return redirect(url_for('store_invoices'))
    
    return render_template_string(STORE_INVOICE_PRINT_TEMPLATE, invoice=invoice)

# --- Estimates ---
@app.route('/store/estimates')
def store_estimates():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    estimates = load_store_estimates()
    return render_template_string(STORE_ESTIMATES_LIST_TEMPLATE, estimates=estimates)

@app.route('/store/estimates/create')
def store_estimates_create():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    estimate_no = generate_estimate_number()
    today = get_bd_time().strftime('%Y-%m-%d')
    
    return render_template_string(STORE_ESTIMATE_CREATE_TEMPLATE, estimate_no=estimate_no, today=today)

@app.route('/store/estimates/save', methods=['POST'])
def store_estimates_save():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    estimates = load_store_estimates()
    
    # Parse items
    items = []
    i = 0
    while f'items[{i}][description]' in request.form:
        item = {
            "description": request.form.get(f'items[{i}][description]', ''),
            "size": request.form.get(f'items[{i}][size]', ''),
            "qty": int(request.form.get(f'items[{i}][qty]', 1) or 1),
            "price": float(request.form.get(f'items[{i}][price]', 0) or 0),
            "total": float(request.form.get(f'items[{i}][total]', 0) or 0)
        }
        items.append(item)
        i += 1
    
    estimate_date = request.form.get('estimate_date', '')
    formatted_date = estimate_date
    try:
        dt = datetime.strptime(estimate_date, '%Y-%m-%d')
        formatted_date = dt.strftime('%d-%m-%Y')
    except:
        pass
    
    valid_until = request.form.get('valid_until', '')
    formatted_valid = ''
    if valid_until:
        try:
            dt = datetime.strptime(valid_until, '%Y-%m-%d')
            formatted_valid = dt.strftime('%d-%m-%Y')
        except:
            pass
    
    new_estimate = {
        "estimate_no": request.form.get('estimate_no', ''),
        "customer_name": request.form.get('customer_name', ''),
        "customer_phone": request.form.get('customer_phone', ''),
        "customer_address": request.form.get('customer_address', ''),
        "date": formatted_date,
        "valid_until": formatted_valid,
        "items": items,
        "discount": float(request.form.get('discount', 0) or 0),
        "total": float(request.form.get('total', 0) or 0),
        "notes": request.form.get('notes', ''),
        "created_at": get_bd_date_str()
    }
    
    estimates.append(new_estimate)
    save_store_estimates(estimates)
    
    flash('Estimate created successfully!')
    
    action = request.form.get('action', 'save')
    if action == 'save_print':
        return redirect(url_for('store_estimates_print', estimate_no=new_estimate['estimate_no']))
    
    return redirect(url_for('store_estimates'))

@app.route('/store/estimates/print/<estimate_no>')
def store_estimates_print(estimate_no):
    if 'user' not in session:
        return redirect(url_for('home'))
    
    estimates = load_store_estimates()
    estimate = next((est for est in estimates if est.get('estimate_no') == estimate_no), None)
    
    if not estimate:
        flash('Estimate not found!')
        return redirect(url_for('store_estimates'))
    
    return render_template_string(STORE_ESTIMATE_PRINT_TEMPLATE, estimate=estimate)

# --- Due Collection ---
@app.route('/store/dues')
def store_dues():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoices = load_store_invoices()
    pending_dues = [inv for inv in invoices if inv.get('due', 0) > 0]
    today = get_bd_time().strftime('%Y-%m-%d')
    
    return render_template_string(
        STORE_DUE_COLLECTION_TEMPLATE,
        invoice=None,
        search_invoice='',
        pending_dues=pending_dues,
        today=today
    )

@app.route('/store/dues/search')
def store_dues_search():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoice_no = request.args.get('invoice_no', '').strip()
    invoices = load_store_invoices()
    pending_dues = [inv for inv in invoices if inv.get('due', 0) > 0]
    today = get_bd_time().strftime('%Y-%m-%d')
    
    invoice = next((inv for inv in invoices if inv.get('invoice_no', '').lower() == invoice_no.lower()), None)
    
    return render_template_string(
        STORE_DUE_COLLECTION_TEMPLATE,
        invoice=invoice,
        search_invoice=invoice_no,
        pending_dues=pending_dues,
        today=today
    )

@app.route('/store/dues/collect', methods=['POST'])
def store_dues_collect():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    invoice_no = request.form.get('invoice_no', '').strip()
    amount = float(request.form.get('amount', 0) or 0)
    payment_date = request.form.get('payment_date', '')
    notes = request.form.get('notes', '')
    
    invoices = load_store_invoices()
    
    for inv in invoices:
        if inv.get('invoice_no') == invoice_no:
            # Format date
            formatted_date = payment_date
            try:
                dt = datetime.strptime(payment_date, '%Y-%m-%d')
                formatted_date = dt.strftime('%d-%m-%Y')
            except:
                pass
            
            # Add payment record
            if 'payments' not in inv:
                inv['payments'] = []
            
            inv['payments'].append({
                "date": formatted_date,
                "amount": amount,
                "notes": notes
            })
            
            # Update paid and due
            inv['paid'] = inv.get('paid', 0) + amount
            inv['due'] = inv.get('total', 0) - inv['paid']
            if inv['due'] < 0:
                inv['due'] = 0
            
            break
    
    save_store_invoices(invoices)
    flash(f'Payment of ৳{amount:,.0f} recorded successfully!')
    
    return redirect(url_for('store_dues_search', invoice_no=invoice_no))

# ==============================================================================
# MAIN APP RUN
# ==============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
