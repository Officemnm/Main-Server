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
from bson.objectid import ObjectId

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
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) # কাজের সুবিধার জন্য ২ মিনিট থেকে বাড়িয়ে ৩০ মিনিট করা হলো, আপনি চাইলে কমাতে পারেন

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
# MongoDB কানেকশন সেটআপ (নতুন স্টোর কালেকশন সহ)
# ==============================================================================
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/?appName=Office"

try:
    client = MongoClient(MONGO_URI)
    db = client['office_db']
    
    # আগের কালেকশন
    users_col = db['users']
    stats_col = db['stats']
    accessories_col = db['accessories']
    
    # নতুন স্টোর প্যানেল কালেকশন
    store_products_col = db['store_products']
    store_customers_col = db['store_customers']
    store_invoices_col = db['store_invoices']
    store_payments_col = db['store_payments']
    
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
# MongoDB COLLECTIONS FOR STORE (NEW)
# ==============================================================================
# Note: client, db, users_col, stats_col, accessories_col are already defined in PART 1

products_col = db['store_products']
customers_col = db['store_customers']
invoices_col = db['store_invoices']

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
# NEW HELPER FUNCTIONS: STORE MODULE (ALUMINUM SHOP)
# ==============================================================================

def get_store_summary():
    total_products = products_col.count_documents({})
    total_customers = customers_col.count_documents({})
    
    # Calculate Financials
    total_sales = 0
    total_due = 0
    monthly_sales = 0
    
    now = get_bd_time()
    current_month = now.strftime('%Y-%m')
    
    invoices = invoices_col.find({"status": {"$ne": "deleted"}})
    
    for inv in invoices:
        if inv.get('type') == 'invoice': # Exclude quotations
            total_sales += float(inv.get('grand_total', 0))
            total_due += float(inv.get('due_amount', 0))
            
            # Monthly Sales
            inv_date = inv.get('date') # Format: YYYY-MM-DD
            if inv_date and inv_date.startswith(current_month):
                monthly_sales += float(inv.get('grand_total', 0))
            
    # Calculate Expenses (If we had an expense collection, for now using dummy or stored in stats)
    total_expense = 0 # Placeholder
    
    return {
        "total_products": total_products,
        "total_customers": total_customers,
        "total_sales": total_sales,
        "total_due": total_due,
        "monthly_sales": monthly_sales,
        "total_expense": total_expense,
        "recent_invoices": list(invoices_col.find({"type": "invoice", "status": {"$ne": "deleted"}}).sort("invoice_no", -1).limit(5))
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

    item_match = re.search(r"Garments?   Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
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
    # ... (Part 1 এর CSS এর ধারাবাহিকতা)
        .time-badge i {
            color: var(--accent-orange);
        }
        
        /* Store Specific Styles */
        .store-stat-card {
            background: linear-gradient(145deg, #1e1e2a, #16161f);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .store-table-row:hover {
            background: rgba(255, 255, 255, 0.02);
        }
        .badge-paid { background: rgba(16, 185, 129, 0.2); color: #34D399; padding: 4px 8px; border-radius: 4px; font-size: 11px; }
        .badge-due { background: rgba(239, 68, 68, 0.2); color: #F87171; padding: 4px 8px; border-radius: 4px; font-size: 11px; }
        .badge-partial { background: rgba(255, 122, 0, 0.2); color: #FF9A40; padding: 4px 8px; border-radius: 4px; font-size: 11px; }
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
            "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store_panel"],
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
    if 'downloads' not in data: data['downloads'] = []
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
# NEW: STORE MANAGEMENT HELPER FUNCTIONS (Aluminium Shop)
# ==============================================================================

def get_next_invoice_id():
    """Generates unique Invoice ID like INV-1001"""
    last_invoice = store_invoices_col.find_one(sort=[("invoice_id", -1)])
    if last_invoice and 'invoice_id' in last_invoice:
        try:
            last_num = int(last_invoice['invoice_id'].split('-')[1])
            return f"INV-{last_num + 1}"
        except:
            return "INV-1001"
    return "INV-1001"

def get_store_dashboard_summary():
    """Calculates totals for Store Dashboard"""
    products_count = store_products_col.count_documents({})
    customers_count = store_customers_col.count_documents({})
    
    # Calculate Sales and Due
    pipeline = [
        {"$group": {
            "_id": None,
            "total_sales": {"$sum": "$grand_total"},
            "total_paid": {"$sum": "$paid_amount"},
            "total_due": {"$sum": "$due_amount"}
        }}
    ]
    result = list(store_invoices_col.aggregate(pipeline))
    
    if result:
        stats = result[0]
        total_sales = stats.get('total_sales', 0)
        total_due = stats.get('total_due', 0)
    else:
        total_sales = 0
        total_due = 0
        
    # Today's Sales
    today_str = get_bd_date_str()
    today_sales = store_invoices_col.count_documents({"date": today_str})
    
    return {
        "products": products_count,
        "customers": customers_count,
        "total_sales": total_sales,
        "total_due": total_due,
        "today_sales_count": today_sales
    }

# ==============================================================================
# আপডেটেড: রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স (Main Admin)
# ==============================================================================
def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    # Store Stats ইন্টিগ্রেশন
    store_stats = get_store_dashboard_summary()
    
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

    # 3. Closing & PO
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
        
    # Chart Data Preparation
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
        chart_closing = [0]; chart_po = [0]; chart_acc = [0]
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
        "store": store_stats, # Added Store Stats
        "chart": {
            "labels": chart_labels,
            "closing": chart_closing,
            "po": chart_po,
            "acc": chart_acc
        },
        "history": history
    }
    # ==============================================================================
# HTML TEMPLATES: LOGIN PAGE
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
        html, body {{ height: 100%; margin: 0; padding: 0; overflow-x: hidden; }}
        body {{ background: var(--bg-body); min-height: 100vh; display: flex; justify-content: center; align-items: center; position: relative; overflow-y: auto; }}
        .login-container {{ position: relative; z-index: 10; width: 100%; max-width: 420px; padding: 20px; margin: auto; display: flex; flex-direction: column; justify-content: center; min-height: 100vh; }}
        .login-card {{ background: var(--gradient-card); border: 1px solid var(--border-color); border-radius: 24px; padding: 40px 35px; backdrop-filter: blur(20px); box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow); }}
        .brand-section {{ text-align: center; margin-bottom: 35px; }}
        .brand-icon {{ width: 70px; height: 70px; background: var(--gradient-orange); border-radius: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 32px; color: white; margin-bottom: 18px; box-shadow: 0 15px 40px var(--accent-orange-glow); }}
        .brand-name {{ font-size: 28px; font-weight: 900; color: white; letter-spacing: -1px; }}
        .brand-name span {{ background: var(--gradient-orange); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .login-btn {{ margin-top: 8px; padding: 14px 24px; font-size: 15px; border-radius: 12px; display: flex; align-items: center; justify-content: center; gap: 10px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="brand-section">
                <div class="brand-icon"><i class="fas fa-layer-group"></i></div>
                <div class="brand-name">MNM<span>Software</span></div>
                <div style="color:#8b8b9e; font-size:11px; letter-spacing:2px; margin-top:6px; font-weight:600;">SECURE ACCESS PORTAL</div>
            </div>
            <form action="/login" method="post">
                <div class="input-group"><label><i class="fas fa-user"></i> USERNAME</label><input type="text" name="username" required placeholder="Enter ID"></div>
                <div class="input-group"><label><i class="fas fa-lock"></i> PASSWORD</label><input type="password" name="password" required placeholder="Enter Password"></div>
                <button type="submit" class="login-btn">Sign In <i class="fas fa-arrow-right"></i></button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div style="margin-top:20px; padding:10px; background:rgba(239,68,68,0.1); color:#F87171; border-radius:8px; font-size:13px; text-align:center;">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ADMIN DASHBOARD TEMPLATE (UPDATED WITH STORE LINK)
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
    <div class="animated-bg"></div>
    <div id="loading-overlay">
        <div class="spinner-container"><div class="spinner"></div></div>
        <div class="loading-text">Processing...</div>
    </div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="showSection('dashboard', this)"><i class="fas fa-home"></i> Dashboard</div>
            
            <!-- NEW STORE LINK -->
            <a href="/store" class="nav-link" style="color: var(--accent-cyan);"><i class="fas fa-store"></i> Store Panel</a>
            
            <div class="nav-link" onclick="showSection('analytics', this)"><i class="fas fa-chart-pie"></i> Closing Report</div>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-database"></i> Accessories</a>
            <div class="nav-link" onclick="showSection('help', this)"><i class="fas fa-file-invoice"></i> PO Generator</div>
            <div class="nav-link" onclick="showSection('settings', this)"><i class="fas fa-users-cog"></i> Users</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div id="section-dashboard">
            <div class="header-section">
                <div><div class="page-title">Admin Dashboard</div></div>
                <div class="status-badge"><span>System Online</span></div>
            </div>
            
            <div class="stats-grid">
                <div class="card stat-card">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info"><h3 class="count-up" data-target="{{{{ stats.closing.count }}}}">0</h3><p>Closing</p></div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="color:var(--accent-purple);"><i class="fas fa-boxes"></i></div>
                    <div class="stat-info"><h3 class="count-up" data-target="{{{{ stats.accessories.count }}}}">0</h3><p>Accessories</p></div>
                </div>
                <div class="card stat-card">
                    <div class="stat-icon" style="color:var(--accent-cyan);"><i class="fas fa-store"></i></div>
                    <div class="stat-info"><h3 class="count-up" data-target="{{{{ stats.store.today_sales_count }}}}">0</h3><p>Today's Sales</p></div>
                </div>
            </div>

            <div class="card">
                <div class="section-header"><span>Daily Activity</span></div>
                <div class="chart-container" style="height: 300px;"><canvas id="mainChart"></canvas></div>
            </div>
        </div>

        <!-- Analytics Section -->
        <div id="section-analytics" style="display:none;">
            <div class="header-section"><div><div class="page-title">Closing Report</div></div></div>
            <div class="card" style="max-width:500px; margin:auto;">
                <h3>Generate Report</h3>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><label>REF NO</label><input type="text" name="ref_no" required></div>
                    <button type="submit">Generate</button>
                </form>
            </div>
        </div>

        <!-- Help Section -->
        <div id="section-help" style="display:none;">
             <div class="header-section"><div><div class="page-title">PO Generator</div></div></div>
             <div class="card" style="max-width:500px; margin:auto;">
                <h3>Upload PDF</h3>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="upload-zone" onclick="document.getElementById('fu').click()">
                        <input type="file" id="fu" name="pdf_files" multiple accept=".pdf" style="display:none;">
                        <i class="fas fa-cloud-upload-alt" style="font-size:40px; color:var(--accent-orange);"></i>
                        <p>Click to Upload</p>
                        <div id="fc"></div>
                    </div>
                    <button type="submit" style="margin-top:20px;">Process</button>
                </form>
             </div>
        </div>

        <!-- Settings Section -->
        <div id="section-settings" style="display:none;">
            <div class="header-section"><div><div class="page-title">User Management</div></div></div>
            <div class="dashboard-grid-2">
                <div class="card">
                    <h3>Users</h3>
                    <div id="userTable"></div>
                </div>
                <div class="card">
                    <h3>Add/Edit User</h3>
                    <form id="userForm">
                        <input type="hidden" id="action_type" value="create">
                        <div class="input-group"><label>User</label><input type="text" id="u_name"></div>
                        <div class="input-group"><label>Pass</label><input type="text" id="u_pass"></div>
                        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;">
                            <label class="perm-checkbox"><input type="checkbox" id="p_close"> Closing</label>
                            <label class="perm-checkbox"><input type="checkbox" id="p_acc"> Access.</label>
                            <label class="perm-checkbox"><input type="checkbox" id="p_po"> PO</label>
                            <label class="perm-checkbox"><input type="checkbox" id="p_store"> Store</label>
                        </div>
                        <button type="button" onclick="saveUser()">Save</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <script>
        // Navigation
        function showSection(id, el) {{
            document.querySelectorAll('.main-content > div').forEach(d=>d.style.display='none');
            document.getElementById('section-'+id).style.display='block';
            document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
            if(el) el.classList.add('active');
            if(id==='settings') loadUsers();
        }}
        
        // Chart
        const ctx = document.getElementById('mainChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {{{{ stats.chart.labels | tojson }}}},
                datasets: [
                    {{ label: 'Closing', data: {{{{ stats.chart.closing | tojson }}}}, borderColor: '#FF7A00', tension:0.4 }},
                    {{ label: 'Store', data: {{{{ stats.chart.acc | tojson }}}}, borderColor: '#06B6D4', tension:0.4 }}
                ]
            }},
            options: {{ responsive:true, maintainAspectRatio:false }}
        }});
        
        // Count Up
        setTimeout(() => {{
            document.querySelectorAll('.count-up').forEach(c => {{
                let target = +c.getAttribute('data-target');
                c.innerText = target; 
            }});
        }}, 500);

        // User Management
        function loadUsers() {{
            fetch('/admin/get-users').then(r=>r.json()).then(d=>{{
                let h='<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th>Act</th></tr></thead><tbody>';
                for(let u in d) h+=`<tr><td>${{u}}</td><td>${{d[u].role}}</td><td><button onclick="delUser('${{u}}')" class="btn-del">X</button></td></tr>`;
                document.getElementById('userTable').innerHTML=h+'</tbody></table>';
            }});
        }}
        function saveUser() {{
            let perms = [];
            if(document.getElementById('p_close').checked) perms.push('closing');
            if(document.getElementById('p_acc').checked) perms.push('accessories');
            if(document.getElementById('p_po').checked) perms.push('po_sheet');
            if(document.getElementById('p_store').checked) perms.push('store_panel');
            
            fetch('/admin/save-user', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{
                    username: document.getElementById('u_name').value,
                    password: document.getElementById('u_pass').value,
                    action_type: document.getElementById('action_type').value,
                    permissions: perms
                }})
            }}).then(r=>r.json()).then(d=>{{ alert(d.message); loadUsers(); }});
        }}
        function delUser(u) {{ if(confirm('Delete?')) fetch('/admin/delete-user', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{username:u}})}}).then(loadUsers); }}
        
        // File Upload
        document.getElementById('fu').onchange = function() {{ document.getElementById('fc').innerText = this.files.length + ' Files'; }}
    </script>
