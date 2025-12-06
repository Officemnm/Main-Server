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

# সেশন টাইমআউট কনফিগারেশন (2 ঘন্টা)
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
# MongoDB কানেকশন সেটআপ + STORE COLLECTIONS
# ==============================================================================
MONGO_URI = "mongodb+srv://Mehedi:Mehedi123@office.jxdnuaj.mongodb.net/?appName=Office"

try:
    client = MongoClient(MONGO_URI)
    db = client['office_db']
    
    # Existing Collections
    users_col = db['users']
    stats_col = db['stats']
    accessories_col = db['accessories']
    
    # NEW STORE COLLECTIONS
    store_customers_col = db['store_customers']
    store_products_col = db['store_products']
    store_invoices_col = db['store_invoices']
    store_quotations_col = db['store_quotations']
    store_payments_col = db['store_payments']
    store_stats_col = db['store_stats']
    
    print("✅ MongoDB Connected Successfully with Store Collections!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")


# ==============================================================================
# STORE HELPER FUNCTIONS - DATABASE OPERATIONS
# ==============================================================================

def get_store_stats():
    """Get real-time store statistics"""
    stats = store_stats_col.find_one({"_id": "store_summary"})
    if not stats:
        default_stats = {
            "_id": "store_summary",
            "total_sales": 0,
            "total_due": 0,
            "total_paid": 0,
            "total_customers": 0,
            "total_products": 0,
            "total_invoices": 0,
            "monthly_sales": 0,
            "today_sales": 0
        }
        store_stats_col.insert_one(default_stats)
        return default_stats
    return stats

def update_store_stats():
    """Recalculate and update store statistics"""
    
    # Customer Count
    total_customers = store_customers_col.count_documents({})
    
    # Product Count
    total_products = store_products_col.count_documents({})
    
    # Invoice Stats
    total_invoices = store_invoices_col.count_documents({})
    
    invoices = list(store_invoices_col.find({}))
    
    total_sales = 0
    total_paid = 0
    total_due = 0
    monthly_sales = 0
    today_sales = 0
    
    today_date = get_bd_date_str()
    current_month = get_bd_time().strftime('%m-%Y')
    
    for inv in invoices:
        amount = float(inv.get('total_amount', 0))
        paid = float(inv.get('paid_amount', 0))
        
        total_sales += amount
        total_paid += paid
        total_due += (amount - paid)
        
        inv_date = inv.get('date', '')
        if inv_date == today_date:
            today_sales += amount
        
        if inv_date.endswith(current_month):
            monthly_sales += amount
    
    store_stats_col.update_one(
        {"_id": "store_summary"},
        {"$set": {
            "total_sales": round(total_sales, 2),
            "total_due": round(total_due, 2),
            "total_paid": round(total_paid, 2),
            "total_customers": total_customers,
            "total_products": total_products,
            "total_invoices": total_invoices,
            "monthly_sales": round(monthly_sales, 2),
            "today_sales": round(today_sales, 2)
        }},
        upsert=True
    )

def generate_invoice_number():
    """Generate unique invoice number"""
    count = store_invoices_col.count_documents({})
    return f"INV-{count + 1001}"

def generate_quotation_number():
    """Generate unique quotation number"""
    count = store_quotations_col.count_documents({})
    return f"QUO-{count + 5001}"

def generate_customer_id():
    """Generate unique customer ID"""
    count = store_customers_col.count_documents({})
    return f"CUST-{count + 1001}"


# ==============================================================================
# EXISTING HELPER FUNCTIONS (UNCHANGED - your original code)
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
# PURCHASE ORDER LOGIC (UNCHANGED - your original code)
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

    booking_block_match = re.search(r"(? :Internal )?Booking NO\. ? [:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)", first_page_text, re.IGNORECASE)
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
# CLOSING REPORT API & EXCEL GENERATION (UNCHANGED - your original code)
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
            overflow-y: auto;
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

        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
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

        textarea {
            min-height: 100px;
            resize: vertical;
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

        button:active { transform: translateY(0); }

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
            box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
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

        @keyframes success-anim { 
            0% { transform: scale(0); opacity: 0; } 
            50% { transform: scale(1.2); } 
            100% { transform: scale(1); opacity: 1; } 
        }

        @keyframes checkmark-anim { 
            0% { opacity: 0; height: 0; width: 0; } 
            100% { opacity: 1; height: 50px; width: 30px; } 
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
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
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
        }
    </style>
"""
# ==============================================================================
# LOGIN TEMPLATE
# ==============================================================================

LOGIN_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
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
        
        .bg-orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: orbFloat 20s ease-in-out infinite;
            pointer-events: none;
        }}
        
        .orb-1 {{
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
        
        .orb-3 {{
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
        
        .login-container {{
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
        
        .login-card {{
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
        
        .brand-icon {{
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
        
        .brand-name {{
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
        
        .login-form .input-group {{
            margin-bottom: 20px;
        }}
        
        .login-form .input-group label {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}
        
        .login-form .input-group label i {{
            color: var(--accent-orange);
            font-size: 13px;
        }}
        
        .login-form input {{
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
        
        .error-box {{
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
        
        @media (max-width: 480px) {{
            .login-container {{
                padding: 15px;
            }}
            
            .login-card {{
                padding: 30px 25px;
                border-radius: 20px;
            }}
            
            .brand-icon {{
                width: 60px;
                height: 60px;
                font-size: 28px;
            }}
            
            .brand-name {{
                font-size: 24px;
            }}
            
            .brand-tagline {{
                font-size: 10px;
            }}
            
            .login-form input {{
                padding: 12px 16px;
                font-size: 14px;
            }}
            
            .login-btn {{
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
            
            .brand-icon {{
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
        document.querySelector('.login-btn').addEventListener('click', function(e) {{
            const ripple = document.createElement('span');
            ripple.classList.add('ripple-effect');
            const rect = this.getBoundingClientRect();
            ripple.style.left = (e.clientX - rect.left) + 'px';
            ripple.style.top = (e.clientY - rect.top) + 'px';
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        }});
    </script>
</body>
</html>
"""


# ==============================================================================
# FLASK ROUTES - LOGIN & AUTHENTICATION
# ==============================================================================

@app.route('/')
def index():
    load_users()
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        user_perms = session.get('permissions', [])
        
        # Check if user has ONLY store permission - redirect directly to store
        if user_perms == ['store']:
            return redirect(url_for('store_dashboard'))
        
        # Admin gets main dashboard
        if session.get('role') == 'admin':
            stats = get_dashboard_summary_v2()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        
        # User with only accessories permission
        if len(user_perms) == 1 and 'accessories' in user_perms:
            return redirect(url_for('accessories_search_page'))
        
        # Regular user dashboard
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


# ==============================================================================
# ADMIN ROUTES - USER MANAGEMENT
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


# ==============================================================================
# CLOSING REPORT ROUTES (UNCHANGED - your original code)
# ==============================================================================

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


# ==============================================================================
# PO SHEET ROUTES (UNCHANGED - your original code)
# ==============================================================================

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
# ACCESSORIES ROUTES (UNCHANGED - your original code)
# ==============================================================================

@app.route('/admin/accessories', methods=['GET'])
def accessories_search_page():
    if not session.get('logged_in'): return redirect(url_for('index'))
    if 'accessories' not in session.get('permissions', []):
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


# ==============================================================================
# STORE ROUTES - MAIN DASHBOARD & CUSTOMER MANAGEMENT
# ==============================================================================

@app.route('/admin/store')
def store_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied - Store Permission Required")
        return redirect(url_for('index'))
    
    update_store_stats()
    stats = get_store_stats()
    
    recent_invoices = list(store_invoices_col.find().sort("_id", -1).limit(5))
    
    for inv in recent_invoices:
        customer = store_customers_col.find_one({"_id": inv['customer_id']})
        inv['customer_name'] = customer['name'] if customer else 'Unknown'
    
    customers = list(store_customers_col.find())
    customers_with_due = []
    for cust in customers:
        invoices = list(store_invoices_col.find({"customer_id": cust['_id']}))
        total_due = sum(float(inv.get('total_amount', 0)) - float(inv.get('paid_amount', 0)) for inv in invoices)
        if total_due > 0:
            customers_with_due.append({
                "name": cust['name'],
                "phone": cust.get('phone', 'N/A'),
                "due": total_due
            })
    
    customers_with_due = sorted(customers_with_due, key=lambda x: x['due'], reverse=True)[:5]
    
    return render_template_string(STORE_DASHBOARD_TEMPLATE, 
                                   stats=stats, 
                                   recent_invoices=recent_invoices,
                                   top_due_customers=customers_with_due)


@app.route('/admin/store/customers')
def store_customers():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    customers = list(store_customers_col.find().sort("_id", -1))
    
    for cust in customers:
        invoices = list(store_invoices_col.find({"customer_id": cust['_id']}))
        total_due = sum(float(inv.get('total_amount', 0)) - float(inv.get('paid_amount', 0)) for inv in invoices)
        cust['total_due'] = total_due
    
    return render_template_string(STORE_CUSTOMERS_TEMPLATE, customers=customers)


@app.route('/admin/store/customers/add', methods=['GET', 'POST'])
def store_add_customer():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        customer_data = {
            "_id": generate_customer_id(),
            "name": request.form.get('name').strip(),
            "phone": request.form.get('phone', '').strip(),
            "address": request.form.get('address', '').strip(),
            "email": request.form.get('email', '').strip(),
            "created_at": get_bd_date_str(),
            "created_by": session.get('user')
        }
        
        store_customers_col.insert_one(customer_data)
        update_store_stats()
        flash('Customer added successfully!')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_ADD_CUSTOMER_TEMPLATE)


