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

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) 

bd_tz = pytz.timezone('Asia/Dhaka')

def get_bd_time():
    return datetime.now(bd_tz)

def get_bd_date_str():
    return get_bd_time().strftime('%d-%m-%Y')

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
    
    # --- Store Collections ---
    store_customers_col = db['store_customers']
    store_products_col = db['store_products']
    store_invoices_col = db['store_invoices']
    store_quotations_col = db['store_quotations']
    store_payments_col = db['store_payments']
    store_settings_col = db['store_settings']
    store_expenses_col = db['store_expenses']
    
    print("MongoDB Connected Successfully!")
except Exception as e:
    print(f"MongoDB Connection Error: {e}")

# ==============================================================================
# STORE HELPER FUNCTIONS
# ==============================================================================

def generate_invoice_number():
    """Generate unique invoice number like INV-2025-0001"""
    year = get_bd_time().strftime('%Y')
    record = store_settings_col.find_one({"_id": "invoice_counter"})
    if record and record.get('year') == year:
        counter = record.get('counter', 0) + 1
    else:
        counter = 1
    store_settings_col.replace_one(
        {"_id": "invoice_counter"},
        {"_id": "invoice_counter", "counter": counter, "year": year},
        upsert=True
    )
    return f"INV-{year}-{str(counter).zfill(4)}"

def generate_quotation_number():
    """Generate unique quotation number like QTN-2025-0001"""
    year = get_bd_time().strftime('%Y')
    record = store_settings_col.find_one({"_id": "quotation_counter"})
    if record and record.get('year') == year:
        counter = record.get('counter', 0) + 1
    else:
        counter = 1
    store_settings_col.replace_one(
        {"_id": "quotation_counter"},
        {"_id": "quotation_counter", "counter": counter, "year": year},
        upsert=True
    )
    return f"QTN-{year}-{str(counter).zfill(4)}"

def generate_customer_id():
    """Generate unique customer ID like CUST-0001"""
    record = store_settings_col.find_one({"_id": "customer_counter"})
    if record:
        counter = record.get('counter', 0) + 1
    else:
        counter = 1
    store_settings_col.replace_one(
        {"_id": "customer_counter"},
        {"_id": "customer_counter", "counter": counter},
        upsert=True
    )
    return f"CUST-{str(counter).zfill(4)}"

# --- Customer Functions ---
def get_all_customers():
    return list(store_customers_col.find().sort("created_at", -1))

def get_customer_by_id(customer_id):
    return store_customers_col.find_one({"customer_id": customer_id})

def add_customer(data):
    customer_id = generate_customer_id()
    customer = {
        "customer_id": customer_id,
        "name": data.get('name'),
        "phone": data.get('phone'),
        "email": data.get('email', ''),
        "address": data.get('address', ''),
        "total_due": 0,
        "total_paid": 0,
        "total_purchase": 0,
        "created_at": get_bd_time().isoformat(),
        "updated_at": get_bd_time().isoformat()
    }
    store_customers_col.insert_one(customer)
    return customer_id

def update_customer(customer_id, data):
    store_customers_col.update_one(
        {"customer_id": customer_id},
        {"$set": {
            "name": data.get('name'),
            "phone": data.get('phone'),
            "email": data.get('email', ''),
            "address": data.get('address', ''),
            "updated_at": get_bd_time().isoformat()
        }}
    )

def delete_customer(customer_id):
    store_customers_col.delete_one({"customer_id": customer_id})

# --- Product Functions ---
def get_all_products():
    return list(store_products_col.find().sort("name", 1))

def get_product_by_id(product_id):
    try:
        return store_products_col.find_one({"_id": ObjectId(product_id)})
    except:
        return None

def add_product(data):
    product = {
        "name": data.get('name'),
        "category": data.get('category', 'General'),
        "unit": data.get('unit', 'pcs'),
        "buy_price": float(data.get('buy_price', 0)),
        "sell_price": float(data.get('sell_price', 0)),
        "stock": float(data.get('stock', 0)),
        "description": data.get('description', ''),
        "created_at": get_bd_time().isoformat(),
        "updated_at": get_bd_time().isoformat()
    }
    result = store_products_col.insert_one(product)
    return str(result.inserted_id)

def update_product(product_id, data):
    store_products_col.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {
            "name": data.get('name'),
            "category": data.get('category', 'General'),
            "unit": data.get('unit', 'pcs'),
            "buy_price": float(data.get('buy_price', 0)),
            "sell_price": float(data.get('sell_price', 0)),
            "stock": float(data.get('stock', 0)),
            "description": data.get('description', ''),
            "updated_at": get_bd_time().isoformat()
        }}
    )

def delete_product(product_id):
    store_products_col.delete_one({"_id": ObjectId(product_id)})

def update_product_stock(product_id, qty_change):
    """Update product stock (negative for sales, positive for purchase)"""
    store_products_col.update_one(
        {"_id": ObjectId(product_id)},
        {"$inc": {"stock": qty_change}}
    )

# --- Invoice Functions ---
def get_all_invoices():
    return list(store_invoices_col.find().sort("created_at", -1))

def get_invoice_by_number(invoice_no):
    return store_invoices_col.find_one({"invoice_no": invoice_no})

def get_customer_invoices(customer_id):
    return list(store_invoices_col.find({"customer_id": customer_id}).sort("created_at", -1))

def create_invoice(data):
    invoice_no = generate_invoice_number()
    
    items = data.get('items', [])
    subtotal = sum(float(item.get('total', 0)) for item in items)
    discount = float(data.get('discount', 0))
    total = subtotal - discount
    paid = float(data.get('paid', 0))
    due = total - paid
    
    invoice = {
        "invoice_no": invoice_no,
        "customer_id": data.get('customer_id'),
        "customer_name": data.get('customer_name'),
        "customer_phone": data.get('customer_phone'),
        "customer_address": data.get('customer_address', ''),
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "paid": paid,
        "due": due,
        "status": "paid" if due <= 0 else "due",
        "notes": data.get('notes', ''),
        "created_by": data.get('created_by', 'Unknown'),
        "created_at": get_bd_time().isoformat(),
        "updated_at": get_bd_time().isoformat()
    }
    
    store_invoices_col.insert_one(invoice)
    
    # Update customer totals
    if data.get('customer_id'):
        store_customers_col.update_one(
            {"customer_id": data.get('customer_id')},
            {"$inc": {
                "total_purchase": total,
                "total_paid": paid,
                "total_due": due
            }}
        )
    
    # Update product stock
    for item in items:
        if item.get('product_id'):
            update_product_stock(item['product_id'], -float(item.get('qty', 0)))
    
    # Record payment if any
    if paid > 0:
        add_payment({
            "invoice_no": invoice_no,
            "customer_id": data.get('customer_id'),
            "customer_name": data.get('customer_name'),
            "amount": paid,
            "payment_method": data.get('payment_method', 'Cash'),
            "notes": f"Payment for invoice {invoice_no}"
        })
    
    return invoice_no

def update_invoice(invoice_no, data):
    old_invoice = get_invoice_by_number(invoice_no)
    if not old_invoice:
        return False
    
    items = data.get('items', [])
    subtotal = sum(float(item.get('total', 0)) for item in items)
    discount = float(data.get('discount', 0))
    total = subtotal - discount
    paid = float(data.get('paid', 0))
    due = total - paid
    
    # Calculate difference for customer update
    old_total = old_invoice.get('total', 0)
    old_paid = old_invoice.get('paid', 0)
    old_due = old_invoice.get('due', 0)
    
    store_invoices_col.update_one(
        {"invoice_no": invoice_no},
        {"$set": {
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "paid": paid,
            "due": due,
            "status": "paid" if due <= 0 else "due",
            "notes": data.get('notes', ''),
            "updated_at": get_bd_time().isoformat()
        }}
    )
    
    # Update customer totals
    if old_invoice.get('customer_id'):
        store_customers_col.update_one(
            {"customer_id": old_invoice.get('customer_id')},
            {"$inc": {
                "total_purchase": total - old_total,
                "total_paid": paid - old_paid,
                "total_due": due - old_due
            }}
        )
    
    return True

# --- Payment Functions ---
def get_all_payments():
    return list(store_payments_col.find().sort("created_at", -1))

def add_payment(data):
    payment = {
        "invoice_no": data.get('invoice_no', ''),
        "customer_id": data.get('customer_id'),
        "customer_name": data.get('customer_name'),
        "amount": float(data.get('amount', 0)),
        "payment_method": data.get('payment_method', 'Cash'),
        "notes": data.get('notes', ''),
        "created_by": data.get('created_by', session.get('user', 'Unknown')),
        "created_at": get_bd_time().isoformat()
    }
    store_payments_col.insert_one(payment)
    return True

def collect_due(invoice_no, amount, payment_method='Cash'):
    """Collect due payment for an invoice"""
    invoice = get_invoice_by_number(invoice_no)
    if not invoice:
        return False
    
    new_paid = invoice.get('paid', 0) + amount
    new_due = invoice.get('total', 0) - new_paid
    
    store_invoices_col.update_one(
        {"invoice_no": invoice_no},
        {"$set": {
            "paid": new_paid,
            "due": new_due,
            "status": "paid" if new_due <= 0 else "due",
            "updated_at": get_bd_time().isoformat()
        }}
    )
    
    # Update customer
    if invoice.get('customer_id'):
        store_customers_col.update_one(
            {"customer_id": invoice.get('customer_id')},
            {"$inc": {
                "total_paid": amount,
                "total_due": -amount
            }}
        )
    
    # Record payment
    add_payment({
        "invoice_no": invoice_no,
        "customer_id": invoice.get('customer_id'),
        "customer_name": invoice.get('customer_name'),
        "amount": amount,
        "payment_method": payment_method,
        "notes": f"Due collection for invoice {invoice_no}"
    })
    
    return True

# --- Quotation Functions ---
def get_all_quotations():
    return list(store_quotations_col.find().sort("created_at", -1))

def get_quotation_by_number(quotation_no):
    return store_quotations_col.find_one({"quotation_no": quotation_no})

def create_quotation(data):
    quotation_no = generate_quotation_number()
    
    items = data.get('items', [])
    subtotal = sum(float(item.get('total', 0)) for item in items)
    discount = float(data.get('discount', 0))
    total = subtotal - discount
    
    quotation = {
        "quotation_no": quotation_no,
        "customer_name": data.get('customer_name'),
        "customer_phone": data.get('customer_phone'),
        "customer_address": data.get('customer_address', ''),
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "validity": data.get('validity', '7 days'),
        "notes": data.get('notes', ''),
        "status": "pending",
        "created_by": data.get('created_by', 'Unknown'),
        "created_at": get_bd_time().isoformat()
    }
    
    store_quotations_col.insert_one(quotation)
    return quotation_no

def convert_quotation_to_invoice(quotation_no, paid_amount=0):
    """Convert a quotation to invoice"""
    quotation = get_quotation_by_number(quotation_no)
    if not quotation:
        return None
    
    invoice_data = {
        "customer_name": quotation.get('customer_name'),
        "customer_phone": quotation.get('customer_phone'),
        "customer_address": quotation.get('customer_address'),
        "items": quotation.get('items'),
        "discount": quotation.get('discount', 0),
        "paid": paid_amount,
        "notes": f"Converted from quotation {quotation_no}",
        "created_by": session.get('user', 'Unknown')
    }
    
    invoice_no = create_invoice(invoice_data)
    
    # Update quotation status
    store_quotations_col.update_one(
        {"quotation_no": quotation_no},
        {"$set": {"status": "converted", "converted_to": invoice_no}}
    )
    
    return invoice_no

