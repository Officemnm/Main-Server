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
app. secret_key = 'super-secret-secure-key-bd' 

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
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/? appName=Office"

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
# Authentication এবং User Management Functions
# ==============================================================================

def init_admin_user():
    """ডিফল্ট অ্যাডমিন ইউজার তৈরি করে যদি না থাকে"""
    try:
        if users_col.count_documents({}) == 0:
            users_col.insert_one({
                'username': 'admin',
                'password': 'admin123',
                'role': 'admin',
                'created_at': get_bd_time()
            })
            print("Default admin user created!")
    except Exception as e:
        print(f"Error creating admin user: {e}")

# অ্যাপ্লিকেশন স্টার্টে অ্যাডমিন ইউজার তৈরি
init_admin_user()

def login_required(f):
    """ডেকোরেটর: লগইন চেক করে"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login first! ', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """ডেকোরেটর: অ্যাডমিন চেক করে"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login first! ', 'warning')
            return redirect(url_for('login'))
        if session. get('role') != 'admin':
            flash('Admin access required!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def store_login_required(f):
    """ডেকোরেটর: স্টোর লগইন চেক করে"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'store_user' not in session:
            flash('Please login to store first!', 'warning')
            return redirect(url_for('store_login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# Main Authentication Routes
# ==============================================================================

@app.route('/')
def index():
    """মূল পেজ - লগইন থাকলে ড্যাশবোর্ডে পাঠায়"""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """লগইন পেজ"""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    
    if request. method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password required!', 'danger')
            return redirect(url_for('login'))
        
        # Database থেকে ইউজার খুঁজুন
        user = users_col.find_one({'username': username, 'password': password})
        
        if user:
            session. permanent = True
            session['username'] = username
            session['role'] = user. get('role', 'user')
            session['login_time'] = get_bd_time(). isoformat()
            flash(f'Welcome {username}! ', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
            return redirect(url_for('login'))
    
    # GET request - লগইন ফর্ম দেখান
    login_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Login - Office System</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                max-width: 400px;
                width: 100%;
            }
            .login-title {
                color: #667eea;
                font-weight: bold;
                margin-bottom: 30px;
                text-align: center;
            }
            .btn-login {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                padding: 12px;
                font-weight: bold;
            }
            .btn-login:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2 class="login-title">🔐 Office Login</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <form method="POST" action="{{ url_for('login') }}">
                <div class="mb-3">
                    <label class="form-label">Username</label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary btn-login w-100">Login</button>
            </form>
            
            <div class="text-center mt-3">
                <a href="{{ url_for('store_login') }}" class="text-decoration-none">Store Login →</a>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(login_html)

@app.route('/logout')
def logout():
    """লগআউট"""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

# ==============================================================================
# Store Authentication Routes
# ==============================================================================

@app.route('/store/login', methods=['GET', 'POST'])
def store_login():
    """স্টোর লগইন পেজ"""
    if 'store_user' in session:
        return redirect(url_for('store_panel'))
    
    if request. method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password required!', 'danger')
            return redirect(url_for('store_login'))
        
        # Database থেকে স্টোর ইউজার খুঁজুন
        user = store_users_col.find_one({'username': username, 'password': password, 'status': 'active'})
        
        if user:
            session.permanent = True
            session['store_user'] = username
            session['store_role'] = user.get('role', 'staff')
            session['store_login_time'] = get_bd_time().isoformat()
            flash(f'Welcome to Store, {username}!', 'success')
            return redirect(url_for('store_panel'))
        else:
            flash('Invalid credentials or inactive account!', 'danger')
            return redirect(url_for('store_login'))
    
    # GET request - স্টোর লগইন ফর্ম
    store_login_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Store Login</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                max-width: 400px;
                width: 100%;
            }
            .login-title {
                color: #11998e;
                font-weight: bold;
                margin-bottom: 30px;
                text-align: center;
            }
            .btn-login {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                border: none;
                padding: 12px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2 class="login-title">🏪 Store Login</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Username</label>
                    <input type="text" name="username" class="form-control" required autofocus>
                </div>
                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-primary btn-login w-100">Login to Store</button>
            </form>
            
            <div class="text-center mt-3">
                <a href="{{ url_for('login') }}" class="text-decoration-none">← Back to Main Login</a>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(store_login_html)

@app.route('/store/logout')
def store_logout():
    """স্টোর লগআউট"""
    session.pop('store_user', None)
    session.pop('store_role', None)
    session.pop('store_login_time', None)
    flash('Logged out from store! ', 'success')
    return redirect(url_for('store_login'))
    # ==============================================================================
# Dashboard এবং Main Routes
# ==============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """মূল ড্যাশবোর্ড পেজ"""
    username = session.get('username')
    role = session.get('role', 'user')
    
    # স্ট্যাটিস্টিক্স সংগ্রহ
    total_users = users_col.count_documents({})
    total_accessories = accessories_col.count_documents({})
    total_store_products = store_products_col.count_documents({})
    total_store_invoices = store_invoices_col.count_documents({})
    
    dashboard_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Dashboard - Office System</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0. 0/css/all.min. css">
        <style>
            body {
                background: #f8f9fa;
            }
            .navbar {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .navbar-brand {
                font-weight: bold;
                font-size: 1.5rem;
            }
            .card {
                border: none;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                transition: transform 0. 3s;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            .card-icon {
                font-size: 3rem;
                margin-bottom: 20px;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
                color: #667eea;
            }
            . menu-card {
                cursor: pointer;
                height: 100%;
                padding: 30px;
            }
            .menu-card-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
            .menu-card-success { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
            .menu-card-warning { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; }
            .menu-card-info { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }
            .menu-card-danger { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white; }
        </style>
    </head>
    <body>
        <!-- Navbar -->
        <nav class="navbar navbar-expand-lg navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-building"></i> Office System
                </a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <div class="collapse navbar-collapse" id="navbarNav">
                    <ul class="navbar-nav ms-auto">
                        <li class="nav-item">
                            <span class="nav-link">👤 {{ username }} ({{ role }})</span>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('logout') }}">
                                <i class="fas fa-sign-out-alt"></i> Logout
                            </a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>

        <!-- Main Content -->
        <div class="container mt-4">
            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Statistics -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="stat-card text-center">
                        <i class="fas fa-users" style="font-size: 2rem; color: #667eea;"></i>
                        <div class="stat-number">{{ total_users }}</div>
                        <div class="text-muted">Total Users</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card text-center">
                        <i class="fas fa-box" style="font-size: 2rem; color: #11998e;"></i>
                        <div class="stat-number">{{ total_accessories }}</div>
                        <div class="text-muted">Accessories</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card text-center">
                        <i class="fas fa-shopping-cart" style="font-size: 2rem; color: #f5576c;"></i>
                        <div class="stat-number">{{ total_store_products }}</div>
                        <div class="text-muted">Store Products</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-card text-center">
                        <i class="fas fa-file-invoice" style="font-size: 2rem; color: #4facfe;"></i>
                        <div class="stat-number">{{ total_store_invoices }}</div>
                        <div class="text-muted">Invoices</div>
                    </div>
                </div>
            </div>

            <!-- Menu Cards -->
            <h3 class="mb-4">Main Menu</h3>
            <div class="row">
                <!-- Closing Report -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-primary" onclick="location.href='{{ url_for('form') }}'">
                        <div class="text-center">
                            <i class="fas fa-file-alt card-icon"></i>
                            <h4>Closing Report</h4>
                            <p>Generate daily closing reports</p>
                        </div>
                    </div>
                </div>

                <!-- PO Sheet -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-success" onclick="location.href='{{ url_for('po_form') }}'">
                        <div class="text-center">
                            <i class="fas fa-file-invoice card-icon"></i>
                            <h4>PO Sheet</h4>
                            <p>Upload and process PO files</p>
                        </div>
                    </div>
                </div>

                <!-- Store Management -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-info" onclick="location.href='{{ url_for('store_panel') }}'">
                        <div class="text-center">
                            <i class="fas fa-store card-icon"></i>
                            <h4>Store Panel</h4>
                            <p>Manage store operations</p>
                        </div>
                    </div>
                </div>

                <!-- Accessories -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-warning" onclick="location.href='{{ url_for('accessories_page') }}'">
                        <div class="text-center">
                            <i class="fas fa-toolbox card-icon"></i>
                            <h4>Accessories</h4>
                            <p>Manage accessories inventory</p>
                        </div>
                    </div>
                </div>

                {% if role == 'admin' %}
                <!-- User Management (Admin Only) -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-danger" onclick="location.href='{{ url_for('user_management') }}'">
                        <div class="text-center">
                            <i class="fas fa-users-cog card-icon"></i>
                            <h4>User Management</h4>
                            <p>Manage system users</p>
                        </div>
                    </div>
                </div>

                <!-- Store User Management (Admin Only) -->
                <div class="col-md-4 mb-4">
                    <div class="card menu-card menu-card-primary" onclick="location.href='{{ url_for('store_user_management') }}'">
                        <div class="text-center">
                            <i class="fas fa-user-tie card-icon"></i>
                            <h4>Store Users</h4>
                            <p>Manage store users</p>
                        </div>
                    </div>
                </div>
                {% endif %}
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(dashboard_html, 
                                 username=username, 
                                 role=role,
                                 total_users=total_users,
                                 total_accessories=total_accessories,
                                 total_store_products=total_store_products,
                                 total_store_invoices=total_store_invoices)

# ==============================================================================
# User Management (Admin Only)
# ==============================================================================

@app.route('/user-management', methods=['GET', 'POST'])
@admin_required
def user_management():
    """ইউজার ম্যানেজমেন্ট পেজ (শুধুমাত্র অ্যাডমিন)"""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form. get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'user')
            
            if not username or not password:
                flash('Username and password required!', 'danger')
                return redirect(url_for('user_management'))
            
            # চেক করুন ইউজার আছে কিনা
            if users_col.find_one({'username': username}):
                flash('Username already exists! ', 'danger')
                return redirect(url_for('user_management'))
            
            users_col.insert_one({
                'username': username,
                'password': password,
                'role': role,
                'created_at': get_bd_time(),
                'created_by': session.get('username')
            })
            flash(f'User {username} added successfully!', 'success')
            return redirect(url_for('user_management'))
        
        elif action == 'delete':
            username = request.form.get('username')
            if username == 'admin':
                flash('Cannot delete admin user!', 'danger')
                return redirect(url_for('user_management'))
            
            users_col.delete_one({'username': username})
            flash(f'User {username} deleted! ', 'success')
            return redirect(url_for('user_management'))
    
    # সব ইউজার লিস্ট
    users = list(users_col.find())
    
    user_mgmt_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>User Management</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card { border: none; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
            </div>
        </nav>

        <div class="container mt-4">
            <h2 class="mb-4"><i class="fas fa-users-cog"></i> User Management</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Add User Form -->
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Add New User</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="add">
                        <div class="row">
                            <div class="col-md-4">
                                <input type="text" name="username" class="form-control" placeholder="Username" required>
                            </div>
                            <div class="col-md-3">
                                <input type="text" name="password" class="form-control" placeholder="Password" required>
                            </div>
                            <div class="col-md-3">
                                <select name="role" class="form-select">
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <button type="submit" class="btn btn-primary w-100">Add User</button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Users List -->
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">All Users</h5>
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Username</th>
                                    <th>Role</th>
                                    <th>Created At</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for user in users %}
                                <tr>
                                    <td>{{ user.username }}</td>
                                    <td>
                                        {% if user.role == 'admin' %}
                                            <span class="badge bg-danger">Admin</span>
                                        {% else %}
                                            <span class="badge bg-primary">User</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ user.created_at.strftime('%d-%m-%Y %H:%M') if user.created_at else 'N/A' }}</td>
                                    <td>
                                        {% if user.username != 'admin' %}
                                        <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this user?');">
                                            <input type="hidden" name="action" value="delete">
                                            <input type="hidden" name="username" value="{{ user.username }}">
                                            <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                                        </form>
                                        {% else %}
                                        <span class="text-muted">Protected</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(user_mgmt_html, users=users)
    # ==============================================================================
# Closing Report Functions
# ==============================================================================

def fetch_data_from_url(url):
    """URL থেকে ডেটা ফেচ করে"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response. text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def parse_html_data(html_content):
    """HTML কন্টেন্ট পার্স করে ডেটা বের করে"""
    soup = BeautifulSoup(html_content, 'html.parser')
    data = []
    
    try:
        table = soup.find('table')
        if not table:
            return data
        
        rows = table.find_all('tr')[1:]  # হেডার স্কিপ করুন
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 8:
                data.append({
                    'date': cols[0].text. strip(),
                    'order_id': cols[1].text.strip(),
                    'customer_name': cols[2].text.strip(),
                    'customer_phone': cols[3].text.strip(),
                    'product': cols[4].text.strip(),
                    'quantity': cols[5].text.strip(),
                    'price': cols[6]. text.strip(),
                    'status': cols[7].text.strip()
                })
    except Exception as e:
        print(f"Error parsing HTML: {e}")
    
    return data

def create_closing_report_excel(data, logo_path=None):
    """Closing Report এর জন্য Excel তৈরি করে"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Closing Report"
    
    # স্টাইল ডিফাইন করুন
    header_font = Font(bold=True, size=12, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # লোগো যোগ করুন (যদি থাকে)
    row_start = 1
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            img.width = 100
            img.height = 50
            ws.add_image(img, 'A1')
            row_start = 4
        except:
            pass
    
    # শিরোনাম
    ws.merge_cells(f'A{row_start}:H{row_start}')
    title_cell = ws[f'A{row_start}']
    title_cell.value = "Daily Closing Report"
    title_cell.font = Font(bold=True, size=16, color="4472C4")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # তারিখ
    row_start += 1
    ws.merge_cells(f'A{row_start}:H{row_start}')
    date_cell = ws[f'A{row_start}']
    date_cell.value = f"Date: {get_bd_date_str()}"
    date_cell. font = Font(size=11)
    date_cell.alignment = Alignment(horizontal="center")
    
    # হেডার রো
    row_start += 2
    headers = ['Date', 'Order ID', 'Customer Name', 'Phone', 'Product', 'Qty', 'Price', 'Status']
    
    for col_num, header in enumerate(headers, 1):
        cell = ws. cell(row=row_start, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell. alignment = header_alignment
        cell.border = thin_border
    
    # ডেটা রো
    for row_num, item in enumerate(data, row_start + 1):
        ws.cell(row=row_num, column=1, value=item. get('date', '')).border = thin_border
        ws. cell(row=row_num, column=2, value=item. get('order_id', '')). border = thin_border
        ws.cell(row=row_num, column=3, value=item.get('customer_name', '')).border = thin_border
        ws.cell(row=row_num, column=4, value=item.get('customer_phone', '')).border = thin_border
        ws.cell(row=row_num, column=5, value=item.get('product', '')).border = thin_border
        ws.cell(row=row_num, column=6, value=item.get('quantity', '')). border = thin_border
        
        price_cell = ws.cell(row=row_num, column=7, value=item.get('price', ''))
        price_cell. border = thin_border
        price_cell.alignment = Alignment(horizontal="right")
        
        ws.cell(row=row_num, column=8, value=item.get('status', '')).border = thin_border
    
    # কলাম প্রস্থ সেট করুন
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D']. width = 15
    ws. column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 8
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 12
    
    # সামারি যোগ করুন
    summary_row = len(data) + row_start + 2
    ws.merge_cells(f'A{summary_row}:F{summary_row}')
    summary_cell = ws[f'A{summary_row}']
    summary_cell.value = "Total Records:"
    summary_cell.font = Font(bold=True)
    summary_cell.alignment = Alignment(horizontal="right")
    
    total_cell = ws. cell(row=summary_row, column=7)
    total_cell.value = len(data)
    total_cell.font = Font(bold=True)
    total_cell.border = thin_border
    
    return wb

# ==============================================================================
# Closing Report Routes
# ==============================================================================

@app.route('/closing-report')
@login_required
def form():
    """Closing Report ফর্ম পেজ"""
    form_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Closing Report</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card {
                border: none;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0. 1);
                margin-top: 30px;
            }
            . card-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 15px 15px 0 0 !important;
                padding: 20px;
            }
            .btn-generate {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                padding: 12px 30px;
                font-weight: bold;
            }
            .btn-generate:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <span class="navbar-text text-white">
                    <i class="fas fa-user"></i> {{ session.get('username') }}
                </span>
            </div>
        </nav>

        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="mb-0"><i class="fas fa-file-alt"></i> Generate Closing Report</h4>
                        </div>
                        <div class="card-body p-4">
                            {% with messages = get_flashed_messages(with_categories=true) %}
                                {% if messages %}
                                    {% for category, message in messages %}
                                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                            {{ message }}
                                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                        </div>
                                    {% endfor %}
                                {% endif %}
                            {% endwith %}

                            <form action="{{ url_for('preview_closing_report') }}" method="POST" enctype="multipart/form-data">
                                <div class="mb-3">
                                    <label class="form-label">
                                        <i class="fas fa-link"></i> Data Source URL (Optional)
                                    </label>
                                    <input type="url" name="url" class="form-control" 
                                           placeholder="https://example.com/data">
                                    <small class="text-muted">Leave empty if uploading file</small>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label">
                                        <i class="fas fa-upload"></i> Upload Data File (Optional)
                                    </label>
                                    <input type="file" name="datafile" class="form-control" accept=".xlsx,.xls,. csv">
                                    <small class="text-muted">Excel or CSV format</small>
                                </div>

                                <div class="mb-4">
                                    <label class="form-label">
                                        <i class="fas fa-image"></i> Company Logo (Optional)
                                    </label>
                                    <input type="file" name="logo" class="form-control" accept="image/*">
                                    <small class="text-muted">PNG, JPG, or JPEG format</small>
                                </div>

                                <div class="d-grid">
                                    <button type="submit" class="btn btn-primary btn-generate">
                                        <i class="fas fa-eye"></i> Preview Report
                                    </button>
                                </div>
                            </form>

                            <div class="alert alert-info mt-4">
                                <i class="fas fa-info-circle"></i> 
                                <strong>Note:</strong> You can provide a URL or upload a file.  The report will be previewed before download.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(form_html)

@app.route('/preview-closing-report', methods=['POST'])
@login_required
def preview_closing_report():
    """Closing Report প্রিভিউ পেজ"""
    data = []
    logo_path = None
    
    # URL থেকে ডেটা ফেচ
    url = request.form.get('url', '').strip()
    if url:
        html_content = fetch_data_from_url(url)
        if html_content:
            data = parse_html_data(html_content)
    
    # ফাইল থেকে ডেটা পড়ুন
    if 'datafile' in request.files:
        file = request.files['datafile']
        if file and file.filename:
            try:
                if file. filename.endswith('.csv'):
                    df = pd. read_csv(file)
                else:
                    df = pd. read_excel(file)
                
                data = df.to_dict('records')
            except Exception as e:
                flash(f'Error reading file: {str(e)}', 'danger')
                return redirect(url_for('form'))
    
    # লোগো প্রসেস করুন
    if 'logo' in request.files:
        logo = request.files['logo']
        if logo and logo.filename:
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logo_' + logo.filename)
            logo.save(logo_path)
    
    if not data:
        flash('No data found!  Please provide URL or file.', 'warning')
        return redirect(url_for('form'))
    
    # সেশনে ডেটা সেভ করুন
    session['closing_report_data'] = data
    session['closing_report_logo'] = logo_path
    
    preview_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Preview Closing Report</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .preview-card {
                background: white;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                padding: 30px;
                margin-top: 20px;
            }
            . table-responsive {
                max-height: 500px;
                overflow-y: auto;
            }
            . btn-download {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                border: none;
                padding: 12px 30px;
                font-weight: bold;
                color: white;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('form') }}">
                    <i class="fas fa-arrow-left"></i> Back
                </a>
                <span class="navbar-text text-white">
                    Preview Mode
                </span>
            </div>
        </nav>

        <div class="container">
            <div class="preview-card">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h3><i class="fas fa-file-alt"></i> Closing Report Preview</h3>
                    <form action="{{ url_for('download_closing_report') }}" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-download">
                            <i class="fas fa-download"></i> Download Excel
                        </button>
                    </form>
                </div>

                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 
                    Total Records: <strong>{{ data|length }}</strong> | 
                    Date: <strong>{{ current_date }}</strong>
                </div>

                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead class="table-primary">
                            <tr>
                                <th>Date</th>
                                <th>Order ID</th>
                                <th>Customer</th>
                                <th>Phone</th>
                                <th>Product</th>
                                <th>Qty</th>
                                <th>Price</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in data %}
                            <tr>
                                <td>{{ item.get('date', 'N/A') }}</td>
                                <td>{{ item.get('order_id', 'N/A') }}</td>
                                <td>{{ item.get('customer_name', 'N/A') }}</td>
                                <td>{{ item.get('customer_phone', 'N/A') }}</td>
                                <td>{{ item.get('product', 'N/A') }}</td>
                                <td>{{ item.get('quantity', 'N/A') }}</td>
                                <td>{{ item.get('price', 'N/A') }}</td>
                                <td>
                                    {% if item.get('status') == 'Completed' %}
                                        <span class="badge bg-success">{{ item.get('status') }}</span>
                                    {% else %}
                                        <span class="badge bg-warning">{{ item.get('status', 'N/A') }}</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(preview_html, data=data, current_date=get_bd_date_str())

@app.route('/download-closing-report', methods=['POST'])
@login_required
def download_closing_report():
    """Closing Report ডাউনলোড করুন"""
    data = session.get('closing_report_data', [])
    logo_path = session. get('closing_report_logo')
    
    if not data:
        flash('No data to download! ', 'danger')
        return redirect(url_for('form'))
    
    # Excel তৈরি করুন
    wb = create_closing_report_excel(data, logo_path)
    
    # Memory buffer এ সেভ করুন
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # সেশন ক্লিয়ার করুন
    session. pop('closing_report_data', None)
    session.pop('closing_report_logo', None)
    
    filename = f"Closing_Report_{get_bd_date_str()}. xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument. spreadsheetml.sheet',
        as_attachment=True,# ==============================================================================
# PO Sheet Functions
# ==============================================================================

def process_po_file(file_path):
    """PO ফাইল প্রসেস করে ডেটা বের করে"""
    try:
        df = pd.read_excel(file_path)
        
        # প্রয়োজনীয় কলাম চেক করুন
        required_cols = ['PO Number', 'Item', 'Quantity', 'Unit Price', 'Total']
        
        # কলাম নাম নরমালাইজ করুন
        df.columns = df.columns.str.strip()
        
        data = []
        for _, row in df.iterrows():
            item_data = {}
            for col in df.columns:
                item_data[col] = str(row[col]) if pd.notna(row[col]) else ''
            data. append(item_data)
        
        return data, list(df.columns)
    except Exception as e:
        print(f"Error processing PO file: {e}")
        return [], []

def create_po_sheet_excel(data, columns, logo_path=None):
    """PO Sheet এর জন্য Excel তৈরি করে"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PO Sheet"
    
    # স্টাইল ডিফাইন
    header_font = Font(bold=True, size=12, color="FFFFFF")
    header_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # লোগো যোগ করুন
    row_start = 1
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            img.width = 120
            img.height = 60
            ws.add_image(img, 'A1')
            row_start = 5
        except:
            pass
    
    # শিরোনাম
    col_count = len(columns)
    ws.merge_cells(f'A{row_start}:{openpyxl.utils.get_column_letter(col_count)}{row_start}')
    title_cell = ws[f'A{row_start}']
    title_cell.value = "Purchase Order Sheet"
    title_cell.font = Font(bold=True, size=16, color="2E75B6")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # তারিখ
    row_start += 1
    ws.merge_cells(f'A{row_start}:{openpyxl.utils.get_column_letter(col_count)}{row_start}')
    date_cell = ws[f'A{row_start}']
    date_cell.value = f"Generated: {get_bd_time(). strftime('%d-%m-%Y %H:%M')}"
    date_cell.font = Font(size=11)
    date_cell.alignment = Alignment(horizontal="center")
    
    # হেডার রো
    row_start += 2
    for col_num, header in enumerate(columns, 1):
        cell = ws. cell(row=row_start, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell. alignment = header_alignment
        cell.border = thin_border
    
    # ডেটা রো
    for row_num, item in enumerate(data, row_start + 1):
        for col_num, col_name in enumerate(columns, 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell. value = item.get(col_name, '')
            cell.border = thin_border
            
            # সংখ্যা ফরম্যাটিং
            if 'price' in col_name.lower() or 'total' in col_name.lower() or 'amount' in col_name.lower():
                cell.alignment = Alignment(horizontal="right")
                try:
                    cell.value = float(cell.value)
                    cell.number_format = '#,##0.00'
                except:
                    pass
    
    # কলাম প্রস্থ অটো-এডজাস্ট
    for col_num, col_name in enumerate(columns, 1):
        col_letter = openpyxl.utils.get_column_letter(col_num)
        max_length = len(col_name)
        
        for row in ws.iter_rows(min_row=row_start, max_row=len(data)+row_start, min_col=col_num, max_col=col_num):
            for cell in row:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
        
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[col_letter].width = adjusted_width
    
    # সামারি
    summary_row = len(data) + row_start + 2
    ws.merge_cells(f'A{summary_row}:{openpyxl.utils.get_column_letter(col_count-1)}{summary_row}')
    summary_cell = ws[f'A{summary_row}']
    summary_cell.value = "Total Items:"
    summary_cell.font = Font(bold=True)
    summary_cell.alignment = Alignment(horizontal="right")
    
    total_cell = ws.cell(row=summary_row, column=col_count)
    total_cell.value = len(data)
    total_cell.font = Font(bold=True)
    total_cell.border = thin_border
    total_cell.fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
    
    return wb

# ==============================================================================
# PO Sheet Routes
# ==============================================================================

@app.route('/po-sheet')
@login_required
def po_form():
    """PO Sheet ফর্ম পেজ"""
    po_form_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>PO Sheet Generator</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
            .card {
                border: none;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                margin-top: 30px;
            }
            . card-header {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                color: white;
                border-radius: 15px 15px 0 0 !important;
                padding: 20px;
            }
            .btn-generate {
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                border: none;
                padding: 12px 30px;
                font-weight: bold;
            }
            .btn-generate:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(17, 153, 142, 0.4);
            }
            .upload-area {
                border: 2px dashed #11998e;
                border-radius: 10px;
                padding: 40px;
                text-align: center;
                background: #f8f9fa;
                margin-bottom: 20px;
            }
            . upload-icon {
                font-size: 3rem;
                color: #11998e;
                margin-bottom: 15px;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <span class="navbar-text text-white">
                    <i class="fas fa-user"></i> {{ session.get('username') }}
                </span>
            </div>
        </nav>

        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h4 class="mb-0"><i class="fas fa-file-invoice"></i> PO Sheet Generator</h4>
                        </div>
                        <div class="card-body p-4">
                            {% with messages = get_flashed_messages(with_categories=true) %}
                                {% if messages %}
                                    {% for category, message in messages %}
                                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                            {{ message }}
                                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                        </div>
                                    {% endfor %}
                                {% endif %}
                            {% endwith %}

                            <form action="{{ url_for('preview_po_sheet') }}" method="POST" enctype="multipart/form-data">
                                <div class="upload-area">
                                    <div class="upload-icon">
                                        <i class="fas fa-cloud-upload-alt"></i>
                                    </div>
                                    <h5>Upload PO File</h5>
                                    <p class="text-muted">Drag and drop or click to browse</p>
                                    <input type="file" name="pofile" class="form-control" accept=". xlsx,.xls" required>
                                </div>

                                <div class="mb-4">
                                    <label class="form-label">
                                        <i class="fas fa-image"></i> Company Logo (Optional)
                                    </label>
                                    <input type="file" name="logo" class="form-control" accept="image/*">
                                    <small class="text-muted">PNG, JPG, or JPEG format</small>
                                </div>

                                <div class="d-grid">
                                    <button type="submit" class="btn btn-primary btn-generate">
                                        <i class="fas fa-eye"></i> Preview PO Sheet
                                    </button>
                                </div>
                            </form>

                            <div class="alert alert-info mt-4">
                                <i class="fas fa-info-circle"></i> 
                                <strong>Supported Format:</strong> Excel files (.xlsx, .xls) with columns like PO Number, Item, Quantity, Unit Price, Total.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    return render_template_string(po_form_html)

@app.route('/preview-po-sheet', methods=['POST'])
@login_required
def preview_po_sheet():
    """PO Sheet প্রিভিউ পেজ"""
    if 'pofile' not in request. files:
        flash('No file uploaded! ', 'danger')
        return redirect(url_for('po_form'))
    
    po_file = request.files['pofile']
    
    if not po_file or not po_file.filename:
        flash('Please select a file! ', 'danger')
        return redirect(url_for('po_form'))
    
    # ফাইল সেভ করুন
    filename = 'po_' + get_bd_time().strftime('%Y%m%d_%H%M%S') + '_' + po_file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    po_file.save(file_path)
    
    # লোগো প্রসেস করুন
    logo_path = None
    if 'logo' in request.files:
        logo = request.files['logo']
        if logo and logo.filename:
            logo_filename = 'logo_' + logo.filename
            logo_path = os.path.join(app. config['UPLOAD_FOLDER'], logo_filename)
            logo. save(logo_path)
    
    # ফাইল প্রসেস করুন
    data, columns = process_po_file(file_path)
    
    if not data:
        flash('Error processing file!  Please check the format. ', 'danger')
        return redirect(url_for('po_form'))
    
    # সেশনে ডেটা সেভ করুন
    session['po_data'] = data
    session['po_columns'] = columns
    session['po_logo'] = logo_path
    session['po_file_path'] = file_path
    
    preview_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Preview PO Sheet</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
            .preview-card {
                background: white;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                padding: 30px;
                margin-top: 20px;
            }
            .table-responsive {
                max-height: 500px;
                overflow: auto;
            }
            . btn-download {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                padding: 12px 30px;
                font-weight: bold;
                color: white;
            }
            .table {
                font-size: 0.9rem;
            }
            .table thead th {
                position: sticky;
                top: 0;
                background: #2E75B6;
                color: white;
                z-index: 10;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('po_form') }}">
                    <i class="fas fa-arrow-left"></i> Back
                </a>
                <span class="navbar-text text-white">
                    Preview Mode
                </span>
            </div>
        </nav>

        <div class="container-fluid px-4">
            <div class="preview-card">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h3><i class="fas fa-file-invoice"></i> PO Sheet Preview</h3>
                    <form action="{{ url_for('download_po_sheet') }}" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-download">
                            <i class="fas fa-download"></i> Download Excel
                        </button>
                    </form>
                </div>

                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 
                    Total Items: <strong>{{ data|length }}</strong> | 
                    Columns: <strong>{{ columns|length }}</strong> |
                    Generated: <strong>{{ current_time }}</strong>
                </div>

                <div class="table-responsive">
                    <table class="table table-striped table-hover table-bordered">
                        <thead>
                            <tr>
                                {% for col in columns %}
                                <th>{{ col }}</th>
                                {% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in data %}
                            <tr>
                                {% for col in columns %}
                                <td>{{ item.get(col, '') }}</td>
                                {% endfor %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(preview_html, 
                                 data=data, 
                                 columns=columns,
                                 current_time=get_bd_time(). strftime('%d-%m-%Y %H:%M'))

@app.route('/download-po-sheet', methods=['POST'])
@login_required
def download_po_sheet():
    """PO Sheet ডাউনলোড করুন"""
    data = session.get('po_data', [])
    columns = session.get('po_columns', [])
    logo_path = session.get('po_logo')
    file_path = session. get('po_file_path')
    
    if not data:
        flash('No data to download!', 'danger')
        return redirect(url_for('po_form'))
    
    # Excel তৈরি করুন
    wb = create_po_sheet_excel(data, columns, logo_path)
    
    # Memory buffer এ সেভ করুন
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # আপলোড করা ফাইল ডিলিট করুন
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if logo_path and os.path. exists(logo_path):
            os.remove(logo_path)
    except:
        pass
    
    # সেশন ক্লিয়ার করুন
    session.pop('po_data', None)
    session.pop('po_columns', None)
    session.pop('po_logo', None)
    session.pop('po_file_path', None)
    
    filename = f"PO_Sheet_{get_bd_date_str()}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument. spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
    # ==============================================================================
# Store User Management (Admin Only)
# ==============================================================================

@app.route('/store-user-management', methods=['GET', 'POST'])
@admin_required
def store_user_management():
    """স্টোর ইউজার ম্যানেজমেন্ট (Admin Only)"""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = request.form.get('role', 'staff')
            
            if not username or not password:
                flash('Username and password required!', 'danger')
                return redirect(url_for('store_user_management'))
            
            # চেক করুন ইউজার আছে কিনা
            if store_users_col. find_one({'username': username}):
                flash('Username already exists!', 'danger')
                return redirect(url_for('store_user_management'))
            
            store_users_col.insert_one({
                'username': username,
                'password': password,
                'role': role,
                'status': 'active',
                'created_at': get_bd_time(),
                'created_by': session. get('username')
            })
            flash(f'Store user {username} added successfully!', 'success')
            return redirect(url_for('store_user_management'))
        
        elif action == 'toggle_status':
            username = request.form.get('username')
            user = store_users_col.find_one({'username': username})
            if user:
                new_status = 'inactive' if user. get('status') == 'active' else 'active'
                store_users_col.update_one(
                    {'username': username},
                    {'$set': {'status': new_status}}
                )
                flash(f'User {username} status changed to {new_status}!', 'success')
            return redirect(url_for('store_user_management'))
        
        elif action == 'delete':
            username = request.form.get('username')
            store_users_col.delete_one({'username': username})
            flash(f'User {username} deleted! ', 'success')
            return redirect(url_for('store_user_management'))
    
    # সব স্টোর ইউজার লিস্ট
    store_users = list(store_users_col.find())
    
    store_user_mgmt_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Store User Management</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card { border: none; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
            </div>
        </nav>

        <div class="container mt-4">
            <h2 class="mb-4"><i class="fas fa-user-tie"></i> Store User Management</h2>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Add User Form -->
            <div class="card mb-4">
                <div class="card-body">
                    <h5 class="card-title">Add New Store User</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="add">
                        <div class="row">
                            <div class="col-md-3">
                                <input type="text" name="username" class="form-control" placeholder="Username" required>
                            </div>
                            <div class="col-md-3">
                                <input type="text" name="password" class="form-control" placeholder="Password" required>
                            </div>
                            <div class="col-md-3">
                                <select name="role" class="form-select">
                                    <option value="staff">Staff</option>
                                    <option value="manager">Manager</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <button type="submit" class="btn btn-primary w-100">Add User</button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Users List -->
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">All Store Users</h5>
                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Username</th>
                                    <th>Role</th>
                                    <th>Status</th>
                                    <th>Created At</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for user in store_users %}
                                <tr>
                                    <td>{{ user. username }}</td>
                                    <td>
                                        {% if user.role == 'manager' %}
                                            <span class="badge bg-warning">Manager</span>
                                        {% else %}
                                            <span class="badge bg-info">Staff</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        {% if user.status == 'active' %}
                                            <span class="badge bg-success">Active</span>
                                        {% else %}
                                            <span class="badge bg-danger">Inactive</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ user.created_at.strftime('%d-%m-%Y %H:%M') if user.created_at else 'N/A' }}</td>
                                    <td>
                                        <form method="POST" style="display:inline;">
                                            <input type="hidden" name="action" value="toggle_status">
                                            <input type="hidden" name="username" value="{{ user.username }}">
                                            <button type="submit" class="btn btn-sm btn-warning">Toggle Status</button>
                                        </form>
                                        <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this user?');">
                                            <input type="hidden" name="action" value="delete">
                                            <input type="hidden" name="username" value="{{ user.username }}">
                                            <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(store_user_mgmt_html, store_users=store_users)

# ==============================================================================
# Store Panel (১ম কোডের ডিজাইন অনুযায়ী)
# ==============================================================================

@app.route('/store')
@store_login_required
def store_panel():
    """স্টোর প্যানেল - ১ম কোডের ডিজাইন"""
    username = session.get('store_user')
    role = session.get('store_role', 'staff')
    
    # Statistics
    total_products = store_products_col.count_documents({})
    total_customers = store_customers_col.count_documents({})
    total_invoices = store_invoices_col.count_documents({})
    total_estimates = store_estimates_col.count_documents({})
    
    # Recent invoices
    recent_invoices = list(store_invoices_col. find(). sort('created_at', -1).limit(5))
    
    store_panel_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Store Management Panel</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body {
                background: #f4f6f9;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li {
                padding: 0;
            }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .sidebar-menu a.active {
                background: rgba(255,255,255,0.2);
                border-left: 4px solid #3498db;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .top-bar {
                background: white;
                padding: 15px 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .stat-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                transition: transform 0.3s;
            }
            .stat-card:hover {
                transform: translateY(-5px);
            }
            .stat-icon {
                width: 60px;
                height: 60px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.5rem;
                color: white;
                float: left;
                margin-right: 15px;
            }
            .stat-icon-blue { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .stat-icon-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
            .stat-icon-orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
            .stat-icon-purple { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
            
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
                color: #2c3e50;
            }
            .stat-label {
                color: #7f8c8d;
                font-size: 0.9rem;
            }
            .recent-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-top: 20px;
            }
            .quick-action-btn {
                padding: 15px;
                border-radius: 10px;
                border: none;
                font-weight: bold;
                width: 100%;
                margin-bottom: 10px;
                transition: all 0.3s;
            }
            .quick-action-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}" class="active"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <!-- Top Bar -->
            <div class="top-bar">
                <div>
                    <h4 class="mb-0">Welcome, {{ username }}!</h4>
                    <small class="text-muted">Store Management System</small>
                </div>
                <div>
                    <span class="badge bg-primary">{{ role }}</span>
                    <span class="text-muted ms-2">{{ current_date }}</span>
                </div>
            </div>

            <!-- Flash Messages -->
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Statistics Cards -->
            <div class="row">
                <div class="col-md-3 mb-4">
                    <div class="stat-card">
                        <div class="stat-icon stat-icon-blue">
                            <i class="fas fa-box"></i>
                        </div>
                        <div>
                            <div class="stat-number">{{ total_products }}</div>
                            <div class="stat-label">Total Products</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="stat-card">
                        <div class="stat-icon stat-icon-green">
                            <i class="fas fa-users"></i>
                        </div>
                        <div>
                            <div class="stat-number">{{ total_customers }}</div>
                            <div class="stat-label">Customers</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="stat-card">
                        <div class="stat-icon stat-icon-orange">
                            <i class="fas fa-file-invoice"></i>
                        </div>
                        <div>
                            <div class="stat-number">{{ total_invoices }}</div>
                            <div class="stat-label">Invoices</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="stat-card">
                        <div class="stat-icon stat-icon-purple">
                            <i class="fas fa-file-alt"></i>
                        </div>
                        <div>
                            <div class="stat-number">{{ total_estimates }}</div>
                            <div class="stat-label">Estimates</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Actions and Recent Invoices -->
            <div class="row">
                <div class="col-md-4">
                    <div class="recent-card">
                        <h5 class="mb-3"><i class="fas fa-bolt"></i> Quick Actions</h5>
                        <button class="quick-action-btn btn btn-primary" onclick="location.href='{{ url_for('add_invoice') }}'">
                            <i class="fas fa-plus"></i> New Invoice
                        </button>
                        <button class="quick-action-btn btn btn-success" onclick="location. href='{{ url_for('add_estimate') }}'">
                            <i class="fas fa-plus"></i> New Estimate
                        </button>
                        <button class="quick-action-btn btn btn-info" onclick="location.href='{{ url_for('add_customer') }}'">
                            <i class="fas fa-user-plus"></i> Add Customer
                        </button>
                        <button class="quick-action-btn btn btn-warning" onclick="location.href='{{ url_for('add_product') }}'">
                            <i class="fas fa-box"></i> Add Product
                        </button>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="recent-card">
                        <h5 class="mb-3"><i class="fas fa-clock"></i> Recent Invoices</h5>
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Invoice #</th>
                                        <th>Customer</th>
                                        <th>Amount</th>
                                        <th>Date</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% if recent_invoices %}
                                        {% for invoice in recent_invoices %}
                                        <tr>
                                            <td><strong>{{ invoice.invoice_number }}</strong></td>
                                            <td>{{ invoice.customer_name }}</td>
                                            <td>৳{{ invoice.total_amount }}</td>
                                            <td>{{ invoice.created_at. strftime('%d-%m-%Y') if invoice.created_at else 'N/A' }}</td>
                                            <td>
                                                <a href="{{ url_for('view_invoice', invoice_id=invoice._id) }}" class="btn btn-sm btn-primary">View</a>
                                            </td>
                                        </tr>
                                        {% endfor %}
                                    {% else %}
                                        <tr>
                                            <td colspan="5" class="text-center text-muted">No invoices yet</td>
                                        </tr>
                                    {% endif %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min. js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(store_panel_html,
                                 username=username,
                                 role=role,
                                 current_date=get_bd_date_str(),
                                 total_products=total_products,
                                 total_customers=total_customers,
                                 total_invoices=total_invoices,
                                 total_estimates=total_estimates,
                                 recent_invoices=recent_invoices)
    # ==============================================================================
# Store Products Management
# ==============================================================================

@app. route('/store/products')
@store_login_required
def store_products():
    """স্টোর প্রোডাক্ট লিস্ট"""
    products = list(store_products_col.find(). sort('created_at', -1))
    
    products_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Products - Store Panel</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .content-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .product-card {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 15px;
                transition: all 0.3s;
            }
            .product-card:hover {
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}" class="active"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3><i class="fas fa-box"></i> Products Management</h3>
                <a href="{{ url_for('add_product') }}" class="btn btn-primary">
                    <i class="fas fa-plus"></i> Add New Product
                </a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <div class="content-card">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Product Name</th>
                                <th>Category</th>
                                <th>Price</th>
                                <th>Stock</th>
                                <th>Unit</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if products %}
                                {% for product in products %}
                                <tr>
                                    <td><strong>{{ product.name }}</strong></td>
                                    <td><span class="badge bg-info">{{ product.category }}</span></td>
                                    <td>৳{{ product.price }}</td>
                                    <td>
                                        {% if product.stock > 10 %}
                                            <span class="badge bg-success">{{ product.stock }}</span>
                                        {% elif product.stock > 0 %}
                                            <span class="badge bg-warning">{{ product.stock }}</span>
                                        {% else %}
                                            <span class="badge bg-danger">Out of Stock</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ product.unit }}</td>
                                    <td>
                                        <a href="{{ url_for('edit_product', product_id=product._id) }}" class="btn btn-sm btn-warning">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                        <form method="POST" action="{{ url_for('delete_product', product_id=product._id) }}" 
                                              style="display:inline;" onsubmit="return confirm('Delete this product?');">
                                            <button type="submit" class="btn btn-sm btn-danger">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="6" class="text-center text-muted">No products found.  Add your first product!</td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(products_html, products=products)

