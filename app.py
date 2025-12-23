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

# সেশন টাইমআউট কনফিগারেশন (5 মিনিট)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5) 

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
# ENHANCED CSS STYLES - PREMIUM MODERN UI (UPDATED FLASH & SEARCH)
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

        /* PROFESSIONAL FLASH MESSAGES (Updated) */
        #flash-container {
            position: fixed;
            top: 30px;
            right: 30px;
            z-index: 10001;
            width: auto;
            min-width: 300px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .flash-message {
            background: #1a1a25;
            color: white;
            padding: 16px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            border-left: 4px solid;
            animation: slideInRight 0.5s ease-out;
            border: 1px solid rgba(255,255,255,0.05);
        }

        @keyframes slideInRight {
            from { opacity: 0; transform: translateX(100%); }
            to { opacity: 1; transform: translateX(0); }
        }

        .flash-error {
            border-left-color: var(--accent-red);
            background: linear-gradient(90deg, rgba(239, 68, 68, 0.1), transparent);
        }

        .flash-success {
            border-left-color: var(--accent-green);
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.1), transparent);
        }

        .flash-info {
            border-left-color: var(--accent-blue);
            background: linear-gradient(90deg, rgba(59, 130, 246, 0.1), transparent);
        }

        /* Enhanced Forms & Search */
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

        input, select { 
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

        input::placeholder {
            color: var(--text-secondary);
            opacity: 0.5;
        }

        input:focus, select:focus { 
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
            box-shadow: 0 0 0 4px var(--accent-orange-glow);
        }
        
        /* Table Search & Filter Bar */
        .table-controls {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            background: rgba(255, 255, 255, 0.02);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }
        
        .search-box {
            flex: 1;
            position: relative;
        }
        
        .search-box i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }
        
        .search-box input {
            padding-left: 40px;
            background: #12121a;
        }

        /* Dashboard & Layout Styles */
        .header-section { 
            display: flex;
            justify-content: space-between; 
            align-items: flex-start; 
            margin-bottom: 35px;
        }

        .page-title { 
            font-size: 32px;
            font-weight: 800; 
            color: white; 
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }

        .page-subtitle { 
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 400;
        }

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
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
        }

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

        .card:hover {
            border-color: var(--border-glow);
            box-shadow: var(--shadow-glow);
            transform: translateY(-4px);
        }
        
        /* Stat Cards */
        .stat-card { 
            display: flex;
            align-items: center; 
            gap: 24px; 
            transition: var(--transition-smooth);
            cursor: pointer;
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
        }

        .stat-info h3 { 
            font-size: 36px;
            font-weight: 800; 
            margin: 0; 
            color: white;
            line-height: 1;
        }

        .stat-info p { 
            font-size: 13px;
            color: var(--text-secondary); 
            margin: 6px 0 0 0; 
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 600;
        }

        /* Buttons */
        button { 
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
        }

        button:hover { 
            transform: translateY(-3px);
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }

        /* Tables */
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
        
        /* Mobile */
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
        }

        @media (max-width: 1024px) {
            .sidebar { transform: translateX(-100%); width: 280px; } 
            .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; padding: 20px; }
            .mobile-toggle { display: flex; }
            .dashboard-grid-2 { grid-template-columns: 1fr; }
            .table-controls { flex-direction: column; }
        }
        
        /* Loading Overlay */
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
        }
        
        .spinner { 
            width: 60px;
            height: 60px; 
            border: 4px solid rgba(255, 122, 0, 0.1);
            border-top: 4px solid var(--accent-orange);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
"""
# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (MongoDB ব্যবহার করে)
# ==============================================================================

def load_users():
    """
    MongoDB থেকে ইউজার ডেটা লোড করে। যদি কোনো ডেটা না থাকে, ডিফল্ট অ্যাডমিন তৈরি করে।
    """
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
    """
    MongoDB তে ইউজার ডেটা সেভ করে।
    """
    users_col.replace_one(
        {"_id": "global_users"}, 
        {"_id": "global_users", "data": users_data}, 
        upsert=True
    )

def load_stats():
    """
    MongoDB থেকে স্ট্যাটস ডেটা লোড করে।
    """
    record = stats_col.find_one({"_id": "dashboard_stats"})
    if record:
        return record['data']
    else:
        default_stats = {"downloads": [], "last_booking": "None"}
        stats_col.insert_one({"_id": "dashboard_stats", "data": default_stats})
        return default_stats

def save_stats(data):
    """
    MongoDB তে স্ট্যাটস ডেটা সেভ করে।
    """
    stats_col.replace_one(
        {"_id": "dashboard_stats"},
        {"_id": "dashboard_stats", "data": data},
        upsert=True
    )

def update_stats(ref_no, username, type_label="Closing Report"):
    """
    সাধারণ হিস্ট্রি আপডেট ফাংশন (Closing Report এর জন্য)।
    """
    data = load_stats()
    now = get_bd_time()
    new_record = {
        "ref": ref_no,
        "user": username,
        "date": now.strftime('%d-%m-%Y'),
        "time": now.strftime('%I:%M %p'),
        "type": type_label,
        "iso_time": now.isoformat()
    }
    # লেটেস্ট এন্ট্রি শুরুতে যোগ করা
    data['downloads'].insert(0, new_record)
    # ৩০০০ রেকর্ডের বেশি হলে পুরনো ডিলিট
    if len(data['downloads']) > 3000:
        data['downloads'] = data['downloads'][:3000]
        
    data['last_booking'] = ref_no
    save_stats(data)

def update_po_stats(username, file_count, booking_ref="N/A"):
    """
    PO Sheet জেনারেশনের হিস্ট্রি আপডেট ফাংশন।
    """
    data = load_stats()
    now = get_bd_time()
    new_record = {
        "ref": booking_ref,
        "user": username,
        "file_count": file_count,
        "date": now.strftime('%d-%m-%Y'),
        "time": now.strftime('%I:%M %p'),
        "type": "PO Sheet",
        "iso_time": now.isoformat()
    }
    if 'downloads' not in data:
        data['downloads'] = []
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
# নতুন ফাংশন: সকল সেভ করা বুকিং রেফারেন্স লিস্ট (History এর জন্য)
# ==============================================================================

def get_all_accessories_bookings():
    """
    সকল সেভ করা বুকিং রেফারেন্স লিস্ট রিটার্ন করে
    """
    db_acc = load_accessories_db()
    bookings = []
    for ref, data in db_acc.items():
        challan_count = len(data.get('challans', []))
        total_qty = sum([int(c.get('qty', 0)) for c in data.get('challans', [])])
        bookings.append({
            'ref': ref,
            'buyer': data.get('buyer', 'N/A'),
            'style': data.get('style', 'N/A'),
            'challan_count': challan_count,
            'total_qty': total_qty,
            'last_updated': data.get('last_api_call', 'N/A')
        })
    
    # Sort by ref
    bookings = sorted(bookings, key=lambda x: x['ref'], reverse=True)
    return bookings

# ==============================================================================
# ড্যাশবোর্ড সামারি ফাংশন (UPDATED WITH 24H HISTORY & SEARCH)
# ==============================================================================

def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    now = get_bd_time()
    today_str = now.strftime('%d-%m-%Y')
    
    # ইউজার ডিটেইলস প্রসেসিং
    user_details = []
    for u, d in users_data.items():
        user_details.append({
            "username": u,
            "role": d.get('role', 'user'),
            "created_at": d.get('created_at', 'N/A'),
            "last_login": d.get('last_login', 'Never'),
            "last_duration": d.get('last_duration', 'N/A')
        })

    # এক্সেসরিজ ডেটা প্রসেসিং (চার্টের জন্য)
    acc_lifetime_count = 0
    acc_today_list = []
    daily_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0})
    
    # এক্সেসরিজ হিস্ট্রি ইন্টিগ্রেশন
    accessories_history_items = []

    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            acc_lifetime_count += 1
            c_date = challan.get('date')
            
            # এক্সেসরিজ এন্ট্রিকে হিস্ট্রি অবজেক্টে রূপান্তর
            acc_entry = {
                "ref": ref,
                "user": "System", # সাধারণত কে এন্ট্রি দিয়েছে তা স্টোর করা নেই, তাই ডিফল্ট
                "date": c_date,
                "time": "N/A", # চালানে সময় নেই, শুধু তারিখ আছে
                "type": "Accessories",
                "iso_time": "" # সর্টিংয়ের জন্য পরে হ্যান্ডেল করা হবে
            }
            accessories_history_items.append(acc_entry)
            
            if c_date == today_str:
                acc_today_list.append({
                    "ref": ref,
                    "buyer": data.get('buyer'),
                    "style": data.get('style'),
                    "time": "Today",
                    "qty": challan.get('qty')
                })
            
            try:
                dt_obj = datetime.strptime(c_date, '%d-%m-%Y')
                sort_key = dt_obj.strftime('%Y-%m-%d')
                daily_data[sort_key]['acc'] += 1
                daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
                
                # ISO টাইম বানানো সর্টিংয়ের জন্য (দিনের শেষে ধরা হলো)
                acc_entry['iso_time'] = dt_obj.replace(hour=23, minute=59).isoformat()
            except: 
                pass

    # অন্যান্য হিস্ট্রি ডেটা প্রসেসিং
    closing_lifetime_count = 0
    po_lifetime_count = 0
    closing_list = []
    po_list = []
    
    existing_history = stats_data.get('downloads', [])
    
    # দুটি লিস্ট মার্জ করা (Existing + Accessories)
    full_history = existing_history + accessories_history_items
    
    # সর্টিং (ISO Time অনুযায়ী, লেটেস্ট আগে)
    # যেসব ডেটায় iso_time নেই, সেগুলোকে শেষে ফেলা হবে
    full_history.sort(key=lambda x: x.get('iso_time') or '1970-01-01', reverse=True)

    # লুপ চালিয়ে কাউন্ট বের করা
    for item in existing_history:
        item_date = item.get('date', '')
        if item.get('type') == 'PO Sheet':
            po_lifetime_count += 1
            if item_date == today_str: 
                po_list.append(item)
        else:
            closing_lifetime_count += 1
            if item_date == today_str:
                closing_list.append(item)
        
        try:
            dt_obj = datetime.strptime(item_date, '%d-%m-%Y')
            sort_key = dt_obj.strftime('%Y-%m-%d')
            
            if item.get('type') == 'PO Sheet':
                daily_data[sort_key]['po'] += 1
            else: 
                daily_data[sort_key]['closing'] += 1
            daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
        except:
            pass
    
    # চার্ট ডেটা তৈরি
    first_of_last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    start_date = first_of_last_month.strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
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
        "users": {"count": len(users_data), "details": user_details},
        "accessories": {"count": acc_lifetime_count, "details": acc_today_list},
        "closing": {"count": closing_lifetime_count, "details": closing_list},
        "po": {"count": po_lifetime_count, "details": po_list},
        "chart": {
            "labels": chart_labels,
            "closing": chart_closing,
            "po": chart_po,
            "acc": chart_acc
        },
        "history": full_history  # এখন এখানে এক্সেসরিজ সহ সব হিস্ট্রি আছে
    }
    # ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PO SHEET.py থেকে হুবহু)
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

def is_color_name(text):
    text = text.strip()
    if not text:
        return False
    if re.match(r'^\d+$', text):
        return False
    if re.match(r'^\d+[,\.]\d{2}$', text):
        return False
    if is_potential_size(text):
        return False
    keywords = ['spec', 'price', 'total', 'quantity', 'amount', 'currency', 'order']
    if any(kw in text.lower() for kw in keywords):
        return False
    if not re.search(r'[a-zA-Z]', text):
        return False
    return True

def is_partial_color_name(text):
    text = text.strip()
    if not text:
        return False
    if re.match(r'^[A-Za-z\s]+$', text):
        keywords = ['spec', 'price', 'total', 'quantity', 'amount']
        if not any(kw in text.lower() for kw in keywords):
            return True
    return False

def parse_vertical_table(lines, start_idx, sizes, order_no):
    extracted_data = []
    i = start_idx
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith("Total") and i + 1 < len(lines):
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if "Quantity" in next_line or "Amount" in next_line or re.match(r'^Quantity', next_line):
                break
            if re.match(r'^\d', next_line):
                break
        
        if line and is_color_name(line):
            color_name = line
            i += 1
            
            while i < len(lines):
                next_line = lines[i].strip()
                
                if 'spec' in next_line.lower():
                    i += 1
                    break
                
                if re.match(r'^\d+$', next_line):
                    break
                
                if not next_line:
                    i += 1
                    continue
                
                if is_partial_color_name(next_line):
                    color_name = color_name + " " + next_line
                    i += 1
                else:
                    break
            
            if i < len(lines) and 'spec' in lines[i].lower():
                i += 1
            
            quantities = []
            size_idx = 0
            
            while size_idx < len(sizes) and i < len(lines):
                qty_line = lines[i].strip() if i < len(lines) else ""
                price_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                
                if qty_line and is_color_name(qty_line):
                    while size_idx < len(sizes):
                        quantities.append(0)
                        size_idx += 1
                    break
                
                if (qty_line == "" or qty_line.isspace()) and (price_line == "" or price_line.isspace()):
                    quantities.append(0)
                    size_idx += 1
                    i += 2
                    continue
                
                if re.match(r'^\d+$', qty_line):
                    quantities.append(int(qty_line))
                    size_idx += 1
                    i += 2
                    continue
                
                i += 1
            
            if quantities:
                while len(quantities) < len(sizes):
                    quantities.append(0)
                
                for idx, size in enumerate(sizes):
                    extracted_data.append({
                        'P.O NO': order_no,
                        'Color': color_name,
                        'Size': size,
                        'Quantity': quantities[idx] if idx < len(quantities) else 0
                    })
            
            continue
        
        i += 1
    
    return extracted_data

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
            
            for i, line in enumerate(lines):
                if ("Colo" in line or "Size" in line) and "Total" in line:
                    parts = line.split()
                    try:
                        total_idx = [idx for idx, x in enumerate(parts) if 'Total' in x][0]
                        raw_sizes = parts[:total_idx]
                        sizes = [s for s in raw_sizes if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/", "Size's"]]
                        
                        valid_size_count = sum(1 for s in sizes if is_potential_size(s))
                        if sizes and valid_size_count >= len(sizes) / 2:
                            data = parse_vertical_table(lines, i + 1, sizes, order_no)
                            extracted_data.extend(data)
                    except: 
                        pass
                    break
                    
    except Exception as e: 
        print(f"Error processing file: {e}")
    
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
   
    for year in ['2025', '2024', '2023']: 
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
# CLOSING REPORT PREVIEW TEMPLATE (TRANSPOSED VERSION)
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
        body { background-color: #f8f9fa; padding: 30px 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 1.0rem; }
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
        
        /* Table Styles */
        .table-card { background: white; border-radius: 0; margin-bottom: 30px; border: none; overflow-x: auto; }
        .color-header { background-color: #2c3e50 !important; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; text-transform: uppercase; border: 1px solid #000;}
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; font-size: 0.95rem; }
        
        .table th, .table td { text-align: center; vertical-align: middle; border: 1px solid #000; padding: 8px 10px; color: #000; font-weight: 600; }
        
        /* First Column (Metric Names) */
        .table td:first-child { 
            text-align: left; 
            font-weight: 800; 
            background-color: #f1f2e8; 
            width: 180px; 
            white-space: nowrap;
        }
        
        /* Header Row (Sizes) */
        .table thead th { 
            background-color: #fff !important; 
            color: #000 !important; 
            font-weight: 900; 
            font-size: 1.1rem;
        }
        
        /* Special Row Styling */
        .row-3pct { background-color: #B9C2DF !important; }
        .row-3pct td:not(:first-child) { background-color: #B9C2DF !important; }
        
        .row-input { background-color: #C4D09D !important; }
        .row-input td:not(:first-child) { background-color: #C4D09D !important; }
        
        .row-balance td:not(:first-child) { font-weight: 700; color: #c0392b; }
        
        /* Last Column (Total) */
        .col-total { font-weight: 900 !important; background-color: #e8f6f3; }
        
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 15px; position: sticky; top: 0; z-index: 1000; background: #f8f9fa; padding: 10px 0; }
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; border: none; }
        .btn-excel { background-color: #27ae60; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; text-decoration: none; display: inline-block; }
        .btn-excel:hover { color: white; background-color: #219150; }
        .footer-credit { text-align: center; margin-top: 40px; margin-bottom: 20px; font-size: 1rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #000; font-weight: 600;}
        
        @media print {
            @page { margin: 5mm; size: landscape; }
            body { background-color: white; padding: 0; }
            .container { max-width: 100% !important; width: 100%; }
            .no-print { display: none !important; }
            .action-bar { display: none; }
            .table th, .table td { border: 1px solid #000 !important; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important;}
            .row-3pct td { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .row-input td { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            .booking-box { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important; border: 1px solid #000;}
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
                        <th style="text-align: left; background-color: #f1f2e8 !important;">METRICS</th>
                        {% for size in block.headers %}
                            <th>{{ size }}</th>
                        {% endfor %}
                        <th class="col-total">TOTAL</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Calculation Logic -->
                    {% set ns = namespace(tot_3=0, tot_act=0, tot_cut=0, tot_inp=0, tot_bal=0, tot_sp=0) %}
                    {% set data_3pct = [] %}
                    {% set data_actual = [] %}
                    {% set data_cut = [] %}
                    {% set data_inp = [] %}
                    {% set data_bal = [] %}
                    {% set data_sp = [] %}
                    {% set data_pct = [] %}
                    
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
                        
                        <!-- Append to lists -->
                        {% set _ = data_3pct.append(qty_3) %}
                        {% set _ = data_actual.append(actual) %}
                        {% set _ = data_cut.append(cut_qc) %}
                        {% set _ = data_inp.append(inp_qty) %}
                        {% set _ = data_bal.append(balance) %}
                        {% set _ = data_sp.append(short_plus) %}
                        {% set _ = data_pct.append(percentage) %}
                    {% endfor %}

                    <!-- Render Transposed Rows -->
                    <tr class="row-3pct">
                        <td>ORDER QTY 3%</td>
                        {% for val in data_3pct %} <td>{{ val }}</td> {% endfor %}
                        <td class="col-total">{{ ns.tot_3 }}</td>
                    </tr>
                    <tr>
                        <td>ACTUAL QTY</td>
                        {% for val in data_actual %} <td>{{ val }}</td> {% endfor %}
                        <td class="col-total">{{ ns.tot_act }}</td>
                    </tr>
                    <tr>
                        <td>CUTTING QC</td>
                        {% for val in data_cut %} <td>{{ val }}</td> {% endfor %}
                        <td class="col-total">{{ ns.tot_cut }}</td>
                    </tr>
                    <tr class="row-input">
                        <td>INPUT QTY</td>
                        {% for val in data_inp %} <td>{{ val }}</td> {% endfor %}
                        <td class="col-total">{{ ns.tot_inp }}</td>
                    </tr>
                    <tr class="row-balance">
                        <td>BALANCE</td>
                        {% for val in data_bal %} <td>{{ val }}</td> {% endfor %}
                        <td class="col-total">{{ ns.tot_bal }}</td>
                    </tr>
                    <tr>
                        <td>SHORT/PLUS</td>
                        {% for val in data_sp %} 
                            <td style="color: {{ 'green' if val >= 0 else 'red' }}">{{ val }}</td> 
                        {% endfor %}
                        <td class="col-total">{{ ns.tot_sp }}</td>
                    </tr>
                    <tr>
                        <td>PERCENTAGE %</td>
                        {% for val in data_pct %} 
                            <td>{{ "%.2f"|format(val) }}%</td> 
                        {% endfor %}
                        <td class="col-total">
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
# ==============================================================================
# ACCESSORIES REPORT TEMPLATE
# ==============================================================================

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
                        <form action="/admin/accessories/delete" method="POST" style="display: inline;" onsubmit="return confirm('Delete this challan?');">
                            <input type="hidden" name="ref" value="{{ ref }}">
                            <input type="hidden" name="index" value="{{ loop.index0 }}">
                            <button type="submit" class="action-btn btn-del-row" style="border: none; cursor: pointer;"><i class="fas fa-trash"></i></button>
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

# ==============================================================================
# PO REPORT TEMPLATE (HUBUHU FROM PO SHEET.py)
# ==============================================================================

PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PO Report - Cotton Clothing BD</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #1e40af;
            --primary-light: #3b82f6;
            --dark: #0f172a;
            --dark-light: #1e293b;
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-600: #475569;
            --gray-800: #1e293b;
            --success: #059669;
            --success-light: #d1fae5;
            --warning: #d97706;
            --warning-light: #fef3c7;
        }
        
        * { font-family: 'Inter', sans-serif; }
        
        body { 
            background: var(--gray-100);
            min-height: 100vh;
            padding: 30px 0; 
        }
        
        .container { max-width: 1200px; }
        
        /* ===== HEADER ===== */
        .company-header { 
            background: white;
            border-radius: 12px;
            padding: 24px 32px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid var(--primary);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .company-name { 
            font-size: 1.5rem; 
            font-weight: 800; 
            color: var(--dark);
            letter-spacing: -0.5px;
            margin-bottom: 4px;
        }
        
        .report-title { 
            font-size: 0.85rem; 
            color: var(--gray-600);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .date-box {
            text-align: right;
        }
        
        .date-label {
            font-size: 0.7rem;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }
        
        .date-value {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--dark);
        }
        
        /* ===== INFO SECTION ===== */
        .info-section {
            display: grid;
            grid-template-columns: 1fr 220px;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .info-grid { 
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        
        .info-item {
            padding: 12px 16px;
            background: var(--gray-50);
            border-radius: 8px;
            border-left: 3px solid var(--primary-light);
        }
        
        /* Booking Item Highlight */
        .info-item.booking-highlight {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-left: 4px solid #f59e0b;
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.25);
        }
        
        .info-item.booking-highlight .info-value {
            color: #92400e;
            font-size: 1.05rem;
        }
        
        .info-label { 
            font-size: 0.65rem;
            font-weight: 700;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        
        .info-value { 
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--dark);
        }

        .grand-total-box { 
            background: linear-gradient(135deg, var(--dark) 0%, var(--dark-light) 100%);
            color: white; 
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .grand-total-label { 
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: 600;
            opacity: 0.8;
            margin-bottom: 8px;
        }
        
        .grand-total-value { 
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1;
        }
        
        .grand-total-unit {
            font-size: 0.75rem;
            opacity: 0.7;
            margin-top: 6px;
            font-weight: 500;
        }

        /* ===== TABLE ===== */
        .table-card { 
            background: white;
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .color-header { 
            background: var(--dark);
            color: white;
            padding: 14px 20px;
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .table { 
            margin-bottom: 0; 
            width: 100%;
        }
        
        .table th { 
            background: var(--gray-100);
            color: var(--gray-800);
            font-weight: 700;
            font-size: 0.75rem;
            text-align: center;
            padding: 12px 10px;
            border-bottom: 2px solid var(--gray-200);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .table td { 
            text-align: center;
            vertical-align: middle;
            padding: 12px 10px;
            color: var(--dark);
            font-weight: 600;
            font-size: 0.9rem;
            border-bottom: 1px solid var(--gray-200);
        }
        
        .table tbody tr:hover td {
            background: var(--gray-50);
        }
        
        .order-col { 
            font-weight: 800 !important;
            background: var(--gray-50) !important;
            color: var(--primary) !important;
            border-right: 2px solid var(--gray-200) !important;
        }
        
        .total-col { 
            font-weight: 800 !important;
            background: var(--success-light) !important;
            color: var(--success) !important;
            border-left: 2px solid #a7f3d0 !important;
        }
        
        .total-col-header { 
            background: var(--success-light) !important;
            color: var(--success) !important;
            font-weight: 800 !important;
            border-left: 2px solid #a7f3d0 !important;
        }

        /* ===== SUMMARY ROWS ===== */
        .table tbody tr.summary-row td { 
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
            color: #92400e !important;
            font-weight: 800 !important;
            font-size: 1.0rem !important;
            border-top: 3px solid #f59e0b !important;
            border-bottom: 1px solid #fbbf24 !important;
            padding: 14px 10px !important;
        }
        
        .table tbody tr.summary-row:last-child td {
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
            color: #1e40af !important;
            font-weight: 800 !important;
            font-size: 1.0rem !important;
            border-top: 3px solid #3b82f6 !important;
            border-bottom: none !important;
        }
        
        .summary-label { 
            text-align: right !important;
            padding-right: 20px !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 800 !important;
        }

        /* ===== ACTION BAR ===== */
        .action-bar { 
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .btn-back {
            background: white;
            color: var(--dark);
            border: 2px solid var(--gray-200);
            border-radius: 8px;
            padding: 10px 24px;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        
        .btn-back:hover {
            border-color: var(--primary-light);
            color: var(--primary);
        }
        
        .btn-print { 
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 28px;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(30, 64, 175, 0.3);
        }
        
        .btn-print:hover {
            background: var(--primary-light);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(30, 64, 175, 0.4);
        }
        
        /* ===== FOOTER ===== */
        .footer-credit { 
            text-align: center;
            margin-top: 30px;
            padding: 16px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            font-size: 0.85rem;
            color: var(--gray-600);
        }
        
        .footer-credit strong {
            color: var(--primary);
        }

        /* ===== PRINT ===== */
        @media print {
            @page { 
                margin: 10mm;
                size: portrait;
            }
            
            body { 
                background: white !important;
                padding: 0 !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }
            
            .container { 
                max-width: 100% !important;
                padding: 0 !important;
            }
            
            .no-print { display: none !important; }
            
            .company-header {
                border-radius: 0 !important;
                box-shadow: none !important;
                border: 1px solid #000 !important;
                border-left: 4px solid #000 !important;
                margin-bottom: 10px !important;
                padding: 15px 20px !important;
            }
            
            .company-name {
                font-size: 1.3rem !important;
            }
            
            .info-section {
                margin-bottom: 10px !important;
            }
            
            .info-grid {
                border-radius: 0 !important;
                box-shadow: none !important;
                border: 1px solid #000 !important;
                padding: 15px !important;
            }
            
            .info-item {
                border-left: 3px solid #000 !important;
            }
            
            .info-item.booking-highlight {
                background: #fff8dc !important;
                border-left: 4px solid #000 !important;
            }
            
            .grand-total-box {
                border-radius: 0 !important;
                box-shadow: none !important;
                border: 2px solid #000 !important;
                background: #f0f0f0 !important;
                color: #000 !important;
            }
            
            .grand-total-box * {
                color: #000 !important;
            }
            
            .table-card {
                border-radius: 0 !important;
                box-shadow: none !important;
                border: 1px solid #000 !important;
                margin-bottom: 10px !important;
                break-inside: avoid;
            }
            
            .color-header {
                background: #e0e0e0 !important;
                color: #000 !important;
                padding: 10px 15px !important;
                font-size: 11pt !important;
            }
            
            .table th {
                background: #f5f5f5 !important;
                color: #000 !important;
                font-size: 9pt !important;
                padding: 8px 6px !important;
                border: 1px solid #000 !important;
            }
            
            .table td {
                font-size: 10pt !important;
                padding: 8px 6px !important;
                border: 1px solid #000 !important;
            }
            
            .order-col {
                background: #f8f8f8 !important;
                color: #000 !important;
            }
            
            .total-col,
            .total-col-header {
                background: #e8f5e9 !important;
                color: #000 !important;
            }
            
            .summary-row td {
                font-size: 10.5pt !important;
                font-weight: 800 !important;
                border-top: 2px solid #000 !important;
            }
            
            .summary-row:first-of-type td {
                background: #fff8e1 !important;
                color: #000 !important;
            }
            
            .summary-row:last-of-type td {
                background: #e3f2fd !important;
                color: #000 !important;
            }
            
            .footer-credit {
                border-radius: 0 !important;
                box-shadow: none !important;
                border-top: 1px solid #000 !important;
                margin-top: 15px !important;
                padding: 10px !important;
                background: transparent !important;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn-back">← Back</a>
            <button onclick="window.print()" class="btn-print">Print Report</button>
        </div>

        <div class="company-header">
            <div class="header-content">
                <div>
                    <div class="company-name">Cotton Clothing BD Limited</div>
                    <div class="report-title">Purchase Order Summary Report</div>
                </div>
                <div class="date-box">
                    <div class="date-label">Report Date</div>
                    <div class="date-value" id="date"></div>
                </div>
            </div>
        </div>

        {% if message %}
            <div class="alert alert-warning text-center no-print">{{ message }}</div>
        {% endif %}

        {% if tables %}
            <div class="info-section">
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Buyer</div>
                        <div class="info-value">{{ meta.buyer }}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Season</div>
                        <div class="info-value">{{ meta.season }}</div>
                    </div>
                    <div class="info-item booking-highlight">
                        <div class="info-label">Booking No</div>
                        <div class="info-value">{{ meta.booking }}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Department</div>
                        <div class="info-value">{{ meta.dept }}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Style</div>
                        <div class="info-value">{{ meta.style }}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Item</div>
                        <div class="info-value">{{ meta.item }}</div>
                    </div>
                </div>
                
                <div class="grand-total-box">
                    <div class="grand-total-label">Grand Total</div>
                    <div class="grand-total-value">{{ grand_total }}</div>
                    <div class="grand-total-unit">Pieces</div>
                </div>
            </div>

            {% for item in tables %}
                <div class="table-card">
                    <div class="color-header">Color: {{ item.color }}</div>
                    <div class="table-responsive">
                        {{ item.table | safe }}
                    </div>
                </div>
            {% endfor %}
            
            <div class="footer-credit">
                Report Generated by <strong>Mehedi Hasan</strong>
            </div>
        {% endif %}
    </div>

    <script>
        const d = new Date();
        document.getElementById('date').innerText = 
            String(d.getDate()).padStart(2,'0') + '-' + 
            String(d.getMonth()+1).padStart(2,'0') + '-' + 
            d.getFullYear();
    </script>
</body>
</html>
"""

# ==============================================================================
# LOGIN TEMPLATE
# ==============================================================================

LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Login - MNM Software</title>
    {COMMON_STYLES}
    <style>
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }}
        
        body {{
            background: var(--bg-body);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            overflow-y: auto;
        }}
        
        .bg-orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: orbFloat 20s ease-in-out infinite;
            pointer-events: none;
        }}
        
        .orb-1 {{
            width: 300px;
            height: 300px;
            background: var(--accent-orange);
            top: -100px;
            left: -100px;
            animation-delay: 0s;
        }}
        
        .orb-2 {{
            width: 250px;
            height: 250px;
            background: var(--accent-purple);
            bottom: -50px;
            right: -50px;
            animation-delay: -5s;
        }}
        
        .orb-3 {{
            width: 150px;
            height: 150px;
            background: var(--accent-green);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            animation-delay: -10s;
        }}
        
        @keyframes orbFloat {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            25% {{ transform: translate(30px, -30px) scale(1.05); }}
            50% {{ transform: translate(-20px, 20px) scale(0.95); }}
            75% {{ transform: translate(15px, 30px) scale(1.02); }}
        }}
        
        .login-container {{
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
        }}
        
        .login-card {{
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px 35px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            animation: loginCardAppear 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        @keyframes loginCardAppear {{
            from {{
                opacity: 0;
                transform: translateY(30px) scale(0.95);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}
        
        .brand-section {{
            text-align: center;
            margin-bottom: 35px;
        }}
        
        .brand-icon {{
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
        }}
        
        @keyframes brandIconPulse {{
            0%, 100% {{ transform: scale(1) rotate(0deg); box-shadow: 0 15px 40px var(--accent-orange-glow); }}
            50% {{ transform: scale(1.05) rotate(5deg); box-shadow: 0 20px 50px var(--accent-orange-glow); }}
        }}
        
        .brand-name {{
            font-size: 28px;
            font-weight: 900;
            color: white;
            letter-spacing: -1px;
        }}
        
        .brand-name span {{
            background: var(--gradient-orange);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .brand-tagline {{
            color: var(--text-secondary);
            font-size: 11px;
            letter-spacing: 2px;
            margin-top: 6px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .login-form .input-group {{
            margin-bottom: 20px;
        }}
        
        .login-form .input-group label {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        
        .login-form .input-group label i {{
            color: var(--accent-orange);
            font-size: 13px;
        }}
        
        .login-form input {{
            padding: 14px 18px;
            font-size: 14px;
            border-radius: 12px;
        }}
        
        .login-btn {{
            margin-top: 8px;
            padding: 14px 24px;
            font-size: 15px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .login-btn i {{
            transition: transform 0.3s;
        }}
        
        .login-btn:hover i {{
            transform: translateX(5px);
        }}
        
        .footer-credit {{
            text-align: center;
            margin-top: 25px;
            color: var(--text-secondary);
            font-size: 11px;
            opacity: 0.5;
            font-weight: 500;
        }}
        
        .footer-credit a {{
            color: var(--accent-orange);
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>
    
    <!-- Updated Flash Container -->
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category if category != 'message' else 'info' }}}}">
                        {{{{ message }}}}
                    </div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>

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
            
            <div class="footer-credit">
                © 2025 <a href="#">Mehedi Hasan</a> • All Rights Reserved
            </div>
        </div>
    </div>
    
    <script>
        // Auto-hide flash messages
        setTimeout(function() {{
            let flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(function(msg) {{
                msg.style.opacity = '0';
                setTimeout(function() {{ msg.style.display = 'none'; }}, 500);
            }});
        }}, 4000);
    </script>
</body>
</html>
"""
# ==============================================================================
# MAIN DASHBOARD TEMPLATE (ADMIN & USER)
# ==============================================================================

DASHBOARD_TEMPLATE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>MNM Production Dashboard</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="particles-js"></div>
    <div class="animated-bg"></div>
    
    <!-- Loading Overlay -->
    <div id="loading-overlay">
        <div class="spinner"></div>
        <h3 style="color:white; margin-top:20px; font-weight:300;">Processing Request...</h3>
    </div>

    <!-- Flash Messages -->
    <div id="flash-container">
        {{% with messages = get_flashed_messages(with_categories=true) %}}
            {{% if messages %}}
                {{% for category, message in messages %}}
                    <div class="flash-message flash-{{{{ category if category != 'message' else 'info' }}}}">
                        {{{{ message }}}}
                    </div>
                {{% endfor %}}
            {{% endif %}}
        {{% endwith %}}
    </div>

    <!-- Sidebar -->
    <div class="sidebar" id="sidebar">
        <div class="brand-logo">
            <i class="fas fa-layer-group"></i>
            <div>MNM<span>Pro</span></div>
        </div>
        
        <div class="nav-menu">
            <div class="nav-item">
                <a href="/" class="nav-link active">
                    <i class="fas fa-home"></i> Dashboard
                </a>
            </div>
            
            {{% if 'closing' in permissions %}}
            <div class="nav-item">
                <a href="#closing-section" class="nav-link" onclick="showSection('closing')">
                    <i class="fas fa-file-invoice"></i> Closing Report
                </a>
            </div>
            {{% endif %}}
            
            {{% if 'po_sheet' in permissions %}}
            <div class="nav-item">
                <a href="#po-section" class="nav-link" onclick="showSection('po')">
                    <i class="fas fa-file-pdf"></i> PO Sheet Parser
                </a>
            </div>
            {{% endif %}}

            {{% if 'accessories' in permissions %}}
            <div class="nav-item">
                <a href="#accessories-section" class="nav-link" onclick="showSection('accessories')">
                    <i class="fas fa-box-open"></i> Accessories
                    <span class="nav-badge">{{{{ summary.accessories.count }}}}</span>
                </a>
            </div>
            {{% endif %}}
            
            {{% if session.role == 'admin' %}}
            <div class="nav-item">
                <a href="#users-section" class="nav-link" onclick="showSection('users')">
                    <i class="fas fa-users-cog"></i> User Management
                </a>
            </div>
            {{% endif %}}
        </div>
        
        <div class="sidebar-footer">
            Logged in as: <strong>{{{{ session.username }}}}</strong><br>
            <a href="/logout" style="color: var(--accent-red); text-decoration: none; font-weight: 700; margin-top: 10px; display: inline-block;">
                <i class="fas fa-sign-out-alt"></i> Logout
            </a>
        </div>
    </div>

    <button class="mobile-toggle" onclick="document.getElementById('sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </button>

    <!-- Main Content -->
    <div class="main-content">
        <!-- Dashboard Home Section -->
        <div id="dashboard-section">
            <div class="header-section">
                <div>
                    <div class="page-title">Dashboard Overview</div>
                    <div class="page-subtitle">Welcome back, {{{{ session.username }}}}</div>
                </div>
                <div class="status-badge">
                    <div class="status-dot"></div> System Active
                </div>
            </div>

            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="card stat-card">
                    <div class="stat-icon"><i class="fas fa-file-invoice"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ summary.closing.count }}}}</h3>
                        <p>Closing Reports</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="color: var(--accent-purple); background: rgba(139, 92, 246, 0.1);"><i class="fas fa-file-pdf"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ summary.po.count }}}}</h3>
                        <p>PO Sheets Processed</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="color: var(--accent-cyan); background: rgba(6, 182, 212, 0.1);"><i class="fas fa-users"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ summary.users.count }}}}</h3>
                        <p>Active Users</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="color: var(--accent-green); background: rgba(16, 185, 129, 0.1);"><i class="fas fa-box"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ summary.accessories.count }}}}</h3>
                        <p>Accessories Challans</p>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid-2">
                <!-- Activity Chart -->
                <div class="card">
                    <div class="page-title" style="font-size: 20px; margin-bottom: 20px;">Production Analytics</div>
                    <canvas id="activityChart" height="150"></canvas>
                </div>

                <!-- Recent History (Last 24h & Search) -->
                <div class="card" style="max-height: 500px; display: flex; flex-direction: column;">
                    <div class="page-title" style="font-size: 20px; margin-bottom: 15px;">Recent Activity</div>
                    
                    <!-- Search & Filter Controls -->
                    <div class="table-controls" style="padding: 10px; margin-bottom: 10px;">
                        <div class="search-box">
                            <i class="fas fa-search"></i>
                            <input type="text" id="historySearch" placeholder="Search ref, user..." onkeyup="filterHistory()">
                        </div>
                        <select id="historyFilter" onchange="filterHistory()" style="width: auto; padding: 10px;">
                            <option value="all">All Types</option>
                            <option value="Closing Report">Closing</option>
                            <option value="PO Sheet">PO Sheet</option>
                            <option value="Accessories">Accessories</option>
                        </select>
                    </div>

                    <div style="overflow-y: auto; flex-grow: 1;">
                        <table class="dark-table" id="historyTable">
                            <thead>
                                <tr>
                                    <th>Ref / Booking</th>
                                    <th>Type</th>
                                    <th>User</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {{% for item in summary.history %}}
                                <tr>
                                    <td style="font-weight: 700; color: white;">{{{{ item.ref }}}}</td>
                                    <td>
                                        <span class="table-badge" 
                                              style="color: {{{{ 'var(--accent-orange)' if item.type == 'Closing Report' else ('var(--accent-purple)' if item.type == 'PO Sheet' else 'var(--accent-green)') }}}};">
                                            {{{{ item.type }}}}
                                        </span>
                                    </td>
                                    <td style="color: var(--text-secondary);">{{{{ item.user }}}}</td>
                                    <td style="font-size: 11px; opacity: 0.7;">
                                        {{{{ item.time }}}}<br>
                                        <span style="font-size: 9px;">{{{{ item.date }}}}</span>
                                    </td>
                                </tr>
                                {{% endfor %}}
                            </tbody>
                        </table>
                        
                        <!-- No Data Message -->
                        <div id="noDataMessage" style="display: none; text-align: center; padding: 20px; color: var(--text-secondary);">
                            No matching records found.
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Closing Report Section -->
        <div id="closing-section" style="display: none;">
            <div class="header-section">
                <div>
                    <div class="page-title">Closing Report Generator</div>
                    <div class="page-subtitle">Automated ERP data extraction & formatting</div>
                </div>
            </div>
            
            <div class="card" style="max-width: 600px; margin: 0 auto;">
                <form action="/generate_closing" method="post" onsubmit="showLoading()">
                    <div class="input-group">
                        <label>Booking Reference No</label>
                        <input type="text" name="ref_no" required placeholder="e.g. UFL-2024-1234" style="font-size: 18px;">
                    </div>
                    <button type="submit">
                        <i class="fas fa-magic"></i> Generate Report
                    </button>
                </form>
            </div>
        </div>

        <!-- PO Sheet Section -->
        <div id="po-section" style="display: none;">
            <div class="header-section">
                <div>
                    <div class="page-title">PO Sheet Parser</div>
                    <div class="page-subtitle">Extract structured data from PDF orders</div>
                </div>
            </div>

            <div class="card" style="max-width: 600px; margin: 0 auto;">
                <form action="/upload_po" method="post" enctype="multipart/form-data" onsubmit="showLoading()">
                    <div class="input-group">
                        <label>Select PDF Files (Multiple Allowed)</label>
                        <input type="file" name="files" multiple accept=".pdf" required 
                               style="padding: 30px; border: 2px dashed var(--border-color); text-align: center;">
                    </div>
                    <button type="submit" style="background: linear-gradient(135deg, var(--accent-purple) 0%, #6D28D9 100%);">
                        <i class="fas fa-cogs"></i> Process PDFs
                    </button>
                </form>
            </div>
        </div>

        <!-- User Management Section (Admin Only) -->
        {{% if session.role == 'admin' %}}
        <div id="users-section" style="display: none;">
            <div class="header-section">
                <div>
                    <div class="page-title">User Management</div>
                    <div class="page-subtitle">Manage access and permissions</div>
                </div>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <h3 style="margin-bottom: 20px;">Create New User</h3>
                    <form action="/create_user" method="post">
                        <div class="input-group">
                            <label>Username</label>
                            <input type="text" name="new_username" required>
                        </div>
                        <div class="input-group">
                            <label>Password</label>
                            <input type="password" name="new_password" required>
                        </div>
                        <div class="input-group">
                            <label>Role</label>
                            <select name="role">
                                <option value="user">Standard User</option>
                                <option value="admin">Administrator</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Permissions</label>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                                    <input type="checkbox" name="perms" value="closing" checked style="width: auto;"> Closing Report
                                </label>
                                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                                    <input type="checkbox" name="perms" value="po_sheet" checked style="width: auto;"> PO Parser
                                </label>
                                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px;">
                                    <input type="checkbox" name="perms" value="accessories" checked style="width: auto;"> Accessories
                                </label>
                            </div>
                        </div>
                        <button type="submit" style="background: var(--accent-green);">Create User</button>
                    </form>
                </div>

                <div class="card">
                    <h3 style="margin-bottom: 20px;">Existing Users</h3>
                    <div style="overflow-y: auto; max-height: 400px;">
                        <table class="dark-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Role</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {{% for u in summary.users.details %}}
                                <tr>
                                    <td>{{{{ u.username }}}}</td>
                                    <td>
                                        <span class="table-badge" style="background: {{{{ 'var(--accent-red)' if u.role == 'admin' else 'var(--accent-blue)' }}}};">
                                            {{{{ u.role }}}}
                                        </span>
                                    </td>
                                    <td>
                                        {{% if u.username != 'Admin' %}}
                                        <form action="/delete_user" method="post" onsubmit="return confirm('Delete user?');">
                                            <input type="hidden" name="username" value="{{{{ u.username }}}}">
                                            <button type="submit" style="padding: 5px 10px; font-size: 12px; background: var(--accent-red); width: auto;">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                        {{% endif %}}
                                    </td>
                                </tr>
                                {{% endfor %}}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        {{% endif %}}
"""
# ==============================================================================
# JAVASCRIPT FOR DASHBOARD (Chart & Interaction)
# ==============================================================================

DASHBOARD_SCRIPT = """
<script>
    // Initialize Particles
    particlesJS('particles-js', {
        particles: {
            number: { value: 60, density: { enable: true, value_area: 800 } },
            color: { value: '#ffffff' },
            opacity: { value: 0.1, random: false },
            size: { value: 3, random: true },
            line_linked: { enable: true, distance: 150, color: '#ffffff', opacity: 0.1, width: 1 },
            move: { enable: true, speed: 2 }
        }
    });

    // Chart Configuration
    const ctx = document.getElementById('activityChart').getContext('2d');
    const chartData = {
        labels: {{ summary.chart.labels | tojson }},
        datasets: [
            {
                label: 'Closing Reports',
                data: {{ summary.chart.closing | tojson }},
                borderColor: '#FF7A00',
                backgroundColor: 'rgba(255, 122, 0, 0.1)',
                tension: 0.4, fill: true
            },
            {
                label: 'PO Sheets',
                data: {{ summary.chart.po | tojson }},
                borderColor: '#8B5CF6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                tension: 0.4, fill: true
            },
            {
                label: 'Accessories',
                data: {{ summary.chart.acc | tojson }},
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4, fill: true
            }
        ]
    };

    new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#8b8b9e' } }
            },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8b8b9e' } },
                x: { grid: { display: false }, ticks: { color: '#8b8b9e' } }
            }
        }
    });

    // Section Navigation
    function showSection(sectionId) {
        document.querySelectorAll('.main-content > div').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
        
        const target = sectionId === 'dashboard' ? 'dashboard-section' : 
                      sectionId === 'closing' ? 'closing-section' : 
                      sectionId === 'po' ? 'po-section' : 
                      sectionId === 'accessories' ? 'accessories-section' : 
                      sectionId === 'users' ? 'users-section' : 'dashboard-section';
                      
        document.getElementById(target).style.display = 'block';
        event.currentTarget.classList.add('active');
        
        // Hide sidebar on mobile after click
        if (window.innerWidth <= 1024) {
            document.getElementById('sidebar').classList.remove('active');
        }
    }

    // Search & Filter Logic
    function filterHistory() {
        const searchText = document.getElementById('historySearch').value.toLowerCase();
        const filterType = document.getElementById('historyFilter').value;
        const rows = document.querySelectorAll('#historyTable tbody tr');
        let hasVisible = false;

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            const typeBadge = row.querySelector('.table-badge').innerText;
            
            const matchesSearch = text.includes(searchText);
            const matchesType = filterType === 'all' || typeBadge === filterType;

            if (matchesSearch && matchesType) {
                row.style.display = '';
                hasVisible = true;
            } else {
                row.style.display = 'none';
            }
        });
        
        document.getElementById('noDataMessage').style.display = hasVisible ? 'none' : 'block';
    }

    function showLoading() {
        document.getElementById('loading-overlay').style.display = 'flex';
    }
    
    // Auto-hide Flash Messages
    setTimeout(() => {
        const flashes = document.querySelectorAll('.flash-message');
        flashes.forEach(f => {
            f.style.opacity = '0';
            setTimeout(() => f.remove(), 500);
        });
    }, 4000);
</script>
</body>
</html>
"""

# ==============================================================================
# FLASK ROUTES
# ==============================================================================

@app.before_request
def check_session():
    if request.endpoint not in ['login', 'static'] and 'username' not in session:
        return render_template_string(LOGIN_TEMPLATE)
    session.permanent = True

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    users_db = load_users()
    
    if username in users_db and users_db[username]['password'] == password:
        session['username'] = username
        session['role'] = users_db[username]['role']
        
        # Update Login Time
        now = get_bd_time()
        users_db[username]['last_login'] = now.strftime('%d-%m-%Y %I:%M %p')
        save_users(users_db)
        
        flash("Welcome back! Login successful.", "success")
        return redirect(url_for('dashboard'))
    
    flash("Invalid credentials provided.", "error")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    # Calculate duration
    if 'username' in session:
        user = session['username']
        users_db = load_users()
        if user in users_db:
            last_login = users_db[user].get('last_login')
            if last_login != 'Never':
                try:
                    login_dt = datetime.strptime(last_login, '%d-%m-%Y %I:%M %p')
                    logout_dt = get_bd_time()
                    duration = logout_dt - login_dt
                    minutes = int(duration.total_seconds() / 60)
                    users_db[user]['last_duration'] = f"{minutes} mins"
                    save_users(users_db)
                except: pass

    session.clear()
    flash("You have been logged out securely.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    users_db = load_users()
    permissions = users_db.get(session['username'], {}).get('permissions', [])
    summary_data = get_dashboard_summary_v2()
    
    return render_template_string(
        DASHBOARD_TEMPLATE + DASHBOARD_SCRIPT, 
        permissions=permissions,
        summary=summary_data
    )

# --------------------------
# CLOSING REPORT ROUTES
# --------------------------
@app.route('/generate_closing', methods=['POST'])
def generate_closing():
    ref_no = request.form.get('ref_no', '').strip()
    users_db = load_users()
    perms = users_db.get(session['username'], {}).get('permissions', [])
    
    if 'closing' not in perms:
        flash("Access Denied: You do not have permission for Closing Reports.", "error")
        return redirect(url_for('dashboard'))

    if not ref_no:
        flash("Reference Number is required.", "error")
        return redirect(url_for('dashboard'))

    try:
        report_data = fetch_closing_report_data(ref_no)
        if report_data:
            update_stats(ref_no, session['username'], "Closing Report")
            return render_template_string(CLOSING_REPORT_PREVIEW_TEMPLATE, report_data=report_data, ref_no=ref_no)
        else:
            flash(f"Data not found for Ref: {ref_no}", "error")
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"System Error: {str(e)}", "error")
        return redirect(url_for('dashboard'))

@app.route('/download-closing-excel')
def download_closing_excel():
    ref_no = request.args.get('ref_no')
    if not ref_no: return redirect(url_for('dashboard'))
    
    report_data = fetch_closing_report_data(ref_no)
    if not report_data:
        flash("Data expired. Please generate report again.", "error")
        return redirect(url_for('dashboard'))
        
    excel_file = create_formatted_excel_report(report_data, ref_no)
    if excel_file:
        response = make_response(excel_file.read())
        response.headers['Content-Disposition'] = f'attachment; filename=Closing_Report_{ref_no}.xlsx'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response
    return redirect(url_for('dashboard'))

# --------------------------
# PO SHEET ROUTES (EXACT LOGIC FROM UPLOADED FILE)
# --------------------------
@app.route('/upload_po', methods=['POST'])
def upload_po():
    users_db = load_users()
    perms = users_db.get(session['username'], {}).get('permissions', [])
    
    if 'po_sheet' not in perms:
        flash("Access Denied: Permission restricted.", "error")
        return redirect(url_for('dashboard'))

    if 'files' not in request.files:
        flash("No files uploaded.", "error")
        return redirect(url_for('dashboard'))
    
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        flash("No files selected.", "error")
        return redirect(url_for('dashboard'))

    all_data = []
    final_meta = {}
    
    try:
        # প্রসেসিং শুরু
        for file in files:
            if file and file.filename.endswith('.pdf'):
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(temp_path)
                
                extracted, meta = extract_data_dynamic(temp_path)
                if extracted:
                    all_data.extend(extracted)
                if meta['buyer'] != 'N/A':
                    final_meta = meta 
                
                os.remove(temp_path) # ক্লিনআপ

        if not all_data:
            flash("Could not extract valid data from the provided PDFs.", "error")
            return redirect(url_for('dashboard'))

        # ডেটাফ্রেম প্রসেসিং এবং পিভট টেবিল (PO SHEET.py এর লজিক)
        df = pd.DataFrame(all_data)
        
        # সাইজ সর্টিং
        all_sizes = list(df['Size'].unique())
        sorted_sizes = sort_sizes(all_sizes)
        
        # কালার অনুযায়ী গ্রুপিং
        colors = df['Color'].unique()
        final_tables = []
        grand_total_qty = 0

        for color in colors:
            color_df = df[df['Color'] == color]
            
            # পিভট টেবিল তৈরি
            pivot = color_df.pivot_table(
                index='P.O NO', 
                columns='Size', 
                values='Quantity', 
                aggfunc='sum', 
                fill_value=0
            )
            
            # মিসিং সাইজ কলাম অ্যাড করা
            for size in sorted_sizes:
                if size not in pivot.columns:
                    pivot[size] = 0
            
            # কলাম রি-অর্ডার
            pivot = pivot[sorted_sizes]
            
            # Total কলাম (প্রতিটি রো এর যোগফল)
            pivot['Total'] = pivot.sum(axis=1)
            
            # Actual Qty (প্রতিটি কলামের যোগফল) - নিচের সারি
            actual_qty_row = pivot.sum(axis=0)
            actual_qty_row.name = 'Actual Qty'
            
            # 3% Order Qty ক্যালকুলেশন
            qty_plus_3 = actual_qty_row.apply(lambda x: int(np.ceil(x * 1.03)))
            qty_plus_3.name = '3% Order Qty'
            
            # গ্র্যান্ড টোটাল আপডেট
            grand_total_qty += actual_qty_row['Total']
            
            # সারিগুলো যুক্ত করা
            pivot = pd.concat([pivot, actual_qty_row.to_frame().T])
            pivot = pd.concat([pivot, qty_plus_3.to_frame().T])
            
            # ফরম্যাটিং
            pivot = pivot.reset_index()
            pivot = pivot.rename(columns={'index': 'P.O NO'})
            pivot.columns.name = None

            pd.set_option('colheader_justify', 'center')
            
            # HTML কনভার্শন
            table_html = pivot.to_html(classes='table table-bordered', index=False, border=0)
            
            # REGEX REPLACEMENTS (HUBUHU FROM PO SHEET.py)
            table_html = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', table_html)
            table_html = table_html.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
            table_html = table_html.replace('<td>Total</td>', '<td class="total-col">Total</td>')
            
            table_html = table_html.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
            table_html = table_html.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
            table_html = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', table_html)

            final_tables.append({'color': color, 'table': table_html})
        
        # স্ট্যাটস আপডেট
        update_po_stats(session['username'], len(files), final_meta.get('booking', 'N/A'))

        return render_template_string(
            PO_REPORT_TEMPLATE, 
            tables=final_tables, 
            meta=final_meta, 
            grand_total=f"{grand_total_qty:,}"
        )

    except Exception as e:
        flash(f"Error processing PO files: {str(e)}", "error")
        return redirect(url_for('dashboard'))

# --------------------------
# ACCESSORIES ROUTES
# --------------------------
@app.route('/admin/accessories/save', methods=['POST'])
def save_accessories_entry():
    # এই রাউটটি আগের কোড থেকে অপরিবর্তিত রাখা হয়েছে, শুধু DB ইন্টিগ্রেশন আপডেট
    if request.method == 'POST':
        ref = request.form.get('ref_no')
        buyer = request.form.get('buyer')
        style = request.form.get('style')
        item_type = request.form.get('item_type')
        
        # চালান ডিটেইলস
        lines = request.form.getlist('line[]')
        colors = request.form.getlist('color[]')
        sizes = request.form.getlist('size[]')
        qtys = request.form.getlist('qty[]')
        
        acc_db = load_accessories_db()
        
        if ref not in acc_db:
            acc_db[ref] = {
                'buyer': buyer, 'style': style, 'item_type': item_type,
                'challans': [], 'created_at': get_bd_time().strftime('%d-%m-%Y')
            }
        
        new_entries = []
        today_str = get_bd_date_str()
        
        for i in range(len(lines)):
            if lines[i] and qtys[i]:
                entry = {
                    'date': today_str,
                    'line': lines[i],
                    'color': colors[i],
                    'size': sizes[i],
                    'qty': qtys[i],
                    'status': 'Done'
                }
                acc_db[ref]['challans'].append(entry)
                new_entries.append(entry)
        
        save_accessories_db(acc_db)
        flash("Accessories challan saved successfully!", "success")
        return redirect(f'/admin/accessories/input_direct?ref={ref}')

# Accessories পেজ রেন্ডারিং এর জন্য একটি রাউট দরকার
@app.route('/admin/accessories/input_direct')
def accessories_input():
    ref = request.args.get('ref', '')
    acc_db = load_accessories_db()
    
    data = acc_db.get(ref, {})
    challans = data.get('challans', [])
    
    # লাইন ওয়াইজ সামারি
    line_summary = defaultdict(int)
    for c in challans:
        line_summary[c['line']] += int(c['qty'])
        
    return render_template_string(
        ACCESSORIES_REPORT_TEMPLATE,
        ref=ref,
        buyer=data.get('buyer', ''),
        style=data.get('style', ''),
        item_type=data.get('item_type', ''),
        challans=challans,
        count=len(challans),
        today=get_bd_date_str(),
        line_summary=dict(line_summary)
    )

# --------------------------
# USER MANAGEMENT ROUTES
# --------------------------
@app.route('/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    
    username = request.form['new_username']
    password = request.form['new_password']
    role = request.form['role']
    perms = request.form.getlist('perms')
    
    users = load_users()
    if username in users:
        flash("Username already exists.", "error")
    else:
        users[username] = {
            "password": password,
            "role": role,
            "permissions": perms,
            "created_at": get_bd_date_str(),
            "last_login": "Never",
            "last_duration": "N/A"
        }
        save_users(users)
        flash(f"User {username} created successfully.", "success")
    
    return redirect(url_for('dashboard'))

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    username = request.form['username']
    
    users = load_users()
    if username in users and username != 'Admin':
        del users[username]
        save_users(users)
        flash(f"User {username} deleted.", "success")
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