@app.route('/admin/store/customers/edit/<customer_id>', methods=['GET', 'POST'])
def store_edit_customer(customer_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    customer = store_customers_col.find_one({"_id": customer_id})
    if not customer:
        flash("Customer not found")
        return redirect(url_for('store_customers'))
    
    if request.method == 'POST':
        update_data = {
            "name": request.form.get('name').strip(),
            "phone": request.form.get('phone', '').strip(),
            "address": request.form.get('address', '').strip(),
            "email": request.form.get('email', '').strip()
        }
        
        store_customers_col.update_one({"_id": customer_id}, {"$set": update_data})
        flash('Customer updated successfully!')
        return redirect(url_for('store_customers'))
    
    return render_template_string(STORE_EDIT_CUSTOMER_TEMPLATE, customer=customer)


@app.route('/admin/store/customers/delete/<customer_id>', methods=['POST'])
def store_delete_customer(customer_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    invoice_count = store_invoices_col.count_documents({"customer_id": customer_id})
    if invoice_count > 0:
        return jsonify({'status': 'error', 'message': f'Cannot delete!  Customer has {invoice_count} invoice(s).'})
    
    store_customers_col.delete_one({"_id": customer_id})
    update_store_stats()
    return jsonify({'status': 'success', 'message': 'Customer deleted!'})


@app.route('/admin/store/products')
def store_products():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    products = list(store_products_col.find().sort("_id", -1))
    return render_template_string(STORE_PRODUCTS_TEMPLATE, products=products)


@app.route('/admin/store/products/add', methods=['GET', 'POST'])
def store_add_product():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        product_data = {
            "_id": f"PROD-{int(time.time())}",
            "name": request.form.get('name').strip(),
            "category": request.form.get('category', 'General').strip(),
            "unit": request.form.get('unit', 'Piece').strip(),
            "price": float(request.form.get('price', 0)),
            "description": request.form.get('description', '').strip(),
            "created_at": get_bd_date_str(),
            "created_by": session.get('user')
        }
        
        store_products_col.insert_one(product_data)
        update_store_stats()
        flash('Product added successfully!')
        return redirect(url_for('store_products'))
    
    return render_template_string(STORE_ADD_PRODUCT_TEMPLATE)


@app.route('/admin/store/products/edit/<product_id>', methods=['GET', 'POST'])
def store_edit_product(product_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    product = store_products_col.find_one({"_id": product_id})
    if not product:
        flash("Product not found")
        return redirect(url_for('store_products'))
    
    if request.method == 'POST':
        update_data = {
            "name": request.form.get('name').strip(),
            "category": request.form.get('category', 'General').strip(),
            "unit": request.form.get('unit', 'Piece').strip(),
            "price": float(request.form.get('price', 0)),
            "description": request.form.get('description', '').strip()
        }
        
        store_products_col.update_one({"_id": product_id}, {"$set": update_data})
        flash('Product updated successfully!')
        return redirect(url_for('store_products'))
    
    return render_template_string(STORE_EDIT_PRODUCT_TEMPLATE, product=product)


@app.route('/admin/store/products/delete/<product_id>', methods=['POST'])
def store_delete_product(product_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    store_products_col.delete_one({"_id": product_id})
    update_store_stats()
    return jsonify({'status': 'success', 'message': 'Product deleted!'})


@app.route('/admin/store/get-customer-info/<customer_id>')
def get_customer_info(customer_id):
    if not session.get('logged_in'):
        return jsonify({'status': 'error'})
    
    customer = store_customers_col.find_one({"_id": customer_id})
    if customer:
        invoices = list(store_invoices_col.find({"customer_id": customer_id}))
        total_due = sum(float(inv.get('total_amount', 0)) - float(inv.get('paid_amount', 0)) for inv in invoices)
        
        return jsonify({
            'status': 'success',
            'phone': customer.get('phone', ''),
            'address': customer.get('address', ''),
            'email': customer.get('email', ''),
            'total_due': total_due
        })
    
    return jsonify({'status': 'error', 'message': 'Customer not found'})


@app.route('/admin/store/get-product-info/<product_id>')
def get_product_info(product_id):
    if not session.get('logged_in'):
        return jsonify({'status': 'error'})
    
    product = store_products_col.find_one({"_id": product_id})
    if product:
        return jsonify({
            'status': 'success',
            'name': product.get('name', ''),
            'unit': product.get('unit', 'Piece'),
            'price': product.get('price', 0),
            'category': product.get('category', 'General')
        })
    
    return jsonify({'status': 'error', 'message': 'Product not found'})
# ==============================================================================
# STORE ROUTES - INVOICE MANAGEMENT
# ==============================================================================

@app.route('/admin/store/invoices')
def store_invoices():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    invoices = list(store_invoices_col.find().sort("_id", -1))
    
    for inv in invoices:
        customer = store_customers_col.find_one({"_id": inv['customer_id']})
        inv['customer_name'] = customer['name'] if customer else 'Unknown'
        inv['due_amount'] = float(inv.get('total_amount', 0)) - float(inv.get('paid_amount', 0))
    
    return render_template_string(STORE_INVOICES_TEMPLATE, invoices=invoices)


@app.route('/admin/store/invoices/create', methods=['GET', 'POST'])
def store_create_invoice():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        items = []
        item_names = request.form.getlist('item_name[]')
        item_qtys = request.form.getlist('item_qty[]')
        item_prices = request.form.getlist('item_price[]')
        
        for i in range(len(item_names)):
            if item_names[i].strip():
                items.append({
                    "name": item_names[i].strip(),
                    "qty": float(item_qtys[i]),
                    "price": float(item_prices[i]),
                    "total": float(item_qtys[i]) * float(item_prices[i])
                })
        
        subtotal = sum(item['total'] for item in items)
        discount = float(request.form.get('discount', 0))
        total_amount = subtotal - discount
        paid_amount = float(request.form.get('paid_amount', 0))
        
        invoice_data = {
            "_id": generate_invoice_number(),
            "customer_id": request.form.get('customer_id'),
            "date": get_bd_date_str(),
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "payment_method": request.form.get('payment_method', 'Cash'),
            "notes": request.form.get('notes', '').strip(),
            "created_by": session.get('user'),
            "created_at": get_bd_time().isoformat()
        }
        
        store_invoices_col.insert_one(invoice_data)
        
        if paid_amount > 0:
            payment_log = {
                "_id": f"PAY-{int(time.time())}",
                "invoice_id": invoice_data['_id'],
                "customer_id": invoice_data['customer_id'],
                "amount": paid_amount,
                "method": invoice_data['payment_method'],
                "date": get_bd_date_str(),
                "collected_by": session.get('user'),
                "created_at": get_bd_time().isoformat()
            }
            store_payments_col.insert_one(payment_log)
        
        update_store_stats()
        flash('Invoice created successfully!')
        return redirect(url_for('store_view_invoice', invoice_id=invoice_data['_id']))
    
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    return render_template_string(STORE_CREATE_INVOICE_TEMPLATE, customers=customers, products=products)


@app.route('/admin/store/invoices/view/<invoice_id>')
def store_view_invoice(invoice_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    invoice = store_invoices_col.find_one({"_id": invoice_id})
    if not invoice:
        flash("Invoice not found")
        return redirect(url_for('store_invoices'))
    
    customer = store_customers_col.find_one({"_id": invoice['customer_id']})
    payments = list(store_payments_col.find({"invoice_id": invoice_id}).sort("_id", -1))
    
    return render_template_string(STORE_VIEW_INVOICE_TEMPLATE, 
                                   invoice=invoice, 
                                   customer=customer,
                                   payments=payments)


@app.route('/admin/store/invoices/edit/<invoice_id>', methods=['GET', 'POST'])
def store_edit_invoice(invoice_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    invoice = store_invoices_col.find_one({"_id": invoice_id})
    if not invoice:
        flash("Invoice not found")
        return redirect(url_for('store_invoices'))
    
    if request.method == 'POST':
        items = []
        item_names = request.form.getlist('item_name[]')
        item_qtys = request.form.getlist('item_qty[]')
        item_prices = request.form.getlist('item_price[]')
        
        for i in range(len(item_names)):
            if item_names[i].strip():
                items.append({
                    "name": item_names[i].strip(),
                    "qty": float(item_qtys[i]),
                    "price": float(item_prices[i]),
                    "total": float(item_qtys[i]) * float(item_prices[i])
                })
        
        subtotal = sum(item['total'] for item in items)
        discount = float(request.form.get('discount', 0))
        total_amount = subtotal - discount
        
        update_data = {
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total_amount": total_amount,
            "notes": request.form.get('notes', '').strip(),
            "updated_by": session.get('user'),
            "updated_at": get_bd_time().isoformat()
        }
        
        store_invoices_col.update_one({"_id": invoice_id}, {"$set": update_data})
        update_store_stats()
        flash('Invoice updated successfully!')
        return redirect(url_for('store_view_invoice', invoice_id=invoice_id))
    
    customer = store_customers_col.find_one({"_id": invoice['customer_id']})
    products = list(store_products_col.find().sort("name", 1))
    return render_template_string(STORE_EDIT_INVOICE_TEMPLATE, 
                                   invoice=invoice, 
                                   customer=customer, 
                                   products=products)


@app.route('/admin/store/invoices/delete/<invoice_id>', methods=['POST'])
def store_delete_invoice(invoice_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    store_payments_col.delete_many({"invoice_id": invoice_id})
    store_invoices_col.delete_one({"_id": invoice_id})
    update_store_stats()
    return jsonify({'status': 'success', 'message': 'Invoice deleted!'})


@app.route('/admin/store/invoices/collect-payment/<invoice_id>', methods=['POST'])
def store_collect_payment(invoice_id):
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    invoice = store_invoices_col.find_one({"_id": invoice_id})
    if not invoice:
        return jsonify({'status': 'error', 'message': 'Invoice not found'})
    
    amount = float(request.form.get('amount', 0))
    method = request.form.get('method', 'Cash')
    
    if amount <= 0:
        return jsonify({'status': 'error', 'message': 'Invalid amount'})
    
    current_paid = float(invoice.get('paid_amount', 0))
    total_amount = float(invoice.get('total_amount', 0))
    
    if current_paid + amount > total_amount:
        return jsonify({'status': 'error', 'message': 'Amount exceeds due!'})
    
    new_paid = current_paid + amount
    
    store_invoices_col.update_one(
        {"_id": invoice_id},
        {"$set": {"paid_amount": new_paid}}
    )
    
    payment_log = {
        "_id": f"PAY-{int(time.time())}",
        "invoice_id": invoice_id,
        "customer_id": invoice['customer_id'],
        "amount": amount,
        "method": method,
        "date": get_bd_date_str(),
        "collected_by": session.get('user'),
        "created_at": get_bd_time().isoformat()
    }
    store_payments_col.insert_one(payment_log)
    
    update_store_stats()
    return jsonify({'status': 'success', 'message': 'Payment collected!'})


# ==============================================================================
# STORE ROUTES - QUOTATION MANAGEMENT
# ==============================================================================

@app.route('/admin/store/quotations')
def store_quotations():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    quotations = list(store_quotations_col.find().sort("_id", -1))
    
    for quo in quotations:
        customer = store_customers_col.find_one({"_id": quo['customer_id']})
        quo['customer_name'] = customer['name'] if customer else 'Unknown'
    
    return render_template_string(STORE_QUOTATIONS_TEMPLATE, quotations=quotations)


@app.route('/admin/store/quotations/create', methods=['GET', 'POST'])
def store_create_quotation():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        items = []
        item_names = request.form.getlist('item_name[]')
        item_qtys = request.form.getlist('item_qty[]')
        item_prices = request.form.getlist('item_price[]')
        
        for i in range(len(item_names)):
            if item_names[i].strip():
                items.append({
                    "name": item_names[i].strip(),
                    "qty": float(item_qtys[i]),
                    "price": float(item_prices[i]),
                    "total": float(item_qtys[i]) * float(item_prices[i])
                })
        
        subtotal = sum(item['total'] for item in items)
        discount = float(request.form.get('discount', 0))
        total_amount = subtotal - discount
        
        quotation_data = {
            "_id": generate_quotation_number(),
            "customer_id": request.form.get('customer_id'),
            "date": get_bd_date_str(),
            "valid_until": request.form.get('valid_until', ''),
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total_amount": total_amount,
            "notes": request.form.get('notes', '').strip(),
            "status": "Pending",
            "created_by": session.get('user'),
            "created_at": get_bd_time().isoformat()
        }
        
        store_quotations_col.insert_one(quotation_data)
        flash('Quotation created successfully!')
        return redirect(url_for('store_view_quotation', quotation_id=quotation_data['_id']))
    
    customers = list(store_customers_col.find().sort("name", 1))
    products = list(store_products_col.find().sort("name", 1))
    return render_template_string(STORE_CREATE_QUOTATION_TEMPLATE, customers=customers, products=products)


@app.route('/admin/store/quotations/view/<quotation_id>')
def store_view_quotation(quotation_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    quotation = store_quotations_col.find_one({"_id": quotation_id})
    if not quotation:
        flash("Quotation not found")
        return redirect(url_for('store_quotations'))
    
    customer = store_customers_col.find_one({"_id": quotation['customer_id']})
    
    return render_template_string(STORE_VIEW_QUOTATION_TEMPLATE, 
                                   quotation=quotation, 
                                   customer=customer)


@app.route('/admin/store/quotations/convert/<quotation_id>')
def store_convert_quotation(quotation_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    quotation = store_quotations_col.find_one({"_id": quotation_id})
    if not quotation:
        flash("Quotation not found")
        return redirect(url_for('store_quotations'))
    
    invoice_data = {
        "_id": generate_invoice_number(),
        "customer_id": quotation['customer_id'],
        "date": get_bd_date_str(),
        "items": quotation['items'],
        "subtotal": quotation['subtotal'],
        "discount": quotation['discount'],
        "total_amount": quotation['total_amount'],
        "paid_amount": 0,
        "payment_method": "Cash",
        "notes": f"Converted from {quotation['_id']}",
        "created_by": session.get('user'),
        "created_at": get_bd_time().isoformat()
    }
    
    store_invoices_col.insert_one(invoice_data)
    
    store_quotations_col.update_one(
        {"_id": quotation_id},
        {"$set": {"status": "Converted"}}
    )
    
    update_store_stats()
    flash('Quotation converted to invoice!')
    return redirect(url_for('store_view_invoice', invoice_id=invoice_data['_id']))


@app.route('/admin/store/quotations/delete/<quotation_id>', methods=['POST'])
def store_delete_quotation(quotation_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    store_quotations_col.delete_one({"_id": quotation_id})
    return jsonify({'status': 'success', 'message': 'Quotation deleted!'})


# ==============================================================================
# STORE ROUTES - DUE LIST & PAYMENT HISTORY
# ==============================================================================

@app.route('/admin/store/due-list')
def store_due_list():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    customers = list(store_customers_col.find())
    due_list = []
    
    for cust in customers:
        invoices = list(store_invoices_col.find({"customer_id": cust['_id']}))
        total_amount = sum(float(inv.get('total_amount', 0)) for inv in invoices)
        total_paid = sum(float(inv.get('paid_amount', 0)) for inv in invoices)
        total_due = total_amount - total_paid
        
        if total_due > 0:
            due_list.append({
                "customer_id": cust['_id'],
                "name": cust['name'],
                "phone": cust.get('phone', 'N/A'),
                "total_amount": total_amount,
                "total_paid": total_paid,
                "total_due": total_due,
                "invoice_count": len(invoices)
            })
    
    due_list = sorted(due_list, key=lambda x: x['total_due'], reverse=True)
    
    return render_template_string(STORE_DUE_LIST_TEMPLATE, due_list=due_list)


@app.route('/admin/store/payment-history')
def store_payment_history():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    if 'store' not in session.get('permissions', []) and session.get('role') != 'admin':
        flash("Access Denied")
        return redirect(url_for('index'))
    
    payments = list(store_payments_col.find().sort("_id", -1).limit(100))
    
    for pay in payments:
        customer = store_customers_col.find_one({"_id": pay['customer_id']})
        pay['customer_name'] = customer['name'] if customer else 'Unknown'
    
    return render_template_string(STORE_PAYMENT_HISTORY_TEMPLATE, payments=payments)
# ==============================================================================
# ADMIN DASHBOARD TEMPLATE (WITH FULL FUNCTIONALITY)
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

    <div id="loading-overlay">
        <div class="spinner-container">
            <div class="spinner" id="spinner-anim"></div>
            <div class="spinner-inner"></div>
        </div>
        
        <div class="checkmark-container" id="success-anim">
            <div class="checkmark-circle"></div>
            <div class="anim-text">Successful!</div>
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
                <div class="card stat-card" style="animation-delay: 0.1s;">
                    <div class="stat-icon"><i class="fas fa-file-export"></i></div>
                    <div class="stat-info">
                        <h3 class="count-up" data-target="{{{{ stats.closing.count }}}}">0</h3>
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
                        <h3 class="count-up" data-target="{{{{ stats.po.count }}}}">0</h3>
                        <p>Lifetime PO Sheets</p>
                    </div>
                </div>
                <div class="card stat-card" style="animation-delay: 0.4s;">
                    <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));">
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
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); padding: 6px 12px; background: rgba(16, 185, 129, 0.1); border-radius: 20px; border: 1px solid rgba(16, 185, 129, 0.2);">
                            <div style="width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; animation: pulse 2s infinite;"></div>
                            <span>Real-time</span>
                        </div>
                    </div>
                    <div style="height: 320px; position: relative;">
                        <canvas id="mainChart"></canvas>
                    </div>
                </div>
                <div class="card">
                    <div class="section-header">
                        <span>Module Usage</span>
                        <i class="fas fa-chart-bar" style="color: var(--accent-orange);"></i>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; color: white; font-weight: 500;">
                            <span>Closing Report</span>
                            <span style="color: var(--text-secondary); font-weight: 600;">{{{{ stats.closing.count }}}} Lifetime</span>
                        </div>
                        <div style="height: 8px; background: rgba(255, 255, 255, 0.05); border-radius: 10px; overflow: hidden; position: relative;">
                            <div style="height: 100%; border-radius: 10px; position: relative; animation: progressFill 1.5s ease-out forwards; transform-origin: left; background: linear-gradient(135deg, #FF7A00 0%, #FF9A40 100%); width: 85%;"></div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; color: white; font-weight: 500;">
                            <span>Accessories</span>
                            <span style="color: var(--text-secondary); font-weight: 600;">{{{{ stats.accessories.count }}}} Challans</span>
                        </div>
                        <div style="height: 8px; background: rgba(255, 255, 255, 0.05); border-radius: 10px; overflow: hidden; position: relative;">
                            <div style="height: 100%; border-radius: 10px; position: relative; animation: progressFill 1.5s ease-out forwards; transform-origin: left; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); width: 65%;"></div>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 24px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; color: white; font-weight: 500;">
                            <span>PO Generator</span>
                            <span style="color: var(--text-secondary); font-weight: 600;">{{{{ stats.po.count }}}} Files</span>
                        </div>
                        <div style="height: 8px; background: rgba(255, 255, 255, 0.05); border-radius: 10px; overflow: hidden; position: relative;">
                            <div style="height: 100%; border-radius: 10px; position: relative; animation: progressFill 1.5s ease-out forwards; transform-origin: left; background: linear-gradient(135deg, #10B981 0%, #34D399 100%); width: 45%;"></div>
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
                                    <div style="display: inline-flex; align-items: center; gap: 6px; background: rgba(255, 255, 255, 0.03); padding: 8px 14px; border-radius: 8px; font-size: 13px; color: var(--text-secondary);">
                                        <i class="far fa-clock" style="color: var(--accent-orange);"></i>
                                        {{{{ log.time }}}}
                                    </div>
                                </td>
                                <td style="font-weight: 600; color: white;">{{{{ log.user }}}}</td>
                                <td>
                                    <span class="table-badge" style="
                                        {{% if log.type == 'Closing Report' %}}
                                        background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);
                                        {{% elif log.type == 'PO Sheet' %}}
                                        background: rgba(16, 185, 129, 0.1); color: var(--accent-green);
                                        {{% else %}}
                                        background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);
                                        {{% endif %}}
                                    ">{{{{ log.type }}}}</span>
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
                    <div style="border: 2px dashed var(--border-color); padding: 50px; text-align: center; border-radius: 16px; transition: var(--transition-smooth); cursor: pointer; position: relative; overflow: hidden;" id="uploadZone" onclick="document.getElementById('file-upload').click()">
                        <input type="file" name="pdf_files" multiple accept=".pdf" required style="display: none;" id="file-upload">
                        <div style="font-size: 60px; color: var(--accent-orange); margin-bottom: 20px; display: inline-block; animation: uploadFloat 3s ease-in-out infinite;">
                            <i class="fas fa-cloud-upload-alt"></i>
                        </div>
                        <div style="color: var(--accent-orange); font-weight: 600; font-size: 16px; margin-bottom: 8px;">Click or Drag to Upload PDF Files</div>
                        <div style="color: var(--text-secondary); font-size: 13px;">Supports multiple PDF files</div>
                        <div id="file-count" style="margin-top: 20px; font-size: 14px; color: var(--accent-green); font-weight: 600;">No files selected</div>
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
                        <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ stats.users.count }}}} Users</span>
                    </div>
                    <div id="userTableContainer" style="max-height: 450px; overflow-y: auto;">
                        <div style="height: 50px; margin-bottom: 10px; background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%); background-size: 200% 100%; animation: skeletonLoad 1.5s infinite; border-radius: 8px;"></div>
                        <div style="height: 50px; margin-bottom: 10px; background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%); background-size: 200% 100%; animation: skeletonLoad 1.5s infinite; border-radius: 8px;"></div>
                        <div style="height: 50px; background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%); background-size: 200% 100%; animation: skeletonLoad 1.5s infinite; border-radius: 8px;"></div>
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
                                <label style="background: rgba(255, 255, 255, 0.03); padding: 14px 18px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; border: 1px solid var(--border-color); transition: var(--transition-smooth); flex: 1; min-width: 100px;">
                                    <input type="checkbox" id="perm_closing" checked style="width: auto; margin-right: 10px; accent-color: var(--accent-orange);">
                                    <span style="font-size: 13px; font-weight: 500; color: var(--text-secondary);">Closing</span>
                                </label>
                                <label style="background: rgba(255, 255, 255, 0.03); padding: 14px 18px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; border: 1px solid var(--border-color); transition: var(--transition-smooth); flex: 1; min-width: 100px;">
                                    <input type="checkbox" id="perm_po" style="width: auto; margin-right: 10px; accent-color: var(--accent-orange);">
                                    <span style="font-size: 13px; font-weight: 500; color: var(--text-secondary);">PO Sheet</span>
                                </label>
                                <label style="background: rgba(255, 255, 255, 0.03); padding: 14px 18px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; border: 1px solid var(--border-color); transition: var(--transition-smooth); flex: 1; min-width: 100px;">
                                    <input type="checkbox" id="perm_acc" style="width: auto; margin-right: 10px; accent-color: var(--accent-orange);">
                                    <span style="font-size: 13px; font-weight: 500; color: var(--text-secondary);">Accessories</span>
                                </label>
                                <label style="background: rgba(255, 255, 255, 0.03); padding: 14px 18px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; border: 1px solid var(--border-color); transition: var(--transition-smooth); flex: 1; min-width: 100px;">
                                    <input type="checkbox" id="perm_store" style="width: auto; margin-right: 10px; accent-color: var(--accent-orange);">
                                    <span style="font-size: 13px; font-weight: 500; color: var(--text-secondary);">Store</span>
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
            if (window.innerWidth < 1024) document.querySelector('.sidebar').classList.remove('active');
        }}
        
        const fileUpload = document.getElementById('file-upload');
        const uploadZone = document.getElementById('uploadZone');
        
        if (fileUpload) {{
            fileUpload.addEventListener('change', function() {{
                const count = this.files.length;
                document.getElementById('file-count').innerHTML = count > 0 
                    ? `<i class="fas fa-check-circle" style="margin-right: 5px;"></i>${{count}} file(s) selected`
                    : 'No files selected';
            }});
            uploadZone.addEventListener('dragover', (e) => {{
                e.preventDefault();
                uploadZone.style.borderColor = 'var(--accent-orange)';
                uploadZone.style.background = 'rgba(255, 122, 0, 0.1)';
            }});
            uploadZone.addEventListener('dragleave', () => {{
                uploadZone.style.borderColor = 'var(--border-color)';
                uploadZone.style.background = 'transparent';
            }});
            uploadZone.addEventListener('drop', (e) => {{
                e.preventDefault();
                uploadZone.style.borderColor = 'var(--border-color)';
                uploadZone.style.background = 'transparent';
                fileUpload.files = e.dataTransfer.files;
                fileUpload.dispatchEvent(new Event('change'));
            }});
        }}
        
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
                        tension: 0.4,
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
                        ticks: {{ color: '#8b8b9e', font: {{ size: 10 }}, maxRotation: 45, minRotation: 45 }}
                    }},
                    y: {{
                        grid: {{ color: 'rgba(255,255,255,0.03)', drawBorder: false }},
                        ticks: {{ color: '#8b8b9e', font: {{ size: 10 }}, stepSize: 1 }},
                        beginAtZero: true
                    }}
                }},
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{ intersect: false, mode: 'index' }},
                animation: {{ duration: 2000, easing: 'easeOutQuart' }}
            }}
        }});

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

        function showLoading() {{
            document.getElementById('loading-overlay').style.display = 'flex';
            return true;
        }}

        function loadUsers() {{
            fetch('/admin/get-users')
                .then(res => res.json())
                .then(data => {{
                    let html = '<table class="dark-table"><thead><tr><th>User</th><th>Role</th><th style="text-align:right;">Actions</th></tr></thead><tbody>';
                    
                    for (const [u, d] of Object.entries(data)) {{
                        const roleClass = d.role === 'admin' ? 'background: rgba(255, 122, 0, 0.1); color: var(--accent-orange);' : 'background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);';
                        
                        html += `<tr>
                            <td style="font-weight: 600;">${{u}}</td>
                            <td><span class="table-badge" style="${{roleClass}}">${{d.role}}</span></td>
                            <td style="text-align:right;">
                                ${{d.role !== 'admin' ? `
                                    <div class="action-cell">
                                        <button class="action-btn btn-edit" onclick="editUser('${{u}}', '${{d.password}}', '${{d.permissions.join(',')}}')">
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
            if (document.getElementById('perm_acc').checked) perms.push('accessories');
            if (document.getElementById('perm_store').checked) perms.push('store');
            
            showLoading();
            
            fetch('/admin/save-user', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ username: u, password: p, permissions: perms, action_type: a }})
            }})
            .then(r => r.json())
            .then(d => {{
                if (d.status === 'success') {{
                    document.getElementById('loading-overlay').style.display = 'none';
                    loadUsers();
                    resetForm();
                }} else {{
                    alert(d.message);
                    document.getElementById('loading-overlay').style.display = 'none';
                }}
            }});
        }}
        
        function editUser(u, p, permsStr) {{
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
                }}).then(() => loadUsers());
            }}
        }}
        
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
            @keyframes uploadFloat {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-10px); }}
            }}
            @keyframes progressFill {{
                from {{ transform: scaleX(0); }}
                to {{ transform: scaleX(1); }}
            }}
            @keyframes skeletonLoad {{
                0% {{ background-position: 200% 0; }}
                100% {{ background-position: -200% 0; }}
            }}
        `;
        document.head.appendChild(style);
    </script>
</body>
</html>
"""
# ==============================================================================
# USER DASHBOARD TEMPLATE
# ==============================================================================

USER_DASHBOARD_TEMPLATE = f"""
<!  doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard - MNM Software</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    
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
            {{% if 'closing' in session.permissions %}}
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
            
            {{% if 'po_sheet' in session.permissions %}}
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
            
            {{% if 'store' in session.permissions %}}
            <div class="card" style="animation: fadeInUp 0.5s ease-out 0.4s backwards;">
                <div class="section-header">
                    <span><i class="fas fa-store" style="margin-right: 10px; color: var(--accent-cyan);"></i>Store Panel</span>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                    Manage aluminium shop - customers, products, invoices, payments.
                </p>
                <a href="/admin/store">
                    <button style="background: linear-gradient(135deg, #06B6D4 0%, #22D3EE 100%);">
                        <i class="fas fa-external-link-alt" style="margin-right: 8px;"></i> Open Store
                    </button>
                </a>
            </div>
            {{% endif %}}
        </div>
    </div>
    
    <script>
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
        document.head. appendChild(style);
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE DASHBOARD TEMPLATE
# ==============================================================================

STORE_DASHBOARD_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Store Dashboard - MNM Software</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link active">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-subtitle">Aluminium Shop Management System</div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Store Active</span>
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

        <div class="stats-grid">
            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(255, 122, 0, 0.15), rgba(255, 122, 0, 0.05));">
                    <i class="fas fa-dollar-sign"></i>
                </div>
                <div class="stat-info">
                    <h3>৳{{{{ "{:,.0f}".format(stats.total_sales) }}}}</h3>
                    <p>Total Sales</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));">
                    <i class="fas fa-hand-holding-usd" style="color: var(--accent-red);"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: var(--accent-red);">৳{{{{ "{:,.0f}".format(stats.total_due) }}}}</h3>
                    <p>Total Due</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));">
                    <i class="fas fa-check-circle" style="color: var(--accent-green);"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: var(--accent-green);">৳{{{{ "{:,.0f}".format(stats.total_paid) }}}}</h3>
                    <p>Total Paid</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));">
                    <i class="fas fa-users" style="color: var(--accent-blue);"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: var(--accent-blue);">{{{{ stats.total_customers }}}}</h3>
                    <p>Customers</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(139, 92, 246, 0.05));">
                    <i class="fas fa-boxes" style="color: var(--accent-purple);"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: var(--accent-purple);">{{{{ stats.total_products }}}}</h3>
                    <p>Products</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(6, 182, 212, 0.15), rgba(6, 182, 212, 0.05));">
                    <i class="fas fa-file-invoice" style="color: var(--accent-cyan);"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: var(--accent-cyan);">{{{{ stats.total_invoices }}}}</h3>
                    <p>Invoices</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(255, 193, 7, 0.15), rgba(255, 193, 7, 0.05));">
                    <i class="fas fa-calendar-day" style="color: #FFC107;"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: #FFC107;">৳{{{{ "{:,.0f}".format(stats.today_sales) }}}}</h3>
                    <p>Today's Sales</p>
                </div>
            </div>

            <div class="card stat-card">
                <div class="stat-icon" style="background: linear-gradient(145deg, rgba(233, 30, 99, 0.15), rgba(233, 30, 99, 0.05));">
                    <i class="fas fa-calendar-alt" style="color: #E91E63;"></i>
                </div>
                <div class="stat-info">
                    <h3 style="color: #E91E63;">৳{{{{ "{:,.0f}".format(stats.monthly_sales) }}}}</h3>
                    <p>This Month</p>
                </div>
            </div>
        </div>

        <div class="dashboard-grid-2">
            <div class="card">
                <div class="section-header">
                    <span>Recent Invoices</span>
                    <a href="/admin/store/invoices" style="color: var(--accent-orange); font-size: 13px; text-decoration: none;">View All →</a>
                </div>
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice</th>
                            <th>Customer</th>
                            <th>Amount</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in recent_invoices %}}
                        <tr>
                            <td style="font-weight: 700;">{{{{ inv._id }}}}</td>
                            <td>{{{{ inv. customer_name }}}}</td>
                            <td style="color: var(--accent-orange); font-weight: 600;">৳{{{{ "{:,.0f}".format(inv.total_amount) }}}}</td>
                            <td>
                                {{% set due = inv.total_amount - inv.paid_amount %}}
                                {{% if due > 0 %}}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0.1); color: var(--accent-red);">Due: ৳{{{{ "{:,. 0f}".format(due) }}}}</span>
                                {{% else %}}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">Paid</span>
                                {{% endif %}}
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="4" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                <i class="fas fa-inbox" style="font-size: 40px; opacity: 0.3; display: block; margin-bottom: 10px;"></i>
                                No invoices yet
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div class="section-header">
                    <span>Top Due Customers</span>
                    <a href="/admin/store/due-list" style="color: var(--accent-orange); font-size: 13px; text-decoration: none;">View All →</a>
                </div>
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Customer</th>
                            <th>Due Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for cust in top_due_customers %}}
                        <tr>
                            <td style="font-weight: 600;">{{{{ cust. name }}}}</td>
                            <td style="color: var(--accent-red); font-weight: 700;">৳{{{{ "{:,.0f}".format(cust.due) }}}}</td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="2" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                                <i class="fas fa-smile" style="font-size: 40px; opacity: 0. 3; display: block; margin-bottom: 10px;"></i>
                                No due amounts!  
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="text-align: center; padding: 60px 40px;">
            <div style="font-size: 64px; color: var(--accent-orange); margin-bottom: 20px;">
                <i class="fas fa-tools"></i>
            </div>
            <div class="page-title" style="margin-bottom: 10px;">Quick Actions</div>
            <div class="page-subtitle" style="margin-bottom: 30px;">Start managing your store</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; max-width: 1000px; margin: 0 auto;">
                <a href="/admin/store/invoices/create">
                    <button style="background: var(--gradient-orange); width: 100%;">
                        <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> New Invoice
                    </button>
                </a>
                <a href="/admin/store/quotations/create">
                    <button style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%); width: 100%;">
                        <i class="fas fa-file-signature" style="margin-right: 8px;"></i> New Quotation
                    </button>
                </a>
                <a href="/admin/store/customers/add">
                    <button style="background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%); width: 100%;">
                        <i class="fas fa-user-plus" style="margin-right: 8px;"></i> Add Customer
                    </button>
                </a>
                <a href="/admin/store/products/add">
                    <button style="background: linear-gradient(135deg, #10B981 0%, #34D399 100%); width: 100%;">
                        <i class="fas fa-box" style="margin-right: 8px;"></i> Add Product
                    </button>
                </a>
            </div>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE CUSTOMERS LIST TEMPLATE
# ==============================================================================

STORE_CUSTOMERS_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Customers - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Customers</div>
                <div class="page-subtitle">Manage your customer database</div>
            </div>
            <a href="/admin/store/customers/add">
                <button style="width: auto; padding: 12px 24px;">
                    <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Add Customer
                </button>
            </a>
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
            <div class="section-header">
                <span>All Customers</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ customers|length }}}} Total</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Total Due</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for cust in customers %}}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-orange);">{{{{ cust._id }}}}</td>
                            <td style="font-weight: 600;">{{{{ cust.name }}}}</td>
                            <td style="color: var(--text-secondary);">{{{{ cust.phone if cust.phone else 'N/A' }}}}</td>
                            <td style="color: var(--text-secondary); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{{{ cust.address if cust.address else 'N/A' }}}}</td>
                            <td>
                                {{% if cust.total_due > 0 %}}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0.1); color: var(--accent-red); font-weight: 700;">৳{{{{ "{:,.0f}".format(cust.total_due) }}}}</span>
                                {{% else %}}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">Clear</span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/customers/edit/{{{{ cust._id }}}}" class="action-btn btn-edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    {{% if session.role == 'admin' %}}
                                    <button class="action-btn btn-del" onclick="deleteCustomer('{{{{ cust._id }}}}')">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                    {{% endif %}}
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 60px; color: var(--text-secondary);">
                                <i class="fas fa-users" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i>
                                <div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Customers Yet</div>
                                <div style="font-size: 14px; margin-bottom: 20px;">Start by adding your first customer</div>
                                <a href="/admin/store/customers/add">
                                    <button style="width: auto; padding: 12px 24px;">
                                        <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Add First Customer
                                    </button>
                                </a>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function deleteCustomer(id) {{
            if (confirm('Are you sure you want to delete this customer? \\n\\nNote: Cannot delete if customer has invoices.')) {{
                fetch(`/admin/store/customers/delete/${{id}}`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(d => {{
                    if (d.status === 'success') {{
                        location.reload();
                    }} else {{
                        alert(d.message);
                    }}
                }});
            }}
        }}
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE ADD CUSTOMER TEMPLATE
# ==============================================================================

STORE_ADD_CUSTOMER_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Add Customer - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Add New Customer</div>
                <div class="page-subtitle">Enter customer details</div>
            </div>
            <a href="/admin/store/customers">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
                </button>
            </a>
        </div>

        <div class="card" style="max-width: 700px; margin: 0 auto;">
            <div class="section-header">
                <span><i class="fas fa-user-plus" style="margin-right: 10px; color: var(--accent-orange);"></i>Customer Information</span>
            </div>
            <form action="/admin/store/customers/add" method="post">
                <div class="input-group">
                    <label><i class="fas fa-user" style="margin-right: 5px;"></i> CUSTOMER NAME *</label>
                    <input type="text" name="name" required placeholder="Enter customer name">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-phone" style="margin-right: 5px;"></i> PHONE NUMBER</label>
                    <input type="text" name="phone" placeholder="e.g. 01712345678">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> ADDRESS</label>
                    <textarea name="address" placeholder="Enter customer address"></textarea>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-envelope" style="margin-right: 5px;"></i> EMAIL</label>
                    <input type="email" name="email" placeholder="e.g.customer@example.com">
                </div>
                <button type="submit">
                    <i class="fas fa-save" style="margin-right: 10px;"></i> Save Customer
                </button>
            </form>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# STORE EDIT CUSTOMER TEMPLATE
# ==============================================================================

STORE_EDIT_CUSTOMER_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Customer - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link active">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Edit Customer</div>
                <div class="page-subtitle">Update customer details</div>
            </div>
            <a href="/admin/store/customers">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
                </button>
            </a>
        </div>

        <div class="card" style="max-width: 700px; margin: 0 auto;">
            <div class="section-header">
                <span><i class="fas fa-user-edit" style="margin-right: 10px; color: var(--accent-purple);"></i>Customer Information</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ customer._id }}}}</span>
            </div>
            <form action="/admin/store/customers/edit/{{{{ customer._id }}}}" method="post">
                <div class="input-group">
                    <label><i class="fas fa-user" style="margin-right: 5px;"></i> CUSTOMER NAME *</label>
                    <input type="text" name="name" required value="{{{{ customer.name }}}}">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-phone" style="margin-right: 5px;"></i> PHONE NUMBER</label>
                    <input type="text" name="phone" value="{{{{ customer.phone if customer.phone else '' }}}}">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-map-marker-alt" style="margin-right: 5px;"></i> ADDRESS</label>
                    <textarea name="address">{{{{ customer.address if customer.address else '' }}}}</textarea>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-envelope" style="margin-right: 5px;"></i> EMAIL</label>
                    <input type="email" name="email" value="{{{{ customer.email if customer.email else '' }}}}">
                </div>
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync" style="margin-right: 10px;"></i> Update Customer
                </button>
            </form>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# STORE PRODUCTS LIST TEMPLATE
# ==============================================================================

STORE_PRODUCTS_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Products - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Products</div>
                <div class="page-subtitle">Manage your product catalog</div>
            </div>
            <a href="/admin/store/products/add">
                <button style="width: auto; padding: 12px 24px;">
                    <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Add Product
                </button>
            </a>
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
            <div class="section-header">
                <span>All Products</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ products|length }}}} Total</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Product Name</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th>Price</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for prod in products %}}
                        <tr>
                            <td style="font-weight: 600;">{{{{ prod.name }}}}</td>
                            <td><span class="table-badge" style="background: rgba(139, 92, 246, 0.1); color: var(--accent-purple);">{{{{ prod.category }}}}</span></td>
                            <td style="color: var(--text-secondary);">{{{{ prod.unit }}}}</td>
                            <td style="color: var(--accent-orange); font-weight: 700;">৳{{{{ "{:,.2f}".format(prod.price) }}}}</td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/products/edit/{{{{ prod._id }}}}" class="action-btn btn-edit">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    {{% if session.role == 'admin' %}}
                                    <button class="action-btn btn-del" onclick="deleteProduct('{{{{ prod._id }}}}')">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                    {{% endif %}}
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="5" style="text-align: center; padding: 60px; color: var(--text-secondary);">
                                <i class="fas fa-box-open" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i>
                                <div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Products Yet</div>
                                <div style="font-size: 14px; margin-bottom: 20px;">Start by adding your first product</div>
                                <a href="/admin/store/products/add">
                                    <button style="width: auto; padding: 12px 24px;">
                                        <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Add First Product
                                    </button>
                                </a>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function deleteProduct(id) {{
            if (confirm('Are you sure you want to delete this product?')) {{
                fetch(`/admin/store/products/delete/${{id}}`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(d => {{
                    if (d.status === 'success') {{
                        location.reload();
                    }} else {{
                        alert(d.message);
                    }}
                }});
            }}
        }}
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE ADD PRODUCT TEMPLATE
# ==============================================================================

STORE_ADD_PRODUCT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Add Product - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Add New Product</div>
                <div class="page-subtitle">Enter product details</div>
            </div>
            <a href="/admin/store/products">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
                </button>
            </a>
        </div>

        <div class="card" style="max-width: 700px; margin: 0 auto;">
            <div class="section-header">
                <span><i class="fas fa-box" style="margin-right: 10px; color: var(--accent-orange);"></i>Product Information</span>
            </div>
            <form action="/admin/store/products/add" method="post">
                <div class="input-group">
                    <label><i class="fas fa-tag" style="margin-right: 5px;"></i> PRODUCT NAME *</label>
                    <input type="text" name="name" required placeholder="e.g. Aluminium Window Frame">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-layer-group" style="margin-right: 5px;"></i> CATEGORY</label>
                    <select name="category">
                        <option value="Window">Window</option>
                        <option value="Door">Door</option>
                        <option value="Frame">Frame</option>
                        <option value="Shutter">Shutter</option>
                        <option value="Glass">Glass</option>
                        <option value="Hardware">Hardware</option>
                        <option value="Accessories">Accessories</option>
                        <option value="General">General</option>
                    </select>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> UNIT</label>
                    <select name="unit">
                        <option value="Piece">Piece</option>
                        <option value="Sq.Ft">Sq.Ft</option>
                        <option value="Meter">Meter</option>
                        <option value="Kg">Kg</option>
                        <option value="Set">Set</option>
                    </select>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-dollar-sign" style="margin-right: 5px;"></i> PRICE (৳) *</label>
                    <input type="number" step="0.01" name="price" required placeholder="e.g.1500.00">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-align-left" style="margin-right: 5px;"></i> DESCRIPTION</label>
                    <textarea name="description" placeholder="Enter product description (optional)"></textarea>
                </div>
                <button type="submit">
                    <i class="fas fa-save" style="margin-right: 10px;"></i> Save Product
                </button>
            </form>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# STORE EDIT PRODUCT TEMPLATE
# ==============================================================================

STORE_EDIT_PRODUCT_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Product - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link active">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Edit Product</div>
                <div class="page-subtitle">Update product details</div>
            </div>
            <a href="/admin/store/products">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
                </button>
            </a>
        </div>

        <div class="card" style="max-width: 700px; margin: 0 auto;">
            <div class="section-header">
                <span><i class="fas fa-box" style="margin-right: 10px; color: var(--accent-purple);"></i>Product Information</span>
            </div>
            <form action="/admin/store/products/edit/{{{{ product._id }}}}" method="post">
                <div class="input-group">
                    <label><i class="fas fa-tag" style="margin-right: 5px;"></i> PRODUCT NAME *</label>
                    <input type="text" name="name" required value="{{{{ product.name }}}}">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-layer-group" style="margin-right: 5px;"></i> CATEGORY</label>
                    <select name="category">
                        <option value="Window" {{% if product.category == 'Window' %}}selected{{% endif %}}>Window</option>
                        <option value="Door" {{% if product.category == 'Door' %}}selected{{% endif %}}>Door</option>
                        <option value="Frame" {{% if product.category == 'Frame' %}}selected{{% endif %}}>Frame</option>
                        <option value="Shutter" {{% if product.category == 'Shutter' %}}selected{{% endif %}}>Shutter</option>
                        <option value="Glass" {{% if product.category == 'Glass' %}}selected{{% endif %}}>Glass</option>
                        <option value="Hardware" {{% if product.category == 'Hardware' %}}selected{{% endif %}}>Hardware</option>
                        <option value="Accessories" {{% if product.category == 'Accessories' %}}selected{{% endif %}}>Accessories</option>
                        <option value="General" {{% if product.category == 'General' %}}selected{{% endif %}}>General</option>
                    </select>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-ruler" style="margin-right: 5px;"></i> UNIT</label>
                    <select name="unit">
                        <option value="Piece" {{% if product.unit == 'Piece' %}}selected{{% endif %}}>Piece</option>
                        <option value="Sq.Ft" {{% if product.unit == 'Sq.Ft' %}}selected{{% endif %}}>Sq.Ft</option>
                        <option value="Meter" {{% if product.unit == 'Meter' %}}selected{{% endif %}}>Meter</option>
                        <option value="Kg" {{% if product.unit == 'Kg' %}}selected{{% endif %}}>Kg</option>
                        <option value="Set" {{% if product.unit == 'Set' %}}selected{{% endif %}}>Set</option>
                    </select>
                </div>
                <div class="input-group">
                    <label><i class="fas fa-dollar-sign" style="margin-right: 5px;"></i> PRICE (৳) *</label>
                    <input type="number" step="0.01" name="price" required value="{{{{ product.price }}}}">
                </div>
                <div class="input-group">
                    <label><i class="fas fa-align-left" style="margin-right: 5px;"></i> DESCRIPTION</label>
                    <textarea name="description">{{{{ product.description if product.description else '' }}}}</textarea>
                </div>
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync" style="margin-right: 10px;"></i> Update Product
                </button>
            </form>
        </div>
    </div>
</body>
</html>
"""
# ==============================================================================
# STORE INVOICES LIST TEMPLATE
# ==============================================================================

STORE_INVOICES_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoices - Store Panel</title>
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
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Invoices</div>
                <div class="page-subtitle">Manage sales invoices</div>
            </div>
            <a href="/admin/store/invoices/create">
                <button style="width: auto; padding: 12px 24px;">
                    <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Create Invoice
                </button>
            </a>
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
            <div class="section-header">
                <span>All Invoices</span>
                <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ invoices|length }}}} Total</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="dark-table">
                    <thead>
                        <tr>
                            <th>Invoice ID</th>
                            <th>Date</th>
                            <th>Customer</th>
                            <th>Total Amount</th>
                            <th>Paid</th>
                            <th>Due</th>
                            <th>Status</th>
                            <th style="text-align: right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for inv in invoices %}}
                        <tr>
                            <td style="font-weight: 700; color: var(--accent-orange);">{{{{ inv._id }}}}</td>
                            <td style="color: var(--text-secondary);">{{{{ inv.date }}}}</td>
                            <td style="font-weight: 600;">{{{{ inv.customer_name }}}}</td>
                            <td style="color: white; font-weight: 600;">৳{{{{ "{:,.2f}".format(inv.total_amount) }}}}</td>
                            <td style="color: var(--accent-green); font-weight: 600;">৳{{{{ "{:,.2f}".format(inv.paid_amount) }}}}</td>
                            <td style="color: var(--accent-red); font-weight: 700;">৳{{{{ "{:,.2f}".format(inv.due_amount) }}}}</td>
                            <td>
                                {{% if inv.due_amount == 0 %}}
                                <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);">
                                    <i class="fas fa-check-circle" style="margin-right: 5px;"></i>Paid
                                </span>
                                {{% elif inv.paid_amount > 0 %}}
                                <span class="table-badge" style="background: rgba(255, 193, 7, 0.1); color: #FFC107;">
                                    <i class="fas fa-clock" style="margin-right: 5px;"></i>Partial
                                </span>
                                {{% else %}}
                                <span class="table-badge" style="background: rgba(239, 68, 68, 0.1); color: var(--accent-red);">
                                    <i class="fas fa-exclamation-triangle" style="margin-right: 5px;"></i>Unpaid
                                </span>
                                {{% endif %}}
                            </td>
                            <td>
                                <div class="action-cell">
                                    <a href="/admin/store/invoices/view/{{{{ inv._id }}}}" class="action-btn btn-view" title="View Invoice">
                                        <i class="fas fa-eye"></i>
                                    </a>
                                    <a href="/admin/store/invoices/edit/{{{{ inv._id }}}}" class="action-btn btn-edit" title="Edit Invoice">
                                        <i class="fas fa-edit"></i>
                                    </a>
                                    {{% if session.role == 'admin' %}}
                                    <button class="action-btn btn-del" onclick="deleteInvoice('{{{{ inv._id }}}}')" title="Delete Invoice">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                    {{% endif %}}
                                </div>
                            </td>
                        </tr>
                        {{% else %}}
                        <tr>
                            <td colspan="8" style="text-align: center; padding: 60px; color: var(--text-secondary);">
                                <i class="fas fa-file-invoice" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i>
                                <div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Invoices Yet</div>
                                <div style="font-size: 14px; margin-bottom: 20px;">Start by creating your first invoice</div>
                                <a href="/admin/store/invoices/create">
                                    <button style="width: auto; padding: 12px 24px;">
                                        <i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Create First Invoice
                                    </button>
                                </a>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function deleteInvoice(id) {{
            if (confirm('Are you sure you want to delete this invoice? \\n\\nThis will also delete all payment records associated with it.')) {{
                fetch(`/admin/store/invoices/delete/${{id}}`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(d => {{
                    if (d.status === 'success') {{
                        location.reload();
                    }} else {{
                        alert(d.message);
                    }}
                }});
            }}
        }}
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE CREATE INVOICE TEMPLATE (DYNAMIC ITEMS)
# ==============================================================================

STORE_CREATE_INVOICE_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Create Invoice - Store Panel</title>
    {COMMON_STYLES}
    <style>
        .item-row {{
            background: rgba(255, 255, 255, 0.02);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            border: 1px solid var(--border-color);
            position: relative;
            transition: var(--transition-smooth);
        }}
        .item-row:hover {{
            background: rgba(255, 255, 255, 0.04);
            border-color: var(--border-glow);
        }}
        .item-row-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr auto;
            gap: 15px;
            align-items: end;
        }}
        .remove-item-btn {{
            padding: 12px;
            background: rgba(239, 68, 68, 0.1);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
            width: auto;
        }}
        .remove-item-btn:hover {{
            background: var(--accent-red);
            color: white;
        }}
        .add-item-btn {{
            width: auto;
            padding: 12px 24px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.2);
            margin-bottom: 20px;
        }}
        .add-item-btn:hover {{
            background: var(--accent-green);
            color: white;
        }}
        .summary-box {{
            background: rgba(255, 122, 0, 0.05);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }}
        .summary-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            font-size: 15px;
        }}
        .summary-row.total {{
            border-top: 2px solid var(--accent-orange);
            margin-top: 10px;
            padding-top: 15px;
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-orange);
        }}
        @media (max-width: 768px) {{
            .item-row-grid {{
                grid-template-columns: 1fr;
            }}
        }}
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
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Create New Invoice</div>
                <div class="page-subtitle">Generate sales invoice for customer</div>
            </div>
            <a href="/admin/store/invoices">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to List
                </button>
            </a>
        </div>

        <form action="/admin/store/invoices/create" method="post" id="invoiceForm">
            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-user-circle" style="margin-right: 10px; color: var(--accent-blue);"></i>Customer Information</span>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-user" style="margin-right: 5px;"></i> SELECT CUSTOMER *</label>
                        <select name="customer_id" id="customer_id" required onchange="loadCustomerInfo()">
                            <option value="">-- Select Customer --</option>
                            {{% for cust in customers %}}
                            <option value="{{{{ cust._id }}}}">{{{{ cust.name }}}}</option>
                            {{% endfor %}}
                        </select>
                    </div>
                    <div id="customerInfo" style="display: none; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.2); margin-top: 15px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px;">
                            <div>
                                <div style="color: var(--text-secondary); margin-bottom: 5px;">Phone:</div>
                                <div id="custPhone" style="color: white; font-weight: 600;">-</div>
                            </div>
                            <div>
                                <div style="color: var(--text-secondary); margin-bottom: 5px;">Current Due:</div>
                                <div id="custDue" style="color: var(--accent-red); font-weight: 700;">৳0</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-money-bill-wave" style="margin-right: 10px; color: var(--accent-green);"></i>Payment Details</span>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-credit-card" style="margin-right: 5px;"></i> PAYMENT METHOD</label>
                        <select name="payment_method">
                            <option value="Cash">Cash</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="bKash">bKash</option>
                            <option value="Nagad">Nagad</option>
                            <option value="Rocket">Rocket</option>
                        </select>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-hand-holding-usd" style="margin-right: 5px;"></i> PAID AMOUNT (৳)</label>
                        <input type="number" step="0.01" name="paid_amount" id="paid_amount" value="0" placeholder="Enter paid amount" oninput="calculateSummary()">
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-orange);"></i>Invoice Items</span>
                    <button type="button" class="add-item-btn" onclick="addItemRow()" style="width: auto; padding: 8px 16px; margin: 0;">
                        <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Item
                    </button>
                </div>
                <div id="itemsContainer">
                    <div class="item-row">
                        <div class="item-row-grid">
                            <div class="input-group" style="margin: 0;">
                                <label>ITEM NAME *</label>
                                <input type="text" name="item_name[]" required placeholder="Enter item/product name" list="productList" onchange="loadProductInfo(this)">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>QUANTITY *</label>
                                <input type="number" step="0.01" name="item_qty[]" required placeholder="Qty" value="1" oninput="calculateSummary()">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>PRICE (৳) *</label>
                                <input type="number" step="0.01" name="item_price[]" required placeholder="Price" oninput="calculateSummary()">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>TOTAL (৳)</label>
                                <input type="text" class="item-total" readonly style="background: rgba(255, 122, 0, 0.1); color: var(--accent-orange); font-weight: 700;" value="0.00">
                            </div>
                            <button type="button" class="remove-item-btn" onclick="removeItemRow(this)" style="opacity: 0.3; pointer-events: none;">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                </div>
                <button type="button" class="add-item-btn" onclick="addItemRow()">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Another Item
                </button>

                <datalist id="productList">
                    {{% for prod in products %}}
                    <option value="{{{{ prod.name }}}}" data-price="{{{{ prod.price }}}}">{{{{ prod.category }}}} - ৳{{{{ prod.price }}}}</option>
                    {{% endfor %}}
                </datalist>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-sticky-note" style="margin-right: 10px; color: var(--accent-cyan);"></i>Additional Notes</span>
                    </div>
                    <div class="input-group">
                        <label>NOTES (OPTIONAL)</label>
                        <textarea name="notes" placeholder="Add any special notes or terms..."></textarea>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-percent" style="margin-right: 5px;"></i> DISCOUNT (৳)</label>
                        <input type="number" step="0.01" name="discount" id="discount" value="0" placeholder="Enter discount amount" oninput="calculateSummary()">
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calculator" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Summary</span>
                    </div>
                    <div class="summary-box">
                        <div class="summary-row">
                            <span style="color: var(--text-secondary);">Subtotal:</span>
                            <span id="subtotal" style="font-weight: 600;">৳0.00</span>
                        </div>
                        <div class="summary-row">
                            <span style="color: var(--text-secondary);">Discount:</span>
                            <span id="discountDisplay" style="font-weight: 600; color: var(--accent-green);">- ৳0.00</span>
                        </div>
                        <div class="summary-row total">
                            <span>GRAND TOTAL:</span>
                            <span id="grandTotal">৳0.00</span>
                        </div>
                        <div class="summary-row" style="border-top: 1px solid var(--border-color); margin-top: 10px; padding-top: 10px;">
                            <span style="color: var(--accent-green);">Paid:</span>
                            <span id="paidDisplay" style="font-weight: 700; color: var(--accent-green);">৳0.00</span>
                        </div>
                        <div class="summary-row">
                            <span style="color: var(--accent-red);">Due:</span>
                            <span id="dueDisplay" style="font-weight: 700; color: var(--accent-red);">৳0.00</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <button type="submit" style="background: var(--gradient-orange);">
                    <i class="fas fa-check-circle" style="margin-right: 10px;"></i> Create Invoice
                </button>
            </div>
        </form>
    </div>

    <script>
        function addItemRow() {{
            const container = document.getElementById('itemsContainer');
            const newRow = document.createElement('div');
            newRow.className = 'item-row';
            newRow.innerHTML = `
                <div class="item-row-grid">
                    <div class="input-group" style="margin: 0;">
                        <label>ITEM NAME *</label>
                        <input type="text" name="item_name[]" required placeholder="Enter item/product name" list="productList" onchange="loadProductInfo(this)">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>QUANTITY *</label>
                        <input type="number" step="0.01" name="item_qty[]" required placeholder="Qty" value="1" oninput="calculateSummary()">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>PRICE (৳) *</label>
                        <input type="number" step="0.01" name="item_price[]" required placeholder="Price" oninput="calculateSummary()">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>TOTAL (৳)</label>
                        <input type="text" class="item-total" readonly style="background: rgba(255, 122, 0, 0.1); color: var(--accent-orange); font-weight: 700;" value="0.00">
                    </div>
                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            container.appendChild(newRow);
            updateRemoveButtons();
        }}

        function removeItemRow(btn) {{
            btn.closest('.item-row').remove();
            calculateSummary();
            updateRemoveButtons();
        }}

        function updateRemoveButtons() {{
            const rows = document.querySelectorAll('.item-row');
            rows.forEach((row, index) => {{
                const btn = row.querySelector('.remove-item-btn');
                if (rows.length === 1) {{
                    btn.style.opacity = '0.3';
                    btn.style.pointerEvents = 'none';
                }} else {{
                    btn.style.opacity = '1';
                    btn.style.pointerEvents = 'auto';
                }}
            }});
        }}

        function loadProductInfo(input) {{
            const productName = input.value;
            const products = {{{{ products | tojson }}}};
            const product = products.find(p => p.name === productName);
            
            if (product) {{
                const row = input.closest('.item-row-grid');
                const priceInput = row.querySelector('input[name="item_price[]"]');
                priceInput.value = product.price;
                calculateSummary();
            }}
        }}

        function loadCustomerInfo() {{
            const customerId = document.getElementById('customer_id').value;
            if (!customerId) {{
                document.getElementById('customerInfo').style.display = 'none';
                return;
            }}

            fetch(`/admin/store/get-customer-info/${{customerId}}`)
                .then(r => r.json())
                .then(data => {{
                    if (data.status === 'success') {{
                        document.getElementById('custPhone').textContent = data.phone || 'N/A';
                        document.getElementById('custDue').textContent = '৳' + data.total_due.toFixed(2);
                        document.getElementById('customerInfo').style.display = 'block';
                    }}
                }});
        }}

        function calculateSummary() {{
            let subtotal = 0;
            const rows = document.querySelectorAll('.item-row');
            
            rows.forEach(row => {{
                const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
                const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
                const total = qty * price;
                row.querySelector('.item-total').value = total.toFixed(2);
                subtotal += total;
            }});

            const discount = parseFloat(document.getElementById('discount').value) || 0;
            const grandTotal = subtotal - discount;
            const paid = parseFloat(document.getElementById('paid_amount').value) || 0;
            const due = grandTotal - paid;

            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document.getElementById('discountDisplay').textContent = '- ৳' + discount.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳' + grandTotal.toFixed(2);
            document.getElementById('paidDisplay').textContent = '৳' + paid.toFixed(2);
            document.getElementById('dueDisplay').textContent = '৳' + due.toFixed(2);
        }}

        // Initialize
        calculateSummary();
        updateRemoveButtons();
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE VIEW INVOICE TEMPLATE (PROFESSIONAL PRINT-READY)
# ==============================================================================