# --- Store Dashboard Stats ---
def get_store_dashboard_stats():
    today = get_bd_date_str()
    now = get_bd_time()
    
    # Today's stats
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    all_invoices = list(store_invoices_col.find())
    all_payments = list(store_payments_col.find())
    all_customers = list(store_customers_col.find())
    all_products = list(store_products_col.find())
    
    # Calculate totals
    total_sales = sum(inv.get('total', 0) for inv in all_invoices)
    total_due = sum(inv.get('due', 0) for inv in all_invoices if inv.get('due', 0) > 0)
    total_collected = sum(pay.get('amount', 0) for pay in all_payments)
    
    # Today's sales
    today_invoices = [inv for inv in all_invoices if inv.get('created_at', '').startswith(today.replace('-', '')[:8]) or today in inv.get('created_at', '')]
    today_sales = sum(inv.get('total', 0) for inv in today_invoices)
    today_collection = sum(inv.get('paid', 0) for inv in today_invoices)
    
    # Monthly stats for chart
    monthly_data = defaultdict(lambda: {'sales': 0, 'collection': 0})
    for inv in all_invoices:
        try:
            date_str = inv.get('created_at', '')[:10]
            if 'T' in date_str:
                dt = datetime.fromisoformat(inv.get('created_at', '')[:19])
            else:
                dt = datetime.strptime(date_str, '%d-%m-%Y')
            month_key = dt.strftime('%b %Y')
            monthly_data[month_key]['sales'] += inv.get('total', 0)
            monthly_data[month_key]['collection'] += inv.get('paid', 0)
        except:
            pass
    
    # Get last 6 months
    chart_labels = []
    chart_sales = []
    chart_collection = []
    
    for i in range(5, -1, -1):
        month_date = now - timedelta(days=i*30)
        month_key = month_date.strftime('%b %Y')
        chart_labels.append(month_key)
        chart_sales.append(monthly_data.get(month_key, {}).get('sales', 0))
        chart_collection.append(monthly_data.get(month_key, {}).get('collection', 0))
    
    # Due customers
    due_customers = [c for c in all_customers if c.get('total_due', 0) > 0]
    due_customers.sort(key=lambda x: x.get('total_due', 0), reverse=True)
    
    # Recent invoices
    recent_invoices = all_invoices[:10]
    
    # Low stock products
    low_stock_products = [p for p in all_products if p.get('stock', 0) < 10]
    
    return {
        "total_customers": len(all_customers),
        "total_products": len(all_products),
        "total_invoices": len(all_invoices),
        "total_sales": total_sales,
        "total_due": total_due,
        "total_collected": total_collected,
        "today_sales": today_sales,
        "today_collection": today_collection,
        "today_invoices": len(today_invoices),
        "due_customers": due_customers[:10],
        "recent_invoices": recent_invoices,
        "low_stock_products": low_stock_products,
        "chart": {
            "labels": chart_labels,
            "sales": chart_sales,
            "collection": chart_collection
        }
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

        #particles-js {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }

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

        .glass {
            background: rgba(22, 22, 31, 0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
        }

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

        .count-up {
            display: inline-block;
        }

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
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
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
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            box-shadow: none;
        }

        .btn-success {
            background: linear-gradient(135deg, #10B981 0%, #34D399 100%);
        }

        .btn-danger {
            background: linear-gradient(135deg, #EF4444 0%, #F87171 100%);
        }

        .btn-purple {
            background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);
        }

        .btn-sm {
            padding: 8px 16px;
            font-size: 13px;
        }

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
        }

        .btn-print-sm {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
        }

        .btn-print-sm:hover {
            background: var(--accent-green);
            color: white;
            transform: scale(1.1);
        }

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

        .welcome-modal {
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
            z-index: 5000;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .modal-content {
            background: var(--gradient-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            width: 100%;
            max-width: 600px;
            max-height: 90vh;
            overflow-y: auto;
            animation: modalSlideIn 0.3s ease-out;
        }

        @keyframes modalSlideIn {
            from { opacity: 0; transform: scale(0.9) translateY(-20px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }

        .modal-header {
            padding: 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
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
            padding: 0;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            transition: var(--transition-smooth);
        }

        .modal-close:hover {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            transform: none;
            box-shadow: none;
        }

        .modal-body {
            padding: 24px;
        }

        .modal-footer {
            padding: 20px 24px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }

        /* Grid System */
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

        /* Amount Display */
        .amount {
            font-family: 'Inter', monospace;
            font-weight: 700;
        }

        .amount-green { color: var(--accent-green); }
        .amount-red { color: var(--accent-red); }
        .amount-orange { color: var(--accent-orange); }

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
        }

        .empty-state h3 {
            color: white;
            font-size: 18px;
            margin-bottom: 10px;
        }

        .empty-state p {
            font-size: 14px;
        }

        /* Search Box */
        .search-box {
            position: relative;
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

        /* Filter Bar */
        .filter-bar {
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
            flex-wrap: wrap;
            align-items: center;
        }

        .filter-bar .search-box {
            flex: 1;
            min-width: 250px;
        }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 25px;
            background: rgba(255, 255, 255, 0.03);
            padding: 5px;
            border-radius: 12px;
            width: fit-content;
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
            color: white;
            transform: none;
            box-shadow: none;
        }

        .tab-btn.active {
            background: var(--gradient-orange);
            color: white;
        }

        /* Invoice Items Table */
        .items-table {
            width: 100%;
            border-collapse: collapse;
        }

        .items-table th {
            background: rgba(255, 255, 255, 0.05);
            padding: 12px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-secondary);
        }

        .items-table td {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .items-table input {
            padding: 10px;
            font-size: 14px;
        }

        .items-table .remove-row {
            background: rgba(239, 68, 68, 0.15);
            color: #F87171;
            border: none;
            width: 35px;
            height: 35px;
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
        }

        .items-table .remove-row:hover {
            background: var(--accent-red);
            color: white;
        }

        /* Invoice Summary */
        .invoice-summary {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }

        .summary-row:last-child {
            border-bottom: none;
            font-size: 18px;
            font-weight: 800;
            color: var(--accent-orange);
        }

        .summary-row span:first-child {
            color: var(--text-secondary);
        }

        /* Quick Stats */
        .quick-stat {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }

        .quick-stat-value {
            font-size: 28px;
            font-weight: 800;
            margin-bottom: 5px;
        }

        .quick-stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* Due Badge */
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

        /* Chart Container */
        .chart-container {
            position: relative;
            height: 300px;
            padding: 10px;
        }
    </style>
"""

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান ও হিস্ট্রি (MongoDB ব্যবহার করে) - ORIGINAL
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

def get_dashboard_summary_v2():
    stats_data = load_stats()
    acc_db = load_accessories_db()
    users_data = load_users()
    
    now = get_bd_time()
    today_str = now.strftime('%d-%m-%Y')
    
    user_details = []
    for u, d in users_data.items():
        user_details.append({
            "username": u,
            "role": d.get('role', 'user'),
            "created_at": d.get('created_at', 'N/A'),
            "last_login": d.get('last_login', 'Never'),
            "last_duration": d.get('last_duration', 'N/A')
        })

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
# STORE TEMPLATES
# ==============================================================================

# Store Dashboard Template
STORE_DASHBOARD_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>

    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Aluminum<span>Shop</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link active">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/store/products" class="nav-link">
                <i class="fas fa-boxes"></i> Products
            </a>
            <a href="/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice-dollar"></i> Invoices
            </a>
            <a href="/store/quotations" class="nav-link">
                <i class="fas fa-file-alt"></i> Quotations
            </a>
            <a href="/store/dues" class="nav-link">
                <i class="fas fa-hand-holding-usd"></i> Due Collection
                {{% if stats.total_due > 0 %}}
                <span class="nav-badge" style="background: var(--accent-red);">৳{{{{ "%.0f"|format(stats.total_due) }}}}</span>
                {{% endif %}}
            </a>
            <a href="/store/payments" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Payments
            </a>
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link" style="margin-top: 20px;">
                <i class="fas fa-arrow-left"></i> Main Dashboard
            </a>
            {{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);">
                <i class="fas fa-sign-out-alt"></i> Sign Out
            </a>
        </div>
        <div class="sidebar-footer">
            <i class="fas fa-code"></i> Powered by Mehedi Hasan
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Store Dashboard</div>
                <div class="page-subtitle">Aluminum Shop Management System</div>
            </div>
            <div style="display: flex; gap: 10px;">
                <a href="/store/invoices/new" class="btn btn-success">
                    <i class="fas fa-plus"></i> New Invoice
                </a>
                <a href="/store/quotations/new" class="btn btn-purple">
                    <i class="fas fa-file-alt"></i> New Quotation
                </a>
            </div>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{{{ messages[0] }}}}</span>
                </div>
            {{% endif %}}
        {{% endwith %}}

        <!-- Stats Cards -->
        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{{{ "%.0f"|format(stats.today_sales) }}}}</h3>
                    <p>Today's Sales</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-money-bill-wave" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{{{ "%.0f"|format(stats.today_collection) }}}}</h3>
                    <p>Today's Collection</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));">
                    <i class="fas fa-exclamation-triangle" style="color: var(--accent-red);"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{{{ "%.0f"|format(stats.total_due) }}}}</h3>
                    <p>Total Due</p>
                </div>
            </div>
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                    <i class="fas fa-users" style="color: var(--accent-purple);"></i>
                </div>
                <div class="stat-info">
                    <h3>{{{{ stats.total_customers }}}}</h3>
                    <p>Total Customers</p>
                </div>
            </div>
        </div>

        <!-- Quick Stats Row -->
        <div class="grid-4" style="margin-bottom: 25px;">
            <div class="quick-stat">
                <div class="quick-stat-value amount-green">৳{{{{ "%.0f"|format(stats.total_sales) }}}}</div>
                <div class="quick-stat-label">Total Sales</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value amount-orange">৳{{{{ "%.0f"|format(stats.total_collected) }}}}</div>
                <div class="quick-stat-label">Total Collected</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{{{{ stats.total_invoices }}}}</div>
                <div class="quick-stat-label">Total Invoices</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{{{{ stats.total_products }}}}</div>
                <div class="quick-stat-label">Products</div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <!-- Sales Chart -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-chart-area" style="margin-right: 10px; color: var(--accent-orange);"></i>Sales Overview</span>
                </div>
                <div class="chart-container">
                    <canvas id="salesChart"></canvas>
                </div>
            </div>

            <!-- Due Customers -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-user-clock" style="margin-right: 10px; color: var(--accent-red);"></i>Due Customers</span>
                    <a href="/store/dues" class="btn btn-sm btn-secondary">View All</a>
                </div>
                <div style="max-height: 280px; overflow-y: auto;">
                    {{% if stats.due_customers %}}
                        {{% for customer in stats.due_customers[:5] %}}
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(255,255,255,0.02); border-radius: 10px; margin-bottom: 8px;">
                            <div>
                                <div style="font-weight: 600; color: white;">{{{{ customer.name }}}}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">{{{{ customer.phone }}}}</div>
                            </div>
                            <div class="due-badge">৳{{{{ "%.0f"|format(customer.total_due) }}}}</div>
                        </div>
                        {{% endfor %}}
                    {{% else %}}
                        <div class="empty-state" style="padding: 40px;">
                            <i class="fas fa-check-circle" style="color: var(--accent-green);"></i>
                            <p>No pending dues! </p>
                        </div>
                    {{% endif %}}
                </div>
            </div>
        </div>

        <!-- Recent Invoices -->
        <div class="card" style="margin-top: 25px;">
            <div class="section-header">
                <span><i class="fas fa-file-invoice" style="margin-right: 10px; color: var(--accent-orange);"></i>Recent Invoices</span>
                <a href="/store/invoices" class="btn btn-sm btn-secondary">View All</a>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in stats.recent_invoices[:10] %}}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-orange);">{{{{ inv.invoice_no }}}}</td>
                            <td>{{{{ inv.customer_name }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(inv.total) }}}}</td>
                            <td class="amount amount-green">৳{{{{ "%.0f"|format(inv.paid) }}}}</td>
                            <td class="amount amount-red">৳{{{{ "%.0f"|format(inv.due) }}}}</td>
                            <td>
                                {{% if inv.status == 'paid' %}}
                                <span class="paid-badge">Paid</span>
                                {{% else %}}
                                <span class="due-badge">Due</span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                                    <a href="/store/invoices/print/{{{{ inv.invoice_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="7" class="empty-state">
                                <i class="fas fa-file-invoice"></i>
                                <p>No invoices yet</p>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        // Sales Chart
        const ctx = document.getElementById('salesChart').getContext('2d');
        const gradientSales = ctx.createLinearGradient(0, 0, 0, 300);
        gradientSales.addColorStop(0, 'rgba(255, 122, 0, 0.5)');
        gradientSales.addColorStop(1, 'rgba(255, 122, 0, 0.0)');
        
        const gradientCollection = ctx.createLinearGradient(0, 0, 0, 300);
        gradientCollection.addColorStop(0, 'rgba(16, 185, 129, 0.5)');
        gradientCollection.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {{{{ stats.chart.labels | tojson }}}},
                datasets: [
                    {{
                        label: 'Sales',
                        data: {{{{ stats.chart.sales | tojson }}}},
                        borderColor: '#FF7A00',
                        backgroundColor: gradientSales,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#FF7A00',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        borderWidth: 3
                    }},
                    {{
                        label: 'Collection',
                        data: {{{{ stats.chart.collection | tojson }}}},
                        borderColor: '#10B981',
                        backgroundColor: gradientCollection,
                        tension: 0.4,
                        fill: true,
                        pointBackgroundColor: '#10B981',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        borderWidth: 3
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{ color: '#8b8b9e', font: {{ size: 11 }}, usePointStyle: true }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#8b8b9e', font: {{ size: 10 }} }}
                    }},
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.03)' }},
                        ticks: {{ color: '#8b8b9e', font: {{ size: 10 }} }},
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

# Customer List Template
STORE_CUSTOMERS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Aluminum<span>Shop</span>
        </div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link active"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>
            {{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code"></i> Powered by Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Customers</div>
                <div class="page-subtitle">Manage your customer database</div>
            </div>
            <button class="btn" onclick="openModal('addCustomerModal')">
                <i class="fas fa-plus"></i> Add Customer
            </button>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="flash-message flash-success">
                    <i class="fas fa-check-circle"></i>
                    <span>{{{{ messages[0] }}}}</span>
                </div>
            {{% endif %}}
        {{% endwith %}}

        <div class="card">
            <div class="filter-bar">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search customers..." onkeyup="filterTable()">
                </div>
            </div>

            <div style="overflow-x: auto;">
                <table class="dark-table" id="customersTable">
                    <thead>
                        <tr>
                            <th>Customer ID</th>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Total Purchase</th>
                            <th>Total Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for c in customers %}}
                        <tr>
                            <td style="font-weight: 600; color: var(--accent-orange);">{{{{ c.customer_id }}}}</td>
                            <td style="font-weight: 600;">{{{{ c.name }}}}</td>
                            <td>{{{{ c.phone }}}}</td>
                            <td style="color: var(--text-secondary);">{{{{ c.address or '-' }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(c.total_purchase or 0) }}}}</td>
                            <td>
                                {{% if c.total_due > 0 %}}
                                <span class="due-badge">৳{{{{ "%.0f"|format(c.total_due) }}}}</span>
                                {{% else %}}
                                <span class="paid-badge">৳0</span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/customers/view/{{{{ c.customer_id }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                                    <button class="action-btn btn-edit" onclick="editCustomer('{{{{ c.customer_id }}}}', '{{{{ c.name }}}}', '{{{{ c.phone }}}}', '{{{{ c.email or '' }}}}', '{{{{ c.address or '' }}}}')"><i class="fas fa-edit"></i></button>
                                    <form action="/store/customers/delete/{{{{ c.customer_id }}}}" method="POST" style="display:inline;" onsubmit="return confirm('Delete this customer?');">
                                        <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="7">
                                <div class="empty-state">
                                    <i class="fas fa-users"></i>
                                    <h3>No customers yet</h3>
                                    <p>Add your first customer to get started</p>
                                </div>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Add Customer Modal -->
    <div class="modal-overlay" id="addCustomerModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title"><i class="fas fa-user-plus" style="margin-right: 10px; color: var(--accent-orange);"></i>Add New Customer</div>
                <button class="modal-close" onclick="closeModal('addCustomerModal')">&times;</button>
            </div>
            <form action="/store/customers/add" method="POST">
                <div class="modal-body">
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Customer Name *</label>
                            <input type="text" name="name" required placeholder="Enter full name">
                        </div>
                        <div class="input-group">
                            <label>Phone Number *</label>
                            <input type="text" name="phone" required placeholder="01XXXXXXXXX">
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Email (Optional)</label>
                        <input type="email" name="email" placeholder="email@example.com">
                    </div>
                    <div class="input-group">
                        <label>Address</label>
                        <textarea name="address" placeholder="Enter full address"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('addCustomerModal')">Cancel</button>
                    <button type="submit" class="btn"><i class="fas fa-save"></i> Save Customer</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Edit Customer Modal -->
    <div class="modal-overlay" id="editCustomerModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title"><i class="fas fa-user-edit" style="margin-right: 10px; color: var(--accent-purple);"></i>Edit Customer</div>
                <button class="modal-close" onclick="closeModal('editCustomerModal')">&times;</button>
            </div>
            <form action="/store/customers/update" method="POST">
                <input type="hidden" name="customer_id" id="edit_customer_id">
                <div class="modal-body">
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Customer Name *</label>
                            <input type="text" name="name" id="edit_name" required>
                        </div>
                        <div class="input-group">
                            <label>Phone Number *</label>
                            <input type="text" name="phone" id="edit_phone" required>
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Email</label>
                        <input type="email" name="email" id="edit_email">
                    </div>
                    <div class="input-group">
                        <label>Address</label>
                        <textarea name="address" id="edit_address"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('editCustomerModal')">Cancel</button>
                    <button type="submit" class="btn btn-purple"><i class="fas fa-sync"></i> Update Customer</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openModal(id) {{
            document.getElementById(id).style.display = 'flex';
        }}
        function closeModal(id) {{
            document.getElementById(id).style.display = 'none';
        }}
        function editCustomer(id, name, phone, email, address) {{
            document.getElementById('edit_customer_id').value = id;
            document.getElementById('edit_name').value = name;
            document.getElementById('edit_phone').value = phone;
            document.getElementById('edit_email').value = email;
            document.getElementById('edit_address').value = address;
            openModal('editCustomerModal');
        }}
        function filterTable() {{
            const input = document.getElementById('searchInput').value.toLowerCase();
            const rows = document.querySelectorAll('#customersTable tbody tr');
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(input) ? '' : 'none';
            }});
        }}
        // Close modal on outside click
        document.querySelectorAll('.modal-overlay').forEach(modal => {{
            modal.addEventListener('click', (e) => {{
                if (e.target === modal) closeModal(modal.id);
            }});
        }});
    </script>
</body>
</html>
"""

# Products Template
STORE_PRODUCTS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link active"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>{{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code"></i> Powered by Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Products</div>
                <div class="page-subtitle">Manage your product inventory</div>
            </div>
            <button class="btn" onclick="openModal('addProductModal')">
                <i class="fas fa-plus"></i> Add Product
            </button>
        </div>

        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}

        <div class="card">
            <div class="filter-bar">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search products..." onkeyup="filterTable()">
                </div>
                <select id="categoryFilter" onchange="filterTable()" style="width: auto; min-width: 150px;">
                    <option value="">All Categories</option>
                    <option value="Profile">Profile</option>
                    <option value="Sheet">Sheet</option>
                    <option value="Glass">Glass</option>
                    <option value="Accessories">Accessories</option>
                    <option value="Hardware">Hardware</option>
                    <option value="Other">Other</option>
                </select>
            </div>

            <div style="overflow-x: auto;">
                <table class="dark-table" id="productsTable">
                    <thead>
                        <tr>
                            <th>Product Name</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th>Buy Price</th>
                            <th>Sell Price</th>
                            <th>Stock</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for p in products %}}
                        <tr data-category="{{{{ p.category }}}}">
                            <td style="font-weight: 600;">{{{{ p.name }}}}</td>
                            <td><span class="table-badge">{{{{ p.category }}}}</span></td>
                            <td>{{{{ p.unit }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(p.buy_price or 0) }}}}</td>
                            <td class="amount amount-green">৳{{{{ "%.0f"|format(p.sell_price or 0) }}}}</td>
                            <td>
                                {{% if p.stock < 10 %}}
                                <span class="due-badge">{{{{ p.stock }}}} {{{{ p.unit }}}}</span>
                                {{% else %}}
                                <span class="paid-badge">{{{{ p.stock }}}} {{{{ p.unit }}}}</span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <button class="action-btn btn-edit" onclick="editProduct('{{{{ p._id }}}}', '{{{{ p.name }}}}', '{{{{ p.category }}}}', '{{{{ p.unit }}}}', '{{{{ p.buy_price }}}}', '{{{{ p.sell_price }}}}', '{{{{ p.stock }}}}', '{{{{ p.description or '' }}}}')"><i class="fas fa-edit"></i></button>
                                    <form action="/store/products/delete/{{{{ p._id }}}}" method="POST" style="display:inline;" onsubmit="return confirm('Delete this product?');">
                                        <button type="submit" class="action-btn btn-del"><i class="fas fa-trash"></i></button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="7"><div class="empty-state"><i class="fas fa-boxes"></i><h3>No products yet</h3><p>Add your first product to get started</p></div></td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Add Product Modal -->
    <div class="modal-overlay" id="addProductModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title"><i class="fas fa-box" style="margin-right: 10px; color: var(--accent-orange);"></i>Add New Product</div>
                <button class="modal-close" onclick="closeModal('addProductModal')">&times;</button>
            </div>
            <form action="/store/products/add" method="POST">
                <div class="modal-body">
                    <div class="input-group">
                        <label>Product Name *</label>
                        <input type="text" name="name" required placeholder="Enter product name">
                    </div>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Category</label>
                            <select name="category">
                                <option value="Profile">Profile</option>
                                <option value="Sheet">Sheet</option>
                                <option value="Glass">Glass</option>
                                <option value="Accessories">Accessories</option>
                                <option value="Hardware">Hardware</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Unit</label>
                            <select name="unit">
                                <option value="pcs">Pieces (pcs)</option>
                                <option value="ft">Feet (ft)</option>
                                <option value="meter">Meter</option>
                                <option value="kg">Kilogram (kg)</option>
                                <option value="sft">Square Feet (sft)</option>
                                <option value="set">Set</option>
                            </select>
                        </div>
                    </div>
                    <div class="grid-3">
                        <div class="input-group">
                            <label>Buy Price (৳)</label>
                            <input type="number" name="buy_price" step="0.01" placeholder="0">
                        </div>
                        <div class="input-group">
                            <label>Sell Price (৳) *</label>
                            <input type="number" name="sell_price" step="0.01" required placeholder="0">
                        </div>
                        <div class="input-group">
                            <label>Initial Stock</label>
                            <input type="number" name="stock" step="0.01" placeholder="0">
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Description</label>
                        <textarea name="description" placeholder="Product description (optional)"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('addProductModal')">Cancel</button>
                    <button type="submit" class="btn"><i class="fas fa-save"></i> Save Product</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Edit Product Modal -->
    <div class="modal-overlay" id="editProductModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title"><i class="fas fa-edit" style="margin-right: 10px; color: var(--accent-purple);"></i>Edit Product</div>
                <button class="modal-close" onclick="closeModal('editProductModal')">&times;</button>
            </div>
            <form action="/store/products/update" method="POST">
                <input type="hidden" name="product_id" id="edit_product_id">
                <div class="modal-body">
                    <div class="input-group">
                        <label>Product Name *</label>
                        <input type="text" name="name" id="ep_name" required>
                    </div>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Category</label>
                            <select name="category" id="ep_category">
                                <option value="Profile">Profile</option>
                                <option value="Sheet">Sheet</option>
                                <option value="Glass">Glass</option>
                                <option value="Accessories">Accessories</option>
                                <option value="Hardware">Hardware</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Unit</label>
                            <select name="unit" id="ep_unit">
                                <option value="pcs">Pieces (pcs)</option>
                                <option value="ft">Feet (ft)</option>
                                <option value="meter">Meter</option>
                                <option value="kg">Kilogram (kg)</option>
                                <option value="sft">Square Feet (sft)</option>
                                <option value="set">Set</option>
                            </select>
                        </div>
                    </div>
                    <div class="grid-3">
                        <div class="input-group">
                            <label>Buy Price (৳)</label>
                            <input type="number" name="buy_price" id="ep_buy_price" step="0.01">
                        </div>
                        <div class="input-group">
                            <label>Sell Price (৳) *</label>
                            <input type="number" name="sell_price" id="ep_sell_price" step="0.01" required>
                        </div>
                        <div class="input-group">
                            <label>Stock</label>
                            <input type="number" name="stock" id="ep_stock" step="0.01">
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Description</label>
                        <textarea name="description" id="ep_description"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('editProductModal')">Cancel</button>
                    <button type="submit" class="btn btn-purple"><i class="fas fa-sync"></i> Update Product</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
        function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
        function editProduct(id, name, category, unit, buy_price, sell_price, stock, description) {{
            document.getElementById('edit_product_id').value = id;
            document.getElementById('ep_name').value = name;
            document.getElementById('ep_category').value = category;
            document.getElementById('ep_unit').value = unit;
            document.getElementById('ep_buy_price').value = buy_price;
            document.getElementById('ep_sell_price').value = sell_price;
            document.getElementById('ep_stock').value = stock;
            document.getElementById('ep_description').value = description;
            openModal('editProductModal');
        }}
        function filterTable() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const category = document.getElementById('categoryFilter').value;
            const rows = document.querySelectorAll('#productsTable tbody tr');
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const rowCat = row.getAttribute('data-category');
                const matchSearch = text.includes(search);
                const matchCat = ! category || rowCat === category;
                row.style.display = (matchSearch && matchCat) ? '' : 'none';
            }});
        }}
        document.querySelectorAll('.modal-overlay').forEach(modal => {{
            modal.addEventListener('click', (e) => {{ if (e.target === modal) closeModal(modal.id); }});
        }});
    </script>
