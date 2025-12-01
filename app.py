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
app.secret_key = 'super-secret-secure-key-bd-updated-v2' 

# কনফিগারেশন
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60) 

# --- টাইমজোন কনফিগারেশন (বাংলাদেশ) ---
bd_tz = pytz.timezone('Asia/Dhaka')

def get_bd_time():
    return datetime.now(bd_tz)

def get_bd_date_str():
    return get_bd_time().strftime('%d-%m-%Y')

# ==============================================================================
# MongoDB কানেকশন
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
# CSS & ASSETS (Updated to Match the Image Strictly)
# ==============================================================================
# এই অংশটি পুরো ওয়েবসাইটের লুক চেঞ্জ করে ছবির মতো কালো এবং কমলা (Orange) থিম আনবে।

COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            /* Color Palette from the Image */
            --bg-body: #121212;         /* Deep Black background */
            --bg-sidebar: #1E1E1E;      /* Sidebar Grey */
            --bg-card: #1F1F1F;         /* Card Background */
            --text-primary: #FFFFFF;    /* Main Text */
            --text-secondary: #A0A0A0;  /* Muted Text */
            --accent-orange: #FF8C42;   /* The Orange Highlight */
            --accent-purple: #6C5CE7;   /* For secondary charts */
            --accent-green: #00b894;    /* Success indicators */
            --border-color: #333333;    
            --card-radius: 16px;
            --shadow: 0 4px 20px rgba(0,0,0,0.5);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        
        body {
            background-color: var(--bg-body);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* --- Sidebar Design (Left Side) --- */
        .sidebar {
            width: 250px;
            height: 100vh;
            background-color: var(--bg-body); /* Blends with body or slightly different */
            position: fixed;
            top: 0; left: 0;
            padding: 30px 20px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid var(--border-color);
            z-index: 100;
        }

        .brand-logo {
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 50px;
            padding-left: 10px;
            letter-spacing: 0.5px;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            padding: 14px 20px;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 12px;
            margin-bottom: 8px;
            transition: all 0.3s ease;
            font-size: 14px;
            font-weight: 500;
        }

        .nav-item:hover {
            color: var(--text-primary);
            background: rgba(255, 255, 255, 0.05);
        }

        .nav-item.active {
            background-color: #2D2D2D;
            color: var(--text-primary);
            font-weight: 600;
        }
        
        .nav-item i { width: 25px; font-size: 16px; margin-right: 10px; }

        /* --- Main Content Area --- */
        .main-content {
            margin-left: 250px;
            padding: 30px 40px;
            width: calc(100% - 250px);
        }

        .header-title { font-size: 24px; font-weight: 600; margin-bottom: 5px; }
        .header-subtitle { color: var(--text-secondary); font-size: 13px; margin-bottom: 30px; }

        /* --- Stats Row (Top) --- */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background-color: var(--bg-card);
            padding: 20px;
            border-radius: var(--card-radius);
            display: flex;
            align-items: center;
            border: 1px solid var(--border-color);
        }

        .stat-icon {
            width: 45px; height: 45px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            display: flex; justify-content: center; align-items: center;
            margin-right: 15px;
            font-size: 18px;
            color: var(--text-secondary);
        }

        .stat-info h3 { font-size: 12px; color: var(--text-secondary); font-weight: 400; margin-bottom: 5px; }
        .stat-info p { font-size: 20px; font-weight: 700; color: var(--text-primary); }

        /* --- Dashboard Grid (Middle) --- */
        .dashboard-grid-2 {
            display: grid;
            grid-template-columns: 2fr 1fr; /* Chart takes 2/3, List takes 1/3 */
            gap: 20px;
            margin-bottom: 20px;
        }

        .chart-card {
            background-color: var(--bg-card);
            padding: 25px;
            border-radius: var(--card-radius);
            border: 1px solid var(--border-color);
            position: relative;
        }

        .section-title { font-size: 16px; font-weight: 600; margin-bottom: 20px; color: var(--text-primary); }
        
        /* Progress Bars Style (Like Image) */
        .progress-item { margin-bottom: 20px; }
        .progress-label { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
        .progress-track { width: 100%; height: 8px; background: #2D2D2D; border-radius: 10px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-orange); border-radius: 10px; }

        /* --- Bottom Grid --- */
        .bottom-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 20px;
        }

        /* --- Form Elements (Dark Theme) --- */
        input, select {
            width: 100%;
            padding: 12px 15px;
            background: #2D2D2D;
            border: 1px solid #333;
            color: white;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
        }
        input:focus { border-color: var(--accent-orange); outline: none; }
        label { font-size: 12px; color: var(--text-secondary); margin-bottom: 5px; display: block; }

        button {
            background: var(--accent-orange);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
            width: 100%;
        }
        button:hover { opacity: 0.9; transform: translateY(-2px); }

        /* --- Table Styling --- */
        .detail-table { width: 100%; border-collapse: collapse; }
        .detail-table th { text-align: left; font-size: 12px; color: var(--text-secondary); padding: 15px 10px; border-bottom: 1px solid var(--border-color); }
        .detail-table td { padding: 15px 10px; font-size: 13px; color: var(--text-primary); border-bottom: 1px solid #2D2D2D; }
        .status-badge { padding: 5px 10px; border-radius: 20px; font-size: 10px; font-weight: 600; }
        .status-green { background: rgba(0, 184, 148, 0.2); color: #00b894; }

        /* Mobile Responsive */
        @media (max-width: 900px) {
            .sidebar { transform: translateX(-100%); transition: 0.3s; }
            .sidebar.active { transform: translateX(0); }
            .main-content { margin-left: 0; width: 100%; }
            .dashboard-grid-2, .bottom-grid { grid-template-columns: 1fr; }
            .sidebar-toggle { display: block; position: fixed; top: 20px; right: 20px; color: white; z-index: 200; font-size: 24px; cursor: pointer; }
        }
        .sidebar-toggle { display: none; }
        
        /* Spinner */
        #loading-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 999; justify-content: center; align-items: center; flex-direction: column; }
        .spinner { width: 50px; height: 50px; border: 3px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: var(--accent-orange); animation: spin 1s ease-in-out infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
"""

# ==============================================================================
# হেল্পার ফাংশন (ডাটা ম্যানেজমেন্ট)
# ==============================================================================
# (আগের লজিক অপরিবর্তিত রাখা হয়েছে, শুধু ব্যবহারের জন্য প্রস্তুত করা হলো)

def load_users():
    record = users_col.find_one({"_id": "global_users"})
    default_users = {
        "Admin": {
            "password": "@Nijhum@12", 
            "role": "admin", 
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"],
            "created_at": "N/A", "last_login": "Never", "last_duration": "N/A"
        }
    }
    return record['data'] if record else default_users

def save_users(users_data):
    users_col.replace_one({"_id": "global_users"}, {"_id": "global_users", "data": users_data}, upsert=True)

def load_stats():
    record = stats_col.find_one({"_id": "dashboard_stats"})
    return record['data'] if record else {"downloads": [], "last_booking": "None"}

def save_stats(data):
    stats_col.replace_one({"_id": "dashboard_stats"}, {"_id": "dashboard_stats", "data": data}, upsert=True)

def update_stats(ref_no, username):
    data = load_stats()
    now = get_bd_time()
    new_record = {"ref": ref_no, "user": username, "date": now.strftime('%d-%m-%Y'), "time": now.strftime('%I:%M %p'), "type": "Closing Report"}
    data['downloads'].insert(0, new_record)
    data['downloads'] = data['downloads'][:1000]
    data['last_booking'] = ref_no
    save_stats(data)

def update_po_stats(username, file_count):
    data = load_stats()
    now = get_bd_time()
    new_record = {"user": username, "file_count": file_count, "date": now.strftime('%d-%m-%Y'), "time": now.strftime('%I:%M %p'), "type": "PO Sheet"}
    if 'downloads' not in data: data['downloads'] = []
    data['downloads'].insert(0, new_record)
    data['downloads'] = data['downloads'][:1000]
    save_stats(data)

def load_accessories_db():
    record = accessories_col.find_one({"_id": "accessories_data"})
    return record['data'] if record else {}

def save_accessories_db(data):
    accessories_col.replace_one({"_id": "accessories_data"}, {"_id": "accessories_data", "data": data}, upsert=True)

# ড্যাশবোর্ডের চার্টের জন্য ডাটা প্রস্তুত করা
def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    now = get_bd_time()
    today_str = now.strftime('%d-%m-%Y')
    
    # Logic to map real data to dashboard visual elements
    acc_today_count = 0
    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            if challan.get('date') == today_str: acc_today_count += 1

    po_today_count = 0
    closing_today_count = 0
    history = stats_data.get('downloads', [])
    for item in history:
        if item.get('date') == today_str:
            if item.get('type') == 'PO Sheet': po_today_count += 1
            else: closing_today_count += 1

    return {
        "users": {"count": len(users_data)},
        "accessories": {"count": acc_today_count},
        "closing": {"count": closing_today_count},
        "po": {"count": po_today_count},
        "history": history[:5], # Last 5 for table
        "chart_data": [closing_today_count, acc_today_count, po_today_count, 5] # Dummy 5 for variety
    }
# ==============================================================================
# LOGIN TEMPLATE (Dark Theme with Orange Accent)
# ==============================================================================
LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>System Access</title>
    {COMMON_STYLES}
    <style>
        .login-wrapper {{
            display: flex; justify-content: center; align-items: center;
            height: 100vh; width: 100%;
            background: radial-gradient(circle at center, #1E1E1E 0%, #121212 100%);
        }}
        .login-card {{
            background: var(--bg-card);
            padding: 40px;
            border-radius: 20px;
            width: 100%; max-width: 400px;
            border: 1px solid var(--border-color);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            text-align: center;
        }}
        .brand-text {{ font-size: 24px; font-weight: 700; color: white; margin-bottom: 10px; }}
        .brand-sub {{ font-size: 13px; color: var(--text-secondary); margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="login-wrapper">
        <div class="login-card">
            <div class="brand-text">Cotton<span style="color:var(--accent-orange)">Solutions</span></div>
            <div class="brand-sub">Secure Gateway</div>
            
            <form action="/login" method="post">
                <input type="text" name="username" placeholder="Username" required style="background:#121212; border:1px solid #333;">
                <input type="password" name="password" placeholder="Password" required style="background:#121212; border:1px solid #333;">
                <button type="submit">Sign In</button>
            </form>
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top: 15px; font-size: 12px; color: #ff7675;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            
            <div style="margin-top: 30px; font-size: 11px; color: #555;">© 2025 Mehedi Hasan</div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ADMIN DASHBOARD TEMPLATE (Updated to match the uploaded Image)
# ==============================================================================
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
        <div style="color:white; margin-top:15px; font-size:14px;">Processing...</div>
    </div>

    <div class="sidebar-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">Cotton<span style="color:var(--accent-orange)">Solutions</span></div>
        
        <div style="flex: 1;">
            <a href="/" class="nav-item active" onclick="showSection('dashboard', this)">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="#" class="nav-item" onclick="showSection('closing', this)">
                <i class="fas fa-chart-bar"></i> Analytics (Closing)
            </a>
            <a href="/admin/accessories" class="nav-item">
                <i class="fas fa-database"></i> Databases (Acc.)
            </a>
            <a href="#" class="nav-item" onclick="showSection('po', this)">
                <i class="fas fa-file-invoice"></i> Help (PO Sheet)
            </a>
            <a href="#" class="nav-item" onclick="showSection('users', this)">
                <i class="fas fa-cog"></i> Settings (Users)
            </a>
        </div>

        <a href="/logout" class="nav-item" style="color: #ff7675; margin-top: auto;">
            <i class="fas fa-sign-out-alt"></i> Log Out
        </a>
    </div>

    <div class="main-content">
        
        <div id="section-dashboard">
            <h1 class="header-title">Main Dashboard</h1>
            <p class="header-subtitle">Overview of production reports and user activity.</p>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info">
                        <h3>Closing Reports</h3>
                        <p>{{{{ stats.closing.count }}}}</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-boxes"></i></div>
                    <div class="stat-info">
                        <h3>Accessories</h3>
                        <p>{{{{ stats.accessories.count }}}}</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-file-invoice"></i></div>
                    <div class="stat-info">
                        <h3>PO Generated</h3>
                        <p>{{{{ stats.po.count }}}}</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-users"></i></div>
                    <div class="stat-info">
                        <h3>Active Users</h3>
                        <p>{{{{ stats.users.count }}}}</p>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid-2">
                <div class="chart-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                        <div>
                            <div style="font-size:24px; font-weight:700;">Activity</div>
                            <div style="font-size:12px; color:var(--accent-green);"><i class="fas fa-arrow-up"></i> Live Tracking</div>
                        </div>
                        <i class="fas fa-chart-line" style="color:var(--text-secondary);"></i>
                    </div>
                    <canvas id="mainChart" height="250"></canvas>
                </div>

                <div class="chart-card">
                    <div class="section-title">Module Usage</div>
                    
                    <div class="progress-item">
                        <div class="progress-label"><span>Closing Report</span> <span>High</span></div>
                        <div class="progress-track"><div class="progress-fill" style="width: 85%;"></div></div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-label"><span>Accessories Input</span> <span>Medium</span></div>
                        <div class="progress-track"><div class="progress-fill" style="width: 60%; background: #6C5CE7;"></div></div>
                    </div>

                    <div class="progress-item">
                        <div class="progress-label"><span>PO Generation</span> <span>Normal</span></div>
                        <div class="progress-track"><div class="progress-fill" style="width: 45%; background: #00b894;"></div></div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-label"><span>User Management</span> <span>Low</span></div>
                        <div class="progress-track"><div class="progress-fill" style="width: 20%; background: #e17055;"></div></div>
                    </div>
                </div>
            </div>

            <div class="bottom-grid">
                
                <div class="chart-card" style="grid-column: span 2;">
                    <div class="section-title" style="display:flex; justify-content:space-between;">
                        <span>Recent History</span>
                        <i class="fas fa-history" style="opacity:0.5"></i>
                    </div>
                    <table class="detail-table">
                        <thead>
                            <tr><th>User</th><th>Action</th><th>Time</th></tr>
                        </thead>
                        <tbody>
                            {{% for log in stats.history %}}
                            <tr>
                                <td><div style="display:flex; align-items:center;"><div style="width:25px; height:25px; background:#333; border-radius:50%; margin-right:10px;"></div> {{{{ log.user }}}}</div></td>
                                <td style="color:var(--text-secondary)">{{{{ log.type }}}}</td>
                                <td>{{{{ log.time }}}}</td>
                            </tr>
                            {{% endfor %}}
                        </tbody>
                    </table>
                </div>

                <div class="chart-card">
                    <div class="section-title">Quick Actions</div>
                    <div style="display:flex; flex-direction:column; gap:10px;">
                        <div style="display:flex; align-items:center;">
                            <input type="checkbox" checked disabled style="width:15px; margin:0 10px 0 0;"> 
                            <span style="font-size:13px; color:var(--text-secondary)">Check Database</span>
                        </div>
                        <div style="display:flex; align-items:center;">
                            <input type="checkbox" checked disabled style="width:15px; margin:0 10px 0 0;"> 
                            <span style="font-size:13px; color:var(--text-secondary)">Backup Logs</span>
                        </div>
                        <button onclick="showSection('closing', this)" style="margin-top:10px; font-size:12px; padding:8px;">+ New Closing Report</button>
                    </div>
                </div>

                <div class="chart-card">
                    <div class="section-title">System Status</div>
                    <div style="position:relative; height:150px; display:flex; justify-content:center;">
                        <canvas id="storageChart"></canvas>
                        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); text-align:center;">
                            <div style="font-size:20px; font-weight:700;">98%</div>
                            <div style="font-size:10px; color:var(--text-secondary)">Uptime</div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
"""
        <div id="section-closing" style="display:none; max-width: 600px; margin: 0 auto;">
            <div class="chart-card">
                <div class="section-title"><i class="fas fa-file-export"></i> Generate Closing Report</div>
                <p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px;">Enter the internal booking reference number to fetch data.</p>
                
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <label>Internal Reference No</label>
                    <input type="text" name="ref_no" placeholder="e.g. DFL/24/123..." required>
                    <button type="submit">Generate Report</button>
                </form>
            </div>
        </div>

        <div id="section-po" style="display:none; max-width: 600px; margin: 0 auto;">
             <div class="chart-card">
                <div class="section-title"><i class="fas fa-file-invoice"></i> PO Sheet Generator</div>
                <p style="color:var(--text-secondary); margin-bottom:20px; font-size:13px;">Upload Booking PDF and PO PDFs together.</p>

                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <label>Select PDF Files</label>
                    <div style="background: #2D2D2D; padding: 20px; border-radius: 8px; text-align: center; border: 1px dashed #555; margin-bottom: 20px;">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display: none;" id="file-upload">
                        <label for="file-upload" style="cursor: pointer; color: var(--accent-orange); font-weight: 600; font-size: 14px;">
                            <i class="fas fa-cloud-upload-alt"></i> Click to Upload Files
                        </label>
                        <div id="file-count" style="font-size: 12px; color: #888; margin-top: 5px;">No files selected</div>
                    </div>
                    <button type="submit">Process Files</button>
                </form>
            </div>
        </div>

        <div id="section-users" style="display:none;">
            <div class="dashboard-grid-2">
                <div class="chart-card">
                    <div class="section-title">User Directory</div>
                    <div style="overflow-x: auto;">
                        <div id="userTableContainer">Loading...</div>
                    </div>
                </div>

                <div class="chart-card">
                    <div class="section-title">Manage User</div>
                    <form id="userForm">
                        <input type="hidden" id="action_type" name="action_type" value="create">
                        
                        <label>Username</label>
                        <input type="text" id="new_username" name="username" required>
                        
                        <label>Password</label>
                        <input type="text" id="new_password" name="password" required>

                        <label>Permissions</label>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px;">
                            <label style="background: #333; padding: 5px 10px; border-radius: 4px; font-size: 11px; cursor: pointer;">
                                <input type="checkbox" name="permissions" value="closing" id="perm_closing" checked style="width:auto; margin:0;"> Closing
                            </label>
                            <label style="background: #333; padding: 5px 10px; border-radius: 4px; font-size: 11px; cursor: pointer;">
                                <input type="checkbox" name="permissions" value="po_sheet" id="perm_po" style="width:auto; margin:0;"> PO Sheet
                            </label>
                            <label style="background: #333; padding: 5px 10px; border-radius: 4px; font-size: 11px; cursor: pointer;">
                                <input type="checkbox" name="permissions" value="accessories" id="perm_acc" style="width:auto; margin:0;"> Accessories
                            </label>
                        </div>

                        <button type="button" onclick="handleUserSubmit()" id="saveUserBtn">Create User</button>
                        <button type="button" onclick="resetForm()" style="background: #444; margin-top: 10px;">Reset</button>
                    </form>
                </div>
            </div>
        </div>

    </div> <script>
        // --- File Upload UI Logic ---
        document.getElementById('file-upload').addEventListener('change', function(){
            document.getElementById('file-count').textContent = this.files.length + " files selected";
        });

        // --- Sidebar & Section Switching ---
        function showSection(id, element) {
            // Hide all sections
            document.getElementById('section-dashboard').style.display = 'none';
            document.getElementById('section-closing').style.display = 'none';
            document.getElementById('section-po').style.display = 'none';
            document.getElementById('section-users').style.display = 'none';
            
            // Show selected
            document.getElementById('section-' + id).style.display = 'block';

            // Update Sidebar Active State
            if(element) {
                document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
                element.classList.add('active');
            }

            // Load Users if needed
            if(id === 'users') loadUsers();
            
            // Close Sidebar on Mobile
            if(window.innerWidth < 900) {
                document.querySelector('.sidebar').classList.remove('active');
            }
        }

        // --- CHART.JS CONFIGURATION (Matches Image Style) ---
        // Main Activity Chart (Curved Lines)
        const ctx = document.getElementById('mainChart').getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(255, 140, 66, 0.2)'); // Orange fade
        gradient.addColorStop(1, 'rgba(255, 140, 66, 0)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [
                    {
                        label: 'Total Reports',
                        data: [12, 19, 15, 25, 22, 30], // Dummy data for visual
                        borderColor: '#FF8C42', // Orange
                        backgroundColor: gradient,
                        tension: 0.4, // Smooth curves
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: '#1E1E1E',
                        pointBorderColor: '#FF8C42',
                        pointBorderWidth: 2,
                        fill: true
                    },
                    {
                        label: 'PO Generated',
                        data: [8, 12, 10, 18, 14, 20],
                        borderColor: '#FFFFFF', // White Line
                        borderDash: [5, 5],
                        tension: 0.4,
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false } // Hide legend like image
                },
                scales: {
                    x: { 
                        grid: { display: false, color: '#333' },
                        ticks: { color: '#888' }
                    },
                    y: { 
                        grid: { color: '#2D2D2D' },
                        ticks: { color: '#888' },
                        beginAtZero: true
                    }
                }
            }
        });

        // Storage/Status Chart (Doughnut)
        const ctxStorage = document.getElementById('storageChart').getContext('2d');
        new Chart(ctxStorage, {
            type: 'doughnut',
            data: {
                labels: ['Used', 'Free'],
                datasets: [{
                    data: [85, 15],
                    backgroundColor: ['#FF8C42', '#2D2D2D'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                cutout: '75%', // Thinner ring
                plugins: { legend: { display: false } }
            }
        });

        // --- USER MANAGEMENT LOGIC (AJAX) ---
        function loadUsers() {
             fetch('/admin/get-users')
                .then(res => res.json())
                .then(data => {
                     let html = '<table class="detail-table"><thead><tr><th>User</th><th>Role</th><th>Perms</th><th>Action</th></tr></thead><tbody>';
                     for (const [user, details] of Object.entries(data)) {
                         let perms = details.permissions ? details.permissions.map(p => p.charAt(0).toUpperCase() + p.slice(1)).join(', ') : '';
                         html += `<tr>
                            <td><div style="font-weight:600; color:white;">${user}</div></td>
                            <td><span class="status-badge status-green">${details.role}</span></td>
                            <td style="font-size:11px; color:#888;">${perms.substring(0, 15)}${perms.length>15?'...':''}</td>
                            <td>
                                ${details.role !== 'admin' ? 
                                    `<button onclick="editUser('${user}', '${details.password}', '${details.permissions.join(',')}')" style="padding:5px 10px; font-size:10px; width:auto; margin-right:5px;"><i class="fas fa-edit"></i></button>
                                     <button onclick="deleteUser('${user}')" style="background:#e17055; padding:5px 10px; font-size:10px; width:auto;"><i class="fas fa-trash"></i></button>` : 
                                    '<span style="opacity:0.5; font-size:10px;">Admin</span>'}
                            </td>
                        </tr>`;
                     }
                     html += '</tbody></table>';
                     document.getElementById('userTableContainer').innerHTML = html;
                });
        }

        function handleUserSubmit() {
            const username = document.getElementById('new_username').value;
            const password = document.getElementById('new_password').value;
            const action = document.getElementById('action_type').value;
            
            if(!username || !password) { alert("Username & Password required!"); return; }
            
            let permissions = [];
            if(document.getElementById('perm_closing').checked) permissions.push('closing');
            if(document.getElementById('perm_po').checked) permissions.push('po_sheet');
            if(document.getElementById('perm_acc').checked) permissions.push('accessories');

            fetch('/admin/save-user', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username, password, permissions, action_type: action })
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    loadUsers();
                    resetForm();
                } else {
                    alert(data.message);
                }
            });
        }

        function editUser(user, pass, permsStr) {
            document.getElementById('new_username').value = user;
            document.getElementById('new_username').readOnly = true; 
            document.getElementById('new_password').value = pass;
            document.getElementById('action_type').value = 'update';
            document.getElementById('saveUserBtn').innerText = 'Update User';
            
            let perms = permsStr.split(',');
            document.getElementById('perm_closing').checked = perms.includes('closing');
            document.getElementById('perm_po').checked = perms.includes('po_sheet');
            document.getElementById('perm_acc').checked = perms.includes('accessories');
        }

        function resetForm() {
            document.getElementById('userForm').reset();
            document.getElementById('action_type').value = 'create';
            document.getElementById('saveUserBtn').innerText = 'Create User';
            document.getElementById('new_username').readOnly = false;
        }

        function deleteUser(user) {
            if(confirm('Are you sure?')) {
                fetch('/admin/delete-user', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username: user })
                }).then(() => loadUsers());
            }
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# USER DASHBOARD (Redesigned - Dark Theme)
# ==============================================================================
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
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div style="color:white; margin-top:15px;">Processing...</div>
    </div>

    <div class="sidebar">
        <div class="brand-logo">Cotton<span style="color:var(--accent-orange)">Solutions</span></div>
        <div class="nav-item active"><i class="fas fa-home"></i> Home</div>
        <a href="/logout" class="nav-item" style="color: #ff7675; margin-top: auto;">
            <i class="fas fa-sign-out-alt"></i> Log Out
        </a>
    </div>

    <div class="main-content">
        <h1 class="header-title">Welcome, <span style="color:var(--accent-orange)">{{{{ session.user }}}}</span></h1>
        <p class="header-subtitle">Select a module to proceed.</p>

        <div class="stats-grid">
            {{% if 'closing' in session.permissions %}}
            <div class="chart-card" style="display:block;">
                <div class="section-title"><i class="fas fa-file-export"></i> Closing Report</div>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <label>Internal Reference No</label>
                    <input type="text" name="ref_no" placeholder="Enter Booking Ref..." required>
                    <button type="submit">Generate Report</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'po_sheet' in session.permissions %}}
             <div class="chart-card" style="display:block;">
                <div class="section-title"><i class="fas fa-file-invoice"></i> PO Sheet Generator</div>
                 <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <label>Select PDF Files</label>
                    <input type="file" name="pdf_files" multiple accept=".pdf" required style="padding:10px; height:auto;">
                    <button type="submit" style="background:var(--accent-green); margin-top:10px;">Generate</button>
                </form>
            </div>
            {{% endif %}}

            {{% if 'accessories' in session.permissions %}}
            <div class="chart-card" style="display:block;">
                <div class="section-title"><i class="fas fa-boxes"></i> Accessories</div>
                <p style="color:var(--text-secondary); font-size:13px; margin-bottom:15px;">Manage challans and input data.</p>
                <a href="/admin/accessories" style="text-decoration:none;">
                    <button style="background:var(--accent-purple);">Open Dashboard</button>
                </a>
            </div>
            {{% endif %}}
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div style="background: rgba(231, 76, 60, 0.2); color: #ff7675; padding: 15px; border-radius: 8px; margin-top: 20px; border: 1px solid #ff7675;">
                    {{{{ messages[0] }}}}
                </div>
            {{% endif %}}
        {{% endwith %}}
    </div>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES UI TEMPLATES (Redesigned - Dark Theme)