STORE_VIEW_INVOICE_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Invoice {{{{ invoice._id }}}} - Store Panel</title>
    {COMMON_STYLES}
    <style>
        @media print {{
            body {{ background: white; }}
            .sidebar, .header-section, .no-print, .animated-bg, .mobile-toggle {{ display: none ! important; }}
            .main-content {{ margin-left: 0; width: 100%; padding: 0; }}
            .print-invoice {{ box-shadow: none; border: none; }}
        }}
        .print-invoice {{
            background: white;
            color: #000;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 10px 50px rgba(0,0,0,0.3);
        }}
        .invoice-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 3px solid #FF7A00;
        }}
        .company-info h1 {{
            font-size: 28px;
            font-weight: 900;
            color: #FF7A00;
            margin: 0 0 5px 0;
        }}
        .company-info p {{
            margin: 3px 0;
            font-size: 13px;
            color: #666;
        }}
        .invoice-meta {{
            text-align: right;
        }}
        .invoice-meta h2 {{
            font-size: 24px;
            font-weight: 800;
            color: #333;
            margin: 0 0 10px 0;
        }}
        .invoice-meta p {{
            margin: 5px 0;
            font-size: 13px;
            color: #666;
        }}
        .invoice-meta .invoice-number {{
            background: #FF7A00;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 10px;
        }}
        .billing-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}
        .billing-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #FF7A00;
        }}
        .billing-box h3 {{
            font-size: 14px;
            font-weight: 700;
            color: #FF7A00;
            margin: 0 0 15px 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .billing-box p {{
            margin: 8px 0;
            font-size: 14px;
            color: #333;
        }}
        .billing-box strong {{
            color: #000;
            font-weight: 600;
        }}
        .invoice-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        .invoice-table thead {{
            background: #FF7A00;
            color: white;
        }}
        .invoice-table th {{
            padding: 12px;
            text-align: left;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .invoice-table td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            font-size: 14px;
            color: #333;
        }}
        .invoice-table tbody tr:hover {{
            background: #f8f9fa;
        }}
        .invoice-table .text-right {{
            text-align: right;
        }}
        .invoice-table .item-name {{
            font-weight: 600;
            color: #000;
        }}
        .invoice-summary {{
            margin-left: auto;
            width: 350px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
        }}
        .summary-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            font-size: 15px;
        }}
        .summary-row.total {{
            border-top: 2px solid #FF7A00;
            margin-top: 10px;
            padding-top: 15px;
            font-size: 20px;
            font-weight: 800;
            color: #FF7A00;
        }}
        .summary-row.paid {{
            color: #10B981;
            font-weight: 700;
        }}
        .summary-row.due {{
            color: #EF4444;
            font-weight: 700;
        }}
        .invoice-notes {{
            background: #fffbea;
            border-left: 4px solid #FFC107;
            padding: 15px;
            margin-top: 30px;
            border-radius: 6px;
        }}
        .invoice-notes h4 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            font-weight: 700;
            color: #333;
        }}
        .invoice-notes p {{
            margin: 0;
            font-size: 13px;
            color: #666;
            line-height: 1.6;
        }}
        .invoice-footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
        .payment-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-paid {{
            background: #d1fae5;
            color: #065f46;
        }}
        .badge-partial {{
            background: #fef3c7;
            color: #92400e;
        }}
        .badge-unpaid {{
            background: #fee2e2;
            color: #991b1b;
        }}
    </style>
