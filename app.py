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
    
    # Existing Collections
    users_col = db['users']
    stats_col = db['stats']
    accessories_col = db['accessories']

    # --- NEW STORE PANEL COLLECTIONS ---
    store_products_col = db['store_products']
    store_customers_col = db['store_customers']
    store_invoices_col = db['store_invoices']
    
    print("MongoDB Connected Successfully! (Store Modules Loaded)")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")


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
    </style>
"""
# ==============================================================================
# STORE MODULE TEMPLATES
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MNM Software</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
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
            <a href="/store/dashboard" class="nav-link active">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices/create" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> New Invoice
            </a>
             <a href="/store/invoices/list" class="nav-link">
                <i class="fas fa-list-alt"></i> Invoice List
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-contract"></i> Quotations
            </a>
             <a href="/store/users" class="nav-link">
                <i class="fas fa-user-cog"></i> User Manage
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Store Dashboard</div>
                <div class="page-subtitle">Aluminum Shop Management System</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Store Active</span>
            </div>
        </div>

        <div class="store-grid">
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:13px; color:var(--text-secondary);">TOTAL SALES</div>
                        <div style="font-size:28px; font-weight:800; color:white; margin-top:5px;">
                            ৳{{{{ "{:,.0f}".format(stats.total_sales) }}}}
                        </div>
                    </div>
                    <div style="width:50px; height:50px; background:rgba(16, 185, 129, 0.1); color:var(--accent-green); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;">
                        <i class="fas fa-chart-line"></i>
                    </div>
                </div>
            </div>

            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:13px; color:var(--text-secondary);">TOTAL DUE</div>
                        <div style="font-size:28px; font-weight:800; color:var(--accent-red); margin-top:5px;">
                            ৳{{{{ "{:,.0f}".format(stats.total_due) }}}}
                        </div>
                    </div>
                    <div style="width:50px; height:50px; background:rgba(239, 68, 68, 0.1); color:var(--accent-red); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;">
                        <i class="fas fa-exclamation-circle"></i>
                    </div>
                </div>
            </div>

            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:13px; color:var(--text-secondary);">TODAY'S SALES</div>
                        <div style="font-size:28px; font-weight:800; color:var(--accent-orange); margin-top:5px;">
                            ৳{{{{ "{:,.0f}".format(stats.today_sales) }}}}
                        </div>
                    </div>
                    <div style="width:50px; height:50px; background:rgba(255, 122, 0, 0.1); color:var(--accent-orange); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;">
                        <i class="fas fa-sun"></i>
                    </div>
                </div>
            </div>

            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:13px; color:var(--text-secondary);">CUSTOMERS</div>
                        <div style="font-size:28px; font-weight:800; color:var(--accent-purple); margin-top:5px;">
                            {{{{ stats.customers }}}}
                        </div>
                    </div>
                     <div style="width:50px; height:50px; background:rgba(139, 92, 246, 0.1); color:var(--accent-purple); border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:20px;">
                        <i class="fas fa-users"></i>
                    </div>
                </div>
            </div>
        </div>

        <div class="dashboard-grid-2" style="margin-top:30px;">
            <div class="card">
                <div class="header-section">
                    <span style="font-weight:700;">Quick Actions</span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:15px;">
                    <a href="/store/invoices/create" style="text-decoration:none;">
                        <button style="width:100%; height:100%; padding:20px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color);">
                            <i class="fas fa-plus-circle" style="font-size:24px; color:var(--accent-green); margin-bottom:10px; display:block;"></i>
                            New Invoice
                        </button>
                    </a>
                     <a href="/store/customers" style="text-decoration:none;">
                        <button style="width:100%; height:100%; padding:20px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color);">
                            <i class="fas fa-user-plus" style="font-size:24px; color:var(--accent-purple); margin-bottom:10px; display:block;"></i>
                            Add Customer
                        </button>
                    </a>
                     <a href="/store/products" style="text-decoration:none;">
                        <button style="width:100%; height:100%; padding:20px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color);">
                            <i class="fas fa-box-open" style="font-size:24px; color:var(--accent-orange); margin-bottom:10px; display:block;"></i>
                            Add Product
                        </button>
                    </a>
                </div>
            </div>
             <div class="card">
                <div class="header-section">
                    <span style="font-weight:700;">System Status</span>
                </div>
                <div style="font-size:14px; color:var(--text-secondary); line-height:1.6;">
                    <p><i class="fas fa-server" style="color:var(--accent-green); width:20px;"></i> Database: Online</p>
                    <p><i class="fas fa-clock" style="color:var(--accent-orange); width:20px;"></i> Server Time: {{{{ server_time }}}}</p>
                    <p><i class="fas fa-user-shield" style="color:var(--accent-purple); width:20px;"></i> Logged in as: {{{{ session.user }}}}</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

STORE_PRODUCTS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Products - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/store/dashboard" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/products" class="nav-link active"><i class="fas fa-box"></i> Products</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/invoices/create" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> New Invoice</a>
            <a href="/store/invoices/list" class="nav-link"><i class="fas fa-list-alt"></i> Invoice List</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Product Inventory</div>
                <div class="page-subtitle">Manage aluminum profiles and accessories</div>
            </div>
            <button onclick="document.getElementById('addProductModal').style.display='flex'">
                <i class="fas fa-plus"></i> Add Product
            </button>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="status-badge status-pending" style="margin-bottom:20px; padding:10px 20px; width:100%;">
                    {{{{ messages[0] }}}}
                </div>
            {{% endif %}}
        {{% endwith %}}

        <div class="card">
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Product Name</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th>Price (Tk)</th>
                            <th>Stock</th>
                            <th style="text-align:right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for p in products %}}
                        <tr>
                            <td style="font-weight:600; color:white;">{{{{ p.name }}}}</td>
                            <td><span class="status-badge">{{{{ p.category }}}}</span></td>
                            <td>{{{{ p.unit }}}}</td>
                            <td style="color:var(--accent-green); font-weight:700;">{{{{ p.price }}}}</td>
                            <td>{{{{ p.stock }}}}</td>
                            <td style="text-align:right;">
                                <button onclick="editProduct('{{{{ p._id }}}}', '{{{{ p.name }}}}', '{{{{ p.category }}}}', '{{{{ p.price }}}}', '{{{{ p.stock }}}}', '{{{{ p.unit }}}}')" 
                                        style="padding:6px 12px; font-size:12px; background:var(--accent-purple); margin-right:5px;">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <form action="/store/products/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete product?');">
                                    <input type="hidden" name="product_id" value="{{{{ p._id }}}}">
                                    <button type="submit" style="padding:6px 12px; font-size:12px; background:var(--accent-red);">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </form>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="6" style="text-align:center; padding:30px; color:var(--text-secondary);">
                                No products found. Add your first product!
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Add/Edit Modal -->
    <div id="addProductModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:2000; justify-content:center; align-items:center;">
        <div class="card" style="width:400px; max-width:90%;">
            <div style="margin-bottom:20px; font-size:20px; font-weight:700; color:white;">Product Details</div>
            <form action="/store/products/save" method="POST">
                <input type="hidden" name="product_id" id="modal_product_id">
                <div class="input-group">
                    <label>Product Name</label>
                    <input type="text" name="name" id="modal_name" required>
                </div>
                <div class="input-group">
                    <label>Category</label>
                    <select name="category" id="modal_category">
                        <option value="Aluminum Profile">Aluminum Profile</option>
                        <option value="Glass">Glass</option>
                        <option value="Accessories">Accessories</option>
                        <option value="Sheet">Sheet</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                <div class="input-group">
                    <label>Unit</label>
                    <select name="unit" id="modal_unit">
                        <option value="Pcs">Pcs</option>
                        <option value="Feet">Feet</option>
                        <option value="Kg">Kg</option>
                        <option value="Sq.Ft">Sq.Ft</option>
                    </select>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                    <div class="input-group">
                        <label>Price (Tk)</label>
                        <input type="number" step="0.01" name="price" id="modal_price" required>
                    </div>
                    <div class="input-group">
                        <label>Stock</label>
                        <input type="number" name="stock" id="modal_stock" value="0">
                    </div>
                </div>
                <div style="display:flex; gap:10px; margin-top:10px;">
                    <button type="submit" style="flex:1;">Save Product</button>
                    <button type="button" onclick="closeModal()" style="background:var(--bg-body); border:1px solid var(--border-color); flex:1;">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function editProduct(id, name, cat, price, stock, unit) {{
            document.getElementById('modal_product_id').value = id;
            document.getElementById('modal_name').value = name;
            document.getElementById('modal_category').value = cat;
            document.getElementById('modal_price').value = price;
            document.getElementById('modal_stock').value = stock;
            document.getElementById('modal_unit').value = unit;
            document.getElementById('addProductModal').style.display = 'flex';
        }}
        
        function closeModal() {{
            document.getElementById('addProductModal').style.display = 'none';
            // Reset form
            document.getElementById('modal_product_id').value = '';
            document.getElementsByName('name')[0].value = '';
            document.getElementsByName('price')[0].value = '';
            document.getElementsByName('stock')[0].value = '0';
        }}
    </script>
</body>
</html>
"""
STORE_CUSTOMERS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Customers - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/store/dashboard" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <a href="/store/customers" class="nav-link active"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/invoices/create" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> New Invoice</a>
            <a href="/store/invoices/list" class="nav-link"><i class="fas fa-list-alt"></i> Invoice List</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Customer Management</div>
                <div class="page-subtitle">Manage client details and dues</div>
            </div>
            <button onclick="document.getElementById('addCustomerModal').style.display='flex'">
                <i class="fas fa-user-plus"></i> Add Customer
            </button>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="status-badge status-pending" style="margin-bottom:20px; padding:10px 20px; width:100%;">
                    {{{{ messages[0] }}}}
                </div>
            {{% endif %}}
        {{% endwith %}}

        <div class="card">
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Total Due</th>
                            <th style="text-align:right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for c in customers %}}
                        <tr>
                            <td style="font-weight:600; color:white;">{{{{ c.name }}}}</td>
                            <td>{{{{ c.phone }}}}</td>
                            <td style="font-size:12px; color:var(--text-secondary);">{{{{ c.address }}}}</td>
                            <td>
                                {{% if c.total_due > 0 %}}
                                <span style="color:var(--accent-red); font-weight:700;">৳{{{{ "{:,.0f}".format(c.total_due) }}}}</span>
                                {{% else %}}
                                <span style="color:var(--accent-green);">Paid</span>
                                {{% endif %}}
                            </td>
                            <td style="text-align:right;">
                                <button onclick="editCustomer('{{{{ c._id }}}}', '{{{{ c.name }}}}', '{{{{ c.phone }}}}', '{{{{ c.address }}}}')" 
                                        style="padding:6px 12px; font-size:12px; background:var(--accent-purple); margin-right:5px;">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <a href="/store/invoices/create?customer_id={{{{ c._id }}}}" style="text-decoration:none;">
                                    <button style="padding:6px 12px; font-size:12px; background:var(--accent-green);">
                                        <i class="fas fa-file-invoice"></i> Inv
                                    </button>
                                </a>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="5" style="text-align:center; padding:30px; color:var(--text-secondary);">
                                No customers found.
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Add/Edit Customer Modal -->
    <div id="addCustomerModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:2000; justify-content:center; align-items:center;">
        <div class="card" style="width:400px; max-width:90%;">
            <div style="margin-bottom:20px; font-size:20px; font-weight:700; color:white;">Customer Details</div>
            <form action="/store/customers/save" method="POST">
                <input type="hidden" name="customer_id" id="modal_customer_id">
                <div class="input-group">
                    <label>Full Name</label>
                    <input type="text" name="name" id="modal_name" required>
                </div>
                <div class="input-group">
                    <label>Phone Number</label>
                    <input type="text" name="phone" id="modal_phone" required>
                </div>
                <div class="input-group">
                    <label>Address</label>
                    <textarea name="address" id="modal_address" rows="3"></textarea>
                </div>
                <div style="display:flex; gap:10px; margin-top:10px;">
                    <button type="submit" style="flex:1;">Save Customer</button>
                    <button type="button" onclick="closeCustomerModal()" style="background:var(--bg-body); border:1px solid var(--border-color); flex:1;">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function editCustomer(id, name, phone, address) {{
            document.getElementById('modal_customer_id').value = id;
            document.getElementById('modal_name').value = name;
            document.getElementById('modal_phone').value = phone;
            document.getElementById('modal_address').value = address;
            document.getElementById('addCustomerModal').style.display = 'flex';
        }}
        
        function closeCustomerModal() {{
            document.getElementById('addCustomerModal').style.display = 'none';
            document.getElementById('modal_customer_id').value = '';
            document.getElementsByName('name')[0].value = '';
            document.getElementsByName('phone')[0].value = '';
            document.getElementsByName('address')[0].value = '';
        }}
    </script>