@app.route('/store/products/add', methods=['GET', 'POST'])
@store_login_required
def add_product():
    """নতুন প্রোডাক্ট যোগ করুন"""
    if request.method == 'POST':
        name = request.form. get('name', '').strip()
        category = request.form.get('category', '').strip()
        price = request.form.get('price', '0')
        stock = request.form. get('stock', '0')
        unit = request. form.get('unit', 'pcs')
        description = request.form.get('description', '').strip()
        
        if not name or not category:
            flash('Product name and category are required! ', 'danger')
            return redirect(url_for('add_product'))
        
        try:
            price = float(price)
            stock = int(stock)
        except:
            flash('Invalid price or stock value!', 'danger')
            return redirect(url_for('add_product'))
        
        store_products_col.insert_one({
            'name': name,
            'category': category,
            'price': price,
            'stock': stock,
            'unit': unit,
            'description': description,
            'created_at': get_bd_time(),
            'created_by': session.get('store_user')
        })
        
        flash(f'Product "{name}" added successfully!', 'success')
        return redirect(url_for('store_products'))
    
    add_product_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Add Product</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            . sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}" class="active"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('store_products') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Products
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-plus-circle"></i> Add New Product</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Product Name *</label>
                        <input type="text" name="name" class="form-control" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Category *</label>
                        <input type="text" name="category" class="form-control" 
                               placeholder="e.g., Electronics, Clothing, Food" required>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Price (৳) *</label>
                            <input type="number" name="price" class="form-control" step="0.01" min="0" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Stock Quantity *</label>
                            <input type="number" name="stock" class="form-control" min="0" required>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Unit</label>
                        <select name="unit" class="form-select">
                            <option value="pcs">Pieces (pcs)</option>
                            <option value="kg">Kilogram (kg)</option>
                            <option value="ltr">Liter (ltr)</option>
                            <option value="box">Box</option>
                            <option value="pack">Pack</option>
                            <option value="meter">Meter</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Description</label>
                        <textarea name="description" class="form-control" rows="3"></textarea>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary btn-lg">
                            <i class="fas fa-save"></i> Add Product
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(add_product_html)