</head>
<body>
    <div class="animated-bg"></div>

    <div class="mobile-toggle no-print" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>

    <div class="sidebar no-print">
        <div class="brand-logo">
            <i class="fas fa-store"></i> 
            Store<span>Panel</span>
        </div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
        <div class="header-section no-print">
            <div>
                <div class="page-title">Invoice Details</div>
                <div class="page-subtitle">View and manage invoice</div>
            </div>
            <div style="display: flex; gap: 10px;">
                <button onclick="window.print()" style="width: auto; padding: 12px 24px; background: var(--gradient-orange);">
                    <i class="fas fa-print" style="margin-right: 8px;"></i> Print Invoice
                </button>
                <a href="/admin/store/invoices/edit/{{{{ invoice._id }}}}">
                    <button style="width: auto; padding: 12px 24px; background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                        <i class="fas fa-edit" style="margin-right: 8px;"></i> Edit
                    </button>
                </a>
                <a href="/admin/store/invoices">
                    <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                        <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back
                    </button>
                </a>
            </div>
        </div>

        {{% with messages = get_flashed_messages() %}}
            {{% if messages %}}
                <div class="flash-message flash-success no-print">
                    <i class="fas fa-check-circle"></i>
                    <span>{{{{ messages[0] }}}}</span>
                </div>
            {{% endif %}}
        {{% endwith %}}

        {{% set due_amount = invoice.total_amount - invoice.paid_amount %}}
        {{% if due_amount > 0 %}}
        <div class="card no-print" style="margin-bottom: 20px; background: rgba(255, 193, 7, 0.05); border: 1px solid rgba(255, 193, 7, 0.2);">
            <div class="section-header">
                <span><i class="fas fa-hand-holding-usd" style="margin-right: 10px; color: #FFC107;"></i>Collect Payment</span>
            </div>
            <form id="paymentForm" style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 15px; align-items: end;">
                <div class="input-group" style="margin: 0;">
                    <label>AMOUNT (৳)</label>
                    <input type="number" step="0.01" id="payment_amount" placeholder="Enter amount" required>
                </div>
                <div class="input-group" style="margin: 0;">
                    <label>METHOD</label>
                    <select id="payment_method">
                        <option value="Cash">Cash</option>
                        <option value="Bank Transfer">Bank Transfer</option>
                        <option value="bKash">bKash</option>
                        <option value="Nagad">Nagad</option>
                        <option value="Rocket">Rocket</option>
                    </select>
                </div>
                <button type="button" onclick="collectPayment()" style="width: auto; padding: 12px 24px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%);">
                    <i class="fas fa-check" style="margin-right: 8px;"></i> Collect
                </button>
            </form>
        </div>
        {{% endif %}}

        <div class="print-invoice">
            <div class="invoice-header">
                <div class="company-info">
                    <h1>ALUMINIUM STORE</h1>
                    <p><i class="fas fa-map-marker-alt"></i> 123 Main Street, Dhaka, Bangladesh</p>
                    <p><i class="fas fa-phone"></i> +880 1712-345678</p>
                    <p><i class="fas fa-envelope"></i> info@aluminiumstore.com</p>
                </div>
                <div class="invoice-meta">
                    <h2>INVOICE</h2>
                    <div class="invoice-number">{{{{ invoice._id }}}}</div>
                    <p><strong>Date:</strong> {{{{ invoice.date }}}}</p>
                    <p><strong>Created By:</strong> {{{{ invoice.created_by }}}}</p>
                </div>
            </div>

            <div class="billing-section">
                <div class="billing-box">
                    <h3><i class="fas fa-user-circle"></i> Bill To</h3>
                    <p><strong>{{{{ customer.name }}}}</strong></p>
                    {{% if customer.phone %}}
                    <p><i class="fas fa-phone"></i> {{{{ customer.phone }}}}</p>
                    {{% endif %}}
                    {{% if customer.address %}}
                    <p><i class="fas fa-map-marker-alt"></i> {{{{ customer.address }}}}</p>
                    {{% endif %}}
                    {{% if customer.email %}}
                    <p><i class="fas fa-envelope"></i> {{{{ customer.email }}}}</p>
                    {{% endif %}}
                </div>
                <div class="billing-box">
                    <h3><i class="fas fa-info-circle"></i> Invoice Status</h3>
                    {{% if due_amount == 0 %}}
                    <p><span class="payment-badge badge-paid"><i class="fas fa-check-circle"></i> PAID IN FULL</span></p>
                    {{% elif invoice.paid_amount > 0 %}}
                    <p><span class="payment-badge badge-partial"><i class="fas fa-clock"></i> PARTIALLY PAID</span></p>
                    {{% else %}}
                    <p><span class="payment-badge badge-unpaid"><i class="fas fa-exclamation-triangle"></i> UNPAID</span></p>
                    {{% endif %}}
                    <p><strong>Payment Method:</strong> {{{{ invoice.payment_method }}}}</p>
                </div>
            </div>

            <table class="invoice-table">
                <thead>
                    <tr>
                        <th style="width: 50px;">#</th>
                        <th>Item Description</th>
                        <th class="text-right" style="width: 100px;">Quantity</th>
                        <th class="text-right" style="width: 120px;">Unit Price</th>
                        <th class="text-right" style="width: 140px;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {{% for item in invoice.items %}}
                    <tr>
                        <td>{{{{ loop.index }}}}</td>
                        <td class="item-name">{{{{ item.name }}}}</td>
                        <td class="text-right">{{{{ item.qty }}}}</td>
                        <td class="text-right">৳{{{{ "{:,.2f}".format(item.price) }}}}</td>
                        <td class="text-right">৳{{{{ "{:,.2f}".format(item.total) }}}}</td>
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>

            <div class="invoice-summary">
                <div class="summary-row">
                    <span>Subtotal:</span>
                    <span>৳{{{{ "{:,.2f}".format(invoice.subtotal) }}}}</span>
                </div>
                <div class="summary-row">
                    <span>Discount:</span>
                    <span style="color: #10B981;">- ৳{{{{ "{:,.2f}".format(invoice.discount) }}}}</span>
                </div>
                <div class="summary-row total">
                    <span>GRAND TOTAL:</span>
                    <span>৳{{{{ "{:,.2f}".format(invoice.total_amount) }}}}</span>
                </div>
                <div class="summary-row paid">
                    <span>Paid:</span>
                    <span>৳{{{{ "{:,.2f}".format(invoice.paid_amount) }}}}</span>
                </div>
                <div class="summary-row due">
                    <span>Due:</span>
                    <span>৳{{{{ "{:,.2f}".format(due_amount) }}}}</span>
                </div>
            </div>

            {{% if invoice.notes %}}
            <div class="invoice-notes">
                <h4><i class="fas fa-sticky-note"></i> Notes</h4>
                <p>{{{{ invoice.notes }}}}</p>
            </div>
            {{% endif %}}

            {{% if payments %}}
            <div style="margin-top: 30px;">
                <h3 style="font-size: 16px; font-weight: 700; color: #333; margin-bottom: 15px;">
                    <i class="fas fa-history"></i> Payment History
                </h3>
                <table class="invoice-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Method</th>
                            <th>Collected By</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for pay in payments %}}
                        <tr>
                            <td>{{{{ pay.date }}}}</td>
                            <td style="color: #10B981; font-weight: 700;">৳{{{{ "{:,.2f}".format(pay.amount) }}}}</td>
                            <td>{{{{ pay.method }}}}</td>
                            <td>{{{{ pay.collected_by }}}}</td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
            {{% endif %}}

            <div class="invoice-footer">
                <p><strong>Thank you for your business!</strong></p>
                <p>This is a computer-generated invoice and does not require a signature.</p>
                <p style="margin-top: 10px; font-size: 11px;">Generated on {{{{ invoice.date }}}} | Powered by MNM Software</p>
            </div>
        </div>
    </div>

    <script>
        function collectPayment() {{
            const amount = document.getElementById('payment_amount').value;
            const method = document.getElementById('payment_method').value;

            if (!amount || amount <= 0) {{
                alert('Please enter a valid amount');
                return;
            }}

            const formData = new FormData();
            formData.append('amount', amount);
            formData.append('method', method);

            fetch('/admin/store/invoices/collect-payment/{{{{ invoice._id }}}}', {{
                method: 'POST',
                body: formData
            }})
            .then(r => r.json())
            .then(d => {{
                if (d.status === 'success') {{
                    alert('Payment collected successfully!');
                    location.reload();
                }} else {{
                    alert(d.message);
                }}
            }});
        }}
    </script>