</body>
</html>
"""

STORE_CREATE_INVOICE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Create Invoice - Store Panel</title>
    {COMMON_STYLES}
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <style>
        .select2-container--default .select2-selection--single {{ background-color: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color); height: 45px; border-radius: 10px; }}
        .select2-container--default .select2-selection--single .select2-selection__rendered {{ color: white; line-height: 45px; padding-left: 15px; }}
        .select2-dropdown {{ background-color: #1a1a25; border: 1px solid var(--border-color); color: white; }}
        .select2-results__option[aria-selected=true] {{ background-color: var(--accent-orange); }}
        
        .product-row {{ display: grid; grid-template-columns: 3fr 1fr 1fr 1fr 40px; gap: 10px; margin-bottom: 10px; align-items: center; }}
        .summary-box {{ background: rgba(0,0,0,0.2); padding: 15px; border-radius: 10px; margin-top: 20px; }}
        .summary-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }}
        .summary-total {{ font-size: 18px; font-weight: 800; color: var(--accent-orange); border-top: 1px solid var(--border-color); padding-top: 10px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/store/dashboard" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/invoices/create" class="nav-link active"><i class="fas fa-file-invoice-dollar"></i> New Invoice</a>
            <a href="/store/invoices/list" class="nav-link"><i class="fas fa-list-alt"></i> Invoice List</a>
        </div>
    </div>

    <div class="main-content">
        <form action="/store/invoices/save" method="POST" id="invoiceForm">
            <div class="header-section">
                <div>
                    <div class="page-title">New Invoice</div>
                    <div class="page-subtitle">Create sales invoice or quotation</div>
                </div>
                <div style="display:flex; gap:10px;">
                    <select name="type" style="width:150px; background:var(--accent-purple);">
                        <option value="Invoice">Sales Invoice</option>
                        <option value="Quotation">Quotation</option>
                    </select>
                    <button type="submit"><i class="fas fa-save"></i> Save Invoice</button>
                </div>
            </div>

            <div class="dashboard-grid-2">
                <!-- Left: Products & Customer -->
                <div style="display:flex; flex-direction:column; gap:20px;">
                    <!-- Customer Selection -->
                    <div class="card">
                        <div style="margin-bottom:15px; font-weight:700;">Customer Details</div>
                        <div style="display:flex; gap:15px;">
                            <div style="flex:2;">
                                <select name="customer_id" id="customerSelect" style="width:100%;">
                                    <option value="">Select Existing Customer</option>
                                    {{% for c in customers %}}
                                    <option value="{{{{ c._id }}}}" {{% if pre_customer == c._id|string %}}selected{{% endif %}}>{{{{ c.name }}}} - {{{{ c.phone }}}}</option>
                                    {{% endfor %}}
                                </select>
                            </div>
                            <div style="flex:1;">
                                <input type="text" name="customer_name" id="new_cus_name" placeholder="Or New Customer Name">
                            </div>
                            <div style="flex:1;">
                                <input type="text" name="customer_phone" id="new_cus_phone" placeholder="Phone">
                            </div>
                        </div>
                        <div style="margin-top:10px;">
                            <input type="text" name="customer_address" id="new_cus_address" placeholder="Address (Optional)">
                        </div>
                    </div>

                    <!-- Product List -->
                    <div class="card">
                        <div style="margin-bottom:15px; font-weight:700; display:flex; justify-content:space-between;">
                            <span>Items</span>
                            <button type="button" onclick="addProductRow()" style="padding:5px 10px; font-size:12px; width:auto;">+ Add Item</button>
                        </div>
                        
                        <div id="productContainer">
                            <!-- Headers -->
                            <div class="product-row" style="font-size:12px; color:var(--text-secondary); border-bottom:1px solid var(--border-color); padding-bottom:5px;">
                                <div>Product</div>
                                <div>Price</div>
                                <div>Qty</div>
                                <div>Total</div>
                                <div></div>
                            </div>
                            <!-- Dynamic Rows will be added here -->
                        </div>
                    </div>
                </div>

                <!-- Right: Totals -->
                <div class="card" style="height:fit-content;">
                    <div style="font-weight:700; margin-bottom:15px;">Payment Details</div>
                    
                    <div class="input-group">
                        <label>Discount (Tk)</label>
                        <input type="number" name="discount" id="discount" value="0" oninput="calculateGrandTotal()">
                    </div>

                    <div class="summary-box">
                        <div class="summary-row">
                            <span>Sub Total:</span>
                            <span id="subTotal">0.00</span>
                        </div>
                        <div class="summary-row" style="color:var(--accent-red);">
                            <span>Discount:</span>
                            <span id="discountDisplay">0.00</span>
                        </div>
                        <div class="summary-row summary-total">
                            <span>Grand Total:</span>
                            <span id="grandTotal">0.00</span>
                        </div>
                    </div>

                    <div class="input-group" style="margin-top:20px;">
                        <label>Paid Amount</label>
                        <input type="number" name="paid_amount" id="paidAmount" value="0" oninput="calculateDue()">
                    </div>
                    
                    <div style="text-align:center; margin-top:10px; font-size:14px;">
                        Due: <span id="dueAmount" style="font-weight:800; color:var(--accent-red);">0.00</span>
                    </div>
                </div>
            </div>
        </form>
    </div>

    <!-- Hidden Template for JS -->
    <select id="productMasterList" style="display:none;">
        <option value="">Select Product</option>
        {{% for p in products %}}
        <option value="{{{{ p._id }}}}" data-price="{{{{ p.price }}}}">{{{{ p.name }}}} ({{{{ p.stock }}}} {{{{ p.unit }}}})</option>
        {{% endfor %}}
    </select>

    <script>
        $(document).ready(function() {{
            $('#customerSelect').select2();
            addProductRow(); // Add initial row
        }});

        function addProductRow() {{
            const rowId = Date.now();
            const options = $('#productMasterList').html();
            
            const html = `
                <div class="product-row" id="row_${{rowId}}">
                    <select name="product_ids[]" class="p-select" onchange="updatePrice(this, ${{rowId}})" required>
                        ${{options}}
                    </select>
                    <input type="number" name="prices[]" id="price_${{rowId}}" step="0.01" oninput="updateRowTotal(${{rowId}})" required placeholder="0.00">
                    <input type="number" name="quantities[]" id="qty_${{rowId}}" step="0.01" value="1" oninput="updateRowTotal(${{rowId}})" required>
                    <input type="number" class="row-total" id="total_${{rowId}}" readonly value="0.00" style="background:rgba(0,0,0,0.3); border:none;">
                    <button type="button" onclick="removeRow(${{rowId}})" style="padding:5px; background:var(--accent-red); color:white; width:30px; height:30px; display:flex; align-items:center; justify-content:center;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            $('#productContainer').append(html);
            $(`#row_${{rowId}} .p-select`).select2();
        }}

        function removeRow(id) {{
            $(`#row_${{id}}`).remove();
            calculateGrandTotal();
        }}

        function updatePrice(select, id) {{
            const price = $(select).find(':selected').data('price');
            $(`#price_${{id}}`).val(price);
            updateRowTotal(id);
        }}

        function updateRowTotal(id) {{
            const price = parseFloat($(`#price_${{id}}`).val()) || 0;
            const qty = parseFloat($(`#qty_${{id}}`).val()) || 0;
            const total = price * qty;
            $(`#total_${{id}}`).val(total.toFixed(2));
            calculateGrandTotal();
        }}

        function calculateGrandTotal() {{
            let subTotal = 0;
            $('.row-total').each(function() {{
                subTotal += parseFloat($(this).val()) || 0;
            }});
            
            const discount = parseFloat($('#discount').val()) || 0;
            const grandTotal = subTotal - discount;

            $('#subTotal').text(subTotal.toFixed(2));
            $('#discountDisplay').text(discount.toFixed(2));
            $('#grandTotal').text(grandTotal.toFixed(2));
            
            calculateDue();
        }}

        function calculateDue() {{
            const grandTotal = parseFloat($('#grandTotal').text()) || 0;
            const paid = parseFloat($('#paidAmount').val()) || 0;
            const due = grandTotal - paid;
            $('#dueAmount').text(due.toFixed(2));
        }}
    </script>
</body>
</html>
"""
STORE_INVOICE_LIST_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Invoices - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/store/dashboard" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/invoices/create" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> New Invoice</a>
            <a href="/store/invoices/list" class="nav-link active"><i class="fas fa-list-alt"></i> Invoice List</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoice History</div>
                <div class="page-subtitle">Track sales and payments</div>
            </div>
            <div class="input-group" style="width: 300px; margin-bottom:0;">
                <input type="text" placeholder="Search Invoice or Customer..." onkeyup="searchTable(this.value)">
            </div>
        </div>

        <div class="card">
            <div style="overflow-x: auto;">
                <table class="dark-table" id="invoiceTable">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align:right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in invoices %}}
                        <tr>
                            <td>
                                <div class="time-badge">{{{{ inv.date }}}}</div>
                            </td>
                            <td style="font-weight:700; color:white;">{{{{ inv.invoice_no }}}}</td>
                            <td>{{{{ inv.customer_name }}}}</td>
                            <td style="font-weight:700;">{{{{ "{:,.2f}".format(inv.grand_total) }}}}</td>
                            <td style="color:var(--accent-green);">{{{{ "{:,.2f}".format(inv.paid_amount) }}}}</td>
                            <td style="color:var(--accent-red);">{{{{ "{:,.2f}".format(inv.due_amount) }}}}</td>
                            <td>
                                {{% if inv.due_amount <= 0 %}}
                                <span class="status-badge" style="background:rgba(16, 185, 129, 0.1); color:var(--accent-green);">Paid</span>
                                {{% else %}}
                                <span class="status-badge status-pending">Due</span>
                                {{% endif %}}
                            </td>
                            <td style="text-align:right;">
                                <a href="/store/invoices/print/{{{{ inv.invoice_no }}}}" target="_blank" class="action-btn" style="background:var(--accent-blue); color:white; margin-right:5px;">
                                    <i class="fas fa-print"></i>
                                </a>
                                <a href="/store/invoices/edit/{{{{ inv.invoice_no }}}}" class="action-btn btn-edit">
                                    <i class="fas fa-edit"></i>
                                </a>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="8" style="text-align:center; padding:40px; color:var(--text-secondary);">
                                <i class="fas fa-file-invoice" style="font-size:30px; margin-bottom:10px; display:block; opacity:0.3;"></i>
                                No invoices found.
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <script>
        function searchTable(val) {{
            val = val.toLowerCase();
            const rows = document.querySelectorAll('#invoiceTable tbody tr');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(val) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

STORE_PRINT_INVOICE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ inv.invoice_no }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; color: #333; padding: 40px; max-width: 800px; margin: 0 auto; background: white; }
        .header { display: flex; justify-content: space-between; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }
        .company-info h1 { margin: 0; color: #FF7A00; font-size: 28px; text-transform: uppercase; }
        .company-info p { margin: 5px 0; color: #666; font-size: 13px; }
        .invoice-details { text-align: right; }
        .invoice-details h2 { margin: 0; font-size: 24px; color: #333; }
        .meta { margin-top: 10px; font-size: 14px; color: #555; }
        
        .bill-to { margin-bottom: 30px; background: #f9f9f9; padding: 20px; border-radius: 8px; }
        .bill-to h3 { margin: 0 0 10px 0; font-size: 12px; text-transform: uppercase; color: #888; letter-spacing: 1px; }
        .customer-name { font-size: 18px; font-weight: 700; margin-bottom: 5px; }
        
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        th { text-align: left; padding: 12px; border-bottom: 2px solid #333; font-size: 12px; text-transform: uppercase; }
        td { padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
        .total-row td { border-bottom: none; font-weight: 700; text-align: right; }
        
        .totals { float: right; width: 300px; }
        .totals-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
        .totals-row.final { border-top: 2px solid #333; border-bottom: none; font-size: 18px; font-weight: 800; margin-top: 10px; padding-top: 15px; }
        
        .footer { clear: both; margin-top: 80px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #888; text-align: center; }
        .status-stamp { position: absolute; top: 200px; right: 50px; font-size: 40px; font-weight: 900; color: rgba(255, 0, 0, 0.1); border: 4px solid rgba(255, 0, 0, 0.1); padding: 10px 20px; text-transform: uppercase; transform: rotate(-20deg); pointer-events: none; }
        .status-paid { color: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.1); }

        @media print {
            body { padding: 0; margin: 0; }
            .no-print { display: none; }
        }
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="padding: 10px 20px; background: #333; color: white; border: none; cursor: pointer;">Print Invoice</button>
    </div>

    {% if inv.due_amount <= 0 %}
        <div class="status-stamp status-paid">PAID</div>
    {% else %}
        <div class="status-stamp">DUE</div>
    {% endif %}

    <div class="header">
        <div class="company-info">
            <h1>AluStore Panel</h1>
            <p>Kazi Tower, Tongi, Gazipur</p>
            <p>Phone: +880 1234 567890</p>
        </div>
        <div class="invoice-details">
            <h2>{{ inv.type|upper }}</h2>
            <div class="meta"># {{ inv.invoice_no }}</div>
            <div class="meta">Date: {{ inv.date }}</div>
        </div>
    </div>

    <div class="bill-to">
        <h3>Bill To</h3>
        <div class="customer-name">{{ inv.customer_name }}</div>
        <div>{{ inv.customer_phone }}</div>
        {% if inv.customer_address %}<div>{{ inv.customer_address }}</div>{% endif %}
    </div>

    <table>
        <thead>
            <tr>
                <th>Item Description</th>
                <th style="text-align: center;">Unit Price</th>
                <th style="text-align: center;">Qty</th>
                <th style="text-align: right;">Total</th>
            </tr>
        </thead>
        <tbody>
            {% for item in inv.items %}
            <tr>
                <td>{{ item.product_name }}</td>
                <td style="text-align: center;">{{ item.price }}</td>
                <td style="text-align: center;">{{ item.qty }}</td>
                <td style="text-align: right;">{{ "{:,.2f}".format(item.total) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="totals">
        <div class="totals-row">
            <span>Sub Total:</span>
            <span>{{ "{:,.2f}".format(inv.sub_total) }}</span>
        </div>
        {% if inv.discount > 0 %}
        <div class="totals-row">
            <span>Discount:</span>
            <span>-{{ "{:,.2f}".format(inv.discount) }}</span>
        </div>
        {% endif %}
        <div class="totals-row final">
            <span>Grand Total:</span>
            <span>{{ "{:,.2f}".format(inv.grand_total) }}</span>
        </div>
        <div class="totals-row">
            <span>Paid Amount:</span>
            <span>{{ "{:,.2f}".format(inv.paid_amount) }}</span>
        </div>
        <div class="totals-row" style="color: #e74c3c; font-weight: 700;">
            <span>Due Amount:</span>
            <span>{{ "{:,.2f}".format(inv.due_amount) }}</span>
        </div>
    </div>

    <div class="footer">
        <p>Thank you for your business!</p>
        <p>This is a computer generated invoice.</p>
    </div>
</body>
</html>
"""

STORE_USER_MANAGE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Store Users - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars" style="color:white;"></i>
    </div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            <a href="/store/dashboard" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/users" class="nav-link active"><i class="fas fa-user-cog"></i> User Manage</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Store User Management</div>
                <div class="page-subtitle">Manage staff access for store panel</div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- User List -->
            <div class="card">
                <div class="section-header"><span>Store Staff</span></div>
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Role</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for u, d in users.items() %}}
                            {{% if 'store_panel' in d.permissions and d.role != 'admin' %}}
                            <tr>
                                <td style="font-weight:600;">{{{{ u }}}}</td>
                                <td><span class="status-badge">Staff</span></td>
                                <td>
                                    <form action="/store/users/delete" method="POST" onsubmit="return confirm('Remove user?');">
                                        <input type="hidden" name="username" value="{{{{ u }}}}">
                                        <button type="submit" class="btn-del action-btn"><i class="fas fa-trash"></i></button>
                                    </form>
                                </td>
                            </tr>
                            {{% endif %}}
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>

            <!-- Add User -->
            <div class="card">
                <div class="section-header"><span>Add Staff</span></div>
                <form action="/store/users/add" method="POST">
                    <div class="input-group">
                        <label>Username</label>
                        <input type="text" name="username" required>
                    </div>
                    <div class="input-group">
                        <label>Password</label>
                        <input type="text" name="password" required>
                    </div>
                    <div class="input-group">
                         <label style="display:flex; align-items:center; gap:10px;">
                            <input type="checkbox" name="can_delete" style="width:auto;">
                            Allow Delete Permissions
                        </label>
                    </div>
                    <button type="submit">Create Staff Account</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTES (STORE CONTROLLERS)
# ==============================================================================

# --- Store Dashboard ---
@app.route('/store/dashboard')
def store_dashboard_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    # Check if user has store permission
    if 'store_panel' not in session.get('permissions', []):
        flash("Access Denied: Store Panel permission required.")
        return redirect(url_for('index'))
    
    stats = get_store_stats()
    server_time = get_bd_time().strftime("%d-%b-%Y %I:%M %p")
    return render_template_string(STORE_DASHBOARD_TEMPLATE, stats=stats, server_time=server_time)

# --- Product Management ---
@app.route('/store/products')
def store_products_list():
    if not session.get('logged_in'): return redirect(url_for('index'))
    products = list(store_products_col.find({}))
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products)

@app.route('/store/products/save', methods=['POST'])
def store_product_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    p_id = request.form.get('product_id')
    name = request.form.get('name')
    category = request.form.get('category')
    unit = request.form.get('unit')
    price = float(request.form.get('price') or 0)
    stock = float(request.form.get('stock') or 0)
    
    data = {
        "name": name,
        "category": category,
        "unit": unit,
        "price": price,
        "stock": stock,
        "updated_at": get_bd_time()
    }

    if p_id:
        store_products_col.update_one({"_id": ObjectId(p_id)}, {"$set": data})
        flash("Product updated successfully!")
    else:
        store_products_col.insert_one(data)
        flash("Product added successfully!")
        
    return redirect(url_for('store_products_list'))

@app.route('/store/products/delete', methods=['POST'])
def store_product_delete():
    if not session.get('logged_in'): return redirect(url_for('index'))
    p_id = request.form.get('product_id')
    store_products_col.delete_one({"_id": ObjectId(p_id)})
    flash("Product deleted.")
    return redirect(url_for('store_products_list'))

# --- Customer Management ---
@app.route('/store/customers')
def store_customers_list():
    if not session.get('logged_in'): return redirect(url_for('index'))
    customers = list(store_customers_col.find({}))
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)

@app.route('/store/customers/save', methods=['POST'])
def store_customer_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    c_id = request.form.get('customer_id')
    name = request.form.get('name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    
    data = {
        "name": name,
        "phone": phone,
        "address": address,
        "updated_at": get_bd_time()
    }
    
    if c_id:
        store_customers_col.update_one({"_id": ObjectId(c_id)}, {"$set": data})
        flash("Customer updated.")
    else:
        data["total_due"] = 0 # Initialize due for new customer
        store_customers_col.insert_one(data)
        flash("Customer added.")
        
    return redirect(url_for('store_customers_list'))

# --- Invoice Management ---
@app.route('/store/invoices/create')
def store_invoice_create():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    # Pre-select customer if passed via query param
    pre_customer = request.args.get('customer_id', '')
    
    customers = list(store_customers_col.find({}))
    products = list(store_products_col.find({}))
    
    return render_template_string(STORE_CREATE_INVOICE_TEMPLATE, customers=customers, products=products, pre_customer=pre_customer)

@app.route('/store/invoices/save', methods=['POST'])
def store_invoice_save():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    try:
        # 1. Handle Customer
        customer_id = request.form.get('customer_id')
        
        if not customer_id:
            # Create new customer on the fly
            new_cus_data = {
                "name": request.form.get('customer_name'),
                "phone": request.form.get('customer_phone'),
                "address": request.form.get('customer_address'),
                "total_due": 0,
                "created_at": get_bd_time()
            }
            res = store_customers_col.insert_one(new_cus_data)
            customer_id = str(res.inserted_id)
            customer_name = new_cus_data['name']
            customer_phone = new_cus_data['phone']
            customer_address = new_cus_data['address']
        else:
            # Get existing customer details
            cus = store_customers_col.find_one({"_id": ObjectId(customer_id)})
            customer_name = cus['name']
            customer_phone = cus['phone']
            customer_address = cus.get('address', '')

        # 2. Process Invoice Items
        product_ids = request.form.getlist('product_ids[]')
        prices = request.form.getlist('prices[]')
        quantities = request.form.getlist('quantities[]')
        
        items = []
        sub_total = 0
        
        for i in range(len(product_ids)):
            p_id = product_ids[i]
            if not p_id: continue
            
            price = float(prices[i])
            qty = float(quantities[i])
            total = price * qty
            sub_total += total
            
            # Get Product Name for Invoice Record
            prod = store_products_col.find_one({"_id": ObjectId(p_id)})
            items.append({
                "product_id": p_id,
                "product_name": prod['name'],
                "price": price,
                "qty": qty,
                "total": total
            })
            
            # Update Stock
            new_stock = float(prod.get('stock', 0)) - qty
            store_products_col.update_one({"_id": ObjectId(p_id)}, {"$set": {"stock": new_stock}})

        # 3. Calculate Totals
        discount = float(request.form.get('discount') or 0)
        paid_amount = float(request.form.get('paid_amount') or 0)
        grand_total = sub_total - discount
        due_amount = grand_total - paid_amount
        
        # 4. Create Invoice Record
        invoice_data = {
            "invoice_no": generate_invoice_id(),
            "date": get_bd_date_str(),
            "iso_date": get_bd_time(),
            "type": request.form.get('type'), # Invoice or Quotation
            "customer_id": customer_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "items": items,
            "sub_total": sub_total,
            "discount": discount,
            "grand_total": grand_total,
            "paid_amount": paid_amount,
            "due_amount": due_amount,
            "created_by": session.get('user')
        }
        
        store_invoices_col.insert_one(invoice_data)
        
        # 5. Update Customer Due
        if request.form.get('type') == 'Invoice': # Only update due for actual Invoices, not Quotations
            store_customers_col.update_one(
                {"_id": ObjectId(customer_id)}, 
                {"$inc": {"total_due": due_amount}}
            )

        flash("Invoice saved successfully!")
        return redirect(url_for('store_invoices_list'))

    except Exception as e:
        flash(f"Error saving invoice: {str(e)}")
        return redirect(url_for('store_invoices_list'))

@app.route('/store/invoices/list')
def store_invoices_list():
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoices = list(store_invoices_col.find({}).sort("iso_date", -1))
    return render_template_string(STORE_INVOICE_LIST_TEMPLATE, invoices=invoices)

@app.route('/store/invoices/print/<invoice_no>')
def store_invoice_print(invoice_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    inv = store_invoices_col.find_one({"invoice_no": invoice_no})
    if not inv: return "Invoice Not Found"
    return render_template_string(STORE_PRINT_INVOICE_TEMPLATE, inv=inv)

# --- Store User Management ---
@app.route('/store/users')
def store_users_list():
    if not session.get('logged_in') or session.get('role') != 'admin': return redirect(url_for('index'))
    users = load_users()
    return render_template_string(STORE_USER_MANAGE_TEMPLATE, users=users)

@app.route('/store/users/add', methods=['POST'])
def store_user_add():
    if not session.get('logged_in') or session.get('role') != 'admin': return redirect(url_for('index'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    users = load_users()
    if username in users:
        flash("User already exists")
        return redirect(url_for('store_users_list'))
        
    users[username] = {
        "password": password,
        "role": "user",
        "permissions": ["store_panel"], # Store only permission
        "created_at": get_bd_date_str()
    }
    save_users(users)
    flash("Store Staff Added")
    return redirect(url_for('store_users_list'))

@app.route('/store/users/delete', methods=['POST'])
def store_user_delete():
    if not session.get('logged_in') or session.get('role') != 'admin': return redirect(url_for('index'))
    username = request.form.get('username')
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
    return redirect(url_for('store_users_list'))
    # ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    # Render requires binding to 0.0.0.0 and the PORT env variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