@app.route('/store/products/edit/<product_id>', methods=['GET', 'POST'])
@store_login_required
def edit_product(product_id):
    """প্রোডাক্ট এডিট করুন"""
    from bson import ObjectId
    
    try:
        product = store_products_col.find_one({'_id': ObjectId(product_id)})
    except:
        flash('Invalid product ID!', 'danger')
        return redirect(url_for('store_products'))
    
    if not product:
        flash('Product not found!', 'danger')
        return redirect(url_for('store_products'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        price = request.form.get('price', '0')
        stock = request.form. get('stock', '0')
        unit = request.form.get('unit', 'pcs')
        description = request.form. get('description', '').strip()
        
        if not name or not category:
            flash('Product name and category are required!', 'danger')
            return redirect(url_for('edit_product', product_id=product_id))
        
        try:
            price = float(price)
            stock = int(stock)
        except:
            flash('Invalid price or stock value!', 'danger')
            return redirect(url_for('edit_product', product_id=product_id))
        
        store_products_col. update_one(
            {'_id': ObjectId(product_id)},
            {'$set': {
                'name': name,
                'category': category,
                'price': price,
                'stock': stock,
                'unit': unit,
                'description': description,
                'updated_at': get_bd_time(),
                'updated_by': session.get('store_user')
            }}
        )
        
        flash(f'Product "{name}" updated successfully!', 'success')
        return redirect(url_for('store_products'))
    
    edit_product_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Product</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            . sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}" class="active"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('store_products') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Products
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-edit"></i> Edit Product</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Product Name *</label>
                        <input type="text" name="name" class="form-control" value="{{ product.name }}" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Category *</label>
                        <input type="text" name="category" class="form-control" value="{{ product.category }}" required>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Price (৳) *</label>
                            <input type="number" name="price" class="form-control" step="0.01" min="0" 
                                   value="{{ product. price }}" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Stock Quantity *</label>
                            <input type="number" name="stock" class="form-control" min="0" 
                                   value="{{ product.stock }}" required>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Unit</label>
                        <select name="unit" class="form-select">
                            <option value="pcs" {% if product.unit == 'pcs' %}selected{% endif %}>Pieces (pcs)</option>
                            <option value="kg" {% if product.unit == 'kg' %}selected{% endif %}>Kilogram (kg)</option>
                            <option value="ltr" {% if product.unit == 'ltr' %}selected{% endif %}>Liter (ltr)</option>
                            <option value="box" {% if product. unit == 'box' %}selected{% endif %}>Box</option>
                            <option value="pack" {% if product.unit == 'pack' %}selected{% endif %}>Pack</option>
                            <option value="meter" {% if product.unit == 'meter' %}selected{% endif %}>Meter</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Description</label>
                        <textarea name="description" class="form-control" rows="3">{{ product.description }}</textarea>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-warning btn-lg">
                            <i class="fas fa-save"></i> Update Product
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(edit_product_html, product=product)

@app. route('/store/products/delete/<product_id>', methods=['POST'])
@store_login_required
def delete_product(product_id):
    """প্রোডাক্ট ডিলিট করুন"""
    from bson import ObjectId
    
    try:
        store_products_col.delete_one({'_id': ObjectId(product_id)})
        flash('Product deleted successfully!', 'success')
    except:
        flash('Error deleting product!', 'danger')
    
    return redirect(url_for('store_products'))
    # ==============================================================================
# Store Customers Management
# ==============================================================================

@app.route('/store/customers')
@store_login_required
def store_customers():
    """স্টোর কাস্টমার লিস্ট"""
    customers = list(store_customers_col.find(). sort('created_at', -1))
    
    customers_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Customers - Store Panel</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            . sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            . sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .content-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .search-box {
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}" class="active"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3><i class="fas fa-users"></i> Customers Management</h3>
                <a href="{{ url_for('add_customer') }}" class="btn btn-primary">
                    <i class="fas fa-user-plus"></i> Add New Customer
                </a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <div class="content-card">
                <!-- Search Box -->
                <div class="search-box">
                    <input type="text" id="searchInput" class="form-control" placeholder="Search customers by name, phone, email...">
                </div>

                <div class="table-responsive">
                    <table class="table table-hover" id="customersTable">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                <th>Phone</th>
                                <th>Email</th>
                                <th>Address</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if customers %}
                                {% for customer in customers %}
                                <tr>
                                    <td><strong>{{ customer.name }}</strong></td>
                                    <td>{{ customer.phone }}</td>
                                    <td>{{ customer.email if customer.email else 'N/A' }}</td>
                                    <td>{{ customer.address[:30] + '...' if customer.address and customer.address|length > 30 else customer.address }}</td>
                                    <td>{{ customer.created_at.strftime('%d-%m-%Y') if customer.created_at else 'N/A' }}</td>
                                    <td>
                                        <a href="{{ url_for('edit_customer', customer_id=customer._id) }}" class="btn btn-sm btn-warning">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                        <form method="POST" action="{{ url_for('delete_customer', customer_id=customer._id) }}" 
                                              style="display:inline;" onsubmit="return confirm('Delete this customer?');">
                                            <button type="submit" class="btn btn-sm btn-danger">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="6" class="text-center text-muted">No customers found.  Add your first customer!</td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
        <script>
            // Search functionality
            document.getElementById('searchInput').addEventListener('keyup', function() {
                const searchValue = this.value.toLowerCase();
                const table = document.getElementById('customersTable');
                const rows = table. getElementsByTagName('tr');
                
                for (let i = 1; i < rows.length; i++) {
                    const row = rows[i];
                    const text = row.textContent. toLowerCase();
                    
                    if (text.includes(searchValue)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                }
            });
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(customers_html, customers=customers)

@app. route('/store/customers/add', methods=['GET', 'POST'])
@store_login_required
def add_customer():
    """নতুন কাস্টমার যোগ করুন"""
    if request.method == 'POST':
        name = request.form. get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        company = request.form.get('company', '').strip()
        
        if not name or not phone:
            flash('Customer name and phone are required!', 'danger')
            return redirect(url_for('add_customer'))
        
        # চেক করুন ফোন নাম্বার আগে থেকে আছে কিনা
        existing = store_customers_col.find_one({'phone': phone})
        if existing:
            flash('Customer with this phone number already exists!', 'warning')
            return redirect(url_for('add_customer'))
        
        store_customers_col.insert_one({
            'name': name,
            'phone': phone,
            'email': email,
            'address': address,
            'company': company,
            'created_at': get_bd_time(),
            'created_by': session.get('store_user')
        })
        
        flash(f'Customer "{name}" added successfully!', 'success')
        return redirect(url_for('store_customers'))
    
    add_customer_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Add Customer</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            . sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}" class="active"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('store_customers') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Customers
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-user-plus"></i> Add New Customer</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Customer Name *</label>
                        <input type="text" name="name" class="form-control" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Phone Number *</label>
                        <input type="tel" name="phone" class="form-control" placeholder="01XXXXXXXXX" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Email (Optional)</label>
                        <input type="email" name="email" class="form-control" placeholder="customer@example.com">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Company (Optional)</label>
                        <input type="text" name="company" class="form-control">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Address</label>
                        <textarea name="address" class="form-control" rows="3"></textarea>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary btn-lg">
                            <i class="fas fa-save"></i> Add Customer
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(add_customer_html)