</body>
</html>
"""

# ==============================================================================
# USER DASHBOARD TEMPLATE
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
    <div class="animated-bg"></div>
    <div id="loading-overlay"><div class="spinner-container"><div class="spinner"></div></div><div class="loading-text">Processing...</div></div>
    
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            <div class="nav-link active"><i class="fas fa-home"></i> Home</div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: auto;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>
    
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Welcome, {{{{ session.user }}}}!</div></div>
        </div>

        <div class="stats-grid">
            {{% if 'store_panel' in session.permissions %}}
            <div class="card" style="border: 1px solid var(--accent-cyan);">
                <div class="section-header"><span><i class="fas fa-store" style="color:var(--accent-cyan);"></i> Store Panel</span></div>
                <p style="color:#888; margin-bottom:15px;">Manage Aluminium Shop</p>
                <a href="/store"><button style="background: linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%);">Open Store</button></a>
            </div>
            {{% endif %}}

            {{% if 'closing' in session.permissions %}}
            <div class="card">
                <div class="section-header"><span><i class="fas fa-file-export"></i> Closing Report</span></div>
                <form action="/generate-report" method="post" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><input type="text" name="ref_no" placeholder="Booking Ref" required></div>
                    <button type="submit">Generate</button>
                </form>
            </div>
            {{% endif %}}
            
            {{% if 'po_sheet' in session.permissions %}}
            <div class="card">
                <div class="section-header"><span><i class="fas fa-file-pdf"></i> PO Sheet</span></div>
                <form action="/generate-po-report" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('loading-overlay').style.display='flex'">
                    <div class="input-group"><input type="file" name="pdf_files" multiple accept=".pdf" required></div>
                    <button type="submit">Process Files</button>
                </form>
            </div>
            {{% endif %}}
            
            {{% if 'accessories' in session.permissions %}}
            <div class="card">
                <div class="section-header"><span><i class="fas fa-boxes"></i> Accessories</span></div>
                <a href="/admin/accessories"><button>Open Dashboard</button></a>
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
    <title>Accessories Search</title>
    {COMMON_STYLES}
    <style>body {{ justify-content: center; align-items: center; }}</style>
</head>
<body>
    <div class="card" style="width:100%; max-width:450px; padding:40px;">
        <div style="text-align:center; margin-bottom:30px;">
            <i class="fas fa-boxes" style="font-size:40px; color:var(--accent-purple); margin-bottom:10px;"></i>
            <h2>Accessories Challan</h2>
        </div>
        <form action="/admin/accessories/input" method="post">
            <div class="input-group"><label>BOOKING REF</label><input type="text" name="ref_no" required></div>
            <button type="submit">Proceed</button>
        </form>
        <a href="/" style="display:block; text-align:center; margin-top:20px; color:#888; text-decoration:none;">Back to Dashboard</a>
    </div>
</body>
</html>
"""

ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Accessories Entry</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="sidebar">
        <div class="brand-logo">Accessories</div>
        <div class="nav-menu">
            <a href="/" class="nav-link"><i class="fas fa-home"></i> Home</a>
            <a href="/admin/accessories" class="nav-link"><i class="fas fa-search"></i> Search</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Entry: {{{{ ref }}}}</div><div class="page-subtitle">{{{{ buyer }}}} - {{{{ style }}}}</div></div>
            <a href="/admin/accessories/print?ref={{{{ ref }}}}" target="_blank"><button style="width:auto;">Print Report</button></a>
        </div>
        <div class="dashboard-grid-2">
            <div class="card">
                <h3>New Entry</h3>
                <form action="/admin/accessories/save" method="post">
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    <div class="input-group"><label>Type</label><select name="item_type"><option>Top</option><option>Bottom</option></select></div>
                    <div class="input-group"><label>Color</label><select name="color">{{% for c in colors %}}<option>{{{{ c }}}}</option>{{% endfor %}}</select></div>
                    <div class="input-group"><label>Line</label><input type="text" name="line_no" required></div>
                    <div class="input-group"><label>Size</label><input type="text" name="size" value="ALL"></div>
                    <div class="input-group"><label>Qty</label><input type="number" name="qty" required></div>
                    <button type="submit">Save</button>
                </form>
            </div>
            <div class="card">
                <h3>History</h3>
                <div style="max-height:400px; overflow-y:auto;">
                    {{% for item in challans|reverse %}}
                    <div style="display:flex; justify-content:space-between; padding:10px; border-bottom:1px solid #333;">
                        <span>{{{{ item.line }}}}</span><span>{{{{ item.color }}}}</span><span>{{{{ item.qty }}}}</span>
                        <a href="/admin/accessories/edit?ref={{{{ ref }}}}&index={{{{ (challans|length) - loop.index }}}}" style="color:var(--accent-orange);">Edit</a>
                    </div>
                    {{% endfor %}}
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Edit Entry</title>
    {COMMON_STYLES}
    <style>body {{ justify-content: center; align-items: center; }}</style>
