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
# স্পেস রিমুভ করা হয়েছে কানেকশন স্ট্রিং থেকে
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
        
        .section-header .actions {
            display: flex;
            gap: 10px;
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
        
        button, .btn { 
            width: auto;
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
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        button.full-width {
            width: 100%;
        }
        
        button::before, .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: 0.5s;
        }

        button:hover::before, .btn:hover::before { left: 100%; }

        button:hover, .btn:hover { 
            transform: translateY(-3px);
            box-shadow: 0 10px 30px var(--accent-orange-glow);
        }

        button:active, .btn:active {
            transform: translateY(0);
        }
        
        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
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
        
        .badge-green { background: rgba(16, 185, 129, 0.15); color: #34D399; }
        .badge-red { background: rgba(239, 68, 68, 0.15); color: #F87171; }
        .badge-yellow { background: rgba(245, 158, 11, 0.15); color: #FBBF24; }
        .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60A5FA; }
        
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
        .perm-checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
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
            min-width: 120px;
        }

        .perm-checkbox:hover {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0.05);
        }

        .perm-checkbox input {
            width: auto;
            margin-right: 10px;
            accent-color: var(--accent-orange);
            transform: scale(1.2);
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
        
        @media (max-width: 900px) {
            .grid-3, .grid-4 { grid-template-columns: repeat(2, 1fr); }
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
            align-items: flex-start; /* Aligns to top */
            padding-top: 5vh;
            overflow-y: auto;
        }
        
        .modal-overlay.active {
            display: flex;
        }
        
        .modal-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 30px;
            max-width: 600px;
            width: 90%;
            animation: modalSlideIn 0.3s ease-out;
            margin-bottom: 5vh;
        }

        .modal-content.modal-lg {
            max-width: 900px;
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
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .modal-title {
            font-size: 20px;
            font-weight: 700;
            color: white;
        }
        
        .modal-close {
            width: 36px;
            height: 36px;
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
            transform: rotate(90deg);
        }

        .modal-footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: flex-end;
            gap: 12px;
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
        
        .empty-state i, .empty-state .lottie-player {
            font-size: 60px;
            opacity: 0.8;
            margin: 0 auto 20px;
            display: block;
        }
        
        .empty-state p {
            font-size: 16px;
            margin-bottom: 20px;
        }
        
        /* Current Entry Indicator - নতুন যোগ করা হয়েছে */
        .current-entry {
            background: rgba(255, 122, 0, 0.1) !important;
            border-left: 3px solid var(--accent-orange) !important;
        }
        
        .current-entry .status-cell {
            color: var(--accent-orange) !important;
        }
        
        /* API Cache Indicator */
        .cache-indicator {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }
        
        .cache-fresh {
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
        }
        
        .cache-stale {
            background: rgba(245, 158, 11, 0.1);
            color: #FBBF24;
        }

        /* Invoice/Estimate Creation specific styles */
        #item-list tr .action-cell {
            opacity: 0;
            transition: opacity 0.3s;
        }
        #item-list tr:hover .action-cell {
            opacity: 1;
        }

        .summary-card {
            background: var(--bg-card);
            border-radius: var(--card-radius);
            padding: 24px;
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
        }
        .summary-row:last-child {
            border-bottom: none;
        }
        .summary-row span:first-child {
            color: var(--text-secondary);
        }
        .summary-row span:last-child {
            font-weight: 600;
            color: var(--text-primary);
        }
        .summary-total {
            font-size: 18px;
            font-weight: 700;
            padding-top: 20px;
            margin-top: 10px;
            border-top: 2px solid var(--accent-orange);
            color: var(--accent-orange);
        }
        .summary-total span:last-child {
            font-size: 22px;
        }

        /* Login Screen Specific Styles */
        .login-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100vw;
            height: 100vh;
            padding: 20px;
            background: var(--gradient-dark);
            flex-direction: column;
            position: relative;
        }
        
        .login-card {
            width: 100%;
            max-width: 450px;
            padding: 40px;
            z-index: 2;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-logo {
            font-size: 40px;
            color: var(--accent-orange);
            margin-bottom: 15px;
            filter: drop-shadow(0 0 15px var(--accent-orange-glow));
        }
        
        .login-title {
            font-size: 24px;
            font-weight: 800;
            color: white;
            margin-bottom: 8px;
        }
        
        .login-subtitle {
            color: var(--text-secondary);
        }
        
        /* Print Styles */
        @media print {
            body { background: #fff !important; color: #000 !important; }
            .no-print { display: none !important; }
            .main-content { margin-left: 0 !important; width: 100% !important; padding: 0 !important; }
            .print-container {
                padding: 0;
                box-shadow: none !important;
                border: none !important;
                background: #fff !important;
            }
            .print-header h1 { color: #000 !important; }
            .print-header p, .print-meta span { color: #555 !important; }
            .print-table th, .print-table td {
                color: #000 !important;
                border-color: #ddd !important;
            }
            .print-summary span { color: #333 !important; }
            .print-summary .print-total { color: #000 !important; }
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
        return record.get('data', default_users)
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
        return record.get('data', {"downloads": [], "last_booking": "None"})
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
    data['downloads'] = data['downloads'][:3000] # Limit history
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
    data['downloads'] = data['downloads'][:3000] # Limit history
    save_stats(data)

def load_accessories_db():
    record = accessories_col.find_one({"_id": "accessories_data"})
    return record.get('data', {}) if record else {}

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
        return record.get('data', default_users)
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
    return record.get('data', []) if record else []

def save_store_products(products):
    store_products_col.replace_one(
        {"_id": "products_data"},
        {"_id": "products_data", "data": products},
        upsert=True
    )

def load_store_customers():
    record = store_customers_col.find_one({"_id": "customers_data"})
    return record.get('data', []) if record else []

def save_store_customers(customers):
    store_customers_col.replace_one(
        {"_id": "customers_data"},
        {"_id": "customers_data", "data": customers},
        upsert=True
    )

def load_store_invoices():
    record = store_invoices_col.find_one({"_id": "invoices_data"})
    return record.get('data', []) if record else []

def save_store_invoices(invoices):
    store_invoices_col.replace_one(
        {"_id": "invoices_data"},
        {"_id": "invoices_data", "data": invoices},
        upsert=True
    )

def load_store_estimates():
    record = store_estimates_col.find_one({"_id": "estimates_data"})
    return record.get('data', []) if record else []

def save_store_estimates(estimates):
    store_estimates_col.replace_one(
        {"_id": "estimates_data"},
        {"_id": "estimates_data", "data": estimates},
        upsert=True
    )

def load_store_payments():
    record = store_payments_col.find_one({"_id": "payments_data"})
    return record.get('data', []) if record else []

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

    # 2. Accessories Today & Analytics - LIFETIME COUNT
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

    # 3. Closing & PO - LIFETIME COUNT & Analytics
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
            inv_dt = datetime.strptime(inv_date, '%Y-%m-%d')
            if inv_dt.strftime('%m-%Y') == current_month:
                monthly_sales += inv.get('total', 0) - inv.get('paid', 0)
        except:
            pass
        total_due += inv.get('due', 0)
    
    recent_invoices = sorted(invoices, key=lambda x: x.get('date', '1970-01-01'), reverse=True)[:5]
    
    return {
        "products_count": len(products),
        "customers_count": len(customers),
        "invoices_count": len(invoices),
        "estimates_count": len(estimates),
        "monthly_sales": f"{monthly_sales:,.2f}",
        "total_due": f"{total_due:,.2f}",
        "recent_invoices": recent_invoices,
    }

# ==============================================================================
# API CACHING HELPER - নতুন ফাংশন যোগ করা হয়েছে
# ==============================================================================

def should_refresh_api_data(last_api_call_time):
    """২৪ ঘন্টা পরে API রিফ্রেশ করা উচিত কিনা চেক করে"""
    if not last_api_call_time:
        return True
    try:
        # Assuming last_api_call_time is already timezone-aware
        last_call = datetime.fromisoformat(last_api_call_time)
        now = get_bd_time()
        time_diff = now - last_call
        return time_diff.total_seconds() > 86400  # 24 hours
    except (ValueError, TypeError):
        return True

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
    """API থেকে ক্লোজিং রিপোর্ট ডাটা ফেচ করে"""
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

def fetch_closing_report_data_with_cache(internal_ref_no):
    """
    ক্যাশিং সহ API থেকে ডাটা ফেচ করে।
    """
    acc_db = load_accessories_db()
    ref = internal_ref_no.upper()
    
    if ref in acc_db:
        last_api_call = acc_db[ref].get('last_api_call')
        cached_colors = acc_db[ref].get('colors', [])
        
        if not should_refresh_api_data(last_api_call) and cached_colors:
            print(f"[CACHE HIT] Using cached data for {ref}")
            return {
                'colors': cached_colors,
                'buyer': acc_db[ref].get('buyer', 'N/A'),
                'style': acc_db[ref].get('style', 'N/A'),
                'from_cache': True,
                'last_updated': last_api_call
            }
    
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
            if block.get('style') != 'N/A':
                style = block.get('style')
    
    if ref not in acc_db:
        acc_db[ref] = {
            "buyer": buyer,
            "style": style,
            "colors": colors,
            "challans": [],
            "last_api_call": get_bd_time().isoformat()
        }
    else:
        acc_db[ref]['buyer'] = buyer if buyer != 'N/A' else acc_db[ref].get('buyer', 'N/A')
        acc_db[ref]['style'] = style if style != 'N/A' else acc_db[ref].get('style', 'N/A')
        acc_db[ref]['colors'] = colors if colors else acc_db[ref].get('colors', [])
        acc_db[ref]['last_api_call'] = get_bd_time().isoformat()
    
    save_accessories_db(acc_db)
    
    return {
        'colors': sorted(colors),
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
        print(f"Parse error: {e}")
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
# HTML টেমপ্লেট স্ট্রিং (পেজ রেন্ডারিং)
# ==============================================================================

# ----------------- MAIN LAYOUT -----------------
LAYOUT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - CCBL Office</title>
    {{ COMMON_STYLES | safe }}
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/js/select2.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/select2/4.0.13/css/select2.min.css" rel="stylesheet" />
</head>
<body>
    <div id="particles-js"></div>
    <div class="animated-bg"></div>

    <!-- Sidebar -->
    <aside class="sidebar" id="sidebar">
        <div class="brand-logo">
            <i class="fa-solid fa-bolt"></i>
            <span>CCBL</span> Office
        </div>
        <nav class="nav-menu">
            {% if session.get('user_type') == 'main' %}
                <a href="{{ url_for('dashboard') }}" class="nav-link {% if active_page == 'dashboard' %}active{% endif %}">
                    <i class="fa-solid fa-border-all"></i> Dashboard
                </a>
                {% if 'closing' in session['permissions'] %}
                <a href="{{ url_for('closing_report_page') }}" class="nav-link {% if active_page == 'closing' %}active{% endif %}">
                    <i class="fa-solid fa-file-excel"></i> Closing Report
                </a>
                {% endif %}
                {% if 'po_sheet' in session['permissions'] %}
                <a href="{{ url_for('po_sheet_page') }}" class="nav-link {% if active_page == 'po_sheet' %}active{% endif %}">
                    <i class="fa-solid fa-file-pdf"></i> PO Sheet
                </a>
                {% endif %}
                {% if 'accessories' in session['permissions'] %}
                <a href="{{ url_for('accessories_challan_page') }}" class="nav-link {% if active_page == 'accessories' %}active{% endif %}">
                    <i class="fa-solid fa-boxes-stacked"></i> Accessories
                </a>
                {% endif %}
                {% if 'view_history' in session['permissions'] %}
                <a href="{{ url_for('history_page') }}" class="nav-link {% if active_page == 'history' %}active{% endif %}">
                    <i class="fa-solid fa-clock-rotate-left"></i> History
                </a>
                {% endif %}
                {% if 'user_manage' in session['permissions'] %}
                <a href="{{ url_for('user_management') }}" class="nav-link {% if active_page == 'user_manage' %}active{% endif %}">
                    <i class="fa-solid fa-users-gear"></i> User Manage
                </a>
                {% endif %}
                {% if 'store' in session['permissions'] %}
                <a href="{{ url_for('store_dashboard') }}" class="nav-link {% if active_page.startswith('store_') %}active{% endif %}">
                    <i class="fa-solid fa-store"></i> Store Panel
                </a>
                {% endif %}
            {% elif session.get('user_type') == 'store' %}
                <a href="{{ url_for('store_dashboard') }}" class="nav-link {% if active_page == 'store_dashboard' %}active{% endif %}">
                    <i class="fa-solid fa-border-all"></i> Dashboard
                </a>
                {% if 'products' in session['permissions'] %}
                <a href="{{ url_for('store_products') }}" class="nav-link {% if active_page == 'store_products' %}active{% endif %}">
                    <i class="fa-solid fa-box-archive"></i> Products
                </a>
                {% endif %}
                {% if 'customers' in session['permissions'] %}
                <a href="{{ url_for('store_customers') }}" class="nav-link {% if active_page == 'store_customers' %}active{% endif %}">
                    <i class="fa-solid fa-user-tag"></i> Customers
                </a>
                {% endif %}
                {% if 'invoices' in session['permissions'] %}
                <a href="{{ url_for('store_invoices') }}" class="nav-link {% if active_page == 'store_invoices' %}active{% endif %}">
                    <i class="fa-solid fa-file-invoice-dollar"></i> Invoices
                </a>
                {% endif %}
                {% if 'estimates' in session['permissions'] %}
                <a href="{{ url_for('store_estimates') }}" class="nav-link {% if active_page == 'store_estimates' %}active{% endif %}">
                    <i class="fa-solid fa-file-alt"></i> Estimates
                </a>
                {% endif %}
                {% if 'user_manage' in session['permissions'] %}
                <a href="{{ url_for('store_user_management') }}" class="nav-link {% if active_page == 'store_user_manage' %}active{% endif %}">
                    <i class="fa-solid fa-users-cog"></i> User Manage
                </a>
                {% endif %}
                <a href="{{ url_for('dashboard') }}" class="nav-link">
                    <i class="fa-solid fa-arrow-left"></i> Back to Main App
                </a>
            {% endif %}
        </nav>
        <div class="sidebar-footer">
            <a href="{{ url_for('logout') }}" class="nav-link" style="color: var(--accent-red);"><i class="fa-solid fa-right-from-bracket"></i> Logout</a>
            <p style="margin-top: 15px;">© {{ get_bd_time().year }} CCBL</p>
        </div>
    </aside>
    
    <!-- Mobile Toggle Button -->
    <button class="mobile-toggle" id="mobile-toggle"><i class="fa-solid fa-bars"></i></button>

    <!-- Main Content -->
    <main class="main-content">
        {% block content %}{% endblock %}
    </main>

    <!-- Loading Overlay -->
    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner"></div>
            <div class="spinner-inner"></div>
        </div>
        <div class="checkmark-container">
            <div class="checkmark-circle"></div>
            <p class="anim-text">Success!</p>
        </div>
        <div class="fail-container">
            <div class="fail-circle"></div>
            <p class="anim-text">Failed!</p>
        </div>
        <p class="loading-text">Processing...</p>
    </div>

    <!-- Welcome Modal -->
    {% if session.get('show_welcome') %}
    <div class="welcome-modal" id="welcome-modal" style="display: flex;">
        <div class="welcome-content">
            <div class="welcome-icon" style="color: var(--accent-orange);">
                <i class="fas fa-hand-sparkles"></i>
            </div>
            <p class="welcome-greeting">Hello, {{ session.get('username') }}!</p>
            <h2 class="welcome-title">Welcome to <span>CCBL Office</span></h2>
            <p class="welcome-message">Your all-in-one hub for managing reports, inventory, and more. Ready to boost your productivity?</p>
            <button class="welcome-close" id="close-welcome">Let's Get Started</button>
        </div>
    </div>
    {% set s = session.pop('show_welcome', None) %}
    {% endif %}

    <!-- Modal Overlay -->
    <div class="modal-overlay" id="modal-overlay">
        <div class="modal-content" id="modal-content-main">
            <!-- Dynamic content will be loaded here -->
        </div>
    </div>
    
    <!-- Global JS -->
    {% block scripts %}{% endblock %}
</body>
</html>
"""

# ----------------- LOGIN PAGE -----------------
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - CCBL Office</title>
    {{ COMMON_STYLES | safe }}
</head>
<body>
    <div id="particles-js"></div>
    <div class="animated-bg"></div>
    <div class="login-wrapper">
        <div class="card login-card glass">
            <div class="login-header">
                <div class="login-logo"><i class="fa-solid fa-bolt"></i></div>
                <h1 class="login-title">{{ title }}</h1>
                <p class="login-subtitle">Sign in to access the dashboard</p>
            </div>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <form method="POST" action="">
                <div class="input-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" placeholder="e.g., admin" required>
                </div>
                <div class="input-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit" class="full-width ripple"><i class="fa-solid fa-right-to-bracket"></i> Login</button>
            </form>
            {% if "Store" not in title %}
            <div style="text-align: center; margin-top: 20px;">
                <a href="{{ url_for('store_login') }}" style="color: var(--accent-orange); text-decoration: none; font-weight: 500;">
                    Go to Store Login <i class="fa-solid fa-arrow-right"></i>
                </a>
            </div>
            {% else %}
            <div style="text-align: center; margin-top: 20px;">
                <a href="{{ url_for('login') }}" style="color: var(--accent-orange); text-decoration: none; font-weight: 500;">
                    <i class="fa-solid fa-arrow-left"></i> Back to Main Login
                </a>
            </div>
            {% endif %}
        </div>
        <p style="color: var(--text-secondary); margin-top: 30px; font-size: 13px;">© {{ get_bd_time().year }} Cotton Clothing (BD) Ltd. All rights reserved.</p>
    </div>
    {% block scripts %}{% endblock %}
</body>
</html>
"""

# ----------------- MAIN DASHBOARD -----------------
DASHBOARD_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-subtitle">Welcome back, {{ session.get('username') }}! Here's your real-time overview.</p>
    </div>
    <div class="status-badge">
        <div class="status-dot"></div>
        <span>System is <strong>Online</strong> & Healthy</span>
    </div>
</div>

<!-- Stats Grid -->
<div class="stats-grid">
    <div class="card stat-card" style="animation-delay: 0.1s;">
        <div class="stat-icon" style="color: var(--accent-orange);">
            <i class="fa-solid fa-file-excel"></i>
        </div>
        <div class="stat-info">
            <h3 class="count-up">{{ summary.closing.count }}</h3>
            <p>Closing Reports</p>
        </div>
    </div>
    <div class="card stat-card" style="animation-delay: 0.2s;">
        <div class="stat-icon" style="color: var(--accent-purple);">
            <i class="fa-solid fa-file-pdf"></i>
        </div>
        <div class="stat-info">
            <h3 class="count-up">{{ summary.po.count }}</h3>
            <p>PO Sheets</p>
        </div>
    </div>
    <div class="card stat-card" style="animation-delay: 0.3s;">
        <div class="stat-icon" style="color: var(--accent-green);">
            <i class="fa-solid fa-boxes-stacked"></i>
        </div>
        <div class="stat-info">
            <h3 class="count-up">{{ summary.accessories.count }}</h3>
            <p>Accessories Challans</p>
        </div>
    </div>
    <div class="card stat-card" style="animation-delay: 0.4s;">
        <div class="stat-icon" style="color: var(--accent-cyan);">
            <i class="fa-solid fa-users"></i>
        </div>
        <div class="stat-info">
            <h3 class="count-up">{{ summary.users.count }}</h3>
            <p>Active Users</p>
        </div>
    </div>
</div>

<!-- Dashboard Grid 2 -->
<div class="dashboard-grid-2">
    <!-- Activity Chart -->
    <div class="card">
        <div class="section-header">
            <span>Recent Activity (Last 45 Days)</span>
            <div class="realtime-indicator">
                <div class="realtime-dot"></div>
                Real-time
            </div>
        </div>
        <div class="chart-container">
            <canvas id="activityChart"></canvas>
        </div>
    </div>

    <!-- Today's Activity -->
    <div class="card">
        <div class="section-header">
            <span>Activity Today</span>
            <div class="time-badge">
                <i class="fa-regular fa-calendar-check"></i>
                <span>{{ get_bd_date_str() }}</span>
            </div>
        </div>
        <div class="progress-item">
            <div class="progress-header">
                <span>Closing Reports</span>
                <span class="progress-value">{{ summary.closing.details|length }}</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill progress-orange" style="width: {{ (summary.closing.details|length / 20 * 100)|int }}%;"></div>
            </div>
        </div>
        <div class="progress-item">
            <div class="progress-header">
                <span>PO Sheets</span>
                <span class="progress-value">{{ summary.po.details|length }}</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill progress-purple" style="width: {{ (summary.po.details|length / 20 * 100)|int }}%;"></div>
            </div>
        </div>
        <div class="progress-item" style="margin-bottom:0;">
            <div class="progress-header">
                <span>Accessories Challans</span>
                <span class="progress-value">{{ summary.accessories.details|length }}</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar-fill progress-green" style="width: {{ (summary.accessories.details|length / 20 * 100)|int }}%;"></div>
            </div>
        </div>
    </div>
</div>

<!-- Recent History Table -->
<div class="card">
    <div class="section-header">
        <span>Recent History</span>
        <a href="{{ url_for('history_page') }}" class="btn btn-sm btn-secondary">View All <i class="fa-solid fa-arrow-right"></i></a>
    </div>
    {% if summary.history %}
    <table class="dark-table">
        <thead>
            <tr>
                <th>Type</th>
                <th>Reference/Count</th>
                <th>User</th>
                <th>Date & Time</th>
            </tr>
        </thead>
        <tbody>
        {% for item in summary.history[:7] %}
            <tr class="animate__animated animate__fadeInUp" style="animation-delay: {{ loop.index * 0.05 }}s;">
                <td>
                    {% if item.type == 'Closing Report' %}
                        <span class="table-badge" style="background: rgba(255, 122, 0, 0.15); color: #FF9A40;"><i class="fa-solid fa-file-excel"></i> {{ item.type }}</span>
                    {% elif item.type == 'PO Sheet' %}
                        <span class="table-badge" style="background: rgba(139, 92, 246, 0.15); color: #A78BFA;"><i class="fa-solid fa-file-pdf"></i> {{ item.type }}</span>
                    {% else %}
                        <span class="table-badge" style="background: rgba(16, 185, 129, 0.15); color: #34D399;"><i class="fa-solid fa-boxes-stacked"></i> {{ item.type }}</span>
                    {% endif %}
                </td>
                <td>{{ item.ref if item.ref else (item.file_count ~ ' files') }}</td>
                <td><i class="fa-solid fa-user-circle" style="color:var(--text-secondary); margin-right: 5px;"></i> {{ item.user }}</td>
                <td>{{ item.date }} at {{ item.time }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
        <div class="empty-state">
            <i class="fa-solid fa-history"></i>
            <p>No history records found yet.</p>
        </div>
    {% endif %}
</div>
{% endblock %}
{% block scripts %}
<script>
document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('activityChart').getContext('2d');
    
    // Create gradient
    const gradientOrange = ctx.createLinearGradient(0, 0, 0, 300);
    gradientOrange.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
    gradientOrange.addColorStop(1, 'rgba(255, 122, 0, 0)');
    
    const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300);
    gradientPurple.addColorStop(0, 'rgba(139, 92, 246, 0.5)');
    gradientPurple.addColorStop(1, 'rgba(139, 92, 246, 0)');
    
    const gradientGreen = ctx.createLinearGradient(0, 0, 0, 300);
    gradientGreen.addColorStop(0, 'rgba(16, 185, 129, 0.5)');
    gradientGreen.addColorStop(1, 'rgba(16, 185, 129, 0)');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: {{ summary.chart.labels | tojson }},
            datasets: [{
                label: 'Closing',
                data: {{ summary.chart.closing | tojson }},
                borderColor: 'var(--accent-orange)',
                backgroundColor: gradientOrange,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: 'var(--accent-orange)',
                pointRadius: 4,
                pointHoverRadius: 6
            }, {
                label: 'PO Sheet',
                data: {{ summary.chart.po | tojson }},
                borderColor: 'var(--accent-purple)',
                backgroundColor: gradientPurple,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: 'var(--accent-purple)',
                pointRadius: 4,
                pointHoverRadius: 6
            }, {
                label: 'Accessories',
                data: {{ summary.chart.acc | tojson }},
                borderColor: 'var(--accent-green)',
                backgroundColor: gradientGreen,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: 'var(--accent-green)',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: 'var(--text-secondary)' } },
                tooltip: {
                    backgroundColor: 'var(--bg-card)',
                    titleColor: 'var(--text-primary)',
                    bodyColor: 'var(--text-secondary)',
                    borderColor: 'var(--border-color)',
                    borderWidth: 1,
                    padding: 10,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: 'var(--text-secondary)', stepSize: 1 }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: 'var(--text-secondary)' }
                }
            }
        }
    });
});
</script>
{% endblock %}
"""

# ----------------- CLOSING/PO/ACCESSORIES PAGES -----------------
# (These remain largely the same from part 1, so they are condensed here)
CLOSING_REPORT_PAGE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Closing Report Generator</h1>
        <p class="page-subtitle">Enter an IR/IB number to generate a closing report.</p>
    </div>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}
{% endwith %}
<div class="card">
    <form method="POST" action="{{ url_for('closing_report_page') }}">
        <div class="input-group">
            <label for="ref_no">IR/IB Number</label>
            <input type="text" id="ref_no" name="ref_no" placeholder="e.g., CCBL-IB-24-1234" required value="{{ ref_no or '' }}">
        </div>
        <button type="submit" class="full-width ripple"><i class="fa-solid fa-cogs"></i> Generate Report</button>
    </form>
</div>
{% endblock %}
"""