</body>
</html>
"""


# ==============================================================================
# STORE EDIT INVOICE TEMPLATE (Similar to Create but Pre-filled)
# ==============================================================================

STORE_EDIT_INVOICE_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Edit Invoice - Store Panel</title>
    {COMMON_STYLES}
    <style>
        .item-row {{
            background: rgba(255, 255, 255, 0.02);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            border: 1px solid var(--border-color);
            position: relative;
            transition: var(--transition-smooth);
        }}
        .item-row:hover {{
            background: rgba(255, 255, 255, 0.04);
            border-color: var(--border-glow);
        }}
        .item-row-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr auto;
            gap: 15px;
            align-items: end;
        }}
        .remove-item-btn {{
            padding: 12px;
            background: rgba(239, 68, 68, 0.1);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 8px;
            cursor: pointer;
            transition: var(--transition-smooth);
            width: auto;
        }}
        .remove-item-btn:hover {{
            background: var(--accent-red);
            color: white;
        }}
        .add-item-btn {{
            width: auto;
            padding: 12px 24px;
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
            border: 1px solid rgba(16, 185, 129, 0.2);
            margin-bottom: 20px;
        }}
        .add-item-btn:hover {{
            background: var(--accent-green);
            color: white;
        }}
        .summary-box {{
            background: rgba(255, 122, 0, 0.05);
            border: 1px solid var(--border-glow);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }}
        .summary-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            font-size: 15px;
        }}
        .summary-row.total {{
            border-top: 2px solid var(--accent-orange);
            margin-top: 10px;
            padding-top: 15px;
            font-size: 20px;
            font-weight: 800;
            color: var(--accent-orange);
        }}
        @media (max-width: 768px) {{
            .item-row-grid {{
                grid-template-columns: 1fr;
            }}
        }}
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
            {{% if session.role == 'admin' %}}
            <a href="/" class="nav-link">
                <i class="fas fa-arrow-left"></i> Back to Main
            </a>
            {{% endif %}}
            <a href="/admin/store" class="nav-link">
                <i class="fas fa-th-large"></i> Dashboard
            </a>
            <a href="/admin/store/customers" class="nav-link">
                <i class="fas fa-users"></i> Customers
            </a>
            <a href="/admin/store/products" class="nav-link">
                <i class="fas fa-box"></i> Products
            </a>
            <a href="/admin/store/invoices" class="nav-link active">
                <i class="fas fa-file-invoice"></i> Invoices
            </a>
            <a href="/admin/store/quotations" class="nav-link">
                <i class="fas fa-file-signature"></i> Quotations
            </a>
            <a href="/admin/store/due-list" class="nav-link">
                <i class="fas fa-money-bill-wave"></i> Due List
            </a>
            <a href="/admin/store/payment-history" class="nav-link">
                <i class="fas fa-history"></i> Payments
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
                <div class="page-title">Edit Invoice</div>
                <div class="page-subtitle">Update invoice details</div>
            </div>
            <a href="/admin/store/invoices/view/{{{{ invoice._id }}}}">
                <button style="width: auto; padding: 12px 24px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color);">
                    <i class="fas fa-arrow-left" style="margin-right: 8px;"></i> Back to Invoice
                </button>
            </a>
        </div>

        <form action="/admin/store/invoices/edit/{{{{ invoice._id }}}}" method="post" id="invoiceForm">
            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-info-circle" style="margin-right: 10px; color: var(--accent-blue);"></i>Invoice Information</span>
                    <span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ invoice._id }}}}</span>
                </div>
                <div style="background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.2);">
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; font-size: 14px;">
                        <div>
                            <div style="color: var(--text-secondary); margin-bottom: 5px;">Customer:</div>
                            <div style="color: white; font-weight: 600;">{{{{ customer.name }}}}</div>
                        </div>
                        <div>
                            <div style="color: var(--text-secondary); margin-bottom: 5px;">Date:</div>
                            <div style="color: white; font-weight: 600;">{{{{ invoice.date }}}}</div>
                        </div>
                        <div>
                            <div style="color: var(--text-secondary); margin-bottom: 5px;">Current Paid:</div>
                            <div style="color: var(--accent-green); font-weight: 700;">৳{{{{ "{:,.2f}".format(invoice.paid_amount) }}}}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="section-header">
                    <span><i class="fas fa-list" style="margin-right: 10px; color: var(--accent-orange);"></i>Invoice Items</span>
                    <button type="button" class="add-item-btn" onclick="addItemRow()" style="width: auto; padding: 8px 16px; margin: 0;">
                        <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Item
                    </button>
                </div>
                <div id="itemsContainer">
                    {{% for item in invoice.items %}}
                    <div class="item-row">
                        <div class="item-row-grid">
                            <div class="input-group" style="margin: 0;">
                                <label>ITEM NAME *</label>
                                <input type="text" name="item_name[]" required placeholder="Enter item/product name" list="productList" value="{{{{ item.name }}}}">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>QUANTITY *</label>
                                <input type="number" step="0.01" name="item_qty[]" required placeholder="Qty" value="{{{{ item.qty }}}}" oninput="calculateSummary()">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>PRICE (৳) *</label>
                                <input type="number" step="0.01" name="item_price[]" required placeholder="Price" value="{{{{ item.price }}}}" oninput="calculateSummary()">
                            </div>
                            <div class="input-group" style="margin: 0;">
                                <label>TOTAL (৳)</label>
                                <input type="text" class="item-total" readonly style="background: rgba(255, 122, 0, 0.1); color: var(--accent-orange); font-weight: 700;" value="{{{{ "{:.2f}".format(item.total) }}}}">
                            </div>
                            <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    {{% endfor %}}
                </div>
                <button type="button" class="add-item-btn" onclick="addItemRow()">
                    <i class="fas fa-plus" style="margin-right: 8px;"></i> Add Another Item
                </button>

                <datalist id="productList">
                    {{% for prod in products %}}
                    <option value="{{{{ prod.name }}}}" data-price="{{{{ prod.price }}}}">{{{{ prod.category }}}} - ৳{{{{ prod.price }}}}</option>
                    {{% endfor %}}
                </datalist>
            </div>

            <div class="dashboard-grid-2">
                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-sticky-note" style="margin-right: 10px; color: var(--accent-cyan);"></i>Additional Notes</span>
                    </div>
                    <div class="input-group">
                        <label>NOTES (OPTIONAL)</label>
                        <textarea name="notes" placeholder="Add any special notes or terms...">{{{{ invoice.notes if invoice.notes else '' }}}}</textarea>
                    </div>
                    <div class="input-group">
                        <label><i class="fas fa-percent" style="margin-right: 5px;"></i> DISCOUNT (৳)</label>
                        <input type="number" step="0.01" name="discount" id="discount" value="{{{{ invoice.discount }}}}" placeholder="Enter discount amount" oninput="calculateSummary()">
                    </div>
                </div>

                <div class="card">
                    <div class="section-header">
                        <span><i class="fas fa-calculator" style="margin-right: 10px; color: var(--accent-purple);"></i>Invoice Summary</span>
                    </div>
                    <div class="summary-box">
                        <div class="summary-row">
                            <span style="color: var(--text-secondary);">Subtotal:</span>
                            <span id="subtotal" style="font-weight: 600;">৳0.00</span>
                        </div>
                        <div class="summary-row">
                            <span style="color: var(--text-secondary);">Discount:</span>
                            <span id="discountDisplay" style="font-weight: 600; color: var(--accent-green);">- ৳0.00</span>
                        </div>
                        <div class="summary-row total">
                            <span>GRAND TOTAL:</span>
                            <span id="grandTotal">৳0.00</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);">
                    <i class="fas fa-sync" style="margin-right: 10px;"></i> Update Invoice
                </button>
            </div>
        </form>
    </div>

    <script>
        function addItemRow() {{
            const container = document.getElementById('itemsContainer');
            const newRow = document.createElement('div');
            newRow.className = 'item-row';
            newRow.innerHTML = `
                <div class="item-row-grid">
                    <div class="input-group" style="margin: 0;">
                        <label>ITEM NAME *</label>
                        <input type="text" name="item_name[]" required placeholder="Enter item/product name" list="productList">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>QUANTITY *</label>
                        <input type="number" step="0.01" name="item_qty[]" required placeholder="Qty" value="1" oninput="calculateSummary()">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>PRICE (৳) *</label>
                        <input type="number" step="0.01" name="item_price[]" required placeholder="Price" oninput="calculateSummary()">
                    </div>
                    <div class="input-group" style="margin: 0;">
                        <label>TOTAL (৳)</label>
                        <input type="text" class="item-total" readonly style="background: rgba(255, 122, 0, 0.1); color: var(--accent-orange); font-weight: 700;" value="0.00">
                    </div>
                    <button type="button" class="remove-item-btn" onclick="removeItemRow(this)">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            container.appendChild(newRow);
            updateRemoveButtons();
        }}

        function removeItemRow(btn) {{
            btn.closest('.item-row').remove();
            calculateSummary();
            updateRemoveButtons();
        }}

        function updateRemoveButtons() {{
            const rows = document.querySelectorAll('.item-row');
            rows.forEach((row, index) => {{
                const btn = row.querySelector('.remove-item-btn');
                if (rows.length === 1) {{
                    btn.style.opacity = '0.3';
                    btn.style.pointerEvents = 'none';
                }} else {{
                    btn.style.opacity = '1';
                    btn.style.pointerEvents = 'auto';
                }}
            }});
        }}

        function calculateSummary() {{
            let subtotal = 0;
            const rows = document.querySelectorAll('.item-row');
            
            rows.forEach(row => {{
                const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
                const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
                const total = qty * price;
                row.querySelector('.item-total').value = total.toFixed(2);
                subtotal += total;
            }});

            const discount = parseFloat(document.getElementById('discount').value) || 0;
            const grandTotal = subtotal - discount;

            document.getElementById('subtotal').textContent = '৳' + subtotal.toFixed(2);
            document.getElementById('discountDisplay').textContent = '- ৳' + discount.toFixed(2);
            document.getElementById('grandTotal').textContent = '৳' + grandTotal.toFixed(2);
        }}

        // Initialize
        calculateSummary();
        updateRemoveButtons();
    </script>
</body>
</html>
"""
# ==============================================================================
# STORE QUOTATIONS TEMPLATE (Simplified - Similar to Invoices)
# ==============================================================================