@app.route('/store/customers/edit/<customer_id>', methods=['GET', 'POST'])
@store_login_required
def edit_customer(customer_id):
    """কাস্টমার এডিট করুন"""
    from bson import ObjectId
    
    try:
        customer = store_customers_col.find_one({'_id': ObjectId(customer_id)})
    except:
        flash('Invalid customer ID!', 'danger')
        return redirect(url_for('store_customers'))
    
    if not customer:
        flash('Customer not found!', 'danger')
        return redirect(url_for('store_customers'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        company = request.form.get('company', '').strip()
        
        if not name or not phone:
            flash('Customer name and phone are required!', 'danger')
            return redirect(url_for('edit_customer', customer_id=customer_id))
        
        store_customers_col.update_one(
            {'_id': ObjectId(customer_id)},
            {'$set': {
                'name': name,
                'phone': phone,
                'email': email,
                'address': address,
                'company': company,
                'updated_at': get_bd_time(),
                'updated_by': session.get('store_user')
            }}
        )
        
        flash(f'Customer "{name}" updated successfully!', 'success')
        return redirect(url_for('store_customers'))
    
    edit_customer_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Customer</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            . sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0. 2);
            }
            . sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                max-width: 600px;
                margin: 0 auto;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}" class="active"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('store_customers') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Customers
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-edit"></i> Edit Customer</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Customer Name *</label>
                        <input type="text" name="name" class="form-control" value="{{ customer.name }}" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Phone Number *</label>
                        <input type="tel" name="phone" class="form-control" value="{{ customer.phone }}" required>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Email (Optional)</label>
                        <input type="email" name="email" class="form-control" value="{{ customer.email if customer.email else '' }}">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Company (Optional)</label>
                        <input type="text" name="company" class="form-control" value="{{ customer.company if customer.company else '' }}">
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Address</label>
                        <textarea name="address" class="form-control" rows="3">{{ customer.address if customer.address else '' }}</textarea>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-warning btn-lg">
                            <i class="fas fa-save"></i> Update Customer
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(edit_customer_html, customer=customer)

@app. route('/store/customers/delete/<customer_id>', methods=['POST'])
@store_login_required
def delete_customer(customer_id):
    """কাস্টমার ডিলিট করুন"""
    from bson import ObjectId
    
    try:
        store_customers_col.delete_one({'_id': ObjectId(customer_id)})
        flash('Customer deleted successfully!', 'success')
    except:
        flash('Error deleting customer!', 'danger')
    
    return redirect(url_for('store_customers'))
    # ==============================================================================
# Store Invoices Management
# ==============================================================================

@app. route('/store/invoices')
@store_login_required
def store_invoices():
    """স্টোর ইনভয়েস লিস্ট"""
    invoices = list(store_invoices_col. find(). sort('created_at', -1))
    
    invoices_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Invoices - Store Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            . sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0. 2);
            }
            . sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .content-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .invoice-badge {
                padding: 5px 10px;
                border-radius: 5px;
                font-size: 0.85rem;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}" class="active"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3><i class="fas fa-file-invoice"></i> Invoices Management</h3>
                <a href="{{ url_for('add_invoice') }}" class="btn btn-primary">
                    <i class="fas fa-plus"></i> Create New Invoice
                </a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <div class="content-card">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Invoice #</th>
                                <th>Customer</th>
                                <th>Date</th>
                                <th>Total Amount</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if invoices %}
                                {% for invoice in invoices %}
                                <tr>
                                    <td><strong>{{ invoice.invoice_number }}</strong></td>
                                    <td>{{ invoice.customer_name }}</td>
                                    <td>{{ invoice.invoice_date if invoice.invoice_date else 'N/A' }}</td>
                                    <td><strong>৳{{ "%.2f"|format(invoice.total_amount) }}</strong></td>
                                    <td>
                                        {% if invoice.status == 'paid' %}
                                            <span class="badge bg-success">Paid</span>
                                        {% elif invoice.status == 'partial' %}
                                            <span class="badge bg-warning">Partial</span>
                                        {% else %}
                                            <span class="badge bg-danger">Unpaid</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        <a href="{{ url_for('view_invoice', invoice_id=invoice._id) }}" class="btn btn-sm btn-info" title="View">
                                            <i class="fas fa-eye"></i>
                                        </a>
                                        <a href="{{ url_for('print_invoice', invoice_id=invoice._id) }}" class="btn btn-sm btn-success" title="Print" target="_blank">
                                            <i class="fas fa-print"></i>
                                        </a>
                                        <a href="{{ url_for('edit_invoice', invoice_id=invoice._id) }}" class="btn btn-sm btn-warning" title="Edit">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                        <form method="POST" action="{{ url_for('delete_invoice', invoice_id=invoice._id) }}" 
                                              style="display:inline;" onsubmit="return confirm('Delete this invoice?');">
                                            <button type="submit" class="btn btn-sm btn-danger" title="Delete">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="6" class="text-center text-muted">No invoices found.  Create your first invoice!</td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(invoices_html, invoices=invoices)