</head>
<body>
    <div class="card" style="width:100%; max-width:400px;">
        <h3>Edit Entry</h3>
        <form action="/admin/accessories/update" method="post">
            <input type="hidden" name="ref" value="{{{{ ref }}}}">
            <input type="hidden" name="index" value="{{{{ index }}}}">
            <div class="input-group"><label>Line</label><input type="text" name="line_no" value="{{{{ item.line }}}}"></div>
            <div class="input-group"><label>Color</label><input type="text" name="color" value="{{{{ item.color }}}}"></div>
            <div class="input-group"><label>Size</label><input type="text" name="size" value="{{{{ item.size }}}}"></div>
            <div class="input-group"><label>Qty</label><input type="number" name="qty" value="{{{{ item.qty }}}}"></div>
            <button type="submit">Update</button>
        </form>
        <form action="/admin/accessories/delete" method="post" style="margin-top:10px;">
            <input type="hidden" name="ref" value="{{{{ ref }}}}">
            <input type="hidden" name="index" value="{{{{ index }}}}">
            <button type="submit" style="background:var(--accent-red);">Delete</button>
        </form>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE DASHBOARD TEMPLATE (COMPREHENSIVE - POS, PRODUCTS, CUSTOMERS)
# ==============================================================================

STORE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Panel - Aluminium Shop</title>
    {COMMON_STYLES}
    <style>
        /* Store Specific CSS */
        .store-card {{ background: var(--bg-card); border: 1px solid var(--border-color); padding: 20px; border-radius: 16px; transition: 0.3s; }}
        .store-card:hover {{ border-color: var(--accent-cyan); transform: translateY(-5px); box-shadow: 0 10px 30px rgba(6, 182, 212, 0.15); }}
        
        .product-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; max-height: 600px; overflow-y: auto; padding-right: 5px; }}
        .product-item {{ background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; transition: 0.2s; position: relative; overflow: hidden; }}
        .product-item:hover {{ background: rgba(6, 182, 212, 0.1); border-color: var(--accent-cyan); }}
        .product-item::before {{ content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 4px; background: var(--accent-cyan); opacity: 0; transition: 0.3s; }}
        .product-item:hover::before {{ opacity: 1; }}
        
        .cart-items {{ flex-grow: 1; overflow-y: auto; margin: 20px 0; max-height: 300px; padding-right: 5px; }}
        .cart-item {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid var(--accent-orange); }}
        
        .invoice-table th, .invoice-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        
        .flex-between {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        
        /* Tab Navigation */
        .nav-link.active {{ background: rgba(6, 182, 212, 0.15); border-left-color: var(--accent-cyan); color: var(--accent-cyan); }}
        
        /* Floating Input Label */
        .floating-label {{ position: relative; margin-bottom: 15px; }}
        .floating-label input {{ padding: 12px; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Alu<span>Shop</span></div>
        <div class="nav-menu">
            <div class="nav-link active" onclick="switchTab('dashboard', this)"><i class="fas fa-th-large"></i> Dashboard</div>
            <div class="nav-link" onclick="switchTab('pos', this)"><i class="fas fa-cash-register"></i> New Sale (POS)</div>
            <div class="nav-link" onclick="switchTab('products', this)"><i class="fas fa-box"></i> Products</div>
            <div class="nav-link" onclick="switchTab('customers', this)"><i class="fas fa-users"></i> Customers</div>
            <div class="nav-link" onclick="switchTab('invoices', this)"><i class="fas fa-file-invoice"></i> Invoices & Due</div>
            <a href="/" class="nav-link" style="margin-top: auto; color: var(--accent-orange);"><i class="fas fa-arrow-left"></i> Back to Main</a>
        </div>
    </div>

    <div class="main-content">
        <!-- DASHBOARD TAB -->
        <div id="tab-dashboard">
            <div class="header-section">
                <div class="page-title">Store Overview</div>
                <button class="status-badge" onclick="switchTab('pos')"><i class="fas fa-plus" style="margin-right:8px;"></i> New Sale</button>
            </div>
            <div class="stats-grid">
                <div class="store-card">
                    <div class="stat-icon" style="color: var(--accent-green); background: rgba(16, 185, 129, 0.1);"><i class="fas fa-coins"></i></div>
                    <h3 style="margin-top:15px;">৳ {{{{ store_stats.total_sales }}}}</h3>
                    <p style="color: var(--text-secondary);">Total Sales</p>
                </div>
                <div class="store-card" style="border-color: var(--accent-red);">
                    <div class="stat-icon" style="color: var(--accent-red); background: rgba(239, 68, 68, 0.1);"><i class="fas fa-hand-holding-usd"></i></div>
                    <h3 style="margin-top:15px;">৳ {{{{ store_stats.total_due }}}}</h3>
                    <p style="color: var(--text-secondary);">Total Due</p>
                </div>
                <div class="store-card">
                    <div class="stat-icon" style="color: var(--accent-cyan); background: rgba(6, 182, 212, 0.1);"><i class="fas fa-receipt"></i></div>
                    <h3 style="margin-top:15px;">{{{{ store_stats.today_sales_count }}}}</h3>
                    <p style="color: var(--text-secondary);">Today's Invoices</p>
                </div>
                <div class="store-card">
                    <div class="stat-icon" style="color: var(--accent-purple); background: rgba(139, 92, 246, 0.1);"><i class="fas fa-cubes"></i></div>
                    <h3 style="margin-top:15px;">{{{{ store_stats.products }}}}</h3>
                    <p style="color: var(--text-secondary);">Total Products</p>
                </div>
            </div>
        </div>

        <!-- POS / NEW SALE TAB -->
        <div id="tab-pos" style="display:none;">
            <div class="header-section"><div class="page-title">New Sale / Quotation</div></div>
            <div class="dashboard-grid-2">
                <!-- Product Selection Area -->
                <div class="card">
                    <input type="text" id="prodSearch" placeholder="🔍 Search Product..." onkeyup="filterProducts()" style="margin-bottom: 15px; border-radius: 50px;">
                    <div class="product-grid" id="posProductGrid">
                        <!-- Products will load here via JS -->
                        <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #666;">
                            <i class="fas fa-spinner fa-spin fa-2x"></i><br>Loading Products...
                        </div>
                    </div>
                </div>
                
                <!-- Cart & Checkout Area -->
                <div class="card">
                    <h3><i class="fas fa-shopping-cart" style="color: var(--accent-orange);"></i> Current Cart</h3>
                    <div id="cartItems" class="cart-items">
                        <p style="color:#666; text-align:center; padding-top: 50px;">Cart is Empty</p>
                    </div>
                    
                    <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px;">
                        <div class="flex-between"><span>Subtotal:</span> <span id="cartSubtotal" style="font-weight:bold;">0</span></div>
                        <div class="flex-between">
                            <span>Discount:</span> 
                            <input type="number" id="cartDiscount" value="0" style="width: 100px; padding: 5px; text-align: right;" onchange="calcTotal()">
                        </div>
                        <div class="flex-between" style="font-size: 18px; color: var(--accent-green);">
                            <h3>Total:</h3> <h3 id="cartTotal">0</h3>
                        </div>
                    </div>
                    <br>
                    <label style="font-size: 12px; color: #888;">SELECT CUSTOMER</label>
                    <select id="posCustomer" style="margin-bottom: 15px;">
                        <option value="Walking Customer">Walking Customer</option>
                        <!-- Customers loaded via JS -->
                    </select>
                    
                    <div class="input-group">
                        <label style="font-size: 12px; color: #888;">PAID AMOUNT</label>
                        <input type="number" id="posPaid" value="0" style="font-size: 18px; color: var(--accent-green); font-weight: bold;">
                    </div>
                    
                    <div style="display:flex; gap:10px; margin-top:15px;">
                        <button onclick="processSale('invoice')" style="background: var(--accent-green); flex: 1;">
                            <i class="fas fa-check"></i> Create Invoice
                        </button>
                        <button onclick="processSale('quotation')" style="background: var(--accent-purple); flex: 1;">
                            <i class="fas fa-file-alt"></i> Quotation
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- PRODUCTS TAB -->
        <div id="tab-products" style="display:none;">
            <div class="header-section">
                <div class="page-title">Product Management</div>
                <button onclick="openProductModal()" style="width:auto;"><i class="fas fa-plus"></i> Add Product</button>
            </div>
            <div class="card">
                <table class="dark-table">
                    <thead><tr><th>Name</th><th>Price</th><th>Stock</th><th>Action</th></tr></thead>
                    <tbody id="productListBody">
                        <tr><td colspan="4" style="text-align:center;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- CUSTOMERS TAB -->
        <div id="tab-customers" style="display:none;">
             <div class="header-section">
                <div class="page-title">Customer List</div>
                <button onclick="openCustomerModal()" style="width:auto;"><i class="fas fa-user-plus"></i> Add Customer</button>
            </div>
             <div class="card">
                <table class="dark-table">
                    <thead><tr><th>Name</th><th>Phone</th><th>Due</th><th>History</th></tr></thead>
                    <tbody id="customerListBody">
                        <tr><td colspan="4" style="text-align:center;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- INVOICES TAB -->
        <div id="tab-invoices" style="display:none;">
             <div class="header-section"><div class="page-title">Invoices & Due Collection</div></div>
             <div class="card">
                <table class="dark-table">
                    <thead><tr><th>Inv ID</th><th>Date</th><th>Customer</th><th>Total</th><th>Paid</th><th>Due</th><th>Action</th></tr></thead>
                    <tbody id="invoiceListBody">
                        <tr><td colspan="7" style="text-align:center;">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- MODALS (Hidden by default) -->
    <!-- Product Modal -->
    <div id="productModal" class="welcome-modal">
        <div class="welcome-content" style="text-align:left;">
            <h3 style="margin-bottom: 20px;">Add/Edit Product</h3>
            <form id="productForm">
                <input type="hidden" id="prodId">
                <div class="input-group"><label>Product Name</label><input type="text" id="prodName" required></div>
                <div class="input-group"><label>Price (Per Unit)</label><input type="number" id="prodPrice" required></div>
                <div class="input-group"><label>Stock Quantity</label><input type="number" id="prodStock" value="100"></div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="button" onclick="saveProduct()">Save Product</button>
                    <button type="button" onclick="closeModal('productModal')" style="background:#333;">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Customer Modal -->
    <div id="customerModal" class="welcome-modal">
        <div class="welcome-content" style="text-align:left;">
            <h3 style="margin-bottom: 20px;">Add Customer</h3>
            <form id="customerForm">
                <div class="input-group"><label>Full Name</label><input type="text" id="custName" required></div>
                <div class="input-group"><label>Phone Number</label><input type="text" id="custPhone"></div>
                <div class="input-group"><label>Address</label><input type="text" id="custAddress"></div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="button" onclick="saveCustomer()">Save Customer</button>
                    <button type="button" onclick="closeModal('customerModal')" style="background:#333;">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        // --- GLOBAL DATA ---
        let cart = [];
        
        // --- TABS ---
        function switchTab(tabId, el) {{
            document.querySelectorAll('.main-content > div').forEach(d => d.style.display = 'none');
            document.getElementById('tab-' + tabId).style.display = 'block';
            if(el) {{
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                el.classList.add('active');
            }}
            
            // Lazy Load Data
            if(tabId === 'products' || tabId === 'pos') loadProducts();
            if(tabId === 'customers' || tabId === 'pos') loadCustomers();
            if(tabId === 'invoices') loadInvoices();
        }}

        // --- PRODUCT FUNCTIONS ---
        function loadProducts() {{
            fetch('/store/api/products').then(r=>r.json()).then(data => {{
                let html = '';
                let posHtml = '';
                if(data.length === 0) {{
                     html = '<tr><td colspan="4" style="text-align:center; color:#888;">No products found</td></tr>';
                     posHtml = '<div style="grid-column:1/-1; text-align:center; color:#888;">No Products Added Yet</div>';
                }} else {{
                    data.forEach(p => {{
                        html += `<tr>
                            <td style="font-weight:500;">${{p.name}}</td>
                            <td>৳ ${{p.price}}</td>
                            <td><span class="table-badge" style="background:rgba(255,255,255,0.05);">${{p.stock}}</span></td>
                            <td><button class="action-btn btn-edit" onclick="editProduct('${{p._id}}', '${{p.name}}', ${{p.price}}, ${{p.stock}})">Edit</button></td>
                        </tr>`;
                        
                        posHtml += `<div class="product-item" onclick="addToCart('${{p._id}}', '${{p.name}}', ${{p.price}})">
                            <div style="font-size: 14px; font-weight:600; margin-bottom:5px;">${{p.name}}</div>
                            <div style="color:var(--accent-cyan); font-size:13px;">৳ ${{p.price}}</div>
                        </div>`;
                    }});
                }}
                document.getElementById('productListBody').innerHTML = html;
                document.getElementById('posProductGrid').innerHTML = posHtml;
            }});
        }}
        
        function openProductModal() {{ document.getElementById('productModal').style.display = 'flex'; document.getElementById('productForm').reset(); document.getElementById('prodId').value = ''; }}
        function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
        
        function saveProduct() {{
            let id = document.getElementById('prodId').value;
            let data = {{
                id: id,
                name: document.getElementById('prodName').value,
                price: document.getElementById('prodPrice').value,
                stock: document.getElementById('prodStock').value
            }};
            fetch('/store/api/product/save', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}})
            .then(r=>r.json()).then(res => {{ closeModal('productModal'); loadProducts(); }});
        }}
        
        function editProduct(id, name, price, stock) {{
            openProductModal();
            document.getElementById('prodId').value = id;
            document.getElementById('prodName').value = name;
            document.getElementById('prodPrice').value = price;
            document.getElementById('prodStock').value = stock;
        }}

        // --- CUSTOMER FUNCTIONS ---
        function loadCustomers() {{
            fetch('/store/api/customers').then(r=>r.json()).then(data => {{
                let html = '';
                let options = '<option value="Walking Customer">Walking Customer</option>';
                if(data.length === 0) html = '<tr><td colspan="4" style="text-align:center; color:#888;">No customers found</td></tr>';
                else {{
                    data.forEach(c => {{
                        let dueColor = c.total_due > 0 ? '#EF4444' : '#10B981';
                        html += `<tr>
                            <td style="font-weight:500;">${{c.name}}</td>
                            <td>${{c.phone}}</td>
                            <td style="color:${{dueColor}}; font-weight:bold;">৳ ${{c.total_due}}</td>
                            <td><span style="font-size:12px; opacity:0.5;">Coming Soon</span></td>
                        </tr>`;
                        options += `<option value="${{c.name}}">${{c.name}}</option>`;
                    }});
                }}
                document.getElementById('customerListBody').innerHTML = html;
                document.getElementById('posCustomer').innerHTML = options;
            }});
        }}
        
        function openCustomerModal() {{ document.getElementById('customerModal').style.display = 'flex'; document.getElementById('customerForm').reset(); }}
        
        function saveCustomer() {{
            let data = {{
                name: document.getElementById('custName').value,
                phone: document.getElementById('custPhone').value,
                address: document.getElementById('custAddress').value
            }};
            fetch('/store/api/customer/save', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}})
            .then(r=>r.json()).then(res => {{ closeModal('customerModal'); loadCustomers(); }});
        }}

        // --- POS & INVOICE FUNCTIONS ---
        function addToCart(id, name, price) {{
            let item = cart.find(c => c.id === id);
            if(item) item.qty++;
            else cart.push({{id: id, name: name, price: price, qty: 1}});
            renderCart();
        }}
        
        function renderCart() {{
            let html = '';
            let total = 0;
            if(cart.length === 0) html = '<div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; opacity:0.3;"><i class="fas fa-shopping-cart" style="font-size:40px; margin-bottom:10px;"></i>Cart Empty</div>';
            else {{
                cart.forEach((c, idx) => {{
                    let sub = c.price * c.qty;
                    total += sub;
                    html += `<div class="cart-item">
                        <div style="flex-grow:1;">
                            <div style="font-weight:600;">${{c.name}}</div>
                            <div style="font-size:12px; opacity:0.7;">৳ ${{c.price}} x ${{c.qty}}</div>
                        </div>
                        <div style="font-weight:bold; margin-right:15px;">৳ ${{sub}}</div>
                        <i class="fas fa-times-circle" onclick="removeFromCart(${idx})" style="color:var(--accent-red); cursor:pointer; font-size:16px;"></i>
                    </div>`;
                }});
            }}
            document.getElementById('cartItems').innerHTML = html;
            document.getElementById('cartSubtotal').innerText = total;
            calcTotal();
        }}
        
        function removeFromCart(idx) {{ cart.splice(idx, 1); renderCart(); }}
        
        function calcTotal() {{
            let sub = parseFloat(document.getElementById('cartSubtotal').innerText);
            let dis = parseFloat(document.getElementById('cartDiscount').value);
            if(isNaN(dis)) dis = 0;
            let total = sub - dis;
            document.getElementById('cartTotal').innerText = total > 0 ? total : 0;
        }}
        
        function processSale(type) {{
            if(cart.length === 0) return alert("Cart is empty! Add products first.");
            
            let paid = parseFloat(document.getElementById('posPaid').value);
            if(isNaN(paid)) paid = 0;

            let data = {{
                type: type,
                customer: document.getElementById('posCustomer').value,
                items: cart,
                subtotal: parseFloat(document.getElementById('cartSubtotal').innerText),
                discount: parseFloat(document.getElementById('cartDiscount').value) || 0,
                grand_total: parseFloat(document.getElementById('cartTotal').innerText),
                paid: paid
            }};
            
            fetch('/store/api/invoice/create', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}})
            .then(r=>r.json()).then(res => {{
                if(res.status === 'success') {{
                    alert(type.toUpperCase() + " Generated Successfully!");
                    cart = []; renderCart(); document.getElementById('posPaid').value = 0;
                    window.open('/store/invoice/print/' + res.invoice_id, '_blank');
                    loadInvoices(); // Refresh invoice list
                }} else alert("Error: " + res.message);
            }});
        }}
        
        function loadInvoices() {{
            fetch('/store/api/invoices').then(r=>r.json()).then(data => {{
                let html = '';
                if(data.length === 0) html = '<tr><td colspan="7" style="text-align:center; color:#888;">No invoices found</td></tr>';
                else {{
                    data.forEach(inv => {{
                        html += `<tr>
                            <td style="color:var(--accent-cyan);">${{inv.invoice_id}}</td>
                            <td>${{inv.date}}</td>
                            <td style="font-weight:500;">${{inv.customer_name}}</td>
                            <td style="font-weight:bold;">৳ ${{inv.grand_total}}</td>
                            <td style="color:var(--accent-green);">৳ ${{inv.paid_amount}}</td>
                            <td style="color:var(--accent-red); font-weight:bold;">৳ ${{inv.due_amount}}</td>
                            <td>
                                <a href="/store/invoice/print/${{inv.invoice_id}}" target="_blank" class="action-btn" style="background:rgba(255,255,255,0.1);">
                                    <i class="fas fa-print"></i> Print
                                </a>
                            </td>
                        </tr>`;
                    }});
                }}
                document.getElementById('invoiceListBody').innerHTML = html;
            }});
        }}
        
        function filterProducts() {{
            let txt = document.getElementById('prodSearch').value.toLowerCase();
            let items = document.querySelectorAll('.product-item');
            items.forEach(item => {{
                if(item.innerText.toLowerCase().includes(txt)) item.style.display = 'block';
                else item.style.display = 'none';
            }});
        }}
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE PANEL BACKEND ROUTES (API)
# ==============================================================================