# ==============================================================================

# 1. Search Page
ACCESSORIES_SEARCH_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Search</title>
    {COMMON_STYLES}
</head>
<body>
    <div style="display: flex; height: 100vh; justify-content: center; align-items: center; background: radial-gradient(circle at center, #1E1E1E 0%, #121212 100%);">
        <div class="chart-card" style="width: 100%; max-width: 450px; padding: 40px;">
            <div class="section-title" style="text-align:center; font-size:20px; margin-bottom:10px;">Accessories Dashboard</div>
            <p style="text-align:center; color:var(--text-secondary); margin-bottom:30px;">Find Booking to Manage Challan</p>
            
            <form action="/admin/accessories/input" method="post">
                <label>Booking Reference No</label>
                <input type="text" name="ref_no" placeholder="e.g. Booking-123..." required>
                <button type="submit">Proceed</button>
            </form>

            <div style="margin-top: 20px; display: flex; justify-content: space-between;">
                <a href="/" style="color:var(--text-secondary); font-size:13px; text-decoration:none;"><i class="fas fa-arrow-left"></i> Back</a>
                <a href="/logout" style="color:#ff7675; font-size:13px; text-decoration:none;">Log Out</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 2. Input Page
ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div style="color:white; margin-top:15px;">Saving...</div>
    </div>

    <div style="display: flex; min-height: 100vh; justify-content: center; align-items: center; padding: 20px;">
        <div class="chart-card" style="width: 100%; max-width: 500px;">
            <div class="section-title"><i class="fas fa-plus-circle"></i> New Challan Entry</div>
            
            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #333;">
                <div style="color:var(--accent-orange); font-size:12px;">BOOKING REF</div>
                <div style="font-size:16px; font-weight:700; margin-bottom:5px;">{{{{ ref }}}}</div>
                <div style="font-size:13px; color:var(--text-secondary);">Buyer: {{{{ buyer }}}} | Style: {{{{ style }}}}</div>
            </div>

            <form action="/admin/accessories/save" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                
                <label>Item Type</label>
                <select name="item_type">
                    <option value="Top">Top</option>
                    <option value="Bottom">Bottom</option>
                </select>

                <label>Select Color</label>
                <select name="color" required>
                    <option value="" disabled selected>-- Choose Color --</option>
                    {{% for color in colors %}}
                    <option value="{{{{ color }}}}">{{{{ color }}}}</option>
                    {{% endfor %}}
                </select>

                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                    <div>
                        <label>Sewing Line</label>
                        <input type="text" name="line_no" placeholder="Line-12" required>
                    </div>
                    <div>
                        <label>Size</label>
                        <input type="text" name="size" value="ALL">
                    </div>
                </div>

                <label>Quantity</label>
                <input type="number" name="qty" placeholder="Enter Qty" required>

                <button type="submit">Save & View Report</button>
            </form>

            <div style="margin-top: 20px; text-align: center;">
                <a href="/admin/accessories" style="color:var(--text-secondary); font-size:13px; text-decoration:none;">Cancel</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# 3. Edit Page
ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Challan</title>
    {COMMON_STYLES}