@app.route('/store/invoices/add', methods=['GET', 'POST'])
@store_login_required
def add_invoice():
    """নতুন ইনভয়েস তৈরি করুন"""
    if request.method == 'POST':
        try:
            # Basic Info
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            customer_address = request.form.get('customer_address', '').strip()
            invoice_date = request.form.get('invoice_date', get_bd_date_str())
            
            # Items (JSON format from JavaScript)
            items_json = request.form.get('items_json', '[]')
            items = json.loads(items_json)
            
            if not customer_name or not items:
                flash('Customer name and at least one item required!', 'danger')
                return redirect(url_for('add_invoice'))
            
            # Calculate totals
            subtotal = sum(float(item. get('total', 0)) for item in items)
            discount = float(request.form.get('discount', 0))
            tax = float(request.form. get('tax', 0))
            total_amount = subtotal - discount + tax
            
            # Generate invoice number
            last_invoice = store_invoices_col.find_one(sort=[('created_at', -1)])
            if last_invoice and 'invoice_number' in last_invoice:
                last_num = int(last_invoice['invoice_number'].split('-')[-1])
                invoice_number = f"INV-{last_num + 1:05d}"
            else:
                invoice_number = "INV-00001"
            
            # Insert invoice
            invoice_data = {
                'invoice_number': invoice_number,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'customer_address': customer_address,
                'invoice_date': invoice_date,
                'items': items,
                'subtotal': subtotal,
                'discount': discount,
                'tax': tax,
                'total_amount': total_amount,
                'status': 'unpaid',
                'created_at': get_bd_time(),
                'created_by': session.get('store_user')
            }
            
            result = store_invoices_col. insert_one(invoice_data)
            
            # Update product stock
            for item in items:
                product_name = item.get('product_name')
                quantity = int(item.get('quantity', 0))
                
                product = store_products_col.find_one({'name': product_name})
                if product:
                    new_stock = product. get('stock', 0) - quantity
                    store_products_col.update_one(
                        {'name': product_name},
                        {'$set': {'stock': new_stock}}
                    )
            
            flash(f'Invoice {invoice_number} created successfully!', 'success')
            return redirect(url_for('view_invoice', invoice_id=result.inserted_id))
            
        except Exception as e:
            flash(f'Error creating invoice: {str(e)}', 'danger')
            return redirect(url_for('add_invoice'))
    
    # GET request - show form
    customers = list(store_customers_col.find())
    products = list(store_products_col.find())
    
    add_invoice_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Create Invoice</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .item-row {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                border: 1px solid #dee2e6;
            }
            .summary-box {
                background: #e9ecef;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}" class="active"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('store_invoices') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Invoices
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-file-invoice"></i> Create New Invoice</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST" id="invoiceForm">
                    <!-- Customer Info -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <label class="form-label">Customer Name *</label>
                            <input type="text" name="customer_name" id="customerName" class="form-control" list="customerList" required>
                            <datalist id="customerList">
                                {% for customer in customers %}
                                <option value="{{ customer.name }}" data-phone="{{ customer.phone }}" data-address="{{ customer.address }}">
                                {% endfor %}
                            </datalist>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Phone</label>
                            <input type="text" name="customer_phone" id="customerPhone" class="form-control">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Invoice Date</label>
                            <input type="date" name="invoice_date" class="form-control" value="{{ current_date }}">
                        </div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label">Address</label>
                        <input type="text" name="customer_address" id="customerAddress" class="form-control">
                    </div>

                    <!-- Items Section -->
                    <h5 class="mb-3">Invoice Items</h5>
                    <div id="itemsContainer"></div>
                    
                    <button type="button" class="btn btn-success mb-3" onclick="addItem()">
                        <i class="fas fa-plus"></i> Add Item
                    </button>

                    <!-- Summary -->
                    <div class="summary-box">
                        <div class="row">
                            <div class="col-md-8">
                                <div class="mb-2">
                                    <label class="form-label">Discount (৳)</label>
                                    <input type="number" name="discount" id="discount" class="form-control" value="0" step="0.01" min="0" onchange="calculateTotal()">
                                </div>
                                <div>
                                    <label class="form-label">Tax (৳)</label>
                                    <input type="number" name="tax" id="tax" class="form-control" value="0" step="0.01" min="0" onchange="calculateTotal()">
                                </div>
                            </div>
                            <div class="col-md-4">
                                <h5>Subtotal: <span id="subtotalDisplay">৳0.00</span></h5>
                                <h5>Discount: <span id="discountDisplay">৳0.00</span></h5>
                                <h5>Tax: <span id="taxDisplay">৳0.00</span></h5>
                                <h4 class="text-primary">Total: <span id="totalDisplay">৳0.00</span></h4>
                            </div>
                        </div>
                    </div>

                    <input type="hidden" name="items_json" id="itemsJson">

                    <div class="d-grid mt-4">
                        <button type="submit" class="btn btn-primary btn-lg">
                            <i class="fas fa-save"></i> Create Invoice
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            const products = {{ products | tojson }};
            let itemCounter = 0;

            // Auto-fill customer info
            document.getElementById('customerName').addEventListener('input', function() {
                const customerName = this. value;
                const customers = {{ customers | tojson }};
                const customer = customers.find(c => c.name === customerName);
                
                if (customer) {
                    document.getElementById('customerPhone').value = customer.phone || '';
                    document.getElementById('customerAddress').value = customer.address || '';
                }
            });

            function addItem() {
                itemCounter++;
                const container = document.getElementById('itemsContainer');
                
                const itemDiv = document.createElement('div');
                itemDiv.className = 'item-row';
                itemDiv.id = 'item-' + itemCounter;
                
                itemDiv.innerHTML = `
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">Product</label>
                            <input type="text" class="form-control product-name" list="productList-${itemCounter}" 
                                   onchange="updatePrice(${itemCounter})" required>
                            <datalist id="productList-${itemCounter}">
                                ${products.map(p => `<option value="${p. name}" data-price="${p.price}" data-stock="${p.stock}">`).join('')}
                            </datalist>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Price (৳)</label>
                            <input type="number" class="form-control item-price" step="0.01" min="0" 
                                   onchange="calculateItemTotal(${itemCounter})" required>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Quantity</label>
                            <input type="number" class="form-control item-quantity" min="1" value="1" 
                                   onchange="calculateItemTotal(${itemCounter})" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Total (৳)</label>
                            <input type="number" class="form-control item-total" readonly>
                        </div>
                        <div class="col-md-1">
                            <label class="form-label">&nbsp;</label>
                            <button type="button" class="btn btn-danger w-100" onclick="removeItem(${itemCounter})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
                
                container.appendChild(itemDiv);
            }

            function updatePrice(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                const productName = itemDiv.querySelector('.product-name').value;
                const product = products.find(p => p.name === productName);
                
                if (product) {
                    itemDiv.querySelector('.item-price'). value = product.price;
                    calculateItemTotal(itemId);
                }
            }

            function calculateItemTotal(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                const price = parseFloat(itemDiv.querySelector('.item-price').value) || 0;
                const quantity = parseInt(itemDiv.querySelector('. item-quantity').value) || 0;
                const total = price * quantity;
                
                itemDiv.querySelector('.item-total'). value = total.toFixed(2);
                calculateTotal();
            }

            function removeItem(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                itemDiv.remove();
                calculateTotal();
            }

            function calculateTotal() {
                let subtotal = 0;
                
                document.querySelectorAll('. item-total').forEach(input => {
                    subtotal += parseFloat(input.value) || 0;
                });
                
                const discount = parseFloat(document.getElementById('discount').value) || 0;
                const tax = parseFloat(document.getElementById('tax').value) || 0;
                const total = subtotal - discount + tax;
                
                document.getElementById('subtotalDisplay').textContent = '৳' + subtotal.toFixed(2);
                document. getElementById('discountDisplay').textContent = '৳' + discount. toFixed(2);
                document.getElementById('taxDisplay').textContent = '৳' + tax. toFixed(2);
                document.getElementById('totalDisplay').textContent = '৳' + total. toFixed(2);
            }

            document.getElementById('invoiceForm').addEventListener('submit', function(e) {
                const items = [];
                
                document.querySelectorAll('.item-row').forEach(itemDiv => {
                    const productName = itemDiv.querySelector('.product-name').value;
                    const price = parseFloat(itemDiv.querySelector('.item-price').value) || 0;
                    const quantity = parseInt(itemDiv.querySelector('.item-quantity').value) || 0;
                    const total = parseFloat(itemDiv.querySelector('.item-total').value) || 0;
                    
                    if (productName && quantity > 0) {
                        items.push({
                            product_name: productName,
                            price: price,
                            quantity: quantity,
                            total: total
                        });
                    }
                });
                
                if (items.length === 0) {
                    e.preventDefault();
                    alert('Please add at least one item! ');
                    return false;
                }
                
                document.getElementById('itemsJson').value = JSON.stringify(items);
            });

            // Add first item by default
            addItem();
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(add_invoice_html, 
                                 customers=customers, 
                                 products=products,
                                 current_date=get_bd_time(). strftime('%Y-%m-%d'))
    # ==============================================================================
# View Invoice
# ==============================================================================

@app.route('/store/invoices/view/<invoice_id>')
@store_login_required
def view_invoice(invoice_id):
    """ইনভয়েস ভিউ করুন"""
    from bson import ObjectId
    
    try:
        invoice = store_invoices_col.find_one({'_id': ObjectId(invoice_id)})
    except:
        flash('Invalid invoice ID! ', 'danger')
        return redirect(url_for('store_invoices'))
    
    if not invoice:
        flash('Invoice not found!', 'danger')
        return redirect(url_for('store_invoices'))
    
    view_invoice_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>View Invoice - {{ invoice.invoice_number }}</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            . sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0. 3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .invoice-card {
                background: white;
                border-radius: 10px;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                max-width: 900px;
                margin: 0 auto;
            }
            .invoice-header {
                border-bottom: 3px solid #3498db;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .invoice-info-box {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .invoice-table {
                margin-top: 20px;
            }
            .total-section {
                background: #e9ecef;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}" class="active"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="d-flex justify-content-between mb-3">
                <a href="{{ url_for('store_invoices') }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Invoices
                </a>
                <div>
                    <a href="{{ url_for('print_invoice', invoice_id=invoice._id) }}" class="btn btn-success" target="_blank">
                        <i class="fas fa-print"></i> Print Invoice
                    </a>
                    <a href="{{ url_for('edit_invoice', invoice_id=invoice._id) }}" class="btn btn-warning">
                        <i class="fas fa-edit"></i> Edit Invoice
                    </a>
                </div>
            </div>

            <div class="invoice-card">
                <!-- Header -->
                <div class="invoice-header">
                    <div class="row">
                        <div class="col-md-6">
                            <h2 class="text-primary">INVOICE</h2>
                            <h5>{{ invoice.invoice_number }}</h5>
                        </div>
                        <div class="col-md-6 text-end">
                            <h4>Your Company Name</h4>
                            <p class="mb-0">123 Business Street</p>
                            <p class="mb-0">Dhaka, Bangladesh</p>
                            <p class="mb-0">Phone: +880 1234-567890</p>
                        </div>
                    </div>
                </div>

                <!-- Customer & Invoice Info -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="invoice-info-box">
                            <h6 class="text-muted">BILL TO:</h6>
                            <h5>{{ invoice.customer_name }}</h5>
                            <p class="mb-1"><i class="fas fa-phone"></i> {{ invoice.customer_phone }}</p>
                            {% if invoice.customer_address %}
                            <p class="mb-0"><i class="fas fa-map-marker-alt"></i> {{ invoice.customer_address }}</p>
                            {% endif %}
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="invoice-info-box">
                            <table class="table table-borderless mb-0">
                                <tr>
                                    <td><strong>Invoice Date:</strong></td>
                                    <td>{{ invoice.invoice_date }}</td>
                                </tr>
                                <tr>
                                    <td><strong>Status:</strong></td>
                                    <td>
                                        {% if invoice.status == 'paid' %}
                                            <span class="badge bg-success">Paid</span>
                                        {% elif invoice.status == 'partial' %}
                                            <span class="badge bg-warning">Partial</span>
                                        {% else %}
                                            <span class="badge bg-danger">Unpaid</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                <tr>
                                    <td><strong>Created By:</strong></td>
                                    <td>{{ invoice.created_by }}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Items Table -->
                <div class="invoice-table">
                    <table class="table table-bordered">
                        <thead class="table-light">
                            <tr>
                                <th>#</th>
                                <th>Product</th>
                                <th class="text-center">Quantity</th>
                                <th class="text-end">Unit Price</th>
                                <th class="text-end">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in invoice.items %}
                            <tr>
                                <td>{{ loop.index }}</td>
                                <td>{{ item.product_name }}</td>
                                <td class="text-center">{{ item. quantity }}</td>
                                <td class="text-end">৳{{ "%.2f"|format(item.price) }}</td>
                                <td class="text-end">৳{{ "%.2f"|format(item. total) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>

                <!-- Totals -->
                <div class="row">
                    <div class="col-md-6"></div>
                    <div class="col-md-6">
                        <div class="total-section">
                            <table class="table table-borderless mb-0">
                                <tr>
                                    <td><strong>Subtotal:</strong></td>
                                    <td class="text-end">৳{{ "%.2f"|format(invoice.subtotal) }}</td>
                                </tr>
                                {% if invoice.discount > 0 %}
                                <tr>
                                    <td><strong>Discount:</strong></td>
                                    <td class="text-end text-danger">- ৳{{ "%.2f"|format(invoice.discount) }}</td>
                                </tr>
                                {% endif %}
                                {% if invoice.tax > 0 %}
                                <tr>
                                    <td><strong>Tax:</strong></td>
                                    <td class="text-end">৳{{ "%.2f"|format(invoice.tax) }}</td>
                                </tr>
                                {% endif %}
                                <tr class="border-top">
                                    <td><h5 class="mb-0"><strong>Total Amount:</strong></h5></td>
                                    <td class="text-end"><h5 class="mb-0 text-primary"><strong>৳{{ "%.2f"|format(invoice.total_amount) }}</strong></h5></td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Footer -->
                <div class="text-center mt-4 pt-3 border-top">
                    <p class="text-muted mb-0">Thank you for your business!</p>
                    <small class="text-muted">This is a computer-generated invoice. </small>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(view_invoice_html, invoice=invoice)

# ==============================================================================
# Print Invoice (Professional Template)
# ==============================================================================

@app.route('/store/invoices/print/<invoice_id>')
@store_login_required
def print_invoice(invoice_id):
    """প্রফেশনাল প্রিন্ট টেমপ্লেট"""
    from bson import ObjectId
    
    try:
        invoice = store_invoices_col. find_one({'_id': ObjectId(invoice_id)})
    except:
        return "Invalid invoice ID", 400
    
    if not invoice:
        return "Invoice not found", 404
    
    print_invoice_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Print Invoice - {{ invoice.invoice_number }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            @media print {
                . no-print { display: none; }
                body { margin: 0; }
                @page { margin: 1cm; }
            }
            
            body {
                font-family: 'Arial', sans-serif;
                background: white;
            }
            
            .invoice-container {
                max-width: 800px;
                margin: 20px auto;
                padding: 40px;
                background: white;
                border: 2px solid #2c3e50;
            }
            
            .invoice-header {
                border-bottom: 4px solid #3498db;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            
            .company-logo {
                font-size: 2. 5rem;
                color: #3498db;
                font-weight: bold;
            }
            
            .invoice-title {
                font-size: 2rem;
                color: #2c3e50;
                font-weight: bold;
            }
            
            .info-box {
                background: #f8f9fa;
                padding: 15px;
                border-left: 4px solid #3498db;
                margin-bottom: 20px;
            }
            
            .invoice-table {
                margin: 30px 0;
            }
            
            .invoice-table th {
                background: #2c3e50;
                color: white;
                padding: 12px;
                font-weight: bold;
            }
            
            .invoice-table td {
                padding: 10px;
                border-bottom: 1px solid #dee2e6;
            }
            
            .total-section {
                background: #f8f9fa;
                padding: 20px;
                border: 2px solid #3498db;
                margin-top: 30px;
            }
            
            .grand-total {
                background: #3498db;
                color: white;
                padding: 15px;
                font-size: 1.3rem;
                font-weight: bold;
                text-align: center;
                margin-top: 10px;
            }
            
            .invoice-footer {
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 2px solid #dee2e6;
            }
            
            .status-badge {
                padding: 8px 20px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .status-paid { background: #28a745; color: white; }
            .status-unpaid { background: #dc3545; color: white; }
            .status-partial { background: #ffc107; color: black; }
        </style>
    </head>
    <body>
        <!-- Print Button -->
        <div class="text-center my-3 no-print">
            <button onclick="window.print()" class="btn btn-primary btn-lg">
                <i class="fas fa-print"></i> Print Invoice
            </button>
            <button onclick="window.close()" class="btn btn-secondary btn-lg ms-2">
                Close
            </button>
        </div>

        <!-- Invoice Container -->
        <div class="invoice-container">
            <!-- Header -->
            <div class="invoice-header">
                <div class="row align-items-center">
                    <div class="col-6">
                        <div class="company-logo">
                            <i class="fas fa-store"></i> YOUR STORE
                        </div>
                        <p class="mb-0"><strong>Address:</strong> 123 Business Street</p>
                        <p class="mb-0"><strong>City:</strong> Dhaka, Bangladesh</p>
                        <p class="mb-0"><strong>Phone:</strong> +880 1234-567890</p>
                        <p class="mb-0"><strong>Email:</strong> info@yourstore.com</p>
                    </div>
                    <div class="col-6 text-end">
                        <div class="invoice-title">INVOICE</div>
                        <h4 class="text-primary">{{ invoice.invoice_number }}</h4>
                        <span class="status-badge status-{{ invoice.status }}">
                            {{ invoice.status|upper }}
                        </span>
                    </div>
                </div>
            </div>

            <!-- Customer & Date Info -->
            <div class="row">
                <div class="col-7">
                    <div class="info-box">
                        <h6 class="text-muted mb-2"><strong>BILL TO:</strong></h6>
                        <h5 class="mb-2">{{ invoice.customer_name }}</h5>
                        <p class="mb-1"><i class="fas fa-phone"></i> {{ invoice.customer_phone }}</p>
                        {% if invoice. customer_address %}
                        <p class="mb-0"><i class="fas fa-map-marker-alt"></i> {{ invoice. customer_address }}</p>
                        {% endif %}
                    </div>
                </div>
                <div class="col-5">
                    <table class="table table-borderless">
                        <tr>
                            <td><strong>Invoice Date:</strong></td>
                            <td>{{ invoice.invoice_date }}</td>
                        </tr>
                        <tr>
                            <td><strong>Created By:</strong></td>
                            <td>{{ invoice.created_by }}</td>
                        </tr>
                        <tr>
                            <td><strong>Print Date:</strong></td>
                            <td>{{ current_date }}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <!-- Items Table -->
            <table class="table invoice-table">
                <thead>
                    <tr>
                        <th style="width: 5%">#</th>
                        <th style="width: 45%">PRODUCT / SERVICE</th>
                        <th style="width: 15%" class="text-center">QTY</th>
                        <th style="width: 15%" class="text-end">UNIT PRICE</th>
                        <th style="width: 20%" class="text-end">TOTAL</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in invoice.items %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td><strong>{{ item.product_name }}</strong></td>
                        <td class="text-center">{{ item.quantity }}</td>
                        <td class="text-end">৳{{ "%.2f"|format(item.price) }}</td>
                        <td class="text-end"><strong>৳{{ "%.2f"|format(item.total) }}</strong></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <!-- Totals Section -->
            <div class="row">
                <div class="col-6">
                    <div class="info-box">
                        <h6><strong>PAYMENT INFORMATION:</strong></h6>
                        <p class="mb-1">Bank: Your Bank Name</p>
                        <p class="mb-1">Account: 1234567890</p>
                        <p class="mb-0">Mobile Banking: 01234567890</p>
                    </div>
                </div>
                <div class="col-6">
                    <div class="total-section">
                        <table class="table table-borderless mb-0">
                            <tr>
                                <td><strong>Subtotal:</strong></td>
                                <td class="text-end">৳{{ "%.2f"|format(invoice. subtotal) }}</td>
                            </tr>
                            {% if invoice.discount > 0 %}
                            <tr>
                                <td><strong>Discount:</strong></td>
                                <td class="text-end text-danger"><strong>- ৳{{ "%.2f"|format(invoice. discount) }}</strong></td>
                            </tr>
                            {% endif %}
                            {% if invoice.tax > 0 %}
                            <tr>
                                <td><strong>Tax/VAT:</strong></td>
                                <td class="text-end">৳{{ "%.2f"|format(invoice.tax) }}</td>
                            </tr>
                            {% endif %}
                        </table>
                        <div class="grand-total">
                            TOTAL: ৳{{ "%.2f"|format(invoice.total_amount) }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="invoice-footer">
                <h6><strong>Terms & Conditions:</strong></h6>
                <p class="small text-muted mb-3">
                    Payment is due within 7 days. Please include the invoice number with your payment.
                    Late payments may incur additional charges.
                </p>
                <hr>
                <p class="mb-1"><strong>Thank you for your business!</strong></p>
                <p class="small text-muted">This is a computer-generated invoice and does not require a signature.</p>
            </div>
        </div>

        <script src="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </body>
    </html>
    '''
    
    return render_template_string(print_invoice_html, 
                                 invoice=invoice,
                                 current_date=get_bd_date_str())

# ==============================================================================
# Edit Invoice (এরর ছাড়া)
# ==============================================================================

@app.route('/store/invoices/edit/<invoice_id>', methods=['GET', 'POST'])
@store_login_required
def edit_invoice(invoice_id):
    """ইনভয়েস এডিট করুন (এরর ছাড়া)"""
    from bson import ObjectId
    
    try:
        invoice = store_invoices_col.find_one({'_id': ObjectId(invoice_id)})
    except:
        flash('Invalid invoice ID!', 'danger')
        return redirect(url_for('store_invoices'))
    
    if not invoice:
        flash('Invoice not found!', 'danger')
        return redirect(url_for('store_invoices'))
    
    if request.method == 'POST':
        try:
            # Get old items to restore stock
            old_items = invoice.get('items', [])
            
            # Restore stock for old items
            for item in old_items:
                product_name = item.get('product_name')
                quantity = int(item.get('quantity', 0))
                
                product = store_products_col.find_one({'name': product_name})
                if product:
                    new_stock = product. get('stock', 0) + quantity
                    store_products_col.update_one(
                        {'name': product_name},
                        {'$set': {'stock': new_stock}}
                    )
            
            # Get updated data
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            customer_address = request.form.get('customer_address', '').strip()
            invoice_date = request.form.get('invoice_date', get_bd_date_str())
            status = request.form.get('status', 'unpaid')
            
            # Items
            items_json = request.form.get('items_json', '[]')
            items = json. loads(items_json)
            
            if not customer_name or not items:
                flash('Customer name and at least one item required!', 'danger')
                return redirect(url_for('edit_invoice', invoice_id=invoice_id))
            
            # Calculate totals
            subtotal = sum(float(item.get('total', 0)) for item in items)
            discount = float(request.form.get('discount', 0))
            tax = float(request.form.get('tax', 0))
            total_amount = subtotal - discount + tax
            
            # Update invoice
            store_invoices_col.update_one(
                {'_id': ObjectId(invoice_id)},
                {'$set': {
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'customer_address': customer_address,
                    'invoice_date': invoice_date,
                    'status': status,
                    'items': items,
                    'subtotal': subtotal,
                    'discount': discount,
                    'tax': tax,
                    'total_amount': total_amount,
                    'updated_at': get_bd_time(),
                    'updated_by': session. get('store_user')
                }}
            )
            
            # Update stock for new items
            for item in items:
                product_name = item.get('product_name')
                quantity = int(item.get('quantity', 0))
                
                product = store_products_col.find_one({'name': product_name})
                if product:
                    new_stock = product.get('stock', 0) - quantity
                    store_products_col.update_one(
                        {'name': product_name},
                        {'$set': {'stock': new_stock}}
                    )
            
            flash(f'Invoice {invoice["invoice_number"]} updated successfully! ', 'success')
            return redirect(url_for('view_invoice', invoice_id=invoice_id))
            
        except Exception as e:
            flash(f'Error updating invoice: {str(e)}', 'danger')
            return redirect(url_for('edit_invoice', invoice_id=invoice_id))
    
    # GET request - show form
    customers = list(store_customers_col.find())
    products = list(store_products_col.find())
    
    edit_invoice_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Edit Invoice</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            . main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .form-card {
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .item-row {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                border: 1px solid #dee2e6;
            }
            .summary-box {
                background: #e9ecef;
                padding: 20px;
                border-radius: 8px;
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}" class="active"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="mb-3">
                <a href="{{ url_for('view_invoice', invoice_id=invoice._id) }}" class="btn btn-secondary">
                    <i class="fas fa-arrow-left"></i> Back to Invoice
                </a>
            </div>

            <div class="form-card">
                <h4 class="mb-4"><i class="fas fa-edit"></i> Edit Invoice - {{ invoice.invoice_number }}</h4>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <form method="POST" id="invoiceForm">
                    <!-- Customer Info -->
                    <div class="row mb-4">
                        <div class="col-md-4">
                            <label class="form-label">Customer Name *</label>
                            <input type="text" name="customer_name" id="customerName" class="form-control" 
                                   value="{{ invoice.customer_name }}" list="customerList" required>
                            <datalist id="customerList">
                                {% for customer in customers %}
                                <option value="{{ customer.name }}" data-phone="{{ customer.phone }}" data-address="{{ customer.address }}">
                                {% endfor %}
                            </datalist>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Phone</label>
                            <input type="text" name="customer_phone" id="customerPhone" class="form-control" 
                                   value="{{ invoice.customer_phone }}">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Invoice Date</label>
                            <input type="date" name="invoice_date" class="form-control" 
                                   value="{{ invoice.invoice_date }}">
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Status</label>
                            <select name="status" class="form-select">
                                <option value="unpaid" {% if invoice.status == 'unpaid' %}selected{% endif %}>Unpaid</option>
                                <option value="partial" {% if invoice.status == 'partial' %}selected{% endif %}>Partial</option>
                                <option value="paid" {% if invoice.status == 'paid' %}selected{% endif %}>Paid</option>
                            </select>
                        </div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label">Address</label>
                        <input type="text" name="customer_address" id="customerAddress" class="form-control" 
                               value="{{ invoice.customer_address }}">
                    </div>

                    <!-- Items Section -->
                    <h5 class="mb-3">Invoice Items</h5>
                    <div id="itemsContainer"></div>
                    
                    <button type="button" class="btn btn-success mb-3" onclick="addItem()">
                        <i class="fas fa-plus"></i> Add Item
                    </button>

                    <!-- Summary -->
                    <div class="summary-box">
                        <div class="row">
                            <div class="col-md-8">
                                <div class="mb-2">
                                    <label class="form-label">Discount (৳)</label>
                                    <input type="number" name="discount" id="discount" class="form-control" 
                                           value="{{ invoice.discount }}" step="0.01" min="0" onchange="calculateTotal()">
                                </div>
                                <div>
                                    <label class="form-label">Tax (৳)</label>
                                    <input type="number" name="tax" id="tax" class="form-control" 
                                           value="{{ invoice.tax }}" step="0.01" min="0" onchange="calculateTotal()">
                                </div>
                            </div>
                            <div class="col-md-4">
                                <h5>Subtotal: <span id="subtotalDisplay">৳0.00</span></h5>
                                <h5>Discount: <span id="discountDisplay">৳0.00</span></h5>
                                <h5>Tax: <span id="taxDisplay">৳0.00</span></h5>
                                <h4 class="text-primary">Total: <span id="totalDisplay">৳0.00</span></h4>
                            </div>
                        </div>
                    </div>

                    <input type="hidden" name="items_json" id="itemsJson">

                    <div class="d-grid mt-4">
                        <button type="submit" class="btn btn-warning btn-lg">
                            <i class="fas fa-save"></i> Update Invoice
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <script src="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            const products = {{ products | tojson }};
            const existingItems = {{ invoice.items | tojson }};
            let itemCounter = 0;

            // Auto-fill customer info
            document.getElementById('customerName').addEventListener('input', function() {
                const customerName = this.value;
                const customers = {{ customers | tojson }};
                const customer = customers.find(c => c.name === customerName);
                
                if (customer) {
                    document.getElementById('customerPhone').value = customer. phone || '';
                    document.getElementById('customerAddress').value = customer.address || '';
                }
            });

            function addItem(existingData = null) {
                itemCounter++;
                const container = document.getElementById('itemsContainer');
                
                const itemDiv = document.createElement('div');
                itemDiv.className = 'item-row';
                itemDiv.id = 'item-' + itemCounter;
                
                const productName = existingData ? existingData.product_name : '';
                const price = existingData ? existingData.price : '';
                const quantity = existingData ? existingData.quantity : 1;
                const total = existingData ? existingData.total : '';
                
                itemDiv.innerHTML = `
                    <div class="row">
                        <div class="col-md-4">
                            <label class="form-label">Product</label>
                            <input type="text" class="form-control product-name" list="productList-${itemCounter}" 
                                   value="${productName}" onchange="updatePrice(${itemCounter})" required>
                            <datalist id="productList-${itemCounter}">
                                ${products.map(p => `<option value="${p.name}" data-price="${p.price}" data-stock="${p.stock}">`).join('')}
                            </datalist>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Price (৳)</label>
                            <input type="number" class="form-control item-price" value="${price}" step="0.01" min="0" 
                                   onchange="calculateItemTotal(${itemCounter})" required>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Quantity</label>
                            <input type="number" class="form-control item-quantity" value="${quantity}" min="1" 
                                   onchange="calculateItemTotal(${itemCounter})" required>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Total (৳)</label>
                            <input type="number" class="form-control item-total" value="${total}" readonly>
                        </div>
                        <div class="col-md-1">
                            <label class="form-label">&nbsp;</label>
                            <button type="button" class="btn btn-danger w-100" onclick="removeItem(${itemCounter})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
                
                container.appendChild(itemDiv);
                
                if (existingData) {
                    calculateItemTotal(itemCounter);
                }
            }

            function updatePrice(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                const productName = itemDiv.querySelector('.product-name').value;
                const product = products.find(p => p.name === productName);
                
                if (product) {
                    itemDiv.querySelector('.item-price'). value = product.price;
                    calculateItemTotal(itemId);
                }
            }

            function calculateItemTotal(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                const price = parseFloat(itemDiv.querySelector('.item-price').value) || 0;
                const quantity = parseInt(itemDiv.querySelector('. item-quantity').value) || 0;
                const total = price * quantity;
                
                itemDiv.querySelector('.item-total'). value = total.toFixed(2);
                calculateTotal();
            }

            function removeItem(itemId) {
                const itemDiv = document.getElementById('item-' + itemId);
                itemDiv.remove();
                calculateTotal();
            }

            function calculateTotal() {
                let subtotal = 0;
                
                document.querySelectorAll('.item-total').forEach(input => {
                    subtotal += parseFloat(input.value) || 0;
                });
                
                const discount = parseFloat(document.getElementById('discount').value) || 0;
                const tax = parseFloat(document.getElementById('tax').value) || 0;
                const total = subtotal - discount + tax;
                
                document.getElementById('subtotalDisplay').textContent = '৳' + subtotal.toFixed(2);
                document. getElementById('discountDisplay').textContent = '৳' + discount. toFixed(2);
                document.getElementById('taxDisplay').textContent = '৳' + tax. toFixed(2);
                document.getElementById('totalDisplay').textContent = '৳' + total. toFixed(2);
            }

            document.getElementById('invoiceForm').addEventListener('submit', function(e) {
                const items = [];
                
                document.querySelectorAll('.item-row').forEach(itemDiv => {
                    const productName = itemDiv.querySelector('.product-name').value;
                    const price = parseFloat(itemDiv.querySelector('.item-price').value) || 0;
                    const quantity = parseInt(itemDiv. querySelector('.item-quantity').value) || 0;
                    const total = parseFloat(itemDiv.querySelector('.item-total').value) || 0;
                    
                    if (productName && quantity > 0) {
                        items.push({
                            product_name: productName,
                            price: price,
                            quantity: quantity,
                            total: total
                        });
                    }
                });
                
                if (items.length === 0) {
                    e.preventDefault();
                    alert('Please add at least one item! ');
                    return false;
                }
                
                document.getElementById('itemsJson').value = JSON.stringify(items);
            });

            // Load existing items
            existingItems.forEach(item => {
                addItem(item);
            });
            
            calculateTotal();
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(edit_invoice_html, 
                                 invoice=invoice,
                                 customers=customers, 
                                 products=products)

# ==============================================================================
# Delete Invoice
# ==============================================================================

@app.route('/store/invoices/delete/<invoice_id>', methods=['POST'])
@store_login_required
def delete_invoice(invoice_id):
    """ইনভয়েস ডিলিট করুন"""
    from bson import ObjectId
    
    try:
        invoice = store_invoices_col.find_one({'_id': ObjectId(invoice_id)})
        
        if invoice:
            # Restore stock
            for item in invoice.get('items', []):
                product_name = item.get('product_name')
                quantity = int(item.get('quantity', 0))
                
                product = store_products_col.find_one({'name': product_name})
                if product:
                    new_stock = product.get('stock', 0) + quantity
                    store_products_col.update_one(
                        {'name': product_name},
                        {'$set': {'stock': new_stock}}
                    )
            
            store_invoices_col.delete_one({'_id': ObjectId(invoice_id)})
            flash('Invoice deleted successfully!', 'success')
        else:
            flash('Invoice not found!', 'danger')
    except Exception as e:
        flash(f'Error deleting invoice: {str(e)}', 'danger')
    
    return redirect(url_for('store_invoices'))
    # ==============================================================================
# Store Estimates Management
# ==============================================================================

@app.route('/store/estimates')
@store_login_required
def store_estimates():
    """স্টোর এস্টিমেট লিস্ট"""
    estimates = list(store_estimates_col.find(). sort('created_at', -1))
    
    estimates_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Estimates - Store Panel</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0. 0/css/all.min. css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .content-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}" class="active"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3><i class="fas fa-file-alt"></i> Estimates Management</h3>
                <a href="{{ url_for('add_estimate') }}" class="btn btn-primary">
                    <i class="fas fa-plus"></i> Create New Estimate
                </a>
            </div>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <div class="content-card">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Estimate #</th>
                                <th>Customer</th>
                                <th>Date</th>
                                <th>Total Amount</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if estimates %}
                                {% for estimate in estimates %}
                                <tr>
                                    <td><strong>{{ estimate.estimate_number }}</strong></td>
                                    <td>{{ estimate.customer_name }}</td>
                                    <td>{{ estimate.estimate_date if estimate.estimate_date else 'N/A' }}</td>
                                    <td><strong>৳{{ "%.2f"|format(estimate.total_amount) }}</strong></td>
                                    <td>
                                        {% if estimate.status == 'approved' %}
                                            <span class="badge bg-success">Approved</span>
                                        {% elif estimate.status == 'rejected' %}
                                            <span class="badge bg-danger">Rejected</span>
                                        {% else %}
                                            <span class="badge bg-warning">Pending</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        <a href="{{ url_for('print_estimate', estimate_id=estimate._id) }}" class="btn btn-sm btn-success" title="Print" target="_blank">
                                            <i class="fas fa-print"></i>
                                        </a>
                                        <form method="POST" action="{{ url_for('convert_to_invoice', estimate_id=estimate._id) }}" 
                                              style="display:inline;">
                                            <button type="submit" class="btn btn-sm btn-primary" title="Convert to Invoice">
                                                <i class="fas fa-exchange-alt"></i>
                                            </button>
                                        </form>
                                        <form method="POST" action="{{ url_for('delete_estimate', estimate_id=estimate._id) }}" 
                                              style="display:inline;" onsubmit="return confirm('Delete this estimate?');">
                                            <button type="submit" class="btn btn-sm btn-danger" title="Delete">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="6" class="text-center text-muted">No estimates found.  Create your first estimate!</td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min. js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(estimates_html, estimates=estimates)