@app.route('/store')
def store_dashboard_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    # Check permissions
    perms = session.get('permissions', [])
    if 'store' not in perms and session.get('role') != 'admin':
        flash("Access Denied: You do not have permission to access Store Panel.")
        return redirect(url_for('index'))
        
    # Get Summary Data
    store_stats = get_store_dashboard_summary()
    
    return render_template_string(STORE_TEMPLATE, store_stats=store_stats)

# --- Product API ---
@app.route('/store/api/products', methods=['GET'])
def get_store_products():
    if not session.get('logged_in'): return jsonify([])
    products = list(store_products_col.find({}, {'_id': 1, 'name': 1, 'price': 1, 'stock': 1}))
    # Convert ObjectId to string
    for p in products:
        p['_id'] = str(p['_id'])
    return jsonify(products)

@app.route('/store/api/product/save', methods=['POST'])
def save_store_product():
    if not session.get('logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    data = request.json
    name = data.get('name')
    price = float(data.get('price', 0))
    stock = int(data.get('stock', 0))
    prod_id = data.get('id')
    
    if prod_id: # Update
        store_products_col.update_one(
            {'_id': ObjectId(prod_id)},
            {'$set': {'name': name, 'price': price, 'stock': stock}}
        )
    else: # Create
        store_products_col.insert_one({
            'name': name,
            'price': price,
            'stock': stock,
            'created_at': get_bd_time()
        })
        
    return jsonify({'status': 'success'})

# --- Customer API ---
@app.route('/store/api/customers', methods=['GET'])
def get_store_customers():
    if not session.get('logged_in'): return jsonify([])
    customers = list(store_customers_col.find({}, {'_id': 1, 'name': 1, 'phone': 1, 'address': 1, 'total_due': 1}))
    for c in customers:
        c['_id'] = str(c['_id'])
        c['total_due'] = c.get('total_due', 0)
    return jsonify(customers)

@app.route('/store/api/customer/save', methods=['POST'])
def save_store_customer():
    if not session.get('logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    address = data.get('address')
    
    # Check if exists by phone (if phone is provided)
    if phone and store_customers_col.find_one({'phone': phone}):
        # Update existing
        store_customers_col.update_one(
            {'phone': phone},
            {'$set': {'name': name, 'address': address}}
        )
    else:
        store_customers_col.insert_one({
            'name': name,
            'phone': phone,
            'address': address,
            'total_due': 0,
            'created_at': get_bd_time()
        })
        
    return jsonify({'status': 'success'})

# --- Invoice & Sales API ---
@app.route('/store/api/invoice/create', methods=['POST'])
def create_store_invoice():
    if not session.get('logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    data = request.json
    invoice_type = data.get('type') # 'invoice' or 'quotation'
    customer_name = data.get('customer')
    items = data.get('items', [])
    subtotal = data.get('subtotal', 0)
    discount = data.get('discount', 0)
    grand_total = data.get('grand_total', 0)
    paid_amount = data.get('paid', 0)
    
    # Generate ID
    inv_id = get_next_invoice_id()
    if invoice_type == 'quotation':
        inv_id = "QT-" + inv_id.split('-')[1]
    
    due_amount = grand_total - paid_amount if invoice_type == 'invoice' else 0
    
    invoice_doc = {
        'invoice_id': inv_id,
        'type': invoice_type,
        'date': get_bd_date_str(),
        'timestamp': get_bd_time(),
        'customer_name': customer_name,
        'items': items,
        'subtotal': subtotal,
        'discount': discount,
        'grand_total': grand_total,
        'paid_amount': paid_amount,
        'due_amount': due_amount,
        'created_by': session.get('user'),
        'status': 'active'
    }
    
    # Save Invoice
    store_invoices_col.insert_one(invoice_doc)
    
    # If Invoice (Real Sale): Update Stock & Customer Due
    if invoice_type == 'invoice':
        # 1. Update Customer Due
        if customer_name != "Walking Customer":
            customer = store_customers_col.find_one({'name': customer_name})
            if customer:
                new_due = customer.get('total_due', 0) + due_amount
                store_customers_col.update_one({'_id': customer['_id']}, {'$set': {'total_due': new_due}})
            else:
                # If customer selected in POS but not in DB (rare case), create basic profile
                store_customers_col.insert_one({
                    'name': customer_name, 'phone': '', 'address': '', 
                    'total_due': due_amount, 'created_at': get_bd_time()
                })
        
        # 2. Update Product Stock
        for item in items:
            prod_id = item.get('id')
            qty = int(item.get('qty', 0))
            if prod_id:
                store_products_col.update_one(
                    {'_id': ObjectId(prod_id)},
                    {'$inc': {'stock': -qty}}
                )
                
        # 3. Record Payment (if any)
        if paid_amount > 0:
            store_payments_col.insert_one({
                'invoice_id': inv_id,
                'customer_name': customer_name,
                'amount': paid_amount,
                'date': get_bd_date_str(),
                'type': 'sale_payment'
            })

    return jsonify({'status': 'success', 'invoice_id': inv_id})

@app.route('/store/api/invoices', methods=['GET'])
def get_store_invoices():
    if not session.get('logged_in'): return jsonify([])
    # Get last 50 invoices sorted by newest
    invoices = list(store_invoices_col.find({}, {'_id': 0}).sort('timestamp', -1).limit(50))
    return jsonify(invoices)

# --- Invoice Print View ---
@app.route('/store/invoice/print/<invoice_id>')
def print_store_invoice(invoice_id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    invoice = store_invoices_col.find_one({'invoice_id': invoice_id})
    if not invoice:
        return "Invoice Not Found"
        
    # Get Customer Details (for address/phone on invoice)
    customer = store_customers_col.find_one({'name': invoice['customer_name']})
    cust_phone = customer.get('phone', '') if customer else ''
    cust_address = customer.get('address', '') if customer else ''
    
    return render_template_string(INVOICE_PRINT_TEMPLATE, inv=invoice, phone=cust_phone, address=cust_address)

# ==============================================================================
# ORIGINAL ROUTES (Part of Main Code)
# ==============================================================================
# These routes were in your original code and are preserved here to ensure
# the full code works.

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session.get('role') == 'admin':
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
                excel_file, 
                as_attachment=True, 
                download_name=f"Report-{internal_ref_no.replace('/', '_')}.xlsx", 
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ))
        else:
            flash("Data source returned empty.")
            return redirect(url_for('index'))
    except Exception as e:
        flash("Failed to generate Excel.")
        return redirect(url_for('index'))

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
        colors = data['colors']
        style = data['style']
        buyer = data['buyer']
        challans = data['challans'] 
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
            
            db_acc[ref_no] = {
                "style": style, "buyer": buyer, "colors": colors, 
                "item_type": "", "challans": challans
            }
            save_accessories_db(db_acc)
        except:
            flash("Connection Error with ERP")
            return redirect(url_for('accessories_search_page'))

    return render_template_string(ACCESSORIES_INPUT_TEMPLATE, ref=ref_no, colors=colors, style=style, buyer=buyer, challans=challans)

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
        
        for item in db_acc[ref]['challans']:
            item['status'] = "✔"
        
        new_entry = {
            "date": get_bd_date_str(),
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
        db_acc[ref]['challans'][index]['line'] = request.form.get('line_no')
        db_acc[ref]['challans'][index]['color'] = request.form.get('color')
        db_acc[ref]['challans'][index]['size'] = request.form.get('size')
        db_acc[ref]['challans'][index]['qty'] = request.form.get('qty')
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

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER): 
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    try:
        uploaded_files = request.files.getlist('pdf_files')
        all_data = []
        final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
        
        for file in uploaded_files:
            if file.filename == '': continue
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            data, meta = extract_data_dynamic(file_path)
            if meta['buyer'] != 'N/A': final_meta = meta
            if data: all_data.extend(data)
        
        if not all_data:
            return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found in uploaded files.")

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
            pivot.columns.name = None
            try:
                sorted_cols = sort_sizes(pivot.columns.tolist())
                pivot = pivot[sorted_cols]
            except: pass
            
            pivot['Total'] = pivot.sum(axis=1)
            grand_total_qty += pivot['Total'].sum()

            actual_qty = pivot.sum()
            actual_qty.name = 'Actual Qty'
            qty_plus_3 = (actual_qty * 1.03).round().astype(int)
            qty_plus_3.name = '3% Order Qty'
            
            pivot_final = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
            pivot_final = pivot_final.reset_index()
            pivot_final = pivot_final.rename(columns={'index': 'P.O NO'})
            
            pd.set_option('colheader_justify', 'center')
            html_table = pivot_final.to_html(classes='table table-bordered table-striped', index=False, border=0)
            
            html_table = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', html_table)
            html_table = html_table.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
            html_table = html_table.replace('<td>Total</td>', '<td class="total-col">Total</td>')
            html_table = html_table.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
            html_table = html_table.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
            html_table = re.sub(r'<tr>\s*<td class="summary-label">', '<tr class="summary-row"><td class="summary-label">', html_table)

            final_tables.append({'color': color, 'table': html_table})
            
        return render_template_string(PO_REPORT_TEMPLATE, tables=final_tables, meta=final_meta, grand_total=f"{grand_total_qty:,}")
    except Exception as e:
        flash(f"Error processing files: {str(e)}")
        return redirect(url_for('index'))
        # ==============================================================================
# FLASK ROUTES: STORE MODULE (BACKEND API)
# ==============================================================================

@app.route('/store')
def store_dashboard_view():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied: Store Panel")
        return redirect(url_for('index'))
    
    # Get Summary Data
    summary = get_store_dashboard_summary()
    return render_template_string(STORE_TEMPLATE, store_stats=summary)

# --- Product API ---
@app.route('/store/api/products', methods=['GET'])
def get_store_products():
    if not session.get('logged_in'): return jsonify([])
    products = list(products_col.find({}))
    for p in products:
        p['_id'] = str(p['_id']) # Convert ObjectId to string
    return jsonify(products)

@app.route('/store/api/product/save', methods=['POST'])
def save_store_product():
    if not session.get('logged_in'): return jsonify({'status':'error'})
    data = request.json
    
    product_data = {
        "name": data.get('name'),
        "price": float(data.get('price')),
        "stock": int(data.get('stock'))
    }
    
    if data.get('id'): # Update existing
        products_col.update_one({'_id': ObjectId(data.get('id'))}, {'$set': product_data})
    else: # Insert new
        products_col.insert_one(product_data)
        
    return jsonify({'status': 'success'})

# --- Customer API ---
@app.route('/store/api/customers', methods=['GET'])
def get_store_customers():
    if not session.get('logged_in'): return jsonify([])
    customers = list(customers_col.find({}))
    for c in customers:
        c['_id'] = str(c['_id'])
    return jsonify(customers)

@app.route('/store/api/customer/save', methods=['POST'])
def save_store_customer():
    if not session.get('logged_in'): return jsonify({'status':'error'})
    data = request.json
    
    customer_data = {
        "name": data.get('name'),
        "phone": data.get('phone'),
        "address": data.get('address'),
        "total_due": 0 # Initial due
    }
    customers_col.insert_one(customer_data)
    return jsonify({'status': 'success'})

# --- Invoice/Sales API ---
@app.route('/store/api/invoice/create', methods=['POST'])
def create_store_invoice():
    if not session.get('logged_in'): return jsonify({'status':'error'})
    data = request.json
    
    invoice_id = get_next_invoice_id()
    date_str = get_bd_date_str()
    
    items = data.get('items', [])
    customer_name = data.get('customer')
    grand_total = float(data.get('grand_total'))
    paid_amount = float(data.get('paid'))
    due_amount = grand_total - paid_amount
    
    # 1. Save Invoice
    invoice_doc = {
        "invoice_id": invoice_id,
        "date": date_str,
        "type": data.get('type', 'invoice'), # 'invoice' or 'quotation'
        "customer_name": customer_name,
        "items": items,
        "subtotal": data.get('subtotal'),
        "discount": data.get('discount'),
        "grand_total": grand_total,
        "paid_amount": paid_amount,
        "due_amount": due_amount,
        "created_by": session.get('user'),
        "status": "active"
    }
    invoices_col.insert_one(invoice_doc)
    
    # If it's a Quotation, we don't deduct stock or add due yet
    if data.get('type') == 'invoice':
        # 2. Update Stock
        for item in items:
            products_col.update_one(
                {"_id": ObjectId(item['id'])},
                {"$inc": {"stock": -int(item['qty'])}}
            )
            
        # 3. Update Customer Due (if not Walking Customer)
        if customer_name != "Walking Customer" and due_amount != 0:
            customers_col.update_one(
                {"name": customer_name},
                {"$inc": {"total_due": due_amount}}
            )
    
    return jsonify({'status': 'success', 'invoice_id': invoice_id})

@app.route('/store/api/invoices', methods=['GET'])
def get_store_invoices():
    if not session.get('logged_in'): return jsonify([])
    # Get last 50 invoices
    invoices = list(invoices_col.find({"status": "active"}).sort("_id", -1).limit(50))
    for inv in invoices:
        inv['_id'] = str(inv['_id'])
    return jsonify(invoices)

# ==============================================================================
# INVOICE PRINT TEMPLATE & ROUTE
# ==============================================================================

INVOICE_PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ invoice.invoice_id }}</title>
    <style>
        body { background: #e0e0e0; font-family: 'Segoe UI', sans-serif; -webkit-print-color-adjust: exact; }
        .invoice-container { max-width: 800px; margin: 30px auto; background: white; padding: 40px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .header { display: flex; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }
        .company-info h1 { margin: 0; color: #2c3e50; font-size: 28px; text-transform: uppercase; }
        .company-info p { margin: 5px 0 0; color: #666; font-size: 14px; }
        .invoice-details { text-align: right; }
        .invoice-details h2 { margin: 0; color: #e67e22; }
        .invoice-details p { margin: 5px 0 0; font-weight: bold; color: #333; }
        
        .bill-to { margin-bottom: 30px; }
        .bill-to h3 { margin: 0 0 10px; color: #2c3e50; font-size: 16px; border-bottom: 1px solid #eee; display: inline-block; padding-bottom: 5px; }
        .bill-to p { margin: 0; font-size: 15px; font-weight: 600; }
        
        .items-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        .items-table th { background: #2c3e50; color: white; padding: 12px; text-align: left; font-size: 14px; }
        .items-table td { padding: 12px; border-bottom: 1px solid #eee; font-size: 14px; }
        .items-table tr:last-child td { border-bottom: 2px solid #333; }
        
        .totals { display: flex; justify-content: flex-end; }
        .totals-table { width: 300px; border-collapse: collapse; }
        .totals-table td { padding: 8px; text-align: right; font-size: 14px; }
        .totals-table .label { font-weight: 600; color: #666; }
        .totals-table .amount { font-weight: bold; color: #333; }
        .totals-table .grand-total { font-size: 18px; color: #e67e22; border-top: 2px solid #333; padding-top: 10px; }
        
        .footer { margin-top: 50px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #eee; padding-top: 20px; }
        
        @media print {
            body { background: white; margin: 0; }
            .invoice-container { box-shadow: none; margin: 0; width: 100%; max-width: 100%; padding: 20px; }
            .no-print { display: none; }
        }
    </style>
</head>
<body>
    <div class="invoice-container">
        <div class="header">
            <div class="company-info">
                <h1>Aluminium Shop</h1>
                <p>123, Industrial Area, Dhaka, Bangladesh</p>
                <p>Phone: +880 1700-000000</p>
            </div>
            <div class="invoice-details">
                <h2>{{ invoice.type|upper }}</h2>
                <p># {{ invoice.invoice_id }}</p>
                <p>Date: {{ invoice.date }}</p>
            </div>
        </div>
        
        <div class="bill-to">
            <h3>BILL TO</h3>
            <p>{{ invoice.customer_name }}</p>
        </div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Item Description</th>
                    <th style="text-align:right;">Price</th>
                    <th style="text-align:center;">Qty</th>
                    <th style="text-align:right;">Total</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ item.name }}</td>
                    <td style="text-align:right;">{{ item.price }}</td>
                    <td style="text-align:center;">{{ item.qty }}</td>
                    <td style="text-align:right;">{{ item.price * item.qty }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <div class="totals">
            <table class="totals-table">
                <tr>
                    <td class="label">Subtotal:</td>
                    <td class="amount">{{ invoice.subtotal }}</td>
                </tr>
                <tr>
                    <td class="label">Discount:</td>
                    <td class="amount">- {{ invoice.discount }}</td>
                </tr>
                <tr>
                    <td class="label grand-total">Grand Total:</td>
                    <td class="amount grand-total">{{ invoice.grand_total }}</td>
                </tr>
                <tr>
                    <td class="label">Paid:</td>
                    <td class="amount" style="color: green;">{{ invoice.paid_amount }}</td>
                </tr>
                <tr>
                    <td class="label">Due:</td>
                    <td class="amount" style="color: red;">{{ invoice.due_amount }}</td>
                </tr>
            </table>
        </div>
        
        <div style="margin-top: 60px; display: flex; justify-content: space-between;">
            <div style="text-align: center;">
                <div style="border-top: 1px solid #333; width: 150px; margin: 0 auto;"></div>
                <p style="font-size: 12px; margin-top: 5px;">Customer Signature</p>
            </div>
            <div style="text-align: center;">
                <div style="border-top: 1px solid #333; width: 150px; margin: 0 auto;"></div>
                <p style="font-size: 12px; margin-top: 5px;">Authorized Signature</p>
            </div>
        </div>
        
        <div class="footer">
            <p>Thank you for your business!</p>
            <p>Computer Generated Invoice | MNM Software</p>
        </div>
        
        <div class="no-print" style="text-align: center; margin-top: 20px;">
            <button onclick="window.print()" style="padding: 10px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; border-radius: 5px;">Print Invoice</button>
            <button onclick="window.close()" style="padding: 10px 20px; background: #e74c3c; color: white; border: none; cursor: pointer; border-radius: 5px; margin-left: 10px;">Close</button>
        </div>
    </div>
</body>
</html>
"""

@app.route('/store/invoice/print/<invoice_id>')
def print_invoice(invoice_id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    invoice = invoices_col.find_one({"invoice_id": invoice_id})
    if not invoice:
        return "Invoice Not Found", 404
        
    return render_template_string(INVOICE_PRINT_TEMPLATE, invoice=invoice)

# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    # MongoDB কানেকশন চেক প্রিন্ট করা হচ্ছে কনসোলে
    print(f"Server starting... MongoDB Status: {'Connected' if 'db' in locals() else 'Failed'}")
    
    # প্রোডাকশন এনভায়রনমেন্টের জন্য পোর্ট সেট করা
    port = int(os.environ.get("PORT", 5000))
    
    # অ্যাপ রান করা
    app.run(host='0.0.0.0', port=port, debug=True)