</head>
<body>
    <div style="display: flex; height: 100vh; justify-content: center; align-items: center;">
        <div class="chart-card" style="width: 100%; max-width: 450px;">
            <div class="section-title">Edit Challan Data</div>
            
            <form action="/admin/accessories/update" method="post">
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <input type="hidden" name="index" value="{{{{ index }}}}">
                
                <label>Sewing Line</label>
                <input type="text" name="line_no" value="{{{{ item.line }}}}" required>
                
                <label>Color</label>
                <input type="text" name="color" value="{{{{ item.color }}}}" required>
                
                <label>Size</label>
                <input type="text" name="size" value="{{{{ item.size }}}}" required>
                
                <label>Quantity</label>
                <input type="number" name="qty" value="{{{{ item.qty }}}}" required>
                
                <button type="submit" style="background:var(--accent-orange);">Update Entry</button>
            </form>
            <div style="margin-top: 15px; text-align: center;">
                <a href="/admin/accessories/print?ref={{{{ ref }}}}" style="color:white; font-size:12px;">Cancel</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# PRINT REPORT TEMPLATES (Original White Design - Unchanged)
# ==============================================================================

# 1. Closing Report (White for Print)
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

# 2. Accessories Report (White for Print)
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

# 3. PO Report (White for Print)
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
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PDF)
# ==============================================================================