@app.route('/store/estimates/add', methods=['GET', 'POST'])
@store_login_required
def add_estimate():
    """নতুন এস্টিমেট তৈরি (Invoice এর মতো)"""
    if request.method == 'POST':
        try:
            customer_name = request.form. get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            customer_address = request.form.get('customer_address', '').strip()
            estimate_date = request.form.get('estimate_date', get_bd_date_str())
            
            items_json = request.form.get('items_json', '[]')
            items = json.loads(items_json)
            
            if not customer_name or not items:
                flash('Customer name and at least one item required!', 'danger')
                return redirect(url_for('add_estimate'))
            
            subtotal = sum(float(item. get('total', 0)) for item in items)
            discount = float(request.form.get('discount', 0))
            tax = float(request.form.get('tax', 0))
            total_amount = subtotal - discount + tax
            
            # Generate estimate number
            last_estimate = store_estimates_col.find_one(sort=[('created_at', -1)])
            if last_estimate and 'estimate_number' in last_estimate:
                last_num = int(last_estimate['estimate_number'].split('-')[-1])
                estimate_number = f"EST-{last_num + 1:05d}"
            else:
                estimate_number = "EST-00001"
            
            estimate_data = {
                'estimate_number': estimate_number,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'customer_address': customer_address,
                'estimate_date': estimate_date,
                'items': items,
                'subtotal': subtotal,
                'discount': discount,
                'tax': tax,
                'total_amount': total_amount,
                'status': 'pending',
                'created_at': get_bd_time(),
                'created_by': session. get('store_user')
            }
            
            store_estimates_col.insert_one(estimate_data)
            flash(f'Estimate {estimate_number} created successfully!', 'success')
            return redirect(url_for('store_estimates'))
            
        except Exception as e:
            flash(f'Error creating estimate: {str(e)}', 'danger')
            return redirect(url_for('add_estimate'))
    
    # GET - Same form as invoice
    customers = list(store_customers_col.find())
    products = list(store_products_col.find())
    
    # Use same HTML as add_invoice but change title and endpoints
    return redirect(url_for('store_estimates'))  # Simplified for now