PREVIEW_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Preview - {{ title }}</title>
    {{ COMMON_STYLES | safe }}
    <style>
        body { display: block; background: #333; }
        .preview-controls { 
            position: fixed; top: 0; left: 0; width: 100%; 
            background: var(--bg-card); padding: 15px; 
            display: flex; gap: 15px; justify-content: center;
            border-bottom: 1px solid var(--border-color);
            z-index: 100;
        }
        #pdf-preview { margin-top: 80px; text-align: center; }
        iframe { width: 80%; height: 85vh; border: 1px solid #555; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="preview-controls no-print">
        <h3 style="color: white; margin-right: auto;">Preview: {{ filename }}</h3>
        <a href="javascript:window.print()" class="btn btn-success"><i class="fa fa-print"></i> Print</a>
        <a href="{{ download_url }}" class="btn btn-primary"><i class="fa fa-download"></i> Download Excel</a>
        <a href="{{ back_url }}" class="btn btn-secondary"><i class="fa fa-arrow-left"></i> Back</a>
    </div>
    <div id="pdf-preview">
        <iframe src="{{ preview_url }}"></iframe>
    </div>
</body>
</html>
"""

PO_SHEET_PAGE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div><h1 class="page-title">PO Sheet Generator</h1><p class="page-subtitle">Upload PO PDFs to generate a consolidated Excel sheet.</p></div>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}
<div class="card">
    <form method="POST" enctype="multipart/form-data" id="po-form">
        <div class="input-group">
            <label>Upload PO Files (PDF)</label>
            <div class="upload-zone" id="upload-zone">
                <input type="file" name="po_files" id="po_files" multiple accept=".pdf" style="display:none;">
                <div class="upload-icon"><i class="fa-solid fa-cloud-arrow-up"></i></div>
                <div class="upload-text">Click to browse or drag & drop files here</div>
                <div class="upload-hint">You can select multiple PDF files at once</div>
            </div>
            <div id="file-count" style="margin-top: 15px; color: var(--accent-green); font-weight: 600;"></div>
        </div>
        <button type="submit" class="full-width ripple"><i class="fa-solid fa-cogs"></i> Generate PO Sheet</button>
    </form>
</div>
{% endblock %}
{% block scripts %}
<script>
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('po_files');
    const fileCount = document.getElementById('file-count');

    uploadZone.addEventListener('click', () => fileInput.click());
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      uploadZone.addEventListener(eventName, e => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
      uploadZone.addEventListener(eventName, () => uploadZone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      uploadZone.addEventListener(eventName, () => uploadZone.classList.remove('dragover'), false);
    });

    uploadZone.addEventListener('drop', e => {
      fileInput.files = e.dataTransfer.files;
      updateFileCount();
    });

    fileInput.addEventListener('change', updateFileCount);

    function updateFileCount() {
        const numFiles = fileInput.files.length;
        if (numFiles > 0) {
            fileCount.textContent = `${numFiles} file(s) selected.`;
        } else {
            fileCount.textContent = '';
        }
    }
</script>
{% endblock %}
"""

ACCESSORIES_CHALLAN_PAGE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div><h1 class="page-title">Accessories Challan</h1><p class="page-subtitle">Create and manage accessories challans.</p></div>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}
<div class="dashboard-grid-2">
    <div class="card">
        <form id="ref-form" method="POST" action="{{ url_for('accessories_challan_page') }}">
            <div class="input-group">
                <label for="ref_no">Enter IR/IB Number to load data</label>
                <input type="text" name="ref_no" id="ref_no" placeholder="e.g., CCBL-IB-24-1234" value="{{ ref_no or '' }}" required>
            </div>
            <button type="submit" name="action" value="load" class="full-width ripple"><i class="fa-solid fa-search"></i> Load Data</button>
        </form>
        {% if data %}
        <form id="challan-form" method="POST" action="{{ url_for('accessories_challan_page') }}" style="margin-top: 20px;">
            <input type="hidden" name="ref_no" value="{{ ref_no }}">
            <div class="input-group">
                <label>Select Colors</label>
                <div style="max-height: 150px; overflow-y: auto; background: rgba(255,255,255,0.03); border-radius: 12px; padding: 10px; border: 1px solid var(--border-color);">
                {% for color in data.colors %}
                    <label class="perm-checkbox" style="margin-bottom: 8px;">
                        <input type="checkbox" name="colors" value="{{ color }}"> <span>{{ color }}</span>
                    </label>
                {% endfor %}
                </div>
            </div>
            <div class="input-group">
                <label for="challan_qty">Challan Quantity (per color)</label>
                <input type="number" name="challan_qty" id="challan_qty" required placeholder="e.g., 500">
            </div>
            <div class="grid-2">
                <div class="input-group">
                    <label for="out_time">Out Time</label>
                    <input type="time" name="out_time" id="out_time" required>
                </div>
                <div class="input-group">
                    <label for="vehicle_no">Vehicle Number</label>
                    <input type="text" name="vehicle_no" id="vehicle_no" required placeholder="e.g., DHAKA-1234">
                </div>
            </div>
            <button type="submit" name="action" value="generate" class="full-width ripple btn-success"><i class="fa-solid fa-plus-circle"></i> Generate Challan</button>
        </form>
        {% endif %}
    </div>
    <div class="card">
        {% if data %}
            <div class="section-header">
                <span>Details for {{ ref_no }}</span>
                <span class="cache-indicator {{ 'cache-fresh' if data.from_cache else 'cache-stale' }}">
                    <i class="fa-solid {{ 'fa-check-circle' if data.from_cache else 'fa-cloud-download-alt' }}"></i>
                    {{ 'From Cache' if data.from_cache else 'Live Data' }}
                </span>
            </div>
            <p><strong>Buyer:</strong> {{ data.buyer }}</p>
            <p style="margin-top: 5px;"><strong>Style:</strong> {{ data.style }}</p>
            <hr style="border-color: var(--border-color); margin: 20px 0;">
        {% endif %}
        <div class="section-header">
            <span>Recent Challans for {{ ref_no }}</span>
        </div>
        {% if challans %}
        <div style="max-height: 300px; overflow-y:auto;">
        <table class="dark-table">
        {% for c in challans %}
            <tr><td>
                <strong>{{ c.qty }} pcs</strong> for {{ c.colors|join(', ') }}
                <br><small style="color: var(--text-secondary);">{{ c.date }} at {{ c.time }} | Vehicle: {{ c.vehicle_no }}</small>
            </td></tr>
        {% endfor %}
        </table>
        </div>
        {% else %}
        <div class="empty-state" style="padding:20px 0;">
            <i class="fa-solid fa-file-circle-xmark"></i>
            <p>No challans found for this reference.</p>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
"""

USER_MANAGEMENT_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div><h1 class="page-title">User Management</h1><p class="page-subtitle">Add, edit, or remove users and manage their permissions.</p></div>
    <button class="btn btn-primary" onclick="openModal('{{ url_for('add_user') }}')"><i class="fa-solid fa-user-plus"></i> Add New User</button>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}
<div class="card">
    <table class="dark-table">
        <thead><tr><th>Username</th><th>Role</th><th>Permissions</th><th>Created On</th><th>Last Login</th><th>Actions</th></tr></thead>
        <tbody>
            {% for username, details in users.items() %}
            <tr>
                <td><i class="fa-solid fa-user" style="margin-right:8px; color:var(--text-secondary);"></i> {{ username }}</td>
                <td><span class="table-badge">{{ details.role or 'user' }}</span></td>
                <td>
                    {% for perm in details.permissions or [] %}
                    <span class="table-badge" style="background: rgba(255,255,255,0.05); margin-right: 4px; margin-bottom: 4px;">{{ perm }}</span>
                    {% endfor %}
                </td>
                <td>{{ details.created_at or 'N/A' }}</td>
                <td>{{ details.last_login or 'Never' }}</td>
                <td class="action-cell">
                    <button onclick="openModal('{{ url_for('edit_user', username=username) }}')" class="action-btn btn-edit tooltip" data-tooltip="Edit"><i class="fa-solid fa-pencil-alt"></i></button>
                    {% if username != 'Admin' and username != session.get('username') %}
                    <form action="{{ url_for('delete_user', username=username) }}" method="POST" onsubmit="return confirm('Are you sure you want to delete this user?');" style="display:inline;">
                        <button type="submit" class="action-btn btn-del tooltip" data-tooltip="Delete"><i class="fa-solid fa-trash-alt"></i></button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

USER_FORM_MODAL_HTML = """
<form method="POST" action="{{ action_url }}">
    <div class="modal-header">
        <h2 class="modal-title">{{ 'Add' if 'add' in action_url else 'Edit' }} User</h2>
        <span class="modal-close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-body">
        <div class="input-group">
            <label for="username">Username</label>
            <input type="text" name="username" value="{{ user.username or '' }}" {{ 'readonly' if user.username }} required>
        </div>
        <div class="input-group">
            <label for="password">Password {% if 'edit' in action_url %}(Leave blank to keep unchanged){% endif %}</label>
            <input type="password" name="password" {{ 'required' if 'add' in action_url }}>
        </div>
        <div class="input-group">
            <label for="role">Role</label>
            <select name="role">
                <option value="user" {{ 'selected' if user.role == 'user' }}>User</option>
                <option value="admin" {{ 'selected' if user.role == 'admin' }}>Admin</option>
            </select>
        </div>
        <div class="input-group">
            <label>Permissions</label>
            <div class="perm-checkbox-group">
                {% for p in available_permissions %}
                <label class="perm-checkbox">
                    <input type="checkbox" name="permissions" value="{{ p }}" {{ 'checked' if p in (user.permissions or []) }}> <span>{{ p.replace('_', ' ')|title }}</span>
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-save"></i> Save User</button>
    </div>
</form>
"""

HISTORY_PAGE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div><h1 class="page-title">Activity History</h1><p class="page-subtitle">A log of all generated reports and sheets.</p></div>
</div>
<div class="card">
    <table class="dark-table">
        <thead><tr><th>Type</th><th>Details</th><th>User</th><th>Timestamp</th></tr></thead>
        <tbody>
        {% for item in history %}
            <tr>
                <td>
                    {% if item.type == 'Closing Report' %}<span class="table-badge" style="background: rgba(255, 122, 0, 0.15); color: #FF9A40;"><i class="fa-solid fa-file-excel"></i> {{ item.type }}</span>
                    {% elif item.type == 'PO Sheet' %}<span class="table-badge" style="background: rgba(139, 92, 246, 0.15); color: #A78BFA;"><i class="fa-solid fa-file-pdf"></i> {{ item.type }}</span>
                    {% else %}<span class="table-badge" style="background: rgba(16, 185, 129, 0.15); color: #34D399;"><i class="fa-solid fa-boxes-stacked"></i> {{ item.type }}</span>
                    {% endif %}
                </td>
                <td>
                    <strong>{{ item.ref if item.ref else ('PO files: ' ~ item.file_count) }}</strong>
                    {% if item.type == 'Accessories Challan' %}<br><small>{{ item.qty }} pcs for {{ item.colors|join(', ') }}</small>{% endif %}
                </td>
                <td><i class="fa-solid fa-user-circle"></i> {{ item.user }}</td>
                <td>{{ item.date }} at {{ item.time }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""


# ==============================================================================
# ==============================================================================
# ======================== STORE MANAGEMENT TEMPLATES ==========================
# ==============================================================================
# ==============================================================================

# ----------------- STORE DASHBOARD -----------------
STORE_DASHBOARD_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Store Dashboard</h1>
        <p class="page-subtitle">Manage your inventory, sales, and customers from one place.</p>
    </div>
    <div class="status-badge">
        <i class="fa-solid fa-store" style="color: var(--accent-orange);"></i>
        <span>Welcome, {{ session.get('username') }}!</span>
    </div>
</div>

<!-- Stats Grid -->
<div class="stats-grid">
    <div class="card stat-card">
        <div class="stat-icon" style="color: var(--accent-green);">
            <i class="fa-solid fa-dollar-sign"></i>
        </div>
        <div class="stat-info">
            <h3>{{ summary.monthly_sales }}</h3>
            <p>Sales This Month</p>
        </div>
    </div>
    <div class="card stat-card">
        <div class="stat-icon" style="color: var(--accent-red);">
            <i class="fa-solid fa-hand-holding-dollar"></i>
        </div>
        <div class="stat-info">
            <h3>{{ summary.total_due }}</h3>
            <p>Total Amount Due</p>
        </div>
    </div>
    <div class="card stat-card">
        <div class="stat-icon" style="color: var(--accent-purple);">
            <i class="fa-solid fa-file-invoice-dollar"></i>
        </div>
        <div class="stat-info">
            <h3>{{ summary.invoices_count }}</h3>
            <p>Total Invoices</p>
        </div>
    </div>
    <div class="card stat-card">
        <div class="stat-icon" style="color: var(--accent-cyan);">
            <i class="fa-solid fa-box-archive"></i>
        </div>
        <div class="stat-info">
            <h3>{{ summary.products_count }}</h3>
            <p>Total Products</p>
        </div>
    </div>
</div>

<!-- Recent Invoices Table -->
<div class="card">
    <div class="section-header">
        <span>Recent Invoices</span>
        <a href="{{ url_for('store_invoices') }}" class="btn btn-sm btn-secondary">View All Invoices <i class="fa-solid fa-arrow-right"></i></a>
    </div>
    {% if summary.recent_invoices %}
    <table class="dark-table">
        <thead>
            <tr>
                <th>Invoice #</th>
                <th>Customer</th>
                <th>Date</th>
                <th>Total</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
        {% for inv in summary.recent_invoices %}
            <tr>
                <td><strong>{{ inv.invoice_no }}</strong></td>
                <td>{{ inv.customer_name }}</td>
                <td>{{ inv.date }}</td>
                <td>{{ "%.2f"|format(inv.total) }} BDT</td>
                <td>
                    {% if inv.due == 0 %}
                        <span class="table-badge badge-green">Paid</span>
                    {% elif inv.due == inv.total %}
                        <span class="table-badge badge-red">Unpaid</span>
                    {% else %}
                        <span class="table-badge badge-yellow">Partially Paid</span>
                    {% endif %}
                </td>
                <td class="action-cell">
                    <a href="{{ url_for('view_invoice', inv_no=inv.invoice_no) }}" class="action-btn btn-view tooltip" data-tooltip="View"><i class="fa-solid fa-eye"></i></a>
                </td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
        <div class="empty-state">
            <lottie-player src="https://assets1.lottiefiles.com/packages/lf20_p2i2c27s.json" background="transparent" speed="1" style="width: 150px; height: 150px;" loop autoplay></lottie-player>
            <p>No invoices created yet.</p>
            <a href="{{ url_for('create_invoice') }}" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Create First Invoice</a>
        </div>
    {% endif %}
</div>
{% endblock %}
"""

# ----------------- STORE PRODUCTS -----------------
STORE_PRODUCTS_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Products</h1>
        <p class="page-subtitle">Manage your product inventory.</p>
    </div>
    <button class="btn btn-primary" onclick="openModal('{{ url_for('add_product') }}')">
        <i class="fa-solid fa-plus"></i> Add New Product
    </button>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}