def is_potential_size(header):
    h = header.strip().upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P.O NO"]:
        return False
    if re.match(r'^\d+$', h): return True
    if re.match(r'^\d+[AMYT]$', h): return True
    if re.match(r'^(XXS|XS|S|M|L|XL|XXL|XXXL|TU|ONE\s*SIZE)$', h): return True
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
    
    return meta

def extract_data_dynamic(file_path):
    extracted_data = []
    metadata = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A'}
    order_no = "Unknown"
    
    try:
        reader = pypdf.PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text()
        
        # বুকিং ফাইল হলে শুধু মেটাডাটা নিয়ে ফিরবে
        if "Main Fabric Booking" in first_page_text or "Fabric Booking Sheet" in first_page_text:
            metadata = extract_metadata(first_page_text)
            return [], metadata 

        # অর্ডার নম্বর খোঁজা
        order_match = re.search(r"Order no\D*(\d+)", first_page_text, re.IGNORECASE)
        if order_match: order_no = order_match.group(1)
        
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

                # সাইজ ডিটেকশন
                if ("Colo" in line or "Size" in line) and "Total" in line:
                    parts = line.split()
                    try:
                        total_idx = [idx for idx, x in enumerate(parts) if 'Total' in x][0]
                        raw_sizes = parts[:total_idx]
                        temp_sizes = [s for s in raw_sizes if s not in ["Colo", "/", "Size", "Colo/Size"]]
                        if temp_sizes:
                            sizes = temp_sizes
                            capturing_data = True
                    except: pass
                    continue
                
                # কোয়ান্টিটি ডাটা এক্সট্রাকশন
                if capturing_data:
                    if line.startswith("Total Quantity") or line.startswith("Total Amount"):
                        capturing_data = False
                        continue
                    
                    if "quantity" in line.lower(): continue

                    clean_line = line.replace("Spec. price", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line): continue

                    numbers_in_line = re.findall(r'\b\d+\b', line)
                    quantities = [int(n) for n in numbers_in_line]
                    color_name = clean_line

                    final_qtys = []
                    if len(quantities) >= len(sizes):
                        final_qtys = quantities[:len(sizes)]
                        color_name = re.sub(r'\s\d+$', '', color_name).strip()
                    
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
# লজিক পার্ট: CLOSING REPORT SCRAPER & EXCEL
# ==============================================================================

