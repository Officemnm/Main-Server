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
from bson import ObjectId

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
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=120) 

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
    
    # স্টোর প্যানেলের জন্য নতুন কালেকশন
    store_users_col = db['store_users']
    store_customers_col = db['store_customers']
    store_products_col = db['store_products']
    store_invoices_col = db['store_invoices']
    store_quotations_col = db['store_quotations']
    store_dues_col = db['store_dues']
    store_payments_col = db['store_payments']
    store_settings_col = db['store_settings']
    
    print("MongoDB Connected Successfully!")
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

        textarea {
            resize: vertical;
            min-height: 100px;
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

        .btn-view {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
        }

        .btn-view:hover {
            background: var(--accent-green);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.4);
        }

        .btn-pay {
            background: rgba(59, 130, 246, 0.15);
            color: #60A5FA;
        }

        .btn-pay:hover {
            background: var(--accent-blue);
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
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

        /* Store Specific Styles */
        .taka-symbol {
            font-family: 'Noto Sans Bengali', sans-serif;
        }

        .amount-positive {
            color: var(--accent-green);
            font-weight: 700;
        }

        .amount-negative {
            color: var(--accent-red);
            font-weight: 700;
        }

        .due-badge {
            background: rgba(239, 68, 68, 0.15);
            color: #F87171;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }

        .paid-badge {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }

        .partial-badge {
            background: rgba(255, 122, 0, 0.15);
            color: var(--accent-orange);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }

        /* Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            z-index: 10000;
            justify-content: center;
            align-items: center;
        }

        .modal-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 30px;
            max-width: 500px;
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
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--border-color);
        }

        .modal-title {
            font-size: 20px;
            font-weight: 700;
            color: white;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 24px;
            cursor: pointer;
            padding: 5px;
            transition: var(--transition-smooth);
            width: auto;
        }

        .modal-close:hover {
            color: var(--accent-red);
            transform: rotate(90deg);
        }

        /* Grid Layouts */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
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

        /* Quick Stats Row */
        .quick-stats {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 25px;
        }

        .quick-stat-item {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 15px 20px;
            flex: 1;
            min-width: 150px;
            text-align: center;
        }

        .quick-stat-value {
            font-size: 24px;
            font-weight: 800;
            color: white;
        }

        .quick-stat-label {
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }

        /* Invoice Table Styles */
        .invoice-items-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        .invoice-items-table th {
            background: rgba(255, 122, 0, 0.1);
            padding: 12px;
            text-align: left;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-orange);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .invoice-items-table td {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
        }

        .invoice-items-table .item-remove {
            color: var(--accent-red);
            cursor: pointer;
            font-size: 16px;
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

        /* Filter Tabs */
        .filter-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .filter-tab {
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition-smooth);
        }

        .filter-tab:hover, .filter-tab.active {
            background: rgba(255, 122, 0, 0.1);
            border-color: var(--accent-orange);
            color: var(--accent-orange);
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
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store"],
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
    now = get_bd_time()
    new_record = {
        "ref": ref_no,
        "user": username,
        "date": now.strftime('%d-%m-%Y'),
        "time": now.strftime('%I:%M %p'),
        "type": "Closing Report",
        "iso_time": now.isoformat()
    }
    data['downloads'].insert(0, new_record)
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
# স্টোর প্যানেল হেল্পার ফাংশন
# ==============================================================================

def load_store_settings():
    """স্টোর সেটিংস লোড করে"""
    record = store_settings_col.find_one({"_id": "store_config"})
    default_settings = {
        "store_name": "MNM Aluminum Store",
        "store_address": "Dhaka, Bangladesh",
        "store_phone": "01700000000",
        "store_email": "store@example.com",
        "invoice_prefix": "INV",
        "quotation_prefix": "QTN",
        "currency_symbol": "৳",
        "tax_rate": 0
    }
    if record:
        return record['data']
    else:
        store_settings_col.insert_one({"_id": "store_config", "data": default_settings})
        return default_settings

def save_store_settings(data):
    """স্টোর সেটিংস সেভ করে"""
    store_settings_col.replace_one(
        {"_id": "store_config"},
        {"_id": "store_config", "data": data},
        upsert=True
    )

def generate_invoice_number():
    """নতুন ইনভয়েস নম্বর জেনারেট করে"""
    settings = load_store_settings()
    prefix = settings.get('invoice_prefix', 'INV')
    
    # সর্বশেষ ইনভয়েস খুঁজে বের করা
    last_invoice = store_invoices_col.find_one(
        sort=[("invoice_number", -1)]
    )
    
    if last_invoice and 'invoice_number' in last_invoice:
        try:
            last_num = int(last_invoice['invoice_number'].replace(prefix + "-", ""))
            new_num = last_num + 1
        except:
            new_num = 1001
    else:
        new_num = 1001
    
    return f"{prefix}-{new_num}"

def generate_quotation_number():
    """নতুন কোটেশন নম্বর জেনারেট করে"""
    settings = load_store_settings()
    prefix = settings.get('quotation_prefix', 'QTN')
    
    last_quotation = store_quotations_col.find_one(
        sort=[("quotation_number", -1)]
    )
    
    if last_quotation and 'quotation_number' in last_quotation:
        try:
            last_num = int(last_quotation['quotation_number'].replace(prefix + "-", ""))
            new_num = last_num + 1
        except:
            new_num = 1001
    else:
        new_num = 1001
    
    return f"{prefix}-{new_num}"

def get_store_dashboard_stats():
    """স্টোর ড্যাশবোর্ডের জন্য পরিসংখ্যান"""
    today = get_bd_date_str()
    
    # মোট কাস্টমার
    total_customers = store_customers_col.count_documents({})
    
    # মোট প্রোডাক্ট
    total_products = store_products_col.count_documents({})
    
    # মোট ইনভয়েস
    total_invoices = store_invoices_col.count_documents({})
    
    # আজকের ইনভয়েস
    today_invoices = store_invoices_col.count_documents({"date": today})
    
    # মোট সেল (সব ইনভয়েসের যোগফল)
    pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}
    ]
    total_sales_result = list(store_invoices_col.aggregate(pipeline))
    total_sales = total_sales_result[0]['total'] if total_sales_result else 0
    
    # আজকের সেল
    pipeline_today = [
        {"$match": {"date": today}},
        {"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}
    ]
    today_sales_result = list(store_invoices_col.aggregate(pipeline_today))
    today_sales = today_sales_result[0]['total'] if today_sales_result else 0
    
    # মোট বাকি
    pipeline_due = [
        {"$group": {"_id": None, "total": {"$sum": "$due_amount"}}}
    ]
    total_due_result = list(store_invoices_col.aggregate(pipeline_due))
    total_due = total_due_result[0]['total'] if total_due_result else 0
    
    # মোট পেমেন্ট রিসিভড
    pipeline_paid = [
        {"$group": {"_id": None, "total": {"$sum": "$paid_amount"}}}
    ]
    total_paid_result = list(store_invoices_col.aggregate(pipeline_paid))
    total_paid = total_paid_result[0]['total'] if total_paid_result else 0
    
    # সাম্প্রতিক ইনভয়েস (শেষ ১০টি)
    recent_invoices = list(store_invoices_col.find().sort("created_at", -1).limit(10))
    
    # সাম্প্রতিক পেমেন্ট (শেষ ১০টি)
    recent_payments = list(store_payments_col.find().sort("date", -1).limit(10))
    
    # বাকিদার কাস্টমার লিস্ট
    due_customers = list(store_invoices_col.aggregate([
        {"$match": {"due_amount": {"$gt": 0}}},
        {"$group": {
            "_id": "$customer_id",
            "customer_name": {"$first": "$customer_name"},
            "total_due": {"$sum": "$due_amount"},
            "invoice_count": {"$sum": 1}
        }},
        {"$sort": {"total_due": -1}},
        {"$limit": 10}
    ]))
    
    return {
        "total_customers": total_customers,
        "total_products": total_products,
        "total_invoices": total_invoices,
        "today_invoices": today_invoices,
        "total_sales": total_sales,
        "today_sales": today_sales,
        "total_due": total_due,
        "total_paid": total_paid,
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
        "due_customers": due_customers
    }

def get_customer_details(customer_id):
    """কাস্টমারের সম্পূর্ণ তথ্য ও লেনদেন"""
    customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        return None
    
    # কাস্টমারের সব ইনভয়েস
    invoices = list(store_invoices_col.find({"customer_id": str(customer_id)}).sort("created_at", -1))
    
    # কাস্টমারের সব পেমেন্ট
    payments = list(store_payments_col.find({"customer_id": str(customer_id)}).sort("date", -1))
    
    # মোট ক্রয়
    total_purchase = sum(inv.get('grand_total', 0) for inv in invoices)
    
    # মোট পেমেন্ট
    total_paid = sum(inv.get('paid_amount', 0) for inv in invoices)
    
    # মোট বাকি
    total_due = sum(inv.get('due_amount', 0) for inv in invoices)
    
    return {
        "customer": customer,
        "invoices": invoices,
        "payments": payments,
        "total_purchase": total_purchase,
        "total_paid": total_paid,
        "total_due": total_due
    }

# --- আপডেটেড: রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স ---
def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    now = get_bd_time()
    today_str = now.strftime('%d-%m-%Y')
    
    # 1.User Stats
    user_details = []
    for u, d in users_data.items():
        user_details.append({
            "username": u,
            "role": d.get('role', 'user'),
            "created_at": d.get('created_at', 'N/A'),
            "last_login": d.get('last_login', 'Never'),
            "last_duration": d.get('last_duration', 'N/A')
        })

    # 2. Accessories Today & Analytics - LIFETIME COUNT
    acc_lifetime_count = 0
    acc_today_list = []
    
    daily_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0})

    for ref, data in acc_db.items():
        for challan in data.get('challans', []):
            acc_lifetime_count += 1
            c_date = challan.get('date')
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
            except: pass

    # 3. Closing & PO - LIFETIME COUNT & Analytics
    closing_lifetime_count = 0
    po_lifetime_count = 0
    closing_list = []
    po_list = []
    
    history = stats_data.get('downloads', [])
    for item in history:
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
        except: pass

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
        buyer_match = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(? :\n|$)", first_page_text)
        if buyer_match: meta['buyer'] = buyer_match.group(1).strip()

    booking_block_match = re.search(r"(? :Internal )?Booking NO\. ? [:\s]*([\s\S]*?)(? :System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
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
                    
                    if sub_lower == "gmts.color /country qty": gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    
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
            <a href="/store" class="nav-link">
                <i class="fas fa-store"></i> Store Panel
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
                    <span>System Online</span>
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
                        <input type="text" name="ref_no" placeholder="e.g. IB-12345 or Booking-123" required>
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
                                <label class="perm-checkbox">
                                    <input type="checkbox" id="perm_store">
                                    <span>Store</span>
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
            if (document.getElementById('perm_store').checked) perms.push('store');
            
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
            document.getElementById('perm_store').checked = pArr.includes('store');
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
        <div class="loading-text">Processing...</div>
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
            
            {% if 'store' in session.permissions %}
            <div class="card" style="animation: fadeInUp 0.5s ease-out 0.4s backwards;">
                <div class="section-header">
                    <span><i class="fas fa-store" style="margin-right: 10px; color: var(--accent-cyan);"></i>Store Panel</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                    Manage store inventory, invoices, customers and payments.
                </p>
                <a href="/store">
                    <button style="background: linear-gradient(135deg, #06B6D4 0%, #22D3EE 100%);">
                        <i class="fas fa-external-link-alt" style="margin-right: 8px;"></i> Open Store
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
        
        if (! sessionStorage.getItem('welcomeShown')) {
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
            <a href="/admin/accessories/print? ref={{ ref }}" target="_blank">
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
                            <input type="text" name="line_no" required placeholder="e.g.L-01">
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
                                <a href="/admin/accessories/edit? ref={{ ref }}&index={{ (challans|length) - loop.index }}" class="action-btn btn-edit">
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
# STORE DASHBOARD TEMPLATE - FULL FEATURED (ALUMINUM SHOP)
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MNM Software</title>
""" + COMMON_STYLES + """
    <style>
        .store-stat-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            transition: var(--transition-smooth);
        }
        
        .store-stat-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-glow);
        }
        
        .store-stat-icon {
            width: 50px;
            height: 50px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-bottom: 15px;
        }
        
        .store-stat-value {
            font-size: 28px;
            font-weight: 800;
            color: white;
            margin-bottom: 5px;
        }
        
        .store-stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .quick-action-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .quick-action-btn {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: var(--transition-smooth);
            text-decoration: none;
            display: block;
        }
        
        .quick-action-btn:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
            transform: translateY(-3px);
        }
        
        .quick-action-btn i {
            font-size: 24px;
            color: var(--accent-orange);
            margin-bottom: 10px;
            display: block;
        }
        
        .quick-action-btn span {
            font-size: 13px;
            font-weight: 600;
            color: white;
        }
        
        .due-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .due-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 10px;
            transition: var(--transition-smooth);
        }
        
        .due-item:hover {
            background: rgba(255, 122, 0, 0.05);
        }
        
        .due-customer {
            font-weight: 600;
            color: white;
            font-size: 14px;
        }
        
        .due-amount {
            font-size: 16px;
            font-weight: 800;
            color: var(--accent-red);
        }
        
        .recent-invoice {
            display: grid;
            grid-template-columns: auto 1fr auto auto;
            gap: 15px;
            align-items: center;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 8px;
        }
        
        .invoice-number {
            background: var(--gradient-orange);
            color: white;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
        }
        
        .invoice-customer {
            font-weight: 500;
            color: white;
            font-size: 14px;
        }
        
        .invoice-amount {
            font-weight: 700;
            color: var(--accent-green);
        }
        
        .invoice-date {
            font-size: 12px;
            color: var(--text-secondary);
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link active">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-alt"></i> Quotations
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
        <div class="header-section">
            <div>
                <div class="page-title">Store Dashboard</div>
                <div class="page-subtitle">Aluminum Shop Management System</div>
            </div>
            <div class="status-badge">
                <div class="realtime-dot"></div>
                <span>{{ today }}</span>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Quick Actions -->
        <div class="quick-action-grid">
            <a href="/store/invoices/new" class="quick-action-btn">
                <i class="fas fa-plus-circle"></i>
                <span>New Invoice</span>
            </a>
            <a href="/store/customers/add" class="quick-action-btn">
                <i class="fas fa-user-plus"></i>
                <span>Add Customer</span>
            </a>
            <a href="/store/products/add" class="quick-action-btn">
                <i class="fas fa-box"></i>
                <span>Add Product</span>
            </a>
            <a href="/store/quotations/new" class="quick-action-btn">
                <i class="fas fa-file-alt"></i>
                <span>New Quotation</span>
            </a>
            <a href="/store/dues" class="quick-action-btn">
                <i class="fas fa-hand-holding-usd"></i>
                <span>Collect Due</span>
            </a>
            <a href="/store/reports" class="quick-action-btn">
                <i class="fas fa-chart-line"></i>
                <span>Reports</span>
            </a>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(255, 122, 0, 0.2), rgba(255, 122, 0, 0.05)); color: var(--accent-orange);">
                    <i class="fas fa-shopping-cart"></i>
                </div>
                <div class="store-stat-value">৳{{ "{:,.0f}".format(stats.today_sales) }}</div>
                <div class="store-stat-label">Today's Sales</div>
            </div>
            
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05)); color: var(--accent-green);">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="store-stat-value">৳{{ "{:,.0f}".format(stats.total_sales) }}</div>
                <div class="store-stat-label">Total Sales</div>
            </div>
            
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.05)); color: var(--accent-red);">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="store-stat-value">৳{{ "{:,.0f}".format(stats.total_due) }}</div>
                <div class="store-stat-label">Total Due</div>
            </div>
            
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.05)); color: var(--accent-blue);">
                    <i class="fas fa-users"></i>
                </div>
                <div class="store-stat-value">{{ stats.total_customers }}</div>
                <div class="store-stat-label">Customers</div>
            </div>
            
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05)); color: var(--accent-purple);">
                    <i class="fas fa-file-invoice"></i>
                </div>
                <div class="store-stat-value">{{ stats.today_invoices }}</div>
                <div class="store-stat-label">Today's Invoices</div>
            </div>
            
            <div class="store-stat-card">
                <div class="store-stat-icon" style="background: linear-gradient(145deg, rgba(6, 182, 212, 0.2), rgba(6, 182, 212, 0.05)); color: var(--accent-cyan);">
                    <i class="fas fa-boxes"></i>
                </div>
                <div class="store-stat-value">{{ stats.total_products }}</div>
                <div class="store-stat-label">Products</div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- Recent Invoices -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-file-invoice-dollar" style="margin-right: 10px; color: var(--accent-orange);"></i>Recent Invoices</span>
                    <a href="/store/invoices" style="color: var(--accent-orange); text-decoration: none; font-size: 13px;">View All →</a>
                </div>
                <div style="max-height: 350px; overflow-y: auto;">
                    {% if stats.recent_invoices %}
                        {% for inv in stats.recent_invoices %}
                        <div class="recent-invoice">
                            <span class="invoice-number">{{ inv.invoice_number }}</span>
                            <span class="invoice-customer">{{ inv.customer_name }}</span>
                            <span class="invoice-amount">৳{{ "{:,.0f}".format(inv.grand_total) }}</span>
                            <span class="invoice-date">{{ inv.date }}</span>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state" style="padding: 40px;">
                            <i class="fas fa-file-invoice" style="font-size: 40px; opacity: 0.2; margin-bottom: 15px;"></i>
                            <div style="color: var(--text-secondary);">No invoices yet</div>
                        </div>
                    {% endif %}
                </div>
            </div>

            <!-- Due Customers -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-exclamation-circle" style="margin-right: 10px; color: var(--accent-red);"></i>Due Customers</span>
                    <a href="/store/dues" style="color: var(--accent-orange); text-decoration: none; font-size: 13px;">Collect →</a>
                </div>
                <div class="due-list">
                    {% if stats.due_customers %}
                        {% for cust in stats.due_customers %}
                        <div class="due-item">
                            <div>
                                <div class="due-customer">{{ cust.customer_name }}</div>
                                <div style="font-size: 11px; color: var(--text-secondary);">{{ cust.invoice_count }} invoice(s)</div>
                            </div>
                            <div class="due-amount">৳{{ "{:,.0f}".format(cust.total_due) }}</div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="empty-state" style="padding: 40px;">
                            <i class="fas fa-check-circle" style="font-size: 40px; opacity: 0.2; color: var(--accent-green); margin-bottom: 15px;"></i>
                            <div style="color: var(--text-secondary);">No pending dues</div>
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE CUSTOMER TEMPLATES
# ==============================================================================