<div class="card">
    {% if products %}
    <table class="dark-table">
        <thead>
            <tr>
                <th>Product Name</th>
                <th>Code</th>
                <th>Price (BDT)</th>
                <th>Stock</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for product in products %}
            <tr>
                <td><strong>{{ product.name }}</strong></td>
                <td>{{ product.code }}</td>
                <td>{{ "%.2f"|format(product.price) }}</td>
                <td>{{ product.stock }}</td>
                <td class="action-cell">
                    <button onclick="openModal('{{ url_for('edit_product', p_id=product.id) }}')" class="action-btn btn-edit tooltip" data-tooltip="Edit"><i class="fa-solid fa-pencil-alt"></i></button>
                    <form action="{{ url_for('delete_product', p_id=product.id) }}" method="POST" onsubmit="return confirm('Are you sure?');" style="display:inline;">
                        <button type="submit" class="action-btn btn-del tooltip" data-tooltip="Delete"><i class="fa-solid fa-trash-alt"></i></button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <lottie-player src="https://assets8.lottiefiles.com/packages/lf20_kxsd2ytq.json" background="transparent" speed="1" style="width: 180px; height: 180px;" loop autoplay></lottie-player>
        <p>No products found. Add your first product to get started!</p>
        <button class="btn btn-primary" onclick="openModal('{{ url_for('add_product') }}')"><i class="fa-solid fa-plus"></i> Add Product</button>
    </div>
    {% endif %}