def get_authenticated_session(username, password):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        response = session_req.post(login_url, data=login_payload, timeout=300)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            return session_req
        return None
    except: return None

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
    
    if found_data: return parse_report_data(found_data)
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
            else: current_block.append(row)
        if current_block: item_blocks.append(current_block)

        for block in item_blocks:
            style, color, buyer_name = "N/A", "N/A", "N/A"
            gmts_qty_data, sewing_input_data, cutting_qc_data = [], [], []
            
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0].get_text(strip=True).lower()
                    if "style" in criteria_main: style = cells[1].get_text(strip=True)
                    elif "color" in criteria_main: color = cells[1].get_text(strip=True)
                    elif "buyer" in criteria_main: buyer_name = cells[1].get_text(strip=True)
                    
                    if "country qty" in criteria_main or "country qty" in cells[2].get_text(strip=True).lower():
                        gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in criteria_main or "sewing input" in cells[2].get_text(strip=True).lower():
                        sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "cutting qc" in criteria_main or "cutting qc" in cells[2].get_text(strip=True).lower():
                         if "balance" not in criteria_main:
                            cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            
            if gmts_qty_data:
                all_report_data.append({
                    'style': style, 'buyer': buyer_name, 'color': color, 
                    'headers': headers, 'gmts_qty': gmts_qty_data, 
                    'sewing_input': sewing_input_data, 'cutting_qc': cutting_qc_data
                })
        return all_report_data
    except: return None

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data: return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    
    # Styles
    bold_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Header
    ws.merge_cells('A1:I1')
    ws['A1'] = "COTTON CLOTHING BD LTD"
    ws['A1'].font = Font(size=20, bold=True)
    ws['A1'].alignment = center_align
    
    ws.merge_cells('A2:I2')
    ws['A2'] = f"CLOSING REPORT - {internal_ref_no}"
    ws['A2'].alignment = center_align

    current_row = 5
    for block in report_data:
        ws.cell(row=current_row, column=1, value=f"Color: {block['color']}").font = bold_font
        current_row += 1
        
        headers = ["SIZE", "ORDER QTY 3%", "ACTUAL", "CUTTING", "INPUT", "BALANCE", "SHORT/PLUS", "%"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=h)
            cell.font = bold_font
            cell.border = thin_border
            cell.alignment = center_align
        
        current_row += 1
        for i, size in enumerate(block['headers']):
            actual = int(block['gmts_qty'][i].replace(',', '') or 0)
            qty_3 = round(actual * 1.03)
            inp = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cut = int(block['cutting_qc'][i].replace(',', '') or 0) if i < len(block.get('cutting_qc', [])) else 0
            
            row_vals = [size, qty_3, actual, cut, inp, cut-inp, inp-qty_3]
            for col, val in enumerate(row_vals, 1):
                cell = ws.cell(row=current_row, column=col, value=val)
                cell.border = thin_border
                cell.alignment = center_align
            
            # Percentage Formula
            perc_cell = ws.cell(row=current_row, column=8, value=f"=IF(B{current_row}>0, G{current_row}/B{current_row}, 0)")
            perc_cell.number_format = '0.00%'
            perc_cell.border = thin_border
            current_row += 1
        current_row += 2

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==============================================================================
# FLASK ROUTES (Controller Logic)
# ==============================================================================