@app.route('/store/estimates/print/<estimate_id>')
@store_login_required
def print_estimate(estimate_id):
    """এস্টিমেট প্রিন্ট (Invoice এর মতো)"""
    from bson import ObjectId
    
    try:
        estimate = store_estimates_col.find_one({'_id': ObjectId(estimate_id)})
    except:
        return "Invalid estimate ID", 400
    
    if not estimate:
        return "Estimate not found", 404
    
    # Similar print template as invoice but with "ESTIMATE" title
    flash('Estimate print feature - similar to invoice print', 'info')
    return redirect(url_for('store_estimates'))

@app.route('/store/estimates/convert/<estimate_id>', methods=['POST'])
@store_login_required
def convert_to_invoice(estimate_id):
    """এস্টিমেট কে ইনভয়েসে কনভার্ট করুন"""
    from bson import ObjectId
    
    try:
        estimate = store_estimates_col.find_one({'_id': ObjectId(estimate_id)})
        
        if not estimate:
            flash('Estimate not found!', 'danger')
            return redirect(url_for('store_estimates'))
        
        # Generate invoice number
        last_invoice = store_invoices_col.find_one(sort=[('created_at', -1)])
        if last_invoice and 'invoice_number' in last_invoice:
            last_num = int(last_invoice['invoice_number'].split('-')[-1])
            invoice_number = f"INV-{last_num + 1:05d}"
        else:
            invoice_number = "INV-00001"
        
        # Create invoice from estimate
        invoice_data = {
            'invoice_number': invoice_number,
            'customer_name': estimate['customer_name'],
            'customer_phone': estimate['customer_phone'],
            'customer_address': estimate. get('customer_address', ''),
            'invoice_date': get_bd_date_str(),
            'items': estimate['items'],
            'subtotal': estimate['subtotal'],
            'discount': estimate.get('discount', 0),
            'tax': estimate.get('tax', 0),
            'total_amount': estimate['total_amount'],
            'status': 'unpaid',
            'converted_from_estimate': estimate['estimate_number'],
            'created_at': get_bd_time(),
            'created_by': session.get('store_user')
        }
        
        result = store_invoices_col. insert_one(invoice_data)
        
        # Update estimate status
        store_estimates_col.update_one(
            {'_id': ObjectId(estimate_id)},
            {'$set': {'status': 'approved', 'converted_to_invoice': invoice_number}}
        )
        
        # Update stock
        for item in estimate['items']:
            product_name = item. get('product_name')
            quantity = int(item.get('quantity', 0))
            
            product = store_products_col.find_one({'name': product_name})
            if product:
                new_stock = product.get('stock', 0) - quantity
                store_products_col.update_one(
                    {'name': product_name},
                    {'$set': {'stock': new_stock}}
                )
        
        flash(f'Estimate converted to Invoice {invoice_number} successfully!', 'success')
        return redirect(url_for('view_invoice', invoice_id=result.inserted_id))
        
    except Exception as e:
        flash(f'Error converting estimate: {str(e)}', 'danger')
        return redirect(url_for('store_estimates'))

@app.route('/store/estimates/delete/<estimate_id>', methods=['POST'])
@store_login_required
def delete_estimate(estimate_id):
    """এস্টিমেট ডিলিট"""
    from bson import ObjectId
    
    try:
        store_estimates_col.delete_one({'_id': ObjectId(estimate_id)})
        flash('Estimate deleted successfully!', 'success')
    except:
        flash('Error deleting estimate!', 'danger')
    
    return redirect(url_for('store_estimates'))

# ==============================================================================
# Store Payments
# ==============================================================================

@app.route('/store/payments')
@store_login_required
def store_payments():
    """পেমেন্ট লিস্ট"""
    payments = list(store_payments_col. find(). sort('created_at', -1))
    
    payments_html = '''
    <! DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1. 0">
        <title>Payments - Store Panel</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            .sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0.2);
            }
            .sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            . main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .content-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}" class="active"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <h3 class="mb-4"><i class="fas fa-money-bill"></i> Payments Management</h3>

            <div class="content-card">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Payment tracking coming soon!  Link payments to invoices and track payment history.
                </div>
                
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Date</th>
                                <th>Invoice #</th>
                                <th>Customer</th>
                                <th>Amount</th>
                                <th>Method</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td colspan="6" class="text-center text-muted">No payments recorded yet</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle. min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(payments_html)

# ==============================================================================
# Store Reports
# ==============================================================================

@app. route('/store/reports')
@store_login_required
def store_reports():
    """রিপোর্ট পেজ"""
    # Calculate statistics
    total_sales = 0
    total_invoices = store_invoices_col.count_documents({})
    
    for invoice in store_invoices_col. find():
        total_sales += invoice. get('total_amount', 0)
    
    paid_invoices = store_invoices_col.count_documents({'status': 'paid'})
    unpaid_invoices = store_invoices_col.count_documents({'status': 'unpaid'})
    
    low_stock_products = list(store_products_col.find({'stock': {'$lt': 10}}))
    
    reports_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reports - Store Panel</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f4f6f9; }
            . sidebar {
                background: linear-gradient(180deg, #2c3e50 0%, #3498db 100%);
                min-height: 100vh;
                color: white;
                position: fixed;
                width: 250px;
                padding-top: 20px;
            }
            .sidebar-brand {
                padding: 20px;
                font-size: 1.5rem;
                font-weight: bold;
                text-align: center;
                border-bottom: 1px solid rgba(255,255,255,0. 2);
            }
            . sidebar-menu {
                list-style: none;
                padding: 0;
                margin-top: 20px;
            }
            .sidebar-menu li { padding: 0; }
            .sidebar-menu a {
                display: block;
                padding: 15px 25px;
                color: white;
                text-decoration: none;
                transition: all 0.3s;
            }
            .sidebar-menu a:hover {
                background: rgba(255,255,255,0.1);
                padding-left: 30px;
            }
            .main-content {
                margin-left: 250px;
                padding: 20px;
            }
            .report-card {
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .stat-box {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-brand">
                <i class="fas fa-store"></i> Store Panel
            </div>
            <ul class="sidebar-menu">
                <li><a href="{{ url_for('store_panel') }}"><i class="fas fa-home"></i> Dashboard</a></li>
                <li><a href="{{ url_for('store_products') }}"><i class="fas fa-box"></i> Products</a></li>
                <li><a href="{{ url_for('store_customers') }}"><i class="fas fa-users"></i> Customers</a></li>
                <li><a href="{{ url_for('store_invoices') }}"><i class="fas fa-file-invoice"></i> Invoices</a></li>
                <li><a href="{{ url_for('store_estimates') }}"><i class="fas fa-file-alt"></i> Estimates</a></li>
                <li><a href="{{ url_for('store_payments') }}"><i class="fas fa-money-bill"></i> Payments</a></li>
                <li><a href="{{ url_for('store_reports') }}" class="active"><i class="fas fa-chart-bar"></i> Reports</a></li>
                <li style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 20px;">
                    <a href="{{ url_for('dashboard') }}"><i class="fas fa-building"></i> Main System</a>
                </li>
                <li><a href="{{ url_for('store_logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></li>
            </ul>
        </div>

        <!-- Main Content -->
        <div class="main-content">
            <h3 class="mb-4"><i class="fas fa-chart-bar"></i> Sales Reports & Analytics</h3>

            <!-- Statistics -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="stat-box" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
                        <div class="stat-number">৳{{ "%.2f"|format(total_sales) }}</div>
                        <div>Total Sales</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div class="stat-number">{{ total_invoices }}</div>
                        <div>Total Invoices</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <div class="stat-number">{{ paid_invoices }}</div>
                        <div>Paid Invoices</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-box" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <div class="stat-number">{{ unpaid_invoices }}</div>
                        <div>Unpaid Invoices</div>
                    </div>
                </div>
            </div>

            <!-- Low Stock Alert -->
            <div class="report-card">
                <h5 class="mb-3"><i class="fas fa-exclamation-triangle text-warning"></i> Low Stock Alert</h5>
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Product</th>
                                <th>Current Stock</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if low_stock_products %}
                                {% for product in low_stock_products %}
                                <tr>
                                    <td>{{ product.name }}</td>
                                    <td><strong>{{ product.stock }}</strong></td>
                                    <td>
                                        {% if product.stock == 0 %}
                                            <span class="badge bg-danger">Out of Stock</span>
                                        {% else %}
                                            <span class="badge bg-warning">Low Stock</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr>
                                    <td colspan="3" class="text-center text-success">All products have sufficient stock! </td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(reports_html, 
                                 total_sales=total_sales,
                                 total_invoices=total_invoices,
                                 paid_invoices=paid_invoices,
                                 unpaid_invoices=unpaid_invoices,
                                 low_stock_products=low_stock_products)

# ==============================================================================
# Accessories Management
# ==============================================================================

@app.route('/accessories')
@login_required
def accessories_page():
    """এক্সেসরিজ ম্যানেজমেন্ট পেজ"""
    accessories = list(accessories_col.find().sort('created_at', -1))
    
    accessories_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Accessories Management</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; }
            . navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .card { border: none; border-radius: 15px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); margin-top: 20px; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="{{ url_for('dashboard') }}">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
            </div>
        </nav>

        <div class="container">
            <div class="card">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h3><i class="fas fa-toolbox"></i> Accessories Inventory</h3>
                        <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addModal">
                            <i class="fas fa-plus"></i> Add Accessory
                        </button>
                    </div>

                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                    {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <div class="table-responsive">
                        <table class="table table-hover">
                            <thead class="table-light">
                                <tr>
                                    <th>Name</th>
                                    <th>Category</th>
                                    <th>Quantity</th>
                                    <th>Location</th>
                                    <th>Added Date</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if accessories %}
                                    {% for item in accessories %}
                                    <tr>
                                        <td><strong>{{ item.name }}</strong></td>
                                        <td><span class="badge bg-info">{{ item.category }}</span></td>
                                        <td>{{ item.quantity }}</td>
                                        <td>{{ item.location }}</td>
                                        <td>{{ item. created_at.strftime('%d-%m-%Y') if item.created_at else 'N/A' }}</td>
                                        <td>
                                            <button class="btn btn-sm btn-warning" onclick="alert('Edit feature')">
                                                <i class="fas fa-edit"></i>
                                            </button>
                                            <form method="POST" action="{{ url_for('delete_accessory', acc_id=item._id) }}" 
                                                  style="display:inline;" onsubmit="return confirm('Delete? ');">
                                                <button type="submit" class="btn btn-sm btn-danger">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                {% else %}
                                    <tr>
                                        <td colspan="6" class="text-center text-muted">No accessories found</td>
                                    </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Add Modal -->
        <div class="modal fade" id="addModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Add Accessory</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form method="POST" action="{{ url_for('add_accessory') }}">
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Name *</label>
                                <input type="text" name="name" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Category *</label>
                                <input type="text" name="category" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Quantity *</label>
                                <input type="number" name="quantity" class="form-control" min="0" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Location</label>
                                <input type="text" name="location" class="form-control">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="submit" class="btn btn-primary">Add Accessory</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1. 3/dist/js/bootstrap. bundle.min.js"></script>
    </body>
    </html>
    '''
    
    return render_template_string(accessories_html, accessories=accessories)