</div>
{% endblock %}
"""

PRODUCT_FORM_MODAL_HTML = """
<form method="POST" action="{{ action_url }}">
    <div class="modal-header">
        <h2 class="modal-title">{{ title }}</h2>
        <span class="modal-close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-body">
        <div class="input-group">
            <label for="name">Product Name</label>
            <input type="text" name="name" value="{{ product.name or '' }}" required>
        </div>
        <div class="grid-2">
            <div class="input-group">
                <label for="code">Product Code</label>
                <input type="text" name="code" value="{{ product.code or '' }}">
            </div>
            <div class="input-group">
                <label for="price">Price (BDT)</label>
                <input type="number" step="0.01" name="price" value="{{ product.price or '' }}" required>
            </div>
        </div>
        <div class="input-group">
            <label for="stock">Stock Quantity</label>
            <input type="number" name="stock" value="{{ product.stock or '0' }}" required>
        </div>
        <div class="input-group">
            <label for="details">Details</label>
            <textarea name="details">{{ product.details or '' }}</textarea>
        </div>
    </div>
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-save"></i> Save Product</button>
    </div>
</form>
"""

# ----------------- STORE CUSTOMERS -----------------
STORE_CUSTOMERS_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Customers</h1>
        <p class="page-subtitle">View and manage your customer list.</p>
    </div>
    <button class="btn btn-primary" onclick="openModal('{{ url_for('add_customer') }}')">
        <i class="fa-solid fa-user-plus"></i> Add New Customer
    </button>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}

<div class="card">
    {% if customers %}
    <table class="dark-table">
        <thead>
            <tr>
                <th>Customer Name</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for customer in customers %}
            <tr>
                <td><strong>{{ customer.name }}</strong></td>
                <td>{{ customer.email }}</td>
                <td>{{ customer.phone }}</td>
                <td class="action-cell">
                    <button onclick="openModal('{{ url_for('edit_customer', c_id=customer.id) }}')" class="action-btn btn-edit tooltip" data-tooltip="Edit"><i class="fa-solid fa-pencil-alt"></i></button>
                    <form action="{{ url_for('delete_customer', c_id=customer.id) }}" method="POST" onsubmit="return confirm('Are you sure?');" style="display:inline;">
                        <button type="submit" class="action-btn btn-del tooltip" data-tooltip="Delete"><i class="fa-solid fa-trash-alt"></i></button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <lottie-player src="https://assets6.lottiefiles.com/packages/lf20_ab0c5hsh.json" background="transparent" speed="1" style="width: 200px; height: 200px;" loop autoplay></lottie-player>
        <p>No customers found. Add your first customer!</p>
        <button class="btn btn-primary" onclick="openModal('{{ url_for('add_customer') }}')"><i class="fa-solid fa-user-plus"></i> Add Customer</button>
    </div>
    {% endif %}
</div>
{% endblock %}
"""

CUSTOMER_FORM_MODAL_HTML = """
<form method="POST" action="{{ action_url }}">
    <div class="modal-header">
        <h2 class="modal-title">{{ title }}</h2>
        <span class="modal-close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-body">
        <div class="input-group">
            <label>Customer Name</label>
            <input type="text" name="name" value="{{ customer.name or '' }}" required>
        </div>
        <div class="grid-2">
            <div class="input-group">
                <label>Email</label>
                <input type="email" name="email" value="{{ customer.email or '' }}">
            </div>
            <div class="input-group">
                <label>Phone</label>
                <input type="text" name="phone" value="{{ customer.phone or '' }}" required>
            </div>
        </div>
        <div class="input-group">
            <label>Address</label>
            <textarea name="address">{{ customer.address or '' }}</textarea>
        </div>
    </div>
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-save"></i> Save Customer</button>
    </div>
</form>
"""

# ----------------- STORE INVOICES -----------------
STORE_INVOICES_LIST_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div>
        <h1 class="page-title">Invoices</h1>
        <p class="page-subtitle">Track all your sales invoices.</p>
    </div>
    <a href="{{ url_for('create_invoice') }}" class="btn btn-primary">
        <i class="fa-solid fa-plus"></i> Create New Invoice
    </a>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}