@app.route('/')
def index():
    # ডাটাবেস ইনিশিয়ালাইজ করা (যদি না থাকে)
    load_users() 
    
    # লগইন না থাকলে লগইন পেজে পাঠানো
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    
    # লগইন থাকলে রোল চেক করা
    else:
        if session.get('role') == 'admin':
            # এডমিন হলে ড্যাশবোর্ড স্ট্যাটাস লোড করা
            stats = get_dashboard_summary_v2()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            # সাধারণ ইউজার হলে ইউজার ড্যাশবোর্ড
            return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    users_db = load_users()

    # ইউজারনেম ও পাসওয়ার্ড যাচাই
    if username in users_db and users_db[username]['password'] == password:
        session.permanent = True
        session['logged_in'] = True
        session['user'] = username
        session['role'] = users_db[username]['role']
        session['permissions'] = users_db[username].get('permissions', [])
        
        # লগইন টাইম ট্র্যাকিং (BD Time)
        now = get_bd_time()
        session['login_start'] = now.isoformat()
        
        # লাস্ট লগইন টাইম আপডেট করা
        users_db[username]['last_login'] = now.strftime('%I:%M %p, %d %b')
        save_users(users_db)
        
        return redirect(url_for('index'))
    else:
        flash('Invalid Username or Password.')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    # সেশন ডিউরেশন ক্যালকুলেশন
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
        except:
            pass

    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