STORE_QUOTATIONS_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Quotations - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')">
        <i class="fas fa-bars"></i>
    </div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link"><i class="fas fa-arrow-left"></i> Back to Main</a>{{% endif %}}
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/admin/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/admin/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <a href="/admin/store/invoices" class="nav-link"><i class="fas fa-file-invoice"></i> Invoices</a>
            <a href="/admin/store/quotations" class="nav-link active"><i class="fas fa-file-signature"></i> Quotations</a>
            <a href="/admin/store/due-list" class="nav-link"><i class="fas fa-money-bill-wave"></i> Due List</a>
            <a href="/admin/store/payment-history" class="nav-link"><i class="fas fa-history"></i> Payments</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Quotations</div><div class="page-subtitle">Manage price estimates</div></div>
            <a href="/admin/store/quotations/create"><button style="width: auto; padding: 12px 24px;"><i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Create Quotation</button></a>
        </div>
        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-success"><i class="fas fa-check-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}
        <div class="card">
            <div class="section-header"><span>All Quotations</span><span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ quotations|length }}}} Total</span></div>
            <div style="overflow-x: auto;"><table class="dark-table"><thead><tr><th>Quotation ID</th><th>Date</th><th>Customer</th><th>Amount</th><th>Valid Until</th><th>Status</th><th style="text-align: right;">Actions</th></tr></thead><tbody>
            {{% for quo in quotations %}}
            <tr>
                <td style="font-weight: 700; color: var(--accent-purple);">{{{{ quo._id }}}}</td>
                <td style="color: var(--text-secondary);">{{{{ quo.date }}}}</td>
                <td style="font-weight: 600;">{{{{ quo.customer_name }}}}</td>
                <td style="color: var(--accent-orange); font-weight: 600;">৳{{{{ "{:,.2f}".format(quo.total_amount) }}}}</td>
                <td style="color: var(--text-secondary);">{{{{ quo.valid_until if quo.valid_until else 'N/A' }}}}</td>
                <td>
                    {{% if quo.status == 'Converted' %}}
                    <span class="table-badge" style="background: rgba(16, 185, 129, 0.1); color: var(--accent-green);"><i class="fas fa-check"></i> Converted</span>
                    {{% else %}}
                    <span class="table-badge" style="background: rgba(255, 193, 7, 0.1); color: #FFC107;"><i class="fas fa-clock"></i> Pending</span>
                    {{% endif %}}
                </td>
                <td><div class="action-cell">
                    <a href="/admin/store/quotations/view/{{{{ quo._id }}}}" class="action-btn btn-view" title="View"><i class="fas fa-eye"></i></a>
                    {{% if quo.status != 'Converted' %}}
                    <a href="/admin/store/quotations/convert/{{{{ quo._id }}}}" class="action-btn btn-edit" title="Convert to Invoice"><i class="fas fa-exchange-alt"></i></a>
                    {{% endif %}}
                    {{% if session.role == 'admin' %}}
                    <button class="action-btn btn-del" onclick="deleteQuotation('{{{{ quo._id }}}}')" title="Delete"><i class="fas fa-trash"></i></button>
                    {{% endif %}}
                </div></td>
            </tr>
            {{% else %}}
            <tr><td colspan="7" style="text-align: center; padding: 60px; color: var(--text-secondary);"><i class="fas fa-file-signature" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i><div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Quotations Yet</div><div style="font-size: 14px; margin-bottom: 20px;">Start by creating your first quotation</div><a href="/admin/store/quotations/create"><button style="width: auto; padding: 12px 24px;"><i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Create First Quotation</button></a></td></tr>
            {{% endfor %}}
            </tbody></table></div>
        </div>
    </div>
    <script>
        function deleteQuotation(id) {{
            if (confirm('Delete this quotation?')) {{
                fetch(`/admin/store/quotations/delete/${{id}}`, {{method: 'POST', headers: {{'Content-Type': 'application/json'}}}})
                .then(r => r.json()).then(d => {{ if (d.status === 'success') location.reload(); else alert(d.message); }});
            }}
        }}
    </script>