<div class="card">
    {% if invoices %}
    <table class="dark-table">
        <thead>
            <tr>
                <th>Invoice #</th>
                <th>Customer</th>
                <th>Date</th>
                <th>Total</th>
                <th>Due</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for inv in invoices %}
            <tr>
                <td><strong>{{ inv.invoice_no }}</strong></td>
                <td>{{ inv.customer_name }}</td>
                <td>{{ inv.date }}</td>
                <td>{{ "%.2f"|format(inv.total) }}</td>
                <td>{{ "%.2f"|format(inv.due) }}</td>
                <td>
                    {% if inv.due == 0 %} <span class="table-badge badge-green">Paid</span>
                    {% elif inv.due == inv.total %} <span class="table-badge badge-red">Unpaid</span>
                    {% else %} <span class="table-badge badge-yellow">Partially Paid</span>
                    {% endif %}
                </td>
                <td class="action-cell">
                    <a href="{{ url_for('view_invoice', inv_no=inv.invoice_no) }}" class="action-btn btn-view tooltip" data-tooltip="View"><i class="fa-solid fa-eye"></i></a>
                    <a href="javascript:void(0)" onclick="openModal('{{ url_for('add_payment', inv_no=inv.invoice_no) }}')" class="action-btn btn-edit tooltip" data-tooltip="Add Payment"><i class="fa-solid fa-money-bill-wave"></i></a>
                    <form action="{{ url_for('delete_invoice', inv_no=inv.invoice_no) }}" method="POST" onsubmit="return confirm('Are you sure?');" style="display:inline;">
                        <button type="submit" class="action-btn btn-del tooltip" data-tooltip="Delete"><i class="fa-solid fa-trash-alt"></i></button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty-state">
        <lottie-player src="https://assets1.lottiefiles.com/packages/lf20_p2i2c27s.json" background="transparent" speed="1" style="width: 150px; height: 150px;" loop autoplay></lottie-player>
        <p>No invoices created yet.</p>
        <a href="{{ url_for('create_invoice') }}" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Create First Invoice</a>
    </div>
    {% endif %}
</div>
{% endblock %}
"""

# ----------------- CREATE INVOICE/ESTIMATE -----------------
CREATE_INVOICE_ESTIMATE_HTML = """
{% extends "layout.html" %}
{% block content %}
<form method="POST" id="invoice-form">
<div class="header-section">
    <div>
        <h1 class="page-title">{{ title }}</h1>
        <p class="page-subtitle">Fill in the details below.</p>
    </div>
    <button type="submit" class="btn btn-success"><i class="fa-solid fa-save"></i> Save {{ type|title }}</button>
</div>