# --- USER MANAGEMENT ROUTES (AJAX) ---
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
            "created_at": get_bd_date_str(),
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
    # ডাটা ফেচিং লজিক কল করা (যা আপনার অরিজিনাল ফাইলে ছিল)
    # নোট: fetch_closing_report_data ফাংশনটি আগের মতো গ্লোবাল স্কোপে থাকতে হবে
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
    if 'accessories' not in session.get('permissions', []):
        flash("Permission Denied.")
        return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no').strip().upper()
    db_acc = load_accessories_db()

    # যদি ডাটাবেসে না থাকে, তবে ERP থেকে ফেচ করবে
    if ref_no in db_acc:
        data = db_acc[ref_no]
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
    else:
        api_data = fetch_closing_report_data(ref_no)
        if not api_data:
            flash(f"Booking not found: {ref_no}")
            return redirect(url_for('accessories_search_page'))
        
        colors = sorted(list(set([item['color'] for item in api_data])))
        style = api_data[0].get('style', 'N/A')
        buyer = api_data[0].get('buyer', 'N/A')
        
        # নতুন এন্ট্রি তৈরি
        db_acc[ref_no] = {
            "style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": [] 
        }
        save_accessories_db(db_acc)

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer)

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref = request.form.get('ref').strip().upper()
    db_acc = load_accessories_db()
    
    if ref in db_acc:
        if request.form.get('item_type'): 
            db_acc[ref]['item_type'] = request.form.get('item_type')
        
        new_entry = {
            "date": get_bd_date_str(),
            "line": request.form.get('line_no'),
            "color": request.form.get('color'),
            "size": request.form.get('size'),
            "qty": request.form.get('qty')
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
    return render_template_string(ACCESSORIES_REPORT_TEMPLATE, 
                                  ref=ref, buyer=data['buyer'], style=data['style'],
                                  item_type=data.get('item_type', ''), challans=data['challans'],
                                  today=get_bd_date_str())

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('index'))

    ref = request.form.get('ref')
    index = int(request.form.get('index'))
    db_acc = load_accessories_db()

    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        db_acc[ref]['challans'][index]['line'] = request.form.get('line_no')
        db_acc[ref]['challans'][index]['color'] = request.form.get('color')
        db_acc[ref]['challans'][index]['size'] = request.form.get('size')
        db_acc[ref]['challans'][index]['qty'] = request.form.get('qty')
        save_accessories_db(db_acc)
            
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    ref = request.args.get('ref')
    index = int(request.args.get('index'))
    db_acc = load_accessories_db()
    item = db_acc[ref]['challans'][index]
    return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item)