</body>
</html>
"""

# Invoices List Template
STORE_INVOICES_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link active"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>{{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code"></i> Powered by Mehedi Hasan</div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Invoices</div>
                <div class="page-subtitle">Manage sales invoices</div>
            </div>
            <a href="/store/invoices/new" class="btn btn-success">
                <i class="fas fa-plus"></i> New Invoice
            </a>
        </div>

        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}

        <div class="card">
            <div class="filter-bar">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search invoices..." onkeyup="filterTable()">
                </div>
                <select id="statusFilter" onchange="filterTable()" style="width: auto; min-width: 120px;">
                    <option value="">All Status</option>
                    <option value="paid">Paid</option>
                    <option value="due">Due</option>
                </select>
            </div>

            <div style="overflow-x: auto;">
                <table class="dark-table" id="invoicesTable">
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Phone</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in invoices %}}
                        <tr data-status="{{{{ inv.status }}}}">
                            <td style="font-weight: 700; color: var(--accent-orange);">{{{{ inv.invoice_no }}}}</td>
                            <td>{{{{ inv.created_at[:10] if inv.created_at else '-' }}}}</td>
                            <td style="font-weight: 600;">{{{{ inv.customer_name }}}}</td>
                            <td>{{{{ inv.customer_phone }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(inv.total or 0) }}}}</td>
                            <td class="amount amount-green">৳{{{{ "%.0f"|format(inv.paid or 0) }}}}</td>
                            <td class="amount amount-red">৳{{{{ "%.0f"|format(inv.due or 0) }}}}</td>
                            <td>
                                {{% if inv.status == 'paid' %}}<span class="paid-badge">Paid</span>{{% else %}}<span class="due-badge">Due</span>{{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                                    <a href="/store/invoices/print/{{{{ inv.invoice_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                    <a href="/store/invoices/edit/{{{{ inv.invoice_no }}}}" class="action-btn btn-edit"><i class="fas fa-edit"></i></a>
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="9"><div class="empty-state"><i class="fas fa-file-invoice"></i><h3>No invoices yet</h3><p>Create your first invoice</p></div></td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterTable() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const status = document.getElementById('statusFilter').value;
            const rows = document.querySelectorAll('#invoicesTable tbody tr');
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const rowStatus = row.getAttribute('data-status');
                const matchSearch = text.includes(search);
                const matchStatus = ! status || rowStatus === status;
                row.style.display = (matchSearch && matchStatus) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

# Create Invoice Template
STORE_CREATE_INVOICE_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Invoice - Aluminum Shop</title>
    {COMMON_STYLES}
    <style>
        .product-select {{ min-width: 200px; }}
        .qty-input {{ width: 80px ! important; }}
        .price-input {{ width: 100px !important; }}
        .total-input {{ width: 120px !important; background: rgba(16, 185, 129, 0.1) !important; }}
    </style>
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link active"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create New Invoice</div>
                <div class="page-subtitle">Generate sales invoice</div>
            </div>
            <a href="/store/invoices" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Back</a>
        </div>

        <form action="/store/invoices/save" method="POST" id="invoiceForm">
            <div class="grid-2" style="margin-bottom: 25px;">
                <!-- Customer Info -->
                <div class="card">
                    <div class="section-header"><span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span></div>
                    <div class="input-group">
                        <label>Select Customer</label>
                        <select name="customer_id" id="customerSelect" onchange="fillCustomerInfo()">
                            <option value="">-- Walk-in Customer --</option>
                            {{% for c in customers %}}
                            <option value="{{{{ c.customer_id }}}}" data-name="{{{{ c.name }}}}" data-phone="{{{{ c.phone }}}}" data-address="{{{{ c.address or '' }}}}">{{{{ c.name }}}} ({{{{ c.phone }}}})</option>
                            {{% endfor %}}
                        </select>
                    </div>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Customer Name *</label>
                            <input type="text" name="customer_name" id="customerName" required placeholder="Enter name">
                        </div>
                        <div class="input-group">
                            <label>Phone *</label>
                            <input type="text" name="customer_phone" id="customerPhone" required placeholder="01XXXXXXXXX">
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Address</label>
                        <input type="text" name="customer_address" id="customerAddress" placeholder="Address">
                    </div>
                </div>

                <!-- Payment Info -->
                <div class="card">
                    <div class="section-header"><span><i class="fas fa-money-bill-wave" style="margin-right: 10px; color: var(--accent-green);"></i>Payment Details</span></div>
                    <div class="invoice-summary">
                        <div class="summary-row">
                            <span>Subtotal</span>
                            <span id="subtotalDisplay">৳0</span>
                        </div>
                        <div class="summary-row">
                            <span>Discount</span>
                            <input type="number" name="discount" id="discountInput" value="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotal()">
                        </div>
                        <div class="summary-row">
                            <span>Grand Total</span>
                            <span id="grandTotalDisplay" style="font-size: 24px;">৳0</span>
                        </div>
                        <div class="summary-row">
                            <span>Paid Amount</span>
                            <input type="number" name="paid" id="paidInput" value="0" step="0.01" style="width: 120px; text-align: right;" onchange="calculateTotal()">
                        </div>
                        <div class="summary-row" style="color: var(--accent-red);">
                            <span>Due Amount</span>
                            <span id="dueDisplay">৳0</span>
                        </div>
                    </div>
                    <div class="input-group" style="margin-top: 15px;">
                        <label>Payment Method</label>
                        <select name="payment_method">
                            <option value="Cash">Cash</option>
                            <option value="bKash">bKash</option>
                            <option value="Nagad">Nagad</option>
                            <option value="Bank">Bank Transfer</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Items Table -->
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Items</span>
                    <button type="button" class="btn btn-sm" onclick="addRow()"><i class="fas fa-plus"></i> Add Item</button>
                </div>
                <div style="overflow-x: auto;">
                    <table class="items-table" id="itemsTable">
                        <thead>
                            <tr>
                                <th>Product</th>
                                <th>Description</th>
                                <th>Qty</th>
                                <th>Unit</th>
                                <th>Price</th>
                                <th>Total</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody id="itemsBody">
                            <tr>
                                <td>
                                    <select name="product_id[]" class="product-select" onchange="productSelected(this)">
                                        <option value="">Select Product</option>
                                        {{% for p in products %}}
                                        <option value="{{{{ p._id }}}}" data-price="{{{{ p.sell_price }}}}" data-unit="{{{{ p.unit }}}}">{{{{ p.name }}}}</option>
                                        {{% endfor %}}
                                    </select>
                                </td>
                                <td><input type="text" name="description[]" placeholder="Description"></td>
                                <td><input type="number" name="qty[]" class="qty-input" step="0.01" value="1" onchange="calculateRow(this)"></td>
                                <td><input type="text" name="unit[]" class="qty-input" value="pcs" readonly></td>
                                <td><input type="number" name="price[]" class="price-input" step="0.01" value="0" onchange="calculateRow(this)"></td>
                                <td><input type="number" name="total[]" class="total-input" value="0" readonly></td>
                                <td><button type="button" class="remove-row" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Notes -->
            <div class="card" style="margin-top: 25px;">
                <div class="input-group" style="margin-bottom: 0;">
                    <label>Notes (Optional)</label>
                    <textarea name="notes" placeholder="Additional notes for this invoice..."></textarea>
                </div>
            </div>

            <div style="margin-top: 25px; display: flex; gap: 15px; justify-content: flex-end;">
                <a href="/store/invoices" class="btn btn-secondary">Cancel</a>
                <button type="submit" class="btn btn-success"><i class="fas fa-save"></i> Save Invoice</button>
            </div>
        </form>
    </div>

    <script>
        const productsData = {{{{ products | tojson }}}};

        function fillCustomerInfo() {{
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            if (option.value) {{
                document.getElementById('customerName').value = option.dataset.name;
                document.getElementById('customerPhone').value = option.dataset.phone;
                document.getElementById('customerAddress').value = option.dataset.address;
            }}
        }}

        function productSelected(select) {{
            const row = select.closest('tr');
            const option = select.options[select.selectedIndex];
            if (option.value) {{
                row.querySelector('input[name="price[]"]').value = option.dataset.price || 0;
                row.querySelector('input[name="unit[]"]').value = option.dataset.unit || 'pcs';
                calculateRow(select);
            }}
        }}

        function calculateRow(el) {{
            const row = el.closest('tr');
            const qty = parseFloat(row.querySelector('input[name="qty[]"]').value) || 0;
            const price = parseFloat(row.querySelector('input[name="price[]"]').value) || 0;
            row.querySelector('input[name="total[]"]').value = (qty * price).toFixed(2);
            calculateTotal();
        }}

        function calculateTotal() {{
            let subtotal = 0;
            document.querySelectorAll('input[name="total[]"]').forEach(input => {{
                subtotal += parseFloat(input.value) || 0;
            }});
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            const grandTotal = subtotal - discount;
            const paid = parseFloat(document.getElementById('paidInput').value) || 0;
            const due = grandTotal - paid;

            document.getElementById('subtotalDisplay').textContent = '৳' + subtotal.toFixed(0);
            document.getElementById('grandTotalDisplay').textContent = '৳' + grandTotal.toFixed(0);
            document.getElementById('dueDisplay').textContent = '৳' + due.toFixed(0);
        }}

        function addRow() {{
            const tbody = document.getElementById('itemsBody');
            const newRow = tbody.rows[0].cloneNode(true);
            newRow.querySelectorAll('input').forEach(input => {{
                if (input.name === 'qty[]') input.value = '1';
                else if (input.name === 'unit[]') input.value = 'pcs';
                else input.value = '';
            }});
            newRow.querySelector('select').selectedIndex = 0;
            tbody.appendChild(newRow);
        }}

        function removeRow(btn) {{
            const tbody = document.getElementById('itemsBody');
            if (tbody.rows.length > 1) {{
                btn.closest('tr').remove();
                calculateTotal();
            }}
        }}
    </script>
</body>
</html>
"""