<div class="dashboard-grid-2">
    <div>
        <div class="card" style="margin-bottom: 24px;">
            <div class="section-header"><span>Customer Information</span></div>
            <div class="input-group">
                <label>Select Customer</label>
                <select name="customer_id" id="customer-select" required>
                    <option></option>
                    {% for c in customers %}
                        <option value="{{ c.id }}" {% if c.id == (doc.customer_id if doc else '') %}selected{% endif %}>{{ c.name }} - {{ c.phone }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="grid-2">
                <div class="input-group">
                    <label>{{ type|title }} Number</label>
                    <input type="text" name="{{ type }}_no" value="{{ doc_number }}" readonly>
                </div>
                <div class="input-group">
                    <label>Date</label>
                    <input type="date" name="date" value="{{ doc.date if doc else get_bd_time().strftime('%Y-%m-%d') }}" required>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="section-header">
                <span>Products / Services</span>
                <button type="button" id="add-item-btn" class="btn btn-sm btn-secondary"><i class="fa-solid fa-plus"></i> Add Item</button>
            </div>
            <table class="dark-table">
                <thead><tr><th style="width:40%;">Item</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead>
                <tbody id="item-list">
                {% if doc and doc.items %}
                    {% for item in doc.items %}
                    <tr>
                        <td><input type="text" name="item_name" placeholder="Item Name" value="{{ item.name }}" required></td>
                        <td><input type="number" name="item_qty" class="qty" placeholder="1" value="{{ item.qty }}" required></td>
                        <td><input type="number" name="item_price" class="price" step="0.01" placeholder="0.00" value="{{ item.price }}" required></td>
                        <td><input type="text" name="item_total" class="total" value="{{ '%.2f'|format(item.qty * item.price) }}" readonly></td>
                        <td class="action-cell"><button type="button" class="action-btn btn-del remove-item"><i class="fa fa-trash"></i></button></td>
                    </tr>
                    {% endfor %}
                {% else %}
                    <tr>
                        <td><input type="text" name="item_name" placeholder="Item Name" required></td>
                        <td><input type="number" name="item_qty" class="qty" placeholder="1" value="1" required></td>
                        <td><input type="number" name="item_price" class="price" step="0.01" placeholder="0.00" required></td>
                        <td><input type="text" name="item_total" class="total" readonly></td>
                        <td class="action-cell"><button type="button" class="action-btn btn-del remove-item"><i class="fa fa-trash"></i></button></td>
                    </tr>
                {% endif %}
                </tbody>
            </table>
        </div>
    </div>

    <div>
        <div class="card summary-card" style="margin-bottom: 24px;">
            <div class="section-header"><span>Summary</span></div>
            <div class="summary-row"><span>Subtotal</span><span id="subtotal">0.00</span></div>
            <div class="summary-row">
                <span>Discount</span>
                <input type="number" name="discount" id="discount" value="{{ doc.discount or 0 }}" step="0.01" style="width: 100px; text-align:right; padding: 5px 10px; font-size:14px;">
            </div>
            <div class="summary-row">
                <span>Tax (%)</span>
                <input type="number" name="tax" id="tax" value="{{ doc.tax or 0 }}" step="0.01" style="width: 100px; text-align:right; padding: 5px 10px; font-size:14px;">
            </div>
            <div class="summary-row summary-total"><span>Total (BDT)</span><span id="grand-total">0.00</span></div>
        </div>
        <div class="card">
             <div class="input-group">
                <label>Notes</label>
                <textarea name="notes" placeholder="Any additional notes...">{{ doc.notes or '' }}</textarea>
            </div>
        </div>
    </div>
</div>
</form>

<template id="item-template">
    <tr>
        <td><input type="text" name="item_name" placeholder="Item Name" required></td>
        <td><input type="number" name="item_qty" class="qty" placeholder="1" value="1" required></td>
        <td><input type="number" name="item_price" class="price" step="0.01" placeholder="0.00" required></td>
        <td><input type="text" name="item_total" class="total" readonly></td>
        <td class="action-cell"><button type="button" class="action-btn btn-del remove-item"><i class="fa fa-trash"></i></button></td>
    </tr>
</template>

{% endblock %}
{% block scripts %}
<script>
$(document).ready(function() {
    $('#customer-select').select2({
        placeholder: "Search for a customer",
        allowClear: true
    });
    
    function calculateTotals() {
        let subtotal = 0;
        $('#item-list tr').each(function() {
            let qty = parseFloat($(this).find('.qty').val()) || 0;
            let price = parseFloat($(this).find('.price').val()) || 0;
            let total = qty * price;
            $(this).find('.total').val(total.toFixed(2));
            subtotal += total;
        });

        $('#subtotal').text(subtotal.toFixed(2));

        let discount = parseFloat($('#discount').val()) || 0;
        let tax_percent = parseFloat($('#tax').val()) || 0;
        
        let total_after_discount = subtotal - discount;
        let tax_amount = total_after_discount * (tax_percent / 100);
        let grand_total = total_after_discount + tax_amount;

        $('#grand-total').text(grand_total.toFixed(2));
    }
    
    $('#add-item-btn').on('click', function() {
        const template = document.getElementById('item-template').content.cloneNode(true);
        $('#item-list').append(template);
    });

    $('#item-list').on('click', '.remove-item', function() {
        $(this).closest('tr').remove();
        calculateTotals();
    });

    $('#invoice-form').on('input', '.qty, .price, #discount, #tax', function() {
        calculateTotals();
    });

    calculateTotals();
});
</script>
{% endblock %}
"""

# ----------------- VIEW INVOICE/ESTIMATE -----------------
VIEW_INVOICE_ESTIMATE_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section no-print">
    <div>
        <h1 class="page-title">{{ type|title }} #{{ doc.invoice_no or doc.estimate_no }}</h1>
        <p class="page-subtitle">Details for {{ doc.customer_name }}</p>
    </div>
    <div class="actions">
        <a href="javascript:window.print()" class="btn btn-success"><i class="fa-solid fa-print"></i> Print</a>
        {% if type == 'estimate' %}
        <a href="{{ url_for('convert_to_invoice', est_no=doc.estimate_no) }}" class="btn btn-purple"><i class="fa-solid fa-exchange-alt"></i> Convert to Invoice</a>
        {% else %}
        <button onclick="openModal('{{ url_for('add_payment', inv_no=doc.invoice_no) }}')" class="btn btn-purple"><i class="fa-solid fa-money-bill-wave"></i> Add Payment</button>
        {% endif %}
        <a href="{{ url_for('store_invoices' if type == 'invoice' else 'store_estimates') }}" class="btn btn-secondary"><i class="fa-solid fa-arrow-left"></i> Back to List</a>
    </div>
</div>

<div class="card print-container">
    <header class="print-header" style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid var(--border-color);">
        <div>
            <h1 style="font-size: 28px; font-weight: 800; color: var(--text-primary);">{{ type|title|upper }}</h1>
            <p style="color: var(--text-secondary);">#{{ doc.invoice_no or doc.estimate_no }}</p>
        </div>
        <div style="text-align: right;">
            <h2 style="font-size: 20px; font-weight: 700;">Cotton Clothing (BD) Ltd.</h2>
            <p style="color: var(--text-secondary);">Your Company Address</p>
        </div>
    </header>
    
    <div class="print-meta" style="display: flex; justify-content: space-between; margin-bottom: 40px; font-size: 14px;">
        <div>
            <span style="display: block; color: var(--text-secondary); margin-bottom: 5px;">Billed To</span>
            <strong style="display: block; font-size: 16px;">{{ doc.customer_name }}</strong>
            <p style="color: var(--text-secondary); margin: 0;">{{ customer.address or 'No address' }}</p>
            <p style="color: var(--text-secondary); margin: 0;">{{ customer.email or 'No email' }}</p>
            <p style="color: var(--text-secondary); margin: 0;">{{ customer.phone }}</p>
        </div>
        <div style="text-align: right;">
            <p><span style="color: var(--text-secondary);">Date of Issue:</span> <strong>{{ doc.date }}</strong></p>
            {% if type == 'invoice' %}
            <p><span style="color: var(--text-secondary);">Due Date:</span> <strong>{{ doc.due_date or 'N/A' }}</strong></p>
            <div style="margin-top: 20px;">
                {% if doc.due == 0 %} <span class="table-badge badge-green" style="font-size: 16px;">PAID</span>
                {% else %} <span class="table-badge badge-red" style="font-size: 16px;">UNPAID</span>
                {% endif %}
            </div>
            {% endif %}
        </div>
    </div>
    
    <table class="dark-table print-table" style="margin-bottom: 30px;">
        <thead style="background: var(--bg-card);"><tr style="background: var(--bg-card) !important;"><th style="background: var(--bg-card) !important;">Item</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Price</th><th style="text-align:right;">Total</th></tr></thead>
        <tbody>
        {% for item in doc.items %}
            <tr><td><strong>{{ item.name }}</strong></td><td style="text-align:right;">{{ item.qty }}</td><td style="text-align:right;">{{ "%.2f"|format(item.price) }}</td><td style="text-align:right;">{{ "%.2f"|format(item.qty * item.price) }}</td></tr>
        {% endfor %}
        </tbody>
    </table>
    
    <div class="print-summary" style="display: flex; justify-content: flex-end;">
        <div style="width: 300px;">
            <div style="display: flex; justify-content: space-between; padding: 8px 0;"><span style="color: var(--text-secondary);">Subtotal</span><span>{{ "%.2f"|format(doc.subtotal) }} BDT</span></div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;"><span style="color: var(--text-secondary);">Discount</span><span>-{{ "%.2f"|format(doc.discount) }} BDT</span></div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;"><span style="color: var(--text-secondary);">Tax ({{ doc.tax }}%)</span><span>+{{ "%.2f"|format(doc.tax_amount) }} BDT</span></div>
            {% if type == 'invoice' %}
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color);"><span style="color: var(--text-secondary);">Paid</span><span>-{{ "%.2f"|format(doc.paid) }} BDT</span></div>
            <div class="print-total" style="display: flex; justify-content: space-between; padding: 15px 0; font-size: 20px; font-weight: 700; color: var(--accent-red); border-top: 2px solid var(--accent-red); margin-top:10px;"><span>Amount Due</span><span>{{ "%.2f"|format(doc.due) }} BDT</span></div>
            {% else %}
             <div class="print-total" style="display: flex; justify-content: space-between; padding: 15px 0; font-size: 20px; font-weight: 700; color: var(--accent-orange); border-top: 2px solid var(--accent-orange); margin-top:10px;"><span>Grand Total</span><span>{{ "%.2f"|format(doc.total) }} BDT</span></div>
            {% endif %}
        </div>
    </div>
    
    {% if doc.notes %}
    <div style="margin-top: 40px;">
        <h4 style="font-weight: 600; margin-bottom: 10px;">Notes</h4>
        <p style="color: var(--text-secondary);">{{ doc.notes }}</p>
    </div>
    {% endif %}

    {% if type == 'invoice' and payments %}
    <div class="no-print" style="margin-top: 40px;">
        <h3 class="page-title">Payment History</h3>
        <div class="card">
            <table class="dark-table">
            <thead><tr><th>Date</th><th>Amount</th><th>Method</th><th>Notes</th></tr></thead>
            <tbody>
            {% for p in payments %}
                <tr><td>{{ p.date }}</td><td>{{ "%.2f"|format(p.amount) }}</td><td>{{ p.method }}</td><td>{{ p.notes }}</td></tr>
            {% endfor %}
            </tbody>
            </table>
        </div>
    </div>
    {% endif %}

</div>
{% endblock %}
"""

# ----------------- ADD PAYMENT MODAL -----------------
ADD_PAYMENT_MODAL_HTML = """
<form method="POST" action="{{ url_for('add_payment', inv_no=invoice.invoice_no) }}">
    <div class="modal-header">
        <h2 class="modal-title">Add Payment for #{{ invoice.invoice_no }}</h2>
        <span class="modal-close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-body">
        <p style="margin-bottom: 20px;">Amount Due: <strong style="color: var(--accent-red);">{{ "%.2f"|format(invoice.due) }} BDT</strong></p>
        <div class="input-group">
            <label>Amount</label>
            <input type="number" step="0.01" name="amount" max="{{ invoice.due }}" required>
        </div>
        <div class="grid-2">
            <div class="input-group">
                <label>Payment Date</label>
                <input type="date" name="date" value="{{ get_bd_time().strftime('%Y-%m-%d') }}" required>
            </div>
            <div class="input-group">
                <label>Payment Method</label>
                <select name="method">
                    <option>Cash</option>
                    <option>Bank Transfer</option>
                    <option>Cheque</option>
                    <option>Mobile Banking</option>
                </select>
            </div>
        </div>
        <div class="input-group">
            <label>Notes</label>
            <textarea name="notes"></textarea>
        </div>
    </div>
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-plus"></i> Add Payment</button>
    </div>
</form>
"""

# ----------------- STORE USER MANAGEMENT -----------------
STORE_USER_MANAGEMENT_HTML = """
{% extends "layout.html" %}
{% block content %}
<div class="header-section">
    <div><h1 class="page-title">Store User Management</h1><p class="page-subtitle">Manage users for the Store Panel.</p></div>
    <button class="btn btn-primary" onclick="openModal('{{ url_for('add_store_user') }}')"><i class="fa-solid fa-user-plus"></i> Add Store User</button>
</div>
{% with messages = get_flashed_messages(with_categories=true) %}{% for c, m in messages %}<div class="flash-message flash-{{c}}">{{m}}</div>{% endfor %}{% endwith %}
<div class="card">
    <table class="dark-table">
        <thead><tr><th>Username</th><th>Role</th><th>Permissions</th><th>Created On</th><th>Last Login</th><th>Actions</th></tr></thead>
        <tbody>
            {% for username, details in users.items() %}
            <tr>
                <td><i class="fa-solid fa-user"></i> {{ username }}</td>
                <td><span class="table-badge">{{ details.role or 'user' }}</span></td>
                <td>
                    {% for perm in details.permissions or [] %}
                    <span class="table-badge" style="background: rgba(255,255,255,0.05); margin-right: 4px; margin-bottom: 4px;">{{ perm }}</span>
                    {% endfor %}
                </td>
                <td>{{ details.created_at or 'N/A' }}</td>
                <td>{{ details.last_login or 'Never' }}</td>
                <td class="action-cell">
                    <button onclick="openModal('{{ url_for('edit_store_user', username=username) }}')" class="action-btn btn-edit"><i class="fa-solid fa-pencil-alt"></i></button>
                    {% if username != 'StoreAdmin' and username != session.get('username') %}
                    <form action="{{ url_for('delete_store_user', username=username) }}" method="POST" onsubmit="return confirm('Are you sure?');">
                        <button type="submit" class="action-btn btn-del"><i class="fa-solid fa-trash-alt"></i></button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

STORE_USER_FORM_MODAL_HTML = """
<form method="POST" action="{{ action_url }}">
    <div class="modal-header">
        <h2 class="modal-title">{{ 'Add' if 'add' in action_url else 'Edit' }} Store User</h2>
        <span class="modal-close" onclick="closeModal()">&times;</span>
    </div>
    <div class="modal-body">
        <div class="input-group">
            <label for="username">Username</label>
            <input type="text" name="username" value="{{ user.username or '' }}" {{ 'readonly' if user.username }} required>
        </div>
        <div class="input-group">
            <label for="password">Password {% if 'edit' in action_url %}(Leave blank to keep unchanged){% endif %}</label>
            <input type="password" name="password" {{ 'required' if 'add' in action_url }}>
        </div>
        <div class="input-group">
            <label for="role">Role</label>
            <select name="role">
                <option value="store_user" {{ 'selected' if user.role == 'store_user' }}>Store User</option>
                <option value="store_admin" {{ 'selected' if user.role == 'store_admin' }}>Store Admin</option>
            </select>
        </div>
        <div class="input-group">
            <label>Permissions</label>
            <div class="perm-checkbox-group">
                {% for p in available_permissions %}
                <label class="perm-checkbox">
                    <input type="checkbox" name="permissions" value="{{ p }}" {{ 'checked' if p in (user.permissions or []) }}> <span>{{ p.replace('_', ' ')|title }}</span>
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
    <div class="modal-footer">
        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary"><i class="fa-solid fa-save"></i> Save User</button>
    </div>
</form>
"""


# ==============================================================================
# FLASK রাউট এবং লজিক
# ==============================================================================

# ----------------- DECORATORS & CORE ROUTES -----------------
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        session.permanent = True 
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def store_login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session or (session.get('user_type') != 'store' and 'store' not in session.get('permissions', [])):
             return redirect(url_for('store_login'))
        session.permanent = True
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def permission_required(permission):
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if permission not in session.get('permissions', []):
                flash(f"You don't have permission to access this page.", "error")
                # Redirect to appropriate dashboard
                if session.get('user_type') == 'store':
                    return redirect(url_for('store_dashboard'))
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator


@app.route('/')
def index():
    if 'username' in session:
        if session.get('user_type') == 'store':
            return redirect(url_for('store_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['permissions'] = users[username].get('permissions', [])
            session['user_type'] = 'main'
            session['show_welcome'] = True 
            
            # Update last login time
            users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
            save_users(users)
            
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Please try again.", "error")
    return render_template_string(LOGIN_HTML, title="Main Login")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
    
@app.route('/dashboard')
@login_required
def dashboard():
    summary = get_dashboard_summary_v2()
    return render_template_string(DASHBOARD_HTML, title="Dashboard", active_page="dashboard", summary=summary, get_bd_time=get_bd_time, get_bd_date_str=get_bd_date_str)

@app.context_processor
def inject_common_vars():
    """Makes COMMON_STYLES available to all templates."""
    return dict(COMMON_STYLES=COMMON_STYLES)

# ----------------- Main App Routes (Closing, PO, etc.) -----------------

@app.route('/closing-report', methods=['GET', 'POST'])
@login_required
@permission_required('closing')
def closing_report_page():
    ref_no = None
    if request.method == 'POST':
        ref_no = request.form.get('ref_no')
        if not ref_no:
            flash("IR/IB Number is required.", "error")
            return redirect(url_for('closing_report_page'))
        
        session['last_ref_no'] = ref_no # Save to session for preview
        
        # Show loading screen
        return render_template_string("""
            {% extends "layout.html" %}
            {% block content %}
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    document.getElementById('loading-overlay').style.display = 'flex';
                    window.location.href = "{{ url_for('process_and_preview_closing') }}";
                });
            </script>
            {% endblock %}
        """, title="Processing...")

    return render_template_string(CLOSING_REPORT_PAGE_HTML, title="Closing Report", active_page="closing", ref_no=session.get('last_ref_no'))

@app.route('/process-and-preview-closing')
@login_required
def process_and_preview_closing():
    ref_no = session.get('last_ref_no')
    if not ref_no:
        flash("Session expired or invalid reference number.", "warning")
        return redirect(url_for('closing_report_page'))
        
    report_data = fetch_closing_report_data(ref_no)
    if not report_data:
        flash(f"Could not find data for IR/IB No: {ref_no}. Please check the number and try again.", "error")
        return redirect(url_for('closing_report_page'))

    excel_stream = create_formatted_excel_report(report_data, ref_no)
    if not excel_stream:
        flash("Failed to generate the Excel report.", "error")
        return redirect(url_for('closing_report_page'))

    # Save to a temporary file for preview
    filename = f"Closing_Report_{ref_no}_{get_bd_time().strftime('%Y%m%d%H%M%S')}.xlsx"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'wb') as f:
        f.write(excel_stream.getvalue())

    # Update stats after successful generation
    update_stats(ref_no, session['username'])
    
    # URL for Google Docs Viewer
    preview_url = f"https://docs.google.com/gview?url={request.url_root}{url_for('download_file', filename=filename)}&embedded=true"

    return render_template_string(
        PREVIEW_PAGE_HTML,
        title="Closing Report Preview",
        preview_url=preview_url,
        download_url=url_for('download_file', filename=filename),
        back_url=url_for('closing_report_page'),
        filename=filename
    )

@app.route('/po-sheet', methods=['GET', 'POST'])
@login_required
@permission_required('po_sheet')
def po_sheet_page():
    if request.method == 'POST':
        files = request.files.getlist('po_files')
        if not files or all(f.filename == '' for f in files):
            flash("No files selected for upload.", "error")
            return redirect(request.url)

        session['po_file_paths'] = []
        for file in files:
            if file and file.filename.endswith('.pdf'):
                filename = f"po_{uuid.uuid4()}.pdf"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                session['po_file_paths'].append(filepath)

        if not session['po_file_paths']:
            flash("No valid PDF files were uploaded.", "error")
            return redirect(request.url)
        
        # Show loading screen
        return render_template_string("""
            {% extends "layout.html" %}
            {% block content %}
            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    document.getElementById('loading-overlay').style.display = 'flex';
                    window.location.href = "{{ url_for('process_and_preview_po') }}";
                });
            </script>
            {% endblock %}
        """, title="Processing POs...")

    return render_template_string(PO_SHEET_PAGE_HTML, title="PO Sheet", active_page="po_sheet")

@app.route('/process-and-preview-po')
@login_required
def process_and_preview_po():
    file_paths = session.get('po_file_paths', [])
    if not file_paths:
        flash("Session expired or no files to process.", "warning")
        return redirect(url_for('po_sheet_page'))

    all_data = []
    fabric_booking_detected = False
    
    for path in file_paths:
        data, metadata = extract_data_dynamic(path)
        if not data and metadata.get('booking') != 'N/A':
            fabric_booking_detected = True
        all_data.extend(data)
        os.remove(path) # Clean up file

    session.pop('po_file_paths', None) # Clean up session

    if not all_data:
        if fabric_booking_detected:
            flash("Fabric Booking Sheet detected. No garment data to process.", "warning")
        else:
            flash("Could not extract any data from the uploaded PDFs.", "error")
        return redirect(url_for('po_sheet_page'))

    df = pd.DataFrame(all_data)
    pivot_df = df.pivot_table(index=['P.O NO', 'Color'], columns='Size', values='Quantity', fill_value=0).reset_index()
    
    # Sort sizes logically before creating the Excel
    if 'Size' in df.columns:
        original_sizes = df['Size'].unique()
        sorted_size_list = sort_sizes(original_sizes)
        
        # Reorder pivot table columns based on sorted sizes
        fixed_cols = ['P.O NO', 'Color']
        pivot_cols = list(pivot_df.columns)
        size_cols = [s for s in sorted_size_list if s in pivot_cols]
        other_cols = [c for c in pivot_cols if c not in fixed_cols and c not in size_cols]
        pivot_df = pivot_df[fixed_cols + size_cols + other_cols]

    # Add a Total column
    pivot_df['Total Quantity'] = pivot_df.drop(columns=['P.O NO', 'Color']).sum(axis=1)
    
    output_filename = f"PO_Sheet_{get_bd_time().strftime('%Y%m%d%H%M%S')}.xlsx"
    output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    pivot_df.to_excel(output_filepath, index=False)
    
    update_po_stats(session['username'], len(file_paths))

    preview_url = f"https://docs.google.com/gview?url={request.url_root}{url_for('download_file', filename=output_filename)}&embedded=true"
    
    return render_template_string(
        PREVIEW_PAGE_HTML,
        title="PO Sheet Preview",
        preview_url=preview_url,
        download_url=url_for('download_file', filename=output_filename),
        back_url=url_for('po_sheet_page'),
        filename=output_filename
    )


@app.route('/download/<filename>')
@login_required
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

@app.route('/accessories', methods=['GET', 'POST'])
@login_required
@permission_required('accessories')
def accessories_challan_page():
    ref_no = request.form.get('ref_no', session.get('last_acc_ref'))
    data, challans, action = None, None, request.form.get('action')

    if ref_no:
        session['last_acc_ref'] = ref_no
        acc_db = load_accessories_db()
        challans = sorted(acc_db.get(ref_no.upper(), {}).get('challans', []), key=lambda x: x['timestamp'], reverse=True)

    if action == 'load':
        if not ref_no:
            flash("IR/IB Number is required.", "error")
        else:
            data = fetch_closing_report_data_with_cache(ref_no)
            if not data or not data.get('colors'):
                flash(f"No data or colors found for {ref_no}.", "warning")
                data = None
    
    elif action == 'generate':
        colors = request.form.getlist('colors')
        qty = request.form.get('challan_qty')
        out_time = request.form.get('out_time')
        vehicle = request.form.get('vehicle_no')

        if not all([ref_no, colors, qty, out_time, vehicle]):
            flash("All fields are required to generate a challan.", "error")
        else:
            acc_db = load_accessories_db()
            ref_upper = ref_no.upper()
            now = get_bd_time()
            challan_entry = {
                'id': str(uuid.uuid4()),
                'colors': colors,
                'qty': int(qty),
                'out_time': out_time,
                'vehicle_no': vehicle,
                'user': session['username'],
                'date': now.strftime('%d-%m-%Y'),
                'time': now.strftime('%I:%M %p'),
                'timestamp': now.isoformat()
            }
            if ref_upper not in acc_db:
                # This should ideally not happen if 'load' was clicked first
                acc_db[ref_upper] = {"challans": []}
            acc_db[ref_upper].setdefault('challans', []).append(challan_entry)
            save_accessories_db(acc_db)
            flash(f"Challan for {len(colors)} color(s) generated successfully!", "success")
            return redirect(url_for('accessories_challan_page')) # Redirect to prevent re-submission
        # Reload data after failed generation attempt
        data = fetch_closing_report_data_with_cache(ref_no)

    return render_template_string(ACCESSORIES_CHALLAN_PAGE_HTML, title="Accessories", active_page="accessories", ref_no=ref_no, data=data, challans=challans)


@app.route('/history')
@login_required
@permission_required('view_history')
def history_page():
    stats = load_stats()
    history = stats.get('downloads', [])
    return render_template_string(HISTORY_PAGE_HTML, title="History", active_page="history", history=history)

# ----------------- User Management Routes -----------------
@app.route('/user-management')
@login_required
@permission_required('user_manage')
def user_management():
    users = load_users()
    return render_template_string(USER_MANAGEMENT_HTML, title="User Management", active_page="user_manage", users=users)

@app.route('/user/add', methods=['GET', 'POST'])
@login_required
@permission_required('user_manage')
def add_user():
    available_permissions = ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store"]
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        if username in users:
            flash("Username already exists.", "error")
        else:
            users[username] = {
                "password": request.form['password'],
                "role": request.form['role'],
                "permissions": request.form.getlist('permissions'),
                "created_at": get_bd_date_str()
            }
            save_users(users)
            flash(f"User '{username}' created successfully.", "success")
            return redirect(url_for('user_management'))
    
    # For modal GET request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(USER_FORM_MODAL_HTML, action_url=url_for('add_user'), user={}, available_permissions=available_permissions)
    
    # Fallback for direct navigation (optional)
    return redirect(url_for('user_management'))

@app.route('/user/edit/<username>', methods=['GET', 'POST'])
@login_required
@permission_required('user_manage')
def edit_user(username):
    users = load_users()
    user = users.get(username)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('user_management'))

    available_permissions = ["closing", "po_sheet", "user_manage", "view_history", "accessories", "store"]
    
    if request.method == 'POST':
        user['role'] = request.form['role']
        user['permissions'] = request.form.getlist('permissions')
        if request.form.get('password'):
            user['password'] = request.form['password']
        save_users(users)
        flash(f"User '{username}' updated successfully.", "success")
        return redirect(url_for('user_management'))

    # For modal GET request
    user_data = user.copy()
    user_data['username'] = username
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(USER_FORM_MODAL_HTML, action_url=url_for('edit_user', username=username), user=user_data, available_permissions=available_permissions)
    
    return redirect(url_for('user_management'))


@app.route('/user/delete/<username>', methods=['POST'])
@login_required
@permission_required('user_manage')
def delete_user(username):
    if username == 'Admin' or username == session.get('username'):
        flash("Cannot delete the root admin or yourself.", "error")
        return redirect(url_for('user_management'))
    
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        flash(f"User '{username}' deleted successfully.", "success")
    else:
        flash("User not found.", "error")
    return redirect(url_for('user_management'))


# ==============================================================================
# ==============================================================================
# ======================== STORE MANAGEMENT ROUTES =============================
# ==============================================================================
# ==============================================================================

@app.route('/store/login', methods=['GET', 'POST'])
def store_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_store_users()
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['permissions'] = users[username].get('permissions', [])
            session['user_type'] = 'store' 
            session['show_welcome'] = True
            
            users[username]['last_login'] = get_bd_time().strftime('%d-%m-%Y %I:%M %p')
            save_store_users(users)
            
            return redirect(url_for('store_dashboard'))
        else:
            flash("Invalid store credentials.", "error")
    return render_template_string(LOGIN_HTML, title="Store Login")

@app.route('/store')
@app.route('/store/dashboard')
@store_login_required
def store_dashboard():
    summary = get_store_dashboard_summary()
    return render_template_string(STORE_DASHBOARD_HTML, title="Store Dashboard", active_page="store_dashboard", summary=summary)

# ----------------- Store Product Routes -----------------
@app.route('/store/products')
@store_login_required
@permission_required('products')
def store_products():
    products = load_store_products()
    return render_template_string(STORE_PRODUCTS_HTML, title="Products", active_page="store_products", products=products)

@app.route('/store/product/add', methods=['GET', 'POST'])
@store_login_required
@permission_required('products')
def add_product():
    if request.method == 'POST':
        products = load_store_products()
        new_product = {
            "id": str(uuid.uuid4()),
            "name": request.form['name'],
            "code": request.form['code'],
            "price": float(request.form['price']),
            "stock": int(request.form['stock']),
            "details": request.form['details']
        }
        products.append(new_product)
        save_store_products(products)
        flash("Product added successfully!", "success")
        return redirect(url_for('store_products'))
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(PRODUCT_FORM_MODAL_HTML, title="Add New Product", action_url=url_for('add_product'), product={})
    return redirect(url_for('store_products'))

@app.route('/store/product/edit/<p_id>', methods=['GET', 'POST'])
@store_login_required
@permission_required('products')
def edit_product(p_id):
    products = load_store_products()
    product = next((p for p in products if p.get('id') == p_id), None)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('store_products'))
        
    if request.method == 'POST':
        product['name'] = request.form['name']
        product['code'] = request.form['code']
        product['price'] = float(request.form['price'])
        product['stock'] = int(request.form['stock'])
        product['details'] = request.form['details']
        save_store_products(products)
        flash("Product updated successfully!", "success")
        return redirect(url_for('store_products'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(PRODUCT_FORM_MODAL_HTML, title="Edit Product", action_url=url_for('edit_product', p_id=p_id), product=product)
    return redirect(url_for('store_products'))

@app.route('/store/product/delete/<p_id>', methods=['POST'])
@store_login_required
@permission_required('products')
def delete_product(p_id):
    products = load_store_products()
    products = [p for p in products if p.get('id') != p_id]
    save_store_products(products)
    flash("Product deleted successfully!", "success")
    return redirect(url_for('store_products'))


# ----------------- Store Customer Routes -----------------
@app.route('/store/customers')
@store_login_required
@permission_required('customers')
def store_customers():
    customers = load_store_customers()
    return render_template_string(STORE_CUSTOMERS_HTML, title="Customers", active_page="store_customers", customers=customers)

@app.route('/store/customer/add', methods=['GET', 'POST'])
@store_login_required
@permission_required('customers')
def add_customer():
    if request.method == 'POST':
        customers = load_store_customers()
        new_customer = {
            "id": str(uuid.uuid4()),
            "name": request.form['name'],
            "email": request.form['email'],
            "phone": request.form['phone'],
            "address": request.form['address']
        }
        customers.append(new_customer)
        save_store_customers(customers)
        flash("Customer added successfully!", "success")
        return redirect(url_for('store_customers'))
        
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(CUSTOMER_FORM_MODAL_HTML, title="Add New Customer", action_url=url_for('add_customer'), customer={})
    return redirect(url_for('store_customers'))

@app.route('/store/customer/edit/<c_id>', methods=['GET', 'POST'])
@store_login_required
@permission_required('customers')
def edit_customer(c_id):
    customers = load_store_customers()
    customer = next((c for c in customers if c.get('id') == c_id), None)
    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for('store_customers'))
        
    if request.method == 'POST':
        customer['name'] = request.form['name']
        customer['email'] = request.form['email']
        customer['phone'] = request.form['phone']
        customer['address'] = request.form['address']
        save_store_customers(customers)
        flash("Customer updated successfully!", "success")
        return redirect(url_for('store_customers'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(CUSTOMER_FORM_MODAL_HTML, title="Edit Customer", action_url=url_for('edit_customer', c_id=c_id), customer=customer)
    return redirect(url_for('store_customers'))

@app.route('/store/customer/delete/<c_id>', methods=['POST'])
@store_login_required
@permission_required('customers')
def delete_customer(c_id):
    customers = load_store_customers()
    customers = [c for c in customers if c.get('id') != c_id]
    save_store_customers(customers)
    flash("Customer deleted successfully!", "success")
    return redirect(url_for('store_customers'))

# ----------------- Store Invoice Routes -----------------
@app.route('/store/invoices')
@store_login_required
@permission_required('invoices')
def store_invoices():
    invoices = load_store_invoices()
    sorted_invoices = sorted(invoices, key=lambda x: x.get('date', '1970-01-01'), reverse=True)
    return render_template_string(STORE_INVOICES_LIST_HTML, title="Invoices", active_page="store_invoices", invoices=sorted_invoices)

@app.route('/store/invoice/create', methods=['GET', 'POST'])
@store_login_required
@permission_required('invoices')
def create_invoice():
    if request.method == 'POST':
        invoices = load_store_invoices()
        customers = load_store_customers()
        
        items = []
        subtotal = 0
        item_names = request.form.getlist('item_name')
        item_qtys = request.form.getlist('item_qty')
        item_prices = request.form.getlist('item_price')
        
        for i in range(len(item_names)):
            qty = float(item_qtys[i])
            price = float(item_prices[i])
            total = qty * price
            items.append({"name": item_names[i], "qty": qty, "price": price})
            subtotal += total
        
        discount = float(request.form.get('discount', 0))
        tax_percent = float(request.form.get('tax', 0))
        total_after_discount = subtotal - discount
        tax_amount = total_after_discount * (tax_percent / 100)
        grand_total = total_after_discount + tax_amount
        
        customer = next((c for c in customers if c.get('id') == request.form['customer_id']), None)
        
        new_invoice = {
            "invoice_no": request.form['invoice_no'],
            "customer_id": request.form['customer_id'],
            "customer_name": customer['name'] if customer else 'N/A',
            "date": request.form['date'],
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax_percent,
            "tax_amount": tax_amount,
            "total": grand_total,
            "paid": 0,
            "due": grand_total,
            "notes": request.form.get('notes', '')
        }
        invoices.append(new_invoice)
        save_store_invoices(invoices)
        flash(f"Invoice {new_invoice['invoice_no']} created successfully!", "success")
        return redirect(url_for('view_invoice', inv_no=new_invoice['invoice_no']))
        
    customers = load_store_customers()
    return render_template_string(CREATE_INVOICE_ESTIMATE_HTML, title="Create New Invoice", active_page="store_invoices", customers=customers, doc_number=generate_invoice_number(), get_bd_time=get_bd_time, type="invoice")

@app.route('/store/invoice/view/<inv_no>')
@store_login_required
@permission_required('invoices')
def view_invoice(inv_no):
    invoice = next((i for i in load_store_invoices() if i['invoice_no'] == inv_no), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for('store_invoices'))
    customer = next((c for c in load_store_customers() if c.get('id') == invoice['customer_id']), {})
    payments = [p for p in load_store_payments() if p['invoice_no'] == inv_no]
    return render_template_string(VIEW_INVOICE_ESTIMATE_HTML, title=f"View Invoice", active_page="store_invoices", doc=invoice, customer=customer, payments=payments, type="invoice")

@app.route('/store/invoice/delete/<inv_no>', methods=['POST'])
@store_login_required
@permission_required('invoices')
def delete_invoice(inv_no):
    invoices = [i for i in load_store_invoices() if i['invoice_no'] != inv_no]
    save_store_invoices(invoices)
    # Also delete associated payments
    payments = [p for p in load_store_payments() if p['invoice_no'] != inv_no]
    save_store_payments(payments)
    flash(f"Invoice {inv_no} deleted.", "success")
    return redirect(url_for('store_invoices'))

# ----------------- Store Estimate Routes -----------------
@app.route('/store/estimates')
@store_login_required
@permission_required('estimates')
def store_estimates():
    estimates = sorted(load_store_estimates(), key=lambda x: x.get('date', '1970-01-01'), reverse=True)
    return render_template_string(STORE_INVOICES_LIST_HTML, title="Estimates", active_page="store_estimates", invoices=estimates) # Re-use template

@app.route('/store/estimate/create', methods=['GET', 'POST'])
@store_login_required
@permission_required('estimates')
def create_estimate():
    if request.method == 'POST':
        estimates = load_store_estimates()
        customers = load_store_customers()
        # Similar logic to create_invoice but for estimates
        items = []
        subtotal = 0
        item_names = request.form.getlist('item_name')
        item_qtys = request.form.getlist('item_qty')
        item_prices = request.form.getlist('item_price')
        
        for i in range(len(item_names)):
            qty = float(item_qtys[i]); price = float(item_prices[i]); total = qty * price
            items.append({"name": item_names[i], "qty": qty, "price": price})
            subtotal += total
        
        discount = float(request.form.get('discount', 0))
        tax_percent = float(request.form.get('tax', 0))
        total_after_discount = subtotal - discount
        tax_amount = total_after_discount * (tax_percent / 100)
        grand_total = total_after_discount + tax_amount
        customer = next((c for c in customers if c.get('id') == request.form['customer_id']), None)

        new_estimate = {
            "estimate_no": request.form['estimate_no'], "customer_id": request.form['customer_id'],
            "customer_name": customer['name'] if customer else 'N/A', "date": request.form['date'],
            "items": items, "subtotal": subtotal, "discount": discount, "tax": tax_percent,
            "tax_amount": tax_amount, "total": grand_total, "notes": request.form.get('notes', '')
        }
        estimates.append(new_estimate)
        save_store_estimates(estimates)
        flash(f"Estimate {new_estimate['estimate_no']} created successfully!", "success")
        return redirect(url_for('view_estimate', est_no=new_estimate['estimate_no']))
        
    customers = load_store_customers()
    return render_template_string(CREATE_INVOICE_ESTIMATE_HTML, title="Create New Estimate", active_page="store_estimates", customers=customers, doc_number=generate_estimate_number(), get_bd_time=get_bd_time, type="estimate")

@app.route('/store/estimate/view/<est_no>')
@store_login_required
@permission_required('estimates')
def view_estimate(est_no):
    estimate = next((e for e in load_store_estimates() if e['estimate_no'] == est_no), None)
    if not estimate:
        flash("Estimate not found.", "error")
        return redirect(url_for('store_estimates'))
    customer = next((c for c in load_store_customers() if c.get('id') == estimate['customer_id']), {})
    return render_template_string(VIEW_INVOICE_ESTIMATE_HTML, title=f"View Estimate", active_page="store_estimates", doc=estimate, customer=customer, type="estimate")

@app.route('/store/estimate/delete/<est_no>', methods=['POST'])
@store_login_required
@permission_required('estimates')
def delete_estimate(est_no):
    estimates = [e for e in load_store_estimates() if e['estimate_no'] != est_no]
    save_store_estimates(estimates)
    flash(f"Estimate {est_no} deleted.", "success")
    return redirect(url_for('store_estimates'))

@app.route('/store/estimate/convert/<est_no>')
@store_login_required
@permission_required('invoices')
def convert_to_invoice(est_no):
    estimate = next((e for e in load_store_estimates() if e['estimate_no'] == est_no), None)
    if not estimate:
        flash("Estimate not found.", "error")
        return redirect(url_for('store_estimates'))
    
    invoices = load_store_invoices()
    new_invoice = {
        **estimate, # copy all data
        "invoice_no": generate_invoice_number(),
        "paid": 0,
        "due": estimate['total']
    }
    del new_invoice['estimate_no']
    
    invoices.append(new_invoice)
    save_store_invoices(invoices)
    
    # Optional: delete the estimate after conversion
    estimates = [e for e in load_store_estimates() if e['estimate_no'] != est_no]
    save_store_estimates(estimates)
    
    flash(f"Estimate {est_no} converted to Invoice {new_invoice['invoice_no']}.", "success")
    return redirect(url_for('view_invoice', inv_no=new_invoice['invoice_no']))

# ----------------- Store Payment Routes -----------------
@app.route('/store/payment/add/<inv_no>', methods=['GET', 'POST'])
@store_login_required
@permission_required('payments')
def add_payment(inv_no):
    invoices = load_store_invoices()
    invoice = next((i for i in invoices if i['invoice_no'] == inv_no), None)
    if not invoice:
        flash("Invoice not found.", "error")
        return redirect(url_for('store_invoices'))

    if request.method == 'POST':
        payments = load_store_payments()
        amount = float(request.form['amount'])
        
        payments.append({
            "payment_id": str(uuid.uuid4()), "invoice_no": inv_no,
            "amount": amount, "date": request.form['date'],
            "method": request.form['method'], "notes": request.form.get('notes', '')
        })
        save_store_payments(payments)
        
        # Update invoice status
        invoice['paid'] += amount
        invoice['due'] -= amount
        save_store_invoices(invoices)
        
        flash("Payment added successfully!", "success")
        return redirect(url_for('view_invoice', inv_no=inv_no))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(ADD_PAYMENT_MODAL_HTML, invoice=invoice, get_bd_time=get_bd_time)
    return redirect(url_for('view_invoice', inv_no=inv_no))


# ----------------- Store User Management Routes -----------------
@app.route('/store/user-management')
@store_login_required
@permission_required('user_manage')
def store_user_management():
    users = load_store_users()
    return render_template_string(STORE_USER_MANAGEMENT_HTML, title="Store User Management", active_page="store_user_manage", users=users)

@app.route('/store/user/add', methods=['GET', 'POST'])
@store_login_required
@permission_required('user_manage')
def add_store_user():
    available_permissions = ["products", "customers", "invoices", "estimates", "payments", "user_manage"]
    if request.method == 'POST':
        users = load_store_users()
        username = request.form['username']
        if username in users:
            flash("Username already exists.", "error")
        else:
            users[username] = {
                "password": request.form['password'], "role": request.form['role'],
                "permissions": request.form.getlist('permissions'), "created_at": get_bd_date_str()
            }
            save_store_users(users)
            flash("Store user created successfully.", "success")
        return redirect(url_for('store_user_management'))
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(STORE_USER_FORM_MODAL_HTML, action_url=url_for('add_store_user'), user={}, available_permissions=available_permissions)
    return redirect(url_for('store_user_management'))

@app.route('/store/user/edit/<username>', methods=['GET', 'POST'])
@store_login_required
@permission_required('user_manage')
def edit_store_user(username):
    users = load_store_users()
    user = users.get(username)
    available_permissions = ["products", "customers", "invoices", "estimates", "payments", "user_manage"]
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('store_user_management'))

    if request.method == 'POST':
        user['role'] = request.form['role']
        user['permissions'] = request.form.getlist('permissions')
        if request.form.get('password'):
            user['password'] = request.form['password']
        save_store_users(users)
        flash("Store user updated successfully.", "success")
        return redirect(url_for('store_user_management'))

    user_data = user.copy(); user_data['username'] = username
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template_string(STORE_USER_FORM_MODAL_HTML, action_url=url_for('edit_store_user', username=username), user=user_data, available_permissions=available_permissions)
    return redirect(url_for('store_user_management'))

@app.route('/store/user/delete/<username>', methods=['POST'])
@store_login_required
@permission_required('user_manage')
def delete_store_user(username):
    if username == 'StoreAdmin' or username == session.get('username'):
        flash("Cannot delete the root store admin or yourself.", "error")
        return redirect(url_for('store_user_management'))
    
    users = load_store_users()
    if username in users:
        del users[username]
        save_store_users(users)
        flash("Store user deleted.", "success")
    return redirect(url_for('store_user_management'))

# ==============================================================================
# MAIN APP EXECUTION
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