# --- PO REPORT ROUTE ---
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
        # PDF প্রসেসিং ফাংশন কল (অরিজিনাল লজিক)
        data, meta = extract_data_dynamic(file_path)
        if meta['buyer'] != 'N/A': final_meta = meta
        if data: all_data.extend(data)
    
    if not all_data:
        flash("No valid PO data found in PDF.")
        return redirect(url_for('index'))

    update_po_stats(session.get('user', 'Unknown'), len(uploaded_files))

    # Data Processing for Table (Using Pandas)
    df = pd.DataFrame(all_data)
    df['Color'] = df['Color'].str.strip()
    df = df[df['Color'] != ""]
    unique_colors = df['Color'].unique()
    
    final_tables = []
    grand_total_qty = 0

    for color in unique_colors:
        color_df = df[df['Color'] == color]
        pivot = color_df.pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        
        # Sorting Sizes logic needed here (Assuming sort_sizes exists)
        try:
            sorted_cols = sort_sizes(pivot.columns.tolist())
            pivot = pivot[sorted_cols]
        except: pass # Skip sort if fails
        
        pivot['Total'] = pivot.sum(axis=1)
        grand_total_qty += pivot['Total'].sum()

        # Summary Rows
        actual = pivot.sum()
        plus_3 = (actual * 1.03).round().astype(int)
        
        # HTML Table Construction
        pivot.loc['Actual Qty'] = actual
        pivot.loc['3% Order Qty'] = plus_3
        
        pivot = pivot.reset_index()
        html_table = pivot.to_html(classes='table table-bordered table-striped', index=False)
        
        # Style Injection
        html_table = html_table.replace('<td>Actual Qty</td>', '<td class="summary-row">Actual Qty</td>')
        html_table = html_table.replace('<td>3% Order Qty</td>', '<td class="summary-row">3% Order Qty</td>')

        final_tables.append({'color': color, 'table': html_table})
        
    return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")

# --- EXCEL DOWNLOAD ROUTE ---
@app.route('/download-closing-excel', methods=['GET'])
def download_closing_excel():
    ref_no = request.args.get('ref_no')
    data = fetch_closing_report_data(ref_no)
    if data:
        excel_file = create_formatted_excel_report(data, ref_no)
        return make_response(send_file(
            excel_file, as_attachment=True, 
            download_name=f"Report-{ref_no.replace('/', '-')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
    return redirect(url_for('index'))

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == '__main__':
    # নোট: আপনার অরিজিনাল কোডের `fetch_closing_report_data`, `extract_data_dynamic`, 
    # `sort_sizes`, এবং `create_formatted_excel_report` ফাংশনগুলো 
    # এই ফাইলের উপরের অংশে (Part 1 এর পর) থাকতে হবে।
    
    app.run(debug=True, port=5000)