STORE_CUSTOMERS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - Store Panel</title>
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
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-alt"></i> Quotations
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
                <div class="page-title">Customer Management</div>
                <div class="page-subtitle">Manage your customers and their accounts</div>
            </div>
            <a href="/store/customers/add">
                <button style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-user-plus" style="margin-right: 8px;"></i> Add Customer
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Search Box -->
        <div class="card" style="margin-bottom: 25px; padding: 20px;">
            <div class="search-box" style="margin-bottom: 0;">
                <i class="fas fa-search"></i>
                <input type="text" id="searchCustomer" placeholder="Search by name, phone or address..." onkeyup="filterCustomers()">
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <span>All Customers</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{ customers|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table" id="customerTable">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Total Purchase</th>
                            <th>Total Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for cust in customers %}
                        <tr>
                            <td style="font-weight: 600;">{{ cust.name }}</td>
                            <td>{{ cust.phone }}</td>
                            <td style="color: var(--text-secondary); max-width: 200px; overflow: hidden; text-overflow: ellipsis;">{{ cust.address or '-' }}</td>
                            <td class="amount-positive">৳{{ "{:,.0f}".format(cust.total_purchase or 0) }}</td>
                            <td>
                                {% if cust.total_due and cust.total_due > 0 %}
                                <span class="due-badge">৳{{ "{:,.0f}".format(cust.total_due) }}</span>
                                {% else %}
                                <span class="paid-badge">Cleared</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/customers/view/{{ cust._id }}" class="action-btn btn-view" title="View Details">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/store/customers/edit/{{ cust._id }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <button class="action-btn btn-del" onclick="deleteCustomer('{{ cust._id }}')" title="Delete">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                <i class="fas fa-users" style="font-size: 40px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                No customers found. Add your first customer! 
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
            const input = document.getElementById('searchCustomer').value.toLowerCase();
            const rows = document.querySelectorAll('#customerTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            });
        }
        
        function deleteCustomer(id) {
            if (confirm('Are you sure you want to delete this customer?  This action cannot be undone.')) {
                fetch('/store/customers/delete/' + id, {
                    method: 'POST'
                }).then(() => location.reload());
            }
        }
    </script>
</body>
</html>
"""

STORE_CUSTOMER_ADD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Add Customer - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Add New Customer</div>
                <div class="page-subtitle">Enter customer details below</div>
            </div>
        </div>

        <div class="card" style="max-width: 600px;">
            <div class="section-header">
                <span><i class="fas fa-user-plus" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span>
            </div>
            
            <form action="/store/customers/add" method="post">
                <div class="input-group">
                    <label><i class="fas fa-user" style="margin-right: 5px;"></i> CUSTOMER NAME *</label>
                    <input type="text" name="name" required placeholder="Enter full name">
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-phone" style="margin-right: 5px;"></i> PHONE NUMBER *</label>
                        <input type="tel" name="phone" required placeholder="01XXXXXXXXX">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-envelope" style="margin-right: 5px;"></i> EMAIL (Optional)</label>
                        <input type="email" name="email" placeholder="email@example.com">
                    </div>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> ADDRESS</label>
                    <textarea name="address" placeholder="Enter full address" rows="3"></textarea>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sticky-note" style="margin-right: 5px;"></i> NOTES (Optional)</label>
                    <textarea name="notes" placeholder="Any additional notes about this customer" rows="2"></textarea>
                </div>
                
                <div style="display: flex; gap: 15px; margin-top: 10px;">
                    <button type="submit">
                        <i class="fas fa-save" style="margin-right: 8px;"></i> Save Customer
                    </button>
                    <a href="/store/customers" style="flex: 1;">
                        <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                            <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                        </button>
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

STORE_CUSTOMER_EDIT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Customer - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Edit Customer</div>
                <div class="page-subtitle">Update customer information</div>
            </div>
        </div>

        <div class="card" style="max-width: 600px;">
            <div class="section-header">
                <span><i class="fas fa-user-edit" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Information</span>
            </div>
            
            <form action="/store/customers/edit/{{ customer._id }}" method="post">
                <div class="input-group">
                    <label><i class="fas fa-user" style="margin-right: 5px;"></i> CUSTOMER NAME *</label>
                    <input type="text" name="name" required value="{{ customer.name }}">
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-phone" style="margin-right: 5px;"></i> PHONE NUMBER *</label>
                        <input type="tel" name="phone" required value="{{ customer.phone }}">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-envelope" style="margin-right: 5px;"></i> EMAIL</label>
                        <input type="email" name="email" value="{{ customer.email or '' }}">
                    </div>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> ADDRESS</label>
                    <textarea name="address" rows="3">{{ customer.address or '' }}</textarea>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sticky-note" style="margin-right: 5px;"></i> NOTES</label>
                    <textarea name="notes" rows="2">{{ customer.notes or '' }}</textarea>
                </div>
                
                <div style="display: flex; gap: 15px; margin-top: 10px;">
                    <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-sync-alt" style="margin-right: 8px;"></i> Update Customer
                    </button>
                    <a href="/store/customers" style="flex: 1;">
                        <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                            <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                        </button>
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

STORE_CUSTOMER_VIEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customer Details - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{ data.customer.name }}</div>
                <div class="page-subtitle">Customer Profile & Transaction History</div>
            </div>
            <div style="display: flex; gap: 10px;">
                <a href="/store/invoices/new? customer={{ data.customer._id }}">
                    <button style="width: auto; padding: 12px 20px;">
                        <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
                    </button>
                </a>
                <a href="/store/customers/edit/{{ data.customer._id }}">
                    <button style="width: auto; padding: 12px 20px; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-edit" style="margin-right: 8px;"></i> Edit
                    </button>
                </a>
            </div>
        </div>

        <!-- Customer Stats -->
        <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 30px;">
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-shopping-bag" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{ "{:,.0f}".format(data.total_purchase) }}</h3>
                    <p>Total Purchase</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));">
                    <i class="fas fa-check-circle" style="color: var(--accent-blue);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{ "{:,.0f}".format(data.total_paid) }}</h3>
                    <p>Total Paid</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));">
                    <i class="fas fa-exclamation-circle" style="color: var(--accent-red);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{ "{:,.0f}".format(data.total_due) }}</h3>
                    <p>Total Due</p>
                </div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- Customer Info -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span>
                </div>
                <div style="display: grid; gap: 15px;">
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Phone</span>
                        <span style="font-weight: 600;">{{ data.customer.phone }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Email</span>
                        <span style="font-weight: 600;">{{ data.customer.email or '-' }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Address</span>
                        <span style="font-weight: 600; text-align: right; max-width: 200px;">{{ data.customer.address or '-' }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Total Invoices</span>
                        <span style="font-weight: 600;">{{ data.invoices|length }}</span>
                    </div>
                </div>
                
                {% if data.total_due > 0 %}
                <a href="/store/dues/collect/{{ data.customer._id }}">
                    <button style="margin-top: 20px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-hand-holding-usd" style="margin-right: 8px;"></i> Collect Due Payment
                    </button>
                </a>
                {% endif %}
            </div>

            <!-- Recent Payments -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-history" style="margin-right: 10px; color: var(--accent-green);"></i>Recent Payments</span>
                </div>
                <div style="max-height: 300px; overflow-y: auto;">
                    {% if data.payments %}
                        {% for pay in data.payments[:10] %}
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px; margin-bottom: 8px;">
                            <div>
                                <div style="font-weight: 600; color: var(--accent-green);">৳{{ "{:,.0f}".format(pay.amount) }}</div>
                                <div style="font-size: 11px; color: var(--text-secondary);">{{ pay.date }}</div>
                            </div>
                            <div style="font-size: 12px; color: var(--text-secondary);">{{ pay.method or 'Cash' }}</div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="text-align: center; padding: 30px; color: var(--text-secondary);">
                            No payment records found
                        </div>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- Invoice History -->
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-file-invoice-dollar" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice History</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in data.invoices %}
                        <tr>
                            <td><span class="invoice-number">{{ inv.invoice_number }}</span></td>
                            <td>{{ inv.date }}</td>
                            <td style="font-weight: 600;">৳{{ "{:,.0f}".format(inv.grand_total) }}</td>
                            <td class="amount-positive">৳{{ "{:,.0f}".format(inv.paid_amount) }}</td>
                            <td>
                                {% if inv.due_amount > 0 %}
                                <span class="due-badge">৳{{ "{:,.0f}".format(inv.due_amount) }}</span>
                                {% else %}
                                <span class="paid-badge">Paid</span>
                                {% endif %}
                            </td>
                            <td>
                                {% if inv.due_amount == 0 %}
                                <span class="paid-badge">Completed</span>
                                {% elif inv.paid_amount > 0 %}
                                <span class="partial-badge">Partial</span>
                                {% else %}
                                <span class="due-badge">Unpaid</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/invoices/view/{{ inv._id }}" class="action-btn btn-view">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/store/invoices/print/{{ inv._id }}" class="action-btn btn-edit" target="_blank">
                                        <i class="fas fa-print"></i>
                                    </a>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                No invoices found for this customer
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
# STORE PRODUCT TEMPLATES
# ==============================================================================

STORE_PRODUCTS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - Store Panel</title>
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
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-alt"></i> Quotations
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
                <div class="page-subtitle">Manage your product inventory</div>
            </div>
            <a href="/store/products/add">
                <button style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Product
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Search & Filter -->
        <div class="card" style="margin-bottom: 25px; padding: 20px;">
            <div style="display: flex; gap: 15px; flex-wrap: wrap;">
                <div class="search-box" style="flex: 1; min-width: 250px; margin-bottom: 0;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchProduct" placeholder="Search products..." onkeyup="filterProducts()">
                </div>
                <select id="categoryFilter" onchange="filterProducts()" style="width: auto; min-width: 150px;">
                    <option value="">All Categories</option>
                    {% for cat in categories %}
                    <option value="{{ cat }}">{{ cat }}</option>
                    {% endfor %}
                </select>
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <span>All Products</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{ products|length }} Items</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table" id="productTable">
                    <thead>
                        <tr>
                            <th>Product Name</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th>Price</th>
                            <th>Stock</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for prod in products %}
                        <tr data-category="{{ prod.category or '' }}">
                            <td style="font-weight: 600;">{{ prod.name }}</td>
                            <td><span class="table-badge">{{ prod.category or 'General' }}</span></td>
                            <td>{{ prod.unit or 'Pcs' }}</td>
                            <td class="amount-positive">৳{{ "{:,.2f}".format(prod.price or 0) }}</td>
                            <td>
                                {% if prod.stock is defined %}
                                    {% if prod.stock <= 0 %}
                                    <span class="due-badge">Out of Stock</span>
                                    {% elif prod.stock < 10 %}
                                    <span class="partial-badge">{{ prod.stock }}</span>
                                    {% else %}
                                    <span class="paid-badge">{{ prod.stock }}</span>
                                    {% endif %}
                                {% else %}
                                <span style="color: var(--text-secondary);">N/A</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/products/edit/{{ prod._id }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <button class="action-btn btn-del" onclick="deleteProduct('{{ prod._id }}')" title="Delete">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                <i class="fas fa-box-open" style="font-size: 40px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                No products found. Add your first product! 
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
            const search = document.getElementById('searchProduct').value.toLowerCase();
            const category = document.getElementById('categoryFilter').value;
            const rows = document.querySelectorAll('#productTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                const rowCategory = row.getAttribute('data-category') || '';
                const matchSearch = text.includes(search);
                const matchCategory = ! category || rowCategory === category;
                row.style.display = (matchSearch && matchCategory) ? '' : 'none';
            });
        }
        
        function deleteProduct(id) {
            if (confirm('Are you sure you want to delete this product?')) {
                fetch('/store/products/delete/' + id, {
                    method: 'POST'
                }).then(() => location.reload());
            }
        }
    </script>
</body>
</html>
"""

STORE_PRODUCT_ADD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Add Product - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Add New Product</div>
                <div class="page-subtitle">Enter product details below</div>
            </div>
        </div>

        <div class="card" style="max-width: 700px;">
            <div class="section-header">
                <span><i class="fas fa-box" style="margin-right: 10px; color: var(--accent-orange);"></i>Product Information</span>
            </div>
            
            <form action="/store/products/add" method="post">
                <div class="input-group">
                    <label><i class="fas fa-tag" style="margin-right: 5px;"></i> PRODUCT NAME *</label>
                    <input type="text" name="name" required placeholder="Enter product name">
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-folder" style="margin-right: 5px;"></i> CATEGORY</label>
                        <input type="text" name="category" placeholder="e.g. Aluminum Profile" list="categories">
                        <datalist id="categories">
                            <option value="Aluminum Profile">
                            <option value="Aluminum Sheet">
                            <option value="Glass">
                            <option value="Accessories">
                            <option value="Hardware">
                            <option value="Other">
                        </datalist>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> UNIT</label>
                        <select name="unit">
                            <option value="Pcs">Pcs (Piece)</option>
                            <option value="Ft">Ft (Feet)</option>
                            <option value="Meter">Meter</option>
                            <option value="Kg">Kg (Kilogram)</option>
                            <option value="Set">Set</option>
                            <option value="Sqft">Sqft (Square Feet)</option>
                        </select>
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-money-bill-wave" style="margin-right: 5px;"></i> SELLING PRICE (৳) *</label>
                        <input type="number" name="price" required step="0.01" min="0" placeholder="0.00">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-coins" style="margin-right: 5px;"></i> COST PRICE (৳)</label>
                        <input type="number" name="cost_price" step="0.01" min="0" placeholder="0.00">
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-warehouse" style="margin-right: 5px;"></i> STOCK QUANTITY</label>
                        <input type="number" name="stock" min="0" placeholder="0">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-exclamation-triangle" style="margin-right: 5px;"></i> LOW STOCK ALERT</label>
                        <input type="number" name="low_stock_alert" min="0" placeholder="10">
                    </div>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-align-left" style="margin-right: 5px;"></i> DESCRIPTION</label>
                    <textarea name="description" placeholder="Product description (optional)" rows="3"></textarea>
                </div>
                
                <div style="display: flex; gap: 15px; margin-top: 10px;">
                    <button type="submit">
                        <i class="fas fa-save" style="margin-right: 8px;"></i> Save Product
                    </button>
                    <a href="/store/products" style="flex: 1;">
                        <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                            <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                        </button>
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

STORE_PRODUCT_EDIT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Product - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Edit Product</div>
                <div class="page-subtitle">Update product information</div>
            </div>
        </div>

        <div class="card" style="max-width: 700px;">
            <div class="section-header">
                <span><i class="fas fa-edit" style="margin-right: 10px; color: var(--accent-purple);"></i>Product Information</span>
            </div>
            
            <form action="/store/products/edit/{{ product._id }}" method="post">
                <div class="input-group">
                    <label><i class="fas fa-tag" style="margin-right: 5px;"></i> PRODUCT NAME *</label>
                    <input type="text" name="name" required value="{{ product.name }}">
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-folder" style="margin-right: 5px;"></i> CATEGORY</label>
                        <input type="text" name="category" value="{{ product.category or '' }}" list="categories">
                        <datalist id="categories">
                            <option value="Aluminum Profile">
                            <option value="Aluminum Sheet">
                            <option value="Glass">
                            <option value="Accessories">
                            <option value="Hardware">
                            <option value="Other">
                        </datalist>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> UNIT</label>
                        <select name="unit">
                            <option value="Pcs" {{ 'selected' if product.unit == 'Pcs' else '' }}>Pcs (Piece)</option>
                            <option value="Ft" {{ 'selected' if product.unit == 'Ft' else '' }}>Ft (Feet)</option>
                            <option value="Meter" {{ 'selected' if product.unit == 'Meter' else '' }}>Meter</option>
                            <option value="Kg" {{ 'selected' if product.unit == 'Kg' else '' }}>Kg (Kilogram)</option>
                            <option value="Set" {{ 'selected' if product.unit == 'Set' else '' }}>Set</option>
                            <option value="Sqft" {{ 'selected' if product.unit == 'Sqft' else '' }}>Sqft (Square Feet)</option>
                        </select>
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-money-bill-wave" style="margin-right: 5px;"></i> SELLING PRICE (৳) *</label>
                        <input type="number" name="price" required step="0.01" min="0" value="{{ product.price or 0 }}">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-coins" style="margin-right: 5px;"></i> COST PRICE (৳)</label>
                        <input type="number" name="cost_price" step="0.01" min="0" value="{{ product.cost_price or 0 }}">
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="input-group">
                        <label><i class="fas fa-warehouse" style="margin-right: 5px;"></i> STOCK QUANTITY</label>
                        <input type="number" name="stock" min="0" value="{{ product.stock or 0 }}">
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-exclamation-triangle" style="margin-right: 5px;"></i> LOW STOCK ALERT</label>
                        <input type="number" name="low_stock_alert" min="0" value="{{ product.low_stock_alert or 10 }}">
                    </div>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-align-left" style="margin-right: 5px;"></i> DESCRIPTION</label>
                    <textarea name="description" rows="3">{{ product.description or '' }}</textarea>
                </div>
                
                <div style="display: flex; gap: 15px; margin-top: 10px;">
                    <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-sync-alt" style="margin-right: 8px;"></i> Update Product
                    </button>
                    <a href="/store/products" style="flex: 1;">
                        <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                            <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                        </button>
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE INVOICE TEMPLATES
# ==============================================================================