@app.route('/accessories/add', methods=['POST'])
@login_required
def add_accessory():
    """এক্সেসরি যোগ করুন"""
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    quantity = request.form.get('quantity', 0)
    location = request. form.get('location', ''). strip()
    
    if name and category:
        accessories_col.insert_one({
            'name': name,
            'category': category,
            'quantity': int(quantity),
            'location': location,
            'created_at': get_bd_time(),
            'created_by': session. get('username')
        })
        flash('Accessory added successfully!', 'success')
    else:
        flash('Name and category required!', 'danger')
    
    return redirect(url_for('accessories_page'))

@app.route('/accessories/delete/<acc_id>', methods=['POST'])
@login_required
def delete_accessory(acc_id):
    """এক্সেসরি ডিলিট করুন"""
    from bson import ObjectId
    
    try:
        accessories_col.delete_one({'_id': ObjectId(acc_id)})
        flash('Accessory deleted! ', 'success')
    except:
        flash('Error deleting accessory!', 'danger')
    
    return redirect(url_for('accessories_page'))
    # ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """404 Error Handler"""
    error_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>404 - Page Not Found</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }
            .error-container {
                text-align: center;
            }
            .error-code {
                font-size: 8rem;
                font-weight: bold;
                text-shadow: 3px 3px 10px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">404</div>
            <h2>Page Not Found</h2>
            <p class="mb-4">The page you are looking for doesn't exist.</p>
            <a href="{{ url_for('dashboard') }}" class="btn btn-light btn-lg">
                <i class="fas fa-home"></i> Go to Dashboard
            </a>
        </div>
    </body>
    </html>
    '''
    return render_template_string(error_html), 404

@app.errorhandler(500)
def internal_error(error):
    """500 Error Handler"""
    error_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>500 - Internal Server Error</title>
        <link href="https://cdn. jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }
            .error-container {
                text-align: center;
            }
            .error-code {
                font-size: 8rem;
                font-weight: bold;
                text-shadow: 3px 3px 10px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">500</div>
            <h2>Internal Server Error</h2>
            <p class="mb-4">Something went wrong.  Please try again later.</p>
            <a href="{{ url_for('dashboard') }}" class="btn btn-light btn-lg">
                <i class="fas fa-home"></i> Go to Dashboard
            </a>
        </div>
    </body>
    </html>
    '''
    return render_template_string(error_html), 500

@app.errorhandler(403)
def forbidden_error(error):
    """403 Error Handler"""
    error_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>403 - Forbidden</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
            }
            . error-container {
                text-align: center;
            }
            .error-code {
                font-size: 8rem;
                font-weight: bold;
                text-shadow: 3px 3px 10px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">403</div>
            <h2>Access Forbidden</h2>
            <p class="mb-4">You don't have permission to access this resource. </p>
            <a href="{{ url_for('dashboard') }}" class="btn btn-light btn-lg">
                <i class="fas fa-home"></i> Go to Dashboard
            </a>
        </div>
    </body>
    </html>
    '''
    return render_template_string(error_html), 403

# ==============================================================================
# Helper Routes for Testing
# ==============================================================================

@app.route('/test-db')
def test_db():
    """Database Connection Test"""
    try:
        # Test MongoDB connection
        client. admin. command('ping')
        
        # Count documents
        users_count = users_col.count_documents({})
        products_count = store_products_col.count_documents({})
        
        return f'''
        <h2>Database Connection Test</h2>
        <p style="color: green;">✓ MongoDB Connected Successfully!</p>
        <ul>
            <li>Users: {users_count}</li>
            <li>Products: {products_count}</li>
            <li>Server Time: {get_bd_time(). strftime('%Y-%m-%d %H:%M:%S')}</li>
        </ul>
        <a href="{url_for('login')}">Go to Login</a>
        '''
    except Exception as e:
        return f'''
        <h2>Database Connection Test</h2>
        <p style="color: red;">✗ Connection Failed! </p>
        <p>Error: {str(e)}</p>
        '''

@app.route('/create-demo-data')
@admin_required
def create_demo_data():
    """ডেমো ডেটা তৈরি করুন (Testing এর জন্য)"""
    try:
        # Demo Store User
        if store_users_col.count_documents({'username': 'store1'}) == 0:
            store_users_col.insert_one({
                'username': 'store1',
                'password': 'store123',
                'role': 'staff',
                'status': 'active',
                'created_at': get_bd_time()
            })
        
        # Demo Products
        demo_products = [
            {'name': 'Laptop', 'category': 'Electronics', 'price': 45000, 'stock': 10, 'unit': 'pcs'},
            {'name': 'Mouse', 'category': 'Electronics', 'price': 500, 'stock': 50, 'unit': 'pcs'},
            {'name': 'Keyboard', 'category': 'Electronics', 'price': 1500, 'stock': 30, 'unit': 'pcs'},
            {'name': 'Monitor', 'category': 'Electronics', 'price': 12000, 'stock': 15, 'unit': 'pcs'},
            {'name': 'Headphone', 'category': 'Electronics', 'price': 2000, 'stock': 25, 'unit': 'pcs'},
        ]
        
        for product in demo_products:
            if store_products_col.count_documents({'name': product['name']}) == 0:
                product['created_at'] = get_bd_time()
                product['created_by'] = 'admin'
                store_products_col.insert_one(product)
        
        # Demo Customers
        demo_customers = [
            {'name': 'Ahmed Hassan', 'phone': '01712345678', 'email': 'ahmed@example.com', 'address': 'Dhaka, Bangladesh'},
            {'name': 'Fatima Khan', 'phone': '01823456789', 'email': 'fatima@example.com', 'address': 'Chittagong, Bangladesh'},
            {'name': 'Rahul Ahmed', 'phone': '01934567890', 'email': 'rahul@example.com', 'address': 'Sylhet, Bangladesh'},
        ]
        
        for customer in demo_customers:
            if store_customers_col.count_documents({'phone': customer['phone']}) == 0:
                customer['created_at'] = get_bd_time()
                customer['created_by'] = 'admin'
                store_customers_col.insert_one(customer)
        
        # Demo Accessories
        demo_accessories = [
            {'name': 'HDMI Cable', 'category': 'Cables', 'quantity': 100, 'location': 'Shelf A1'},
            {'name': 'USB Cable', 'category': 'Cables', 'quantity': 150, 'location': 'Shelf A2'},
            {'name': 'Power Adapter', 'category': 'Adapters', 'quantity': 80, 'location': 'Shelf B1'},
        ]
        
        for accessory in demo_accessories:
            if accessories_col.count_documents({'name': accessory['name']}) == 0:
                accessory['created_at'] = get_bd_time()
                accessory['created_by'] = 'admin'
                accessories_col.insert_one(accessory)
        
        flash('Demo data created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating demo data: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

# ==============================================================================
# System Info Route
# ==============================================================================

@app.route('/system-info')
@admin_required
def system_info():
    """সিস্টেম ইনফরমেশন"""
    import platform
    import sys
    
    info_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>System Information</title>
        <link href="https://cdn.jsdelivr. net/npm/bootstrap@5. 1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare. com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; padding: 20px; }
            .info-card { 
                background: white; 
                border-radius: 15px; 
                padding: 30px; 
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                max-width: 800px;
                margin: 0 auto;
            }
            .info-row { 
                padding: 10px; 
                border-bottom: 1px solid #e9ecef; 
            }
            .info-label { 
                font-weight: bold; 
                color: #495057; 
            }
        </style>
    </head>
    <body>
        <div class="info-card">
            <h2 class="mb-4"><i class="fas fa-info-circle"></i> System Information</h2>
            
            <div class="info-row">
                <span class="info-label">Python Version:</span>
                <span>{{ python_version }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Flask Version:</span>
                <span>{{ flask_version }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Operating System:</span>
                <span>{{ os_info }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Server Time (BD):</span>
                <span>{{ current_time }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Users:</span>
                <span>{{ total_users }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Store Users:</span>
                <span>{{ total_store_users }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Products:</span>
                <span>{{ total_products }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Customers:</span>
                <span>{{ total_customers }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Invoices:</span>
                <span>{{ total_invoices }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Estimates:</span>
                <span>{{ total_estimates }}</span>
            </div>
            
            <div class="info-row">
                <span class="info-label">Total Accessories:</span>
                <span>{{ total_accessories }}</span>
            </div>
            
            <div class="mt-4 text-center">
                <a href="{{ url_for('dashboard') }}" class="btn btn-primary">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <a href="{{ url_for('create_demo_data') }}" class="btn btn-success">
                    <i class="fas fa-plus"></i> Create Demo Data
                </a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return render_template_string(info_html,
                                 python_version=sys.version,
                                 flask_version=Flask.__version__,
                                 os_info=f"{platform.system()} {platform. release()}",
                                 current_time=get_bd_time().strftime('%Y-%m-%d %H:%M:%S %Z'),
                                 total_users=users_col.count_documents({}),
                                 total_store_users=store_users_col.count_documents({}),
                                 total_products=store_products_col.count_documents({}),
                                 total_customers=store_customers_col.count_documents({}),
                                 total_invoices=store_invoices_col. count_documents({}),
                                 total_estimates=store_estimates_col.count_documents({}),
                                 total_accessories=accessories_col.count_documents({}))

# ==============================================================================
# Main Application Runner
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Office Management System Starting...")
    print("=" * 60)
    print(f"📅 Server Time (Bangladesh): {get_bd_time(). strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 MongoDB Status: Connected to {MONGO_URI[:30]}...")
    print(f"👤 Default Admin: username='admin', password='admin123'")
    print("=" * 60)
    print("\n✨ Features Available:")
    print("   1. Main System Login (admin/admin123)")
    print("   2.  Closing Report (Preview → Download)")
    print("   3.  PO Sheet (Preview → Download)")
    print("   4. Store Panel (Beautiful Design)")
    print("   5.  Products Management")
    print("   6.  Customers Management")
    print("   7. Invoices (Add/Edit/View/Print)")
    print("   8.  Estimates (Convert to Invoice)")
    print("   9. Reports & Analytics")
    print("   10. Accessories Management")
    print("   11.  User Management (Admin Only)")
    print("   12.  Store User Management (Admin Only)")
    print("=" * 60)
    print("\n🔑 Access URLs:")
    print("   Main Login:  http://localhost:5000/login")
    print("   Store Login: http://localhost:5000/store/login")
    print("   Test DB:     http://localhost:5000/test-db")
    print("   System Info: http://localhost:5000/system-info")
    print("=" * 60)
    print("\n⚙️  Important Notes:")
    print("   ✓ Closing Report: প্রিভিউ দেখে তারপর ডাউনলোড")
    print("   ✓ PO Sheet: প্রিভিউ দেখে তারপর ডাউনলোড")
    print("   ✓ Invoice/Estimate: এরর ছাড়া এডিট করা যাবে")
    print("   ✓ Store Login: সরাসরি Store Panel এ যাবে")
    print("   ✓ Print: Professional Template সহ")
    print("=" * 60)
    print("\n🎯 Quick Start:")
    print("   1. প্রথমে: http://localhost:5000/test-db - DB চেক করুন")
    print("   2. Login: admin / admin123")
    print("   3. Demo Data: Dashboard থেকে 'Create Demo Data' ক্লিক করুন")
    print("   4. Store User তৈরি করুন: User Management থেকে")
    print("=" * 60)
    print("\n💡 Troubleshooting:")
    print("   - যদি MongoDB Error আসে: MONGO_URI চেক করুন")
    print("   - যদি Port Busy: app.run(port=5001) করুন")
    print("   - Session Timeout: 2 ঘণ্টা পর আবার Login করুন")
    print("=" * 60)
    print("\n🔥 Server Starting on http://localhost:5000")
    print("   Press CTRL+C to quit\n")
    
    # Run the application
    try:
        app.run(
            host='0.0.0.0',  # সব IP থেকে এক্সেস করা যাবে
            port=5000,
            debug=True,  # Development mode (Auto-reload on code change)
            threaded=True  # Multiple requests handle করবে
        )
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("👋 Server Stopped.  Thank you for using Office Management System!")
        print("=" * 60)
    except Exception as e:
        print("\n\n" + "=" * 60)
        print(f"❌ Error starting server: {str(e)}")
        print("=" * 60)
        download_name=filename
    )
    