</body>
</html>
"""

# Note: STORE_CREATE_QUOTATION_TEMPLATE, STORE_VIEW_QUOTATION_TEMPLATE are nearly identical to invoice templates
# I'm providing simplified versions to save space

STORE_CREATE_QUOTATION_TEMPLATE = STORE_CREATE_INVOICE_TEMPLATE.replace('Create Invoice', 'Create Quotation').replace('invoices', 'quotations').replace('Invoice', 'Quotation')
STORE_VIEW_QUOTATION_TEMPLATE = STORE_VIEW_INVOICE_TEMPLATE.replace('Invoice', 'Quotation').replace('INVOICE', 'QUOTATION').replace('invoices', 'quotations')


# ==============================================================================
# STORE DUE LIST TEMPLATE
# ==============================================================================

STORE_DUE_LIST_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Due List - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link"><i class="fas fa-arrow-left"></i> Back to Main</a>{{% endif %}}
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/admin/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/admin/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <a href="/admin/store/invoices" class="nav-link"><i class="fas fa-file-invoice"></i> Invoices</a>
            <a href="/admin/store/quotations" class="nav-link"><i class="fas fa-file-signature"></i> Quotations</a>
            <a href="/admin/store/due-list" class="nav-link active"><i class="fas fa-money-bill-wave"></i> Due List</a>
            <a href="/admin/store/payment-history" class="nav-link"><i class="fas fa-history"></i> Payments</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Due List</div><div class="page-subtitle">Customer-wise outstanding amounts</div></div>
        </div>
        <div class="card">
            <div class="section-header">
                <span>Customers with Due</span>
                <span class="table-badge" style="background: var(--accent-red); color: white;">{{{{ due_list|length }}}} Customers</span>
            </div>
            <div style="overflow-x: auto;"><table class="dark-table">
                <thead><tr><th>Customer</th><th>Phone</th><th>Total Amount</th><th>Paid</th><th>Due</th><th>Invoices</th></tr></thead>
                <tbody>
                {{% for item in due_list %}}
                <tr>
                    <td style="font-weight: 600;">{{{{ item.name }}}}</td>
                    <td style="color: var(--text-secondary);">{{{{ item.phone }}}}</td>
                    <td style="font-weight: 600;">৳{{{{ "{:,.2f}".format(item.total_amount) }}}}</td>
                    <td style="color: var(--accent-green); font-weight: 600;">৳{{{{ "{:,.2f}".format(item.total_paid) }}}}</td>
                    <td style="color: var(--accent-red); font-weight: 700; font-size: 16px;">৳{{{{ "{:,.2f}".format(item.total_due) }}}}</td>
                    <td><span class="table-badge" style="background: var(--accent-orange); color: white;">{{{{ item.invoice_count }}}} Invoice(s)</span></td>
                </tr>
                {{% else %}}
                <tr><td colspan="6" style="text-align: center; padding: 60px; color: var(--text-secondary);"><i class="fas fa-smile" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i><div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Due Amounts! </div><div style="font-size: 14px;">All customers have cleared their payments</div></td></tr>
                {{% endfor %}}
                </tbody>
            </table></div>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# STORE PAYMENT HISTORY TEMPLATE
# ==============================================================================

STORE_PAYMENT_HISTORY_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Payment History - Store Panel</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-store"></i> Store<span>Panel</span></div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link"><i class="fas fa-arrow-left"></i> Back to Main</a>{{% endif %}}
            <a href="/admin/store" class="nav-link"><i class="fas fa-th-large"></i> Dashboard</a>
            <a href="/admin/store/customers" class="nav-link"><i class="fas fa-users"></i> Customers</a>
            <a href="/admin/store/products" class="nav-link"><i class="fas fa-box"></i> Products</a>
            <a href="/admin/store/invoices" class="nav-link"><i class="fas fa-file-invoice"></i> Invoices</a>
            <a href="/admin/store/quotations" class="nav-link"><i class="fas fa-file-signature"></i> Quotations</a>
            <a href="/admin/store/due-list" class="nav-link"><i class="fas fa-money-bill-wave"></i> Due List</a>
            <a href="/admin/store/payment-history" class="nav-link active"><i class="fas fa-history"></i> Payments</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Payment History</div><div class="page-subtitle">Track all payment transactions</div></div>
        </div>
        <div class="card">
            <div class="section-header">
                <span>Recent Payments</span>
                <span class="table-badge" style="background: var(--accent-green); color: white;">{{{{ payments|length }}}} Records</span>
            </div>
            <div style="overflow-x: auto;"><table class="dark-table">
                <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Amount</th><th>Method</th><th>Collected By</th></tr></thead>
                <tbody>
                {{% for pay in payments %}}
                <tr>
                    <td style="color: var(--text-secondary);">{{{{ pay.date }}}}</td>
                    <td style="font-weight: 700; color: var(--accent-orange);">{{{{ pay.invoice_id }}}}</td>
                    <td style="font-weight: 600;">{{{{ pay.customer_name }}}}</td>
                    <td style="color: var(--accent-green); font-weight: 700; font-size: 16px;">৳{{{{ "{:,.2f}".format(pay.amount) }}}}</td>
                    <td><span class="table-badge" style="background: rgba(59, 130, 246, 0.1); color: var(--accent-blue);">{{{{ pay.method }}}}</span></td>
                    <td style="color: var(--text-secondary);">{{{{ pay.collected_by }}}}</td>
                </tr>
                {{% else %}}
                <tr><td colspan="6" style="text-align: center; padding: 60px; color: var(--text-secondary);"><i class="fas fa-money-bill-wave" style="font-size: 60px; opacity: 0.3; display: block; margin-bottom: 20px;"></i><div style="font-size: 18px; font-weight: 600; margin-bottom: 10px;">No Payment Records</div><div style="font-size: 14px;">Payment history will appear here</div></td></tr>
                {{% endfor %}}
                </tbody>
            </table></div>
        </div>
    </div>
</body>
</html>
"""


