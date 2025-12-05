import requests
import openpyxl
from openpyxl. styles import Font, Alignment, Border, Side, PatternFill
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
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office. jxdnuaj.mongodb.net/? appName=Office"

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
# Store Helper Functions
# ==============================================================================

def load_store_products():
    """স্টোর প্রোডাক্ট লোড করা"""
    record = store_products_col.find_one({"_id": "products_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_products(products):
    """স্টোর প্রোডাক্ট সেভ করা"""
    store_products_col.replace_one(
        {"_id": "products_data"},
        {"_id": "products_data", "data": products},
        upsert=True
    )

def load_store_customers():
    """স্টোর কাস্টমার লোড করা"""
    record = store_customers_col.find_one({"_id": "customers_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_customers(customers):
    """স্টোর কাস্টমার সেভ করা"""
    store_customers_col. replace_one(
        {"_id": "customers_data"},
        {"_id": "customers_data", "data": customers},
        upsert=True
    )

def load_store_invoices():
    """স্টোর ইনভয়েস লোড করা"""
    record = store_invoices_col. find_one({"_id": "invoices_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_invoices(invoices):
    """স্টোর ইনভয়েস সেভ করা"""
    store_invoices_col.replace_one(
        {"_id": "invoices_data"},
        {"_id": "invoices_data", "data": invoices},
        upsert=True
    )

def load_store_estimates():
    """স্টোর এস্টিমেট লোড করা"""
    record = store_estimates_col.find_one({"_id": "estimates_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_estimates(estimates):
    """স্টোর এস্টিমেট সেভ করা"""
    store_estimates_col.replace_one(
        {"_id": "estimates_data"},
        {"_id": "estimates_data", "data": estimates},
        upsert=True
    )

def load_store_payments():
    """স্টোর পেমেন্ট লোড করা"""
    record = store_payments_col.find_one({"_id": "payments_data"})
    if record:
        return record['data']
    else:
        return []

def save_store_payments(payments):
    """স্টোর পেমেন্ট সেভ করা"""
    store_payments_col.replace_one(
        {"_id": "payments_data"},
        {"_id": "payments_data", "data": payments},
        upsert=True
    )

def load_store_users():
    """স্টোর ইউজার লোড করা"""
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
        return record['data']
    else:
        store_users_col.insert_one({"_id": "store_users_data", "data": default_users})
        return default_users

def save_store_users(users_data):
    """স্টোর ইউজার সেভ করা"""
    store_users_col.replace_one(
        {"_id": "store_users_data"}, 
        {"_id": "store_users_data", "data": users_data}, 
        upsert=True
    )

def generate_invoice_number():
    """ইনভয়েস নাম্বার জেনারেট করা"""
    invoices = load_store_invoices()
    if not invoices:
        return "INV-0001"
    last_num = 0
    for inv in invoices:
        try:
            num = int(inv['invoice_no']. split('-')[1])
            if num > last_num:
                last_num = num
        except:
            pass
    return f"INV-{str(last_num + 1). zfill(4)}"

def generate_estimate_number():
    """এস্টিমেট নাম্বার জেনারেট করা"""
    estimates = load_store_estimates()
    if not estimates:
        return "EST-0001"
    last_num = 0
    for est in estimates:
        try:
            num = int(est['estimate_no']. split('-')[1])
            if num > last_num:
                last_num = num
        except:
            pass
    return f"EST-{str(last_num + 1).zfill(4)}"

def get_dashboard_summary_v2():
    """ড্যাশবোর্ড সামারি প্রাপ্ত করা"""
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
            "role": d. get('role', 'user'),
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
            except: 
                pass

    # 3. Closing & PO
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

    first_of_last_month = (now. replace(day=1) - timedelta(days=1)).replace(day=1)
    start_date = first_of_last_month.strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    sorted_keys = sorted([k for k in daily_data. keys() if start_date <= k <= end_date])
    
    chart_labels = []
    chart_closing = []
    chart_po = []
    chart_acc = []

    if not sorted_keys:
        curr_d = now. strftime('%d-%b')
        chart_labels = [curr_d]
        chart_closing = [0]
        chart_po = [0]
        chart_acc = [0]
    else:
        for k in sorted_keys:
            d = daily_data[k]
            chart_labels.append(d. get('label', k))
            chart_closing.append(d['closing'])
            chart_po. append(d['po'])
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
    """স্টোর ড্যাশবোর্ড সামারি প্রাপ্ত করা"""
    products = load_store_products()
    customers = load_store_customers()
    invoices = load_store_invoices()
    estimates = load_store_estimates()
    
    now = get_bd_time()
    current_month = now.strftime('%m-%Y')
    monthly_sales = 0
    total_due = 0
    
    for inv in invoices:
        inv_date = inv.get('date', '')
        try:
            if inv_date. split('-')[1] + '-' + inv_date.split('-')[2] == current_month:
                monthly_sales += inv.get('total', 0)
        except:
            pass
        total_due += inv.get('due', 0)
    
    recent_invoices = invoices[-5:] if invoices else []
    
    return {
        "products_count": len(products),
        "customers_count": len(customers),
        "invoices_count": len(invoices),
        "estimates_count": len(estimates),
        "monthly_sales": monthly_sales,
        "total_due": total_due,
        "recent_invoices": recent_invoices
    }
    # ==============================================================================
# PDF Parser এবং Data Extraction
# ==============================================================================

def extract_text_from_pdf(pdf_path):
    """PDF থেকে টেক্সট এক্সট্র্যাক্ট করা"""
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"PDF Parse Error: {e}")
        return ""

def parse_po_from_text(text):
    """PDF টেক্সট থেকে PO ডেটা পার্স করা"""
    po_data = {}
    
    # Reference Number খোঁজা
    ref_match = re.search(r'(? :Ref|Reference|PO)\s*[:\#]?\s*([A-Z0-9\-]+)', text, re.IGNORECASE)
    po_data['ref_no'] = ref_match.group(1) if ref_match else "Unknown"
    
    # Buyer খোঁজা
    buyer_match = re.search(r'(? :Buyer|Company|From)\s*[:\#]?\s*([^\n]+)', text, re.IGNORECASE)
    po_data['buyer'] = buyer_match. group(1). strip() if buyer_match else "Unknown"
    
    # Style খোঁজা
    style_match = re.search(r'(?:Style|Product)\s*[:\#]?\s*([^\n]+)', text, re.IGNORECASE)
    po_data['style'] = style_match.group(1). strip() if style_match else "Unknown"
    
    # Quantity খোঁজা
    qty_match = re.search(r'(?:Qty|Quantity|Pcs)\s*[:\#]?\s*(\d+)', text, re. IGNORECASE)
    po_data['qty'] = int(qty_match.group(1)) if qty_match else 0
    
    # Date খোঁজা
    date_match = re.search(r'(?:Date)\s*[:\#]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        try:
            date_obj = datetime.strptime(date_str. replace('/', '-'), '%d-%m-%Y')
            po_data['date'] = date_obj. strftime('%d-%m-%Y')
        except:
            po_data['date'] = get_bd_date_str()
    else:
        po_data['date'] = get_bd_date_str()
    
    # Description খোঁজা
    desc_match = re.search(r'(?:Description|Details)\s*[:\#]?\s*([^\n]+)', text, re.IGNORECASE)
    po_data['description'] = desc_match.group(1). strip() if desc_match else ""
    
    return po_data

def create_po_excel(po_list):
    """PO ডেটা থেকে Excel ফাইল তৈরি করা"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PO Sheet"
    
    # স্টাইল সেটআপ
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # হেডার লাইন
    headers = ["SL", "Reference No", "Buyer", "Style", "Qty", "Date", "Description"]
    ws.append(headers)
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell. font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    
    # ডেটা রো যোগ করা
    for idx, po in enumerate(po_list, 1):
        ws.append([
            idx,
            po. get('ref_no', ''),
            po.get('buyer', ''),
            po.get('style', ''),
            po.get('qty', 0),
            po.get('date', ''),
            po.get('description', '')
        ])
    
    # কলাম সাইজ সেট করা
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 10
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G']. width = 30
    
    # সকল সেল বর্ডার যোগ করা
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=7):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    # Freeze পেনস
    ws.freeze_panes = "A2"
    
    return wb

def create_closing_report_excel(data):
    """ক্লোজিং রিপোর্ট Excel তৈরি করা"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws. title = "Closing Report"
    
    # স্টাইল সেটআপ
    header_fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # টাইটেল
    ws['A1'] = "CLOSING REPORT"
    ws['A1'].font = Font(bold=True, size=14, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="203864", end_color="203864", fill_type="solid")
    ws. merge_cells('A1:H1')
    ws['A1'].alignment = Alignment(horizontal="center", vertical="center")
    
    # রিপোর্ট তথ্য
    now = get_bd_time()
    ws['A2'] = f"Generated: {now. strftime('%d-%m-%Y %I:%M %p')}"
    ws['A3'] = f"Reference No: {data.get('ref_no', 'N/A')}"
    
    # হেডার
    headers = ["SL", "Item Code", "Description", "In Qty", "Out Qty", "Balance", "Remarks", "Status"]
    ws.append([])
    ws.append(headers)
    
    for cell in ws[5]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # ডেটা রো
    items = data.get('items', [])
    for idx, item in enumerate(items, 1):
        ws.append([
            idx,
            item.get('item_code', ''),
            item.get('description', ''),
            item.get('in_qty', 0),
            item. get('out_qty', 0),
            item.get('balance', 0),
            item. get('remarks', ''),
            item.get('status', '')
        ])
    
    # কলাম সাইজ
    col_widths = [5, 15, 25, 12, 12, 12, 20, 12]
    for idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    
    # সকল সেল বর্ডার
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, min_col=1, max_col=8):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    # Freeze পেনস
    ws.freeze_panes = "A6"
    
    # সামারি তথ্য
    summary_row = ws.max_row + 2
    ws[f'A{summary_row}'] = "SUMMARY"
    ws[f'A{summary_row}'].font = Font(bold=True, size=11)
    
    total_in = sum(item.get('in_qty', 0) for item in items)
    total_out = sum(item.get('out_qty', 0) for item in items)
    total_balance = sum(item.get('balance', 0) for item in items)
    
    ws[f'A{summary_row + 1}'] = "Total In Qty"
    ws[f'B{summary_row + 1}'] = total_in
    
    ws[f'A{summary_row + 2}'] = "Total Out Qty"
    ws[f'B{summary_row + 2}'] = total_out
    
    ws[f'A{summary_row + 3}'] = "Total Balance"
    ws[f'B{summary_row + 3}'] = total_balance
    ws[f'B{summary_row + 3}'].font = Font(bold=True)
    
    return wb

def create_store_invoice_excel(invoice_data):
    """স্টোর ইনভয়েস Excel তৈরি করা"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Invoice"
    
    # স্টাইল
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # টাইটেল
    ws['A1'] = "INVOICE"
    ws['A1']. font = Font(bold=True, size=16)
    ws. merge_cells('A1:F1')
    
    # ইনভয়েস ইনফো
    ws['A3'] = f"Invoice No: {invoice_data.get('invoice_no', '')}"
    ws['A4'] = f"Date: {invoice_data.get('date', '')}"
    ws['A5'] = f"Customer: {invoice_data.get('customer_name', '')}"
    
    # হেডার
    headers = ["SL", "Item", "Qty", "Unit Price", "Amount", "Discount %"]
    ws.append([])
    ws.append(headers)
    
    header_row = 7
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # আইটেম রো
    items = invoice_data.get('items', [])
    for idx, item in enumerate(items, 1):
        row = header_row + idx
        ws.append([
            idx,
            item.get('item_name', ''),
            item.get('quantity', 0),
            item.get('unit_price', 0),
            item.get('amount', 0),
            item.get('discount_percent', 0)
        ])
    
    # কলাম সাইজ
    col_widths = [5, 25, 8, 15, 15, 12]
    for idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl. utils.get_column_letter(idx)].width = width
    
    # সামারি
    summary_row = header_row + len(items) + 2
    ws[f'D{summary_row}'] = "Subtotal:"
    ws[f'E{summary_row}'] = invoice_data.get('subtotal', 0)
    
    ws[f'D{summary_row + 1}'] = "Total Discount:"
    ws[f'E{summary_row + 1}'] = invoice_data.get('discount', 0)
    
    ws[f'D{summary_row + 2}'] = "Tax:"
    ws[f'E{summary_row + 2}'] = invoice_data.get('tax', 0)
    
    ws[f'D{summary_row + 3}'] = "TOTAL:"
    ws[f'E{summary_row + 3}'] = invoice_data.get('total', 0)
    ws[f'E{summary_row + 3}'].font = Font(bold=True, size=12)
    
    ws[f'D{summary_row + 4}'] = "Paid:"
    ws[f'E{summary_row + 4}'] = invoice_data.get('paid', 0)
    
    ws[f'D{summary_row + 5}'] = "Due:"
    ws[f'E{summary_row + 5}'] = invoice_data.get('due', 0)
    
    return wb

def create_store_estimate_excel(estimate_data):
    """স্টোর এস্টিমেট Excel তৈরি করা"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Estimate"
    
    # স্টাইল
    header_fill = PatternFill(start_color="C65911", end_color="C65911", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # টাইটেল
    ws['A1'] = "ESTIMATE / QUOTATION"
    ws['A1'].font = Font(bold=True, size=16)
    ws.merge_cells('A1:F1')
    
    # এস্টিমেট ইনফো
    ws['A3'] = f"Estimate No: {estimate_data. get('estimate_no', '')}"
    ws['A4'] = f"Date: {estimate_data.get('date', '')}"
    ws['A5'] = f"Customer: {estimate_data.get('customer_name', '')}"
    
    # হেডার
    headers = ["SL", "Item", "Qty", "Unit Price", "Amount", "Notes"]
    ws.append([])
    ws.append(headers)
    
    header_row = 7
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell. border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # আইটেম রো
    items = estimate_data. get('items', [])
    for idx, item in enumerate(items, 1):
        row = header_row + idx
        ws.append([
            idx,
            item.get('item_name', ''),
            item.get('quantity', 0),
            item.get('unit_price', 0),
            item.get('amount', 0),
            item.get('notes', '')
        ])
    
    # কলাম সাইজ
    col_widths = [5, 25, 8, 15, 15, 20]
    for idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl. utils.get_column_letter(idx)].width = width
    
    # সামারি
    summary_row = header_row + len(items) + 2
    ws[f'D{summary_row}'] = "Subtotal:"
    ws[f'E{summary_row}'] = estimate_data.get('subtotal', 0)
    
    ws[f'D{summary_row + 1}'] = "Discount:"
    ws[f'E{summary_row + 1}'] = estimate_data.get('discount', 0)
    
    ws[f'D{summary_row + 2}'] = "Tax:"
    ws[f'E{summary_row + 2}'] = estimate_data.get('tax', 0)
    
    ws[f'D{summary_row + 3}'] = "TOTAL:"
    ws[f'E{summary_row + 3}'] = estimate_data.get('total', 0)
    ws[f'E{summary_row + 3}'].font = Font(bold=True, size=12)
    
    ws[f'A{summary_row + 5}'] = estimate_data.get('notes', '')
    ws[f'A{summary_row + 5}'].alignment = Alignment(wrap_text=True)
    
    return wb
    # ==============================================================================
# Authentication Routes
# ==============================================================================

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Office Management System - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .login-container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
            padding: 40px;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-header h1 {
            color: #333;
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .login-header p {
            color: #666;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            color: #333;
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn-login {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        . btn-login:hover {
            transform: translateY(-2px);
        }
        
        .error-message {
            color: #dc3545;
            font-size: 14px;
            margin-top: 10px;
            padding: 10px;
            background: #f8d7da;
            border-radius: 5px;
            display: none;
        }
        
        .error-message.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>Office Management</h1>
            <p>System Login</p>
        </div>
        
        <form method="POST" id="loginForm">
            <div class="form-group">
                <label for="username">Username</label>
                <input 
                    type="text" 
                    id="username" 
                    name="username" 
                    placeholder="Enter your username"
                    required
                    autocomplete="off"
                >
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input 
                    type="password" 
                    id="password" 
                    name="password" 
                    placeholder="Enter your password"
                    required
                    autocomplete="off"
                >
            </div>
            
            <button type="submit" class="btn-login">Login</button>
            
            <div class="error-message" id="errorMsg">
                {{ error_message }}
            </div>
        </form>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            const username = document.getElementById('username'). value. trim();
            const password = document.getElementById('password').value;
            
            if (! username || !password) {
                e.preventDefault();
                const errorDiv = document.getElementById('errorMsg');
                errorDiv.textContent = 'Please fill in all fields';
                errorDiv.classList.add('show');
            }
        });
        
        {% if error_message %}
        document.getElementById('errorMsg').classList. add('show');
        {% endif %}
    </script>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    """লগইন পেজ এবং অথেন্টিকেশন"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template_string(LOGIN_TEMPLATE, error_message='Please fill in all fields')
        
        users = load_users()
        
        if username not in users:
            return render_template_string(LOGIN_TEMPLATE, error_message='Invalid username or password')
        
        user = users[username]
        if user['password'] != password:
            return render_template_string(LOGIN_TEMPLATE, error_message='Invalid username or password')
        
        # সেশন সেট করা
        session. permanent = True
        session['username'] = username
        session['role'] = user. get('role', 'user')
        session['permissions'] = user.get('permissions', [])
        session['login_time'] = get_bd_time(). isoformat()
        
        # ইউজার লাস্ট লগইন আপডেট করা
        users[username]['last_login'] = get_bd_date_str()
        save_users(users)
        
        # ড্যাশবোর্ড রিডাইরেক্ট
        if user. get('role') == 'store_admin' or user.get('role') == 'store_user':
            return redirect(url_for('store_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    """লগআউট"""
    username = session.get('username')
    if username:
        users = load_users()
        if username in users:
            login_time_str = session.get('login_time')
            try:
                login_time = datetime.fromisoformat(login_time_str)
                logout_time = get_bd_time()
                duration = str(logout_time - login_time).split('.')[0]
                users[username]['last_duration'] = duration
            except:
                users[username]['last_duration'] = 'N/A'
            save_users(users)
    
    session.clear()
    return redirect(url_for('login'))

def login_required(f):
    """লগইন রিকোয়ার্ড ডেকোরেটর"""
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def permission_required(permission):
    """পারমিশন চেক ডেকোরেটর"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))
            
            permissions = session.get('permissions', [])
            if permission not in permissions and session.get('role') != 'admin':
                return jsonify({'error': 'Permission Denied'}), 403
            
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

# ==============================================================================
# Main Dashboard Routes
# ==============================================================================

@app.route('/')
def home():
    """হোম পেজ - লগইন এ রিডাইরেক্ট"""
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """মেইন ড্যাশবোর্ড"""
    username = session.get('username')
    role = session.get('role')
    
    # পারমিশন চেক
    if role == 'store_admin' or role == 'store_user':
        return redirect(url_for('store_dashboard'))
    
    summary = get_dashboard_summary_v2()
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 username=username, 
                                 role=role,
                                 summary=summary)

@app.route('/api/dashboard-data')
@login_required
def get_dashboard_data():
    """ড্যাশবোর্ড ডেটা API"""
    summary = get_dashboard_summary_v2()
    return jsonify(summary)

@app.route('/closing', methods=['GET', 'POST'])
@login_required
@permission_required('closing')
def closing_report():
    """ক্লোজিং রিপোর্ট পেজ"""
    username = session.get('username')
    
    if request.method == 'POST':
        # ক্লোজিং রিপোর্ট ডেটা পাওয়া
        ref_no = request.form.get('ref_no', '')
        items = request.form.getlist('item_code[]')
        descriptions = request.form.getlist('description[]')
        in_qtys = request.form.getlist('in_qty[]')
        out_qtys = request.form.getlist('out_qty[]')
        
        closing_data = {
            'ref_no': ref_no,
            'items': []
        }
        
        for i in range(len(items)):
            in_qty = int(in_qtys[i]) if in_qtys[i] else 0
            out_qty = int(out_qtys[i]) if out_qtys[i] else 0
            balance = in_qty - out_qty
            
            closing_data['items'].append({
                'item_code': items[i],
                'description': descriptions[i],
                'in_qty': in_qty,
                'out_qty': out_qty,
                'balance': balance,
                'remarks': request.form.get(f'remarks_{i}', ''),
                'status': 'OK' if balance >= 0 else 'SHORT'
            })
        
        # Excel তৈরি করা
        wb = create_closing_report_excel(closing_data)
        
        # ফাইল সংরক্ষণ এবং ডাউনলোড
        file_path = os.path.join(UPLOAD_FOLDER, f'closing_{ref_no}_{int(time.time())}.xlsx')
        wb.save(file_path)
        
        # স্ট্যাটিস্টিক্স আপডেট করা
        update_stats(ref_no, username)
        
        return send_file(file_path, as_attachment=True, download_name=f'Closing_{ref_no}.xlsx')
    
    return render_template_string(CLOSING_TEMPLATE, username=username)

@app.route('/po-sheet', methods=['GET', 'POST'])
@login_required
@permission_required('po_sheet')
def po_sheet():
    """PO শীট পেজ - PDF আপলোড এবং পার্সিং"""
    username = session.get('username')
    po_list = []
    
    if request.method == 'POST':
        files = request.files.getlist('pdf_files[]')
        
        for file in files:
            if file and file.filename. endswith('.pdf'):
                # PDF ফাইল সংরক্ষণ করা
                pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(pdf_path)
                
                # PDF থেকে ডেটা এক্সট্র্যাক্ট করা
                text = extract_text_from_pdf(pdf_path)
                po_data = parse_po_from_text(text)
                po_list.append(po_data)
        
        if po_list:
            # Excel তৈরি করা
            wb = create_po_excel(po_list)
            
            # ফাইল সংরক্ষণ এবং ডাউনলোড
            file_path = os.path.join(UPLOAD_FOLDER, f'PO_Sheet_{int(time.time())}.xlsx')
            wb.save(file_path)
            
            # স্ট্যাটিস্টিক্স আপডেট করা
            update_po_stats(username, len(po_list))
            
            return send_file(file_path, as_attachment=True, download_name='PO_Sheet.xlsx')
    
    return render_template_string(PO_SHEET_TEMPLATE, username=username, po_list=po_list)

@app.route('/accessories', methods=['GET', 'POST'])
@login_required
@permission_required('accessories')
def accessories():
    """অ্যাক্সেসরিজ ম্যানেজমেন্ট পেজ"""
    username = session.get('username')
    acc_db = load_accessories_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            ref_no = request.form.get('ref_no', '')
            buyer = request.form.get('buyer', '')
            style = request.form.get('style', '')
            
            if ref_no not in acc_db:
                acc_db[ref_no] = {
                    'buyer': buyer,
                    'style': style,
                    'challans': []
                }
        
        elif action == 'add_challan':
            ref_no = request.form.get('ref_no', '')
            qty = int(request.form.get('qty', 0))
            
            if ref_no in acc_db:
                acc_db[ref_no]['challans'].append({
                    'date': get_bd_date_str(),
                    'qty': qty
                })
        
        save_accessories_db(acc_db)
    
    return render_template_string(ACCESSORIES_TEMPLATE, username=username, acc_db=acc_db)

@app.route('/user-manage', methods=['GET', 'POST'])
@login_required
@permission_required('user_manage')
def user_manage():
    """ইউজার ম্যানেজমেন্ট পেজ"""
    username = session.get('username')
    users = load_users()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            new_username = request.form.get('new_username', '').strip()
            new_password = request.form.get('new_password', '')
            role = request.form.get('role', 'user')
            
            if new_username and new_password:
                if new_username not in users:
                    users[new_username] = {
                        'password': new_password,
                        'role': role,
                        'permissions': get_default_permissions(role),
                        'created_at': get_bd_date_str(),
                        'last_login': 'Never',
                        'last_duration': 'N/A'
                    }
                    save_users(users)
                    message = f"✓ User '{new_username}' created successfully"
                else:
                    message = "✗ User already exists"
        
        elif action == 'delete':
            del_username = request.form.get('del_username', '')
            if del_username and del_username != 'Admin':
                del users[del_username]
                save_users(users)
                message = f"✓ User '{del_username}' deleted"
        
        elif action == 'update':
            upd_username = request.form. get('upd_username', '')
            upd_password = request.form.get('upd_password', '')
            upd_role = request.form. get('upd_role', '')
            
            if upd_username in users:
                if upd_password:
                    users[upd_username]['password'] = upd_password
                if upd_role:
                    users[upd_username]['role'] = upd_role
                    users[upd_username]['permissions'] = get_default_permissions(upd_role)
                save_users(users)
                message = f"✓ User '{upd_username}' updated"
    
    return render_template_string(USER_MANAGE_TEMPLATE, 
                                 username=username, 
                                 users=users,
                                 message=message)

def get_default_permissions(role):
    """ডিফল্ট পারমিশন পাওয়া"""
    permissions_map = {
        'admin': ['closing', 'po_sheet', 'user_manage', 'view_history', 'accessories'],
        'user': ['closing', 'po_sheet'],
        'manager': ['closing', 'po_sheet', 'accessories', 'view_history']
    }
    return permissions_map.get(role, [])

@app.route('/history')
@login_required
@permission_required('view_history')
def view_history():
    """হিস্ট্রি ভিউ পেজ"""
    username = session.get('username')
    stats = load_stats()
    history = stats.get('downloads', [])
    
    return render_template_string(HISTORY_TEMPLATE, username=username, history=history)
    # ==============================================================================
# Store Dashboard Route
# ==============================================================================

@app.route('/store/dashboard')
@login_required
def store_dashboard():
    """স্টোর ড্যাশবোর্ড"""
    username = session.get('username')
    summary = get_store_dashboard_summary()
    
    return render_template_string(STORE_DASHBOARD_TEMPLATE, username=username, summary=summary)

@app. route('/store/api/dashboard-data')
@login_required
def store_get_dashboard_data():
    """স্টোর ড্যাশবোর্ড ডেটা API"""
    summary = get_store_dashboard_summary()
    return jsonify(summary)

# ==============================================================================
# Store Products Management
# ==============================================================================

@app. route('/store/products', methods=['GET', 'POST'])
@login_required
def store_products():
    """স্টোর প্রোডাক্ট ম্যানেজমেন্ট"""
    username = session.get('username')
    products = load_store_products()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            product = {
                'id': int(time.time()),
                'name': request.form.get('name', ''),
                'code': request.form.get('code', ''),
                'category': request.form.get('category', ''),
                'unit_price': float(request.form. get('unit_price', 0)),
                'stock': int(request.form.get('stock', 0)),
                'reorder_level': int(request. form.get('reorder_level', 10)),
                'description': request. form.get('description', ''),
                'created_at': get_bd_date_str()
            }
            products.append(product)
            save_store_products(products)
            message = f"✓ Product '{product['name']}' added successfully"
        
        elif action == 'update':
            product_id = int(request.form.get('product_id'))
            for product in products:
                if product['id'] == product_id:
                    product['name'] = request.form.get('name', product['name'])
                    product['code'] = request.form.get('code', product['code'])
                    product['category'] = request.form.get('category', product['category'])
                    product['unit_price'] = float(request.form.get('unit_price', product['unit_price']))
                    product['stock'] = int(request.form.get('stock', product['stock']))
                    product['reorder_level'] = int(request.form.get('reorder_level', product['reorder_level']))
                    product['description'] = request.form. get('description', product['description'])
                    break
            save_store_products(products)
            message = f"✓ Product updated successfully"
        
        elif action == 'delete':
            product_id = int(request.form.get('product_id'))
            products = [p for p in products if p['id'] != product_id]
            save_store_products(products)
            message = f"✓ Product deleted successfully"
    
    return render_template_string(STORE_PRODUCTS_TEMPLATE, 
                                 username=username, 
                                 products=products,
                                 message=message)

# ==============================================================================
# Store Customers Management
# ==============================================================================

@app.route('/store/customers', methods=['GET', 'POST'])
@login_required
def store_customers():
    """স্টোর কাস্টমার ম্যানেজমেন্ট"""
    username = session.get('username')
    customers = load_store_customers()
    message = ""
    
    if request. method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            customer = {
                'id': int(time.time()),
                'name': request.form.get('name', ''),
                'phone': request.form.get('phone', ''),
                'email': request.form.get('email', ''),
                'address': request.form.get('address', ''),
                'city': request.form.get('city', ''),
                'credit_limit': float(request.form.get('credit_limit', 0)),
                'created_at': get_bd_date_str()
            }
            customers. append(customer)
            save_store_customers(customers)
            message = f"✓ Customer '{customer['name']}' added successfully"
        
        elif action == 'update':
            customer_id = int(request.form.get('customer_id'))
            for customer in customers:
                if customer['id'] == customer_id:
                    customer['name'] = request.form.get('name', customer['name'])
                    customer['phone'] = request. form.get('phone', customer['phone'])
                    customer['email'] = request.form.get('email', customer['email'])
                    customer['address'] = request. form.get('address', customer['address'])
                    customer['city'] = request.form.get('city', customer['city'])
                    customer['credit_limit'] = float(request.form.get('credit_limit', customer['credit_limit']))
                    break
            save_store_customers(customers)
            message = f"✓ Customer updated successfully"
        
        elif action == 'delete':
            customer_id = int(request.form.get('customer_id'))
            customers = [c for c in customers if c['id'] != customer_id]
            save_store_customers(customers)
            message = f"✓ Customer deleted successfully"
    
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, 
                                 username=username, 
                                 customers=customers,
                                 message=message)
    # ==============================================================================
# Store Invoices Management
# ==============================================================================

@app.route('/store/invoices', methods=['GET', 'POST'])
@login_required
def store_invoices():
    """স্টোর ইনভয়েস ম্যানেজমেন্ট"""
    username = session.get('username')
    invoices = load_store_invoices()
    customers = load_store_customers()
    products = load_store_products()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            invoice = {
                'id': int(time.time()),
                'invoice_no': generate_invoice_number(),
                'customer_id': int(request. form.get('customer_id')),
                'customer_name': request.form.get('customer_name', ''),
                'date': request.form.get('date', get_bd_date_str()),
                'due_date': request.form.get('due_date', ''),
                'items': [],
                'subtotal': 0,
                'discount': 0,
                'discount_percent': 0,
                'tax': 0,
                'tax_percent': 0,
                'total': 0,
                'paid': 0,
                'due': 0,
                'notes': request.form.get('notes', ''),
                'status': 'Draft',
                'created_at': get_bd_date_str(),
                'created_by': username
            }
            
            # আইটেম যোগ করা
            item_names = request.form.getlist('item_name[]')
            item_ids = request.form.getlist('item_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            discounts = request.form.getlist('discount[]')
            
            subtotal = 0
            total_discount = 0
            
            for i in range(len(item_names)):
                if item_names[i]:
                    qty = int(quantities[i]) if quantities[i] else 0
                    unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                    discount = float(discounts[i]) if discounts[i] else 0
                    amount = (qty * unit_price) - discount
                    
                    invoice['items'].append({
                        'item_id': item_ids[i] if item_ids[i] else '',
                        'item_name': item_names[i],
                        'quantity': qty,
                        'unit_price': unit_price,
                        'discount': discount,
                        'amount': amount
                    })
                    
                    subtotal += (qty * unit_price)
                    total_discount += discount
            
            # গণনা করা
            invoice['subtotal'] = subtotal
            invoice['discount'] = total_discount
            invoice['discount_percent'] = float(request.form.get('discount_percent', 0))
            invoice['tax_percent'] = float(request.form.get('tax_percent', 0))
            
            if invoice['discount_percent'] > 0:
                invoice['discount'] += (subtotal * invoice['discount_percent'] / 100)
            
            taxable = subtotal - invoice['discount']
            invoice['tax'] = (taxable * invoice['tax_percent'] / 100)
            invoice['total'] = taxable + invoice['tax']
            invoice['due'] = invoice['total']
            invoice['status'] = 'Finalized'
            
            invoices.append(invoice)
            save_store_invoices(invoices)
            
            message = f"✓ Invoice '{invoice['invoice_no']}' created successfully"
        
        elif action == 'update':
            invoice_id = int(request.form.get('invoice_id'))
            
            for invoice in invoices:
                if invoice['id'] == invoice_id:
                    invoice['due_date'] = request.form.get('due_date', invoice['due_date'])
                    invoice['notes'] = request.form.get('notes', invoice['notes'])
                    
                    # আইটেম আপডেট করা
                    invoice['items'] = []
                    item_names = request.form. getlist('item_name[]')
                    quantities = request.form.getlist('quantity[]')
                    unit_prices = request.form.getlist('unit_price[]')
                    discounts = request.form. getlist('discount[]')
                    
                    subtotal = 0
                    total_discount = 0
                    
                    for i in range(len(item_names)):
                        if item_names[i]:
                            qty = int(quantities[i]) if quantities[i] else 0
                            unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                            discount = float(discounts[i]) if discounts[i] else 0
                            amount = (qty * unit_price) - discount
                            
                            invoice['items'].append({
                                'item_name': item_names[i],
                                'quantity': qty,
                                'unit_price': unit_price,
                                'discount': discount,
                                'amount': amount
                            })
                            
                            subtotal += (qty * unit_price)
                            total_discount += discount
                    
                    invoice['subtotal'] = subtotal
                    invoice['discount'] = total_discount
                    invoice['discount_percent'] = float(request.form.get('discount_percent', 0))
                    invoice['tax_percent'] = float(request.form. get('tax_percent', 0))
                    
                    if invoice['discount_percent'] > 0:
                        invoice['discount'] += (subtotal * invoice['discount_percent'] / 100)
                    
                    taxable = subtotal - invoice['discount']
                    invoice['tax'] = (taxable * invoice['tax_percent'] / 100)
                    invoice['total'] = taxable + invoice['tax']
                    invoice['due'] = invoice['total'] - invoice. get('paid', 0)
                    
                    break
            
            save_store_invoices(invoices)
            message = f"✓ Invoice updated successfully"
        
        elif action == 'delete':
            invoice_id = int(request. form.get('invoice_id'))
            invoices = [inv for inv in invoices if inv['id'] != invoice_id]
            save_store_invoices(invoices)
            message = f"✓ Invoice deleted successfully"
        
        elif action == 'download':
            invoice_id = int(request.form.get('invoice_id'))
            
            for invoice in invoices:
                if invoice['id'] == invoice_id:
                    wb = create_store_invoice_excel(invoice)
                    file_path = os.path.join(UPLOAD_FOLDER, f"invoice_{invoice['invoice_no']}_{int(time.time())}.xlsx")
                    wb.save(file_path)
                    return send_file(file_path, as_attachment=True, download_name=f"{invoice['invoice_no']}.xlsx")
    
    return render_template_string(STORE_INVOICES_TEMPLATE,
                                 username=username,
                                 invoices=invoices,
                                 customers=customers,
                                 products=products,
                                 message=message)

@app.route('/store/invoice/<int:invoice_id>/view')
@login_required
def view_invoice(invoice_id):
    """ইনভয়েস ভিউ পেজ"""
    invoices = load_store_invoices()
    
    for invoice in invoices:
        if invoice['id'] == invoice_id:
            return render_template_string(VIEW_INVOICE_TEMPLATE, invoice=invoice)
    
    return "Invoice not found", 404

@app.route('/store/invoice/<int:invoice_id>/download')
@login_required
def download_invoice(invoice_id):
    """ইনভয়েস ডাউনলোড করা"""
    invoices = load_store_invoices()
    
    for invoice in invoices:
        if invoice['id'] == invoice_id:
            wb = create_store_invoice_excel(invoice)
            file_path = os.path.join(UPLOAD_FOLDER, f"invoice_{invoice['invoice_no']}_{int(time.time())}.xlsx")
            wb.save(file_path)
            return send_file(file_path, as_attachment=True, download_name=f"{invoice['invoice_no']}. xlsx")
    
    return "Invoice not found", 404

# ==============================================================================
# Store Estimates Management
# ==============================================================================

@app.route('/store/estimates', methods=['GET', 'POST'])
@login_required
def store_estimates():
    """স্টোর এস্টিমেট ম্যানেজমেন্ট"""
    username = session.get('username')
    estimates = load_store_estimates()
    customers = load_store_customers()
    products = load_store_products()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            estimate = {
                'id': int(time. time()),
                'estimate_no': generate_estimate_number(),
                'customer_id': int(request.form.get('customer_id')),
                'customer_name': request.form. get('customer_name', ''),
                'date': request.form.get('date', get_bd_date_str()),
                'valid_until': request.form.get('valid_until', ''),
                'items': [],
                'subtotal': 0,
                'discount': 0,
                'discount_percent': 0,
                'tax': 0,
                'tax_percent': 0,
                'total': 0,
                'notes': request.form.get('notes', ''),
                'status': 'Draft',
                'created_at': get_bd_date_str(),
                'created_by': username
            }
            
            # আইটেম যোগ করা
            item_names = request.form. getlist('item_name[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            item_notes = request.form.getlist('notes[]')
            
            subtotal = 0
            
            for i in range(len(item_names)):
                if item_names[i]:
                    qty = int(quantities[i]) if quantities[i] else 0
                    unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                    amount = qty * unit_price
                    
                    estimate['items'].append({
                        'item_name': item_names[i],
                        'quantity': qty,
                        'unit_price': unit_price,
                        'amount': amount,
                        'notes': item_notes[i] if i < len(item_notes) else ''
                    })
                    
                    subtotal += amount
            
            # গণনা করা
            estimate['subtotal'] = subtotal
            estimate['discount_percent'] = float(request.form.get('discount_percent', 0))
            estimate['tax_percent'] = float(request.form.get('tax_percent', 0))
            
            if estimate['discount_percent'] > 0:
                estimate['discount'] = (subtotal * estimate['discount_percent'] / 100)
            
            taxable = subtotal - estimate['discount']
            estimate['tax'] = (taxable * estimate['tax_percent'] / 100)
            estimate['total'] = taxable + estimate['tax']
            estimate['status'] = 'Sent'
            
            estimates.append(estimate)
            save_store_estimates(estimates)
            
            message = f"✓ Estimate '{estimate['estimate_no']}' created successfully"
        
        elif action == 'update':
            estimate_id = int(request.form.get('estimate_id'))
            
            for estimate in estimates:
                if estimate['id'] == estimate_id:
                    estimate['valid_until'] = request.form. get('valid_until', estimate['valid_until'])
                    estimate['notes'] = request.form.get('notes', estimate['notes'])
                    estimate['status'] = request.form. get('status', estimate['status'])
                    
                    # আইটেম আপডেট করা
                    estimate['items'] = []
                    item_names = request.form. getlist('item_name[]')
                    quantities = request.form.getlist('quantity[]')
                    unit_prices = request. form.getlist('unit_price[]')
                    item_notes = request.form.getlist('notes[]')
                    
                    subtotal = 0
                    
                    for i in range(len(item_names)):
                        if item_names[i]:
                            qty = int(quantities[i]) if quantities[i] else 0
                            unit_price = float(unit_prices[i]) if unit_prices[i] else 0
                            amount = qty * unit_price
                            
                            estimate['items'].append({
                                'item_name': item_names[i],
                                'quantity': qty,
                                'unit_price': unit_price,
                                'amount': amount,
                                'notes': item_notes[i] if i < len(item_notes) else ''
                            })
                            
                            subtotal += amount
                    
                    estimate['subtotal'] = subtotal
                    estimate['discount_percent'] = float(request.form. get('discount_percent', 0))
                    estimate['tax_percent'] = float(request.form.get('tax_percent', 0))
                    
                    if estimate['discount_percent'] > 0:
                        estimate['discount'] = (subtotal * estimate['discount_percent'] / 100)
                    
                    taxable = subtotal - estimate['discount']
                    estimate['tax'] = (taxable * estimate['tax_percent'] / 100)
                    estimate['total'] = taxable + estimate['tax']
                    
                    break
            
            save_store_estimates(estimates)
            message = f"✓ Estimate updated successfully"
        
        elif action == 'delete':
            estimate_id = int(request.form.get('estimate_id'))
            estimates = [est for est in estimates if est['id'] != estimate_id]
            save_store_estimates(estimates)
            message = f"✓ Estimate deleted successfully"
        
        elif action == 'download':
            estimate_id = int(request.form.get('estimate_id'))
            
            for estimate in estimates:
                if estimate['id'] == estimate_id:
                    wb = create_store_estimate_excel(estimate)
                    file_path = os. path.join(UPLOAD_FOLDER, f"estimate_{estimate['estimate_no']}_{int(time.time())}.xlsx")
                    wb.save(file_path)
                    return send_file(file_path, as_attachment=True, download_name=f"{estimate['estimate_no']}.xlsx")
    
    return render_template_string(STORE_ESTIMATES_TEMPLATE,
                                 username=username,
                                 estimates=estimates,
                                 customers=customers,
                                 products=products,
                                 message=message)

@app.route('/store/estimate/<int:estimate_id>/view')
@login_required
def view_estimate(estimate_id):
    """এস্টিমেট ভিউ পেজ"""
    estimates = load_store_estimates()
    
    for estimate in estimates:
        if estimate['id'] == estimate_id:
            return render_template_string(VIEW_ESTIMATE_TEMPLATE, estimate=estimate)
    
    return "Estimate not found", 404

@app.route('/store/estimate/<int:estimate_id>/download')
@login_required
def download_estimate(estimate_id):
    """এস্টিমেট ডাউনলোড করা"""
    estimates = load_store_estimates()
    
    for estimate in estimates:
        if estimate['id'] == estimate_id:
            wb = create_store_estimate_excel(estimate)
            file_path = os.path.join(UPLOAD_FOLDER, f"estimate_{estimate['estimate_no']}_{int(time.time())}.xlsx")
            wb.save(file_path)
            return send_file(file_path, as_attachment=True, download_name=f"{estimate['estimate_no']}.xlsx")
    
    return "Estimate not found", 404
    # ==============================================================================
# Store Payments Management
# ==============================================================================

@app.route('/store/payments', methods=['GET', 'POST'])
@login_required
def store_payments():
    """স্টোর পেমেন্ট ম্যানেজমেন্ট"""
    username = session.get('username')
    payments = load_store_payments()
    invoices = load_store_invoices()
    customers = load_store_customers()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            payment = {
                'id': int(time.time()),
                'invoice_id': int(request.form.get('invoice_id')),
                'invoice_no': request.form.get('invoice_no', ''),
                'customer_id': int(request.form.get('customer_id')),
                'customer_name': request.form.get('customer_name', ''),
                'amount': float(request.form.get('amount', 0)),
                'payment_method': request.form.get('payment_method', ''),
                'reference': request.form.get('reference', ''),
                'date': request.form.get('date', get_bd_date_str()),
                'notes': request.form.get('notes', ''),
                'created_at': get_bd_date_str(),
                'created_by': username
            }
            
            payments.append(payment)
            save_store_payments(payments)
            
            # ইনভয়েস পেমেন্ট আপডেট করা
            for invoice in invoices:
                if invoice['id'] == payment['invoice_id']:
                    invoice['paid'] = invoice. get('paid', 0) + payment['amount']
                    invoice['due'] = invoice['total'] - invoice['paid']
                    
                    if invoice['due'] <= 0:
                        invoice['status'] = 'Paid'
                    else:
                        invoice['status'] = 'Partially Paid'
                    break
            
            save_store_invoices(invoices)
            message = f"✓ Payment recorded successfully"
        
        elif action == 'delete':
            payment_id = int(request.form.get('payment_id'))
            
            # পুরাতন পেমেন্ট খুঁজে বের করা এবং ইনভয়েস থেকে বাদ দেওয়া
            for payment in payments:
                if payment['id'] == payment_id:
                    # ইনভয়েস আপডেট করা
                    for invoice in invoices:
                        if invoice['id'] == payment['invoice_id']:
                            invoice['paid'] = invoice.get('paid', 0) - payment['amount']
                            invoice['due'] = invoice['total'] - invoice['paid']
                            
                            if invoice['due'] >= invoice['total']:
                                invoice['status'] = 'Pending'
                            elif invoice['due'] <= 0:
                                invoice['status'] = 'Paid'
                            else:
                                invoice['status'] = 'Partially Paid'
                            break
                    break
            
            payments = [p for p in payments if p['id'] != payment_id]
            save_store_payments(payments)
            save_store_invoices(invoices)
            message = f"✓ Payment deleted successfully"
    
    # পেমেন্ট স্ট্যাটিস্টিক্স
    total_received = sum(p['amount'] for p in payments)
    total_pending = sum(inv['due'] for inv in invoices if inv. get('due', 0) > 0)
    
    return render_template_string(STORE_PAYMENTS_TEMPLATE,
                                 username=username,
                                 payments=payments,
                                 invoices=invoices,
                                 customers=customers,
                                 message=message,
                                 total_received=total_received,
                                 total_pending=total_pending)

@app.route('/store/api/invoice/<int:invoice_id>')
@login_required
def get_invoice_details(invoice_id):
    """ইনভয়েস ডিটেইলস API"""
    invoices = load_store_invoices()
    
    for invoice in invoices:
        if invoice['id'] == invoice_id:
            return jsonify({
                'invoice_no': invoice['invoice_no'],
                'customer_name': invoice['customer_name'],
                'customer_id': invoice['customer_id'],
                'total': invoice['total'],
                'paid': invoice. get('paid', 0),
                'due': invoice. get('due', 0)
            })
    
    return jsonify({'error': 'Invoice not found'}), 404

# ==============================================================================
# Store Settings এবং User Management
# ==============================================================================

@app.route('/store/users', methods=['GET', 'POST'])
@login_required
def store_users():
    """স্টোর ইউজার ম্যানেজমেন্ট"""
    username = session.get('username')
    users = load_store_users()
    message = ""
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            new_username = request.form.get('new_username', '').strip()
            new_password = request.form.get('new_password', '')
            role = request.form.get('role', 'store_user')
            
            if new_username and new_password:
                if new_username not in users:
                    users[new_username] = {
                        'password': new_password,
                        'role': role,
                        'permissions': get_store_default_permissions(role),
                        'created_at': get_bd_date_str(),
                        'last_login': 'Never'
                    }
                    save_store_users(users)
                    message = f"✓ Store user '{new_username}' created successfully"
                else:
                    message = "✗ User already exists"
        
        elif action == 'delete':
            del_username = request.form.get('del_username', '')
            if del_username and del_username != 'StoreAdmin':
                del users[del_username]
                save_store_users(users)
                message = f"✓ Store user '{del_username}' deleted"
        
        elif action == 'update':
            upd_username = request.form. get('upd_username', '')
            upd_password = request.form.get('upd_password', '')
            upd_role = request.form. get('upd_role', '')
            
            if upd_username in users:
                if upd_password:
                    users[upd_username]['password'] = upd_password
                if upd_role:
                    users[upd_username]['role'] = upd_role
                    users[upd_username]['permissions'] = get_store_default_permissions(upd_role)
                save_store_users(users)
                message = f"✓ Store user '{upd_username}' updated"
    
    return render_template_string(STORE_USERS_TEMPLATE,
                                 username=username,
                                 users=users,
                                 message=message)

def get_store_default_permissions(role):
    """স্টোর ডিফল্ট পারমিশন পাওয়া"""
    permissions_map = {
        'store_admin': ['products', 'customers', 'invoices', 'estimates', 'payments', 'user_manage', 'settings'],
        'store_user': ['invoices', 'estimates', 'customers'],
        'store_manager': ['products', 'customers', 'invoices', 'estimates', 'payments']
    }
    return permissions_map.get(role, [])

@app.route('/store/settings')
@login_required
def store_settings():
    """স্টোর সেটিংস পেজ"""
    username = session.get('username')
    
    # স্টোর কনফিগারেশন ডেটা (MongoDB থেকে পাওয়া যেতে পারে)
    store_config = {
        'store_name': 'My Store',
        'address': 'Store Address',
        'phone': '01700000000',
        'email': 'store@example.com',
        'tax_percent': 0,
        'currency': 'BDT'
    }
    
    return render_template_string(STORE_SETTINGS_TEMPLATE,
                                 username=username,
                                 config=store_config)

# ==============================================================================
# Store Reports
# ==============================================================================

@app.route('/store/reports')
@login_required
def store_reports():
    """স্টোর রিপোর্টস পেজ"""
    username = session.get('username')
    invoices = load_store_invoices()
    payments = load_store_payments()
    
    # আজকের ডেটা
    today = get_bd_date_str()
    today_invoices = [inv for inv in invoices if inv. get('date') == today]
    today_payments = [p for p in payments if p.get('date') == today]
    
    # মাসিক ডেটা
    current_month = get_bd_time(). strftime('%m-%Y')
    monthly_total = 0
    monthly_paid = 0
    
    for inv in invoices:
        inv_date = inv.get('date', '')
        try:
            if inv_date. split('-')[1] + '-' + inv_date.split('-')[2] == current_month:
                monthly_total += inv. get('total', 0)
                monthly_paid += inv.get('paid', 0)
        except:
            pass
    
    # সারমর্য
    summary = {
        'today_invoices': len(today_invoices),
        'today_amount': sum(inv['total'] for inv in today_invoices),
        'today_payments': len(today_payments),
        'today_received': sum(p['amount'] for p in today_payments),
        'monthly_total': monthly_total,
        'monthly_received': monthly_paid,
        'monthly_pending': monthly_total - monthly_paid
    }
    
    return render_template_string(STORE_REPORTS_TEMPLATE,
                                 username=username,
                                 summary=summary)

# ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """404 এরর হ্যান্ডলার"""
    return render_template_string(ERROR_404_TEMPLATE), 404

@app.errorhandler(500)
def internal_error(error):
    """500 এরর হ্যান্ডলার"""
    return render_template_string(ERROR_500_TEMPLATE), 500

# ==============================================================================
# API Endpoints
# ==============================================================================

@app.route('/api/customer/<int:customer_id>')
@login_required
def get_customer_details(customer_id):
    """কাস্টমার ডিটেইলস API"""
    customers = load_store_customers()
    
    for customer in customers:
        if customer['id'] == customer_id:
            return jsonify(customer)
    
    return jsonify({'error': 'Customer not found'}), 404

@app.route('/api/customers/search')
@login_required
def search_customers():
    """কাস্টমার সার্চ API"""
    query = request.args.get('q', '').lower()
    customers = load_store_customers()
    
    results = [c for c in customers if query in c['name'].lower() or query in c['phone']]
    
    return jsonify(results[:10])

@app.route('/api/products/search')
@login_required
def search_products():
    """প্রোডাক্ট সার্চ API"""
    query = request.args.get('q', '').lower()
    products = load_store_products()
    
    results = [p for p in products if query in p['name'].lower() or query in p['code']. lower()]
    
    return jsonify(results[:10])

# ==============================================================================
# Application Entry Point
# ==============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    # ==============================================================================
# DASHBOARD TEMPLATE
# ==============================================================================

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Office Management - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        . navbar h1 {
            font-size: 24px;
        }
        
        .navbar-right {
            display: flex;
            gap: 2rem;
            align-items: center;
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #3498db;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }
        
        .logout-btn {
            background-color: #e74c3c;
            color: white;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        
        .logout-btn:hover {
            background-color: #c0392b;
        }
        
        . sidebar {
            position: fixed;
            left: 0;
            top: 70px;
            width: 250px;
            height: calc(100vh - 70px);
            background-color: #34495e;
            padding-top: 1rem;
            overflow-y: auto;
            box-shadow: 2px 0 4px rgba(0,0,0,0.1);
        }
        
        .sidebar a {
            display: block;
            color: white;
            padding: 1rem 1.5rem;
            text-decoration: none;
            border-left: 4px solid transparent;
            transition: all 0.3s;
        }
        
        . sidebar a:hover,
        .sidebar a.active {
            background-color: #2c3e50;
            border-left-color: #3498db;
        }
        
        .sidebar . section-title {
            color: #95a5a6;
            font-size: 12px;
            text-transform: uppercase;
            padding: 1rem 1.5rem 0.5rem;
            font-weight: bold;
        }
        
        .main-content {
            margin-left: 250px;
            margin-top: 70px;
            padding: 2rem;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1. 5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #3498db;
        }
        
        .stat-card h3 {
            color: #7f8c8d;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        
        .stat-card .number {
            font-size: 32px;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .stat-card. closing {
            border-left-color: #27ae60;
        }
        
        .stat-card.po {
            border-left-color: #f39c12;
        }
        
        .stat-card. accessories {
            border-left-color: #9b59b6;
        }
        
        . stat-card.users {
            border-left-color: #e74c3c;
        }
        
        .chart-container {
            background: white;
            padding: 1. 5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        
        .chart-container h3 {
            margin-bottom: 1rem;
            color: #2c3e50;
        }
        
        .chart-canvas {
            max-height: 400px;
        }
        
        .table-container {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        
        .table-container h3 {
            margin-bottom: 1rem;
            color: #2c3e50;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0. 25rem 0.75rem;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-success {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-warning {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-danger {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        @media (max-width: 768px) {
            .sidebar {
                width: 200px;
            }
            
            .main-content {
                margin-left: 200px;
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- Navbar -->
    <div class="navbar">
        <h1>📊 Office Management System</h1>
        <div class="navbar-right">
            <div class="user-info">
                <div class="user-avatar">{{ username[0]. upper() }}</div>
                <div>
                    <div>{{ username }}</div>
                    <small>{{ role. capitalize() }}</small>
                </div>
            </div>
            <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
        </div>
    </div>
    
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="section-title">Main</div>
        <a href="{{ url_for('dashboard') }}" class="active">Dashboard</a>
        
        {% if 'closing' in session. get('permissions', []) or role == 'admin' %}
        <a href="{{ url_for('closing_report') }}">Closing Report</a>
        {% endif %}
        
        {% if 'po_sheet' in session.get('permissions', []) or role == 'admin' %}
        <a href="{{ url_for('po_sheet') }}">PO Sheet</a>
        {% endif %}
        
        {% if 'accessories' in session.get('permissions', []) or role == 'admin' %}
        <a href="{{ url_for('accessories') }}">Accessories</a>
        {% endif %}
        
        <div class="section-title">Admin</div>
        
        {% if 'user_manage' in session.get('permissions', []) or role == 'admin' %}
        <a href="{{ url_for('user_manage') }}">User Management</a>
        {% endif %}
        
        {% if 'view_history' in session.get('permissions', []) or role == 'admin' %}
        <a href="{{ url_for('view_history') }}">History</a>
        {% endif %}
    </div>
    
    <!-- Main Content -->
    <div class="main-content">
        <h2>Dashboard</h2>
        
        <!-- Statistics Cards -->
        <div class="dashboard-grid">
            <div class="stat-card users">
                <h3>Total Users</h3>
                <div class="number">{{ summary.users. count }}</div>
            </div>
            <div class="stat-card closing">
                <h3>Closing Reports</h3>
                <div class="number">{{ summary.closing.count }}</div>
            </div>
            <div class="stat-card po">
                <h3>PO Sheets</h3>
                <div class="number">{{ summary.po. count }}</div>
            </div>
            <div class="stat-card accessories">
                <h3>Accessories</h3>
                <div class="number">{{ summary.accessories.count }}</div>
            </div>
        </div>
        
        <!-- Chart -->
        <div class="chart-container">
            <h3>Activity Chart (Last 30 Days)</h3>
            <div class="chart-canvas">
                <canvas id="activityChart"></canvas>
            </div>
        </div>
        
        <!-- Today's Activity -->
        {% if summary.closing.details or summary.po.details or summary.accessories.details %}
        <div class="table-container">
            <h3>Today's Activity</h3>
            <table>
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Reference</th>
                        <th>User</th>
                        <th>Time</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in summary.closing.details %}
                    <tr>
                        <td><span class="badge badge-success">Closing</span></td>
                        <td>{{ item.ref }}</td>
                        <td>{{ item.user }}</td>
                        <td>{{ item.time }}</td>
                        <td>-</td>
                    </tr>
                    {% endfor %}
                    
                    {% for item in summary. po.details %}
                    <tr>
                        <td><span class="badge badge-warning">PO Sheet</span></td>
                        <td>-</td>
                        <td>{{ item.user }}</td>
                        <td>{{ item.time }}</td>
                        <td>{{ item.file_count }} files</td>
                    </tr>
                    {% endfor %}
                    
                    {% for item in summary.accessories.details %}
                    <tr>
                        <td><span class="badge badge-danger">Accessories</span></td>
                        <td>{{ item.ref }}</td>
                        <td>-</td>
                        <td>Today</td>
                        <td>{{ item.qty }} qty</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
        
        <!-- Recent History -->
        <div class="table-container" style="margin-top: 2rem;">
            <h3>Recent Activity</h3>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Time</th>
                        <th>User</th>
                        <th>Type</th>
                        <th>Reference</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in summary.history[:10] %}
                    <tr>
                        <td>{{ item.date }}</td>
                        <td>{{ item.time }}</td>
                        <td>{{ item.user }}</td>
                        <td>{{ item.type }}</td>
                        <td>{{ item.get('ref', item.get('file_count', '-')) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        // Chart Data
        const chartLabels = {{ summary.chart. labels | tojson }};
        const chartClosing = {{ summary.chart.closing | tojson }};
        const chartPO = {{ summary.chart.po | tojson }};
        const chartAcc = {{ summary.chart.acc | tojson }};
        
        const ctx = document.getElementById('activityChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [
                    {
                        label: 'Closing Reports',
                        data: chartClosing,
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'PO Sheets',
                        data: chartPO,
                        borderColor: '#f39c12',
                        backgroundColor: 'rgba(243, 156, 18, 0.1)',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Accessories',
                        data: chartAcc,
                        borderColor: '#9b59b6',
                        backgroundColor: 'rgba(155, 89, 182, 0.1)',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# CLOSING REPORT TEMPLATE
# ==============================================================================

CLOSING_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Closing Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #2c3e50;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #2c3e50;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 0. 75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        . items-table {
            width: 100%;
            margin-top: 2rem;
            border-collapse: collapse;
        }
        
        .items-table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        .items-table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
        }
        
        .items-table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .items-table input {
            width: 100%;
            padding: 0.5rem;
        }
        
        .btn-container {
            margin-top: 2rem;
            display: flex;
            gap: 1rem;
        }
        
        button, . btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background-color: #3498db;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #2980b9;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .btn-add-row {
            background-color: #27ae60;
            color: white;
            margin-bottom: 1rem;
        }
        
        .btn-remove {
            background-color: #e74c3c;
            color: white;
            padding: 0.5rem 1rem;
            font-size: 12px;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📋 Closing Report</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Create Closing Report</h1>
        
        <form method="POST" id="closingForm">
            <div class="form-group">
                <label>Reference Number *</label>
                <input type="text" name="ref_no" placeholder="e.g., REF-001" required>
            </div>
            
            <h3 style="margin-top: 2rem; margin-bottom: 1rem;">Items</h3>
            
            <table class="items-table">
                <thead>
                    <tr>
                        <th>Item Code</th>
                        <th>Description</th>
                        <th>In Qty</th>
                        <th>Out Qty</th>
                        <th>Remarks</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody id="itemsBody">
                    <tr>
                        <td><input type="text" name="item_code[]" placeholder="Code"></td>
                        <td><input type="text" name="description[]" placeholder="Description"></td>
                        <td><input type="number" name="in_qty[]" min="0" value="0"></td>
                        <td><input type="number" name="out_qty[]" min="0" value="0"></td>
                        <td><input type="text" name="remarks[]" placeholder="Remarks"></td>
                        <td><button type="button" class="btn-remove" onclick="removeRow(this)">Remove</button></td>
                    </tr>
                </tbody>
            </table>
            
            <button type="button" class="btn-add-row" onclick="addRow()">+ Add Row</button>
            
            <div class="btn-container">
                <button type="submit" class="btn-primary">Generate Report</button>
                <a href="{{ url_for('dashboard') }}" class="btn btn-secondary">Cancel</a>
            </div>
        </form>
    </div>
    
    <script>
        function addRow() {
            const tbody = document.getElementById('itemsBody');
            const newRow = tbody.rows[0].cloneNode(true);
            
            // Clear input values
            newRow.querySelectorAll('input').forEach(input => {
                input.value = '';
            });
            
            tbody.appendChild(newRow);
        }
        
        function removeRow(btn) {
            const tbody = document.getElementById('itemsBody');
            if (tbody.rows.length > 1) {
                btn.parentElement.parentElement.remove();
            } else {
                alert('At least one row must remain');
            }
        }
        
        document.getElementById('closingForm').addEventListener('submit', function(e) {
            const refNo = document.querySelector('input[name="ref_no"]').value;
            if (!refNo. trim()) {
                e.preventDefault();
                alert('Please enter Reference Number');
            }
        });
    </script>
</body>
</html>
"""
# ==============================================================================
# PO SHEET TEMPLATE
# ==============================================================================

PO_SHEET_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PO Sheet</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #2c3e50;
        }
        
        .upload-section {
            border: 2px dashed #3498db;
            border-radius: 8px;
            padding: 2rem;
            text-align: center;
            background-color: #ecf8ff;
            margin-bottom: 2rem;
        }
        
        .upload-section h3 {
            color: #3498db;
            margin-bottom: 1rem;
        }
        
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
        }
        
        .file-input-wrapper input[type=file] {
            position: absolute;
            left: -9999px;
        }
        
        .file-input-label {
            display: inline-block;
            padding: 0.75rem 1. 5rem;
            background-color: #3498db;
            color: white;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .file-input-label:hover {
            background-color: #2980b9;
        }
        
        .file-list {
            margin-top: 1rem;
            text-align: left;
        }
        
        .file-item {
            padding: 0. 75rem;
            background-color: #f9f9f9;
            border-left: 4px solid #3498db;
            margin-bottom: 0.5rem;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .file-item button {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 0. 25rem 0.75rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .file-item button:hover {
            background-color: #c0392b;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        .btn-container {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
        }
        
        button, . btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }
        
        . btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .info-box {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 1rem;
            border-radius: 4px;
            margin-top: 1rem;
            color: #155724;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📄 PO Sheet Generator</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Upload PDF Files to Generate PO Sheet</h1>
        
        <form method="POST" enctype="multipart/form-data" id="poForm">
            <div class="upload-section">
                <h3>📁 Select PDF Files</h3>
                <p>Upload one or more PDF files to extract PO data</p>
                
                <div class="file-input-wrapper">
                    <label for="pdfFiles" class="file-input-label">Choose Files</label>
                    <input type="file" id="pdfFiles" name="pdf_files[]" multiple accept=".pdf">
                </div>
                
                <div class="file-list" id="fileList">
                    <!-- Files will be listed here -->
                </div>
            </div>
            
            <div class="btn-container">
                <button type="submit" class="btn-primary">Generate PO Sheet</button>
                <a href="{{ url_for('dashboard') }}" class="btn btn-secondary">Cancel</a>
            </div>
        </form>
        
        {% if po_list %}
        <div class="info-box">
            <strong>✓ Success!</strong> {{ po_list | length }} PO(s) extracted from PDF files.
        </div>
        
        <div class="table-container">
            <h2 style="margin-bottom: 1rem;">Extracted PO Data</h2>
            <table>
                <thead>
                    <tr>
                        <th>SL</th>
                        <th>Reference No</th>
                        <th>Buyer</th>
                        <th>Style</th>
                        <th>Qty</th>
                        <th>Date</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {% for idx, po in po_list | list | enumerate %}
                    <tr>
                        <td>{{ idx + 1 }}</td>
                        <td>{{ po.ref_no }}</td>
                        <td>{{ po.buyer }}</td>
                        <td>{{ po.style }}</td>
                        <td>{{ po. qty }}</td>
                        <td>{{ po.date }}</td>
                        <td>{{ po.description }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>
    
    <script>
        const fileInput = document.getElementById('pdfFiles');
        const fileList = document.getElementById('fileList');
        
        fileInput.addEventListener('change', function() {
            fileList.innerHTML = '';
            
            if (this.files. length === 0) {
                fileList.innerHTML = '<p style="color: #7f8c8d;">No files selected</p>';
                return;
            }
            
            Array.from(this.files).forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.innerHTML = `
                    <span>📄 ${file.name} (${(file.size / 1024). toFixed(2)} KB)</span>
                    <button type="button" onclick="removeFile(${index})">Remove</button>
                `;
                fileList.appendChild(fileItem);
            });
        });
        
        function removeFile(index) {
            const dt = new DataTransfer();
            const input = document.getElementById('pdfFiles');
            
            Array.from(input.files).forEach((file, i) => {
                if (i !== index) {
                    dt.items.add(file);
                }
            });
            
            input.files = dt.files;
            
            const event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
        }
        
        document.getElementById('poForm').addEventListener('submit', function(e) {
            const fileInput = document.getElementById('pdfFiles');
            if (fileInput.files.length === 0) {
                e. preventDefault();
                alert('Please select at least one PDF file');
            }
        });
    </script>
</body>
</html>
"""

# ==============================================================================
# ACCESSORIES TEMPLATE
# ==============================================================================

ACCESSORIES_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Accessories Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #2c3e50;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #2c3e50;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #2c3e50;
        }
        
        input, select, textarea {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .stat-badge {
            display: inline-block;
            padding: 0. 25rem 0.75rem;
            background-color: #e8f4f8;
            color: #2c3e50;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 2rem;
            border: 1px solid #888;
            border-radius: 8px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        . close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        . close:hover {
            color: black;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>🎁 Accessories Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Accessories</h1>
        
        <!-- Add New Accessory Form -->
        <div class="form-section">
            <h3>➕ Add New Accessory Reference</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Reference Number *</label>
                        <input type="text" name="ref_no" placeholder="e.g., ACC-001" required>
                    </div>
                    <div class="form-group">
                        <label>Buyer *</label>
                        <input type="text" name="buyer" placeholder="Buyer name" required>
                    </div>
                    <div class="form-group">
                        <label>Style *</label>
                        <input type="text" name="style" placeholder="Style name" required>
                    </div>
                    <div style="display: flex; align-items: flex-end;">
                        <button type="submit" class="btn-primary">Add Reference</button>
                    </div>
                </div>
            </form>
        </div>
        
        <!-- Accessories List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">📋 Current Accessories</h3>
            
            {% if acc_db %}
            <table>
                <thead>
                    <tr>
                        <th>Ref No</th>
                        <th>Buyer</th>
                        <th>Style</th>
                        <th>Total Qty</th>
                        <th>Challans</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for ref_no, data in acc_db.items() %}
                    <tr>
                        <td><strong>{{ ref_no }}</strong></td>
                        <td>{{ data.buyer }}</td>
                        <td>{{ data. style }}</td>
                        <td>
                            <span class="stat-badge">
                                {{ data.challans | length }} challans
                            </span>
                        </td>
                        <td>
                            {% set total_qty = data.challans | map(attribute='qty') | sum %}
                            <strong>{{ total_qty }}</strong> qty
                        </td>
                        <td>
                            <button class="btn-secondary" onclick="openChallanModal('{{ ref_no }}')">
                                Add Challan
                            </button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No accessories found. Add a new reference to get started.
            </p>
            {% endif %}
        </div>
    </div>
    
    <!-- Challan Modal -->
    <div id="challanModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeChallanModal()">&times;</span>
            <h3>Add Challan</h3>
            <form method="POST" id="challanForm">
                <input type="hidden" name="action" value="add_challan">
                <input type="hidden" name="ref_no" id="refNoInput">
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Quantity *</label>
                    <input type="number" name="qty" min="1" placeholder="Enter quantity" required>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="submit" class="btn-primary">Add Challan</button>
                    <button type="button" class="btn-secondary" onclick="closeChallanModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function openChallanModal(refNo) {
            document.getElementById('refNoInput').value = refNo;
            document.getElementById('challanModal').style.display = 'block';
        }
        
        function closeChallanModal() {
            document.getElementById('challanModal'). style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('challanModal');
            if (event. target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# USER MANAGEMENT TEMPLATE
# ==============================================================================

USER_MANAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>User Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #2c3e50;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #2c3e50;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0. 5rem;
            color: #2c3e50;
        }
        
        input, select {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        . btn-warning {
            background-color: #f39c12;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-warning:hover {
            background-color: #d68910;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0. 25rem 0.75rem;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-admin {
            background-color: #fadbd8;
            color: #922b21;
        }
        
        .badge-manager {
            background-color: #fef5e7;
            color: #7d6608;
        }
        
        .badge-user {
            background-color: #d5f4e6;
            color: #0b5345;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 2rem;
            border: 1px solid #888;
            border-radius: 8px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        . close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        . close:hover {
            color: black;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>👥 User Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Users</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Add New User Form -->
        <div class="form-section">
            <h3>➕ Create New User</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Username *</label>
                        <input type="text" name="new_username" placeholder="Username" required>
                    </div>
                    <div class="form-group">
                        <label>Password *</label>
                        <input type="password" name="new_password" placeholder="Password" required>
                    </div>
                    <div class="form-group">
                        <label>Role *</label>
                        <select name="role" required>
                            <option value="user">User</option>
                            <option value="manager">Manager</option>
                            <option value="admin">Admin</option>
                        </select>
                    </div>
                    <div style="display: flex; align-items: flex-end;">
                        <button type="submit" class="btn-primary">Create User</button>
                    </div>
                </div>
            </form>
        </div>
        
        <!-- Users List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">📋 Current Users</h3>
            
            {% if users %}
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Created At</th>
                        <th>Last Login</th>
                        <th>Duration</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for username, user_data in users.items() %}
                    <tr>
                        <td><strong>{{ username }}</strong></td>
                        <td>
                            <span class="badge badge-{{ user_data.role }}">
                                {{ user_data.role | capitalize }}
                            </span>
                        </td>
                        <td>{{ user_data. created_at }}</td>
                        <td>{{ user_data.last_login }}</td>
                        <td>{{ user_data.last_duration }}</td>
                        <td>
                            <div class="action-buttons">
                                {% if username != 'Admin' %}
                                <button class="btn-warning" onclick="openEditModal('{{ username }}', '{{ user_data.role }}')">
                                    Edit
                                </button>
                                <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this user?');">
                                    <input type="hidden" name="action" value="delete">
                                    <input type="hidden" name="del_username" value="{{ username }}">
                                    <button type="submit" class="btn-danger">Delete</button>
                                </form>
                                {% else %}
                                <span style="color: #7f8c8d;">Default Admin</span>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No users found. 
            </p>
            {% endif %}
        </div>
    </div>
    
    <!-- Edit User Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>Edit User</h3>
            <form method="POST" id="editForm">
                <input type="hidden" name="action" value="update">
                <input type="hidden" name="upd_username" id="editUsername">
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Password (Leave empty to keep current)</label>
                    <input type="password" name="upd_password" placeholder="New password">
                </div>
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Role *</label>
                    <select name="upd_role" required>
                        <option value="user">User</option>
                        <option value="manager">Manager</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="submit" class="btn-primary">Update User</button>
                    <button type="button" class="btn-secondary" onclick="closeEditModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function openEditModal(username, role) {
            document.getElementById('editUsername'). value = username;
            document. querySelector('select[name="upd_role"]').value = role;
            document.getElementById('editModal').style. display = 'block';
        }
        
        function closeEditModal() {
            document.getElementById('editModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target == modal) {
                modal. style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# HISTORY TEMPLATE
# ==============================================================================

HISTORY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Activity History</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #2c3e50;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-closing {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-po {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-accessories {
            background-color: #d1ecf1;
            color: #0c5460;
        }
        
        .empty-state {
            text-align: center;
            padding: 3rem;
            color: #7f8c8d;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📜 Activity History</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Complete Activity History</h1>
        
        {% if history %}
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Time</th>
                        <th>User</th>
                        <th>Type</th>
                        <th>Reference / Details</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in history %}
                    <tr>
                        <td>{{ item.date }}</td>
                        <td>{{ item.time }}</td>
                        <td>{{ item.user }}</td>
                        <td>
                            {% if item.type == 'Closing Report' %}
                            <span class="badge badge-closing">Closing</span>
                            {% elif item.type == 'PO Sheet' %}
                            <span class="badge badge-po">PO Sheet</span>
                            {% else %}
                            <span class="badge badge-accessories">Accessories</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if item.get('ref') %}
                            Ref: {{ item.ref }}
                            {% elif item.get('file_count') %}
                            {{ item. file_count }} PDF files
                            {% else %}
                            -
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="empty-state">
            <p>No activity history found</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE DASHBOARD TEMPLATE
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Store Management - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        . navbar h1 {
            font-size: 24px;
        }
        
        .navbar-right {
            display: flex;
            gap: 2rem;
            align-items: center;
        }
        
        .user-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #ffc107;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #1f4e78;
        }
        
        .logout-btn {
            background-color: #e74c3c;
            color: white;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
        }
        
        .logout-btn:hover {
            background-color: #c0392b;
        }
        
        . sidebar {
            position: fixed;
            left: 0;
            top: 70px;
            width: 250px;
            height: calc(100vh - 70px);
            background-color: #34495e;
            padding-top: 1rem;
            overflow-y: auto;
            box-shadow: 2px 0 4px rgba(0,0,0,0.1);
        }
        
        .sidebar a {
            display: block;
            color: white;
            padding: 1rem 1.5rem;
            text-decoration: none;
            border-left: 4px solid transparent;
            transition: all 0.3s;
        }
        
        . sidebar a:hover,
        .sidebar a.active {
            background-color: #2c3e50;
            border-left-color: #ffc107;
        }
        
        .sidebar . section-title {
            color: #95a5a6;
            font-size: 12px;
            text-transform: uppercase;
            padding: 1rem 1.5rem 0.5rem;
            font-weight: bold;
        }
        
        .main-content {
            margin-left: 250px;
            margin-top: 70px;
            padding: 2rem;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #1f4e78;
        }
        
        .stat-card h3 {
            color: #7f8c8d;
            font-size: 13px;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        
        .stat-card .number {
            font-size: 32px;
            font-weight: bold;
            color: #1f4e78;
        }
        
        .stat-card. products {
            border-left-color: #3498db;
        }
        
        .stat-card.customers {
            border-left-color: #2ecc71;
        }
        
        .stat-card.invoices {
            border-left-color: #f39c12;
        }
        
        .stat-card. sales {
            border-left-color: #e74c3c;
        }
        
        .stat-card.due {
            border-left-color: #9b59b6;
        }
        
        . stat-card-subtitle {
            font-size: 12px;
            color: #7f8c8d;
            margin-top: 0.5rem;
        }
        
        .chart-container {
            background: white;
            padding: 1. 5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        
        .chart-container h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .chart-canvas {
            max-height: 400px;
        }
        
        .table-container {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        
        .table-container h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0. 75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-success {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-pending {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-draft {
            background-color: #e2e3e5;
            color: #383d41;
        }
        
        .currency {
            font-weight: bold;
            color: #1f4e78;
        }
        
        @media (max-width: 768px) {
            .sidebar {
                width: 200px;
            }
            
            .main-content {
                margin-left: 200px;
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- Navbar -->
    <div class="navbar">
        <h1>🏪 Store Management System</h1>
        <div class="navbar-right">
            <div class="user-info">
                <div class="user-avatar">{{ username[0]. upper() }}</div>
                <div>
                    <div>{{ username }}</div>
                    <small>Store</small>
                </div>
            </div>
            <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
        </div>
    </div>
    
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="section-title">Store</div>
        <a href="{{ url_for('store_dashboard') }}" class="active">Dashboard</a>
        <a href="{{ url_for('store_products') }}">Products</a>
        <a href="{{ url_for('store_customers') }}">Customers</a>
        
        <div class="section-title">Operations</div>
        <a href="{{ url_for('store_invoices') }}">Invoices</a>
        <a href="{{ url_for('store_estimates') }}">Estimates</a>
        <a href="{{ url_for('store_payments') }}">Payments</a>
        
        <div class="section-title">Admin</div>
        <a href="{{ url_for('store_users') }}">User Management</a>
        <a href="{{ url_for('store_settings') }}">Settings</a>
    </div>
    
    <!-- Main Content -->
    <div class="main-content">
        <h2>Dashboard</h2>
        
        <!-- Statistics Cards -->
        <div class="dashboard-grid">
            <div class="stat-card products">
                <h3>Total Products</h3>
                <div class="number">{{ summary.products_count }}</div>
                <div class="stat-card-subtitle">In Stock</div>
            </div>
            <div class="stat-card customers">
                <h3>Total Customers</h3>
                <div class="number">{{ summary.customers_count }}</div>
                <div class="stat-card-subtitle">Active</div>
            </div>
            <div class="stat-card invoices">
                <h3>Total Invoices</h3>
                <div class="number">{{ summary.invoices_count }}</div>
                <div class="stat-card-subtitle">All Time</div>
            </div>
            <div class="stat-card sales">
                <h3>Monthly Sales</h3>
                <div class="number currency">৳{{ summary.monthly_sales | int }}</div>
                <div class="stat-card-subtitle">This Month</div>
            </div>
            <div class="stat-card due">
                <h3>Total Due</h3>
                <div class="number currency">৳{{ summary.total_due | int }}</div>
                <div class="stat-card-subtitle">Pending</div>
            </div>
        </div>
        
        <!-- Recent Invoices -->
        {% if summary.recent_invoices %}
        <div class="table-container">
            <h3>Recent Invoices</h3>
            <table>
                <thead>
                    <tr>
                        <th>Invoice No</th>
                        <th>Customer</th>
                        <th>Date</th>
                        <th>Total</th>
                        <th>Due</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for invoice in summary.recent_invoices | reverse %}
                    <tr>
                        <td><strong>{{ invoice.invoice_no }}</strong></td>
                        <td>{{ invoice.customer_name }}</td>
                        <td>{{ invoice.date }}</td>
                        <td class="currency">৳{{ invoice. total | int }}</td>
                        <td class="currency">৳{{ invoice.due | int }}</td>
                        <td>
                            {% if invoice.status == 'Paid' %}
                            <span class="badge badge-success">Paid</span>
                            {% elif invoice.status == 'Partially Paid' %}
                            <span class="badge badge-pending">Partially Paid</span>
                            {% else %}
                            <span class="badge badge-draft">{{ invoice.status }}</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </div>
    
    <script>
        // Auto-refresh dashboard data every 30 seconds
        setInterval(() => {
            fetch('{{ url_for("store_get_dashboard_data") }}')
                .then(response => response. json())
                .then(data => {
                    // Update stat cards
                    document.querySelector('.products . number').textContent = data.products_count;
                    document. querySelector('.customers .number').textContent = data.customers_count;
                    document.querySelector('.invoices .number').textContent = data. invoices_count;
                })
                .catch(error => console.error('Error:', error));
        }, 30000);
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE PRODUCTS TEMPLATE
# ==============================================================================

STORE_PRODUCTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Products Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select, textarea {
            padding: 0. 75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-warning {
            background-color: #f39c12;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-warning:hover {
            background-color: #d68910;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-instock {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-lowstock {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-outofstock {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
            overflow-y: auto;
        }
        
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 2rem;
            border: 1px solid #888;
            border-radius: 8px;
            width: 90%;
            max-width: 600px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        . close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        . close:hover {
            color: black;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📦 Products Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Products</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Add New Product Form -->
        <div class="form-section">
            <h3>➕ Add New Product</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Product Name *</label>
                        <input type="text" name="name" placeholder="Product name" required>
                    </div>
                    <div class="form-group">
                        <label>Product Code *</label>
                        <input type="text" name="code" placeholder="Code" required>
                    </div>
                    <div class="form-group">
                        <label>Category</label>
                        <input type="text" name="category" placeholder="Category">
                    </div>
                    <div class="form-group">
                        <label>Unit Price *</label>
                        <input type="number" name="unit_price" step="0.01" min="0" placeholder="0.00" required>
                    </div>
                    <div class="form-group">
                        <label>Stock Quantity *</label>
                        <input type="number" name="stock" min="0" placeholder="0" required>
                    </div>
                    <div class="form-group">
                        <label>Reorder Level</label>
                        <input type="number" name="reorder_level" min="0" value="10">
                    </div>
                </div>
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Description</label>
                    <textarea name="description" placeholder="Product description" rows="3"></textarea>
                </div>
                <button type="submit" class="btn-primary" style="margin-top: 1rem;">Add Product</button>
            </form>
        </div>
        
        <!-- Products List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">📋 Current Products</h3>
            
            {% if products %}
            <table>
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Unit Price</th>
                        <th>Stock</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for product in products %}
                    <tr>
                        <td><strong>{{ product.code }}</strong></td>
                        <td>{{ product.name }}</td>
                        <td>{{ product.category }}</td>
                        <td>৳{{ product.unit_price }}</td>
                        <td>{{ product.stock }}</td>
                        <td>
                            {% if product.stock > product.reorder_level %}
                            <span class="badge badge-instock">In Stock</span>
                            {% elif product.stock > 0 %}
                            <span class="badge badge-lowstock">Low Stock</span>
                            {% else %}
                            <span class="badge badge-outofstock">Out</span>
                            {% endif %}
                        </td>
                        <td>{{ product.created_at }}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn-warning" onclick="openEditModal({{ product | tojson }})">Edit</button>
                                <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this product?');">
                                    <input type="hidden" name="action" value="delete">
                                    <input type="hidden" name="product_id" value="{{ product.id }}">
                                    <button type="submit" class="btn-danger">Delete</button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No products found. Add your first product above.
            </p>
            {% endif %}
        </div>
    </div>
    
    <!-- Edit Product Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>Edit Product</h3>
            <form method="POST" id="editForm">
                <input type="hidden" name="action" value="update">
                <input type="hidden" name="product_id" id="editProductId">
                
                <div class="form-grid" style="margin-top: 1rem;">
                    <div class="form-group">
                        <label>Product Name *</label>
                        <input type="text" name="name" id="editName" required>
                    </div>
                    <div class="form-group">
                        <label>Product Code *</label>
                        <input type="text" name="code" id="editCode" required>
                    </div>
                    <div class="form-group">
                        <label>Category</label>
                        <input type="text" name="category" id="editCategory">
                    </div>
                    <div class="form-group">
                        <label>Unit Price *</label>
                        <input type="number" name="unit_price" id="editUnitPrice" step="0.01" min="0" required>
                    </div>
                    <div class="form-group">
                        <label>Stock Quantity *</label>
                        <input type="number" name="stock" id="editStock" min="0" required>
                    </div>
                    <div class="form-group">
                        <label>Reorder Level</label>
                        <input type="number" name="reorder_level" id="editReorderLevel" min="0">
                    </div>
                </div>
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Description</label>
                    <textarea name="description" id="editDescription" rows="3"></textarea>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="submit" class="btn-primary">Update Product</button>
                    <button type="button" class="btn-secondary" onclick="closeEditModal()" style="background-color: #95a5a6;">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function openEditModal(product) {
            document.getElementById('editProductId').value = product.id;
            document.getElementById('editName'). value = product.name;
            document.getElementById('editCode').value = product.code;
            document.getElementById('editCategory').value = product.category;
            document. getElementById('editUnitPrice').value = product.unit_price;
            document.getElementById('editStock'). value = product.stock;
            document.getElementById('editReorderLevel').value = product.reorder_level;
            document.getElementById('editDescription').value = product.description;
            document.getElementById('editModal').style. display = 'block';
        }
        
        function closeEditModal() {
            document.getElementById('editModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE CUSTOMERS TEMPLATE
# ==============================================================================

STORE_CUSTOMERS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Customers Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select, textarea {
            padding: 0. 75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-warning {
            background-color: #f39c12;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-warning:hover {
            background-color: #d68910;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
            overflow-y: auto;
        }
        
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 2rem;
            border: 1px solid #888;
            border-radius: 8px;
            width: 90%;
            max-width: 600px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        . close:hover {
            color: black;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>👥 Customers Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Customers</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Add New Customer Form -->
        <div class="form-section">
            <h3>➕ Add New Customer</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Customer Name *</label>
                        <input type="text" name="name" placeholder="Full name" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" placeholder="Phone number" required>
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" placeholder="Email address">
                    </div>
                    <div class="form-group">
                        <label>City</label>
                        <input type="text" name="city" placeholder="City">
                    </div>
                    <div class="form-group">
                        <label>Credit Limit</label>
                        <input type="number" name="credit_limit" step="0.01" min="0" placeholder="0.00">
                    </div>
                </div>
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Address</label>
                    <textarea name="address" placeholder="Full address" rows="2"></textarea>
                </div>
                <button type="submit" class="btn-primary" style="margin-top: 1rem;">Add Customer</button>
            </form>
        </div>
        
        <!-- Customers List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">📋 Current Customers</h3>
            
            {% if customers %}
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Phone</th>
                        <th>Email</th>
                        <th>City</th>
                        <th>Credit Limit</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for customer in customers %}
                    <tr>
                        <td><strong>{{ customer.name }}</strong></td>
                        <td>{{ customer.phone }}</td>
                        <td>{{ customer.email or '-' }}</td>
                        <td>{{ customer.city or '-' }}</td>
                        <td>৳{{ customer.credit_limit }}</td>
                        <td>{{ customer.created_at }}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="btn-warning" onclick="openEditModal({{ customer | tojson }})">Edit</button>
                                <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this customer?');">
                                    <input type="hidden" name="action" value="delete">
                                    <input type="hidden" name="customer_id" value="{{ customer.id }}">
                                    <button type="submit" class="btn-danger">Delete</button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No customers found. Add your first customer above.
            </p>
            {% endif %}
        </div>
    </div>
    
    <!-- Edit Customer Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>Edit Customer</h3>
            <form method="POST" id="editForm">
                <input type="hidden" name="action" value="update">
                <input type="hidden" name="customer_id" id="editCustomerId">
                
                <div class="form-grid" style="margin-top: 1rem;">
                    <div class="form-group">
                        <label>Customer Name *</label>
                        <input type="text" name="name" id="editName" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" id="editPhone" required>
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" id="editEmail">
                    </div>
                    <div class="form-group">
                        <label>City</label>
                        <input type="text" name="city" id="editCity">
                    </div>
                    <div class="form-group">
                        <label>Credit Limit</label>
                        <input type="number" name="credit_limit" id="editCreditLimit" step="0.01" min="0">
                    </div>
                </div>
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Address</label>
                    <textarea name="address" id="editAddress" rows="2"></textarea>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="submit" class="btn-primary">Update Customer</button>
                    <button type="button" class="btn-secondary" onclick="closeEditModal()" style="background-color: #95a5a6;">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function openEditModal(customer) {
            document.getElementById('editCustomerId').value = customer.id;
            document.getElementById('editName').value = customer.name;
            document.getElementById('editPhone').value = customer.phone;
            document.getElementById('editEmail'). value = customer.email || '';
            document.getElementById('editCity').value = customer.city || '';
            document.getElementById('editCreditLimit').value = customer. credit_limit || 0;
            document.getElementById('editAddress').value = customer.address || '';
            document.getElementById('editModal').style.display = 'block';
        }
        
        function closeEditModal() {
            document. getElementById('editModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target == modal) {
                modal. style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICES TEMPLATE
# ==============================================================================

STORE_INVOICES_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoices Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            border-bottom: 2px solid #ecf0f1;
        }
        
        .tab-btn {
            padding: 1rem 1.5rem;
            background: none;
            border: none;
            cursor: pointer;
            font-weight: 600;
            color: #7f8c8d;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        . tab-btn.active {
            color: #1f4e78;
            border-bottom-color: #1f4e78;
        }
        
        . tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select, textarea {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        . items-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        
        .items-table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        .items-table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        .items-table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .items-table input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        . btn-add-row {
            background-color: #3498db;
            color: white;
            margin-top: 1rem;
        }
        
        .btn-add-row:hover {
            background-color: #2980b9;
        }
        
        .summary-box {
            background-color: #f9f9f9;
            padding: 1. 5rem;
            border-radius: 8px;
            border-left: 4px solid #f39c12;
            margin-top: 2rem;
        }
        
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .summary-row. total {
            font-weight: bold;
            font-size: 16px;
            border-bottom: 2px solid #1f4e78;
            color: #1f4e78;
        }
        
        . back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0. 75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0. 75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-draft {
            background-color: #e2e3e5;
            color: #383d41;
        }
        
        .badge-finalized {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-pending {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .badge-paid {
            background-color: #d1ecf1;
            color: #0c5460;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .btn-view, .btn-edit, .btn-download {
            font-size: 12px;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            color: white;
        }
        
        .btn-view {
            background-color: #3498db;
        }
        
        .btn-edit {
            background-color: #f39c12;
        }
        
        .btn-download {
            background-color: #27ae60;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>🧾 Invoices Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Invoices</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('create-tab')">Create Invoice</button>
            <button class="tab-btn" onclick="switchTab('list-tab')">View Invoices</button>
        </div>
        
        <!-- Create Tab -->
        <div id="create-tab" class="tab-content active">
            <div class="form-section">
                <h3>➕ Create New Invoice</h3>
                <form method="POST" id="invoiceForm">
                    <input type="hidden" name="action" value="create">
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Customer *</label>
                            <select name="customer_id" id="customerSelect" onchange="updateCustomerName()" required>
                                <option value="">Select Customer</option>
                                {% for customer in customers %}
                                <option value="{{ customer.id }}" data-name="{{ customer.name }}">{{ customer.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Invoice Date *</label>
                            <input type="date" name="date" value="{{ get_bd_date_str() }}" required>
                        </div>
                        <div class="form-group">
                            <label>Due Date</label>
                            <input type="date" name="due_date">
                        </div>
                    </div>
                    
                    <input type="hidden" name="customer_name" id="customerName">
                    
                    <!-- Items Table -->
                    <h3 style="margin-top: 2rem; margin-bottom: 1rem;">Items</h3>
                    <table class="items-table">
                        <thead>
                            <tr>
                                <th>Item Name</th>
                                <th>Quantity</th>
                                <th>Unit Price</th>
                                <th>Discount (৳)</th>
                                <th>Amount</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="itemsBody">
                            <tr>
                                <td><input type="text" name="item_name[]" placeholder="Item name" oninput="calculateTotal()"></td>
                                <td><input type="number" name="quantity[]" min="1" value="1" oninput="calculateTotal()"></td>
                                <td><input type="number" name="unit_price[]" step="0.01" min="0" value="0" oninput="calculateTotal()"></td>
                                <td><input type="number" name="discount[]" step="0.01" min="0" value="0" oninput="calculateTotal()"></td>
                                <td class="amount">0</td>
                                <td><button type="button" class="btn-danger" onclick="removeRow(this)">Remove</button></td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <button type="button" class="btn-add-row" onclick="addItemRow()">+ Add Item</button>
                    
                    <!-- Calculations -->
                    <div class="summary-box">
                        <div class="summary-row">
                            <span>Subtotal:</span>
                            <span id="subtotal">৳0. 00</span>
                        </div>
                        <div class="form-grid" style="margin-top: 1rem;">
                            <div class="form-group">
                                <label>Discount %</label>
                                <input type="number" name="discount_percent" step="0.01" min="0" value="0" id="discountPercent" oninput="calculateTotal()">
                            </div>
                            <div class="form-group">
                                <label>Tax %</label>
                                <input type="number" name="tax_percent" step="0.01" min="0" value="0" id="taxPercent" oninput="calculateTotal()">
                            </div>
                        </div>
                        <div class="summary-row" style="margin-top: 1rem;">
                            <span>Tax:</span>
                            <span id="tax">৳0. 00</span>
                        </div>
                        <div class="summary-row total">
                            <span>TOTAL:</span>
                            <span id="total">৳0.00</span>
                        </div>
                    </div>
                    
                    <!-- Notes -->
                    <div class="form-group" style="margin-top: 2rem;">
                        <label>Notes</label>
                        <textarea name="notes" placeholder="Additional notes" rows="3"></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                        <button type="submit" class="btn-primary">Create Invoice</button>
                        <button type="reset" class="btn-secondary">Clear</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- List Tab -->
        <div id="list-tab" class="tab-content">
            <div class="table-container">
                <h3 style="margin-bottom: 1rem;">📋 All Invoices</h3>
                
                {% if invoices %}
                <table>
                    <thead>
                        <tr>
                            <th>Invoice No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for invoice in invoices | reverse %}
                        <tr>
                            <td><strong>{{ invoice.invoice_no }}</strong></td>
                            <td>{{ invoice.customer_name }}</td>
                            <td>{{ invoice.date }}</td>
                            <td>৳{{ invoice.total | int }}</td>
                            <td>৳{{ invoice.paid | int }}</td>
                            <td>৳{{ invoice.due | int }}</td>
                            <td>
                                {% if invoice. status == 'Paid' %}
                                <span class="badge badge-paid">Paid</span>
                                {% elif invoice.status == 'Partially Paid' %}
                                <span class="badge badge-pending">Partially Paid</span>
                                {% elif invoice.status == 'Finalized' %}
                                <span class="badge badge-finalized">Finalized</span>
                                {% else %}
                                <span class="badge badge-draft">{{ invoice.status }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <a href="{{ url_for('view_invoice', invoice_id=invoice.id) }}" class="btn-view">View</a>
                                    <a href="{{ url_for('download_invoice', invoice_id=invoice.id) }}" class="btn-download">Download</a>
                                    <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this invoice?');">
                                        <input type="hidden" name="action" value="delete">
                                        <input type="hidden" name="invoice_id" value="{{ invoice.id }}">
                                        <button type="submit" class="btn-danger">Delete</button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                    No invoices found. Create your first invoice above.
                </p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function switchTab(tabId) {
            // Hide all tabs
            document.querySelectorAll('.tab-content'). forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            document. getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }
        
        function updateCustomerName() {
            const select = document.getElementById('customerSelect');
            const selectedOption = select.options[select.selectedIndex];
            document.getElementById('customerName').value = selectedOption.getAttribute('data-name') || '';
        }
        
        function addItemRow() {
            const tbody = document.getElementById('itemsBody');
            const newRow = tbody.rows[0].cloneNode(true);
            
            newRow.querySelectorAll('input'). forEach(input => {
                input.value = input.name. includes('quantity') ? '1' : '0';
            });
            
            tbody.appendChild(newRow);
        }
        
        function removeRow(btn) {
            const tbody = document.getElementById('itemsBody');
            if (tbody.rows.length > 1) {
                btn.parentElement.parentElement.remove();
                calculateTotal();
            } else {
                alert('At least one item must remain');
            }
        }
        
        function calculateTotal() {
            const rows = document.querySelectorAll('#itemsBody tr');
            let subtotal = 0;
            
            rows.forEach(row => {
                const quantity = parseFloat(row.querySelector('input[name="quantity[]"]').value) || 0;
                const unitPrice = parseFloat(row.querySelector('input[name="unit_price[]"]').value) || 0;
                const discount = parseFloat(row.querySelector('input[name="discount[]"]').value) || 0;
                const amount = (quantity * unitPrice) - discount;
                
                row.querySelector('.amount').textContent = amount. toFixed(2);
                subtotal += amount;
            });
            
            const discountPercent = parseFloat(document.getElementById('discountPercent').value) || 0;
            const taxPercent = parseFloat(document.getElementById('taxPercent').value) || 0;
            
            const discountAmount = (subtotal * discountPercent) / 100;
            const taxableAmount = subtotal - discountAmount;
            const taxAmount = (taxableAmount * taxPercent) / 100;
            const total = taxableAmount + taxAmount;
            
            document.getElementById('subtotal'). textContent = '৳' + subtotal.toFixed(2);
            document. getElementById('tax').textContent = '৳' + taxAmount.toFixed(2);
            document. getElementById('total').textContent = '৳' + total.toFixed(2);
        }
        
        // Initialize
        calculateTotal();
    </script>
</body>
</html>
"""

# ==============================================================================
# VIEW INVOICE TEMPLATE
# ==============================================================================

VIEW_INVOICE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Invoice - {{ invoice.invoice_no }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 900px;
            margin: 2rem auto;
            background: white;
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .invoice-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 3rem;
            border-bottom: 2px solid #1f4e78;
            padding-bottom: 2rem;
        }
        
        .invoice-title h1 {
            color: #1f4e78;
            font-size: 32px;
            margin-bottom: 0. 5rem;
        }
        
        .invoice-number {
            color: #7f8c8d;
            font-size: 14px;
        }
        
        .invoice-info {
            text-align: right;
        }
        
        .invoice-info div {
            margin-bottom: 0.5rem;
        }
        
        .invoice-info label {
            font-weight: 600;
            color: #1f4e78;
        }
        
        .invoice-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        . detail-block h3 {
            color: #1f4e78;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }
        
        .detail-block p {
            color: #2c3e50;
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 2rem;
        }
        
        table thead {
            background-color: #1f4e78;
            color: white;
        }
        
        table th {
            padding: 1rem;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        . summary {
            margin-left: auto;
            width: 40%;
            background-color: #f9f9f9;
            padding: 1. 5rem;
            border-radius: 8px;
        }
        
        .summary-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.75rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .summary-row. total {
            border-bottom: 2px solid #1f4e78;
            font-weight: bold;
            font-size: 16px;
            color: #1f4e78;
        }
        
        .notes {
            background-color: #f0f8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            margin-bottom: 2rem;
        }
        
        .notes h4 {
            color: #1f4e78;
            margin-bottom: 0.5rem;
        }
        
        .notes p {
            color: #2c3e50;
            line-height: 1.6;
        }
        
        . action-buttons {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 2px solid #ecf0f1;
        }
        
        button, a {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }
        
        . btn-print {
            background-color: #1f4e78;
            color: white;
        }
        
        .btn-print:hover {
            background-color: #162f53;
        }
        
        .btn-download {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-download:hover {
            background-color: #229954;
        }
        
        .btn-back {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-back:hover {
            background-color: #7f8c8d;
        }
        
        @media print {
            body {
                background: white;
            }
            . navbar, .action-buttons {
                display: none;
            }
            .container {
                box-shadow: none;
                margin: 0;
            }
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>🧾 Invoice Viewer</h1>
    </div>
    
    <div class="container">
        <!-- Header -->
        <div class="invoice-header">
            <div class="invoice-title">
                <h1>INVOICE</h1>
                <div class="invoice-number">#{{ invoice.invoice_no }}</div>
            </div>
            <div class="invoice-info">
                <div><label>Date:</label> {{ invoice. date }}</div>
                <div><label>Due Date:</label> {{ invoice.due_date or 'N/A' }}</div>
                <div><label>Status:</label> <strong>{{ invoice.status }}</strong></div>
            </div>
        </div>
        
        <!-- Details -->
        <div class="invoice-details">
            <div class="detail-block">
                <h3>Bill To</h3>
                <p><strong>{{ invoice.customer_name }}</strong></p>
            </div>
            <div class="detail-block"></div>
        </div>
        
        <!-- Items Table -->
        <table>
            <thead>
                <tr>
                    <th>Item</th>
                    <th style="text-align: right;">Quantity</th>
                    <th style="text-align: right;">Unit Price</th>
                    <th style="text-align: right;">Discount</th>
                    <th style="text-align: right;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {% for item in invoice.items %}
                <tr>
                    <td>{{ item.item_name }}</td>
                    <td style="text-align: right;">{{ item.quantity }}</td>
                    <td style="text-align: right;">৳{{ item.unit_price }}</td>
                    <td style="text-align: right;">৳{{ item.discount }}</td>
                    <td style="text-align: right;"><strong>৳{{ item. amount | int }}</strong></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <!-- Summary -->
        <div class="summary">
            <div class="summary-row">
                <span>Subtotal</span>
                <span>৳{{ invoice.subtotal | int }}</span>
            </div>
            <div class="summary-row">
                <span>Discount {{ invoice.discount_percent }}%</span>
                <span>-৳{{ invoice.discount | int }}</span>
            </div>
            <div class="summary-row">
                <span>Tax {{ invoice.tax_percent }}%</span>
                <span>৳{{ invoice.tax | int }}</span>
            </div>
            <div class="summary-row total">
                <span>TOTAL</span>
                <span>৳{{ invoice.total | int }}</span>
            </div>
            <div class="summary-row">
                <span>Paid</span>
                <span>৳{{ invoice.paid | int }}</span>
            </div>
            <div class="summary-row" style="color: #e74c3c; font-weight: bold;">
                <span>DUE</span>
                <span>৳{{ invoice.due | int }}</span>
            </div>
        </div>
        
        <!-- Notes -->
        {% if invoice.notes %}
        <div class="notes">
            <h4>Notes</h4>
            <p>{{ invoice. notes }}</p>
        </div>
        {% endif %}
        
        <!-- Actions -->
        <div class="action-buttons">
            <button class="btn-print" onclick="window.print()">🖨️ Print</button>
            <a href="{{ url_for('download_invoice', invoice_id=invoice.id) }}" class="btn-download">📥 Download PDF</a>
            <a href="{{ url_for('store_invoices') }}" class="btn-back">← Back to Invoices</a>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE ESTIMATES TEMPLATE
# ==============================================================================

STORE_ESTIMATES_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estimates Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #C65911;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #C65911;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .tabs {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            border-bottom: 2px solid #ecf0f1;
        }
        
        .tab-btn {
            padding: 1rem 1.5rem;
            background: none;
            border: none;
            cursor: pointer;
            font-weight: 600;
            color: #7f8c8d;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        . tab-btn. active {
            color: #C65911;
            border-bottom-color: #C65911;
        }
        
        . tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-section {
            background-color: #ffe8d1;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #C65911;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #C65911;
        }
        
        . form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #C65911;
        }
        
        input, select, textarea {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #C65911;
            box-shadow: 0 0 5px rgba(198, 89, 17, 0.3);
        }
        
        . items-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }
        
        .items-table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        .items-table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #C65911;
        }
        
        .items-table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .items-table input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #C65911;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #a83d0d;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        .btn-add-row {
            background-color: #C65911;
            color: white;
            margin-top: 1rem;
        }
        
        .btn-add-row:hover {
            background-color: #a83d0d;
        }
        
        .summary-box {
            background-color: #f9f9f9;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #C65911;
            margin-top: 2rem;
        }
        
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .summary-row. total {
            font-weight: bold;
            font-size: 16px;
            border-bottom: 2px solid #C65911;
            color: #C65911;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #C65911;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0. 75rem;
            text-align: left;
            font-weight: 600;
            color: #C65911;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-draft {
            background-color: #e2e3e5;
            color: #383d41;
        }
        
        .badge-sent {
            background-color: #cfe2ff;
            color: #084298;
        }
        
        .badge-accepted {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-rejected {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        . btn-view, .btn-edit, .btn-download {
            font-size: 12px;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            color: white;
        }
        
        .btn-view {
            background-color: #3498db;
        }
        
        .btn-edit {
            background-color: #f39c12;
        }
        
        .btn-download {
            background-color: #C65911;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📝 Estimates Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Estimates & Quotations</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('create-tab')">Create Estimate</button>
            <button class="tab-btn" onclick="switchTab('list-tab')">View Estimates</button>
        </div>
        
        <!-- Create Tab -->
        <div id="create-tab" class="tab-content active">
            <div class="form-section">
                <h3>➕ Create New Estimate</h3>
                <form method="POST" id="estimateForm">
                    <input type="hidden" name="action" value="create">
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Customer *</label>
                            <select name="customer_id" id="customerSelect" onchange="updateCustomerName()" required>
                                <option value="">Select Customer</option>
                                {% for customer in customers %}
                                <option value="{{ customer.id }}" data-name="{{ customer.name }}">{{ customer.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Estimate Date *</label>
                            <input type="date" name="date" value="{{ get_bd_date_str() }}" required>
                        </div>
                        <div class="form-group">
                            <label>Valid Until</label>
                            <input type="date" name="valid_until">
                        </div>
                    </div>
                    
                    <input type="hidden" name="customer_name" id="customerName">
                    
                    <!-- Items Table -->
                    <h3 style="margin-top: 2rem; margin-bottom: 1rem;">Items</h3>
                    <table class="items-table">
                        <thead>
                            <tr>
                                <th>Item Name</th>
                                <th>Quantity</th>
                                <th>Unit Price</th>
                                <th>Amount</th>
                                <th>Notes</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody id="itemsBody">
                            <tr>
                                <td><input type="text" name="item_name[]" placeholder="Item name" oninput="calculateTotal()"></td>
                                <td><input type="number" name="quantity[]" min="1" value="1" oninput="calculateTotal()"></td>
                                <td><input type="number" name="unit_price[]" step="0.01" min="0" value="0" oninput="calculateTotal()"></td>
                                <td class="amount">0</td>
                                <td><input type="text" name="notes[]" placeholder="Notes"></td>
                                <td><button type="button" class="btn-danger" onclick="removeRow(this)">Remove</button></td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <button type="button" class="btn-add-row" onclick="addItemRow()">+ Add Item</button>
                    
                    <!-- Calculations -->
                    <div class="summary-box">
                        <div class="summary-row">
                            <span>Subtotal:</span>
                            <span id="subtotal">৳0. 00</span>
                        </div>
                        <div class="form-grid" style="margin-top: 1rem;">
                            <div class="form-group">
                                <label>Discount %</label>
                                <input type="number" name="discount_percent" step="0.01" min="0" value="0" id="discountPercent" oninput="calculateTotal()">
                            </div>
                            <div class="form-group">
                                <label>Tax %</label>
                                <input type="number" name="tax_percent" step="0.01" min="0" value="0" id="taxPercent" oninput="calculateTotal()">
                            </div>
                        </div>
                        <div class="summary-row" style="margin-top: 1rem;">
                            <span>Tax:</span>
                            <span id="tax">৳0.00</span>
                        </div>
                        <div class="summary-row total">
                            <span>TOTAL:</span>
                            <span id="total">৳0.00</span>
                        </div>
                    </div>
                    
                    <!-- Notes -->
                    <div class="form-group" style="margin-top: 2rem;">
                        <label>Additional Notes</label>
                        <textarea name="notes" placeholder="Terms, conditions, or additional information" rows="3"></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 1rem; margin-top: 2rem;">
                        <button type="submit" class="btn-primary">Create Estimate</button>
                        <button type="reset" class="btn-secondary">Clear</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- List Tab -->
        <div id="list-tab" class="tab-content">
            <div class="table-container">
                <h3 style="margin-bottom: 1rem;">📋 All Estimates</h3>
                
                {% if estimates %}
                <table>
                    <thead>
                        <tr>
                            <th>Estimate No</th>
                            <th>Customer</th>
                            <th>Date</th>
                            <th>Total</th>
                            <th>Valid Until</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for estimate in estimates | reverse %}
                        <tr>
                            <td><strong>{{ estimate.estimate_no }}</strong></td>
                            <td>{{ estimate. customer_name }}</td>
                            <td>{{ estimate.date }}</td>
                            <td>৳{{ estimate.total | int }}</td>
                            <td>{{ estimate.valid_until or 'N/A' }}</td>
                            <td>
                                {% if estimate.status == 'Accepted' %}
                                <span class="badge badge-accepted">Accepted</span>
                                {% elif estimate.status == 'Rejected' %}
                                <span class="badge badge-rejected">Rejected</span>
                                {% elif estimate.status == 'Sent' %}
                                <span class="badge badge-sent">Sent</span>
                                {% else %}
                                <span class="badge badge-draft">{{ estimate.status }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <a href="{{ url_for('view_estimate', estimate_id=estimate.id) }}" class="btn-view">View</a>
                                    <a href="{{ url_for('download_estimate', estimate_id=estimate.id) }}" class="btn-download">Download</a>
                                    <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this estimate?');">
                                        <input type="hidden" name="action" value="delete">
                                        <input type="hidden" name="estimate_id" value="{{ estimate.id }}">
                                        <button type="submit" class="btn-danger">Delete</button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                    No estimates found. Create your first estimate above.
                </p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-btn'). forEach(btn => {
                btn.classList.remove('active');
            });
            
            document.getElementById(tabId). classList.add('active');
            event.target.classList.add('active');
        }
        
        function updateCustomerName() {
            const select = document.getElementById('customerSelect');
            const selectedOption = select.options[select.selectedIndex];
            document.getElementById('customerName').value = selectedOption.getAttribute('data-name') || '';
        }
        
        function addItemRow() {
            const tbody = document.getElementById('itemsBody');
            const newRow = tbody.rows[0].cloneNode(true);
            
            newRow.querySelectorAll('input'). forEach(input => {
                input.value = input.name. includes('quantity') ? '1' : '0';
            });
            
            tbody.appendChild(newRow);
        }
        
        function removeRow(btn) {
            const tbody = document.getElementById('itemsBody');
            if (tbody.rows.length > 1) {
                btn.parentElement.parentElement.remove();
                calculateTotal();
            } else {
                alert('At least one item must remain');
            }
        }
        
        function calculateTotal() {
            const rows = document.querySelectorAll('#itemsBody tr');
            let subtotal = 0;
            
            rows.forEach(row => {
                const quantity = parseFloat(row.querySelector('input[name="quantity[]"]').value) || 0;
                const unitPrice = parseFloat(row.querySelector('input[name="unit_price[]"]').value) || 0;
                const amount = quantity * unitPrice;
                
                row.querySelector('.amount').textContent = amount.toFixed(2);
                subtotal += amount;
            });
            
            const discountPercent = parseFloat(document.getElementById('discountPercent').value) || 0;
            const taxPercent = parseFloat(document.getElementById('taxPercent').value) || 0;
            
            const discountAmount = (subtotal * discountPercent) / 100;
            const taxableAmount = subtotal - discountAmount;
            const taxAmount = (taxableAmount * taxPercent) / 100;
            const total = taxableAmount + taxAmount;
            
            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document. getElementById('tax').textContent = '৳' + taxAmount.toFixed(2);
            document.getElementById('total').textContent = '৳' + total.toFixed(2);
        }
        
        calculateTotal();
    </script>
</body>
</html>
"""

# ==============================================================================
# VIEW ESTIMATE TEMPLATE
# ==============================================================================

VIEW_ESTIMATE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1. 0">
    <title>Estimate - {{ estimate.estimate_no }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #C65911;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 900px;
            margin: 2rem auto;
            background: white;
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .estimate-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 3rem;
            border-bottom: 2px solid #C65911;
            padding-bottom: 2rem;
        }
        
        .estimate-title h1 {
            color: #C65911;
            font-size: 32px;
            margin-bottom: 0.5rem;
        }
        
        .estimate-number {
            color: #7f8c8d;
            font-size: 14px;
        }
        
        .estimate-info {
            text-align: right;
        }
        
        .estimate-info div {
            margin-bottom: 0.5rem;
        }
        
        .estimate-info label {
            font-weight: 600;
            color: #C65911;
        }
        
        .estimate-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        . detail-block h3 {
            color: #C65911;
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }
        
        .detail-block p {
            color: #2c3e50;
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 2rem;
        }
        
        table thead {
            background-color: #C65911;
            color: white;
        }
        
        table th {
            padding: 1rem;
            text-align: left;
            font-weight: 600;
        }
        
        table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .summary {
            margin-left: auto;
            width: 40%;
            background-color: #f9f9f9;
            padding: 1.5rem;
            border-radius: 8px;
        }
        
        .summary-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.75rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        .summary-row. total {
            border-bottom: 2px solid #C65911;
            font-weight: bold;
            font-size: 16px;
            color: #C65911;
        }
        
        .notes {
            background-color: #ffe8d1;
            padding: 1. 5rem;
            border-radius: 8px;
            border-left: 4px solid #C65911;
            margin-bottom: 2rem;
        }
        
        .notes h4 {
            color: #C65911;
            margin-bottom: 0.5rem;
        }
        
        .notes p {
            color: #2c3e50;
            line-height: 1.6;
        }
        
        . action-buttons {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
            padding-top: 2rem;
            border-top: 2px solid #ecf0f1;
        }
        
        button, a {
            padding: 0. 75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }
        
        . btn-print {
            background-color: #C65911;
            color: white;
        }
        
        .btn-print:hover {
            background-color: #a83d0d;
        }
        
        .btn-download {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-download:hover {
            background-color: #229954;
        }
        
        .btn-back {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-back:hover {
            background-color: #7f8c8d;
        }
        
        @media print {
            body {
                background: white;
            }
            . navbar, .action-buttons {
                display: none;
            }
            . container {
                box-shadow: none;
                margin: 0;
            }
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📝 Estimate Viewer</h1>
    </div>
    
    <div class="container">
        <!-- Header -->
        <div class="estimate-header">
            <div class="estimate-title">
                <h1>ESTIMATE / QUOTATION</h1>
                <div class="estimate-number">#{{ estimate.estimate_no }}</div>
            </div>
            <div class="estimate-info">
                <div><label>Date:</label> {{ estimate.date }}</div>
                <div><label>Valid Until:</label> {{ estimate.valid_until or 'N/A' }}</div>
                <div><label>Status:</label> <strong>{{ estimate.status }}</strong></div>
            </div>
        </div>
        
        <!-- Details -->
        <div class="estimate-details">
            <div class="detail-block">
                <h3>For</h3>
                <p><strong>{{ estimate.customer_name }}</strong></p>
            </div>
            <div class="detail-block"></div>
        </div>
        
        <!-- Items Table -->
        <table>
            <thead>
                <tr>
                    <th>Item</th>
                    <th style="text-align: right;">Quantity</th>
                    <th style="text-align: right;">Unit Price</th>
                    <th style="text-align: right;">Amount</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                {% for item in estimate.items %}
                <tr>
                    <td>{{ item.item_name }}</td>
                    <td style="text-align: right;">{{ item.quantity }}</td>
                    <td style="text-align: right;">৳{{ item.unit_price }}</td>
                    <td style="text-align: right;"><strong>৳{{ item.amount | int }}</strong></td>
                    <td>{{ item.get('notes', '') }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <!-- Summary -->
        <div class="summary">
            <div class="summary-row">
                <span>Subtotal</span>
                <span>৳{{ estimate.subtotal | int }}</span>
            </div>
            {% if estimate.discount_percent > 0 %}
            <div class="summary-row">
                <span>Discount {{ estimate.discount_percent }}%</span>
                <span>-৳{{ estimate.discount | int }}</span>
            </div>
            {% endif %}
            {% if estimate.tax_percent > 0 %}
            <div class="summary-row">
                <span>Tax {{ estimate.tax_percent }}%</span>
                <span>৳{{ estimate.tax | int }}</span>
            </div>
            {% endif %}
            <div class="summary-row total">
                <span>TOTAL</span>
                <span>৳{{ estimate.total | int }}</span>
            </div>
        </div>
        
        <!-- Notes -->
        {% if estimate.notes %}
        <div class="notes">
            <h4>Terms & Conditions</h4>
            <p>{{ estimate.notes }}</p>
        </div>
        {% endif %}
        
        <!-- Actions -->
        <div class="action-buttons">
            <button class="btn-print" onclick="window.print()">🖨️ Print</button>
            <a href="{{ url_for('download_estimate', estimate_id=estimate.id) }}" class="btn-download">📥 Download PDF</a>
            <a href="{{ url_for('store_estimates') }}" class="btn-back">← Back to Estimates</a>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE PAYMENTS TEMPLATE
# ==============================================================================

STORE_PAYMENTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payments Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1. 5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        . stat-card h3 {
            font-size: 14px;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
            opacity: 0.9;
        }
        
        .stat-card . number {
            font-size: 28px;
            font-weight: bold;
        }
        
        .  stat-card. received {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        
        .stat-card.pending {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select, textarea {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        . back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0. 75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0. 25rem 0.75rem;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-success {
            background-color: #d4edda;
            color: #155724;
        }
        
        .badge-pending {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .currency {
            font-weight: bold;
            color: #1f4e78;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>💳 Payments Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Payments</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Statistics -->
        <div class="stats-grid">
            <div class="stat-card received">
                <h3>Total Received</h3>
                <div class="number">৳{{ total_received | int }}</div>
            </div>
            <div class="stat-card pending">
                <h3>Total Pending</h3>
                <div class="number">৳{{ total_pending | int }}</div>
            </div>
            <div class="stat-card">
                <h3>Total Payments</h3>
                <div class="number">{{ payments | length }}</div>
            </div>
        </div>
        
        <!-- Add Payment Form -->
        <div class="form-section">
            <h3>➕ Record Payment</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Invoice *</label>
                        <select name="invoice_id" id="invoiceSelect" onchange="updateInvoiceDetails()" required>
                            <option value="">Select Invoice</option>
                            {% for invoice in invoices %}
                            {% if invoice.due > 0 %}
                            <option value="{{ invoice.id }}" 
                                    data-invoice-no="{{ invoice.invoice_no }}"
                                    data-customer="{{ invoice.customer_name }}"
                                    data-customer-id="{{ invoice.customer_id }}"
                                    data-due="{{ invoice.due }}">
                                {{ invoice.invoice_no }} - {{ invoice.customer_name }} (Due: ৳{{ invoice. due | int }})
                            </option>
                            {% endif %}
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Amount *</label>
                        <input type="number" name="amount" step="0.01" min="0" placeholder="0.00" required>
                    </div>
                    <div class="form-group">
                        <label>Payment Method *</label>
                        <select name="payment_method" required>
                            <option value="">Select Method</option>
                            <option value="Cash">Cash</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="Cheque">Cheque</option>
                            <option value="Card">Card</option>
                            <option value="Online">Online</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Reference / Cheque No</label>
                        <input type="text" name="reference" placeholder="Reference number">
                    </div>
                    <div class="form-group">
                        <label>Payment Date *</label>
                        <input type="date" name="date" required>
                    </div>
                </div>
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Notes</label>
                    <textarea name="notes" placeholder="Additional notes" rows="2"></textarea>
                </div>
                <button type="submit" class="btn-primary" style="margin-top: 1rem;">Record Payment</button>
            </form>
        </div>
        
        <!-- Hidden fields for invoice details -->
        <input type="hidden" id="invoiceNo" name="invoice_no">
        <input type="hidden" id="customerId" name="customer_id">
        <input type="hidden" id="customerName" name="customer_name">
        
        <!-- Payments List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">💰 Payment Records</h3>
            
            {% if payments %}
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Invoice No</th>
                        <th>Customer</th>
                        <th>Amount</th>
                        <th>Method</th>
                        <th>Reference</th>
                        <th>Recorded By</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for payment in payments | reverse %}
                    <tr>
                        <td>{{ payment. date }}</td>
                        <td><strong>{{ payment.invoice_no }}</strong></td>
                        <td>{{ payment.customer_name }}</td>
                        <td class="currency">৳{{ payment. amount | int }}</td>
                        <td><span class="badge badge-success">{{ payment.payment_method }}</span></td>
                        <td>{{ payment.reference or '-' }}</td>
                        <td>{{ payment.created_by }}</td>
                        <td>
                            <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this payment?');">
                                <input type="hidden" name="action" value="delete">
                                <input type="hidden" name="payment_id" value="{{ payment.id }}">
                                <button type="submit" class="btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No payments recorded yet. 
            </p>
            {% endif %}
        </div>
    </div>
    
    <script>
        function updateInvoiceDetails() {
            const select = document.getElementById('invoiceSelect');
            const selectedOption = select.options[select.selectedIndex];
            
            document.getElementById('invoiceNo').value = selectedOption.getAttribute('data-invoice-no') || '';
            document.getElementById('customerId').value = selectedOption. getAttribute('data-customer-id') || '';
            document.getElementById('customerName').value = selectedOption. getAttribute('data-customer') || '';
            
            // Set amount to remaining due
            const dueAmount = selectedOption.getAttribute('data-due') || '0';
            document.querySelector('input[name="amount"]'). value = dueAmount;
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE USERS TEMPLATE
# ==============================================================================

STORE_USERS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Store User Management</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1200px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .alert {
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            border-left: 4px solid #27ae60;
            background-color: #d4edda;
            color: #155724;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1. 5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-warning {
            background-color: #f39c12;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-warning:hover {
            background-color: #d68910;
        }
        
        .btn-danger {
            background-color: #e74c3c;
            color: white;
            font-size: 12px;
            padding: 0.5rem 1rem;
        }
        
        .btn-danger:hover {
            background-color: #c0392b;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .table-container {
            margin-top: 2rem;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        table thead {
            background-color: #ecf0f1;
            border-bottom: 2px solid #bdc3c7;
        }
        
        table th {
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #1f4e78;
        }
        
        table td {
            padding: 0.75rem;
            border-bottom: 1px solid #ecf0f1;
        }
        
        table tbody tr:hover {
            background-color: #f9f9f9;
        }
        
        .badge {
            display: inline-block;
            padding: 0. 25rem 0.75rem;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .badge-admin {
            background-color: #fadbd8;
            color: #922b21;
        }
        
        .badge-manager {
            background-color: #fef5e7;
            color: #7d6608;
        }
        
        .badge-user {
            background-color: #d5f4e6;
            color: #0b5345;
        }
        
        .action-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        
        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 2rem;
            border: 1px solid #888;
            border-radius: 8px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        . close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close:hover {
            color: black;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>👥 Store User Management</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Manage Store Users</h1>
        
        {% if message %}
        <div class="alert">{{ message }}</div>
        {% endif %}
        
        <!-- Add New User Form -->
        <div class="form-section">
            <h3>➕ Create New Store User</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Username *</label>
                        <input type="text" name="new_username" placeholder="Username" required>
                    </div>
                    <div class="form-group">
                        <label>Password *</label>
                        <input type="password" name="new_password" placeholder="Password" required>
                    </div>
                    <div class="form-group">
                        <label>Role *</label>
                        <select name="role" required>
                            <option value="store_user">Store User</option>
                            <option value="store_manager">Store Manager</option>
                            <option value="store_admin">Store Admin</option>
                        </select>
                    </div>
                    <div style="display: flex; align-items: flex-end;">
                        <button type="submit" class="btn-primary">Create User</button>
                    </div>
                </div>
            </form>
        </div>
        
        <!-- Users List -->
        <div class="table-container">
            <h3 style="margin-bottom: 1rem;">📋 Current Store Users</h3>
            
            {% if users %}
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Created At</th>
                        <th>Last Login</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for username, user_data in users.items() %}
                    <tr>
                        <td><strong>{{ username }}</strong></td>
                        <td>
                            <span class="badge badge-{{ user_data.role. split('_')[1] }}">
                                {{ user_data.role | replace('_', ' ') | title }}
                            </span>
                        </td>
                        <td>{{ user_data.created_at }}</td>
                        <td>{{ user_data.last_login }}</td>
                        <td>
                            <div class="action-buttons">
                                {% if username != 'StoreAdmin' %}
                                <button class="btn-warning" onclick="openEditModal('{{ username }}', '{{ user_data.role }}')">Edit</button>
                                <form method="POST" style="display:inline;" onsubmit="return confirm('Delete this user?');">
                                    <input type="hidden" name="action" value="delete">
                                    <input type="hidden" name="del_username" value="{{ username }}">
                                    <button type="submit" class="btn-danger">Delete</button>
                                </form>
                                {% else %}
                                <span style="color: #7f8c8d;">Default Admin</span>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="text-align: center; color: #7f8c8d; padding: 2rem;">
                No users found. 
            </p>
            {% endif %}
        </div>
    </div>
    
    <!-- Edit User Modal -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>Edit Store User</h3>
            <form method="POST" id="editForm">
                <input type="hidden" name="action" value="update">
                <input type="hidden" name="upd_username" id="editUsername">
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Password (Leave empty to keep current)</label>
                    <input type="password" name="upd_password" placeholder="New password">
                </div>
                
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Role *</label>
                    <select name="upd_role" required>
                        <option value="store_user">Store User</option>
                        <option value="store_manager">Store Manager</option>
                        <option value="store_admin">Store Admin</option>
                    </select>
                </div>
                
                <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <button type="submit" class="btn-primary">Update User</button>
                    <button type="button" class="btn-secondary" onclick="closeEditModal()">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        function openEditModal(username, role) {
            document. getElementById('editUsername').value = username;
            document.querySelector('select[name="upd_role"]').value = role;
            document.getElementById('editModal').style. display = 'block';
        }
        
        function closeEditModal() {
            document.getElementById('editModal').style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# STORE SETTINGS TEMPLATE
# ==============================================================================

STORE_SETTINGS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Store Settings</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 900px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .form-section {
            background-color: #ecf8ff;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border-left: 4px solid #3498db;
        }
        
        .form-section h3 {
            margin-bottom: 1rem;
            color: #1f4e78;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
        }
        
        label {
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #1f4e78;
        }
        
        input, select, textarea {
            padding: 0.75rem;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
            font-family: inherit;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
        }
        
        button {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        
        .btn-primary {
            background-color: #27ae60;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #229954;
        }
        
        .btn-secondary {
            background-color: #95a5a6;
            color: white;
        }
        
        .btn-secondary:hover {
            background-color: #7f8c8d;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
        
        .info-box {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 1rem;
            border-radius: 4px;
            margin-top: 2rem;
            color: #155724;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>⚙️ Store Settings</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Store Configuration</h1>
        
        <!-- Store Info -->
        <div class="form-section">
            <h3>🏪 Store Information</h3>
            <form>
                <div class="form-grid">
                    <div class="form-group">
                        <label>Store Name</label>
                        <input type="text" value="{{ config.store_name }}" disabled>
                    </div>
                    <div class="form-group">
                        <label>Phone</label>
                        <input type="tel" value="{{ config.phone }}" disabled>
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" value="{{ config.email }}" disabled>
                    </div>
                </div>
                <div class="form-group" style="margin-top: 1rem;">
                    <label>Address</label>
                    <textarea disabled rows="2">{{ config.address }}</textarea>
                </div>
            </form>
        </div>
        
        <!-- Tax & Currency -->
        <div class="form-section">
            <h3>💰 Tax & Currency Settings</h3>
            <form>
                <div class="form-grid">
                    <div class="form-group">
                        <label>Default Tax %</label>
                        <input type="number" value="{{ config. tax_percent }}" step="0.01" min="0" disabled>
                    </div>
                    <div class="form-group">
                        <label>Currency</label>
                        <input type="text" value="{{ config. currency }}" disabled>
                    </div>
                </div>
            </form>
        </div>
        
        <!-- System Info -->
        <div class="form-section">
            <h3>ℹ️ System Information</h3>
            <div style="padding: 1rem; background: white; border-radius: 4px;">
                <p><strong>System Version:</strong> 1.0.0</p>
                <p><strong>Last Updated:</strong> {{ get_bd_date_str() }}</p>
                <p><strong>Server:</strong> Flask Python</p>
                <p><strong>Database:</strong> MongoDB</p>
            </div>
        </div>
        
        <!-- Backup Info -->
        <div class="info-box">
            <strong>✓ Data Backup:</strong> All data is automatically backed up to MongoDB Cloud.  No manual backup needed.
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# STORE REPORTS TEMPLATE
# ==============================================================================

STORE_REPORTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Store Reports</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .navbar {
            background-color: #1f4e78;
            color: white;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .container {
            max-width: 1400px;
            margin: 2rem auto;
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            margin-bottom: 2rem;
            color: #1f4e78;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1. 5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            padding: 1. 5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #3498db;
            text-align: center;
        }
        
        .stat-card h3 {
            color: #7f8c8d;
            font-size: 13px;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        
        .stat-card .number {
            font-size: 28px;
            font-weight: bold;
            color: #1f4e78;
        }
        
        .stat-card. today {
            border-left-color: #27ae60;
        }
        
        .stat-card.monthly {
            border-left-color: #f39c12;
        }
        
        .stat-card. pending {
            border-left-color: #e74c3c;
        }
        
        .back-btn {
            display: inline-block;
            margin-bottom: 1rem;
            color: #3498db;
            text-decoration: none;
        }
        
        .back-btn:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <h1>📊 Store Reports</h1>
    </div>
    
    <div class="container">
        <a href="{{ url_for('store_dashboard') }}" class="back-btn">← Back to Dashboard</a>
        
        <h1>Business Reports & Analytics</h1>
        
        <!-- Statistics -->
        <div class="stats-grid">
            <div class="stat-card today">
                <h3>Today's Invoices</h3>
                <div class="number">{{ summary.today_invoices }}</div>
                <p style="color: #7f8c8d; margin-top: 0.5rem;">৳{{ summary.today_amount | int }}</p>
            </div>
            <div class="stat-card today">
                <h3>Today's Payments</h3>
                <div class="number">{{ summary. today_payments }}</div>
                <p style="color: #7f8c8d; margin-top: 0.5rem;">৳{{ summary.today_received | int }}</p>
            </div>
            <div class="stat-card monthly">
                <h3>Monthly Total</h3>
                <div class="number">৳{{ summary.monthly_total | int }}</div>
            </div>
            <div class="stat-card monthly">
                <h3>Monthly Received</h3>
                <div class="number">৳{{ summary.monthly_received | int }}</div>
            </div>
            <div class="stat-card pending">
                <h3>Monthly Pending</h3>
                <div class="number">৳{{ summary.monthly_pending | int }}</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# ==============================================================================
# ERROR PAGES
# ==============================================================================

ERROR_404_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .error-container {
            text-align: center;
            color: white;
        }
        
        .error-code {
            font-size: 120px;
            font-weight: bold;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .error-message {
            font-size: 32px;
            margin-bottom: 1rem;
        }
        
        .error-description {
            font-size: 16px;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        
        .btn {
            display: inline-block;
            padding: 1rem 2rem;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-code">404</div>
        <div class="error-message">Page Not Found</div>
        <div class="error-description">The page you are looking for does not exist or has been moved.</div>
        <a href="{{ url_for('login') }}" class="btn">← Go to Login</a>
    </div>
</body>
</html>
"""

ERROR_500_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .error-container {
            text-align: center;
            color: white;
        }
        
        .error-code {
            font-size: 120px;
            font-weight: bold;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .error-message {
            font-size: 32px;
            margin-bottom: 1rem;
        }
        
        .error-description {
            font-size: 16px;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        
        . btn {
            display: inline-block;
            padding: 1rem 2rem;
            background: white;
            color: #f5576c;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-code">500</div>
        <div class="error-message">Server Error</div>
        <div class="error-description">Something went wrong on our end. Please try again later.</div>
        <a href="{{ url_for('login') }}" class="btn">← Go to Login</a>
    </div>
</body>
</html>
"""

# ==============================================================================
# APPLICATION RUN
# ==============================================================================

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║        Office & Store Management System                       ║
    ║        Powered by Flask + MongoDB                             ║
    ║                                                                ║
    ║        Starting Server...                                     ║
    ║        URL: http://localhost:5000                             ║
    ║        Username: Admin                                        ║
    ║        Password: @Nijhum@12                                   ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0. 0', port=5000)
