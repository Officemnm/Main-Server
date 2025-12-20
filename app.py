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
# ফিক্সড: কানেকশন স্ট্রিং এর স্পেস রিমুভ করা হয়েছে
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
            color:  var(--text-primary);
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
            position: relative;
        }

        /* Particle Background */
        #particles-js {
            position:  fixed;
            top: 0;
            left:  0;
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
            height:  100%;
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
            width:  1px;
            height: 100%;
            background: linear-gradient(180deg, transparent, var(--accent-orange), transparent);
            opacity: 0.3;
        }

        .brand-logo { 
            font-size: 26px;
            font-weight:  900; 
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
            color:  white;
            padding: 2px 8px;
            border-radius:  10px;
            font-size:  11px;
            font-weight:  700;
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
            font-size:  32px;
            font-weight: 800; 
            color: white; 
            margin-bottom: 8px;
            letter-spacing:  -0.5px;
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
            border-radius:  50px;
            border: 1px solid var(--border-color);
            font-size: 13px;
            font-weight:  600;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: var(--shadow-card);
            transition: var(--transition-smooth);
        }
        
        /* Status Dot Animation - FIXED */
        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: statusPulse 1.5s ease-in-out infinite;
            box-shadow: 0 0 10px var(--accent-green);
        }
        
        @keyframes statusPulse {
            0%, 100% { 
                opacity: 1; 
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            }
            50% { 
                opacity: 0.8; 
                transform: scale(1.2);
                box-shadow: 0 0 0 10px rgba(16, 185, 129, 0);
            }
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
            margin-bottom:  24px; 
        }

        .card { 
            background: var(--gradient-card);
            border:  1px solid var(--border-color);
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
            margin-bottom:  24px; 
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
            height:  100%;
            background: var(--gradient-orange);
            opacity: 0;
            transition:  var(--transition-smooth);
        }

        .stat-card:hover .stat-icon {
            transform: rotate(-10deg) scale(1.1);
            box-shadow: 0 0 30px var(--accent-orange-glow);
        }

        .stat-card:hover .stat-icon i {
            animation: iconBounce 0.5s ease-out;
        }

        @keyframes iconBounce {
            0%, 100% { transform:  scale(1); }
            50% { transform: scale(1.3); }
        }

        .stat-info h3 { 
            font-size: 36px;
            font-weight: 800; 
            margin:  0; 
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
            margin:  6px 0 0 0; 
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
            top:  0;
            left: 0;
            right: 0;
            bottom: 0;
            background:  linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }

        @keyframes progressFill {
            from { transform: scaleX(0); }
            to { transform:  scaleX(1); }
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
            box-shadow: 0 0 0 4px var(--accent-orange-glow), 0 0 20px var(--accent-orange-glow);
        }

        select {
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='%23FF7A00' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position:  right 12px center;
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
            padding:  14px 24px; 
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
            content:  '';
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
            box-shadow:  0 10px 30px var(--accent-orange-glow);
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
            border-radius:  8px;
            font-size:  12px;
            font-weight:  600;
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
            0% { transform:  rotate(0deg); } 
            100% { transform:  rotate(360deg); } 
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
            border:  solid var(--accent-green); 
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
            50% { transform:  scale(1.2); } 
            100% { transform:  scale(1); opacity: 1; } 
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
            font-size:  24px; 
            font-weight: 800; 
            color: white;
            margin-top: 10px; 
            letter-spacing: 1px;
        }

        .loading-text {
            color: var(--text-secondary);
            font-size: 15px;
            margin-top:  20px;
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
            left:  0;
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
            border:  1px solid var(--border-color);
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
                transform:  translateY(-50px) scale(0.9);
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
            margin-bottom:  20px;
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
            margin-bottom:  10px;
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
            border-radius:  12px;
            font-size:  15px;
            font-weight:  700;
            cursor: pointer;
            transition: var(--transition-smooth);
            position: relative;
            z-index: 1;
        }

        .welcome-close:hover {
            transform: translateY(-3px);
            box-shadow:  0 15px 40px var(--accent-orange-glow);
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
            border-radius:  8px;
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
            visibility:  visible;
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
            border-color:  var(--accent-orange);
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
            50% { transform:  translateY(-10px); }
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
            border-radius:  12px;
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
                display:  flex;
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
                grid-template-columns:  1fr;
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
            animation:  skeletonLoad 1.5s infinite;
            border-radius: 8px;
        }

        @keyframes skeletonLoad {
            0% { background-position:  200% 0; }
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
            box-shadow:  0 12px 40px var(--accent-orange-glow);
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
            top:  -2px;
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
            border-radius:  12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            border: 1px solid var(--border-color);
            transition:  var(--transition-smooth);
            flex:  1;
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
            border-radius:  8px;
            font-size:  13px;
            color: var(--text-secondary);
        }

        .time-badge i {
            color: var(--accent-orange);
        }
        
        /* History Card Styles - NEW */
        .history-card {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius:  16px;
            padding: 20px;
            margin-top: 20px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }
        
        .history-card:hover {
            border-color:  var(--accent-purple);
            box-shadow: 0 0 30px rgba(139, 92, 246, 0.2);
            transform: translateY(-3px);
        }
        
        .history-card-header {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .history-card-icon {
            width: 50px;
            height: 50px;
            background: linear-gradient(145deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            color: var(--accent-purple);
        }
        
        .history-card-title {
            font-size: 18px;
            font-weight:  700;
            color: white;
        }
        
        .history-card-subtitle {
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        .history-list {
            max-height: 300px;
            overflow-y:  auto;
        }
        
        .history-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            margin-bottom:  8px;
            transition: var(--transition-smooth);
            cursor: pointer;
            border: 1px solid transparent;
        }
        
        .history-item:hover {
            background: rgba(139, 92, 246, 0.1);
            border-color: rgba(139, 92, 246, 0.3);
        }
        
        .history-item-ref {
            font-weight: 700;
            color: var(--accent-purple);
            font-size: 14px;
        }
        
        .history-item-info {
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .history-item-arrow {
            color: var(--text-secondary);
            transition: var(--transition-smooth);
        }
        
        .history-item:hover .history-item-arrow {
            color: var(--accent-purple);
            transform: translateX(5px);
        }
        
        .history-count-badge {
            background: var(--accent-purple);
            color: white;
            padding: 4px 12px;
            border-radius:  20px;
            font-size: 12px;
            font-weight: 700;
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
    # ফিক্সড: replace_one এর মাঝের স্পেস রিমুভ করা হয়েছে
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
        "ref":  ref_no,
        "user": username,
        "date": now.strftime('%d-%m-%Y'), # ফিক্সড: strftime এর স্পেস রিমুভ
        "time": now.strftime('%I:%M %p'),
        "type": "Closing Report",
        "iso_time": now.isoformat()
    }
    data['downloads'].insert(0, new_record)
    if len(data['downloads']) > 3000:
        data['downloads'] = data['downloads'][:3000]
        
    data['last_booking'] = ref_no
    save_stats(data)

def update_po_stats(username, file_count, booking_ref="N/A"):
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

def check_and_refresh_colors(ref_no, db_acc):
    """
    ২৪ ঘন্টা পর পর API কল করে নতুন কালার আপডেট করে।
    Returns: updated data dict or None if no update needed or failed
    """
    if ref_no not in db_acc:
        return None
    
    data = db_acc[ref_no]
    last_updated = data.get('last_api_call', None)
    now = get_bd_time()
    
    # Check if 24 hours have passed
    needs_refresh = False
    if last_updated is None: 
        needs_refresh = True
    else:
        try:
            last_updated_dt = datetime.fromisoformat(last_updated)
            # Make sure both datetimes are timezone aware
            if last_updated_dt.tzinfo is None:
                last_updated_dt = bd_tz.localize(last_updated_dt)
            
            time_diff = now - last_updated_dt
            if time_diff.total_seconds() >= 86400:  # 24 hours = 86400 seconds
                needs_refresh = True
        except Exception as e:
            print(f"Error parsing last_api_call: {e}")
            needs_refresh = True
    
    if needs_refresh:
        try:
            api_data = fetch_closing_report_data(ref_no)
            if api_data:
                # Get new colors from API
                new_colors = sorted(list(set([item['color'] for item in api_data])))
                existing_colors = data.get('colors', [])
                
                # Merge colors - keep existing and add new ones
                merged_colors = list(set(existing_colors + new_colors))
                merged_colors = sorted(merged_colors)
                
                # Update data
                db_acc[ref_no]['colors'] = merged_colors
                db_acc[ref_no]['last_api_call'] = now.isoformat() # ফিক্সড: isoformat()
                
                # Also update buyer and style if available
                if api_data[0].get('buyer', 'N/A') != 'N/A':
                    db_acc[ref_no]['buyer'] = api_data[0].get('buyer', data.get('buyer', 'N/A'))
                if api_data[0].get('style', 'N/A') != 'N/A': 
                    db_acc[ref_no]['style'] = api_data[0].get('style', data.get('style', 'N/A'))
                
                save_accessories_db(db_acc)
                print(f"Colors refreshed for {ref_no}. New colors: {merged_colors}")
                return db_acc
        except Exception as e:
            print(f"Error refreshing colors for {ref_no}: {e}")
            return None
    
    return None

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
            'ref':  ref,
            'buyer': data.get('buyer', 'N/A'),
            'style': data.get('style', 'N/A'),
            'challan_count': challan_count,
            'total_qty': total_qty,
            'last_updated': data.get('last_api_call', 'N/A')
        })
    
    # Sort by ref number
    bookings = sorted(bookings, key=lambda x: x['ref'], reverse=True)
    return bookings

# --- আপডেটেড:  রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স ---
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
            "last_login":  d.get('last_login', 'Never'),
            "last_duration":  d.get('last_duration', 'N/A')
        })

    # 2. Accessories Today & Analytics - LIFETIME COUNT
    acc_lifetime_count = 0
    acc_today_list = []
    
    # Analytics Container:  {'YYYY-MM-DD': {'label': '01-Dec', 'closing':  0, 'po':  0, 'acc': 0}}
    daily_data = defaultdict(lambda: {'closing': 0, 'po':  0, 'acc': 0})

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
            
            # Analytics Calculation - Daily basis
            try:
                dt_obj = datetime.strptime(c_date, '%d-%m-%Y')
                sort_key = dt_obj.strftime('%Y-%m-%d')
                daily_data[sort_key]['acc'] += 1
                daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
            except:  pass

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
        "accessories": { "count": acc_lifetime_count, "details":  acc_today_list },
        "closing": { "count": closing_lifetime_count, "details":  closing_list },
        "po": { "count": po_lifetime_count, "details": po_list },
        "chart":  {
            "labels": chart_labels,
            "closing": chart_closing,
            "po":  chart_po,
            "acc": chart_acc
        },
        "history": history
    }
    # ==============================================================================