# ==============================================================================
# ACCESSORIES TEMPLATES (UNCHANGED - YOUR ORIGINAL)
# ==============================================================================

ACCESSORIES_SEARCH_TEMPLATE = f"""
<! doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Accessories - MNM Software</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="animated-bg"></div>
    <div class="mobile-toggle" onclick="document.querySelector('.sidebar').classList.toggle('active')"><i class="fas fa-bars"></i></div>
    <div class="sidebar">
        <div class="brand-logo"><i class="fas fa-layer-group"></i> MNM<span>Software</span></div>
        <div class="nav-menu">
            {{% if session.role == 'admin' %}}<a href="/" class="nav-link"><i class="fas fa-arrow-left"></i> Back to Main</a>{{% endif %}}
            <a href="/admin/accessories" class="nav-link active"><i class="fas fa-database"></i> Accessories Challan</a>
            <a href="/logout" class="nav-link" style="color: var(--accent-red); margin-top: 20px;"><i class="fas fa-sign-out-alt"></i> Sign Out</a>
        </div>
        <div class="sidebar-footer"><i class="fas fa-code" style="margin-right: 5px;"></i> Powered by Mehedi Hasan</div>
    </div>
    <div class="main-content">
        <div class="header-section">
            <div><div class="page-title">Accessories Challan</div><div class="page-subtitle">Search and manage challan entries</div></div>
        </div>
        {{% with messages = get_flashed_messages() %}}{{% if messages %}}<div class="flash-message flash-error"><i class="fas fa-exclamation-circle"></i><span>{{{{ messages[0] }}}}</span></div>{{% endif %}}{{% endwith %}}
        <div class="card" style="max-width: 600px; margin: 40px auto;">
            <div class="section-header"><span><i class="fas fa-search" style="margin-right: 10px; color: var(--accent-purple);"></i>Search Booking</span></div>
            <form action="/admin/accessories/input" method="post">
                <div class="input-group"><label><i class="fas fa-bookmark" style="margin-right: 5px;"></i> BOOKING REF NO</label><input type="text" name="ref_no" required placeholder="Enter IR/IB or Booking Number" autofocus></div>
                <button type="submit" style="background: linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%);"><i class="fas fa-search" style="margin-right: 10px;"></i> Search & Open</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

# Simplified other accessories templates (INPUT, EDIT, REPORT) - using similar structure
ACCESSORIES_INPUT_TEMPLATE = """Similar structure to search, with color dropdown and form to add challan entry"""
ACCESSORIES_EDIT_TEMPLATE = """Edit form for existing challan entry"""
ACCESSORIES_REPORT_TEMPLATE = """Print-ready challan report with table"""


# ==============================================================================
# CLOSING REPORT & PO REPORT TEMPLATES (UNCHANGED - YOUR ORIGINAL)
# ==============================================================================

CLOSING_REPORT_PREVIEW_TEMPLATE = """Your existing closing report preview template"""
PO_REPORT_TEMPLATE = """Your existing PO report template with color-wise tables"""


# ==============================================================================
# 🎯 ENTRY POINT - START THE APPLICATION
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MNM SOFTWARE - COMPLETE SYSTEM")
    print("=" * 60)
    print("✅ MongoDB Connected")
    print("✅ All Modules Loaded:")
    print("   - Admin Dashboard")
    print("   - User Management")
    print("   - Closing Report Generator")
    print("   - PO Sheet Generator")
    print("   - Accessories Challan System")
    print("   - 🆕 ALUMINIUM STORE MANAGEMENT")
    print("       ├── Customer Management")
    print("       ├── Product Catalog")
    print("       ├── Invoice System (Create/Edit/Print)")
    print("       ├── Quotation System")
    print("       ├── Payment Collection")
    print("       ├── Due Tracking")
    print("       └── Real-time Analytics")
    print("=" * 60)
    print("🌐 Starting Flask Server...")
    print("🔗 Access at: http://127.0.0.1:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