# Invoice View/Print Template
STORE_INVOICE_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ invoice.invoice_no }} - Aluminum Shop</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: #f5f5f5; padding: 20px; }
        .invoice-container { max-width: 800px; margin: 0 auto; background: white; border: 1px solid #ddd; }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; display: flex; justify-content: space-between; align-items: center; }
        .company-info h1 { font-size: 28px; font-weight: 800; margin-bottom: 5px; }
        .company-info p { font-size: 12px; opacity: 0.9; }
        .invoice-title { text-align: right; }
        .invoice-title h2 { font-size: 36px; font-weight: 800
        # Invoice View Template (Continued) + More Templates + All Routes

# Invoice View/Print Template (Complete)
STORE_INVOICE_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Invoice {{ invoice.invoice_no }} - Aluminum Shop</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: #f5f5f5; padding: 20px; }
        .invoice-container { max-width: 800px; margin: 0 auto; background: white; border: 1px solid #ddd; box-shadow: 0 5px 30px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; display: flex; justify-content: space-between; align-items: center; }
        .company-info h1 { font-size: 28px; font-weight: 800; margin-bottom: 5px; }
        .company-info p { font-size: 12px; opacity: 0.9; }
        .invoice-title { text-align: right; }
        .invoice-title h2 { font-size: 36px; font-weight: 800; color: #FF7A00; }
        .invoice-title p { font-size: 14px; opacity: 0.9; }
        .info-section { display: flex; justify-content: space-between; padding: 25px 30px; border-bottom: 1px solid #eee; }
        .info-box h4 { font-size: 11px; text-transform: uppercase; color: #888; letter-spacing: 1px; margin-bottom: 8px; }
        .info-box p { font-size: 14px; color: #333; font-weight: 500; line-height: 1.6; }
        .info-box .highlight { font-size: 18px; font-weight: 700; color: #1a1a2e; }
        .items-section { padding: 0 30px 30px; }
        .items-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .items-table th { background: #f8f9fa; padding: 12px; text-align: left; font-size: 11px; text-transform: uppercase; color: #666; letter-spacing: 1px; border-bottom: 2px solid #1a1a2e; }
        .items-table td { padding: 15px 12px; border-bottom: 1px solid #eee; font-size: 14px; }
        .items-table .item-name { font-weight: 600; color: #333; }
        .items-table .text-right { text-align: right; }
        .items-table .amount { font-weight: 600; font-family: monospace; font-size: 15px; }
        .summary-section { background: #f8f9fa; padding: 25px 30px; }
        .summary-row { display: flex; justify-content: flex-end; margin-bottom: 8px; }
        .summary-row span { min-width: 150px; }
        .summary-row .label { color: #666; text-align: right; padding-right: 20px; }
        .summary-row .value { font-weight: 600; text-align: right; font-family: monospace; }
        .summary-row.total { font-size: 20px; color: #1a1a2e; border-top: 2px solid #1a1a2e; padding-top: 15px; margin-top: 10px; }
        .summary-row.due .value { color: #e74c3c; }
        .summary-row.paid .value { color: #27ae60; }
        .footer { padding: 25px 30px; text-align: center; border-top: 1px solid #eee; }
        .footer p { font-size: 12px; color: #888; }
        .status-badge { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
        .status-paid { background: #d4edda; color: #155724; }
        .status-due { background: #f8d7da; color: #721c24; }
        .no-print { margin-bottom: 20px; text-align: center; }
        .btn { padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer; font-weight: 600; margin: 0 5px; text-decoration: none; display: inline-block; }
        .btn-print { background: #1a1a2e; color: white; }
        .btn-back { background: #6c757d; color: white; }
        @media print {
            body { padding: 0; background: white; }
            .no-print { display: none; }
            .invoice-container { box-shadow: none; border: none; }
        }
    </style>
</head>
<body>
    <div class="no-print">
        <a href="/store/invoices" class="btn btn-back">← Back to Invoices</a>
        <button onclick="window.print()" class="btn btn-print">🖨️ Print Invoice</button>
        {% if invoice.status == 'due' %}
        <a href="/store/dues/collect/{{ invoice.invoice_no }}" class="btn" style="background: #27ae60; color: white;">💰 Collect Due</a>
        {% endif %}
    </div>

    <div class="invoice-container">
        <div class="header">
            <div class="company-info">
                <h1>ALUMINUM SHOP</h1>
                <p>Quality Aluminum Products & Services</p>
                <p>📍 Your Address Here, City</p>
                <p>📞 01XXXXXXXXX</p>
            </div>
            <div class="invoice-title">
                <h2>INVOICE</h2>
                <p>{{ invoice.invoice_no }}</p>
                <p style="margin-top: 10px;">
                    {% if invoice.status == 'paid' %}
                    <span class="status-badge status-paid">PAID</span>
                    {% else %}
                    <span class="status-badge status-due">DUE</span>
                    {% endif %}
                </p>
            </div>
        </div>

        <div class="info-section">
            <div class="info-box">
                <h4>Bill To</h4>
                <p class="highlight">{{ invoice.customer_name }}</p>
                <p>📞 {{ invoice.customer_phone }}</p>
                {% if invoice.customer_address %}
                <p>📍 {{ invoice.customer_address }}</p>
                {% endif %}
            </div>
            <div class="info-box" style="text-align: right;">
                <h4>Invoice Details</h4>
                <p><strong>Date:</strong> {{ invoice.created_at[:10] if invoice.created_at else 'N/A' }}</p>
                <p><strong>Invoice No:</strong> {{ invoice.invoice_no }}</p>
                {% if invoice.customer_id %}
                <p><strong>Customer ID:</strong> {{ invoice.customer_id }}</p>
                {% endif %}
            </div>
        </div>

        <div class="items-section">
            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 5%;">#</th>
                        <th style="width: 35%;">Item Description</th>
                        <th class="text-right" style="width: 15%;">Qty</th>
                        <th class="text-right" style="width: 10%;">Unit</th>
                        <th class="text-right" style="width: 17%;">Price</th>
                        <th class="text-right" style="width: 18%;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in invoice.items %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td class="item-name">{{ item.description or item.product_name or 'Product' }}</td>
                        <td class="text-right">{{ item.qty }}</td>
                        <td class="text-right">{{ item.unit or 'pcs' }}</td>
                        <td class="text-right amount">৳{{ "%.0f"|format(item.price|float) }}</td>
                        <td class="text-right amount">৳{{ "%.0f"|format(item.total|float) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="summary-section">
            <div class="summary-row">
                <span class="label">Subtotal:</span>
                <span class="value">৳{{ "%.0f"|format(invoice.subtotal) }}</span>
            </div>
            {% if invoice.discount > 0 %}
            <div class="summary-row">
                <span class="label">Discount:</span>
                <span class="value">- ৳{{ "%.0f"|format(invoice.discount) }}</span>
            </div>
            {% endif %}
            <div class="summary-row total">
                <span class="label">Grand Total:</span>
                <span class="value">৳{{ "%.0f"|format(invoice.total) }}</span>
            </div>
            <div class="summary-row paid">
                <span class="label">Paid Amount:</span>
                <span class="value">৳{{ "%.0f"|format(invoice.paid) }}</span>
            </div>
            <div class="summary-row due">
                <span class="label">Due Amount:</span>
                <span class="value">৳{{ "%.0f"|format(invoice.due) }}</span>
            </div>
        </div>

        <div class="footer">
            {% if invoice.notes %}
            <p style="margin-bottom: 15px; color: #333;"><strong>Notes:</strong> {{ invoice.notes }}</p>
            {% endif %}
            <p>Thank you for your business! </p>
            <p style="margin-top: 10px;">Generated by Aluminum Shop Management System</p>
        </div>
    </div>
</body>
</html>
"""

# Due Collection Template
STORE_DUES_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due Collection - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link active"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>{{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Due Collection</div>
                <div class="page-subtitle">Manage and collect pending dues</div>
            </div>
            <div class="quick-stat" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2);">
                <div class="quick-stat-value amount-red">৳{{{{ "%.0f"|format(total_due) }}}}</div>
                <div class="quick-stat-label">Total Pending</div>
            </div>
        </div>

        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}

        <div class="card">
            <div class="section-header">
                <span><i class="fas fa-file-invoice-dollar" style="margin-right: 10px; color: var(--accent-red);"></i>Invoices with Due</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Phone</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in due_invoices %}}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-orange);">{{{{ inv.invoice_no }}}}</td>
                            <td style="font-weight: 600;">{{{{ inv.customer_name }}}}</td>
                            <td>{{{{ inv.customer_phone }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(inv.total) }}}}</td>
                            <td class="amount amount-green">৳{{{{ "%.0f"|format(inv.paid) }}}}</td>
                            <td><span class="due-badge">৳{{{{ "%.0f"|format(inv.due) }}}}</span></td>
                            <td>
                                <div class="action-cell">
                                    <button class="action-btn btn-view" onclick="openCollectModal('{{{{ inv.invoice_no }}}}', '{{{{ inv.customer_name }}}}', {{{{ inv.due }}}})"><i class="fas fa-hand-holding-usd"></i></button>
                                    <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-print-sm"><i class="fas fa-eye"></i></a>
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="7"><div class="empty-state"><i class="fas fa-check-circle" style="color: var(--accent-green);"></i><h3>No pending dues! </h3><p>All invoices are paid</p></div></td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Collect Due Modal -->
    <div class="modal-overlay" id="collectModal">
        <div class="modal-content" style="max-width: 450px;">
            <div class="modal-header">
                <div class="modal-title"><i class="fas fa-money-bill-wave" style="margin-right: 10px; color: var(--accent-green);"></i>Collect Payment</div>
                <button class="modal-close" onclick="closeModal('collectModal')">&times;</button>
            </div>
            <form action="/store/dues/collect" method="POST">
                <input type="hidden" name="invoice_no" id="collect_invoice_no">
                <div class="modal-body">
                    <div style="background: rgba(255,255,255,0.03); padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                        <p style="color: var(--text-secondary); margin-bottom: 5px;">Customer</p>
                        <p style="font-size: 18px; font-weight: 700;" id="collect_customer_name"></p>
                    </div>
                    <div class="grid-2">
                        <div class="quick-stat">
                            <div class="quick-stat-value amount-red" id="collect_due_display">৳0</div>
                            <div class="quick-stat-label">Due Amount</div>
                        </div>
                        <div class="input-group" style="margin-bottom: 0;">
                            <label>Collect Amount *</label>
                            <input type="number" name="amount" id="collect_amount" required step="0.01" placeholder="Enter amount">
                        </div>
                    </div>
                    <div class="input-group" style="margin-top: 20px;">
                        <label>Payment Method</label>
                        <select name="payment_method">
                            <option value="Cash">Cash</option>
                            <option value="bKash">bKash</option>
                            <option value="Nagad">Nagad</option>
                            <option value="Bank">Bank Transfer</option>
                        </select>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('collectModal')">Cancel</button>
                    <button type="submit" class="btn btn-success"><i class="fas fa-check"></i> Collect Payment</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openModal(id) {{ document.getElementById(id).style.display = 'flex'; }}
        function closeModal(id) {{ document.getElementById(id).style.display = 'none'; }}
        function openCollectModal(invoiceNo, customerName, dueAmount) {{
            document.getElementById('collect_invoice_no').value = invoiceNo;
            document.getElementById('collect_customer_name').textContent = customerName;
            document.getElementById('collect_due_display').textContent = '৳' + dueAmount.toFixed(0);
            document.getElementById('collect_amount').value = dueAmount;
            document.getElementById('collect_amount').max = dueAmount;
            openModal('collectModal');
        }}
        document.querySelectorAll('.modal-overlay').forEach(modal => {{
            modal.addEventListener('click', (e) => {{ if (e.target === modal) closeModal(modal.id); }});
        }});
    </script>
</body>
</html>
"""

# Quotations Template
STORE_QUOTATIONS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Quotations - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link active"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>{{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Quotations</div>
                <div class="page-subtitle">Manage estimates and quotations</div>
            </div>
            <a href="/store/quotations/new" class="btn btn-purple"><i class="fas fa-plus"></i> New Quotation</a>
        </div>

        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}

        <div class="card">
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Quotation No</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Phone</th>
                            <th>Total</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for q in quotations %}}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-purple);">{{{{ q.quotation_no }}}}</td>
                            <td>{{{{ q.created_at[:10] if q.created_at else '-' }}}}</td>
                            <td style="font-weight: 600;">{{{{ q.customer_name }}}}</td>
                            <td>{{{{ q.customer_phone }}}}</td>
                            <td class="amount">৳{{{{ "%.0f"|format(q.total or 0) }}}}</td>
                            <td>
                                {{% if q.status == 'converted' %}}
                                <span class="paid-badge">Converted</span>
                                {{% else %}}
                                <span class="table-badge" style="background: rgba(139, 92, 246, 0.15); color: #A78BFA;">Pending</span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/store/quotations/view/{{{{ q.quotation_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                                    <a href="/store/quotations/print/{{{{ q.quotation_no }}}}" class="action-btn btn-print-sm" target="_blank"><i class="fas fa-print"></i></a>
                                    {{% if q.status != 'converted' %}}
                                    <a href="/store/quotations/convert/{{{{ q.quotation_no }}}}" class="action-btn btn-edit" title="Convert to Invoice"><i class="fas fa-exchange-alt"></i></a>
                                    {{% endif %}}
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="7"><div class="empty-state"><i class="fas fa-file-alt"></i><h3>No quotations yet</h3><p>Create your first quotation</p></div></td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""

# Create Quotation Template  
STORE_CREATE_QUOTATION_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>New Quotation - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/quotations" class="nav-link active"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Create Quotation</div>
                <div class="page-subtitle">Generate estimate for customer</div>
            </div>
            <a href="/store/quotations" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Back</a>
        </div>

        <form action="/store/quotations/save" method="POST">
            <div class="grid-2" style="margin-bottom: 25px;">
                <div class="card">
                    <div class="section-header"><span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Information</span></div>
                    <div class="grid-2">
                        <div class="input-group">
                            <label>Customer Name *</label>
                            <input type="text" name="customer_name" required placeholder="Enter name">
                        </div>
                        <div class="input-group">
                            <label>Phone *</label>
                            <input type="text" name="customer_phone" required placeholder="01XXXXXXXXX">
                        </div>
                    </div>
                    <div class="input-group">
                        <label>Address</label>
                        <input type="text" name="customer_address" placeholder="Address">
                    </div>
                </div>
                <div class="card">
                    <div class="section-header"><span><i class="fas fa-cog" style="margin-right: 10px; color: var(--accent-orange);"></i>Quotation Settings</span></div>
                    <div class="input-group">
                        <label>Validity</label>
                        <select name="validity">
                            <option value="7 days">7 Days</option>
                            <option value="15 days">15 Days</option>
                            <option value="30 days">30 Days</option>
                        </select>
                    </div>
                    <div class="invoice-summary" style="margin-top: 15px;">
                        <div class="summary-row">
                            <span>Subtotal</span>
                            <span id="subtotalDisplay">৳0</span>
                        </div>
                        <div class="summary-row">
                            <span>Discount</span>
                            <input type="number" name="discount" id="discountInput" value="0" style="width: 100px; text-align: right;" onchange="calculateTotal()">
                        </div>
                        <div class="summary-row">
                            <span>Grand Total</span>
                            <span id="grandTotalDisplay" style="font-size: 20px;">৳0</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-green);"></i>Quotation Items</span>
                    <button type="button" class="btn btn-sm" onclick="addRow()"><i class="fas fa-plus"></i> Add Item</button>
                </div>
                <table class="items-table" id="itemsTable">
                    <thead>
                        <tr>
                            <th>Product/Description</th>
                            <th>Qty</th>
                            <th>Unit</th>
                            <th>Price</th>
                            <th>Total</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody id="itemsBody">
                        <tr>
                            <td><input type="text" name="description[]" placeholder="Item description" required></td>
                            <td><input type="number" name="qty[]" value="1" step="0.01" style="width: 80px;" onchange="calculateRow(this)"></td>
                            <td><input type="text" name="unit[]" value="pcs" style="width: 70px;"></td>
                            <td><input type="number" name="price[]" value="0" step="0.01" style="width: 100px;" onchange="calculateRow(this)"></td>
                            <td><input type="number" name="total[]" value="0" readonly style="width: 120px; background: rgba(16,185,129,0.1);"></td>
                            <td><button type="button" class="remove-row" onclick="removeRow(this)"><i class="fas fa-times"></i></button></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card" style="margin-top: 25px;">
                <div class="input-group" style="margin-bottom: 0;">
                    <label>Notes</label>
                    <textarea name="notes" placeholder="Terms and conditions, additional notes..."></textarea>
                </div>
            </div>

            <div style="margin-top: 25px; display: flex; gap: 15px; justify-content: flex-end;">
                <a href="/store/quotations" class="btn btn-secondary">Cancel</a>
                <button type="submit" class="btn btn-purple"><i class="fas fa-save"></i> Save Quotation</button>
            </div>
        </form>
    </div>

    <script>
        function calculateRow(el) {{
            const row = el.closest('tr');
            const qty = parseFloat(row.querySelector('input[name="qty[]"]').value) || 0;
            const price = parseFloat(row.querySelector('input[name="price[]"]').value) || 0;
            row.querySelector('input[name="total[]"]').value = (qty * price).toFixed(2);
            calculateTotal();
        }}
        function calculateTotal() {{
            let subtotal = 0;
            document.querySelectorAll('input[name="total[]"]').forEach(input => {{ subtotal += parseFloat(input.value) || 0; }});
            const discount = parseFloat(document.getElementById('discountInput').value) || 0;
            document.getElementById('subtotalDisplay').textContent = '৳' + subtotal.toFixed(0);
            document.getElementById('grandTotalDisplay').textContent = '৳' + (subtotal - discount).toFixed(0);
        }}
        function addRow() {{
            const tbody = document.getElementById('itemsBody');
            const newRow = tbody.rows[0].cloneNode(true);
            newRow.querySelectorAll('input').forEach(input => {{
                if (input.name === 'qty[]') input.value = '1';
                else if (input.name === 'unit[]') input.value = 'pcs';
                else input.value = '';
            }});
            tbody.appendChild(newRow);
        }}
        function removeRow(btn) {{
            const tbody = document.getElementById('itemsBody');
            if (tbody.rows.length > 1) {{ btn.closest('tr').remove(); calculateTotal(); }}
        }}
    </script>
</body>
</html>
"""

# Quotation View/Print Template
STORE_QUOTATION_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Quotation {{ quotation.quotation_no }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Poppins', sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; border: 1px solid #ddd; box-shadow: 0 5px 30px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); color: white; padding: 30px; display: flex; justify-content: space-between; }
        .company-info h1 { font-size: 28px; font-weight: 800; }
        .company-info p { font-size: 12px; opacity: 0.9; }
        .quote-title h2 { font-size: 32px; font-weight: 800; }
        .quote-title p { opacity: 0.9; }
        .info-section { display: flex; justify-content: space-between; padding: 25px 30px; border-bottom: 1px solid #eee; }
        .info-box h4 { font-size: 11px; text-transform: uppercase; color: #888; margin-bottom: 8px; }
        .info-box p { font-size: 14px; color: #333; font-weight: 500; }
        .info-box .highlight { font-size: 18px; font-weight: 700; }
        .items-section { padding: 20px 30px; }
        .items-table { width: 100%; border-collapse: collapse; }
        .items-table th { background: #f8f9fa; padding: 12px; text-align: left; font-size: 11px; text-transform: uppercase; color: #666; border-bottom: 2px solid #8B5CF6; }
        .items-table td { padding: 15px 12px; border-bottom: 1px solid #eee; }
        .items-table .text-right { text-align: right; }
        .items-table .amount { font-weight: 600; font-family: monospace; }
        .summary-section { background: #f8f9fa; padding: 25px 30px; }
        .summary-row { display: flex; justify-content: flex-end; margin-bottom: 8px; }
        .summary-row span { min-width: 150px; }
        .summary-row .label { color: #666; text-align: right; padding-right: 20px; }
        .summary-row .value { font-weight: 600; text-align: right; }
        .summary-row.total { font-size: 20px; color: #8B5CF6; border-top: 2px solid #8B5CF6; padding-top: 15px; }
        .footer { padding: 25px 30px; text-align: center; border-top: 1px solid #eee; }
        .validity { background: #8B5CF6; color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; font-size: 12px; }
        .no-print { margin-bottom: 20px; text-align: center; }
        .btn { padding: 10px 25px; border: none; border-radius: 5px; cursor: pointer; font-weight: 600; margin: 0 5px; text-decoration: none; display: inline-block; }
        .btn-print { background: #8B5CF6; color: white; }
        .btn-back { background: #6c757d; color: white; }
        .btn-convert { background: #10B981; color: white; }
        @media print { .no-print { display: none; } body { padding: 0; } .container { box-shadow: none; } }
    </style>
</head>
<body>
    <div class="no-print">
        <a href="/store/quotations" class="btn btn-back">← Back</a>
        <button onclick="window.print()" class="btn btn-print">🖨️ Print</button>
        {% if quotation.status != 'converted' %}
        <a href="/store/quotations/convert/{{ quotation.quotation_no }}" class="btn btn-convert">Convert to Invoice</a>
        {% endif %}
    </div>

    <div class="container">
        <div class="header">
            <div class="company-info">
                <h1>ALUMINUM SHOP</h1>
                <p>Quality Aluminum Products</p>
                <p>📞 01XXXXXXXXX</p>
            </div>
            <div class="quote-title" style="text-align: right;">
                <h2>QUOTATION</h2>
                <p>{{ quotation.quotation_no }}</p>
                <p style="margin-top: 10px;"><span class="validity">Valid: {{ quotation.validity }}</span></p>
            </div>
        </div>

        <div class="info-section">
            <div class="info-box">
                <h4>Quotation For</h4>
                <p class="highlight">{{ quotation.customer_name }}</p>
                <p>📞 {{ quotation.customer_phone }}</p>
                {% if quotation.customer_address %}<p>📍 {{ quotation.customer_address }}</p>{% endif %}
            </div>
            <div class="info-box" style="text-align: right;">
                <h4>Details</h4>
                <p><strong>Date:</strong> {{ quotation.created_at[:10] if quotation.created_at else 'N/A' }}</p>
                <p><strong>Ref:</strong> {{ quotation.quotation_no }}</p>
            </div>
        </div>

        <div class="items-section">
            <table class="items-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Description</th>
                        <th class="text-right">Qty</th>
                        <th class="text-right">Unit</th>
                        <th class="text-right">Price</th>
                        <th class="text-right">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in quotation.items %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ item.description }}</td>
                        <td class="text-right">{{ item.qty }}</td>
                        <td class="text-right">{{ item.unit }}</td>
                        <td class="text-right amount">৳{{ "%.0f"|format(item.price|float) }}</td>
                        <td class="text-right amount">৳{{ "%.0f"|format(item.total|float) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="summary-section">
            <div class="summary-row">
                <span class="label">Subtotal:</span>
                <span class="value">৳{{ "%.0f"|format(quotation.subtotal) }}</span>
            </div>
            {% if quotation.discount > 0 %}
            <div class="summary-row">
                <span class="label">Discount:</span>
                <span class="value">- ৳{{ "%.0f"|format(quotation.discount) }}</span>
            </div>
            {% endif %}
            <div class="summary-row total">
                <span class="label">Grand Total:</span>
                <span class="value">৳{{ "%.0f"|format(quotation.total) }}</span>
            </div>
        </div>

        <div class="footer">
            {% if quotation.notes %}<p style="margin-bottom: 15px;"><strong>Notes:</strong> {{ quotation.notes }}</p>{% endif %}
            <p>Thank you for considering us! </p>
        </div>
    </div>
</body>
</html>
"""

# Payments History Template
STORE_PAYMENTS_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Payments - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>

    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/store/quotations" class="nav-link"><i class="fas fa-file-alt"></i> Quotations</a>
            <a href="/store/dues" class="nav-link"><i class="fas fa-hand-holding-usd"></i> Due Collection</a>
            <a href="/store/payments" class="nav-link active"><i class="fas fa-money-bill-wave"></i> Payments</a>
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link" style="margin-top: 20px;"><i class="fas fa-arrow-left"></i> Main Dashboard</a>{{% endif %}}
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">Payment History</div>
                <div class="page-subtitle">All payment transactions</div>
            </div>
        </div>

        <div class="card">
            <div class="filter-bar">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="searchInput" placeholder="Search payments..." onkeyup="filterTable()">
                </div>
            </div>

            <div style="overflow-x: auto;">
                <table class="dark-table" id="paymentsTable">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Invoice</th>
                            <th>Customer</th>
                            <th>Amount</th>
                            <th>Method</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for p in payments %}}
                        <tr>
                            <td>{{{{ p.created_at[:10] if p.created_at else '-' }}}}</td>
                            <td style="font-weight: 600; color: var(--accent-orange);">{{{{ p.invoice_no or '-' }}}}</td>
                            <td>{{{{ p.customer_name or '-' }}}}</td>
                            <td class="amount amount-green" style="font-size: 16px;">৳{{{{ "%.0f"|format(p.amount) }}}}</td>
                            <td><span class="table-badge">{{{{ p.payment_method }}}}</span></td>
                            <td style="color: var(--text-secondary);">{{{{ p.notes or '-' }}}}</td>
                        </tr>
                        {{% else %}}
                        <tr><td colspan="6"><div class="empty-state"><i class="fas fa-money-bill-wave"></i><h3>No payments yet</h3></div></td></tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function filterTable() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('#paymentsTable tbody tr').forEach(row => {{
                row.style.display = row.textContent.toLowerCase().includes(search) ? '' : 'none';
            }});
        }}
    </script>
</body>
</html>
"""

# Customer View Template
STORE_CUSTOMER_VIEW_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customer Details - Aluminum Shop</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Aluminum<span>Shop</span></div>
        <div class="nav-menu">
            <a href="/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/store/customers" class="nav-link active"><i class="fas fa-users"></i> Customers</a>
            <a href="/store/products" class="nav-link"><i class="fas fa-boxes"></i> Products</a>
            <a href="/store/invoices" class="nav-link"><i class="fas fa-file-invoice-dollar"></i> Invoices</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red);"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
    </div>

    <div class="main-content">
        <div class="header-section">
            <div>
                <div class="page-title">{{{{ customer.name }}}}</div>
                <div class="page-subtitle">Customer ID: {{{{ customer.customer_id }}}}</div>
            </div>
            <a href="/store/customers" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Back</a>
        </div>

        <div class="grid-4" style="margin-bottom: 25px;">
            <div class="quick-stat">
                <div class="quick-stat-value">৳{{{{ "%.0f"|format(customer.total_purchase or 0) }}}}</div>
                <div class="quick-stat-label">Total Purchase</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value amount-green">৳{{{{ "%.0f"|format(customer.total_paid or 0) }}}}</div>
                <div class="quick-stat-label">Total Paid</div>
            </div>
            <div class="quick-stat" style="background: rgba(239, 68, 68, 0.1);">
                <div class="quick-stat-value amount-red">৳{{{{ "%.0f"|format(customer.total_due or 0) }}}}</div>
                <div class="quick-stat-label">Total Due</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value">{{{{ invoices|length }}}}</div>
                <div class="quick-stat-label">Invoices</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <div class="section-header"><span><i class="fas fa-user" style="margin-right: 10px; color: var(--accent-orange);"></i>Contact Info</span></div>
                <p style="margin-bottom: 10px;"><i class="fas fa-phone" style="width: 25px; color: var(--accent-green);"></i> {{{{ customer.phone }}}}</p>
                {{% if customer.email %}}<p style="margin-bottom: 10px;"><i class="fas fa-envelope" style="width: 25px; color: var(--accent-blue);"></i> {{{{ customer.email }}}}</p>{{% endif %}}
                {{% if customer.address %}}<p><i class="fas fa-map-marker-alt" style="width: 25px; color: var(--accent-red);"></i> {{{{ customer.address }}}}</p>{{% endif %}}
            </div>
            <div class="card">
                <div class="section-header"><span><i class="fas fa-clock" style="margin-right: 10px; color: var(--accent-purple);"></i>Timeline</span></div>
                <p style="margin-bottom: 10px; color: var(--text-secondary);">Created: {{{{ customer.created_at[:10] if customer.created_at else 'N/A' }}}}</p>
                <p style="color: var(--text-secondary);">Last Updated: {{{{ customer.updated_at[:10] if customer.updated_at else 'N/A' }}}}</p>
            </div>
        </div>

        <div class="card" style="margin-top: 25px;">
            <div class="section-header"><span><i class="fas fa-file-invoice" style="margin-right: 10px; color: var(--accent-orange);"></i>Invoice History</span></div>
            <table class="dark-table">
                <thead>
                    <tr>
                        <th>Invoice No</th>
                        <th>Date</th>
                        <th>Total</th>
                        <th>Paid</th>
                        <th>Due</th>
                        <th>Status</th>
                        <th style="text-align: right;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {{% for inv in invoices %}}
                    <tr>
                        <td style="font-weight: 700; color: var(--accent-orange);">{{{{ inv.invoice_no }}}}</td>
                        <td>{{{{ inv.created_at[:10] if inv.created_at else '-' }}}}</td>
                        <td class="amount">৳{{{{ "%.0f"|format(inv.total) }}}}</td>
                        <td class="amount amount-green">৳{{{{ "%.0f"|format(inv.paid) }}}}</td>
                        <td class="amount amount-red">৳{{{{ "%.0f"|format(inv.due) }}}}</td>
                        <td>{{% if inv.status == 'paid' %}}<span class="paid-badge">Paid</span>{{% else %}}<span class="due-badge">Due</span>{{% endif %}}</td>
                        <td>
                            <div class="action-cell">
                                <a href="/store/invoices/view/{{{{ inv.invoice_no }}}}" class="action-btn btn-view"><i class="fas fa-eye"></i></a>
                            </div>
                        </td>
                    </tr>
                    {{% else %}}
                    <tr><td colspan="7" class="empty-state">No invoices found</td></tr>
                    {{% endfor %}}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
# Accessories Report Template
ACCESSORIES_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Accessories Delivery Report</title>
    <link href="https://fonts.googleapis.com/css2? family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Poppins', sans-serif; background: #fff; padding: 20px; color: #000; }
        .container { max-width: 1000px; margin: 0 auto; border: 2px solid #000; padding: 20px; min-height: 90vh; }
        .header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 20px; }
        .company-name { font-size: 28px; font-weight: 800; text-transform: uppercase; color: #2c3e50; }
        .company-address { font-size: 12px; font-weight: 600; color: #444; margin-top: 5px; margin-bottom: 10px; }
        .report-title { background: #2c3e50; color: white; padding: 5px 25px; display: inline-block; font-weight: bold; font-size: 18px; border-radius: 4px; }
        .info-grid { display: flex; justify-content: space-between; margin-bottom: 20px; }
        .info-left { flex: 2; border: 1px dashed #555; padding: 15px; margin-right: 15px; }
        .info-row { display: flex; margin-bottom: 5px; font-size: 14px; }
        .info-label { font-weight: 800; width: 80px; color: #444; }
        .info-val { font-weight: 700; font-size: 15px; color: #000; }
        .booking-border { border: 2px solid #000; padding: 2px 8px; display: inline-block; font-weight: 900; }
        .info-right { flex: 1; padding-left: 15px; border-left: 1px solid #ddd; }
        .right-item { font-size: 14px; margin-bottom: 8px; font-weight: 700; }
        .right-label { color: #555; }
        .summary-container { margin-bottom: 20px; border: 2px solid #000; padding: 10px; background: #f9f9f9; }
        .summary-header { font-weight: 900; text-align: center; border-bottom: 1px solid #000; margin-bottom: 5px; }
        .summary-table { width: 100%; font-size: 13px; font-weight: 700; }
        .summary-table td { padding: 2px 5px; }
        .main-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        .main-table th { background: #2c3e50; color: white; padding: 10px; border: 1px solid #000; font-size: 14px; -webkit-print-color-adjust: exact; }
        .main-table td { border: 1px solid #000; padding: 6px; text-align: center; font-weight: 600; }
        .line-card { display: inline-block; padding: 4px 10px; border: 2px solid #000; font-size: 16px; font-weight: 900; border-radius: 4px; box-shadow: 2px 2px 0 #000; }
        .line-text-bold { font-size: 14px; font-weight: 800; opacity: 0.7; }
        .status-cell { font-size: 20px; color: green; font-weight: 900; }
        .qty-cell { font-size: 16px; font-weight: 800; }
        .action-btn { color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 12px; margin: 0 2px; }
        .btn-edit-row { background-color: #f39c12; }
        .btn-del-row { background-color: #e74c3c; }
        .footer-total { margin-top: 20px; display: flex; justify-content: flex-end; }
        .total-box { border: 3px solid #000; padding: 8px 30px; font-size: 20px; font-weight: 900; background: #ddd; -webkit-print-color-adjust: exact; }
        .no-print { margin-bottom: 20px; text-align: right; }
        .btn { padding: 8px 20px; background: #2c3e50; color: white; border: none; cursor: pointer; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px; }
        @media print { .no-print { display: none; } .action-col { display: none; } .container { border: none; } }
    </style>
</head>
<body>
<div class="no-print">
    <a href="/admin/accessories/input_direct? ref={{ ref }}" class="btn">Back</a>
    <button onclick="window.print()" class="btn">🖨️ Print</button>
</div>
<div class="container">
    <div class="header">
        <div class="company-name">COTTON CLOTHING BD LTD</div>
        <div class="company-address">Kazi Tower, 27 Road, Gazipura, Tongi, Gazipur.</div>
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
        <table class="summary-table"><tr>{% for line, qty in line_summary.items() %}<td>{{ line }}: {{ qty }} pcs</td>{% if loop.index % 4 == 0 %}</tr><tr>{% endif %}{% endfor %}</tr></table>
        <div style="text-align: right; margin-top: 5px; font-weight: 800; border-top: 1px solid #ccc;">Total Deliveries: {{ count }}</div>
    </div>
    <table class="main-table">
        <thead><tr><th>DATE</th><th>LINE NO</th><th>COLOR</th><th>SIZE</th><th>STATUS</th><th>QTY</th>{% if session.role == 'admin' %}<th class="action-col">ACTION</th>{% endif %}</tr></thead>
        <tbody>
            {% set ns = namespace(grand_total=0) %}
            {% for item in challans %}
                {% set ns.grand_total = ns.grand_total + item.qty|int %}
                <tr>
                    <td>{{ item.date }}</td>
                    <td>{% if loop.index == count %}<div class="line-card">{{ item.line }}</div>{% else %}<span class="line-text-bold">{{ item.line }}</span>{% endif %}</td>
                    <td>{{ item.color }}</td>
                    <td>{{ item.size }}</td>
                    <td class="status-cell">{{ item.status }}</td>
                    <td class="qty-cell">{{ item.qty }}</td>
                    {% if session.role == 'admin' %}
                    <td class="action-col">
                        <a href="/admin/accessories/edit? ref={{ ref }}&index={{ loop.index0 }}" class="action-btn btn-edit-row"><i class="fas fa-pencil-alt"></i></a>
                        <form action="/admin/accessories/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete? ');"><input type="hidden" name="ref" value="{{ ref }}"><input type="hidden" name="index" value="{{ loop.index0 }}"><button type="submit" class="action-btn btn-del-row" style="border:none;cursor:pointer;"><i class="fas fa-trash"></i></button></form>
                    </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>
    <div class="footer-total"><div class="total-box">TOTAL QTY: {{ ns.grand_total }}</div></div>
    <div style="text-align: right; font-size: 10px; margin-top: 5px; color: #555;">Report Generated By Mehedi Hasan</div>
    <div style="margin-top: 60px; display: flex; justify-content: space-between; text-align: center; font-weight: bold; padding: 0 50px;">
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Received By</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Input Incharge</div>
        <div style="border-top: 2px solid #000; width: 180px; padding-top: 5px;">Store</div>
    </div>
</div>
</body>
</html>
"""

# Closing Report Preview Template
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
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        .report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; margin-top: 5px; }
        .date-section { font-size: 1.2rem; font-weight: 800; color: #000; margin-top: 5px; }
        .info-container { margin-bottom: 15px; background: white; padding: 15px; display: flex; justify-content: space-between; }
        .info-row { display: flex; flex-direction: column; gap: 5px; }
        .info-item { font-size: 1.2rem; font-weight: 600; color: #444; }
        .info-label { font-weight: 800; color: #444; width: 90px; display: inline-block; }
        .info-value { font-weight: 800; color: #000; }
        .booking-box { background: #2c3e50; color: white; padding: 10px 20px; border-radius: 5px; text-align: right; box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3); min-width: 200px; }
        .booking-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; font-weight: 700; }
        .booking-value { font-size: 1.8rem; font-weight: 800; }
        .table-card { background: white; margin-bottom: 30px; border: none; }
        .color-header { background-color: #2c3e50 !important; color: white; padding: 10px 15px; font-size: 1.4rem; font-weight: 800; border: 1px solid #000; }
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; font-size: 1rem; }
        .table th { background-color: #fff ! important; color: #000 !important; text-align: center; border: 1px solid #000; padding: 8px; font-weight: 900; font-size: 1.2rem; }
        .table td { text-align: center; border: 1px solid #000; padding: 6px; color: #000; font-weight: 600; font-size: 1.1rem; }
        .col-3pct { background-color: #B9C2DF ! important; font-weight: 700; }
        .col-input { background-color: #C4D09D !important; font-weight: 700; }
        .col-balance { font-weight: 700; color: #c0392b; }
        .total-row td { background-color: #fff !important; font-weight: 900; font-size: 1.2rem; border-top: 2px solid #000; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 15px; position: sticky; top: 0; z-index: 1000; background: #f8f9fa; padding: 10px 0; }
        .btn-print { background-color: #2c3e50; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; border: none; }
        .btn-excel { background-color: #27ae60; color: white; border-radius: 50px; padding: 10px 30px; font-weight: 600; text-decoration: none; }
        .btn-excel:hover { color: white; background-color: #219150; }
        .footer-credit { text-align: center; margin-top: 40px; font-size: 1rem; color: #2c3e50; border-top: 1px solid #000; padding-top: 10px; font-weight: 600; }
        @media print {
            @page { margin: 5mm; size: portrait; }
            body { background-color: white; padding: 0; }
            .no-print { display: none ! important; }
            .action-bar { display: none; }
            .table th, .table td { border: 1px solid #000 !important; }
            .color-header { background-color: #2c3e50 !important; -webkit-print-color-adjust: exact; color: white ! important; }
            .col-3pct { background-color: #B9C2DF !important; -webkit-print-color-adjust: exact; }
            .col-input { background-color: #C4D09D !important; -webkit-print-color-adjust: exact; }
            .booking-box { background-color: #2c3e50 ! important; -webkit-print-color-adjust: exact; color: white !important; }
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
                <div class="info-item"><span class="info-label">Buyer:</span> <span class="info-value">{{ report_data[0].buyer }}</span></div>
                <div class="info-item"><span class="info-label">Style:</span> <span class="info-value">{{ report_data[0].style }}</span></div>
            </div>
            <div class="booking-box"><div class="booking-label">IR/IB NO</div><div class="booking-value">{{ ref_no }}</div></div>
        </div>
        {% for block in report_data %}
        <div class="table-card">
            <div class="color-header">COLOR: {{ block.color }}</div>
            <table class="table">
                <thead><tr><th>SIZE</th><th>ORDER QTY 3%</th><th>ACTUAL QTY</th><th>CUTTING QC</th><th>INPUT QTY</th><th>BALANCE</th><th>SHORT/PLUS</th><th>PERCENTAGE %</th></tr></thead>
                <tbody>
                    {% set ns = namespace(tot_3=0, tot_act=0, tot_cut=0, tot_inp=0, tot_bal=0, tot_sp=0) %}
                    {% for i in range(block.headers|length) %}
                        {% set actual = block.gmts_qty[i]|replace(',', '')|int %}
                        {% set qty_3 = (actual * 1.03)|round|int %}
                        {% set cut_qc = 0 %}{% if i < block.cutting_qc|length %}{% set cut_qc = block.cutting_qc[i]|replace(',', '')|int %}{% endif %}
                        {% set inp_qty = 0 %}{% if i < block.sewing_input|length %}{% set inp_qty = block.sewing_input[i]|replace(',', '')|int %}{% endif %}
                        {% set balance = cut_qc - inp_qty %}
                        {% set short_plus = inp_qty - qty_3 %}
                        {% set percentage = 0 %}{% if qty_3 > 0 %}{% set percentage = (short_plus / qty_3) * 100 %}{% endif %}
                        {% set ns.tot_3 = ns.tot_3 + qty_3 %}{% set ns.tot_act = ns.tot_act + actual %}{% set ns.tot_cut = ns.tot_cut + cut_qc %}{% set ns.tot_inp = ns.tot_inp + inp_qty %}{% set ns.tot_bal = ns.tot_bal + balance %}{% set ns.tot_sp = ns.tot_sp + short_plus %}
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
                        <td>TOTAL</td><td>{{ ns.tot_3 }}</td><td>{{ ns.tot_act }}</td><td>{{ ns.tot_cut }}</td><td>{{ ns.tot_inp }}</td><td>{{ ns.tot_bal }}</td><td>{{ ns.tot_sp }}</td>
                        <td>{% if ns.tot_3 > 0 %}{{ "%.2f"|format((ns.tot_sp / ns.tot_3) * 100) }}%{% else %}0.00%{% endif %}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        {% endfor %}
        <div class="footer-credit">Report Generated By <span style="color: #000; font-weight: 900;">Mehedi Hasan</span></div>
        {% endif %}
    </div>
    <script>document.getElementById('date').innerText = new Date().toLocaleDateString('en-GB');</script>
</body>
</html>
"""

# PO Report Template
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
        .company-name { font-size: 2.2rem; font-weight: 800; color: #2c3e50; text-transform: uppercase; }
        .report-title { font-size: 1.1rem; color: #555; font-weight: 600; text-transform: uppercase; margin-top: 5px; }
        .date-section { font-size: 1.2rem; font-weight: 800; color: #000; margin-top: 5px; }
        .info-container { display: flex; justify-content: space-between; margin-bottom: 15px; gap: 15px; }
        .info-box { background: white; border: 1px solid #ddd; border-left: 5px solid #2c3e50; padding: 10px 15px; border-radius: 5px; flex: 2; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .total-box { background: #2c3e50; color: white; padding: 10px 15px; border-radius: 5px; width: 240px; text-align: right; }
        .info-item { margin-bottom: 6px; font-size: 1.3rem; font-weight: 700; }
        .info-label { font-weight: 800; color: #444; width: 90px; display: inline-block; }
        .info-value { font-weight: 800; color: #000; }
        .total-label { font-size: 1.1rem; opacity: 0.9; text-transform: uppercase; font-weight: 700; }
        .total-value { font-size: 2.5rem; font-weight: 800; }
        .table-card { background: white; margin-bottom: 20px; border: 1px solid #dee2e6; }
        .color-header { background-color: #e9ecef; color: #2c3e50; padding: 10px 12px; font-size: 1.5rem; font-weight: 900; border-bottom: 1px solid #dee2e6; }
        .table { margin-bottom: 0; width: 100%; border-collapse: collapse; }
        .table th { background-color: #2c3e50; color: white; font-weight: 900; font-size: 1.2rem; text-align: center; border: 1px solid #34495e; padding: 8px 4px; }
        .table th:empty { background-color: white ! important; border: none; }
        .table td { text-align: center; border: 1px solid #dee2e6; padding: 6px 3px; color: #000; font-weight: 800; font-size: 1.15rem; }
        .table-striped tbody tr:nth-of-type(odd) { background-color: #f8f9fa; }
        .order-col { font-weight: 900 !important; text-align: center ! important; background-color: #fdfdfd; }
        .total-col { font-weight: 900; background-color: #e8f6f3 !important; color: #16a085; border-left: 2px solid #1abc9c ! important; }
        .total-col-header { background-color: #e8f6f3 !important; color: #000 !important; font-weight: 900 !important; border: 1px solid #34495e !important; }
        .table-striped tbody tr.summary-row td { background-color: #d1ecff ! important; font-weight: 900 !important; border-top: 2px solid #aaa !important; font-size: 1.2rem ! important; }
        .summary-label { text-align: right ! important; padding-right: 15px ! important; }
        .action-bar { margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 10px; }
        .btn-print { background-color: #e74c3c; color: white; border-radius: 50px; padding: 8px 30px; font-weight: 600; border: none; }
        .footer-credit { text-align: center; margin-top: 30px; font-size: 0.8rem; color: #2c3e50; border-top: 1px solid #ddd; padding-top: 10px; }
        @media print {
            @page { margin: 5mm; size: portrait; }
            body { background-color: white; padding: 0; -webkit-print-color-adjust: exact ! important; }
            .no-print { display: none !important; }
            .table-striped tbody tr.summary-row td { background-color: #d1ecff !important; box-shadow: inset 0 0 0 9999px #d1ecff !important; }
            .color-header { background-color: #f1f1f1 !important; box-shadow: inset 0 0 0 9999px #f1f1f1 !important; }
            .total-col-header { background-color: #e8f6f3 !important; box-shadow: inset 0 0 0 9999px #e8f6f3 !important; }
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
        {% if message %}<div class="alert alert-warning text-center no-print">{{ message }}</div>{% endif %}
        {% if tables %}
            <div class="info-container">
                <div class="info-box">
                    <div><div class="info-item"><span class="info-label">Buyer:</span> <span class="info-value">{{ meta.buyer }}</span></div><div class="info-item"><span class="info-label">Booking:</span> <span class="info-value">{{ meta.booking }}</span></div><div class="info-item"><span class="info-label">Style:</span> <span class="info-value">{{ meta.style }}</span></div></div>
                    <div><div class="info-item"><span class="info-label">Season:</span> <span class="info-value">{{ meta.season }}</span></div><div class="info-item"><span class="info-label">Dept:</span> <span class="info-value">{{ meta.dept }}</span></div><div class="info-item"><span class="info-label">Item:</span> <span class="info-value">{{ meta.item }}</span></div></div>
                </div>
                <div class="total-box"><div class="total-label">Grand Total</div><div class="total-value">{{ grand_total }}</div><small>Pieces</small></div>
            </div>
            {% for item in tables %}<div class="table-card"><div class="color-header">COLOR: {{ item.color }}</div><div class="table-responsive">{{ item.table | safe }}</div></div>{% endfor %}
            <div class="footer-credit">Report Created By <strong>Mehedi Hasan</strong></div>
        {% endif %}
    </div>
    <script>const d=new Date();document.getElementById('date').innerText=`${String(d.getDate()).padStart(2,'0')}-${String(d.getMonth()+1).padStart(2,'0')}-${d.getFullYear()}`;</script>
</body>
</html>
"""
# ==============================================================================
# LOGIC PART: PO SHEET PARSER & CLOSING REPORT (Keep Original)
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
    STANDARD_ORDER = ['0M', '1M', '3M', '6M', '9M', '12M', '18M', '24M', '36M', '2A', '3A', '4A', '5A', '6A', '8A', '10A', '12A', '14A', '16A', '18A', 'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL', 'TU', 'One Size']
    def sort_key(s):
        s = s.strip()
        if s in STANDARD_ORDER: return (0, STANDARD_ORDER.index(s))
        if s.isdigit(): return (1, int(s))
        match = re.match(r'^(\d+)([A-Z]+)$', s)
        if match: return (2, int(match.group(1)), match.group(2))
        return (3, s)
    return sorted(size_list, key=sort_key)

def extract_metadata(first_page_text):
    meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
    if "KIABI" in first_page_text.upper(): meta['buyer'] = "KIABI"
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
    metadata = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
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
                    if "quantity" in lower_line or "currency" in lower_line or "price" in lower_line or "amount" in lower_line: continue
                    clean_line = line.replace("Spec.price", "").replace("Spec", "").strip()
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
                            extracted_data.append({'P.O NO': order_no, 'Color': color_name, 'Size': size, 'Quantity': final_qtys[idx]})
    except Exception as e: print(f"Error processing file: {e}")
    return extracted_data, metadata

def get_authenticated_session(username, password):
    login_url = 'http://180.92.235.190:8022/erp/login.php'
    login_payload = {'txt_userid': username, 'txt_password': password, 'submit': 'Login'}
    session_req = requests.Session()
    session_req.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    try:
        response = session_req.post(login_url, data=login_payload, timeout=300)
        if "dashboard.php" in response.url or "Invalid" not in response.text:
            return session_req
        else: return None
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
                    if "cutting qc" in main_lower and "balance" not in main_lower: cutting_qc_data = [cell.get_text(strip=True) for cell in cells[1:len(headers)+1]]
                    elif "cutting qc" in sub_lower and "balance" not in sub_lower: cutting_qc_data = [cell.get_text(strip=True) for cell in cells[3:len(headers)+3]]
            if gmts_qty_data:
                plus_3_percent_data = []
                for value in gmts_qty_data:
                    try: plus_3_percent_data.append(str(round(int(value.replace(',', '')) * 1.03)))
                    except: plus_3_percent_data.append(value)
                all_report_data.append({'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 'gmts_qty': gmts_qty_data, 'plus_3_percent': plus_3_percent_data, 'sewing_input': sewing_input_data if sewing_input_data else [], 'cutting_qc': cutting_qc_data if cutting_qc_data else []})
        return all_report_data
    except Exception as e: return None

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
    left_sub_headers = {'A4': 'BUYER', 'B4': report_data[0].get('buyer', ''), 'A5': 'IR/IB NO', 'B5': formatted_ref_no, 'A6': 'STYLE NO', 'B6': report_data[0].get('style', '')}
    for cell_ref, value in left_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell.font = bold_font
        cell.alignment = left_align
        cell.border = thin_border
        if cell_ref == 'B5':
            cell.fill = ir_ib_fill
            cell.font = white_bold_font
        else: cell.fill = dark_green_fill
    ws.merge_cells('B4:G4'); ws.merge_cells('B5:G5'); ws.merge_cells('B6:G6')
    right_sub_headers = {'H4': 'CLOSING DATE', 'I4': current_date, 'H5': 'SHIPMENT', 'I5': 'ALL', 'H6': 'PO NO', 'I6': 'ALL'}
    for cell_ref, value in right_sub_headers.items():
        cell = ws[cell_ref]
        cell.value = value
        cell.font = bold_font
        cell.alignment = left_align
        cell.border = thin_border
        cell.fill = dark_green_fill
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
                if col_idx == 9: cell.number_format = '0.00%'
            current_row += 1
        end_merge_row = current_row - 1
        if start_merge_row <= end_merge_row:
            ws.merge_cells(start_row=start_merge_row, start_column=1, end_row=end_merge_row, end_column=1)
            merged_cell = ws.cell(row=start_merge_row, column=1)
            merged_cell.alignment = color_align
            if not merged_cell.font.bold: merged_cell.font = bold_font
        total_row_str = str(current_row)
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
        totals_formulas = {"A": "TOTAL", "C": f"=SUM(C{start_merge_row}:C{end_merge_row})", "D": f"=SUM(D{start_merge_row}:D{end_merge_row})", "E": f"=SUM(E{start_merge_row}:E{end_merge_row})", "F": f"=SUM(F{start_merge_row}:F{end_merge_row})", "G": f"=SUM(G{start_merge_row}:G{end_merge_row})", "H": f"=SUM(H{start_merge_row}:H{end_merge_row})", "I": f"=IF(C{total_row_str}<>0, H{total_row_str}/C{total_row_str}, 0)"}
        for col_letter, value_or_formula in totals_formulas.items():
            cell = ws[f"{col_letter}{current_row}"]
            cell.value = value_or_formula
            cell.font = bold_font
            cell.border = medium_border
            cell.alignment = center_align
            cell.fill = header_row_fill
            if col_letter == 'I': cell.number_format = '0.00%'
        current_row += 2
    ws.column_dimensions['A'].width = 23
    ws.column_dimensions['B'].width = 8.5
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 17
    ws.column_dimensions['E'].width = 17
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 13.5
    ws.column_dimensions['H'].width = 23
    ws.column_dimensions['I'].width = 18
    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==============================================================================
# FLASK ROUTES - MAIN APPLICATION
# ==============================================================================

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        perms = session.get('permissions', [])
        # Store only user - redirect to store
        if len(perms) == 1 and 'store' in perms:
            return redirect(url_for('store_dashboard'))
        # Accessories only user
        if len(perms) == 1 and 'accessories' in perms:
            return redirect(url_for('accessories_search_page'))
        # Admin
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
    return redirect(url_for('index'))

# Admin User Management Routes
@app.route('/admin/get-users', methods=['GET'])
def get_users():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({})
    return jsonify(load_users())

@app.route('/admin/save-user', methods=['POST'])
def save_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error', 'message': 'Unauthorized'})
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    permissions = data.get('permissions', [])
    action = data.get('action_type')
    if not username or not password: return jsonify({'status': 'error', 'message': 'Invalid Data'})
    users_db = load_users()
    if action == 'create':
        if username in users_db: return jsonify({'status': 'error', 'message': 'User already exists!'})
        users_db[username] = {"password": password, "role": "user", "permissions": permissions, "created_at": get_bd_date_str(), "last_login": "Never", "last_duration": "N/A"}
    elif action == 'update':
        if username not in users_db: return jsonify({'status': 'error', 'message': 'User not found!'})
        users_db[username]['password'] = password
        users_db[username]['permissions'] = permissions
    save_users(users_db)
    return jsonify({'status': 'success', 'message': 'User saved successfully!'})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user():
    if not session.get('logged_in') or session.get('role') != 'admin': return jsonify({'status': 'error', 'message': 'Unauthorized'})
    username = request.json.get('username')
    users_db = load_users()
    if username == 'Admin': return jsonify({'status': 'error', 'message': 'Cannot delete Main Admin!'})
    if username in users_db:
        del users_db[username]
        save_users(users_db)
        return jsonify({'status': 'success', 'message': 'User deleted!'})
    return jsonify({'status': 'error', 'message': 'User not found'})

# Closing Report Routes
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
            return make_response(send_file(excel_file, as_attachment=True, download_name=f"Report-{internal_ref_no.replace('/', '_')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))
        else:
            flash("Data source returned empty.")
            return redirect(url_for('index'))
    except Exception as e:
        flash("Failed to generate Excel.")
        return redirect(url_for('index'))

# PO Report Routes
@app.route('/generate-po-report', methods=['POST'])
def generate_po_report():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if os.path.exists(UPLOAD_FOLDER): shutil.rmtree(UPLOAD_FOLDER)
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
        if not all_data: return render_template_string(PO_REPORT_TEMPLATE, tables=None, message="No PO data found in uploaded files.")
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
            try: sorted_cols = sort_sizes(pivot.columns.tolist()); pivot = pivot[sorted_cols]
            except: pass
            pivot['Total'] = pivot.sum(axis=1)
            grand_total_qty += pivot['Total'].sum()
            actual_qty = pivot.sum()
            actual_qty.name = 'Actual Qty'
            qty_plus_3 = (actual_qty * 1.03).round().astype(int)
            qty_plus_3.name = '3% Order Qty'
            pivot_final = pd.concat([pivot, actual_qty.to_frame().T, qty_plus_3.to_frame().T])
            pivot_final = pivot_final.reset_index().rename(columns={'index': 'P.O NO'})
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

# Accessories Routes
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
            db_acc[ref_no] = {"style": style, "buyer": buyer, "colors": colors, "item_type": "", "challans": challans}
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
        for item in db_acc[ref]['challans']: item['status'] = "✔"
        new_entry = {"date": get_bd_date_str(), "line": request.form.get('line_no'), "color": request.form.get('color'), "size": request.form.get('size'), "qty": request.form.get('qty'), "status": ""}
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

# ==============================================================================
# STORE ROUTES
# ==============================================================================

@app.route('/store')
def store_dashboard():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    stats = get_store_dashboard_stats()
    return render_template_string(STORE_DASHBOARD_TEMPLATE, stats=stats)

# Customer Routes
@app.route('/store/customers')
def store_customers():
    if not session.get('logged_in'): return redirect(url_for('index'))
    customers = get_all_customers()
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)

@app.route('/store/customers/add', methods=['POST'])
def store_add_customer():
    if not session.get('logged_in'): return redirect(url_for('index'))
    data = {'name': request.form.get('name'), 'phone': request.form.get('phone'), 'email': request.form.get('email'), 'address': request.form.get('address')}
    customer_id = add_customer(data)
    flash(f'Customer {customer_id} added successfully!')
    return redirect(url_for('store_customers'))

@app.route('/store/customers/update', methods=['POST'])
def store_update_customer():
    if not session.get('logged_in'): return redirect(url_for('index'))
    customer_id = request.form.get('customer_id')
    data = {'name': request.form.get('name'), 'phone': request.form.get('phone'), 'email': request.form.get('email'), 'address': request.form.get('address')}
    update_customer(customer_id, data)
    flash('Customer updated successfully!')
    return redirect(url_for('store_customers'))

@app.route('/store/customers/delete/<customer_id>', methods=['POST'])
def store_delete_customer(customer_id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    delete_customer(customer_id)
    flash('Customer deleted!')
    return redirect(url_for('store_customers'))

@app.route('/store/customers/view/<customer_id>')
def store_view_customer(customer_id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    customer = get_customer_by_id(customer_id)
    if not customer: return redirect(url_for('store_customers'))
    invoices = get_customer_invoices(customer_id)
    return render_template_string(STORE_CUSTOMER_VIEW_TEMPLATE, customer=customer, invoices=invoices)

# Product Routes
@app.route('/store/products')
def store_products():
    if not session.get('logged_in'): return redirect(url_for('index'))
    products = get_all_products()
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products)

@app.route('/store/products/add', methods=['POST'])
def store_add_product():
    if not session.get('logged_in'): return redirect(url_for('index'))
    data = {'name': request.form.get('name'), 'category': request.form.get('category'), 'unit': request.form.get('unit'), 'buy_price': request.form.get('buy_price', 0), 'sell_price': request.form.get('sell_price', 0), 'stock': request.form.get('stock', 0), 'description': request.form.get('description')}
    add_product(data)
    flash('Product added successfully!')
    return redirect(url_for('store_products'))

@app.route('/store/products/update', methods=['POST'])
def store_update_product():
    if not session.get('logged_in'): return redirect(url_for('index'))
    product_id = request.form.get('product_id')
    data = {'name': request.form.get('name'), 'category': request.form.get('category'), 'unit': request.form.get('unit'), 'buy_price': request.form.get('buy_price', 0), 'sell_price': request.form.get('sell_price', 0), 'stock': request.form.get('stock', 0), 'description': request.form.get('description')}
    update_product(product_id, data)
    flash('Product updated!')
    return redirect(url_for('store_products'))

@app.route('/store/products/delete/<product_id>', methods=['POST'])
def store_delete_product(product_id):
    if not session.get('logged_in'): return redirect(url_for('index'))
    delete_product(product_id)
    flash('Product deleted!')
    return redirect(url_for('store_products'))

# Invoice Routes
@app.route('/store/invoices')
def store_invoices():
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoices = get_all_invoices()
    return render_template_string(STORE_INVOICES_TEMPLATE, invoices=invoices)

@app.route('/store/invoices/new')
def store_new_invoice():
    if not session.get('logged_in'): return redirect(url_for('index'))
    customers = get_all_customers()
    products = get_all_products()
    return render_template_string(STORE_CREATE_INVOICE_TEMPLATE, customers=customers, products=products)

@app.route('/store/invoices/save', methods=['POST'])
def store_save_invoice():
    if not session.get('logged_in'): return redirect(url_for('index'))
    items = []
    product_ids = request.form.getlist('product_id[]')
    descriptions = request.form.getlist('description[]')
    qtys = request.form.getlist('qty[]')
    units = request.form.getlist('unit[]')
    prices = request.form.getlist('price[]')
    totals = request.form.getlist('total[]')
    for i in range(len(descriptions)):
        if descriptions[i] or product_ids[i]:
            items.append({'product_id': product_ids[i] if i < len(product_ids) else '', 'description': descriptions[i], 'qty': qtys[i] if i < len(qtys) else 1, 'unit': units[i] if i < len(units) else 'pcs', 'price': prices[i] if i < len(prices) else 0, 'total': totals[i] if i < len(totals) else 0})
    data = {'customer_id': request.form.get('customer_id'), 'customer_name': request.form.get('customer_name'), 'customer_phone': request.form.get('customer_phone'), 'customer_address': request.form.get('customer_address'), 'items': items, 'discount': request.form.get('discount', 0), 'paid': request.form.get('paid', 0), 'payment_method': request.form.get('payment_method', 'Cash'), 'notes': request.form.get('notes'), 'created_by': session.get('user', 'Unknown')}
    invoice_no = create_invoice(data)
    flash(f'Invoice {invoice_no} created successfully!')
    return redirect(url_for('store_view_invoice', invoice_no=invoice_no))

@app.route('/store/invoices/view/<invoice_no>')
def store_view_invoice(invoice_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoice = get_invoice_by_number(invoice_no)
    if not invoice: return redirect(url_for('store_invoices'))
    return render_template_string(STORE_INVOICE_VIEW_TEMPLATE, invoice=invoice)

@app.route('/store/invoices/print/<invoice_no>')
def store_print_invoice(invoice_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoice = get_invoice_by_number(invoice_no)
    if not invoice: return redirect(url_for('store_invoices'))
    return render_template_string(STORE_INVOICE_VIEW_TEMPLATE, invoice=invoice)

@app.route('/store/invoices/edit/<invoice_no>')
def store_edit_invoice(invoice_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoice = get_invoice_by_number(invoice_no)
    if not invoice: return redirect(url_for('store_invoices'))
    customers = get_all_customers()
    products = get_all_products()
    return render_template_string(STORE_CREATE_INVOICE_TEMPLATE, customers=customers, products=products, invoice=invoice, edit_mode=True)

# Due Collection Routes
@app.route('/store/dues')
def store_dues():
    if not session.get('logged_in'): return redirect(url_for('index'))
    all_invoices = get_all_invoices()
    due_invoices = [inv for inv in all_invoices if inv.get('due', 0) > 0]
    total_due = sum(inv.get('due', 0) for inv in due_invoices)
    return render_template_string(STORE_DUES_TEMPLATE, due_invoices=due_invoices, total_due=total_due)

@app.route('/store/dues/collect', methods=['POST'])
def store_collect_due():
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoice_no = request.form.get('invoice_no')
    amount = float(request.form.get('amount', 0))
    payment_method = request.form.get('payment_method', 'Cash')
    if amount > 0:
        collect_due(invoice_no, amount, payment_method)
        flash(f'৳{amount:.0f} collected for invoice {invoice_no}!')
    return redirect(url_for('store_dues'))

@app.route('/store/dues/collect/<invoice_no>')
def store_collect_due_page(invoice_no):
    return redirect(url_for('store_dues'))

# Quotation Routes
@app.route('/store/quotations')
def store_quotations():
    if not session.get('logged_in'): return redirect(url_for('index'))
    quotations = get_all_quotations()
    return render_template_string(STORE_QUOTATIONS_TEMPLATE, quotations=quotations)

@app.route('/store/quotations/new')
def store_new_quotation():
    if not session.get('logged_in'): return redirect(url_for('index'))
    products = get_all_products()
    return render_template_string(STORE_CREATE_QUOTATION_TEMPLATE, products=products)

@app.route('/store/quotations/save', methods=['POST'])
def store_save_quotation():
    if not session.get('logged_in'): return redirect(url_for('index'))
    items = []
    descriptions = request.form.getlist('description[]')
    qtys = request.form.getlist('qty[]')
    units = request.form.getlist('unit[]')
    prices = request.form.getlist('price[]')
    totals = request.form.getlist('total[]')
    for i in range(len(descriptions)):
        if descriptions[i]:
            items.append({'description': descriptions[i], 'qty': qtys[i] if i < len(qtys) else 1, 'unit': units[i] if i < len(units) else 'pcs', 'price': prices[i] if i < len(prices) else 0, 'total': totals[i] if i < len(totals) else 0})
    data = {'customer_name': request.form.get('customer_name'), 'customer_phone': request.form.get('customer_phone'), 'customer_address': request.form.get('customer_address'), 'items': items, 'discount': request.form.get('discount', 0), 'validity': request.form.get('validity', '7 days'), 'notes': request.form.get('notes'), 'created_by': session.get('user', 'Unknown')}
    quotation_no = create_quotation(data)
    flash(f'Quotation {quotation_no} created!')
    return redirect(url_for('store_view_quotation', quotation_no=quotation_no))

@app.route('/store/quotations/view/<quotation_no>')
def store_view_quotation(quotation_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    quotation = get_quotation_by_number(quotation_no)
    if not quotation: return redirect(url_for('store_quotations'))
    return render_template_string(STORE_QUOTATION_VIEW_TEMPLATE, quotation=quotation)

@app.route('/store/quotations/print/<quotation_no>')
def store_print_quotation(quotation_no):
    return store_view_quotation(quotation_no)

@app.route('/store/quotations/convert/<quotation_no>')
def store_convert_quotation(quotation_no):
    if not session.get('logged_in'): return redirect(url_for('index'))
    invoice_no = convert_quotation_to_invoice(quotation_no)
    if invoice_no:
        flash(f'Quotation converted to Invoice {invoice_no}!')
        return redirect(url_for('store_view_invoice', invoice_no=invoice_no))
    flash('Failed to convert quotation!')
    return redirect(url_for('store_quotations'))

# Payment History Route
@app.route('/store/payments')
def store_payments():
    if not session.get('logged_in'): return redirect(url_for('index'))
    payments = get_all_payments()
    return render_template_string(STORE_PAYMENTS_TEMPLATE, payments=payments)

# ==============================================================================
# APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