# লজিক পার্ট:  PURCHASE ORDER SHEET PARSER (PDF)
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
        if s in STANDARD_ORDER:  return (0, STANDARD_ORDER.index(s))
        if s.isdigit(): return (1, int(s))
        match = re.match(r'^(\d+)([A-Z]+)$', s)
        if match:  return (2, int(match.group(1)), match.group(2))
        return (3, s)
    return sorted(size_list, key=sort_key)

def extract_metadata(first_page_text):
    meta = {
        'buyer': 'N/A', 'booking':  'N/A', 'style': 'N/A', 
        'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'
    }
    if "KIABI" in first_page_text.upper():
        meta['buyer'] = "KIABI"
    else:
        buyer_match = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", first_page_text)
        if buyer_match:  meta['buyer'] = buyer_match.group(1).strip()

    booking_block_match = re.search(r"(?:Internal )?Booking NO\. ?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match:  
        raw_booking = booking_block_match.group(1).strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking:  clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\. ?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match: meta['style'] = style_match.group(1).strip()
    else: 
        style_match = re.search(r"Style Des\. ?[\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match: meta['style'] = style_match.group(1).strip()

    season_match = re.search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re.IGNORECASE)
    if season_match: meta['season'] = season_match.group(1).strip()
    dept_match = re.search(r"Dept\. ?[\s\n: ]*([A-Za-z]+)", first_page_text, re.IGNORECASE)
    if dept_match: meta['dept'] = dept_match.group(1).strip()

    item_match = re.search(r"Garments?    Item[\s\n: ]*([^\n\r]+)", first_page_text, re.IGNORECASE)
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
        if order_match:  order_no = order_match.group(1)
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
                        raw_sizes = parts[: total_idx]
                        temp_sizes = [s for s in raw_sizes if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/", "Size's"]]
                        
                        valid_size_count = sum(1 for s in temp_sizes if is_potential_size(s))
                        if temp_sizes and valid_size_count >= len(temp_sizes) / 2:
                            sizes = temp_sizes
                            capturing_data = True
                        else:
                            sizes = []
                            capturing_data = False
                    except:  pass
                    continue
                
                if capturing_data:
                    if line.startswith("Total Quantity") or line.startswith("Total Amount"):
                        capturing_data = False
                        continue
                    lower_line = line.lower()
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line: 
                        continue
                        
                    clean_line = line.replace("Spec.  price", "").replace("Spec", "").strip()
                    if not re.search(r'[a-zA-Z]', clean_line): continue
                    if re.match(r'^[A-Z]\d+$', clean_line) or "Assortment" in clean_line:  continue

                    numbers_in_line = re.findall(r'\b\d+\b', line)
                    quantities = [int(n) for n in numbers_in_line]
                    color_name = clean_line
                    final_qtys = []

                    if len(quantities) >= len(sizes):
                        if len(quantities) == len(sizes) + 1: final_qtys = quantities[:-1] 
                        else: final_qtys = quantities[: len(sizes)]
                        color_name = re.sub(r'\s\d+$', '', color_name).strip()
                    elif len(quantities) < len(sizes): 
                        vertical_qtys = []
                        for next_line in lines[i+1:]: 
                            next_line = next_line.strip()
                            if "Total" in next_line or re.search(r'[a-zA-Z]', next_line.replace("Spec", "").replace("price", "")): break
                            if re.match(r'^\d+$', next_line): vertical_qtys.append(int(next_line))
                        
                        if len(vertical_qtys) >= len(sizes): final_qtys = vertical_qtys[: len(sizes)]
                    
                    if final_qtys and color_name:
                         for idx, size in enumerate(sizes):
                            extracted_data.append({
                                'P.O NO': order_no,
                                'Color': color_name,
                                'Size': size,
                                'Quantity': final_qtys[idx]
                            })
    except Exception as e:  print(f"Error processing file: {e}")
    return extracted_data, metadata
    # ==============================================================================
# লজিক পার্ট:  CLOSING REPORT API & EXCEL GENERATION
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
    if not active_session:  return None

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
            except:  continue
        if found_data:  break
    
    if found_data:
        return parse_report_data(found_data)
    return None

def parse_report_data(html_content):
    all_report_data = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row:  return None
        all_th = header_row.find_all('th')
        headers = [th.get_text(strip=True) for th in all_th if 'total' not in th.get_text(strip=True).lower()]
        data_rows = soup.select('div#scroll_body table tbody tr')
        item_blocks = []
        current_block = []
        for row in data_rows:
            if row.get('bgcolor') == '#cddcdc':
                if current_block:  item_blocks.append(current_block)
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
                    
                    if main_lower == "style":  style = cells[1].get_text(strip=True)
                    elif main_lower == "color & gmts.  item": color = cells[1].get_text(strip=True)
                    elif "buyer" in main_lower: buyer_name = cells[1].get_text(strip=True)
                    
                    if sub_lower == "gmts. color /country qty": gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    
                    if "sewing input" in main_lower:  sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in sub_lower:  sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
    
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
                    'headers': headers, 'gmts_qty':  gmts_qty_data, 
                    'plus_3_percent': plus_3_percent_data, 
                    'sewing_input':  sewing_input_data if sewing_input_data else [], 
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
        return all_report_data
    except Exception as e:
        return None

def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data:  return None
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
    
                if col_idx in [1, 2, 3, 6, 9]:  cell.font = bold_font
                
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
            if not merged_cell.font.bold:  merged_cell.font = bold_font
        
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
            if cell.coordinate == 'B5':  continue
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
# HTML TEMPLATES (MODERN UI INTEGRATED)
# ==============================================================================

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secure Login | ERP Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """ + COMMON_STYLES + """
    <style>
        .login-container {
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            z-index: 1;
        }
        .login-card {
            background: rgba(22, 22, 31, 0.8);
            backdrop-filter: blur(20px);
            padding: 40px;
            border-radius: 24px;
            border: 1px solid var(--border-color);
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: fadeInUp 0.6s ease-out;
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-logo {
            font-size: 48px;
            color: var(--accent-orange);
            margin-bottom: 15px;
            display: inline-block;
            animation: float 3s ease-in-out infinite;
        }
        @keyframes float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        .login-title {
            font-size: 24px;
            font-weight: 800;
            color: white;
            margin-bottom: 5px;
        }
        .login-subtitle {
            color: var(--text-secondary);
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    <div id="particles-js"></div>
    
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <div class="login-logo">
                    <i class="fa-solid fa-cube"></i>
                </div>
                <h1 class="login-title">Welcome Back</h1>
                <p class="login-subtitle">Sign in to access your dashboard</p>
            </div>
            
            <form method="POST" action="/login">
                <div class="input-group">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="Enter your username" required autocomplete="off">
                </div>
                
                <div class="input-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="••••••••" required>
                </div>
                
                <button type="submit">
                    Sign In <i class="fa-solid fa-arrow-right" style="margin-left: 8px;"></i>
                </button>
            </form>
            
            <div class="sidebar-footer" style="margin-top: 25px; border: none;">
                SECURE SYSTEM • AUTHORIZED PERSONNEL ONLY
            </div>
        </div>
    </div>

    <script>
        particlesJS("particles-js", {
            "particles": {
                "number": { "value": 40 },
                "size": { "value": 2 },
                "color": { "value": "#FF7A00" },
                "line_linked": { 
                    "enable": true, 
                    "color": "#FF7A00", 
                    "opacity": 0.1 
                },
                "move": { "speed": 1 }
            }
        });
    </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# DASHBOARD TEMPLATE (Main UI)
# ------------------------------------------------------------------------------
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard | ERP Nexus</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="mobile-toggle" onclick="toggleSidebar()">
        <i class="fa-solid fa-bars"></i>
    </div>

    <!-- Sidebar -->
    <div class="sidebar" id="sidebar">
        <div class="brand-logo">
            <i class="fa-solid fa-cube"></i>
            <div>ERP<span>Nexus</span></div>
        </div>
        
        <div class="nav-menu">
            <a href="/dashboard" class="nav-link active">
                <i class="fa-solid fa-chart-pie"></i> Overview
            </a>
            
            {% if 'closing' in permissions %}
            <a href="#closing-section" class="nav-link" onclick="showSection('closing')">
                <i class="fa-solid fa-file-invoice"></i> Closing Report
            </a>
            {% endif %}
            
            {% if 'po_sheet' in permissions %}
            <a href="/po_sheet" class="nav-link">
                <i class="fa-solid fa-file-csv"></i> PO Converter
            </a>
            {% endif %}
            
            {% if 'accessories' in permissions %}
            <a href="/accessories" class="nav-link">
                <i class="fa-solid fa-shirt"></i> Accessories
                <span class="nav-badge">{{ stats.accessories.details|length }}</span>
            </a>
            {% endif %}
            
            {% if role == 'admin' %}
            <a href="/manage_users" class="nav-link">
                <i class="fa-solid fa-users-gear"></i> User Management
            </a>
            {% endif %}
        </div>
        
        <div class="sidebar-footer">
            LOGGED IN AS: {{ user|upper }} <br>
            <a href="/logout" style="color: var(--accent-red); text-decoration: none; margin-top: 10px; display: inline-block; font-weight: 700;">
                <i class="fa-solid fa-power-off"></i> LOGOUT
            </a>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-message {% if category == 'error' %}flash-error{% else %}flash-success{% endif %}">
                        <i class="fa-solid {% if category == 'error' %}fa-circle-exclamation{% else %}fa-circle-check{% endif %}"></i>
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Welcome Header -->
        <div class="header-section">
            <div>
                <div class="page-title">Dashboard Overview</div>
                <div class="page-subtitle">Real-time production & booking analytics</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                SYSTEM ONLINE
                <span style="margin-left: 10px; color: var(--text-secondary);">| {{ now }}</span>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon"><i class="fa-solid fa-file-circle-check"></i></div>
                <div class="stat-info">
                    <h3 class="count-up">{{ stats.closing.count }}</h3>
                    <p>Closing Reports</p>
                </div>
            </div>
            
            <div class="card stat-card">
                <div class="stat-icon" style="color: var(--accent-purple);"><i class="fa-solid fa-file-invoice-dollar"></i></div>
                <div class="stat-info">
                    <h3 class="count-up">{{ stats.po.count }}</h3>
                    <p>PO Processed</p>
                </div>
            </div>
            
            <div class="card stat-card">
                <div class="stat-icon" style="color: var(--accent-green);"><i class="fa-solid fa-layer-group"></i></div>
                <div class="stat-info">
                    <h3 class="count-up">{{ stats.accessories.count }}</h3>
                    <p>Accessories</p>
                </div>
            </div>
            
             <div class="card stat-card">
                <div class="stat-icon" style="color: var(--accent-blue);"><i class="fa-solid fa-users"></i></div>
                <div class="stat-info">
                    <h3 class="count-up">{{ stats.users.count }}</h3>
                    <p>Active Users</p>
                </div>
            </div>
        </div>

        <!-- Closing Report Section (Hidden by default, shown via ID link) -->
        <div id="closing-section" class="card" style="margin-bottom: 30px;">
            <div class="section-header">
                <span><i class="fa-solid fa-file-export" style="color: var(--accent-orange); margin-right: 10px;"></i> GENERATE REPORT</span>
            </div>
            <form action="/download_closing" method="post" id="closingForm">
                <div class="input-group">
                    <label>Internal Reference Number (e.g., EFL-25-123)</label>
                    <input type="text" name="ref_no" placeholder="Enter Ref No..." required>
                </div>
                <button type="submit" onclick="showLoading()">
                    <i class="fa-solid fa-cloud-arrow-down"></i> Generate & Download Excel
                </button>
            </form>
        </div>

        <!-- Analytics Chart & History -->
        <div class="dashboard-grid-2">
            <!-- Chart -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fa-solid fa-chart-line"></i> PERFORMANCE ANALYTICS</span>
                    <div class="realtime-indicator">
                        <div class="realtime-dot"></div> Live
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="activityChart"></canvas>
                </div>
            </div>

            <!-- Recent History -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fa-solid fa-clock-rotate-left"></i> RECENT ACTIVITY</span>
                </div>
                <div class="history-list">
                    {% for item in stats.history[:8] %}
                    <div class="history-item">
                        <div>
                            <div class="history-item-ref">{{ item.ref }}</div>
                            <div class="history-item-info">
                                {{ item.user }} • {{ item.time }}
                                {% if item.type == 'PO Sheet' %} • {{ item.file_count }} Files{% endif %}
                            </div>
                        </div>
                        <div class="history-count-badge" style="background: {% if item.type == 'PO Sheet' %}var(--accent-purple){% else %}var(--accent-orange){% endif %}">
                            {{ item.type }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="anim-text">PROCESSING</div>
        <div class="loading-text">Fetching Data from ERP Server...</div>
    </div>

    <script>
        // Sidebar Toggle
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('active');
        }
        
        // Show Loading
        function showLoading() {
            document.getElementById('loading-overlay').style.display = 'flex';
        }

        // Chart Config
        const ctx = document.getElementById('activityChart').getContext('2d');
        const gradientOrange = ctx.createLinearGradient(0, 0, 0, 400);
        gradientOrange.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
        gradientOrange.addColorStop(1, 'rgba(255, 122, 0, 0)');

        const gradientPurple = ctx.createLinearGradient(0, 0, 0, 400);
        gradientPurple.addColorStop(0, 'rgba(139, 92, 246, 0.5)');
        gradientPurple.addColorStop(1, 'rgba(139, 92, 246, 0)');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ stats.chart.labels | tojson }},
                datasets: [
                    {
                        label: 'Closing Reports',
                        data: {{ stats.chart.closing | tojson }},
                        borderColor: '#FF7A00',
                        backgroundColor: gradientOrange,
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#FF7A00'
                    },
                    {
                        label: 'PO Sheets',
                        data: {{ stats.chart.po | tojson }},
                        borderColor: '#8B5CF6',
                        backgroundColor: gradientPurple,
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#8B5CF6'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#8b8b9e' } }
                },
                scales: {
                    y: { 
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#8b8b9e' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#8b8b9e' }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# ACCESSORIES TEMPLATE
# ------------------------------------------------------------------------------
ACCESSORIES_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Accessories | ERP Nexus</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="mobile-toggle" onclick="toggleSidebar()"><i class="fa-solid fa-bars"></i></div>
    
    <div class="sidebar" id="sidebar">
        <div class="brand-logo"><i class="fa-solid fa-cube"></i><div>ERP<span>Nexus</span></div></div>
        <div class="nav-menu">
            <a href="/dashboard" class="nav-link"><i class="fa-solid fa-chart-pie"></i> Overview</a>
            <a href="/accessories" class="nav-link active"><i class="fa-solid fa-shirt"></i> Accessories</a>
        </div>
        <div class="sidebar-footer"><a href="/logout">LOGOUT</a></div>
    </div>

    <div class="main-content">
        <!-- New Booking Form -->
        <div class="card">
            <div class="section-header">
                <span><i class="fa-solid fa-plus-circle"></i> ADD NEW BOOKING</span>
            </div>
            <form action="/add_booking" method="post">
                <div class="input-group">
                    <label>Internal Booking Reference</label>
                    <input type="text" name="ref_no" placeholder="Enter Reference No..." required>
                </div>
                <button type="submit">Initialize Booking</button>
            </form>
        </div>

        <!-- Booking List -->
        <div class="card">
            <div class="section-header"><span><i class="fa-solid fa-list"></i> ACTIVE BOOKINGS</span></div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Reference</th>
                            <th>Buyer / Style</th>
                            <th>Challans</th>
                            <th>Total Qty</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in bookings %}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-orange);">{{ item.ref }}</td>
                            <td>
                                <div style="font-weight: 600;">{{ item.buyer }}</div>
                                <div style="font-size: 11px; color: var(--text-secondary);">{{ item.style }}</div>
                            </td>
                            <td><span class="table-badge">{{ item.challan_count }}</span></td>
                            <td>{{ item.total_qty }}</td>
                            <td>
                                {% if item.last_updated != 'N/A' %}
                                <span style="color: var(--accent-green); font-size: 11px;">● Synced</span>
                                {% else %}
                                <span style="color: var(--accent-red); font-size: 11px;">● Pending</span>
                                {% endif %}
                            </td>
                            <td class="action-cell">
                                <a href="/view_booking/{{ item.ref }}" class="action-btn btn-edit"><i class="fa-solid fa-eye"></i> View</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <script>
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('active'); }
    </script>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# PO SHEET TEMPLATE
# ------------------------------------------------------------------------------
PO_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PO Report | ERP Nexus</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Roboto', sans-serif; background: #fff; color: #333; padding: 20px; }
        .report-header { text-align: center; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #000; }
        .report-title { font-size: 24px; font-weight: 700; text-transform: uppercase; margin: 0; }
        .meta-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; font-size: 12px; }
        .meta-item { border: 1px solid #ddd; padding: 5px; background: #f9f9f9; }
        .meta-label { font-weight: 700; color: #555; display: block; }
        
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 11px; }
        th, td { border: 1px solid #ccc; padding: 4px 6px; text-align: center; }
        th { background: #eee; font-weight: 700; }
        
        .color-header { background: #333; color: #fff; text-align: left; padding: 5px 10px; font-size: 13px; font-weight: 700; margin-top: 15px; }
        .grand-total { font-size: 16px; font-weight: 700; text-align: right; margin-top: 20px; padding: 10px; border-top: 2px solid #000; }
        
        /* Print Optimization */
        @media print {
            .no-print { display: none; }
            body { padding: 0; }
            table { page-break-inside: auto; }
            tr { page-break-inside: avoid; page-break-after: auto; }
        }
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="padding: 10px 20px; background: #000; color: #fff; border: none; cursor: pointer;">PRINT REPORT</button>
        <a href="/dashboard" style="margin-left: 10px; text-decoration: none; color: #333;">Back to Dashboard</a>
    </div>

    <div class="report-header">
        <h1 class="report-title">Purchase Order Breakdown</h1>
        <p>Generated on: {{ meta.generated_at }}</p>
    </div>

    <div class="meta-grid">
        <div class="meta-item"><span class="meta-label">BUYER</span> {{ meta.buyer }}</div>
        <div class="meta-item"><span class="meta-label">BOOKING NO</span> {{ meta.booking }}</div>
        <div class="meta-item"><span class="meta-label">STYLE</span> {{ meta.style }}</div>
        <div class="meta-item"><span class="meta-label">SEASON</span> {{ meta.season }}</div>
        <div class="meta-item"><span class="meta-label">DEPARTMENT</span> {{ meta.dept }}</div>
        <div class="meta-item"><span class="meta-label">ITEM</span> {{ meta.item }}</div>
    </div>

    {% for table in tables %}
        <div class="color-header">COLOR: {{ table.color }}</div>
        {{ table.table | safe }}
    {% endfor %}

    <div class="grand-total">
        GRAND TOTAL QUANTITY: {{ grand_total }}
    </div>
</body>
</html>
"""

# ------------------------------------------------------------------------------
# PO UPLOAD TEMPLATE
# ------------------------------------------------------------------------------
PO_UPLOAD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Upload PO | ERP Nexus</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    """ + COMMON_STYLES + """
</head>
<body>
    <div class="mobile-toggle" onclick="toggleSidebar()"><i class="fa-solid fa-bars"></i></div>
    <div class="sidebar" id="sidebar">
        <div class="brand-logo"><i class="fa-solid fa-cube"></i><div>ERP<span>Nexus</span></div></div>
        <div class="nav-menu">
            <a href="/dashboard" class="nav-link"><i class="fa-solid fa-chart-pie"></i> Overview</a>
            <a href="/po_sheet" class="nav-link active"><i class="fa-solid fa-file-csv"></i> PO Converter</a>
        </div>
    </div>

    <div class="main-content">
        <div class="page-title">PO File Converter</div>
        <div class="page-subtitle">Convert PDF Purchase Orders to HTML Reports</div>
        <br>
        
        <div class="card">
            <form action="/upload_po" method="post" enctype="multipart/form-data" id="uploadForm">
                <div class="upload-zone" id="dropZone">
                    <div class="upload-icon"><i class="fa-solid fa-cloud-arrow-up"></i></div>
                    <div class="upload-text">Drag & Drop PDF Files Here</div>
                    <div class="upload-hint">or click to browse files</div>
                    <input type="file" name="file" multiple accept=".pdf" id="fileInput" style="display: none;">
                </div>
                <div id="file-count"></div>
                
                <div class="input-group" style="margin-top: 20px;">
                    <label>Booking Reference (Optional)</label>
                    <input type="text" name="booking_ref" placeholder="Enter Booking Ref for History...">
                </div>
                
                <button type="submit" id="processBtn" style="margin-top: 20px; display: none;">
                    Process Files
                </button>
            </form>
        </div>
    </div>

    <div id="loading-overlay">
        <div class="spinner-container"><div class="spinner"></div><div class="spinner-inner"></div></div>
        <div class="anim-text">ANALYZING PDF</div>
    </div>

    <script>
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('active'); }
        
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const fileCount = document.getElementById('file-count');
        const processBtn = document.getElementById('processBtn');
        const form = document.getElementById('uploadForm');
        
        dropZone.addEventListener('click', () => fileInput.click());
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            fileInput.files = e.dataTransfer.files;
            updateUI();
        });
        
        fileInput.addEventListener('change', updateUI);
        
        function updateUI() {
            if (fileInput.files.length > 0) {
                fileCount.textContent = fileInput.files.length + " file(s) selected";
                processBtn.style.display = 'block';
            }
        }
        
        form.addEventListener('submit', () => {
            document.getElementById('loading-overlay').style.display = 'flex';
        });
    </script>
</body>
</html>
"""
# ==============================================================================
# FLASK ROUTING LOGIC (CORE APPLICATION)
# ==============================================================================

@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_TEMPLATE)

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
        session['permissions'] = users_db[username]['permissions']
        
        # Update last login
        now = get_bd_time()
        users_db[username]['last_login'] = now.strftime('%d-%m-%Y %I:%M %p')
        save_users(users_db)
        
        return redirect(url_for('dashboard'))
    else:
        return render_template_string(LOGIN_TEMPLATE, error="Invalid Username or Password")

@app.route('/logout')
def logout():
    if session.get('user'):
        # Calculate duration logic could go here
        pass
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    # Reload permissions in case of admin update
    users_db = load_users()
    current_user = session.get('user')
    if current_user in users_db:
        session['permissions'] = users_db[current_user]['permissions']
        session['role'] = users_db[current_user]['role']
    
    stats_summary = get_dashboard_summary_v2()
    
    return render_template_string(
        DASHBOARD_TEMPLATE,
        user=session.get('user'),
        role=session.get('role'),
        permissions=session.get('permissions'),
        stats=stats_summary,
        now=get_bd_time().strftime('%d-%b-%Y %I:%M %p')
    )

# ------------------------------------------------------------------------------
# CLOSING REPORT ROUTES
# ------------------------------------------------------------------------------
@app.route('/download_closing', methods=['POST'])
def download_closing():
    if not session.get('logged_in'): 
        return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no', '').strip()
    if not ref_no:
        flash("Please enter a Reference Number", "error")
        return redirect(url_for('dashboard'))
    
    try:
        report_data = fetch_closing_report_data(ref_no)
        
        if report_data:
            excel_file = create_formatted_excel_report(report_data, ref_no)
            
            # Update Statistics
            update_stats(ref_no, session.get('user'))
            
            filename = f"Closing_Report_{ref_no.upper()}_{get_bd_date_str()}.xlsx"
            
            return send_file(
                excel_file,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            flash(f"Data not found for Ref: {ref_no}", "error")
            return redirect(url_for('dashboard'))
            
    except Exception as e:
        flash(f"System Error: {str(e)}", "error")
        return redirect(url_for('dashboard'))

# ------------------------------------------------------------------------------
# ACCESSORIES ROUTES
# ------------------------------------------------------------------------------
@app.route('/accessories')
def accessories_dashboard():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions'): 
        flash("Access Denied", "error")
        return redirect(url_for('dashboard'))
    
    bookings = get_all_accessories_bookings()
    
    return render_template_string(
        ACCESSORIES_TEMPLATE,
        bookings=bookings,
        user=session.get('user'),
        stats=get_dashboard_summary_v2()
    )

@app.route('/add_booking', methods=['POST'])
def add_booking():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    ref_no = request.form.get('ref_no', '').strip()
    if ref_no:
        db_acc = load_accessories_db()
        if ref_no not in db_acc:
            db_acc[ref_no] = {
                'created_by': session.get('user'),
                'created_at': get_bd_time().isoformat(),
                'challans': [],
                'colors': [],
                'buyer': 'Syncing...',
                'style': 'Syncing...',
                'last_api_call': None
            }
            save_accessories_db(db_acc)
            # Try to fetch initial data
            check_and_refresh_colors(ref_no, db_acc)
            flash(f"Booking {ref_no} initialized!", "success")
        else:
            flash("Booking already exists!", "error")
            
    return redirect(url_for('accessories_dashboard'))

@app.route('/view_booking/<ref_no>')
def view_booking(ref_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    db_acc = load_accessories_db()
    if ref_no not in db_acc:
        flash("Booking not found", "error")
        return redirect(url_for('accessories_dashboard'))
    
    # Auto refresh logic
    check_and_refresh_colors(ref_no, db_acc)
    # Reload after refresh
    db_acc = load_accessories_db()
    data = db_acc[ref_no]
    
    # Simple View Template (Inline for brevity in this part)
    VIEW_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Booking View | {{ ref }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        """ + COMMON_STYLES + """
    </head>
    <body>
        <div class="main-content" style="margin-left:0; width:100%;">
            <a href="/accessories" class="action-btn" style="margin-bottom: 20px;"><i class="fa-solid fa-arrow-left"></i> Back</a>
            
            <div class="header-section">
                <div>
                    <div class="page-title">{{ ref }}</div>
                    <div class="page-subtitle">{{ data.buyer }} | {{ data.style }}</div>
                </div>
                <button onclick="document.getElementById('addChallanModal').style.display='flex'" style="width:auto;">
                    <i class="fa-solid fa-plus"></i> Add Challan
                </button>
            </div>

            <div class="stats-grid">
                <div class="card stat-card">
                    <div class="stat-info">
                        <h3>{{ total_qty }}</h3>
                        <p>Total Received Qty</p>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="section-header"><span>CHALLAN HISTORY</span></div>
                <table class="dark-table">
                    <thead><th>Date</th><th>Challan No</th><th>Color</th><th>Size</th><th>Qty</th><th>Action</th></thead>
                    <tbody>
                        {% for c in data.challans %}
                        <tr>
                            <td>{{ c.date }}</td>
                            <td>{{ c.challan_no }}</td>
                            <td>{{ c.color }}</td>
                            <td>{{ c.size }}</td>
                            <td>{{ c.qty }}</td>
                            <td><a href="/delete_challan/{{ ref }}/{{ loop.index0 }}" style="color:red;">Delete</a></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Add Challan Modal -->
        <div id="addChallanModal" class="welcome-modal">
            <div class="welcome-content">
                <h3>Add New Challan</h3>
                <form action="/add_challan/{{ ref }}" method="post">
                    <div class="input-group">
                        <label>Date</label>
                        <input type="date" name="date" required>
                    </div>
                    <div class="input-group">
                        <label>Challan No</label>
                        <input type="text" name="challan_no" required>
                    </div>
                    <div class="input-group">
                        <label>Color</label>
                        <select name="color">
                            {% for col in data.colors %}
                            <option value="{{ col }}">{{ col }}</option>
                            {% endfor %}
                        </select>
                    </div>
                     <div class="input-group">
                        <label>Size</label>
                        <input type="text" name="size" placeholder="e.g., XL or ALL" required>
                    </div>
                    <div class="input-group">
                        <label>Quantity</label>
                        <input type="number" name="qty" required>
                    </div>
                    <div style="display:flex; gap:10px;">
                        <button type="button" onclick="document.getElementById('addChallanModal').style.display='none'" style="background:#333;">Cancel</button>
                        <button type="submit">Save</button>
                    </div>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    
    total_qty = sum([int(c['qty']) for c in data.get('challans', [])])
    
    return render_template_string(
        VIEW_TEMPLATE, 
        ref=ref_no, 
        data=data, 
        total_qty=total_qty,
        user=session.get('user')
    )

@app.route('/add_challan/<ref_no>', methods=['POST'])
def add_challan(ref_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    db_acc = load_accessories_db()
    if ref_no in db_acc:
        # Convert HTML date yyyy-mm-dd to dd-mm-yyyy
        raw_date = request.form.get('date')
        fmt_date = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%d-%m-%Y')
        
        new_challan = {
            "date": fmt_date,
            "challan_no": request.form.get('challan_no'),
            "color": request.form.get('color'),
            "size": request.form.get('size'),
            "qty": int(request.form.get('qty')),
            "added_by": session.get('user'),
            "added_at": get_bd_time().isoformat()
        }
        db_acc[ref_no]['challans'].insert(0, new_challan)
        save_accessories_db(db_acc)
        flash("Challan Added Successfully", "success")
        
    return redirect(url_for('view_booking', ref_no=ref_no))

@app.route('/delete_challan/<ref_no>/<int:index>')
def delete_challan(ref_no, index):
    if not session.get('logged_in'): return redirect(url_for('index'))
    # Only admin or allowed users should delete - simplified here
    if session.get('role') != 'admin':
        flash("Permission Denied", "error")
        return redirect(url_for('view_booking', ref_no=ref_no))
        
    db_acc = load_accessories_db()
    if ref_no in db_acc and len(db_acc[ref_no]['challans']) > index:
        db_acc[ref_no]['challans'].pop(index)
        save_accessories_db(db_acc)
        flash("Challan Deleted", "success")
        
    return redirect(url_for('view_booking', ref_no=ref_no))

# ------------------------------------------------------------------------------
# PO SHEET PDF ROUTES
# ------------------------------------------------------------------------------
@app.route('/po_sheet')
def po_sheet_index():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'po_sheet' not in session.get('permissions'):
        flash("Access Denied", "error")
        return redirect(url_for('dashboard'))
        
    return render_template_string(PO_UPLOAD_TEMPLATE)

@app.route('/upload_po', methods=['POST'])
def upload_po():
    if not session.get('logged_in'): return redirect(url_for('index'))
    
    uploaded_files = request.files.getlist("file")
    booking_ref = request.form.get("booking_ref", "N/A")
    
    if not uploaded_files or uploaded_files[0].filename == '':
        flash("No file selected", "error")
        return redirect(url_for('po_sheet_index'))

    # Clean uploads folder
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        shutil.rmtree(app.config['UPLOAD_FOLDER'])
    os.makedirs(app.config['UPLOAD_FOLDER'])

    final_tables = []
    final_meta = {}
    grand_total_qty = 0
    file_count = 0

    try:
        for file in uploaded_files:
            if file and file.filename.endswith('.pdf'):
                file_count += 1
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)

                extracted_data, metadata = extract_data_dynamic(filepath)
                if not final_meta and metadata: final_meta = metadata
                
                # If extracted data is empty, skip
                if not extracted_data: continue

                df = pd.DataFrame(extracted_data)
                
                # Pivot Logic
                if not df.empty:
                    df['Size_Index'] = df['Size'].apply(lambda x: sort_sizes([x])[0][0] if sort_sizes([x]) else 999)
                    
                    pivot_df = df.pivot_table(
                        index='Color', columns='Size', values='Quantity', aggfunc='sum'
                    ).fillna(0).astype(int)
                    
                    # Sort Columns (Sizes)
                    sorted_columns = sort_sizes(pivot_df.columns.tolist())
                    pivot_df = pivot_df[sorted_columns]
                    
                    # Add Totals
                    pivot_df['Total'] = pivot_df.sum(axis=1)
                    grand_total_qty += pivot_df['Total'].sum()
                    
                    # Additional Columns
                    pivot_df['3% Order Qty'] = (pivot_df['Total'] * 1.03).round().astype(int)
                    pivot_df['Actual Qty'] = 0
                    
                    # Format HTML Table
                    html_table = pivot_df.to_html(classes='table table-bordered', border=0)
                    final_tables.append({'color': f"File: {file.filename}", 'table': html_table})

        # Update Statistics
        update_po_stats(session.get('user'), file_count, booking_ref)
        
        final_meta['generated_at'] = get_bd_time().strftime('%d-%b-%Y %I:%M %p')

        return render_template_string(
            PO_REPORT_TEMPLATE,
            tables=final_tables,
            meta=final_meta,
            grand_total=f"{grand_total_qty:,}"
        )

    except Exception as e:
        flash(f"Error processing files: {str(e)}", "error")
        return redirect(url_for('po_sheet_index'))

# ------------------------------------------------------------------------------
# USER MANAGEMENT ROUTES (Simplified)
# ------------------------------------------------------------------------------
@app.route('/manage_users')
def manage_users():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    
    users = load_users()
    
    # Template for user management (Inline for brevity)
    MANAGE_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head><title>Users</title>""" + COMMON_STYLES + """</head>
    <body>
        <div class="main-content" style="margin-left:0; width:100%;">
            <a href="/dashboard" class="action-btn">Back</a>
            <div class="page-title">User Management</div>
            <div class="card">
                <table class="dark-table">
                    <thead><th>User</th><th>Role</th><th>Last Login</th></thead>
                    <tbody>
                        {% for name, data in users.items() %}
                        <tr>
                            <td>{{ name }}</td>
                            <td>{{ data.role }}</td>
                            <td>{{ data.last_login }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(MANAGE_TEMPLATE, users=users)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == '__main__':
    # Render provides PORT via environment variable
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' is required for external access in containers
    app.run(host='0.0.0.0', port=port)