STORE_INVOICES_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - Store Panel</title>
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
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-alt"></i> Quotations
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
                <div class="page-subtitle">Manage all your sales invoices</div>
            </div>
            <a href="/store/invoices/new">
                <button style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> New Invoice
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Filter Tabs -->
        <div class="filter-tabs">
            <div class="filter-tab active" onclick="filterInvoices('all', this)">All</div>
            <div class="filter-tab" onclick="filterInvoices('paid', this)">Paid</div>
            <div class="filter-tab" onclick="filterInvoices('partial', this)">Partial</div>
            <div class="filter-tab" onclick="filterInvoices('unpaid', this)">Unpaid</div>
        </div>

        <!-- Search -->
        <div class="card" style="margin-bottom: 25px; padding: 20px;">
            <div class="search-box" style="margin-bottom: 0;">
                <i class="fas fa-search"></i>
                <input type="text" id="searchInvoice" placeholder="Search by invoice number or customer..." onkeyup="searchInvoices()">
            </div>
        </div>

        <div class="card">
            <div class="section-header">
                <span>All Invoices</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{ invoices|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table" id="invoiceTable">
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in invoices %}
                        <tr data-status="{% if inv.due_amount == 0 %}paid{% elif inv.paid_amount > 0 %}partial{% else %}unpaid{% endif %}">
                            <td><span class="invoice-number">{{ inv.invoice_number }}</span></td>
                            <td>{{ inv.date }}</td>
                            <td style="font-weight: 600;">{{ inv.customer_name }}</td>
                            <td style="font-weight: 700;">৳{{ "{:,.0f}".format(inv.grand_total) }}</td>
                            <td class="amount-positive">৳{{ "{:,.0f}".format(inv.paid_amount) }}</td>
                            <td>
                                {% if inv.due_amount > 0 %}
                                <span class="due-badge">৳{{ "{:,.0f}".format(inv.due_amount) }}</span>
                                {% else %}
                                <span style="color: var(--text-secondary);">-</span>
                                {% endif %}
                            </td>
                            <td>
                                {% if inv.due_amount == 0 %}
                                <span class="paid-badge">Paid</span>
                                {% elif inv.paid_amount > 0 %}
                                <span class="partial-badge">Partial</span>
                                {% else %}
                                <span class="due-badge">Unpaid</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/invoices/view/{{ inv._id }}" class="action-btn btn-view" title="View">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/store/invoices/print/{{ inv._id }}" class="action-btn btn-edit" title="Print" target="_blank">
                                        <i class="fas fa-print"></i>
                                    </a>
                                    {% if inv.due_amount > 0 %}
                                    <a href="/store/invoices/pay/{{ inv._id }}" class="action-btn btn-pay" title="Collect Payment">
                                        <i class="fas fa-hand-holding-usd"></i>
                                    </a>
                                    {% endif %}
                                    <a href="/store/invoices/edit/{{ inv._id }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="8" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                <i class="fas fa-file-invoice" style="font-size: 40px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                No invoices found.Create your first invoice! 
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterInvoices(status, element) {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            element.classList.add('active');
            
            const rows = document.querySelectorAll('#invoiceTable tbody tr');
            rows.forEach(row => {
                const rowStatus = row.getAttribute('data-status');
                if (status === 'all' || rowStatus === status) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        function searchInvoices() {
            const search = document.getElementById('searchInvoice').value.toLowerCase();
            const rows = document.querySelectorAll('#invoiceTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(search) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

STORE_INVOICE_NEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Invoice - Store Panel</title>
""" + COMMON_STYLES + """
    <style>
        .invoice-item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto;
            gap: 10px;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .invoice-item-row input, .invoice-item-row select {
            padding: 10px 12px;
            font-size: 14px;
        }
        
        .remove-item {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .remove-item:hover {
            background: var(--accent-red);
            color: white;
        }
        
        .totals-section {
            background: rgba(255, 122, 0, 0.05);
            border: 1px solid rgba(255, 122, 0, 0.2);
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
            color: var(--accent-orange);
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

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create New Invoice</div>
                <div class="page-subtitle">Invoice #: {{ invoice_number }}</div>
            </div>
        </div>

        <form action="/store/invoices/new" method="post" id="invoiceForm">
            <input type="hidden" name="invoice_number" value="{{ invoice_number }}">
            
            <div class="dashboard-grid-2">
                <!-- Customer & Date Info -->
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span>
                    </div>
                    
                    <div class="input-group">
                        <label>SELECT CUSTOMER *</label>
                        <select name="customer_id" id="customerSelect" required onchange="updateCustomerInfo()">
                            <option value="">-- Select Customer --</option>
                            {% for cust in customers %}
                            <option value="{{ cust._id }}" data-name="{{ cust.name }}" data-phone="{{ cust.phone }}" data-address="{{ cust.address or '' }}"
                                {{ 'selected' if selected_customer and str(cust._id) == selected_customer else '' }}>
                                {{ cust.name }} - {{ cust.phone }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div id="customerInfo" style="display: none; background: rgba(255,255,255,0.02); padding: 15px; border-radius: 10px; margin-top: 10px;">
                        <div style="font-weight: 600; margin-bottom: 5px;" id="custName"></div>
                        <div style="font-size: 13px; color: var(--text-secondary);" id="custPhone"></div>
                        <div style="font-size: 13px; color: var(--text-secondary);" id="custAddress"></div>
                    </div>
                    
                    <div style="margin-top: 15px; text-align: center;">
                        <a href="/store/customers/add" style="color: var(--accent-orange); font-size: 13px;">
                            <i class="fas fa-plus-circle"></i> Add New Customer
                        </a>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calendar" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Details</span>
                    </div>
                    
                    <div class="input-group">
                        <label>INVOICE DATE *</label>
                        <input type="date" name="date" value="{{ today }}" required>
                    </div>
                    
                    <div class="input-group">
                        <label>NOTES / REMARKS</label>
                        <textarea name="notes" rows="3" placeholder="Any additional notes..."></textarea>
                    </div>
                </div>
            </div>

            <!-- Invoice Items -->
            <div class="card" style="margin-top: 25px;">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-green);"></i>Invoice Items</span>
                    <button type="button" onclick="addItem()" style="width: auto; padding: 8px 20px; font-size: 13px;">
                        <i class="fas fa-plus" style="margin-right: 5px;"></i> Add Item
                    </button>
                </div>
                
                <!-- Header -->
                <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto; gap: 10px; padding: 10px 15px; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
                    <div>Product / Description</div>
                    <div>Rate (৳)</div>
                    <div>Quantity</div>
                    <div>Unit</div>
                    <div>Amount (৳)</div>
                    <div></div>
                </div>
                
                <div id="itemsContainer">
                    <!-- Items will be added here -->
                </div>
                
                <!-- Totals -->
                <div class="totals-section">
                    <div class="total-row">
                        <span class="total-label">Subtotal</span>
                        <span class="total-value" id="subtotal">৳0</span>
                    </div>
                    <div class="total-row">
                        <span class="total-label">
                            Discount 
                            <input type="number" name="discount" id="discountInput" value="0" min="0" step="0.01" 
                                style="width: 100px; padding: 5px 10px; margin-left: 10px;" onchange="calculateTotals()">
                        </span>
                        <span class="total-value" id="discountAmount">৳0</span>
                    </div>
                    <div class="total-row">
                        <span class="total-label">Grand Total</span>
                        <span class="total-value" id="grandTotal">৳0</span>
                    </div>
                    <div class="total-row" style="border-top: 1px solid var(--border-color); margin-top: 10px; padding-top: 15px;">
                        <span class="total-label">
                            Paid Amount (৳)
                            <input type="number" name="paid_amount" id="paidInput" value="0" min="0" step="0.01"
                                style="width: 150px; padding: 8px 12px; margin-left: 10px;" onchange="calculateTotals()">
                        </span>
                        <span class="total-value" style="color: var(--accent-green);" id="paidAmount">৳0</span>
                    </div>
                    <div class="total-row">
                        <span class="total-label">Due Amount</span>
                        <span class="total-value" style="color: var(--accent-red);" id="dueAmount">৳0</span>
                    </div>
                </div>
                
                <input type="hidden" name="items_json" id="itemsJson">
                <input type="hidden" name="subtotal" id="subtotalInput">
                <input type="hidden" name="grand_total" id="grandTotalInput">
                <input type="hidden" name="due_amount" id="dueAmountInput">
            </div>

            <div style="display: flex; gap: 15px; margin-top: 25px;">
                <button type="submit" onclick="return prepareSubmit()">
                    <i class="fas fa-save" style="margin-right: 8px;"></i> Save Invoice
                </button>
                <a href="/store/invoices" style="flex: 1;">
                    <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                        <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                    </button>
                </a>
            </div>
        </form>
    </div>

    <script>
        // Products data
        const products = {{ products_json | safe }};
        let itemCount = 0;
        
        function updateCustomerInfo() {
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            const infoDiv = document.getElementById('customerInfo');
            
            if (select.value) {
                document.getElementById('custName').textContent = option.getAttribute('data-name');
                document.getElementById('custPhone').textContent = option.getAttribute('data-phone');
                document.getElementById('custAddress').textContent = option.getAttribute('data-address') || '';
                infoDiv.style.display = 'block';
            } else {
                infoDiv.style.display = 'none';
            }
        }
        
        function addItem() {
            itemCount++;
            const container = document.getElementById('itemsContainer');
            
            let productOptions = '<option value="">-- Select or Type --</option>';
            products.forEach(p => {
                productOptions += `<option value="${p._id}" data-price="${p.price}" data-unit="${p.unit}">${p.name}</option>`;
            });
            
            const html = `
                <div class="invoice-item-row" id="item-${itemCount}">
                    <div>
                        <select onchange="updateItemPrice(this, ${itemCount})" id="product-${itemCount}">
                            ${productOptions}
                        </select>
                        <input type="text" id="desc-${itemCount}" placeholder="Or type description..." style="margin-top: 8px;">
                    </div>
                    <input type="number" id="rate-${itemCount}" placeholder="0.00" step="0.01" min="0" onchange="calculateRowTotal(${itemCount})">
                    <input type="number" id="qty-${itemCount}" placeholder="1" value="1" min="0.01" step="0.01" onchange="calculateRowTotal(${itemCount})">
                    <select id="unit-${itemCount}">
                        <option value="Pcs">Pcs</option>
                        <option value="Ft">Ft</option>
                        <option value="Meter">Meter</option>
                        <option value="Kg">Kg</option>
                        <option value="Set">Set</option>
                        <option value="Sqft">Sqft</option>
                    </select>
                    <input type="text" id="amount-${itemCount}" value="0.00" readonly style="background: rgba(255,255,255,0.05); font-weight: 700;">
                    <button type="button" class="remove-item" onclick="removeItem(${itemCount})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            container.insertAdjacentHTML('beforeend', html);
        }
        
        function updateItemPrice(select, id) {
            const option = select.options[select.selectedIndex];
            if (option.value) {
                document.getElementById('rate-' + id).value = option.getAttribute('data-price') || 0;
                document.getElementById('unit-' + id).value = option.getAttribute('data-unit') || 'Pcs';
                calculateRowTotal(id);
            }
        }
        
        function calculateRowTotal(id) {
            const rate = parseFloat(document.getElementById('rate-' + id).value) || 0;
            const qty = parseFloat(document.getElementById('qty-' + id).value) || 0;
            const amount = rate * qty;
            document.getElementById('amount-' + id).value = amount.toFixed(2);
            calculateTotals();
        }
        
        function removeItem(id) {
            document.getElementById('item-' + id).remove();
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('[id^="amount-"]').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            const paid = parseFloat(document.getElementById('paidInput').value) || 0;
            const due = grandTotal - paid;
            
            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document.getElementById('discountAmount').textContent = '৳' + discount.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳' + grandTotal.toFixed(2);
            document.getElementById('paidAmount').textContent = '৳' + paid.toFixed(2);
            document.getElementById('dueAmount').textContent = '৳' + due.toFixed(2);
            
            document.getElementById('subtotalInput').value = subtotal;
            document.getElementById('grandTotalInput').value = grandTotal;
            document.getElementById('dueAmountInput').value = due;
        }
        
        function prepareSubmit() {
            const items = [];
            document.querySelectorAll('.invoice-item-row').forEach(row => {
                const id = row.id.split('-')[1];
                const productSelect = document.getElementById('product-' + id);
                const desc = document.getElementById('desc-' + id).value;
                const productName = productSelect.options[productSelect.selectedIndex].text;
                
                items.push({
                    product_id: productSelect.value,
                    description: desc || (productSelect.value ?  productName : ''),
                    rate: parseFloat(document.getElementById('rate-' + id).value) || 0,
                    quantity: parseFloat(document.getElementById('qty-' + id).value) || 0,
                    unit: document.getElementById('unit-' + id).value,
                    amount: parseFloat(document.getElementById('amount-' + id).value) || 0
                });
            });
            
            if (items.length === 0) {
                alert('Please add at least one item');
                return false;
            }
            
            document.getElementById('itemsJson').value = JSON.stringify(items);
            return true;
        }
        
        // Initialize with one item
        addItem();
        
        // Check if customer pre-selected
        if (document.getElementById('customerSelect').value) {
            updateCustomerInfo();
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICE VIEW & PRINT TEMPLATES
# ==============================================================================

STORE_INVOICE_VIEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoice Details - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoice #{{ invoice.invoice_number }}</div>
                <div class="page-subtitle">Created on {{ invoice.date }}</div>
            </div>
            <div style="display: flex; gap: 10px;">
                <a href="/store/invoices/print/{{ invoice._id }}" target="_blank">
                    <button style="width: auto; padding: 12px 20px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-print" style="margin-right: 8px;"></i> Print
                    </button>
                </a>
                {% if invoice.due_amount > 0 %}
                <a href="/store/invoices/pay/{{ invoice._id }}">
                    <button style="width: auto; padding: 12px 20px; background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);">
                        <i class="fas fa-hand-holding-usd" style="margin-right: 8px;"></i> Collect Payment
                    </button>
                </a>
                {% endif %}
                <a href="/store/invoices/edit/{{ invoice._id }}">
                    <button style="width: auto; padding: 12px 20px; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-edit" style="margin-right: 8px;"></i> Edit
                    </button>
                </a>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- Customer Info -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Details</span>
                </div>
                <div style="display: grid; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Name</span>
                        <span style="font-weight: 600;">{{ invoice.customer_name }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Phone</span>
                        <span style="font-weight: 600;">{{ invoice.customer_phone or '-' }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Address</span>
                        <span style="font-weight: 600; text-align: right; max-width: 200px;">{{ invoice.customer_address or '-' }}</span>
                    </div>
                </div>
            </div>

            <!-- Payment Status -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-money-check-alt" style="margin-right: 10px; color: var(--accent-green);"></i>Payment Status</span>
                    {% if invoice.due_amount == 0 %}
                    <span class="paid-badge">PAID</span>
                    {% elif invoice.paid_amount > 0 %}
                    <span class="partial-badge">PARTIAL</span>
                    {% else %}
                    <span class="due-badge">UNPAID</span>
                    {% endif %}
                </div>
                <div style="display: grid; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                        <span style="color: var(--text-secondary);">Grand Total</span>
                        <span style="font-weight: 700; font-size: 18px;">৳{{ "{:,.2f}".format(invoice.grand_total) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(16, 185, 129, 0.1); border-radius: 8px;">
                        <span style="color: var(--accent-green);">Paid Amount</span>
                        <span style="font-weight: 700; font-size: 18px; color: var(--accent-green);">৳{{ "{:,.2f}".format(invoice.paid_amount) }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(239, 68, 68, 0.1); border-radius: 8px;">
                        <span style="color: var(--accent-red);">Due Amount</span>
                        <span style="font-weight: 700; font-size: 18px; color: var(--accent-red);">৳{{ "{:,.2f}".format(invoice.due_amount) }}</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Invoice Items -->
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Items</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Description</th>
                            <th>Rate</th>
                            <th>Qty</th>
                            <th>Unit</th>
                            <th style="text-align: right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in invoice.items %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td style="font-weight: 600;">{{ item.description }}</td>
                            <td>৳{{ "{:,.2f}".format(item.rate) }}</td>
                            <td>{{ item.quantity }}</td>
                            <td>{{ item.unit }}</td>
                            <td style="text-align: right; font-weight: 700;">৳{{ "{:,.2f}".format(item.amount) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                    <tfoot>
                        <tr style="background: rgba(255,255,255,0.02);">
                            <td colspan="5" style="text-align: right; font-weight: 600;">Subtotal:</td>
                            <td style="text-align: right; font-weight: 700;">৳{{ "{:,.2f}".format(invoice.subtotal) }}</td>
                        </tr>
                        {% if invoice.discount > 0 %}
                        <tr style="background: rgba(255,255,255,0.02);">
                            <td colspan="5" style="text-align: right; font-weight: 600;">Discount:</td>
                            <td style="text-align: right; font-weight: 700; color: var(--accent-red);">-৳{{ "{:,.2f}".format(invoice.discount) }}</td>
                        </tr>
                        {% endif %}
                        <tr style="background: rgba(255, 122, 0, 0.1);">
                            <td colspan="5" style="text-align: right; font-weight: 800; font-size: 16px;">Grand Total:</td>
                            <td style="text-align: right; font-weight: 800; font-size: 16px; color: var(--accent-orange);">৳{{ "{:,.2f}".format(invoice.grand_total) }}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>

        <!-- Payment History -->
        {% if payments %}
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-history" style="margin-right: 10px; color: var(--accent-blue);"></i>Payment History</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Method</th>
                            <th>Note</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for pay in payments %}
                        <tr>
                            <td>{{ pay.date }}</td>
                            <td class="amount-positive">৳{{ "{:,.2f}".format(pay.amount) }}</td>
                            <td>{{ pay.method or 'Cash' }}</td>
                            <td style="color: var(--text-secondary);">{{ pay.note or '-' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}

        {% if invoice.notes %}
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-sticky-note" style="margin-right: 10px; color: var(--text-secondary);"></i>Notes</span>
            </div>
            <p style="color: var(--text-secondary); line-height: 1.6;">{{ invoice.notes }}</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

STORE_INVOICE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice #{{ invoice.invoice_number }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }
        
        body {
            background: #fff;
            color: #000;
            padding: 20px;
        }
        
        .invoice-container {
            max-width: 800px;
            margin: 0 auto;
            border: 2px solid #000;
            padding: 30px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 2px solid #000;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        
        .company-info h1 {
            font-size: 28px;
            font-weight: 800;
            color: #1a1a2e;
            margin-bottom: 5px;
        }
        
        .company-info p {
            font-size: 12px;
            color: #555;
            line-height: 1.5;
        }
        
        .invoice-title {
            text-align: right;
        }
        
        .invoice-title h2 {
            font-size: 32px;
            font-weight: 800;
            color: #FF7A00;
            margin-bottom: 10px;
        }
        
        .invoice-title .invoice-number {
            font-size: 16px;
            font-weight: 700;
            background: #1a1a2e;
            color: #fff;
            padding: 8px 20px;
            border-radius: 5px;
            display: inline-block;
        }
        
        .invoice-title .invoice-date {
            font-size: 13px;
            color: #555;
            margin-top: 10px;
        }
        
        .info-section {
            display: flex;
            justify-content: space-between;
            margin-bottom: 25px;
        }
        
        .info-box {
            width: 48%;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #FF7A00;
        }
        
        .info-box h3 {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #888;
            margin-bottom: 10px;
        }
        
        .info-box p {
            font-size: 14px;
            font-weight: 600;
            color: #000;
            margin-bottom: 5px;
        }
        
        .info-box .sub-info {
            font-size: 12px;
            color: #555;
            font-weight: 400;
        }
        
        .items-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }
        
        .items-table th {
            background: #1a1a2e;
            color: #fff;
            padding: 12px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .items-table th:last-child {
            text-align: right;
        }
        
        .items-table td {
            padding: 12px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }
        
        .items-table td:last-child {
            text-align: right;
            font-weight: 600;
        }
        
        .items-table tbody tr:hover {
            background: #f9f9f9;
        }
        
        .totals-section {
            display: flex;
            justify-content: flex-end;
        }
        
        .totals-box {
            width: 300px;
            background: #f8f9fa;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .totals-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        .totals-row:last-child {
            border-bottom: none;
        }
        
        .totals-row.grand-total {
            background: #FF7A00;
            color: #fff;
            font-size: 18px;
            font-weight: 800;
        }
        
        .totals-label {
            color: #555;
            font-size: 13px;
        }
        
        .totals-value {
            font-weight: 700;
            font-size: 14px;
        }
        
        .grand-total .totals-label,
        .grand-total .totals-value {
            color: #fff;
        }
        
        .payment-status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-weight: 700;
            font-size: 14px;
        }
        
        .status-paid {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status-partial {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }
        
        .status-unpaid {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
        }
        
        .footer p {
            font-size: 11px;
            color: #888;
            margin-bottom: 5px;
        }
        
        .signature-section {
            display: flex;
            justify-content: space-between;
            margin-top: 60px;
            padding-top: 20px;
        }
        
        .signature-box {
            width: 200px;
            text-align: center;
        }
        
        .signature-line {
            border-top: 2px solid #000;
            padding-top: 10px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .no-print {
            margin-bottom: 20px;
            text-align: center;
        }
        
        .no-print button {
            padding: 12px 30px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            border-radius: 8px;
            margin: 0 5px;
        }
        
        .btn-print {
            background: #FF7A00;
            color: #fff;
        }
        
        .btn-back {
            background: #eee;
            color: #333;
        }
        
        @media print {
            body {
                padding: 0;
            }
            
            .invoice-container {
                border: none;
                padding: 0;
            }
            
            .no-print {
                display: none;
            }
            
            .items-table th {
                background: #1a1a2e !important;
                color: #fff !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            
            .totals-row.grand-total {
                background: #FF7A00 !important;
                color: #fff !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
</head>
<body>
    <div class="no-print">
        <button class="btn-print" onclick="window.print()"><i class="fas fa-print"></i> Print Invoice</button>
        <button class="btn-back" onclick="window.close()">Close</button>
    </div>
    
    <div class="invoice-container">
        <div class="header">
            <div class="company-info">
                <h1>{{ settings.store_name }}</h1>
                <p>{{ settings.store_address }}</p>
                <p>Phone: {{ settings.store_phone }}</p>
                {% if settings.store_email %}
                <p>Email: {{ settings.store_email }}</p>
                {% endif %}
            </div>
            <div class="invoice-title">
                <h2>INVOICE</h2>
                <div class="invoice-number">{{ invoice.invoice_number }}</div>
                <div class="invoice-date">Date: {{ invoice.date }}</div>
            </div>
        </div>
        
        <div class="info-section">
            <div class="info-box">
                <h3>Bill To</h3>
                <p>{{ invoice.customer_name }}</p>
                <p class="sub-info">{{ invoice.customer_phone or '' }}</p>
                <p class="sub-info">{{ invoice.customer_address or '' }}</p>
            </div>
            <div class="info-box">
                <h3>Payment Info</h3>
                <p>Total: ৳{{ "{:,.2f}".format(invoice.grand_total) }}</p>
                <p class="sub-info">Paid: ৳{{ "{:,.2f}".format(invoice.paid_amount) }}</p>
                <p class="sub-info">Due: ৳{{ "{:,.2f}".format(invoice.due_amount) }}</p>
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Description</th>
                    <th>Rate</th>
                    <th>Qty</th>
                    <th>Unit</th>
                    <th>Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.description }}</td>
                    <td>৳{{ "{:,.2f}".format(item.rate) }}</td>
                    <td>{{ item.quantity }}</td>
                    <td>{{ item.unit }}</td>
                    <td>৳{{ "{:,.2f}".format(item.amount) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-section">
            <div class="totals-box">
                <div class="totals-row">
                    <span class="totals-label">Subtotal</span>
                    <span class="totals-value">৳{{ "{:,.2f}".format(invoice.subtotal) }}</span>
                </div>
                {% if invoice.discount > 0 %}
                <div class="totals-row">
                    <span class="totals-label">Discount</span>
                    <span class="totals-value">-৳{{ "{:,.2f}".format(invoice.discount) }}</span>
                </div>
                {% endif %}
                <div class="totals-row grand-total">
                    <span class="totals-label">Grand Total</span>
                    <span class="totals-value">৳{{ "{:,.2f}".format(invoice.grand_total) }}</span>
                </div>
            </div>
        </div>
        
        {% if invoice.due_amount == 0 %}
        <div class="payment-status status-paid">
            ✓ PAYMENT COMPLETED
        </div>
        {% elif invoice.paid_amount > 0 %}
        <div class="payment-status status-partial">
            ⚠ PARTIAL PAYMENT - Due: ৳{{ "{:,.2f}".format(invoice.due_amount) }}
        </div>
        {% else %}
        <div class="payment-status status-unpaid">
            ✕ PAYMENT PENDING - Due: ৳{{ "{:,.2f}".format(invoice.due_amount) }}
        </div>
        {% endif %}
        
        {% if invoice.notes %}
        <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <strong>Notes:</strong> {{ invoice.notes }}
        </div>
        {% endif %}
        
        <div class="signature-section">
            <div class="signature-box">
                <div class="signature-line">Customer Signature</div>
            </div>
            <div class="signature-box">
                <div class="signature-line">Authorized Signature</div>
            </div>
        </div>
        
        <div class="footer">
            <p>Thank you for your business! </p>
            <p>Generated by MNM Software • {{ today }}</p>
        </div>
    </div>
</body>
</html>
"""

STORE_INVOICE_EDIT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Invoice - Store Panel</title>
""" + COMMON_STYLES + """
    <style>
        .invoice-item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto;
            gap: 10px;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .invoice-item-row input, .invoice-item-row select {
            padding: 10px 12px;
            font-size: 14px;
        }
        
        .remove-item {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .remove-item:hover {
            background: var(--accent-red);
            color: white;
        }
        
        .totals-section {
            background: rgba(255, 122, 0, 0.05);
            border: 1px solid rgba(255, 122, 0, 0.2);
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
            color: var(--accent-orange);
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Edit Invoice</div>
                <div class="page-subtitle">Invoice #: {{ invoice.invoice_number }}</div>
            </div>
        </div>

        <form action="/store/invoices/edit/{{ invoice._id }}" method="post" id="invoiceForm">
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span>
                    </div>
                    
                    <div class="input-group">
                        <label>CUSTOMER *</label>
                        <select name="customer_id" id="customerSelect" required>
                            {% for cust in customers %}
                            <option value="{{ cust._id }}" {{ 'selected' if str(cust._id) == invoice.customer_id else '' }}>
                                {{ cust.name }} - {{ cust.phone }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calendar" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Details</span>
                    </div>
                    
                    <div class="input-group">
                        <label>INVOICE DATE *</label>
                        <input type="date" name="date" value="{{ invoice.date }}" required>
                    </div>
                    
                    <div class="input-group">
                        <label>NOTES</label>
                        <textarea name="notes" rows="2">{{ invoice.notes or '' }}</textarea>
                    </div>
                </div>
            </div>

            <!-- Invoice Items -->
            <div class="card" style="margin-top: 25px;">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-green);"></i>Invoice Items</span>
                    <button type="button" onclick="addItem()" style="width: auto; padding: 8px 20px; font-size: 13px;">
                        <i class="fas fa-plus" style="margin-right: 5px;"></i> Add Item
                    </button>
                </div>
                
                <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto; gap: 10px; padding: 10px 15px; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
                    <div>Description</div>
                    <div>Rate</div>
                    <div>Quantity</div>
                    <div>Unit</div>
                    <div>Amount</div>
                    <div></div>
                </div>
                
                <div id="itemsContainer">
                    <!-- Existing items will be loaded here -->
                </div>
                
                <div class="totals-section">
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Subtotal</span>
                        <span style="font-weight: 700; color: white;" id="subtotal">৳0</span>
                    </div>
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">
                            Discount 
                            <input type="number" name="discount" id="discountInput" value="{{ invoice.discount or 0 }}" min="0" step="0.01" 
                                style="width: 100px; padding: 5px 10px; margin-left: 10px;" onchange="calculateTotals()">
                        </span>
                        <span style="font-weight: 700; color: white;" id="discountAmount">৳0</span>
                    </div>
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Grand Total</span>
                        <span style="font-weight: 800; font-size: 20px; color: var(--accent-orange);" id="grandTotal">৳0</span>
                    </div>
                </div>
                
                <input type="hidden" name="items_json" id="itemsJson">
                <input type="hidden" name="subtotal" id="subtotalInput">
                <input type="hidden" name="grand_total" id="grandTotalInput">
            </div>

            <div style="display: flex; gap: 15px; margin-top: 25px;">
                <button type="submit" onclick="return prepareSubmit()" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync-alt" style="margin-right: 8px;"></i> Update Invoice
                </button>
                <a href="/store/invoices/view/{{ invoice._id }}" style="flex: 1;">
                    <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                        <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                    </button>
                </a>
            </div>
        </form>
    </div>

    <script>
        const products = {{ products_json | safe }};
        const existingItems = {{ items_json | safe }};
        let itemCount = 0;
        
        function addItem(data = null) {
            itemCount++;
            const container = document.getElementById('itemsContainer');
            
            const html = `
                <div class="invoice-item-row" id="item-${itemCount}">
                    <input type="text" id="desc-${itemCount}" placeholder="Description" value="${data ?  data.description : ''}">
                    <input type="number" id="rate-${itemCount}" placeholder="0.00" step="0.01" min="0" value="${data ? data.rate : ''}" onchange="calculateRowTotal(${itemCount})">
                    <input type="number" id="qty-${itemCount}" placeholder="1" value="${data ? data.quantity : 1}" min="0.01" step="0.01" onchange="calculateRowTotal(${itemCount})">
                    <select id="unit-${itemCount}">
                        <option value="Pcs" ${data && data.unit === 'Pcs' ? 'selected' : ''}>Pcs</option>
                        <option value="Ft" ${data && data.unit === 'Ft' ?  'selected' : ''}>Ft</option>
                        <option value="Meter" ${data && data.unit === 'Meter' ?  'selected' : ''}>Meter</option>
                        <option value="Kg" ${data && data.unit === 'Kg' ?  'selected' : ''}>Kg</option>
                        <option value="Set" ${data && data.unit === 'Set' ? 'selected' : ''}>Set</option>
                        <option value="Sqft" ${data && data.unit === 'Sqft' ? 'selected' : ''}>Sqft</option>
                    </select>
                    <input type="text" id="amount-${itemCount}" value="${data ? data.amount.toFixed(2) : '0.00'}" readonly style="background: rgba(255,255,255,0.05); font-weight: 700;">
                    <button type="button" class="remove-item" onclick="removeItem(${itemCount})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            container.insertAdjacentHTML('beforeend', html);
            if (data) calculateRowTotal(itemCount);
        }
        
        function calculateRowTotal(id) {
            const rate = parseFloat(document.getElementById('rate-' + id).value) || 0;
            const qty = parseFloat(document.getElementById('qty-' + id).value) || 0;
            const amount = rate * qty;
            document.getElementById('amount-' + id).value = amount.toFixed(2);
            calculateTotals();
        }
        
        function removeItem(id) {
            document.getElementById('item-' + id).remove();
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('[id^="amount-"]').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            
            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document.getElementById('discountAmount').textContent = '৳' + discount.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳' + grandTotal.toFixed(2);
            
            document.getElementById('subtotalInput').value = subtotal;
            document.getElementById('grandTotalInput').value = grandTotal;
        }
        
        function prepareSubmit() {
            const items = [];
            document.querySelectorAll('.invoice-item-row').forEach(row => {
                const id = row.id.split('-')[1];
                items.push({
                    description: document.getElementById('desc-' + id).value,
                    rate: parseFloat(document.getElementById('rate-' + id).value) || 0,
                    quantity: parseFloat(document.getElementById('qty-' + id).value) || 0,
                    unit: document.getElementById('unit-' + id).value,
                    amount: parseFloat(document.getElementById('amount-' + id).value) || 0
                });
            });
            
            if (items.length === 0) {
                alert('Please add at least one item');
                return false;
            }
            
            document.getElementById('itemsJson').value = JSON.stringify(items);
            return true;
        }
        
        // Load existing items
        existingItems.forEach(item => addItem(item));
        if (existingItems.length === 0) addItem();
    </script>
</body>
</html>
"""

STORE_INVOICE_PAY_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Collect Payment - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Collect Payment</div>
                <div class="page-subtitle">Invoice #{{ invoice.invoice_number }}</div>
            </div>
        </div>

        <div class="card" style="max-width: 500px;">
            <div class="section-header">
                <span><i class="fas fa-hand-holding-usd" style="margin-right: 10px; color: var(--accent-green);"></i>Payment Details</span>
            </div>
            
            <!-- Invoice Summary -->
            <div style="background: rgba(255,255,255,0.02); padding: 20px; border-radius: 12px; margin-bottom: 25px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: var(--text-secondary);">Customer</span>
                    <span style="font-weight: 600;">{{ invoice.customer_name }}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: var(--text-secondary);">Total Amount</span>
                    <span style="font-weight: 600;">৳{{ "{:,.2f}".format(invoice.grand_total) }}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: var(--text-secondary);">Already Paid</span>
                    <span style="font-weight: 600; color: var(--accent-green);">৳{{ "{:,.2f}".format(invoice.paid_amount) }}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding-top: 10px; border-top: 1px solid var(--border-color);">
                    <span style="color: var(--accent-red); font-weight: 600;">Due Amount</span>
                    <span style="font-weight: 800; font-size: 20px; color: var(--accent-red);">৳{{ "{:,.2f}".format(invoice.due_amount) }}</span>
                </div>
            </div>
            
            <form action="/store/invoices/pay/{{ invoice._id }}" method="post">
                <div class="input-group">
                    <label><i class="fas fa-money-bill-wave" style="margin-right: 5px;"></i> PAYMENT AMOUNT (৳) *</label>
                    <input type="number" name="amount" required step="0.01" min="0.01" max="{{ invoice.due_amount }}" 
                        placeholder="Enter amount" value="{{ invoice.due_amount }}">
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-credit-card" style="margin-right: 5px;"></i> PAYMENT METHOD</label>
                    <select name="method">
                        <option value="Cash">Cash</option>
                        <option value="bKash">bKash</option>
                        <option value="Nagad">Nagad</option>
                        <option value="Bank Transfer">Bank Transfer</option>
                        <option value="Card">Card</option>
                        <option value="Other">Other</option>
                    </select>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sticky-note" style="margin-right: 5px;"></i> NOTE (Optional)</label>
                    <input type="text" name="note" placeholder="Payment note...">
                </div>
                
                <div style="display: flex; gap: 15px; margin-top: 10px;">
                    <button type="submit" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-check" style="margin-right: 8px;"></i> Confirm Payment
                    </button>
                    <a href="/store/invoices/view/{{ invoice._id }}" style="flex: 1;">
                        <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                            <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                        </button>
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE QUOTATION TEMPLATES
# ==============================================================================

STORE_QUOTATIONS_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Quotations - Store Panel</title>
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
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link active">
                <i class="fas fa-file-alt"></i> Quotations
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
                <div class="page-title">Quotations / Estimates</div>
                <div class="page-subtitle">Manage price quotations for customers</div>
            </div>
            <a href="/store/quotations/new">
                <button style="width: auto; padding: 12px 25px;">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> New Quotation
                </button>
            </a>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="section-header">
                <span>All Quotations</span>
                <span class="table-badge" style="background: var(--accent-purple); color: white;">{{ quotations|length }} Total</span>
            </div>
            
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Quotation #</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Total</th>
                            <th>Valid Until</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for qt in quotations %}
                        <tr>
                            <td><span class="table-badge" style="background: rgba(139, 92, 246, 0.2); color: var(--accent-purple);">{{ qt.quotation_number }}</span></td>
                            <td>{{ qt.date }}</td>
                            <td style="font-weight: 600;">{{ qt.customer_name }}</td>
                            <td style="font-weight: 700;">৳{{ "{:,.0f}".format(qt.grand_total) }}</td>
                            <td>{{ qt.valid_until or '-' }}</td>
                            <td>
                                {% if qt.status == 'converted' %}
                                <span class="paid-badge">Converted</span>
                                {% elif qt.status == 'expired' %}
                                <span class="due-badge">Expired</span>
                                {% else %}
                                <span class="partial-badge">Pending</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/quotations/print/{{ qt._id }}" class="action-btn btn-view" title="Print" target="_blank">
                                        <i class="fas fa-print"></i>
                                    </a>
                                    {% if qt.status != 'converted' %}
                                    <a href="/store/quotations/convert/{{ qt._id }}" class="action-btn btn-pay" title="Convert to Invoice">
                                        <i class="fas fa-exchange-alt"></i>
                                    </a>
                                    {% endif %}
                                    <a href="/store/quotations/edit/{{ qt._id }}" class="action-btn btn-edit" title="Edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    <button class="action-btn btn-del" onclick="deleteQuotation('{{ qt._id }}')" title="Delete">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" style="text-align: center; padding: 50px; color: var(--text-secondary);">
                                <i class="fas fa-file-alt" style="font-size: 40px; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                                No quotations found. Create your first quotation! 
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function deleteQuotation(id) {
            if (confirm('Are you sure you want to delete this quotation?')) {
                fetch('/store/quotations/delete/' + id, {
                    method: 'POST'
                }).then(() => location.reload());
            }
        }
    </script>
</body>
</html>
"""

STORE_QUOTATION_NEW_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Quotation - Store Panel</title>
""" + COMMON_STYLES + """
    <style>
        .invoice-item-row {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto;
            gap: 10px;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .invoice-item-row input, .invoice-item-row select {
            padding: 10px 12px;
            font-size: 14px;
        }
        
        .remove-item {
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
        }
        
        .totals-section {
            background: rgba(139, 92, 246, 0.05);
            border: 1px solid rgba(139, 92, 246, 0.2);
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

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/quotations" class="nav-link active">
                <i class="fas fa-file-alt"></i> Quotations
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create New Quotation</div>
                <div class="page-subtitle">Quotation #: {{ quotation_number }}</div>
            </div>
        </div>

        <form action="/store/quotations/new" method="post" id="quotationForm">
            <input type="hidden" name="quotation_number" value="{{ quotation_number }}">
            
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Information</span>
                    </div>
                    
                    <div class="input-group">
                        <label>SELECT CUSTOMER *</label>
                        <select name="customer_id" id="customerSelect" required>
                            <option value="">-- Select Customer --</option>
                            {% for cust in customers %}
                            <option value="{{ cust._id }}" data-name="{{ cust.name }}" data-phone="{{ cust.phone }}">
                                {{ cust.name }} - {{ cust.phone }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div style="margin-top: 15px; text-align: center;">
                        <a href="/store/customers/add" style="color: var(--accent-purple); font-size: 13px;">
                            <i class="fas fa-plus-circle"></i> Add New Customer
                        </a>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calendar" style="margin-right: 10px; color: var(--accent-orange);"></i>Quotation Details</span>
                    </div>
                    
                    <div class="grid-2">
                        <div class="input-group">
                            <label>QUOTATION DATE *</label>
                            <input type="date" name="date" value="{{ today }}" required>
                        </div>
                        <div class="input-group">
                            <label>VALID UNTIL</label>
                            <input type="date" name="valid_until" value="{{ valid_until }}">
                        </div>
                    </div>
                    
                    <div class="input-group">
                        <label>NOTES / TERMS</label>
                        <textarea name="notes" rows="2" placeholder="Terms and conditions..."></textarea>
                    </div>
                </div>
            </div>

            <!-- Quotation Items -->
            <div class="card" style="margin-top: 25px;">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-green);"></i>Quotation Items</span>
                    <button type="button" onclick="addItem()" style="width: auto; padding: 8px 20px; font-size: 13px; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-plus" style="margin-right: 5px;"></i> Add Item
                    </button>
                </div>
                
                <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto; gap: 10px; padding: 10px 15px; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
                    <div>Product / Description</div>
                    <div>Rate (৳)</div>
                    <div>Quantity</div>
                    <div>Unit</div>
                    <div>Amount (৳)</div>
                    <div></div>
                </div>
                
                <div id="itemsContainer"></div>
                
                <div class="totals-section">
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Subtotal</span>
                        <span style="font-weight: 700; color: white;" id="subtotal">৳0</span>
                    </div>
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">
                            Discount 
                            <input type="number" name="discount" id="discountInput" value="0" min="0" step="0.01" 
                                style="width: 100px; padding: 5px 10px; margin-left: 10px;" onchange="calculateTotals()">
                        </span>
                        <span style="font-weight: 700; color: white;" id="discountAmount">৳0</span>
                    </div>
                    <div class="total-row">
                        <span style="color: var(--text-secondary);">Grand Total</span>
                        <span id="grandTotal">৳0</span>
                    </div>
                </div>
                
                <input type="hidden" name="items_json" id="itemsJson">
                <input type="hidden" name="subtotal" id="subtotalInput">
                <input type="hidden" name="grand_total" id="grandTotalInput">
            </div>

            <div style="display: flex; gap: 15px; margin-top: 25px;">
                <button type="submit" onclick="return prepareSubmit()" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-save" style="margin-right: 8px;"></i> Save Quotation
                </button>
                <a href="/store/quotations" style="flex: 1;">
                    <button type="button" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); width: 100%;">
                        <i class="fas fa-times" style="margin-right: 8px;"></i> Cancel
                    </button>
                </a>
            </div>
        </form>
    </div>

    <script>
        const products = {{ products_json | safe }};
        let itemCount = 0;
        
        function addItem() {
            itemCount++;
            const container = document.getElementById('itemsContainer');
            
            let productOptions = '<option value="">-- Select or Type --</option>';
            products.forEach(p => {
                productOptions += `<option value="${p._id}" data-price="${p.price}" data-unit="${p.unit}">${p.name}</option>`;
            });
            
            const html = `
                <div class="invoice-item-row" id="item-${itemCount}">
                    <div>
                        <select onchange="updateItemPrice(this, ${itemCount})" id="product-${itemCount}">
                            ${productOptions}
                        </select>
                        <input type="text" id="desc-${itemCount}" placeholder="Or type description..." style="margin-top: 8px;">
                    </div>
                    <input type="number" id="rate-${itemCount}" placeholder="0.00" step="0.01" min="0" onchange="calculateRowTotal(${itemCount})">
                    <input type="number" id="qty-${itemCount}" placeholder="1" value="1" min="0.01" step="0.01" onchange="calculateRowTotal(${itemCount})">
                    <select id="unit-${itemCount}">
                        <option value="Pcs">Pcs</option>
                        <option value="Ft">Ft</option>
                        <option value="Meter">Meter</option>
                        <option value="Kg">Kg</option>
                        <option value="Set">Set</option>
                        <option value="Sqft">Sqft</option>
                    </select>
                    <input type="text" id="amount-${itemCount}" value="0.00" readonly style="background: rgba(255,255,255,0.05); font-weight: 700;">
                    <button type="button" class="remove-item" onclick="removeItem(${itemCount})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            container.insertAdjacentHTML('beforeend', html);
        }
        
        function updateItemPrice(select, id) {
            const option = select.options[select.selectedIndex];
            if (option.value) {
                document.getElementById('rate-' + id).value = option.getAttribute('data-price') || 0;
                document.getElementById('unit-' + id).value = option.getAttribute('data-unit') || 'Pcs';
                calculateRowTotal(id);
            }
        }
        
        function calculateRowTotal(id) {
            const rate = parseFloat(document.getElementById('rate-' + id).value) || 0;
            const qty = parseFloat(document.getElementById('qty-' + id).value) || 0;
            const amount = rate * qty;
            document.getElementById('amount-' + id).value = amount.toFixed(2);
            calculateTotals();
        }
        
        function removeItem(id) {
            document.getElementById('item-' + id).remove();
            calculateTotals();
        }
        
        function calculateTotals() {
            let subtotal = 0;
            document.querySelectorAll('[id^="amount-"]').forEach(input => {
                subtotal += parseFloat(input.value) || 0;
            });
            
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            
            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document.getElementById('discountAmount').textContent = '৳' + discount.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳' + grandTotal.toFixed(2);
            
            document.getElementById('subtotalInput').value = subtotal;
            document.getElementById('grandTotalInput').value = grandTotal;
        }
        
        function prepareSubmit() {
            const items = [];
            document.querySelectorAll('.invoice-item-row').forEach(row => {
                const id = row.id.split('-')[1];
                const productSelect = document.getElementById('product-' + id);
                const desc = document.getElementById('desc-' + id).value;
                const productName = productSelect.options[productSelect.selectedIndex].text;
                
                items.push({
                    product_id: productSelect.value,
                    description: desc || (productSelect.value ?  productName : ''),
                    rate: parseFloat(document.getElementById('rate-' + id).value) || 0,
                    quantity: parseFloat(document.getElementById('qty-' + id).value) || 0,
                    unit: document.getElementById('unit-' + id).value,
                    amount: parseFloat(document.getElementById('amount-' + id).value) || 0
                });
            });
            
            if (items.length === 0) {
                alert('Please add at least one item');
                return false;
            }
            
            document.getElementById('itemsJson').value = JSON.stringify(items);
            return true;
        }
        
        addItem();
    </script>
</body>
</html>
"""

STORE_QUOTATION_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quotation #{{ quotation.quotation_number }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background: #fff; color: #000; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; border: 2px solid #8B5CF6; padding: 30px; }
        .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #8B5CF6; padding-bottom: 20px; margin-bottom: 20px; }
        .company-info h1 { font-size: 28px; font-weight: 800; color: #1a1a2e; margin-bottom: 5px; }
        .company-info p { font-size: 12px; color: #555; line-height: 1.5; }
        .quote-title { text-align: right; }
        .quote-title h2 { font-size: 32px; font-weight: 800; color: #8B5CF6; margin-bottom: 10px; }
        .quote-title .quote-number { font-size: 16px; font-weight: 700; background: #8B5CF6; color: #fff; padding: 8px 20px; border-radius: 5px; display: inline-block; }
        .quote-title .quote-date { font-size: 13px; color: #555; margin-top: 10px; }
        .info-section { display: flex; justify-content: space-between; margin-bottom: 25px; }
        .info-box { width: 48%; background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #8B5CF6; }
        .info-box h3 { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 10px; }
        .info-box p { font-size: 14px; font-weight: 600; color: #000; margin-bottom: 5px; }
        .info-box .sub-info { font-size: 12px; color: #555; font-weight: 400; }
        .items-table { width: 100%; border-collapse: collapse; margin-bottom: 25px; }
        .items-table th { background: #8B5CF6; color: #fff; padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; }
        .items-table th:last-child { text-align: right; }
        .items-table td { padding: 12px; border-bottom: 1px solid #eee; font-size: 13px; }
        .items-table td:last-child { text-align: right; font-weight: 600; }
        .totals-section { display: flex; justify-content: flex-end; }
        .totals-box { width: 300px; background: #f8f9fa; border-radius: 8px; overflow: hidden; }
        .totals-row { display: flex; justify-content: space-between; padding: 12px 15px; border-bottom: 1px solid #eee; }
        .totals-row.grand-total { background: #8B5CF6; color: #fff; font-size: 18px; font-weight: 800; border-bottom: none; }
        .validity-note { margin-top: 25px; padding: 15px; background: #fff3cd; border-radius: 8px; border: 1px solid #ffc107; text-align: center; font-size: 13px; color: #856404; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; }
        .footer p { font-size: 11px; color: #888; margin-bottom: 5px; }
        .signature-section { display: flex; justify-content: space-between; margin-top: 60px; }
        .signature-box { width: 200px; text-align: center; }
        .signature-line { border-top: 2px solid #000; padding-top: 10px; font-size: 12px; font-weight: 600; }
        .no-print { margin-bottom: 20px; text-align: center; }
        .no-print button { padding: 12px 30px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; border-radius: 8px; margin: 0 5px; }
        .btn-print { background: #8B5CF6; color: #fff; }
        .btn-back { background: #eee; color: #333; }
        @media print {
            body { padding: 0; }
            .container { border: none; padding: 0; }
            .no-print { display: none; }
            .items-table th { background: #8B5CF6 !important; color: #fff ! important; -webkit-print-color-adjust: exact; }
            .totals-row.grand-total { background: #8B5CF6 ! important; color: #fff !important; -webkit-print-color-adjust: exact; }
        }
    </style>
</head>
<body>
    <div class="no-print">
        <button class="btn-print" onclick="window.print()">🖨️ Print Quotation</button>
        <button class="btn-back" onclick="window.close()">Close</button>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="company-info">
                <h1>{{ settings.store_name }}</h1>
                <p>{{ settings.store_address }}</p>
                <p>Phone: {{ settings.store_phone }}</p>
            </div>
            <div class="quote-title">
                <h2>QUOTATION</h2>
                <div class="quote-number">{{ quotation.quotation_number }}</div>
                <div class="quote-date">Date: {{ quotation.date }}</div>
            </div>
        </div>
        
        <div class="info-section">
            <div class="info-box">
                <h3>Quotation For</h3>
                <p>{{ quotation.customer_name }}</p>
                <p class="sub-info">{{ quotation.customer_phone or '' }}</p>
                <p class="sub-info">{{ quotation.customer_address or '' }}</p>
            </div>
            <div class="info-box">
                <h3>Validity</h3>
                <p>Valid Until: {{ quotation.valid_until or 'Not Specified' }}</p>
                <p class="sub-info">Status: {{ quotation.status.title() }}</p>
            </div>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Description</th>
                    <th>Rate</th>
                    <th>Qty</th>
                    <th>Unit</th>
                    <th>Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in quotation.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.description }}</td>
                    <td>৳{{ "{:,.2f}".format(item.rate) }}</td>
                    <td>{{ item.quantity }}</td>
                    <td>{{ item.unit }}</td>
                    <td>৳{{ "{:,.2f}".format(item.amount) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals-section">
            <div class="totals-box">
                <div class="totals-row">
                    <span>Subtotal</span>
                    <span>৳{{ "{:,.2f}".format(quotation.subtotal) }}</span>
                </div>
                {% if quotation.discount > 0 %}
                <div class="totals-row">
                    <span>Discount</span>
                    <span>-৳{{ "{:,.2f}".format(quotation.discount) }}</span>
                </div>
                {% endif %}
                <div class="totals-row grand-total">
                    <span>Grand Total</span>
                    <span>৳{{ "{:,.2f}".format(quotation.grand_total) }}</span>
                </div>
            </div>
        </div>
        
        {% if quotation.valid_until %}
        <div class="validity-note">
            ⚠️ This quotation is valid until <strong>{{ quotation.valid_until }}</strong>. Prices may change after this date.
        </div>
        {% endif %}
        
        {% if quotation.notes %}
        <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <strong>Terms & Conditions:</strong><br>{{ quotation.notes }}
        </div>
        {% endif %}
        
        <div class="signature-section">
            <div class="signature-box">
                <div class="signature-line">Customer Signature</div>
            </div>
            <div class="signature-box">
                <div class="signature-line">Authorized Signature</div>
            </div>
        </div>
        
        <div class="footer">
            <p>Thank you for considering our quotation! </p>
            <p>Generated by MNM Software • {{ today }}</p>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE DUE COLLECTION TEMPLATES
# ==============================================================================

STORE_DUES_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due Collection - Store Panel</title>
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
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/dues" class="nav-link active">
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
                <div class="page-title">Due Collection</div>
                <div class="page-subtitle">Manage and collect pending payments</div>
            </div>
            <div class="status-badge" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.2);">
                <i class="fas fa-exclamation-triangle" style="color: var(--accent-red);"></i>
                <span style="color: var(--accent-red); font-weight: 700;">Total Due: ৳{{ "{:,.0f}".format(total_due) }}</span>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="flash-message flash-{{ category }}">
                    <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                    <span>{{ message }}</span>
                </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Search -->
        <div class="card" style="margin-bottom: 25px; padding: 20px;">
            <div class="search-box" style="margin-bottom: 0;">
                <i class="fas fa-search"></i>
                <input type="text" id="searchDue" placeholder="Search by customer name or phone..." onkeyup="filterDues()">
            </div>
        </div>

        <!-- Due Customers List -->
        <div class="card">
            <div class="section-header">
                <span><i class="fas fa-users" style="margin-right: 10px; color: var(--accent-red);"></i>Customers with Pending Dues</span>
            </div>
            
            <div id="duesList">
                {% for cust in due_customers %}
                <div class="due-customer-card" style="background: rgba(255,255,255,0.02); border-radius: 12px; padding: 20px; margin-bottom: 15px; border: 1px solid var(--border-color);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div>
                            <div style="font-size: 18px; font-weight: 700; color: white;">{{ cust.customer_name }}</div>
                            <div style="font-size: 13px; color: var(--text-secondary);">{{ cust.invoice_count }} unpaid invoice(s)</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 24px; font-weight: 800; color: var(--accent-red);">৳{{ "{:,.0f}".format(cust.total_due) }}</div>
                            <a href="/store/dues/collect/{{ cust._id }}" style="color: var(--accent-green); font-size: 13px; text-decoration: none;">
                                <i class="fas fa-hand-holding-usd"></i> Collect Payment
                            </a>
                        </div>
                    </div>
                    
                    <!-- Unpaid Invoices for this customer -->
                    <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 12px;">
                        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-secondary); margin-bottom: 10px;">Unpaid Invoices</div>
                        {% for inv in cust.invoices %}
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-color);">
                            <div>
                                <span class="table-badge" style="background: rgba(255, 122, 0, 0.2); color: var(--accent-orange);">{{ inv.invoice_number }}</span>
                                <span style="margin-left: 10px; font-size: 13px; color: var(--text-secondary);">{{ inv.date }}</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 15px;">
                                <span style="font-weight: 600;">Due: ৳{{ "{:,.0f}".format(inv.due_amount) }}</span>
                                <a href="/store/invoices/pay/{{ inv._id }}" class="action-btn btn-pay" style="padding: 6px 12px;">
                                    <i class="fas fa-money-bill-wave"></i>
                                </a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% else %}
                <div style="text-align: center; padding: 60px; color: var(--text-secondary);">
                    <i class="fas fa-check-circle" style="font-size: 60px; color: var(--accent-green); opacity: 0.3; margin-bottom: 20px; display: block;"></i>
                    <div style="font-size: 18px; font-weight: 600; margin-bottom: 5px;">All Clear! </div>
                    <div>No pending dues. All payments are collected.</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Recent Payments -->
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-history" style="margin-right: 10px; color: var(--accent-green);"></i>Recent Payments</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Invoice</th>
                            <th>Amount</th>
                            <th>Method</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for pay in recent_payments %}
                        <tr>
                            <td>{{ pay.date }}</td>
                            <td style="font-weight: 600;">{{ pay.customer_name }}</td>
                            <td><span class="table-badge">{{ pay.invoice_number }}</span></td>
                            <td class="amount-positive">৳{{ "{:,.0f}".format(pay.amount) }}</td>
                            <td>{{ pay.method or 'Cash' }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" style="text-align: center; padding: 30px; color: var(--text-secondary);">
                                No payment records yet
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterDues() {
            const search = document.getElementById('searchDue').value.toLowerCase();
            const cards = document.querySelectorAll('.due-customer-card');
            
            cards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(search) ?  '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

STORE_DUE_COLLECT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Collect Due - Store Panel</title>
""" + COMMON_STYLES + """
</head>
<body>
    <div class="animated-bg"></div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link">
                <i class="fas fa-th-large"></i> Store Home
            </a>
            <a href="/store/dues" class="nav-link active">
                <i class="fas fa-wallet"></i> Due Collection
            </a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">© 2025 Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Collect Due Payment</div>
                <div class="page-subtitle">Customer: {{ customer.name }}</div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- Customer Summary -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Summary</span>
                </div>
                
                <div style="display: grid; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px;">
                        <span style="color: var(--text-secondary);">Name</span>
                        <span style="font-weight: 700;">{{ customer.name }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 15px; background: rgba(255,255,255,0.02); border-radius: 10px;">
                        <span style="color: var(--text-secondary);">Phone</span>
                        <span style="font-weight: 700;">{{ customer.phone }}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 15px; background: rgba(239, 68, 68, 0.1); border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.2);">
                        <span style="color: var(--accent-red);">Total Due</span>
                        <span style="font-weight: 800; font-size: 24px; color: var(--accent-red);">৳{{ "{:,.0f}".format(total_due) }}</span>
                    </div>
                </div>
            </div>

            <!-- Payment Form -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-hand-holding-usd" style="margin-right: 10px; color: var(--accent-green);"></i>Make Payment</span>
                </div>
                
                <form action="/store/dues/collect/{{ customer._id }}" method="post">
                    <div class="input-group">
                        <label>PAYMENT AMOUNT (৳) *</label>
                        <input type="number" name="amount" required step="0.01" min="0.01" max="{{ total_due }}"
                            placeholder="Enter amount" value="{{ total_due }}">
                    </div>
                    
                    <div class="input-group">
                        <label>PAYMENT METHOD</label>
                        <select name="method">
                            <option value="Cash">Cash</option>
                            <option value="bKash">bKash</option>
                            <option value="Nagad">Nagad</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="Card">Card</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                    
                    <div class="input-group">
                        <label>NOTE (Optional)</label>
                        <input type="text" name="note" placeholder="Payment note...">
                    </div>
                    
                    <button type="submit" style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                        <i class="fas fa-check" style="margin-right: 8px;"></i> Confirm Payment
                    </button>
                </form>
            </div>
        </div>

        <!-- Unpaid Invoices -->
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-file-invoice" style="margin-right: 10px; color: var(--accent-purple);"></i>Unpaid Invoices</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for inv in unpaid_invoices %}
                        <tr>
                            <td><span class="table-badge" style="background: rgba(255, 122, 0, 0.2); color: var(--accent-orange);">{{ inv.invoice_number }}</span></td>
                            <td>{{ inv.date }}</td>
                            <td>৳{{ "{:,.0f}".format(inv.grand_total) }}</td>
                            <td class="amount-positive">৳{{ "{:,.0f}".format(inv.paid_amount) }}</td>
                            <td><span class="due-badge">৳{{ "{:,.0f}".format(inv.due_amount) }}</span></td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/invoices/pay/{{ inv._id }}" class="action-btn btn-pay">
                                        <i class="fas fa-money-bill-wave"></i>
                                    </a>
                                    <a href="/store/invoices/view/{{ inv._id }}" class="action-btn btn-view">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div style="margin-top: 20px;">
            <a href="/store/dues">
                <button style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to Due List
                </button>
            </a>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTES - AUTHENTICATION & MAIN DASHBOARD
# ==============================================================================

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    users = load_users()
    user_data = users.get(session.get('user'), {})
    
    # স্টোর ইউজার হলে সরাসরি স্টোর ড্যাশবোর্ডে
    if user_data.get('permissions') == ['store'] or (len(user_data.get('permissions', [])) == 1 and 'store' in user_data.get('permissions', [])):
        return redirect(url_for('store_dashboard'))
    
    if session.get('role') == 'admin':
        stats = get_dashboard_summary_v2()
        return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
    else:
        return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = load_users()
        
        if username in users and users[username]['password'] == password:
            session.permanent = True
            session['user'] = username
            session['role'] = users[username]['role']
            session['permissions'] = users[username].get('permissions', [])
            session['login_time'] = get_bd_time().isoformat()
            
            # আপডেট লাস্ট লগইন
            users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
            save_users(users)
            
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!  ')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    if 'user' in session and 'login_time' in session:
        users = load_users()
        if session['user'] in users:
            try:
                login_time = datetime.fromisoformat(session['login_time'])
                now = get_bd_time()
                duration = now - login_time.replace(tzinfo=bd_tz)
                total_seconds = int(duration.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    duration_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_str = f"{minutes}m {seconds}s"
                else:
                    duration_str = f"{seconds}s"
                
                users[session['user']]['last_duration'] = duration_str
                save_users(users)
            except:
                pass
    
    session.clear()
    return redirect(url_for('login'))

# ==============================================================================
# FLASK ROUTES - CLOSING REPORT
# ==============================================================================

@app.route('/generate-report', methods=['POST'])
def generate_report():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref_no = request.form.get('ref_no', '').strip()
    if not ref_no:
        flash('Please enter a valid Ref No.')
        return redirect(url_for('home'))
    
    report_data = fetch_closing_report_data(ref_no)
    
    if report_data:
        excel_file = create_formatted_excel_report(report_data, ref_no)
        if excel_file:
            update_stats(ref_no, session['user'])
            filename = f"Closing_Report_{ref_no}_{get_bd_date_str()}.xlsx"
            return send_file(
                excel_file,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
    
    flash('Data not found or report generation failed for the given Ref No.')
    return redirect(url_for('home'))

# ==============================================================================
# FLASK ROUTES - PO SHEET GENERATOR
# ==============================================================================

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if 'pdf_files' not in request.files:
        flash('No files uploaded.')
        return redirect(url_for('home'))
    
    files = request.files.getlist('pdf_files')
    if not files or files[0].filename == '':
        flash('Please select at least one PDF file.')
        return redirect(url_for('home'))

    all_data = []
    global_metadata = None
    saved_file_paths = []

    for file in files:
        if file and file.filename.endswith('.pdf'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            saved_file_paths.append(file_path)
            
            extracted, meta = extract_data_dynamic(file_path)
            all_data.extend(extracted)
            if not global_metadata and meta.get('buyer') != 'N/A':
                global_metadata = meta

    if not all_data:
        for f_path in saved_file_paths:
            try: os.remove(f_path)
            except: pass
        flash('Could not extract any PO data from the uploaded files.')
        return redirect(url_for('home'))

    update_po_stats(session['user'], len(files))

    df = pd.DataFrame(all_data)
    df['P.O NO'] = df['P.O NO'].astype(str)
    df['Size'] = df['Size'].astype(str)
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0).astype(int)

    pivot_table = df.pivot_table(index=['P.O NO', 'Color'], columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
    pivot_table = pivot_table.reset_index()
    
    size_columns = [col for col in pivot_table.columns if col not in ['P.O NO', 'Color']]
    sorted_sizes = sort_sizes(size_columns)
    final_column_order = ['P.O NO', 'Color'] + sorted_sizes
    pivot_table = pivot_table.reindex(columns=final_column_order, fill_value=0)
    pivot_table['TOTAL'] = pivot_table[sorted_sizes].sum(axis=1)

    output = BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PO Summary"

    title_font = Font(size=16, bold=True, color="FFFFFF")
    header_font = Font(size=11, bold=True, color="FFFFFF")
    cell_font = Font(size=10)
    center_align = Alignment(horizontal='center', vertical='center')
    left_align = Alignment(horizontal='left', vertical='center')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    dark_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    header_fill = PatternFill(start_color="FF7A00", end_color="FF7A00", fill_type="solid")
    alt_fill_1 = PatternFill(start_color="f8f9fa", end_color="f8f9fa", fill_type="solid")
    alt_fill_2 = PatternFill(start_color="ffffff", end_color="ffffff", fill_type="solid")
    total_fill = PatternFill(start_color="e8f5e9", end_color="e8f5e9", fill_type="solid")

    meta = global_metadata or {}
    ws.merge_cells('A1:' + openpyxl.utils.get_column_letter(len(pivot_table.columns)) + '1')
    ws['A1'] = f"PURCHASE ORDER SUMMARY"
    ws['A1'].font = title_font
    ws['A1'].fill = dark_fill
    ws['A1'].alignment = center_align

    info_row = 2
    info_items = [
        f"Buyer: {meta.get('buyer', 'N/A')}",
        f"Booking: {meta.get('booking', 'N/A')}",
        f"Style: {meta.get('style', 'N/A')}",
        f"Date: {get_bd_date_str()}"
    ]
    ws.merge_cells(f'A{info_row}:' + openpyxl.utils.get_column_letter(len(pivot_table.columns)) + f'{info_row}')
    ws[f'A{info_row}'] = " | ".join(info_items)
    ws[f'A{info_row}'].font = Font(size=10, italic=True)
    ws[f'A{info_row}'].alignment = center_align

    header_row = 4
    for col_idx, header in enumerate(pivot_table.columns, 1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    for row_idx, row_data in enumerate(pivot_table.values, header_row + 1):
        fill = alt_fill_1 if row_idx % 2 == 0 else alt_fill_2
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = cell_font
            cell.alignment = center_align if col_idx > 2 else left_align
            cell.border = thin_border
            cell.fill = fill
            if col_idx == len(row_data):
                cell.fill = total_fill
                cell.font = Font(size=10, bold=True)

    total_row = header_row + len(pivot_table) + 1
    ws.cell(row=total_row, column=1, value="GRAND TOTAL").font = Font(bold=True)
    ws.cell(row=total_row, column=1).fill = dark_fill
    ws.cell(row=total_row, column=1).font = Font(bold=True, color="FFFFFF")
    ws.merge_cells(f'A{total_row}:B{total_row}')
    
    for col_idx in range(3, len(pivot_table.columns) + 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        cell = ws.cell(row=total_row, column=col_idx)
        cell.value = f"=SUM({col_letter}{header_row + 1}:{col_letter}{total_row - 1})"
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = dark_fill
        cell.alignment = center_align
        cell.border = thin_border

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        ws.column_dimensions[column].width = max(max_length + 2, 10)

    wb.save(output)
    output.seek(0)

    for f_path in saved_file_paths:
        try: os.remove(f_path)
        except: pass

    filename = f"PO_Summary_{meta.get('style', 'Report')}_{get_bd_date_str()}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ==============================================================================
# FLASK ROUTES - USER MANAGEMENT (ADMIN)
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
    username = data.get('username')
    password = data.get('password')
    permissions = data.get('permissions', [])
    action_type = data.get('action_type', 'create')
    
    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required"})
    
    users = load_users()
    
    if action_type == 'create':
        if username in users:
            return jsonify({"status": "error", "message": "User already exists"})
        users[username] = {
            "password": password,
            "role": "user",
            "permissions": permissions,
            "created_at": get_bd_time().strftime('%d-%m-%Y %I:%M %p'),
            "last_login": "Never",
            "last_duration": "N/A"
        }
    else:
        if username not in users:
            return jsonify({"status": "error", "message": "User not found"})
        if users[username].get('role') == 'admin':
            return jsonify({"status": "error", "message": "Cannot modify admin user"})
        users[username]['password'] = password
        users[username]['permissions'] = permissions
    
    save_users(users)
    return jsonify({"status": "success"})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if 'user' not in session or session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    
    data = request.get_json()
    username = data.get('username')
    
    users = load_users()
    if username in users and users[username].get('role') != 'admin':
        del users[username]
        save_users(users)
        return jsonify({"status": "success"})
    
    return jsonify({"status": "error", "message": "Cannot delete this user"})

# ==============================================================================
# FLASK ROUTES - ACCESSORIES MODULE
# ==============================================================================

@app.route('/admin/accessories')
def accessories_search():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref_no = request.form.get('ref_no', '').strip().upper()
    if not ref_no:
        flash('Please enter a valid reference number.')
        return redirect(url_for('accessories_search'))
    
    report_data = fetch_closing_report_data(ref_no)
    
    if report_data:
        db = load_accessories_db()
        if ref_no not in db:
            colors = list(set([item.get('color', 'N/A') for item in report_data]))
            db[ref_no] = {
                'buyer': report_data[0].get('buyer', 'N/A'),
                'style': report_data[0].get('style', 'N/A'),
                'colors': colors,
                'challans': []
            }
            save_accessories_db(db)
        
        return redirect(url_for('accessories_input_direct', ref=ref_no))
    else:
        flash('Could not find data for this reference number.')
        return redirect(url_for('accessories_search'))

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.args.get('ref', '').upper()
    db = load_accessories_db()
    
    if ref not in db:
        flash('Reference not found. Please search again.')
        return redirect(url_for('accessories_search'))
    
    data = db[ref]
    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref,
        buyer=data.get('buyer', 'N/A'),
        style=data.get('style', 'N/A'),
        colors=data.get('colors', []),
        challans=data.get('challans', [])
    )

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.form.get('ref', '').upper()
    item_type = request.form.get('item_type', 'Top')
    color = request.form.get('color', '')
    line_no = request.form.get('line_no', '')
    size = request.form.get('size', 'ALL')
    qty = request.form.get('qty', 0)
    
    db = load_accessories_db()
    
    if ref in db:
        challan_entry = {
            'type': item_type,
            'color': color,
            'line': line_no,
            'size': size,
            'qty': int(qty),
            'date': get_bd_date_str(),
            'time': get_bd_time().strftime('%I:%M %p'),
            'user': session.get('user', 'Unknown'),
            'status': '✓'
        }
        db[ref]['challans'].append(challan_entry)
        save_accessories_db(db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/edit')
def accessories_edit():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Admin access required.')
        return redirect(url_for('home'))
    
    ref = request.args.get('ref', '').upper()
    index = int(request.args.get('index', 0))
    
    db = load_accessories_db()
    
    if ref in db and 0 <= index < len(db[ref]['challans']):
        item = db[ref]['challans'][index]
        return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item)
    
    flash('Entry not found.')
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    ref = request.form.get('ref', '').upper()
    index = int(request.form.get('index', 0))
    
    db = load_accessories_db()
    
    if ref in db and 0 <= index < len(db[ref]['challans']):
        db[ref]['challans'][index]['line'] = request.form.get('line_no', '')
        db[ref]['challans'][index]['color'] = request.form.get('color', '')
        db[ref]['challans'][index]['size'] = request.form.get('size', 'ALL')
        db[ref]['challans'][index]['qty'] = int(request.form.get('qty', 0))
        db[ref]['challans'][index]['updated_by'] = session.get('user')
        db[ref]['challans'][index]['updated_at'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
        save_accessories_db(db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    ref = request.form.get('ref', '').upper()
    index = int(request.form.get('index', 0))
    
    db = load_accessories_db()
    
    if ref in db and 0 <= index < len(db[ref]['challans']):
        del db[ref]['challans'][index]
        save_accessories_db(db)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/print')
def accessories_print():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    ref = request.args.get('ref', '').upper()
    db = load_accessories_db()
    
    if ref not in db:
        flash('Reference not found.')
        return redirect(url_for('accessories_search'))
    
    data = db[ref]
    
    # Print Template তৈরি করা (Note: Here we can use f-string safely as it's a new variable)
    print_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Accessories Challan - {ref}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .info {{ margin-bottom: 20px; }}
            .info span {{ margin-right: 30px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #000; padding: 8px; text-align: center; }}
            th {{ background: #f0f0f0; }}
            .no-print {{ margin-bottom: 20px; }}
            @media print {{ .no-print {{ display: none; }} }}
        </style>
    </head>
    <body>
        <div class="no-print">
            <button onclick="window.print()">🖨️ Print</button>
            <button onclick="window.close()">Close</button>
        </div>
        
        <div class="header">
            <h1>ACCESSORIES DELIVERY CHALLAN</h1>
            <p>Reference: <strong>{ref}</strong></p>
        </div>
        
        <div class="info">
            <span><strong>Buyer:</strong> {data.get('buyer', 'N/A')}</span>
            <span><strong>Style:</strong> {data.get('style', 'N/A')}</span>
            <span><strong>Date:</strong> {get_bd_date_str()}</span>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>SL</th>
                    <th>Line</th>
                    <th>Type</th>
                    <th>Color</th>
                    <th>Size</th>
                    <th>Quantity</th>
                    <th>Date</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
    """
    
    total_qty = 0
    for i, challan in enumerate(data.get('challans', []), 1):
        total_qty += challan.get('qty', 0)
        print_html += f"""
            <tr>
                <td>{i}</td>
                <td>{challan.get('line', '')}</td>
                <td>{challan.get('type', '')}</td>
                <td>{challan.get('color', '')}</td>
                <td>{challan.get('size', '')}</td>
                <td>{challan.get('qty', 0)}</td>
                <td>{challan.get('date', '')}</td>
                <td>{challan.get('time', '')}</td>
            </tr>
        """
    
    print_html += f"""
            </tbody>
            <tfoot>
                <tr>
                    <th colspan="5">Total</th>
                    <th>{total_qty}</th>
                    <th colspan="2"></th>
                </tr>
            </tfoot>
        </table>
        
        <div style="margin-top: 60px; display: flex; justify-content: space-between;">
            <div style="text-align: center; width: 200px;">
                <div style="border-top: 1px solid #000; padding-top: 5px;">Prepared By</div>
            </div>
            <div style="text-align: center; width: 200px;">
                <div style="border-top: 1px solid #000; padding-top: 5px;">Received By</div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return print_html
    # ==============================================================================
# FLASK ROUTES - STORE PANEL (MAIN)
# ==============================================================================

@app.route('/store')
def store_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check store permission
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash('You do not have access to the Store Panel.')
        return redirect(url_for('home'))
    
    stats = get_store_dashboard_stats()
    today = get_bd_date_str()
    
    return render_template_string(STORE_DASHBOARD_TEMPLATE, stats=stats, today=today)

# ==============================================================================
# FLASK ROUTES - STORE CUSTOMERS
# ==============================================================================

@app.route('/store/customers')
def store_customers():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Get all customers with their due info
    customers = list(store_customers_col.find().sort("name", 1))
    
    # Calculate totals for each customer
    for cust in customers:
        cust_id = str(cust['_id'])
        # Get total purchase and due
        pipeline = [
            {"$match": {"customer_id": cust_id}},
            {"$group": {
                "_id": None,
                "total_purchase": {"$sum": "$grand_total"},
                "total_due": {"$sum": "$due_amount"}
            }}
        ]
        result = list(store_invoices_col.aggregate(pipeline))
        if result:
            cust['total_purchase'] = result[0]['total_purchase']
            cust['total_due'] = result[0]['total_due']
        else:
            cust['total_purchase'] = 0
            cust['total_due'] = 0
    
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)

@app.route('/store/customers/add', methods=['GET', 'POST'])
def store_customer_add():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        customer_data = {
            "name": request.form.get('name', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "email": request.form.get('email', '').strip(),
            "address": request.form.get('address', '').strip(),
            "notes": request.form.get('notes', '').strip(),
            "created_at": get_bd_time().isoformat(),
            "created_by": session.get('user')
        }
        
        store_customers_col.insert_one(customer_data)
        flash('Customer added successfully! ', 'success')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_CUSTOMER_ADD_TEMPLATE)

@app.route('/store/customers/edit/<customer_id>', methods=['GET', 'POST'])
def store_customer_edit(customer_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('store_customers'))
    
    if request.method == 'POST':
        update_data = {
            "name": request.form.get('name', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "email": request.form.get('email', '').strip(),
            "address": request.form.get('address', '').strip(),
            "notes": request.form.get('notes', '').strip(),
            "updated_at": get_bd_time().isoformat(),
            "updated_by": session.get('user')
        }
        
        store_customers_col.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": update_data}
        )
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_CUSTOMER_EDIT_TEMPLATE, customer=customer)

@app.route('/store/customers/view/<customer_id>')
def store_customer_view(customer_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    data = get_customer_details(customer_id)
    if not data:
        flash('Customer not found.', 'error')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_CUSTOMER_VIEW_TEMPLATE, data=data)

@app.route('/store/customers/delete/<customer_id>', methods=['POST'])
def store_customer_delete(customer_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Check if customer has invoices
    invoice_count = store_invoices_col.count_documents({"customer_id": customer_id})
    if invoice_count > 0:
        flash('Cannot delete customer with existing invoices.', 'error')
        return redirect(url_for('store_customers'))
    
    store_customers_col.delete_one({"_id": ObjectId(customer_id)})
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('store_customers'))

# ==============================================================================
# FLASK ROUTES - STORE PRODUCTS
# ==============================================================================

@app.route('/store/products')
def store_products():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    products = list(store_products_col.find().sort("name", 1))
    
    # Get unique categories
    categories = store_products_col.distinct("category")
    categories = [c for c in categories if c]
    
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products, categories=categories)

@app.route('/store/products/add', methods=['GET', 'POST'])
def store_product_add():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        product_data = {
            "name": request.form.get('name', '').strip(),
            "category": request.form.get('category', '').strip(),
            "unit": request.form.get('unit', 'Pcs'),
            "price": float(request.form.get('price', 0) or 0),
            "cost_price": float(request.form.get('cost_price', 0) or 0),
            "stock": int(request.form.get('stock', 0) or 0),
            "low_stock_alert": int(request.form.get('low_stock_alert', 10) or 10),
            "description": request.form.get('description', '').strip(),
            "created_at": get_bd_time().isoformat(),
            "created_by": session.get('user')
        }
        
        store_products_col.insert_one(product_data)
        flash('Product added successfully! ', 'success')
        return redirect(url_for('store_products'))
    
    return render_template_string(STORE_PRODUCT_ADD_TEMPLATE)

@app.route('/store/products/edit/<product_id>', methods=['GET', 'POST'])
def store_product_edit(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    product = store_products_col.find_one({"_id": ObjectId(product_id)})
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('store_products'))
    
    if request.method == 'POST':
        update_data = {
            "name": request.form.get('name', '').strip(),
            "category": request.form.get('category', '').strip(),
            "unit": request.form.get('unit', 'Pcs'),
            "price": float(request.form.get('price', 0) or 0),
            "cost_price": float(request.form.get('cost_price', 0) or 0),
            "stock": int(request.form.get('stock', 0) or 0),
            "low_stock_alert": int(request.form.get('low_stock_alert', 10) or 10),
            "description": request.form.get('description', '').strip(),
            "updated_at": get_bd_time().isoformat(),
            "updated_by": session.get('user')
        }
        
        store_products_col.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": update_data}
        )
        flash('Product updated successfully! ', 'success')
        return redirect(url_for('store_products'))
    
    return render_template_string(STORE_PRODUCT_EDIT_TEMPLATE, product=product)

@app.route('/store/products/delete/<product_id>', methods=['POST'])
def store_product_delete(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    store_products_col.delete_one({"_id": ObjectId(product_id)})
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('store_products'))

# ==============================================================================
# FLASK ROUTES - STORE INVOICES
# ==============================================================================

@app.route('/store/invoices')
def store_invoices():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoices = list(store_invoices_col.find().sort("created_at", -1))
    return render_template_string(STORE_INVOICES_TEMPLATE, invoices=invoices)

@app.route('/store/invoices/new', methods=['GET', 'POST'])
def store_invoice_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
        
        if not customer:
            flash('Customer not found.', 'error')
            return redirect(url_for('store_invoice_new'))
        
        items = json.loads(request.form.get('items_json', '[]'))
        
        invoice_data = {
            "invoice_number": request.form.get('invoice_number'),
            "customer_id": customer_id,
            "customer_name": customer['name'],
            "customer_phone": customer.get('phone', ''),
            "customer_address": customer.get('address', ''),
            "date": request.form.get('date'),
            "items": items,
            "subtotal": float(request.form.get('subtotal', 0)),
            "discount": float(request.form.get('discount', 0) or 0),
            "grand_total": float(request.form.get('grand_total', 0)),
            "paid_amount": float(request.form.get('paid_amount', 0) or 0),
            "due_amount": float(request.form.get('due_amount', 0)),
            "notes": request.form.get('notes', ''),
            "created_at": get_bd_time().isoformat(),
            "created_by": session.get('user')
        }
        
        result = store_invoices_col.insert_one(invoice_data)
        
        # Record initial payment if any
        if invoice_data['paid_amount'] > 0:
            payment_record = {
                "invoice_id": str(result.inserted_id),
                "invoice_number": invoice_data['invoice_number'],
                "customer_id": customer_id,
                "customer_name": customer['name'],
                "amount": invoice_data['paid_amount'],
                "method": "Cash",
                "date": get_bd_date_str(),
                "note": "Initial payment",
                "created_at": get_bd_time().isoformat(),
                "created_by": session.get('user')
            }
            store_payments_col.insert_one(payment_record)
        
        flash('Invoice created successfully!', 'success')
        return redirect(url_for('store_invoice_view', invoice_id=result.inserted_id))
    
    # GET request
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    
    # Convert ObjectId to string for JSON
    products_json = []
    for p in products:
        products_json.append({
            "_id": str(p['_id']),
            "name": p['name'],
            "price": p.get('price', 0),
            "unit": p.get('unit', 'Pcs')
        })
    
    invoice_number = generate_invoice_number()
    today = get_bd_time().strftime('%Y-%m-%d')
    selected_customer = request.args.get('customer', '')
    
    return render_template_string(
        STORE_INVOICE_NEW_TEMPLATE,
        customers=customers,
        products_json=json.dumps(products_json),
        invoice_number=invoice_number,
        today=today,
        selected_customer=selected_customer
    )

@app.route('/store/invoices/view/<invoice_id>')
def store_invoice_view(invoice_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoice = store_invoices_col.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('store_invoices'))
    
    # Get payment history
    payments = list(store_payments_col.find({"invoice_id": invoice_id}).sort("created_at", -1))
    
    return render_template_string(STORE_INVOICE_VIEW_TEMPLATE, invoice=invoice, payments=payments)

@app.route('/store/invoices/print/<invoice_id>')
def store_invoice_print(invoice_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoice = store_invoices_col.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('store_invoices'))
    
    settings = load_store_settings()
    today = get_bd_date_str()
    
    return render_template_string(STORE_INVOICE_PRINT_TEMPLATE, invoice=invoice, settings=settings, today=today)

@app.route('/store/invoices/edit/<invoice_id>', methods=['GET', 'POST'])
def store_invoice_edit(invoice_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoice = store_invoices_col.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('store_invoices'))
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
        
        items = json.loads(request.form.get('items_json', '[]'))
        new_grand_total = float(request.form.get('grand_total', 0))
        
        # Recalculate due based on already paid amount
        already_paid = invoice.get('paid_amount', 0)
        new_due = new_grand_total - already_paid
        
        update_data = {
            "customer_id": customer_id,
            "customer_name": customer['name'] if customer else invoice['customer_name'],
            "customer_phone": customer.get('phone', '') if customer else invoice.get('customer_phone', ''),
            "customer_address": customer.get('address', '') if customer else invoice.get('customer_address', ''),
            "date": request.form.get('date'),
            "items": items,
            "subtotal": float(request.form.get('subtotal', 0)),
            "discount": float(request.form.get('discount', 0) or 0),
            "grand_total": new_grand_total,
            "due_amount": max(0, new_due),
            "notes": request.form.get('notes', ''),
            "updated_at": get_bd_time().isoformat(),
            "updated_by": session.get('user')
        }
        
        store_invoices_col.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": update_data}
        )
        
        flash('Invoice updated successfully! ', 'success')
        return redirect(url_for('store_invoice_view', invoice_id=invoice_id))
    
    # GET request
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    
    products_json = []
    for p in products:
        products_json.append({
            "_id": str(p['_id']),
            "name": p['name'],
            "price": p.get('price', 0),
            "unit": p.get('unit', 'Pcs')
        })
    
    items_json = json.dumps(invoice.get('items', []))
    
    return render_template_string(
        STORE_INVOICE_EDIT_TEMPLATE,
        invoice=invoice,
        customers=customers,
        products_json=json.dumps(products_json),
        items_json=items_json
    )

@app.route('/store/invoices/pay/<invoice_id>', methods=['GET', 'POST'])
def store_invoice_pay(invoice_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    invoice = store_invoices_col.find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('store_invoices'))
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method = request.form.get('method', 'Cash')
        note = request.form.get('note', '')
        
        if amount <= 0:
            flash('Please enter a valid amount.', 'error')
            return redirect(url_for('store_invoice_pay', invoice_id=invoice_id))
        
        if amount > invoice['due_amount']:
            amount = invoice['due_amount']
        
        # Update invoice
        new_paid = invoice['paid_amount'] + amount
        new_due = invoice['grand_total'] - new_paid
        
        store_invoices_col.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": {
                "paid_amount": new_paid,
                "due_amount": max(0, new_due),
                "updated_at": get_bd_time().isoformat()
            }}
        )
        
        # Record payment
        payment_record = {
            "invoice_id": invoice_id,
            "invoice_number": invoice['invoice_number'],
            "customer_id": invoice['customer_id'],
            "customer_name": invoice['customer_name'],
            "amount": amount,
            "method": method,
            "date": get_bd_date_str(),
            "note": note,
            "created_at": get_bd_time().isoformat(),
            "created_by": session.get('user')
        }
        store_payments_col.insert_one(payment_record)
        
        flash(f'Payment of ৳{amount:,.2f} recorded successfully!', 'success')
        return redirect(url_for('store_invoice_view', invoice_id=invoice_id))
    
    return render_template_string(STORE_INVOICE_PAY_TEMPLATE, invoice=invoice)
    # ==============================================================================
# FLASK ROUTES - STORE QUOTATIONS
# ==============================================================================

@app.route('/store/quotations')
def store_quotations():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    quotations = list(store_quotations_col.find().sort("created_at", -1))
    return render_template_string(STORE_QUOTATIONS_TEMPLATE, quotations=quotations)

@app.route('/store/quotations/new', methods=['GET', 'POST'])
def store_quotation_new():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
        
        if not customer:
            flash('Customer not found.', 'error')
            return redirect(url_for('store_quotation_new'))
        
        items = json.loads(request.form.get('items_json', '[]'))
        
        quotation_data = {
            "quotation_number": request.form.get('quotation_number'),
            "customer_id": customer_id,
            "customer_name": customer['name'],
            "customer_phone": customer.get('phone', ''),
            "customer_address": customer.get('address', ''),
            "date": request.form.get('date'),
            "valid_until": request.form.get('valid_until', ''),
            "items": items,
            "subtotal": float(request.form.get('subtotal', 0)),
            "discount": float(request.form.get('discount', 0) or 0),
            "grand_total": float(request.form.get('grand_total', 0)),
            "notes": request.form.get('notes', ''),
            "status": "pending",
            "created_at": get_bd_time().isoformat(),
            "created_by": session.get('user')
        }
        
        result = store_quotations_col.insert_one(quotation_data)
        
        flash('Quotation created successfully!', 'success')
        return redirect(url_for('store_quotations'))
    
    # GET request
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    
    products_json = []
    for p in products:
        products_json.append({
            "_id": str(p['_id']),
            "name": p['name'],
            "price": p.get('price', 0),
            "unit": p.get('unit', 'Pcs')
        })
    
    quotation_number = generate_quotation_number()
    today = get_bd_time().strftime('%Y-%m-%d')
    
    # Valid until default: 7 days from today
    valid_until = (get_bd_time() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    return render_template_string(
        STORE_QUOTATION_NEW_TEMPLATE,
        customers=customers,
        products_json=json.dumps(products_json),
        quotation_number=quotation_number,
        today=today,
        valid_until=valid_until
    )

@app.route('/store/quotations/print/<quotation_id>')
def store_quotation_print(quotation_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    quotation = store_quotations_col.find_one({"_id": ObjectId(quotation_id)})
    if not quotation:
        flash('Quotation not found.', 'error')
        return redirect(url_for('store_quotations'))
    
    settings = load_store_settings()
    today = get_bd_date_str()
    
    return render_template_string(STORE_QUOTATION_PRINT_TEMPLATE, quotation=quotation, settings=settings, today=today)

@app.route('/store/quotations/convert/<quotation_id>')
def store_quotation_convert(quotation_id):
    """কোটেশনকে ইনভয়েসে রূপান্তর করে"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    quotation = store_quotations_col.find_one({"_id": ObjectId(quotation_id)})
    if not quotation:
        flash('Quotation not found.', 'error')
        return redirect(url_for('store_quotations'))
    
    if quotation.get('status') == 'converted':
        flash('This quotation has already been converted to an invoice.', 'error')
        return redirect(url_for('store_quotations'))
    
    # Create invoice from quotation
    invoice_number = generate_invoice_number()
    
    invoice_data = {
        "invoice_number": invoice_number,
        "customer_id": quotation['customer_id'],
        "customer_name": quotation['customer_name'],
        "customer_phone": quotation.get('customer_phone', ''),
        "customer_address": quotation.get('customer_address', ''),
        "date": get_bd_date_str(),
        "items": quotation['items'],
        "subtotal": quotation['subtotal'],
        "discount": quotation.get('discount', 0),
        "grand_total": quotation['grand_total'],
        "paid_amount": 0,
        "due_amount": quotation['grand_total'],
        "notes": f"Converted from {quotation['quotation_number']}. " + quotation.get('notes', ''),
        "from_quotation": quotation_id,
        "created_at": get_bd_time().isoformat(),
        "created_by": session.get('user')
    }
    
    result = store_invoices_col.insert_one(invoice_data)
    
    # Update quotation status
    store_quotations_col.update_one(
        {"_id": ObjectId(quotation_id)},
        {"$set": {
            "status": "converted",
            "converted_to": str(result.inserted_id),
            "converted_at": get_bd_time().isoformat()
        }}
    )
    
    flash(f'Quotation converted to Invoice #{invoice_number}! ', 'success')
    return redirect(url_for('store_invoice_view', invoice_id=result.inserted_id))

@app.route('/store/quotations/edit/<quotation_id>', methods=['GET', 'POST'])
def store_quotation_edit(quotation_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    quotation = store_quotations_col.find_one({"_id": ObjectId(quotation_id)})
    if not quotation:
        flash('Quotation not found.', 'error')
        return redirect(url_for('store_quotations'))
    
    if quotation.get('status') == 'converted':
        flash('Cannot edit a converted quotation.', 'error')
        return redirect(url_for('store_quotations'))
    
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
        
        items = json.loads(request.form.get('items_json', '[]'))
        
        update_data = {
            "customer_id": customer_id,
            "customer_name": customer['name'] if customer else quotation['customer_name'],
            "customer_phone": customer.get('phone', '') if customer else quotation.get('customer_phone', ''),
            "customer_address": customer.get('address', '') if customer else quotation.get('customer_address', ''),
            "date": request.form.get('date'),
            "valid_until": request.form.get('valid_until', ''),
            "items": items,
            "subtotal": float(request.form.get('subtotal', 0)),
            "discount": float(request.form.get('discount', 0) or 0),
            "grand_total": float(request.form.get('grand_total', 0)),
            "notes": request.form.get('notes', ''),
            "updated_at": get_bd_time().isoformat(),
            "updated_by": session.get('user')
        }
        
        store_quotations_col.update_one(
            {"_id": ObjectId(quotation_id)},
            {"$set": update_data}
        )
        
        flash('Quotation updated successfully! ', 'success')
        return redirect(url_for('store_quotations'))
    
    # GET - Render edit form (similar to new but with data)
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    
    products_json = []
    for p in products:
        products_json.append({
            "_id": str(p['_id']),
            "name": p['name'],
            "price": p.get('price', 0),
            "unit": p.get('unit', 'Pcs')
        })
    
    # Return edit template (using same structure as invoice edit)
    return render_template_string(STORE_QUOTATION_NEW_TEMPLATE.replace(
        'Create New Quotation', 'Edit Quotation'
    ).replace(
        'Save Quotation', 'Update Quotation'
    ), 
        customers=customers,
        products_json=json.dumps(products_json),
        quotation_number=quotation['quotation_number'],
        today=quotation.get('date', get_bd_time().strftime('%Y-%m-%d')),
        valid_until=quotation.get('valid_until', '')
    )

@app.route('/store/quotations/delete/<quotation_id>', methods=['POST'])
def store_quotation_delete(quotation_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    quotation = store_quotations_col.find_one({"_id": ObjectId(quotation_id)})
    if quotation and quotation.get('status') == 'converted':
        flash('Cannot delete a converted quotation.', 'error')
        return redirect(url_for('store_quotations'))
    
    store_quotations_col.delete_one({"_id": ObjectId(quotation_id)})
    flash('Quotation deleted successfully!', 'success')
    return redirect(url_for('store_quotations'))

# ==============================================================================
# FLASK ROUTES - STORE DUE COLLECTION
# ==============================================================================

@app.route('/store/dues')
def store_dues():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Get all customers with dues
    pipeline = [
        {"$match": {"due_amount": {"$gt": 0}}},
        {"$group": {
            "_id": "$customer_id",
            "customer_name": {"$first": "$customer_name"},
            "total_due": {"$sum": "$due_amount"},
            "invoice_count": {"$sum": 1},
            "invoices": {"$push": {
                "_id": "$_id",
                "invoice_number": "$invoice_number",
                "date": "$date",
                "grand_total": "$grand_total",
                "paid_amount": "$paid_amount",
                "due_amount": "$due_amount"
            }}
        }},
        {"$sort": {"total_due": -1}}
    ]
    
    due_customers = list(store_invoices_col.aggregate(pipeline))
    
    # Calculate total due
    total_due = sum(c['total_due'] for c in due_customers)
    
    # Get recent payments
    recent_payments = list(store_payments_col.find().sort("created_at", -1).limit(20))
    
    return render_template_string(
        STORE_DUES_TEMPLATE,
        due_customers=due_customers,
        total_due=total_due,
        recent_payments=recent_payments
    )

@app.route('/store/dues/collect/<customer_id>', methods=['GET', 'POST'])
def store_due_collect(customer_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    customer = store_customers_col.find_one({"_id": ObjectId(customer_id)})
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('store_dues'))
    
    # Get unpaid invoices for this customer
    unpaid_invoices = list(store_invoices_col.find({
        "customer_id": customer_id,
        "due_amount": {"$gt": 0}
    }).sort("date", 1))
    
    total_due = sum(inv['due_amount'] for inv in unpaid_invoices)
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        method = request.form.get('method', 'Cash')
        note = request.form.get('note', '')
        
        if amount <= 0:
            flash('Please enter a valid amount.', 'error')
            return redirect(url_for('store_due_collect', customer_id=customer_id))
        
        remaining_amount = amount
        
        # Apply payment to invoices (oldest first)
        for inv in unpaid_invoices:
            if remaining_amount <= 0:
                break
            
            invoice_due = inv['due_amount']
            payment_for_this = min(remaining_amount, invoice_due)
            
            new_paid = inv['paid_amount'] + payment_for_this
            new_due = inv['grand_total'] - new_paid
            
            store_invoices_col.update_one(
                {"_id": inv['_id']},
                {"$set": {
                    "paid_amount": new_paid,
                    "due_amount": max(0, new_due),
                    "updated_at": get_bd_time().isoformat()
                }}
            )
            
            # Record payment
            payment_record = {
                "invoice_id": str(inv['_id']),
                "invoice_number": inv['invoice_number'],
                "customer_id": customer_id,
                "customer_name": customer['name'],
                "amount": payment_for_this,
                "method": method,
                "date": get_bd_date_str(),
                "note": note,
                "created_at": get_bd_time().isoformat(),
                "created_by": session.get('user')
            }
            store_payments_col.insert_one(payment_record)
            
            remaining_amount -= payment_for_this
        
        flash(f'Payment of ৳{amount:,.2f} collected successfully!', 'success')
        return redirect(url_for('store_dues'))
    
    return render_template_string(
        STORE_DUE_COLLECT_TEMPLATE,
        customer=customer,
        unpaid_invoices=unpaid_invoices,
        total_due=total_due
    )

# ==============================================================================
# FLASK ROUTES - STORE SETTINGS & REPORTS
# ==============================================================================

@app.route('/store/settings', methods=['GET', 'POST'])
def store_settings():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('store_dashboard'))
    
    settings = load_store_settings()
    
    if request.method == 'POST':
        settings['store_name'] = request.form.get('store_name', settings['store_name'])
        settings['store_address'] = request.form.get('store_address', settings['store_address'])
        settings['store_phone'] = request.form.get('store_phone', settings['store_phone'])
        settings['store_email'] = request.form.get('store_email', settings['store_email'])
        settings['invoice_prefix'] = request.form.get('invoice_prefix', settings['invoice_prefix'])
        settings['quotation_prefix'] = request.form.get('quotation_prefix', settings['quotation_prefix'])
        
        save_store_settings(settings)
        flash('Settings updated successfully! ', 'success')
    
    # Return a simple settings page
    settings_html = f"""
    <!doctype html>
    <html><head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Store Settings</title>
        {COMMON_STYLES}
    </head>
    <body>
        <div class="animated-bg"></div>
        <div class="sidebar">
            <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
            <div class="nav-menu">
                <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Store Home</a>
                <a href="/store/settings" class="nav-link active"><i class="fas fa-cog"></i> Settings</a>
                <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
            </div>
        </div>
        <div class="main-content">
            <div class="header-section">
                <div><div class="page-title">Store Settings</div><div class="page-subtitle">Configure your store information</div></div>
            </div>
            <div class="card" style="max-width: 600px;">
                <form method="post">
                    <div class="input-group"><label>STORE NAME</label><input type="text" name="store_name" value="{settings['store_name']}"></div>
                    <div class="input-group"><label>ADDRESS</label><textarea name="store_address" rows="2">{settings['store_address']}</textarea></div>
                    <div class="grid-2">
                        <div class="input-group"><label>PHONE</label><input type="text" name="store_phone" value="{settings['store_phone']}"></div>
                        <div class="input-group"><label>EMAIL</label><input type="email" name="store_email" value="{settings['store_email']}"></div>
                    </div>
                    <div class="grid-2">
                        <div class="input-group"><label>INVOICE PREFIX</label><input type="text" name="invoice_prefix" value="{settings['invoice_prefix']}"></div>
                        <div class="input-group"><label>QUOTATION PREFIX</label><input type="text" name="quotation_prefix" value="{settings['quotation_prefix']}"></div>
                    </div>
                    <button type="submit"><i class="fas fa-save" style="margin-right: 8px;"></i> Save Settings</button>
                </form>
            </div>
        </div>
    </body></html>
    """
    return settings_html

@app.route('/store/reports')
def store_reports():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Basic reports page
    stats = get_store_dashboard_stats()
    
    reports_html = f"""
    <!doctype html>
    <html><head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Store Reports</title>
        {COMMON_STYLES}
    </head>
    <body>
        <div class="animated-bg"></div>
        <div class="sidebar">
            <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
            <div class="nav-menu">
                <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Store Home</a>
                <a href="/store/reports" class="nav-link active"><i class="fas fa-chart-line"></i> Reports</a>
                <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
            </div>
        </div>
        <div class="main-content">
            <div class="header-section">
                <div><div class="page-title">Reports & Analytics</div><div class="page-subtitle">Overview of your store performance</div></div>
            </div>
            
            <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr);">
                <div class="card stat-card">
                    <div class="stat-icon"><i class="fas fa-chart-line"></i></div>
                    <div class="stat-info">
                        <h3>৳{stats['total_sales']:,.0f}</h3>
                        <p>Total Sales</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));"><i class="fas fa-check-circle" style="color: var(--accent-green);"></i></div>
                    <div class="stat-info">
                        <h3>৳{stats['total_paid']:,.0f}</h3>
                        <p>Total Collected</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));"><i class="fas fa-exclamation-triangle" style="color: var(--accent-red);"></i></div>
                    <div class="stat-info">
                        <h3>৳{stats['total_due']:,.0f}</h3>
                        <p>Total Due</p>
                    </div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));"><i class="fas fa-file-invoice" style="color: var(--accent-purple);"></i></div>
                    <div class="stat-info">
                        <h3>{stats['total_invoices']}</h3>
                        <p>Total Invoices</p>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-info-circle" style="margin-right: 10px; color: var(--accent-orange);"></i>Summary</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
                    <div style="padding: 20px; background: rgba(255,255,255,0.02); border-radius: 12px; text-align: center;">
                        <div style="font-size: 32px; font-weight: 800; color: var(--accent-orange);">{stats['total_customers']}</div>
                        <div style="color: var(--text-secondary); margin-top: 5px;">Total Customers</div>
                    </div>
                    <div style="padding: 20px; background: rgba(255,255,255,0.02); border-radius: 12px; text-align: center;">
                        <div style="font-size: 32px; font-weight: 800; color: var(--accent-green);">{stats['total_products']}</div>
                        <div style="color: var(--text-secondary); margin-top: 5px;">Total Products</div>
                    </div>
                    <div style="padding: 20px; background: rgba(255,255,255,0.02); border-radius: 12px; text-align: center;">
                        <div style="font-size: 32px; font-weight: 800; color: var(--accent-blue);">{stats['today_invoices']}</div>
                        <div style="color: var(--text-secondary); margin-top: 5px;">Today's Invoices</div>
                    </div>
                </div>
            </div>
        </div>
    </body></html>
    """
    return reports_html

@app.route('/store/users')
def store_users():
    """স্টোর ইউজার ম্যানেজমেন্ট (Admin Only)"""
    if 'user' not in session or session.get('role') != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('store_dashboard'))
    
    users = load_users()
    
    # Filter users with store permission
    store_users = {k: v for k, v in users.items() if 'store' in v.get('permissions', [])}
    
    users_html = f"""
    <!doctype html>
    <html><head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Store Users</title>
        {COMMON_STYLES}
    </head>
    <body>
        <div class="animated-bg"></div>
        <div class="sidebar">
            <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
            <div class="nav-menu">
                <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Store Home</a>
                <a href="/store/users" class="nav-link active"><i class="fas fa-user-cog"></i> Store Users</a>
                <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
            </div>
        </div>
        <div class="main-content">
            <div class="header-section">
                <div><div class="page-title">Store Users</div><div class="page-subtitle">Manage users with store access</div></div>
                <a href="/"><button style="width: auto; padding: 12px 20px;"><i class="fas fa-user-plus" style="margin-right: 8px;"></i> Manage All Users</button></a>
            </div>
            
            <div class="card">
                <div class="section-header"><span>Users with Store Access</span></div>
                <table class="dark-table">
                    <thead><tr><th>Username</th><th>Role</th><th>Last Login</th><th>Permissions</th></tr></thead>
                    <tbody>
    """
    
    for username, data in store_users.items():
        perms = ', '.join(data.get('permissions', []))
        users_html += f"""
            <tr>
                <td style="font-weight: 600;">{username}</td>
                <td><span class="table-badge" style="background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);">{data.get('role', 'user')}</span></td>
                <td style="color: var(--text-secondary);">{data.get('last_login', 'Never')}</td>
                <td style="font-size: 12px; color: var(--text-secondary);">{perms}</td>
            </tr>
        """
    
    if not store_users:
        users_html += '<tr><td colspan="4" style="text-align: center; padding: 40px; color: var(--text-secondary);">No store users found. Add users from main dashboard.</td></tr>'
    
    users_html += """
                    </tbody>
                </table>
            </div>
            
            <div class="card" style="margin-top: 25px;">
                <div class="section-header"><span><i class="fas fa-info-circle" style="margin-right: 10px; color: var(--accent-blue);"></i>How to Add Store Users</span></div>
                <p style="color: var(--text-secondary); line-height: 1.8;">
                    1.Go to <strong>Main Dashboard</strong> → <strong>User Manage</strong><br>
                    2.Create a new user or edit existing user<br>
                    3.Check the <strong>"Store"</strong> permission checkbox<br>
                    4.Save the user<br><br>
                    <em>Users with only "Store" permission will be redirected directly to Store Panel on login.</em>
                </p>
            </div>
        </div>
    </body></html>
    """
    return users_html

# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@app.errorhandler(404)
def not_found(e):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>404 - Page Not Found</title>
        {COMMON_STYLES}
    </head>
    <body style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div class="card" style="text-align: center; max-width: 400px;">
            <div style="font-size: 80px; color: var(--accent-orange); margin-bottom: 20px;">404</div>
            <h2 style="color: white; margin-bottom: 10px;">Page Not Found</h2>
            <p style="color: var(--text-secondary); margin-bottom: 25px;">The page you're looking for doesn't exist.</p>
            <a href="/"><button><i class="fas fa-home" style="margin-right: 8px;"></i> Go Home</button></a>
        </div>
    </body>
    </html>
    """, 404

@app.errorhandler(500)
def server_error(e):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>500 - Server Error</title>
        {COMMON_STYLES}
    </head>
    <body style="display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div class="card" style="text-align: center; max-width: 400px;">
            <div style="font-size: 80px; color: var(--accent-red); margin-bottom: 20px;">500</div>
            <h2 style="color: white; margin-bottom: 10px;">Server Error</h2>
            <p style="color: var(--text-secondary); margin-bottom: 25px;">Something went wrong. Please try again.</p>
            <a href="/"><button style="background: var(--accent-red);"><i class="fas fa-redo" style="margin-right: 8px;"></i> Try Again</button></a>
        </div>
    </body>
    </html>
    """, 500

# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  MNM SOFTWARE - ERP & STORE MANAGEMENT SYSTEM")
    print("  Version: 2.0 (Full Store Panel)")
    print("  Developer: Mehedi Hasan")
    print("=" * 60)
    print("\n🚀 Starting server...")
    print("📍 Access URL: http://localhost:5000")
    print("🔐 Default Admin: Admin / @Nijhum@12")
    print("\n✨ Features Included:")
    print("   • Closing Report Generator")
    print("   • PO Sheet Generator")
    print("   • Accessories Challan")
    print("   • User Management")
    print("   • Full Store Panel:")
    print("      - Customer Management")
    print("      - Product Inventory")
    print("      - Invoice Generation")
    print("      - Quotation/Estimate")
    print("      - Due Collection")
    print("      - Payment Tracking")
    print("      - Professional Print")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
