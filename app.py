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
    return get_bd_time(). strftime('%d-%m-%Y')

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
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/? appName=Office"

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

        .nav-link:hover::before, .nav-link. active::before { width: 100%; }

        .nav-link:hover, .nav-link. active { 
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
            transform: scale(1. 2);
            filter: drop-shadow(0 0 8px var(--accent-orange));
        }

        .nav-link . nav-badge {
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

        . header-section { 
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

        .status-badge:hover {
            border-color: var(--accent-green);
            box-shadow: 0 0 20px rgba(16, 185, 129, 0. 2);
        }

        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: statusPulse 2s ease-in-out infinite;
            box-shadow: 0 0 10px var(--accent-green);
        }

        @keyframes statusPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
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

        . card::before {
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

        . stat-card:hover .stat-icon i {
            animation: iconBounce 0.5s ease-out;
        }

        @keyframes iconBounce {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1. 3); }
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

        . progress-bar-container {
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
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3. org/2000/svg' fill='%23FF7A00' viewBox='0 0 24 24'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            background-size: 24px;
            background-color: #1a1a25;
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

        .btn-del:hover { 
            background: var(--accent-red); 
            color: white;
            transform: scale(1.1);
            box-shadow: 0 0 20px rgba(239, 68, 68, 0. 4);
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
            box-shadow: 0 0 40px rgba(16, 185, 129, 0. 3);
        }

        . checkmark-circle::before {
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
            animation: modalFadeIn 0. 3s ease-out;
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
            transform: scale(1. 02);
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

        . upload-text {
            color: var(--accent-orange);
            font-weight: 600;
            font-size: 16px;
            margin-bottom: 8px;
        }

        . upload-hint {
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

        .flash-error {
            background: rgba(239, 68, 68, 0. 1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #F87171;
        }

        .flash-success {
            background: rgba(16, 185, 129, 0. 1);
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
            .sidebar. active { 
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
            transform: scale(1. 1) rotate(90deg);
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

        . perm-checkbox:has(input:checked) {
            border-color: var(--accent-orange);
            background: rgba(255, 122, 0, 0. 1);
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

        .time-badge i {
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
    now = get_bd_time()
    new_record = {
        "ref": ref_no,
        "user": username,
        "date": now. strftime('%d-%m-%Y'),
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
        "time": now. strftime('%I:%M %p'),
        "type": "PO Sheet",
        "iso_time": now. isoformat()
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

# --- আপডেটেড: রিয়েল-টাইম ড্যাশবোর্ড সামারি এবং এনালিটিক্স (LIFETIME + DAILY CHART) ---
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

    # 2.  Accessories LIFETIME & Daily Analytics
    acc_lifetime_count = 0
    acc_today_list = []
    
    # Daily Analytics Container
    daily_data = defaultdict(lambda: {'closing': 0, 'po': 0, 'acc': 0})

    for ref, data in acc_db. items():
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
            
            # Daily Analytics Calculation
            try:
                dt_obj = datetime.strptime(c_date, '%d-%m-%Y')
                sort_key = dt_obj. strftime('%Y-%m-%d')
                daily_data[sort_key]['acc'] += 1
                daily_data[sort_key]['label'] = dt_obj.strftime('%d-%b')
            except:
                pass

    # 3.  Closing & PO LIFETIME & Daily Analytics
    closing_lifetime_count = 0
    po_lifetime_count = 0
    closing_list = []
    po_list = []
    
    history = stats_data.get('downloads', [])
    for item in history:
        item_date = item.get('date', '')
        if item. get('type') == 'PO Sheet':
            po_lifetime_count += 1
            if item_date == today_str:
                po_list.append(item)
        else:
            closing_lifetime_count += 1
            if item_date == today_str:
                closing_list.append(item)
        
        # Daily Analytics Calculation
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

    # Get last month's 1st date to today (DEW Style Daily Chart)
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
        "history": history
    }


# ==============================================================================
# লজিক পার্ট: PURCHASE ORDER SHEET PARSER (PDF)
# ==============================================================================

def is_potential_size(header):
    h = header.strip(). upper()
    if h in ["COLO", "SIZE", "TOTAL", "QUANTITY", "PRICE", "AMOUNT", "CURRENCY", "ORDER NO", "P. O NO"]:
        return False
    if re.match(r'^\d+$', h):
        return True
    if re.match(r'^\d+[AMYT]$', h):
        return True
    if re.match(r'^(XXS|XS|S|M|L|XL|XXL|XXXL|TU|ONE\s*SIZE)$', h):
        return True
    if re.match(r'^[A-Z]\d{2,}$', h):
        return False
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
        if s in STANDARD_ORDER:
            return (0, STANDARD_ORDER.index(s))
        if s.isdigit():
            return (1, int(s))
        match = re.match(r'^(\d+)([A-Z]+)$', s)
        if match:
            return (2, int(match.group(1)), match.group(2))
        return (3, s)
    return sorted(size_list, key=sort_key)

def extract_metadata(first_page_text):
    meta = {
        'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 
        'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'
    }
    if "KIABI" in first_page_text. upper():
        meta['buyer'] = "KIABI"
    else:
        buyer_match = re. search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(? :\n|$)", first_page_text)
        if buyer_match:
            meta['buyer'] = buyer_match.group(1).strip()

    booking_block_match = re.search(r"(? :Internal )?Booking NO\.  ? [:\s]*([\s\S]*?)(? :System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
    if booking_block_match:
        raw_booking = booking_block_match.group(1). strip()
        clean_booking = raw_booking.replace('\n', '').replace('\r', '').replace(' ', '')
        if "System" in clean_booking:
            clean_booking = clean_booking.split("System")[0]
        meta['booking'] = clean_booking

    style_match = re.search(r"Style Ref\. ?[:\s]*([\w-]+)", first_page_text, re.IGNORECASE)
    if style_match:
        meta['style'] = style_match.group(1). strip()
    else:
        style_match = re.search(r"Style Des\. ? [\s\S]*?([\w-]+)", first_page_text, re.IGNORECASE)
        if style_match:
            meta['style'] = style_match.group(1). strip()

    season_match = re. search(r"Season\s*[:\n\"]*([\w\d-]+)", first_page_text, re. IGNORECASE)
    if season_match:
        meta['season'] = season_match.group(1).strip()

    dept_match = re.search(r"Dept\.  ?[\s\n:]*([A-Za-z]+)", first_page_text, re. IGNORECASE)
    if dept_match:
        meta['dept'] = dept_match.group(1).strip()

    item_match = re.search(r"Garments?   Item[\s\n:]*([^\n\r]+)", first_page_text, re.IGNORECASE)
    if item_match:
        item_text = item_match. group(1).strip()
        if "Style" in item_text:
            item_text = item_text.split("Style")[0].strip()
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
        if order_match:
            order_no = order_match.group(1)
        else:
            alt_match = re.search(r"Order\s*[:\.]?\s*(\d+)", first_page_text, re. IGNORECASE)
            if alt_match:
                order_no = alt_match.group(1)
        
        order_no = str(order_no).strip()
        if order_no. endswith("00"):
            order_no = order_no[:-2]

        for page in reader.pages:
            text = page.extract_text()
            lines = text.split('\n')
            sizes = []
            capturing_data = False
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

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
                    except:
                        pass
                    continue
                
                if capturing_data:
                    if line.startswith("Total Quantity") or line.startswith("Total Amount"):
                        capturing_data = False
                        continue
                    
                    lower_line = line. lower()
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line:
                        continue
                        
                    clean_line = line. replace("Spec. price", ""). replace("Spec", ""). strip()
                    if not re.search(r'[a-zA-Z]', clean_line):
                        continue
                    if re.match(r'^[A-Z]\d+$', clean_line) or "Assortment" in clean_line:
                        continue

                    numbers_in_line = re. findall(r'\b\d+\b', line)
                    quantities = [int(n) for n in numbers_in_line]
                    color_name = clean_line
                    final_qtys = []

                    if len(quantities) >= len(sizes):
                        if len(quantities) == len(sizes) + 1:
                            final_qtys = quantities[:-1]
                        else:
                            final_qtys = quantities[:len(sizes)]
                        color_name = re.sub(r'\s\d+$', '', color_name). strip()
                    elif len(quantities) < len(sizes):
                        vertical_qtys = []
                        for next_line in lines[i+1:]:
                            next_line = next_line.strip()
                            if "Total" in next_line or re.search(r'[a-zA-Z]', next_line. replace("Spec", "").replace("price", "")):
                                break
                            if re.match(r'^\d+$', next_line):
                                vertical_qtys.append(int(next_line))
                        if len(vertical_qtys) >= len(sizes):
                            final_qtys = vertical_qtys[:len(sizes)]
                    
                    if final_qtys and color_name:
                        for idx, size in enumerate(sizes):
                            extracted_data.append({
                                'P.O NO': order_no,
                                'Color': color_name,
                                'Size': size,
                                'Quantity': final_qtys[idx]
                            })
    except Exception as e:
        print(f"Error processing file: {e}")
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
        if "dashboard. php" in response.url or "Invalid" not in response.text:
            return session_req
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def fetch_closing_report_data(internal_ref_no):
    active_session = get_authenticated_session("input2. clothing-cutting", "123456")
    if not active_session:
        return None

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
            except:
                continue
        if found_data:
            break
    
    if found_data:
        return parse_report_data(found_data)
    return None

def parse_report_data(html_content):
    all_report_data = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        if not header_row:
            return None
        all_th = header_row.find_all('th')
        headers = [th.get_text(strip=True) for th in all_th if 'total' not in th.get_text(strip=True). lower()]
        data_rows = soup. select('div#scroll_body table tbody tr')
        item_blocks = []
        current_block = []
        for row in data_rows:
            if row.get('bgcolor') == '#cddcdc':
                if current_block:
                    item_blocks.append(current_block)
                current_block = []
            else:
                current_block. append(row)
        if current_block:
            item_blocks.append(current_block)
        for block in item_blocks:
            style, color, buyer_name, gmts_qty_data, sewing_input_data, cutting_qc_data = "N/A", "N/A", "N/A", None, None, None
            for row in block:
                cells = row.find_all('td')
                if len(cells) > 2:
                    criteria_main = cells[0]. get_text(strip=True)
                    criteria_sub = cells[2].get_text(strip=True)
                    main_lower, sub_lower = criteria_main.lower(), criteria_sub.lower()
                    if main_lower == "style":
                        style = cells[1].get_text(strip=True)
                    elif main_lower == "color & gmts.   item":
                        color = cells[1]. get_text(strip=True)
                    elif "buyer" in main_lower:
                        buyer_name = cells[1].get_text(strip=True)
                    if sub_lower == "gmts.  color /country qty":
                        gmts_qty_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
                    if "sewing input" in main_lower:
                        sewing_input_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "sewing input" in sub_lower:
                        sewing_input_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
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
                        plus_3_percent_data.append(value)
                all_report_data. append({
                    'style': style,
                    'buyer': buyer_name,
                    'color': color,
                    'headers': headers,
                    'gmts_qty': gmts_qty_data,
                    'plus_3_percent': plus_3_percent_data,
                    'sewing_input': sewing_input_data if sewing_input_data else [],
                    'cutting_qc': cutting_qc_data if cutting_qc_data else []
                })
        return all_report_data
    except Exception as e:
        return None
        def create_formatted_excel_report(report_data, internal_ref_no=""):
    if not report_data:
        return None
    wb = openpyxl. Workbook()
    ws = wb. active
    ws.title = "Closing Report"
    
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
    ws['A1']. value = "COTTON CLOTHING BD LTD"
    ws['A1'].font = title_font
    ws['A1'].alignment = center_align

    ws. merge_cells(start_row=2, start_column=1, end_row=2, end_column=NUM_COLUMNS)
    ws['A2'].value = "CLOSING REPORT [ INPUT SECTION ]"
    ws['A2'].font = Font(size=15, bold=True)
    ws['A2'].alignment = center_align
    ws. row_dimensions[3].height = 6

    formatted_ref_no = internal_ref_no. upper()
    current_date = get_bd_time(). strftime("%d/%m/%Y")
    
    left_sub_headers = {
        'A4': 'BUYER', 'B4': report_data[0]. get('buyer', ''),
        'A5': 'IR/IB NO', 'B5': formatted_ref_no,
        'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')
    }
    
    for cell_ref, value in left_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell.font = bold_font
        cell. alignment = left_align
        cell.border = thin_border
        if cell_ref == 'B5':
            cell.fill = ir_ib_fill
            cell.font = white_bold_font
        else:
            cell. fill = dark_green_fill

    ws.merge_cells('B4:G4')
    ws. merge_cells('B5:G5')
    ws.merge_cells('B6:G6')
    
    right_sub_headers = {
        'H4': 'CLOSING DATE', 'I4': current_date,
        'H5': 'SHIPMENT', 'I5': 'ALL',
        'H6': 'PO NO', 'I6': 'ALL'
    }
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
        full_color_name = block.get('color', 'N/A')

        for i, size in enumerate(block['headers']):
            color_to_write = full_color_name if i == 0 else ""
            actual_qty = int(block['gmts_qty'][i]. replace(',', '') or 0)
            input_qty = int(block['sewing_input'][i].replace(',', '') or 0) if i < len(block['sewing_input']) else 0
            cutting_qc_val = int(block. get('cutting_qc', [])[i].replace(',', '') or 0) if i < len(block.get('cutting_qc', [])) else 0
            
            ws.cell(row=current_row, column=1, value=color_to_write)
            ws.cell(row=current_row, column=2, value=size)
            ws.cell(row=current_row, column=4, value=actual_qty)
            ws.cell(row=current_row, column=5, value=cutting_qc_val)
            ws. cell(row=current_row, column=6, value=input_qty)
            
            ws.cell(row=current_row, column=3, value=f"=ROUND(D{current_row}*1.03, 0)")
            ws.cell(row=current_row, column=7, value=f"=E{current_row}-F{current_row}")
            ws.cell(row=current_row, column=8, value=f"=F{current_row}-C{current_row}")
            ws.cell(row=current_row, column=9, value=f'=IF(C{current_row}<>0, H{current_row}/C{current_row}, 0)')
            
            for col_idx in range(1, NUM_COLUMNS + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = medium_border if col_idx == 2 else thin_border
                cell.alignment = center_align
                if col_idx in [1, 2, 3, 6, 9]:
                    cell.font = bold_font
                
                if col_idx == 3:
                    cell.fill = light_blue_fill
                elif col_idx == 6:
                    cell.fill = light_green_fill
                else:
                    cell.fill = dark_green_fill

                if col_idx == 9:
                    cell.number_format = '0.00%'
            current_row += 1
            
        end_merge_row = current_row - 1
        if start_merge_row <= end_merge_row:
            ws. merge_cells(start_row=start_merge_row, start_column=1, end_row=end_merge_row, end_column=1)
            merged_cell = ws. cell(row=start_merge_row, column=1)
            merged_cell. alignment = color_align
            if not merged_cell.font.bold:
                merged_cell.font = bold_font
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
                cell. fill = dark_green_fill
                cell.border = medium_border
        current_row += 2
       
    image_row = current_row + 1
   
    try:
        direct_image_url = 'https://i.ibb.co/v6bp0jQW/rockybilly-regular. webp'
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
        ws.row_dimensions[image_row].height = img.height * 0.90
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
            if cell.coordinate == 'B5':
                continue
            if cell.font:
                existing_font = cell.font
                if cell.row != 1:
                    new_font = Font(name=existing_font. name, size=16. 5, bold=existing_font.bold, italic=existing_font. italic, vertAlign=existing_font. vertAlign, underline=existing_font.underline, strike=existing_font. strike, color=existing_font.color)
                    cell.font = new_font
   
    ws.column_dimensions['A']. width = 23
    ws.column_dimensions['B']. width = 8. 5
    ws. column_dimensions['C'].width = 20
    ws.column_dimensions['D']. width = 17
    ws.column_dimensions['E']. width = 17
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G']. width = 13. 5
    ws. column_dimensions['H'].width = 23
    ws.column_dimensions['I']. width = 18
   
    ws.page_setup.orientation = ws. ORIENTATION_PORTRAIT
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
# HTML TEMPLATES: LOGIN PAGE - RESPONSIVE FIX + COPYRIGHT 2025
# ==============================================================================

LOGIN_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0, maximum-scale=1. 0, user-scalable=no">
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
        
        /* Animated Background Orbs */
        .bg-orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: orbFloat 20s ease-in-out infinite;
            pointer-events: none;
        }}
        
        . orb-1 {{
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
        
        . orb-3 {{
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
        
        . login-container {{
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
        
        . login-card {{
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
        
        . brand-icon {{
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
        
        . brand-name {{
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
        
        .login-form . input-group {{
            margin-bottom: 20px;
        }}
        
        .login-form . input-group label {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        
        .login-form . input-group label i {{
            color: var(--accent-orange);
            font-size: 13px;
        }}
        
        . login-form input {{
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
        
        . error-box {{
            margin-top: 20px;
            padding: 14px 18px;
            background: rgba(239, 68, 68, 0. 1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 10px;
            color: #F87171;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: errorShake 0.5s ease-out;
        }}
        
        @keyframes errorShake {{
            0%, 100% {{ transform: translateX(0); }}
            20%, 60% {{ transform: translateX(-5px); }}
            40%, 80% {{ transform: translateX(5px); }}
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
        
        /* Responsive Fixes */
        @media (max-width: 480px) {{
            .login-container {{
                padding: 15px;
            }}
            
            .login-card {{
                padding: 30px 25px;
                border-radius: 20px;
            }}
            
            . brand-icon {{
                width: 60px;
                height: 60px;
                font-size: 28px;
            }}
            
            . brand-name {{
                font-size: 24px;
            }}
            
            .brand-tagline {{
                font-size: 10px;
            }}
            
            . login-form input {{
                padding: 12px 16px;
                font-size: 14px;
            }}
            
            . login-btn {{
                padding: 12px 20px;
                font-size: 14px;
            }}
        }}
        
        @media (max-height: 700px) {{
            .login-container {{
                min-height: auto;
                padding-top: 30px;
                padding-bottom: 30px;
            }}
            
            .brand-section {{
                margin-bottom: 25px;
            }}
            
            . brand-icon {{
                width: 60px;
                height: 60px;
                font-size: 26px;
                margin-bottom: 12px;
            }}
        }}
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
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="error-box">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{{{ messages[0] }}}}</span>
                    </div>
                {{% endif %}}
            {{% endwith %}}
            
            <div class="footer-credit">
                © 2025 <a href="#">Mehedi Hasan</a> • All Rights Reserved
            </div>
        </div>
    </div>
    
    <script>
        document.querySelector('.login-btn'). addEventListener('click', function(e) {{
            const ripple = document.createElement('span');
            ripple.classList. add('ripple-effect');
            const rect = this.getBoundingClientRect();
            ripple.style.left = (e.clientX - rect.left) + 'px';
            ripple.style. top = (e. clientY - rect. top) + 'px';
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        }});
    </script>
</body>
</html>
"""
# ==============================================================================
# ADMIN DASHBOARD TEMPLATE - LIFETIME STATS + DAILY CHART + STORE OPTION
# ==============================================================================

ADMIN_DASHBOARD_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Dashboard - MNM Software</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div id="particles-js"></div>

    <div class="welcome-modal" id="welcomeModal">
        <div class="welcome-content">
            <div class="welcome-icon" id="welcomeIcon">👋</div>
            <div class="welcome-greeting" id="greetingText">Good Morning</div>
            <div class="welcome-title">Welcome Back, <span>{{{{ session. user }}}}</span>!</div>
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
                    <span>System Online</span>
                </div>
            </div>
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash-message flash-error">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{{{ messages[0] }}}}</span>
                    </div>
                {{% endif %}}
            {{% endwith %}}

            <div class="stats-grid">
                <div class="card stat-card" style="animation-delay: 0. 1s;">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{{{ stats.closing. count }}}}">0</h3>
                        <p>Lifetime Closing</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.2s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                        <i class="fas fa-boxes" style="color: var(--accent-purple);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{{{ stats.accessories.count }}}}">0</h3>
                        <p>Lifetime Accessories</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.3s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                        <i class="fas fa-file-pdf" style="color: var(--accent-green);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{{{ stats.po. count }}}}">0</h3>
                        <p>Lifetime PO Sheets</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.4s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0. 15), rgba(59, 130, 246, 0. 05));">
                        <i class="fas fa-users" style="color: var(--accent-blue);"></i>
                    </div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{{{ stats.users.count }}}}">0</h3>
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
                            <span class="progress-value">{{{{ stats. closing.count }}}} Lifetime</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill progress-orange" style="width: 85%;"></div>
                        </div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-header">
                            <span>Accessories</span>
                            <span class="progress-value">{{{{ stats.accessories.count }}}} Challans</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill progress-purple" style="width: 65%;"></div>
                        </div>
                    </div>
                    
                    <div class="progress-item">
                        <div class="progress-header">
                            <span>PO Generator</span>
                            <span class="progress-value">{{{{ stats.po. count }}}} Files</span>
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
                            {{% for log in stats.history[:10] %}}
                            <tr style="animation: fadeInUp 0.5s ease-out {{{{ loop.index * 0.05 }}}}s backwards;">
                                <td>
                                    <div class="time-badge">
                                        <i class="far fa-clock"></i>
                                        {{{{ log.time }}}}
                                    </div>
                                </td>
                                <td style="font-weight: 600; color: white;">{{{{ log.user }}}}</td>
                                <td>
                                    <span class="table-badge" style="
                                        {{% if log.type == 'Closing Report' %}}
                                        background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);
                                        {{% elif log. type == 'PO Sheet' %}}
                                        background: rgba(16, 185, 129, 0. 1); color: var(--accent-green);
                                        {{% else %}}
                                        background: rgba(139, 92, 246, 0. 1); color: var(--accent-purple);
                                        {{% endif %}}
                                    ">{{{{ log. type }}}}</span>
                                </td>
                                <td style="color: var(--text-secondary);">{{{{ log.ref if log.ref else '-' }}}}</td>
                            </tr>
                            {{% else %}}
                            <tr>
                                <td colspan="4" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                    <i class="fas fa-inbox" style="font-size: 40px; opacity: 0.3; margin-bottom: 15px; display: block;"></i>
                                    No activity recorded yet. 
                                </td>
                            </tr>
                            {{% endfor %}}
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
                        <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ stats.users. count }}}} Users</span>
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
        function showWelcomePopup() {{
            const hour = new Date().getHours();
            let greeting, icon;
            
            if (hour >= 5 && hour < 12) {{
                greeting = "Good Morning";
                icon = "🌅";
            }} else if (hour >= 12 && hour < 17) {{
                greeting = "Good Afternoon";
                icon = "☀️";
            }} else if (hour >= 17 && hour < 21) {{
                greeting = "Good Evening";
                icon = "🌆";
            }} else {{
                greeting = "Good Night";
                icon = "🌙";
            }}
            
            document.getElementById('greetingText').textContent = greeting;
            document.getElementById('welcomeIcon').textContent = icon;
            document.getElementById('welcomeModal').style.display = 'flex';
        }}
        
        function closeWelcome() {{
            const modal = document.getElementById('welcomeModal');
            modal.style.animation = 'modalFadeOut 0. 3s ease-out forwards';
            setTimeout(() => {{
                modal.style.display = 'none';
                sessionStorage.setItem('welcomeShown', 'true');
            }}, 300);
        }}
        
        if (! sessionStorage.getItem('welcomeShown')) {{
            setTimeout(showWelcomePopup, 500);
        }}
        
        // ===== SECTION NAVIGATION =====
        function showSection(id, element) {{
            ['dashboard', 'analytics', 'help', 'settings'].forEach(sid => {{
                document.getElementById('section-' + sid).style.display = 'none';
            }});
            document.getElementById('section-' + id).style.display = 'block';
            
            if (element) {{
                document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
                element.classList.add('active');
            }}
            
            if (id === 'settings') loadUsers();
            if (window.innerWidth < 1024) document.querySelector('.sidebar').classList. remove('active');
        }}
        
        // ===== FILE UPLOAD HANDLER =====
        const fileUpload = document.getElementById('file-upload');
        const uploadZone = document. getElementById('uploadZone');
        
        if (fileUpload) {{
            fileUpload.addEventListener('change', function() {{
                const count = this.files. length;
                document.getElementById('file-count').innerHTML = count > 0 
                    ? `<i class="fas fa-check-circle" style="margin-right: 5px;"></i>${{count}} file(s) selected`
                    : 'No files selected';
            }});
            
            uploadZone.addEventListener('dragover', (e) => {{
                e.preventDefault();
                uploadZone.classList.add('dragover');
            }});
            
            uploadZone.addEventListener('dragleave', () => {{
                uploadZone.classList.remove('dragover');
            }});
            
            uploadZone.addEventListener('drop', (e) => {{
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                fileUpload.files = e.dataTransfer. files;
                fileUpload.dispatchEvent(new Event('change'));
            }});
        }}
        
        // ===== DEW STYLE DAILY CHART =====
        const ctx = document.getElementById('mainChart').getContext('2d');
        
        const gradientOrange = ctx.createLinearGradient(0, 0, 0, 300);
        gradientOrange.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
        gradientOrange.addColorStop(1, 'rgba(255, 122, 0, 0. 0)');
        
        const gradientPurple = ctx.createLinearGradient(0, 0, 0, 300);
        gradientPurple. addColorStop(0, 'rgba(139, 92, 246, 0.5)');
        gradientPurple.addColorStop(1, 'rgba(139, 92, 246, 0.0)');
        
        const gradientGreen = ctx.createLinearGradient(0, 0, 0, 300);
        gradientGreen.addColorStop(0, 'rgba(16, 185, 129, 0. 5)');
        gradientGreen. addColorStop(1, 'rgba(16, 185, 129, 0.0)');
        
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {{{{ stats.chart.labels | tojson }}}},
                datasets: [
                    {{
                        label: 'Closing',
                        data: {{{{ stats.chart.closing | tojson }}}},
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
                    }},
                    {{
                        label: 'Accessories',
                        data: {{{{ stats.chart.acc | tojson }}}},
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
                    }},
                    {{
                        label: 'PO Sheets',
                        data: {{{{ stats.chart.po | tojson }}}},
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
                    }}
                ]
            }},
            options: {{
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            color: '#8b8b9e',
                            font: {{ size: 11, weight: 500 }},
                            usePointStyle: true,
                            padding: 15,
                            boxWidth: 8
                        }}
                    }},
                    tooltip: {{
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
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ 
                            color: '#8b8b9e', 
                            font: {{ size: 10 }},
                            maxRotation: 45,
                            minRotation: 45
                        }}
                    }},
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.03)', drawBorder: false }},
                        ticks: {{ color: '#8b8b9e', font: {{ size: 10 }}, stepSize: 1 }},
                        beginAtZero: true
                    }}
                }},
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                    mode: 'index'
                }},
                animation: {{
                    duration: 2000,
                    easing: 'easeOutQuart'
                }}
            }}
        }});
        
        // ===== COUNT UP ANIMATION =====
        function animateCountUp() {{
            document.querySelectorAll('.count-up').forEach(counter => {{
                const target = parseInt(counter.getAttribute('data-target'));
                const duration = 2000;
                const step = target / (duration / 16);
                let current = 0;
                
                const updateCounter = () => {{
                    current += step;
                    if (current < target) {{
                        counter.textContent = Math.floor(current);
                        requestAnimationFrame(updateCounter);
                    }} else {{
                        counter.textContent = target;
                    }}
                }};
                
                updateCounter();
            }});
        }}
        
        setTimeout(animateCountUp, 500);
        
        // ===== LOADING ANIMATION =====
        function showLoading() {{
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
        }}

        function showSuccess() {{
            const overlay = document. getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim'). parentElement;
            const success = document. getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            spinner.style.display = 'none';
            success.style. display = 'block';
            text. style.display = 'none';
            
            setTimeout(() => {{ overlay.style.display = 'none'; }}, 1500);
        }}

        // ===== USER MANAGEMENT =====
        function loadUsers() {{
            fetch('/admin/get-users')
                .then(res => res.json())
                .then(data => {{
                    let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
                    
                    for (const [u, d] of Object.entries(data)) {{
                        const roleClass = d.role === 'admin' ?  'background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);' : 'background: rgba(139, 92, 246, 0. 1); color: var(--accent-purple);';
                        
                        html += `<tr>
                            <td style="font-weight: 600;">${{u}}</td>
                            <td><span class="table-badge" style="${{roleClass}}">${{d.role}}</span></td>
                            <td style="text-align:right;">
                                ${{d.role !== 'admin' ?  `
                                    <div class="action-cell">
                                        <button class="action-btn btn-edit" onclick="editUser('${{u}}', '${{d.password}}', '${{d. permissions. join(',')}}')">
                                            <i class="fas fa-edit"></i>
                                        </button> 
                                        <button class="action-btn btn-del" onclick="deleteUser('${{u}}')">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    </div>
                                ` : '<i class="fas fa-shield-alt" style="color: var(--accent-orange); opacity: 0.5;"></i>'}}
                            </td>
                        </tr>`;
                    }}
                    
                    document.getElementById('userTableContainer').innerHTML = html + '</tbody></table>';
                }});
        }}
        
        function handleUserSubmit() {{
            const u = document.getElementById('new_username').value;
            const p = document.getElementById('new_password').value;
            const a = document.getElementById('action_type').value;
            
            let perms = [];
            if (document.getElementById('perm_closing').checked) perms.push('closing');
            if (document.getElementById('perm_po').checked) perms.push('po_sheet');
            if (document.getElementById('perm_acc'). checked) perms. push('accessories');
            
            showLoading();
            
            fetch('/admin/save-user', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ username: u, password: p, permissions: perms, action_type: a }})
            }})
            .then(r => r.json())
            .then(d => {{
                if (d.status === 'success') {{
                    showSuccess();
                    loadUsers();
                    resetForm();
                }} else {{
                    alert(d. message);
                    document.getElementById('loading-overlay').style. display = 'none';
                }}
            }});
        }}
        
        function editUser(u, p, permsStr) {{
            document.getElementById('new_username').value = u;
            document. getElementById('new_username').readOnly = true;
            document.getElementById('new_password').value = p;
            document.getElementById('action_type').value = 'update';
            document. getElementById('saveUserBtn').innerHTML = '<i class="fas fa-sync" style="margin-right: 10px;"></i> Update User';
            
            const pArr = permsStr. split(',');
            document.getElementById('perm_closing').checked = pArr.includes('closing');
            document.getElementById('perm_po').checked = pArr.includes('po_sheet');
            document.getElementById('perm_acc'). checked = pArr. includes('accessories');
        }}
        
        function resetForm() {{
            document.getElementById('userForm').reset();
            document.getElementById('action_type').value = 'create';
            document.getElementById('saveUserBtn').innerHTML = '<i class="fas fa-save" style="margin-right: 10px;"></i> Save User';
            document.getElementById('new_username').readOnly = false;
            document.getElementById('perm_closing').checked = true;
        }}
        
        function deleteUser(u) {{
            if (confirm('Are you sure you want to delete "' + u + '"?')) {{
                fetch('/admin/delete-user', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ username: u }})
                }}). then(() => loadUsers());
            }}
        }}
        
        // ===== PARTICLES. JS INITIALIZATION =====
        if (typeof particlesJS !== 'undefined') {{
            particlesJS('particles-js', {{
                particles: {{
                    number: {{ value: 50, density: {{ enable: true, value_area: 800 }} }},
                    color: {{ value: '#FF7A00' }},
                    shape: {{ type: 'circle' }},
                    opacity: {{ value: 0.3, random: true }},
                    size: {{ value: 3, random: true }},
                    line_linked: {{ enable: true, distance: 150, color: '#FF7A00', opacity: 0.1, width: 1 }},
                    move: {{ enable: true, speed: 1, direction: 'none', random: true, out_mode: 'out' }}
                }},
                interactivity: {{
                    events: {{ onhover: {{ enable: true, mode: 'grab' }} }},
                    modes: {{ grab: {{ distance: 140, line_linked: {{ opacity: 0.3 }} }} }}
                }}
            }});
        }}
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {{
                from {{ opacity: 0; transform: translateY(20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes modalFadeOut {{
                to {{ opacity: 0; }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""


# ==============================================================================
# USER DASHBOARD TEMPLATE - MODERN UI
# ==============================================================================

USER_DASHBOARD_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard - MNM Software</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    
    <div class="welcome-modal" id="welcomeModal">
        <div class="welcome-content">
            <div class="welcome-icon" id="welcomeIcon">👋</div>
            <div class="welcome-greeting" id="greetingText">Good Morning</div>
            <div class="welcome-title">Welcome, <span>{{{{ session.user }}}}</span>! </div>
            <div class="welcome-message">
                Your workspace is ready.  Access your assigned modules below. 
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
                <div class="page-title">Welcome, {{{{ session.user }}}}!</div>
                <div class="page-subtitle">Your assigned production modules</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="flash-message flash-error">
                    <i class="fas fa-exclamation-circle"></i>
                    <span>{{{{ messages[0] }}}}</span>
                </div>
            {{% endif %}}
        {{% endwith %}}

        <div class="stats-grid">
            {{% if 'closing' in session. permissions %}}
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
            {{% endif %}}
            
            {{% if 'po_sheet' in session. permissions %}}
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
            {{% endif %}}
            
            {{% if 'accessories' in session.permissions %}}
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
            {{% endif %}}
        </div>
    </div>
    
    <script>
        function showWelcomePopup() {{
            const hour = new Date().getHours();
            let greeting, icon;
            
            if (hour >= 5 && hour < 12) {{
                greeting = "Good Morning";
                icon = "🌅";
            }} else if (hour >= 12 && hour < 17) {{
                greeting = "Good Afternoon";
                icon = "☀️";
            }} else if (hour >= 17 && hour < 21) {{
                greeting = "Good Evening";
                icon = "🌆";
            }} else {{
                greeting = "Good Night";
                icon = "🌙";
            }}
            
            document.getElementById('greetingText').textContent = greeting;
            document. getElementById('welcomeIcon').textContent = icon;
            document. getElementById('welcomeModal').style.display = 'flex';
        }}
        
        function closeWelcome() {{
            const modal = document.getElementById('welcomeModal');
            modal.style.opacity = '0';
            setTimeout(() => {{
                modal.style.display = 'none';
                sessionStorage.setItem('welcomeShown', 'true');
            }}, 300);
        }}
        
        if (! sessionStorage.getItem('welcomeShown')) {{
            setTimeout(showWelcomePopup, 500);
        }}
        
        function showLoading() {{
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }}
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {{
                from {{ opacity: 0; transform: translateY(20px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""
# ==============================================================================
# ACCESSORIES TEMPLATES - MODERN DARK THEME + SELECT FIX + COPYRIGHT 2025
# ==============================================================================

ACCESSORIES_SEARCH_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Search - MNM Software</title>
    {COMMON_STYLES}
    <style>
        body {{
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        
        .search-container {{
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 480px;
            padding: 20px;
        }}
        
        .search-card {{
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 50px 45px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5), 0 0 60px var(--accent-orange-glow);
            animation: cardAppear 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        
        @keyframes cardAppear {{
            from {{ opacity: 0; transform: translateY(20px) scale(0.95); }}
            to {{ opacity: 1; transform: translateY(0) scale(1); }}
        }}
        
        .search-header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        
        .search-icon {{
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
        }}
        
        @keyframes iconFloat {{
            0%, 100% {{ transform: translateY(0); }}
            50% {{ transform: translateY(-10px); }}
        }}
        
        .search-title {{
            font-size: 28px;
            font-weight: 800;
            color: white;
            margin-bottom: 8px;
        }}
        
        .search-subtitle {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        
        .nav-links {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}
        
        . nav-links a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: var(--transition-smooth);
        }}
        
        .nav-links a:hover {{
            color: var(--accent-orange);
        }}
        
        .nav-links a. logout {{
            color: var(--accent-red);
        }}
        
        .nav-links a.logout:hover {{
            color: #ff6b6b;
        }}
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
            
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash-message flash-error" style="margin-top: 20px;">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{{{ messages[0] }}}}</span>
                    </div>
                {{% endif %}}
            {{% endwith %}}
            
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

ACCESSORIES_INPUT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories Entry - MNM Software</title>
    {COMMON_STYLES}
    <style>
        . ref-badge {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 122, 0, 0.1);
            border: 1px solid rgba(255, 122, 0, 0.2);
            padding: 10px 20px;
            border-radius: 12px;
            margin-top: 10px;
        }}
        
        .ref-badge . ref-no {{
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-orange);
        }}
        
        .ref-badge .ref-info {{
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
        }}
        
        . history-scroll {{
            max-height: 500px;
            overflow-y: auto;
            padding-right: 5px;
        }}
        
        . challan-row {{
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
        }}
        
        .challan-row:hover {{
            background: rgba(255, 122, 0, 0.05);
            border-color: var(--border-glow);
        }}
        
        . line-badge {{
            background: var(--gradient-orange);
            color: white;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 13px;
            text-align: center;
        }}
        
        .qty-value {{
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-green);
        }}
        
        .status-check {{
            color: var(--accent-green);
            font-size: 20px;
        }}
        
        .print-btn {{
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%) !important;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 50px 20px;
            color: var(--text-secondary);
        }}
        
        .empty-state i {{
            font-size: 50px;
            opacity: 0.2;
            margin-bottom: 15px;
        }}
        
        . grid-2-cols {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        
        . count-badge {{
            background: var(--accent-purple);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            margin-left: 10px;
        }}
        
        /* Select Dark Background Fix */
        select {{
            background-color: #1a1a25 !important;
            color: white ! important;
        }}
        
        select option {{
            background-color: #1a1a25 ! important;
            color: white !important;
            padding: 10px;
        }}
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
                    <span class="ref-no">{{{{ ref }}}}</span>
                    <span class="ref-info">{{{{ buyer }}}} • {{{{ style }}}}</span>
                </div>
            </div>
            <a href="/admin/accessories/print? ref={{{{ ref }}}}" target="_blank">
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
                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                    
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
                                {{% for c in colors %}}
                                <option value="{{{{ c }}}}">{{{{ c }}}}</option>
                                {{% endfor %}}
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
                    <span class="count-badge">{{{{ challans|length }}}}</span>
                </div>
                <div class="history-scroll">
                    {{% if challans %}}
                        {{% for item in challans|reverse %}}
                        <div class="challan-row" style="animation: fadeInUp 0.3s ease-out {{{{ loop.index * 0.05 }}}}s backwards;">
                            <div class="line-badge">{{{{ item.line }}}}</div>
                            <div style="color: white; font-weight: 500; font-size: 13px;">{{{{ item.color }}}}</div>
                            <div class="qty-value">{{{{ item. qty }}}}</div>
                            <div class="status-check">{{{{ item.status if item.status else '●' }}}}</div>
                            <div class="action-cell">
                                {{% if session.role == 'admin' %}}
                                <a href="/admin/accessories/edit? ref={{{{ ref }}}}&index={{{{ (challans|length) - loop.index }}}}" class="action-btn btn-edit">
                                    <i class="fas fa-pen"></i>
                                </a>
                                <form action="/admin/accessories/delete" method="POST" style="display: inline;" onsubmit="return confirm('Delete this entry?');">
                                    <input type="hidden" name="ref" value="{{{{ ref }}}}">
                                    <input type="hidden" name="index" value="{{{{ (challans|length) - loop.index }}}}">
                                    <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                </form>
                                {{% else %}}
                                <span style="font-size: 10px; color: var(--text-secondary); opacity: 0.5;">🔒</span>
                                {{% endif %}}
                            </div>
                        </div>
                        {{% endfor %}}
                    {{% else %}}
                        <div class="empty-state">
                            <i class="fas fa-inbox"></i>
                            <div>No challans added yet</div>
                            <div style="font-size: 12px; margin-top: 5px;">Add your first entry using the form</div>
                        </div>
                    {{% endif %}}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showLoading() {{
            const overlay = document.getElementById('loading-overlay');
            const spinner = document.getElementById('spinner-anim'). parentElement;
            const success = document.getElementById('success-anim');
            const text = document.getElementById('loading-text');
            
            overlay. style.display = 'flex';
            spinner. style.display = 'block';
            success.style.display = 'none';
            text.style.display = 'block';
            text.textContent = 'Saving Entry... ';
            
            return true;
        }}
        
        const style = document.createElement('style');
        style.textContent = `
            @keyframes fadeInUp {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""

ACCESSORIES_EDIT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Entry - MNM Software</title>
    {COMMON_STYLES}
    <style>
        body {{
            justify-content: center;
            align-items: center;
        }}
        
        .edit-container {{
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 450px;
            padding: 20px;
        }}
        
        .edit-card {{
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 45px;
            backdrop-filter: blur(20px);
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
            animation: cardAppear 0. 5s ease-out;
        }}
        
        @keyframes cardAppear {{
            from {{ opacity: 0; transform: scale(0.95); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        
        . edit-header {{
            text-align: center;
            margin-bottom: 35px;
        }}
        
        . edit-icon {{
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
        }}
        
        .edit-title {{
            font-size: 24px;
            font-weight: 800;
            color: white;
        }}
        
        .cancel-link {{
            display: block;
            text-align: center;
            margin-top: 20px;
            color: var(--text-secondary);
            font-size: 13px;
            text-decoration: none;
            transition: var(--transition-smooth);
        }}
        
        .cancel-link:hover {{
            color: var(--accent-orange);
        }}
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
                <input type="hidden" name="ref" value="{{{{ ref }}}}">
                <input type="hidden" name="index" value="{{{{ index }}}}">
                
                <div class="input-group">
                    <label><i class="fas fa-industry" style="margin-right: 5px;"></i> LINE NO</label>
                    <input type="text" name="line_no" value="{{{{ item.line }}}}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-palette" style="margin-right: 5px;"></i> COLOR</label>
                    <input type="text" name="color" value="{{{{ item. color }}}}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> SIZE</label>
                    <input type="text" name="size" value="{{{{ item.size }}}}" required>
                </div>
                
                <div class="input-group">
                    <label><i class="fas fa-sort-numeric-up" style="margin-right: 5px;"></i> QUANTITY</label>
                    <input type="number" name="qty" value="{{{{ item. qty }}}}" required>
                </div>
                
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync-alt" style="margin-right: 10px;"></i> Update Entry
                </button>
            </form>
            
            <a href="/admin/accessories/input_direct? ref={{{{ ref }}}}" class="cancel-link">
                <i class="fas fa-times" style="margin-right: 5px;"></i> Cancel
            </a>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# REPORT TEMPLATES (ORIGINAL WHITE DESIGN - PRINT FRIENDLY)
# ==============================================================================

CLOSING_REPORT_PREVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Closing Report Preview</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
        . info-value { color: #000; font-weight: 800; }
        .booking-box { background: #2c3e50; color: white; padding: 10px 20px; border-radius: 5px; text-align: right; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); display: flex; flex-direction: column; justify-content: center; min-width: 200px; }
        .booking-label { font-size: 1. 1rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
        . booking-value { font-size: 1.8rem; font-weight: 800; line-height: 1.1; }
        .table-card { background: white; border-radius: 0; margin-bottom: 30px; border: none; }
        .color-header { background-color: #2c3e50 !important; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; text-transform: uppercase; border: 1px solid #000;}
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; font-size: 1rem; }
        . table th { background-color: #fff ! important; color: #000 !important; text-align: center; border: 1px solid #000; padding: 8px; vertical-align: middle; font-weight: 900; font-size: 1. 2rem; }
        .table td { text-align: center; vertical-align: middle; border: 1px solid #000; padding: 6px; color: #000; font-weight: 600; font-size: 1. 1rem; }
        .col-3pct { background-color: #B9C2DF ! important; font-weight: 700; }
        .col-input { background-color: #C4D09D !important; font-weight: 700; }
        .col-balance { font-weight: 700; color: #c0392b; }
        .total-row td { background-color: #fff !important; color: #000 ! important; font-weight: 900; font-size: 1.2rem; border-top: 2px solid #000; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 15px; position: sticky; top: 0; z-index: 1000; background: #f8f9fa; padding: 10px 0; }
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; border: none; }
        .btn-excel { background-color: #27ae60; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; text-decoration: none; display: inline-block; }
        .btn-excel:hover { color: white; background-color: #219150; }
        . footer-credit { text-align: center; margin-top: 40px; margin-bottom: 20px; font-size: 1rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #000; font-weight: 600;}
        @media print {
            @page { margin: 5mm; size: portrait; } 
            body { background-color: white; padding: 0; }
            .container { max-width: 100% !important; width: 100%; }
            .no-print { display: none ! important; }
            .action-bar { display: none; }
            .table th, .table td { border: 1px solid #000 !important; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white !important;}
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            . booking-box { background-color: #2c3e50 ! important; -webkit-print-color-adjust: exact; color: white !important; border: 1px solid #000;}
            .total-row td { font-weight: 900 !important; color: #000 ! important; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="action-bar no-print">
            <a href="/" class="btn btn-outline-secondary rounded-pill px-4">Back to Dashboard</a>
            <button onclick="window.print()" class="btn btn-print"><i class="fas fa-print"></i> Print Report</button>
            <a href="/download-closing-excel? ref_no={{ ref_no }}" class="btn btn-excel"><i class="fas fa-file-excel"></i> Download Excel</a>
        </div>
        <div class="company-header">
            <div class="company-name">COTTON CLOTHING BD LTD</div>
            <div class="report-title">CLOSING REPORT [ INPUT SECTION ]</div>
            <div class="date-section">Date: <span id="date"></span></div>
        </div>
        {% if report_data %}
        <div class="info-container">
            <div class="info-row">
                <div class="info-item">Buyer: <span class="info-value">{{ report_data[0].buyer }}</span></div>
                <div class="info-item">Style: <span class="info-value">{{ report_data[0].style }}</span></div>
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
                    {% for i in range(block. headers|length) %}
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
                        {% set ns. tot_3 = ns.tot_3 + qty_3 %}
                        {% set ns.tot_act = ns. tot_act + actual %}
                        {% set ns.tot_cut = ns.tot_cut + cut_qc %}
                        {% set ns. tot_inp = ns.tot_inp + inp_qty %}
                        {% set ns.tot_bal = ns.tot_bal + balance %}
                        {% set ns. tot_sp = ns.tot_sp + short_plus %}
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
                                0. 00%
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
        document.getElementById('date'). innerText = dateObj. toLocaleDateString('en-GB');
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
        .booking-border { border: 2px solid #000; padding: 2px 8px; display: inline-block; font-weight: 900; }
        .info-right { flex: 1; display: flex; flex-direction: column; justify-content: space-between; height: 100%; border-left: 1px solid #ddd; padding-left: 15px; }
        .right-item { font-size: 14px; margin-bottom: 8px; font-weight: 700; }
        .right-label { color: #555; }
        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .summary-header { font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px; text-transform: uppercase; }
        .summary-table { width: 100%; font-size: 13px; font-weight: 700; }
        .summary-table td { padding: 2px 5px; }
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50 !important; color: white ! important; padding: 10px; border: 1px solid #000; font-size: 14px; text-transform: uppercase; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; vertical-align: middle; color: #000; font-weight: 600; }
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-size: 16px; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; background: #fff; }
        . line-text-bold { font-size: 14px; font-weight: 800; opacity: 0.7; }
        . status-cell { font-size: 20px; color: green; font-weight: 900; }
        . qty-cell { font-size: 16px; font-weight: 800; }
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; margin: 0 2px; display: inline-block; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }
        .no-print { margin-bottom: 20px; text-align: right; }
        . btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; }
        .btn-add { background: #27ae60; }
        .generator-sig { text-align: right; font-size: 10px; margin-top: 5px; color: #555; }
        @media print {
            . no-print { display: none; }
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
                        <a href="/admin/accessories/edit? ref={{ ref }}&index={{ loop.index0 }}" class="action-btn btn-edit-row"><i class="fas fa-pencil-alt"></i></a>
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
<! DOCTYPE html>
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
        . report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; margin-top: 5px; }
        .date-section { font-size: 1.2rem; font-weight: 800; color: #000; margin-top: 5px; }
        .info-container { display: flex; justify-content: space-between; margin-bottom: 15px; gap: 15px; }
        .info-box { background: white; border: 1px solid #ddd; border-left: 5px solid #2c3e50; padding: 10px 15px; border-radius: 5px; flex: 2; box-shadow: 0 2px 5px rgba(0,0,0,0.05); display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .total-box { background: #2c3e50; color: white; padding: 10px 15px; border-radius: 5px; width: 240px; text-align: right; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); }
        . info-item { margin-bottom: 6px; font-size: 1.3rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        . info-label { font-weight: 800; color: #444; width: 90px; display: inline-block; }
        .info-value { font-weight: 800; color: #000; }
        .total-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
        . total-value { font-size: 2.5rem; font-weight: 800; line-height: 1.1; }
        .table-card { background: white; border-radius: 0; margin-bottom: 20px; overflow: hidden; border: 1px solid #dee2e6; }
        .color-header { background-color: #e9ecef; color: #2c3e50; padding: 10px 12px; font-size: 1.5rem; font-weight: 900; border-bottom: 1px solid #dee2e6; text-transform: uppercase; }
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; }
        .table th { background-color: #2c3e50; color: white; font-weight: 900; font-size: 1.2rem; text-align: center; border: 1px solid #34495e; padding: 8px 4px; vertical-align: middle; }
        . table th:empty { background-color: white ! important; border: none; }
        .table td { text-align: center; vertical-align: middle; border: 1px solid #dee2e6; padding: 6px 3px; color: #000; font-weight: 800; font-size: 1.15rem; }
        .table-striped tbody tr:nth-of-type(odd) { background-color: #f8f9fa; }
        .order-col { font-weight: 900 !important; text-align: center ! important; background-color: #fdfdfd; white-space: nowrap; width: 1%; }
        .total-col { font-weight: 900; background-color: #e8f6f3 !important; color: #16a085; border-left: 2px solid #1abc9c ! important; }
        .total-col-header { background-color: #e8f6f3 !important; color: #000 !important; font-weight: 900 !important; border: 1px solid #34495e !important; }
        .table-striped tbody tr. summary-row, .table-striped tbody tr.summary-row td { background-color: #d1ecff ! important; --bs-table-accent-bg: #d1ecff !important; color: #000 ! important; font-weight: 900 !important; border-top: 2px solid #aaa !important; font-size: 1.2rem !important; }
        .summary-label { text-align: right ! important; padding-right: 15px ! important; color: #000 !important; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 10px; }
        .btn-print { background-color: #e74c3c; color: white; border-radius: 50px; padding: 8px 30px; font-weight: 600; border: none; }
        .footer-credit { text-align: center; margin-top: 30px; margin-bottom: 20px; font-size: 0.8rem; color: #2c3e50; padding-top: 10px; border-top: 1px solid #ddd; }
        @media print {
            @page { margin: 5mm; size: portrait; }
            body { background-color: white; padding: 0; -webkit-print-color-adjust: exact ! important; print-color-adjust: exact !important; color-adjust: exact !important; }
            .container { max-width: 100% !important; width: 100% ! important; padding: 0; margin: 0; }
            .no-print { display: none !important; }
            .company-header { border-bottom: 2px solid #000; margin-bottom: 5px; padding-bottom: 5px; }
            .company-name { font-size: 1. 8rem; } 
            .info-container { margin-bottom: 10px; }
            .info-box { border: 1px solid #000 !important; border-left: 5px solid #000 !important; padding: 5px 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .total-box { border: 2px solid #000 !important; background: white !important; color: black !important; padding: 5px 10px; }
            .info-item { font-size: 13pt ! important; font-weight: 800 !important; }
            .table th, .table td { border: 1px solid #000 !important; padding: 2px ! important; font-size: 13pt !important; font-weight: 800 !important; }
            .table th:empty { background-color: white !important; border: none !important; }
            .table-striped tbody tr. summary-row td { background-color: #d1ecff !important; box-shadow: inset 0 0 0 9999px #d1ecff ! important; color: #000 ! important; font-weight: 900 ! important; }
            .color-header { background-color: #f1f1f1 !important; border: 1px solid #000 !important; font-size: 1.4rem !important; font-weight: 900; padding: 5px; margin-top: 10px; box-shadow: inset 0 0 0 9999px #f1f1f1 !important; }
            .total-col-header { background-color: #e8f6f3 !important; box-shadow: inset 0 0 0 9999px #e8f6f3 !important; color: #000 !important; }
            .table-card { border: none; margin-bottom: 10px; break-inside: avoid; }
            .footer-credit { display: block ! important; color: black; border-top: 1px solid #000; margin-top: 10px; font-size: 8pt !important; }
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
        const month = String(dateObj. getMonth() + 1).padStart(2, '0');
        const year = dateObj.getFullYear();
        document.getElementById('date'). innerText = `${day}-${month}-${year}`;
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE DASHBOARD TEMPLATE (NEW)
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MNM Software</title>
    {COMMON_STYLES}
    <style>
        . store-card {{
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 30px;
            transition: var(--transition-smooth);
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }}
        
        .store-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--gradient-orange);
            opacity: 0;
            transition: var(--transition-smooth);
        }}
        
        .store-card:hover {{
            transform: translateY(-8px);
            border-color: var(--accent-orange);
            box-shadow: 0 20px 40px rgba(255, 122, 0, 0.15);
        }}
        
        .store-card:hover::before {{
            opacity: 1;
        }}
        
        .store-card-icon {{
            width: 70px;
            height: 70px;
            border-radius: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin-bottom: 20px;
            transition: var(--transition-smooth);
        }}
        
        .store-card:hover .store-card-icon {{
            transform: scale(1.1) rotate(-5deg);
        }}
        
        . icon-orange {{ background: linear-gradient(145deg, rgba(255, 122, 0, 0.2), rgba(255, 122, 0, 0.05)); color: var(--accent-orange); }}
        . icon-purple {{ background: linear-gradient(145deg, rgba(139, 92, 246, 0.2), rgba(139, 92, 246, 0.05)); color: var(--accent-purple); }}
        .icon-green {{ background: linear-gradient(145deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05)); color: var(--accent-green); }}
        .icon-blue {{ background: linear-gradient(145deg, rgba(59, 130, 246, 0. 2), rgba(59, 130, 246, 0. 05)); color: var(--accent-blue); }}
        . icon-cyan {{ background: linear-gradient(145deg, rgba(6, 182, 212, 0.2), rgba(6, 182, 212, 0.05)); color: var(--accent-cyan); }}
        .icon-red {{ background: linear-gradient(145deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.05)); color: var(--accent-red); }}
        
             . store-card-title {{
            font-size: 20px;
            font-weight: 700;
            color: white;
            margin-bottom: 8px;
        }}
        
        . store-card-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 20px;
        }}
        
        . store-card-stat {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 15px;
            border-top: 1px solid var(--border-color);
        }}
        
        .stat-number {{
            font-size: 28px;
            font-weight: 800;
            color: white;
        }}
        
        .stat-label {{
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        . store-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 24px;
            margin-top: 30px;
        }}
        
        . coming-soon-badge {{
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(255, 122, 0, 0.2);
            color: var(--accent-orange);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .quick-action {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.05);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 12px;
            color: var(--text-secondary);
            transition: var(--transition-smooth);
        }}
        
        .quick-action:hover {{
            background: var(--accent-orange);
            color: white;
        }}
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            <div class="nav-link active">
                <i class="fas fa-th-large"></i> Store Dashboard
            </div>
            <div class="nav-link" style="opacity: 0.5; cursor: not-allowed;">
                <i class="fas fa-box"></i> Products
                <span class="nav-badge" style="background: var(--accent-purple);">Soon</span>
            </div>
            <div class="nav-link" style="opacity: 0. 5; cursor: not-allowed;">
                <i class="fas fa-users"></i> Customers
                <span class="nav-badge" style="background: var(--accent-purple);">Soon</span>
            </div>
            <div class="nav-link" style="opacity: 0.5; cursor: not-allowed;">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
                <span class="nav-badge" style="background: var(--accent-purple);">Soon</span>
            </div>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">
            <i class="fas fa-code" style="margin-right: 5px;"></i> © 2025 Mehedi Hasan
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
            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-orange">
                    <i class="fas fa-boxes"></i>
                </div>
                <div class="store-card-title">Product Inventory</div>
                <div class="store-card-desc">
                    Manage aluminum products, profiles, sheets, and accessories.  Track stock levels and reorder points.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">0</div>
                        <div class="stat-label">Total Products</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-plus"></i> Add Product
                    </div>
                </div>
            </div>

            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-green">
                    <i class="fas fa-shopping-cart"></i>
                </div>
                <div class="store-card-title">Sales & Orders</div>
                <div class="store-card-desc">
                    Create new sales orders, manage pending orders, and track delivery status.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">0</div>
                        <div class="stat-label">Today's Sales</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-receipt"></i> New Sale
                    </div>
                </div>
            </div>

            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-purple">
                    <i class="fas fa-users"></i>
                </div>
                <div class="store-card-title">Customer Management</div>
                <div class="store-card-desc">
                    Maintain customer database, track purchase history, and manage credit accounts.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">0</div>
                        <div class="stat-label">Total Customers</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-user-plus"></i> Add Customer
                    </div>
                </div>
            </div>

            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-blue">
                    <i class="fas fa-file-invoice-dollar"></i>
                </div>
                <div class="store-card-title">Invoices & Billing</div>
                <div class="store-card-desc">
                    Generate professional invoices, track payments, and manage outstanding dues.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">৳0</div>
                        <div class="stat-label">This Month</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-file-alt"></i> Create Invoice
                    </div>
                </div>
            </div>

            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-red">
                    <i class="fas fa-wallet"></i>
                </div>
                <div class="store-card-title">Expense Tracker</div>
                <div class="store-card-desc">
                    Record daily expenses, categorize costs, and monitor profit margins.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">৳0</div>
                        <div class="stat-label">Total Expense</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-plus"></i> Add Expense
                    </div>
                </div>
            </div>

            <div class="store-card">
                <span class="coming-soon-badge">Coming Soon</span>
                <div class="store-card-icon icon-cyan">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="store-card-title">Reports & Analytics</div>
                <div class="store-card-desc">
                    View sales reports, profit analysis, stock movement, and business insights.
                </div>
                <div class="store-card-stat">
                    <div>
                        <div class="stat-number">0</div>
                        <div class="stat-label">Reports Generated</div>
                    </div>
                    <div class="quick-action">
                        <i class="fas fa-download"></i> Export Report
                    </div>
                </div>
            </div>
        </div>

        <div class="card" style="margin-top: 30px;">
            <div class="section-header">
                <span><i class="fas fa-info-circle" style="margin-right: 10px; color: var(--accent-orange);"></i>About Store Module</span>
            </div>
            <p style="color: var(--text-secondary); line-height: 1.8; font-size: 14px;">
                এই Store মডিউলটি একটি এলুমিনিয়াম দোকানের জন্য ডিজাইন করা হয়েছে। এখানে আপনি প্রোডাক্ট ইনভেন্টরি, 
                সেলস অর্ডার, কাস্টমার ম্যানেজমেন্ট, ইনভয়েস জেনারেশন, খরচ ট্র্যাকিং এবং বিজনেস রিপোর্ট তৈরি করতে পারবেন।
                <br><br>
                <strong style="color: var(--accent-orange);">Coming Soon:</strong> সকল ফিচার শীঘ্রই অ্যাক্টিভ করা হবে।
            </p>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# FLASK ROUTES (CONTROLLER LOGIC)
# ==============================================================================

@app. route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        if session. get('role') == 'admin':
            stats = get_dashboard_summary_v2()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            perms = session.get('permissions', [])
            if len(perms) == 1 and 'accessories' in perms:
                return redirect(url_for('accessories_search_page'))
            else:
                return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form. get('password')

    users_db = load_users()

    if username in users_db and users_db[username]['password'] == password:
        session. permanent = True
        session['logged_in'] = True
        session['user'] = username
        session['role'] = users_db[username]['role']
        session['permissions'] = users_db[username]. get('permissions', [])
        
        now = get_bd_time()
        session['login_start'] = now. isoformat()
        
        users_db[username]['last_login'] = now.strftime('%I:%M %p, %d %b')
        save_users(users_db)
        
        return redirect(url_for('index'))
    else:
        flash('Invalid Username or Password.')
        return redirect(url_for('index'))

@app. route('/logout')
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
        except:
            pass

    session.clear()
    flash('Session terminated.')
    return redirect(url_for('index'))


# ==============================================================================
# USER MANAGEMENT ROUTES
# ==============================================================================

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
    password = data.get('password', ''). strip()
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

@app. route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    username = request.json. get('username')
    users_db = load_users()
    
    if username == 'Admin':
        return jsonify({'status': 'error', 'message': 'Cannot delete Main Admin!'})

    if username in users_db:
        del users_db[username]
        save_users(users_db)
        return jsonify({'status': 'success', 'message': 'User deleted!'})
    
    return jsonify({'status': 'error', 'message': 'User not found'})


# ==============================================================================
# STORE ROUTE (NEW)
# ==============================================================================

@app.route('/admin/store')
def store_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template_string(STORE_DASHBOARD_TEMPLATE)


# ==============================================================================
# CLOSING REPORT ROUTES
# ==============================================================================

@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    internal_ref_no = request.form['ref_no']
    if not internal_ref_no:
        return redirect(url_for('index'))

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
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    internal_ref_no = request.args.get('ref_no')
    
    try:
        report_data = fetch_closing_report_data(internal_ref_no)
        if report_data:
            excel_file = create_formatted_excel_report(report_data, internal_ref_no)
            update_stats(internal_ref_no, session.get('user', 'Unknown'))
            return make_response(send_file(
                excel_file,
                as_attachment=True,
                download_name=f"Report-{internal_ref_no. replace('/', '_')}.xlsx",
                mimetype='application/vnd. openxmlformats-officedocument.spreadsheetml.sheet'
            ))
        else:
            flash("Data source returned empty.")
            return redirect(url_for('index'))
    except Exception as e:
        flash("Failed to generate Excel.")
        return redirect(url_for('index'))


# ==============================================================================
# ACCESSORIES ROUTES
# ==============================================================================

@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    if 'accessories' not in session. get('permissions', []):
        flash("Access Denied")
        return redirect(url_for('index'))
    return render_template_string(ACCESSORIES_SEARCH_TEMPLATE)

@app.route('/admin/accessories/input', methods=['POST'])
def accessories_input_page():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ref_no = request. form.get('ref_no') or request.args.get('ref')
    if ref_no:
        ref_no = ref_no.strip(). upper()
    
    if not ref_no:
        return redirect(url_for('accessories_search_page'))

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
            style = api_data[0]. get('style', 'N/A')
            buyer = api_data[0].get('buyer', 'N/A')
            challans = []
            
            db_acc[ref_no] = {
                "style": style,
                "buyer": buyer,
                "colors": colors,
                "item_type": "",
                "challans": challans
            }
            save_accessories_db(db_acc)
        except:
            flash("Connection Error with ERP")
            return redirect(url_for('accessories_search_page'))

    return render_template_string(
        ACCESSORIES_INPUT_TEMPLATE,
        ref=ref_no,
        colors=colors,
        style=style,
        buyer=buyer,
        challans=challans
    )

@app.route('/admin/accessories/input_direct')
def accessories_input_direct():
    return accessories_input_page()

@app.route('/admin/accessories/save', methods=['POST'])
def accessories_save():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ref = request.form.get('ref'). strip(). upper()
    db_acc = load_accessories_db()
    
    if ref in db_acc:
        if request.form.get('item_type'):
            db_acc[ref]['item_type'] = request.form. get('item_type')
        
        for item in db_acc[ref]['challans']:
            item['status'] = "✔"
        
        new_entry = {
            "date": get_bd_date_str(),
            "line": request.form.get('line_no'),
            "color": request.form. get('color'),
            "size": request.form. get('size'),
            "qty": request.form. get('qty'),
            "status": ""
        }
        db_acc[ref]['challans'].append(new_entry)
        save_accessories_db(db_acc)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/print', methods=['GET'])
def accessories_print_view():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ref = request.args.get('ref'). strip().upper()
    db_acc = load_accessories_db()
    
    if ref not in db_acc:
        return redirect(url_for('accessories_search_page'))
    
    data = db_acc[ref]
    challans = data['challans']
    
    line_summary = {}
    for c in challans:
        ln = c['line']
        try:
            q = int(c['qty'])
        except:
            q = 0
        line_summary[ln] = line_summary.get(ln, 0) + q
    sorted_line_summary = dict(sorted(line_summary.items()))

    return render_template_string(
        ACCESSORIES_REPORT_TEMPLATE,
        ref=ref,
        buyer=data['buyer'],
        style=data['style'],
        item_type=data. get('item_type', ''),
        challans=challans,
        line_summary=sorted_line_summary,
        count=len(challans),
        today=get_bd_date_str()
    )

@app.route('/admin/accessories/edit', methods=['GET'])
def accessories_edit():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ref = request.args.get('ref')
    try:
        index = int(request.args.get('index'))
    except:
        return redirect(url_for('accessories_search_page'))
    
    db_acc = load_accessories_db()
    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        item = db_acc[ref]['challans'][index]
        return render_template_string(ACCESSORIES_EDIT_TEMPLATE, ref=ref, index=index, item=item)
    
    return redirect(url_for('accessories_print_view', ref=ref))

@app.route('/admin/accessories/update', methods=['POST'])
def accessories_update():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    index = int(request.form. get('index'))
    db_acc = load_accessories_db()

    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        db_acc[ref]['challans'][index]['line'] = request.form. get('line_no')
        db_acc[ref]['challans'][index]['color'] = request.form.get('color')
        db_acc[ref]['challans'][index]['size'] = request.form. get('size')
        db_acc[ref]['challans'][index]['qty'] = request.form.get('qty')
        save_accessories_db(db_acc)
    
    return redirect(url_for('accessories_input_direct', ref=ref))

@app.route('/admin/accessories/delete', methods=['POST'])
def accessories_delete():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('index'))
    
    ref = request.form.get('ref')
    index = int(request. form.get('index'))
    db_acc = load_accessories_db()

    if ref in db_acc and 0 <= index < len(db_acc[ref]['challans']):
        del db_acc[ref]['challans'][index]
        save_accessories_db(db_acc)
    
    return redirect(url_for('accessories_input_direct', ref=ref))


# ==============================================================================
# PO SHEET ROUTE
# ==============================================================================

@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session. get('logged_in'):
        return redirect(url_for('index'))

    if os.path.exists(UPLOAD_FOLDER):
        shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER)

    try:
        uploaded_files = request. files.getlist('pdf_files')
        all_data = []
        final_meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
        
        for file in uploaded_files:
            if file. filename == '':
                continue
            file_path = os. path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            data, meta = extract_data_dynamic(file_path)
            if meta['buyer'] != 'N/A':
                final_meta = meta
            if data:
                all_data.extend(data)
        
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
            pivot = color_df.pivot_table(
                index='P.O NO',
                columns='Size',
                values='Quantity',
                aggfunc='sum',
                fill_value=0
            )
            
            pivot.columns. name = None
            
            try:
                sorted_cols = sort_sizes(pivot. columns. tolist())
                pivot = pivot[sorted_cols]
            except:
                pass
            
            pivot['Total'] = pivot.sum(axis=1)
            grand_total_qty += pivot['Total'].sum()

            actual_qty = pivot. sum()
            actual_qty. name = 'Actual Qty'
            qty_plus_3 = (actual_qty * 1.03).round(). astype(int)
            qty_plus_3.name = '3% Order Qty'
            
            pivot_final = pd.concat([pivot, actual_qty. to_frame(). T, qty_plus_3.to_frame().T])
            pivot_final = pivot_final.reset_index()
            pivot_final = pivot_final.rename(columns={'index': 'P. O NO'})
            
            pd.set_option('colheader_justify', 'center')
            html_table = pivot_final.to_html(
                classes='table table-bordered table-striped',
                index=False,
                border=0
            )
            
            html_table = re.sub(r'<tr>\s*<td>', '<tr><td class="order-col">', html_table)
            html_table = html_table.replace('<th>Total</th>', '<th class="total-col-header">Total</th>')
            html_table = html_table.replace('<td>Total</td>', '<td class="total-col">Total</td>')
            html_table = html_table.replace('<td>Actual Qty</td>', '<td class="summary-label">Actual Qty</td>')
            html_table = html_table.replace('<td>3% Order Qty</td>', '<td class="summary-label">3% Order Qty</td>')
            html_table = re.sub(
                r'<tr>\s*<td class="summary-label">',
                '<tr class="summary-row"><td class="summary-label">',
                html_table
            )

            final_tables. append({'color': color, 'table': html_table})
            
        return render_template_string(
            PO_REPORT_TEMPLATE,
            tables=final_tables,
            meta=final_meta,
            grand_total=f"{grand_total_qty:,}"
        )
    except Exception as e:
        flash(f"Error processing files: {str(e)}")
        return redirect(url_for('index'))


# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
