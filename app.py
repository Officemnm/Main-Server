import requests
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
import time
import json
import os

# --- Flask লাইব্রেরি ইম্পোর্ট ---
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd' 

# --- ২ মিনিটের সেশন টাইমআউট কনফিগারেশন ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)

# ==============================================================================
# হেল্পার ফাংশন: পরিসংখ্যান বা স্ট্যাটাস ম্যানেজমেন্ট (JSON ফাইল দিয়ে)
# ==============================================================================
STATS_FILE = 'stats.json'

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"downloads": [], "last_booking": "None"}
    try:
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"downloads": [], "last_booking": "None"}

def save_stats(data):
    with open(STATS_FILE, 'w') as f:
        json.dump(data, f)

def update_stats(ref_no):
    data = load_stats()
    # বর্তমান সময় সেভ করা
    current_time = datetime.now().isoformat()
    data['downloads'].append({"ref": ref_no, "time": current_time})
    data['last_booking'] = ref_no
    save_stats(data)

def get_dashboard_summary():
    data = load_stats()
    downloads = data.get('downloads', [])
    last_booking = data.get('last_booking', 'N/A')
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    month_str = now.strftime('%Y-%m')
    
    today_count = 0
    month_count = 0
    
    for d in downloads:
        dt = datetime.fromisoformat(d['time'])
        if dt.strftime('%Y-%m-%d') == today_str:
            today_count += 1
        if dt.strftime('%Y-%m') == month_str:
            month_count += 1
            
    return {
        "today": today_count,
        "month": month_count,
        "last_booking": last_booking
    }

# ==============================================================================
# ফাংশন ১: ERP সিস্টেমে লগইন করার ফাংশন
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

# ==============================================================================
# ফাংশন ২: HTML পার্সার
# ==============================================================================
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
                all_report_data.append({'style': style, 'buyer': buyer_name, 'color': color, 'headers': headers, 'gmts_qty': gmts_qty_data, 'plus_3_percent': plus_3_percent_data, 'sewing_input': sewing_input_data if sewing_input_data else [], 'cutting_qc': cutting_qc_data if cutting_qc_data else []})
        return all_report_data
    except Exception as e:
        return None

# ==============================================================================
# ফাংশন ৩: এক্সেল জেনারেটর 
# ==============================================================================
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
    current_date = datetime.now().strftime("%d/%m/%Y")
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
# CSS & HTML Templates (আপডেট করা হয়েছে)
# ==============================================================================
COMMON_STYLES = """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body {
            background-color: #2c3e50; 
            background-image: url('https://i.ibb.co.com/v64Lz1gj/Picsart-25-11-19-15-49-43-423.jpg');
            background-repeat: no-repeat;
            background-position: center center;
            background-attachment: fixed;
            background-size: cover;
            height: 100vh;
            overflow: hidden; /* Prevent body scroll for admin layout */
        }
        body::before {
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.4); /* Darker overlay for better contrast */
            z-index: -1;
        }
        
        /* --- Shared Classes --- */
        .glass-card {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 45px 40px;
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            color: white;
            animation: floatIn 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
        }

        /* Login & User Dashboard specific centering */
        .center-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
            width: 100%;
        }
        .center-container .glass-card {
            width: 100%;
            max-width: 400px;
            text-align: center;
        }

        @keyframes floatIn {
            from { opacity: 0; transform: translateY(30px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        
        h1 { color: #ffffff; font-size: 26px; font-weight: 600; margin-bottom: 8px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        p.subtitle { color: #e0e0e0; font-size: 13px; margin-bottom: 30px; font-weight: 300; }
        
        .input-group { text-align: left; margin-bottom: 20px; }
        .input-group label {
            display: block;
            font-size: 12px;
            color: #ffffff;
            font-weight: 500;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }
        
        input[type="password"], input[type="text"], select {
            width: 100%;
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            font-size: 15px;
            color: #fff;
            transition: all 0.3s ease;
            outline: none;
            appearance: none;
        }
        
        select {
            cursor: pointer;
            background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23FFFFFF%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E");
            background-repeat: no-repeat;
            background-position: right 15px top 50%;
            background-size: 12px auto;
        }
        select option { background-color: #2c3e50; color: white; }

        input::placeholder { color: rgba(255, 255, 255, 0.6); }
        input:focus, select:focus {
            background: rgba(255, 255, 255, 0.3);
            border-color: #ffffff;
            box-shadow: 0 0 10px rgba(255,255,255,0.2);
        }
        
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .flash {
            margin-top: 15px;
            padding: 10px;
            border-radius: 8px;
            background: rgba(231, 76, 60, 0.8);
            backdrop-filter: blur(4px);
            color: white;
            font-size: 13px;
        }
        
        a.logout {
            display: inline-block;
            margin-top: 20px;
            color: rgba(255,255,255,0.7);
            text-decoration: none;
            font-size: 13px;
            padding: 5px 10px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 20px;
            transition: 0.3s;
        }
        a.logout:hover { background: rgba(255,255,255,0.2); color: white; }

        /* --- LOADER & SUCCESS CSS --- */
        #loading-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(8px);
            z-index: 9999;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
            transition: opacity 0.3s ease;
        }
        
        .spinner {
            width: 60px; height: 60px;
            border: 5px solid rgba(255, 255, 255, 0.2);
            border-top: 5px solid #a29bfe;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 20px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        .success-icon {
            font-size: 60px; color: #2ecc71; display: none; margin-bottom: 10px;
            animation: popIn 0.5s ease;
        }
        @keyframes popIn { from { transform: scale(0); } to { transform: scale(1); } }

        #loading-text { font-size: 18px; font-weight: 500; letter-spacing: 1px; text-align: center; }

        /* Error State */
        .loader-error .spinner { border-top-color: #e74c3c; animation: none; }
        .loader-error #loading-text { color: #e74c3c; font-weight: 700; }
        
        /* Success State */
        .loader-success .spinner { display: none; }
        .loader-success .success-icon { display: block; }
        .loader-success #loading-text { color: #2ecc71; font-weight: 600; }

        /* =========================================
           ADMIN DASHBOARD SPECIFIC CSS
           ========================================= */
        .admin-container {
            display: flex;
            width: 100%;
            height: 100vh;
        }
        
        /* Sidebar */
        .admin-sidebar {
            width: 280px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
            padding: 25px;
        }
        
        .sidebar-header {
            margin-bottom: 40px;
            text-align: center;
        }
        .sidebar-header h2 { color: white; font-size: 22px; font-weight: 600; }
        .sidebar-header p { color: #a29bfe; font-size: 12px; letter-spacing: 1px; }

        .nav-menu { list-style: none; }
        .nav-item { margin-bottom: 15px; }
        
        .nav-link {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            border-radius: 10px;
            transition: all 0.3s ease;
            font-size: 14px;
            cursor: pointer;
        }
        
        .nav-link i { margin-right: 12px; width: 20px; text-align: center; }
        .nav-link:hover, .nav-link.active {
            background: linear-gradient(90deg, rgba(108, 92, 231, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transform: translateX(5px);
        }

        .admin-footer {
            margin-top: auto;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 20px;
        }

        /* Main Content */
        .admin-content {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 20px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.15); }
        
        .stat-icon {
            width: 50px; height: 50px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.1);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: #fff;
            margin-right: 15px;
        }
        .stat-info h3 { font-size: 24px; color: white; margin-bottom: 5px; }
        .stat-info p { font-size: 13px; color: #dcdcdc; }

        .bg-purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .bg-orange { background: linear-gradient(135deg, #ff9966 0%, #ff5e62 100%); }
        .bg-green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }

        /* Content Area */
        .work-area {
            flex: 1;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 20px;
            padding: 30px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            position: relative;
        }
        
        /* Sweet Alert Style Customization */
        .swal-overlay { background-color: rgba(0, 0, 0, 0.6); }
        .swal-modal {
            background-color: #2d3436;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .swal-title { color: white; }
        .swal-text { color: #b2bec3; }
    </style>
"""

# --- লগইন পেজের টেমপ্লেট (অপরিবর্তিত) ---
LOGIN_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MEHEDI HASAN</title>
    {COMMON_STYLES}
</head>
<body>
    <div class="center-container">
        <div class="glass-card">
            <h1>System Access</h1>
            <p class="subtitle">Secure Gateway for ERP Reports</p>
            <form action="/login" method="post">
                <div class="input-group">
                    <label for="username">Select User</label>
                    <select id="username" name="username" required>
                        <option value="KobirAhmed">KobirAhmed</option>
                        <option value="Admin">Admin</option>
                    </select>
                </div>
                <div class="input-group">
                    <label for="password">Authentication PIN</label>
                    <input type="password" id="password" name="password" placeholder="Enter Password" required>
                </div>
                <button type="submit">Verify & Enter</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
        </div>
    </div>
</body>
</html>
"""

# --- ইউজার ড্যাশবোর্ড (KobirAhmed) ---
USER_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard - User</title>
    {COMMON_STYLES}
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-icon">✅</div>
        <div id="loading-text">Processing data... Please wait</div>
    </div>

    <div class="center-container">
        <div class="glass-card">
            <h1>© Mehedi Hasan</h1>
            <p class="subtitle">Create Closing Reports Instantly</p>
            <form action="/generate-report" method="post" id="reportForm" onsubmit="startDownloadProcess()">
                <div class="input-group">
                    <label for="ref_no">Internal Reference No</label>
                    <input type="text" id="ref_no" name="ref_no" placeholder="Booking-123/456.." required>
                    <input type="hidden" name="download_token" id="download_token">
                </div>
                <button type="submit">Generate Excel Report</button>
            </form>
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    <div class="flash">{{{{ messages[0] }}}}</div>
                {{% endif %}}
            {{% endwith %}}
            <a href="/logout" class="logout">Exit Session</a>
        </div>
    </div>

    <script>
        // Auto Logout & Cookie scripts same as before
        let timeout;
        function resetTimer() {{ clearTimeout(timeout); timeout = setTimeout(function() {{ alert("Session expired due to inactivity."); window.location.href = "/logout"; }}, 120000); }}
        document.onmousemove = resetTimer; document.onkeypress = resetTimer; document.onload = resetTimer; resetTimer();

        function getCookie(name) {{ let parts = document.cookie.split(name + "="); if (parts.length == 2) return parts.pop().split(";").shift(); return null; }}
        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); const loadingText = document.getElementById('loading-text'); const spinner = document.querySelector('.spinner'); const successIcon = document.querySelector('.success-icon'); const tokenInput = document.getElementById('download_token');
            const token = new Date().getTime(); tokenInput.value = token;
            overlay.style.display = 'flex'; overlay.className = ''; loadingText.innerHTML = "Processing data...<br><span style='font-size:12px; opacity:0.8'>Downloading will start automatically</span>"; spinner.style.display = 'block'; successIcon.style.display = 'none';
            let attempts = 0;
            const downloadTimer = setInterval(function() {{
                const cookieValue = getCookie("download_token");
                if (cookieValue == token) {{
                    clearInterval(downloadTimer);
                    overlay.classList.add('loader-success'); loadingText.innerHTML = "Successful Download Complete!";
                    setTimeout(() => {{ overlay.style.opacity = '0'; setTimeout(() => {{ overlay.style.display = 'none'; overlay.style.opacity = '1'; }}, 500); }}, 2000);
                }}
                attempts++; if (attempts > 300) {{ clearInterval(downloadTimer); overlay.classList.add('loader-error'); spinner.style.display = 'none'; loadingText.innerHTML = "Server Timeout<br><span style='font-size:12px'>Please try again later.</span><br><a href='/' style='color:white; border:1px solid white; padding:5px; border-radius:4px; margin-top:5px; display:inline-block;'>Reload</a>"; }}
            }}, 1000);
        }}
    </script>
</body>
</html>
"""

# --- অ্যাডমিন ড্যাশবোর্ড (Admin) ---
ADMIN_DASHBOARD_TEMPLATE = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Console</title>
    {COMMON_STYLES}
    <script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script>
</head>
<body>
    <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="success-icon">✅</div>
        <div id="loading-text">Processing data... Please wait</div>
    </div>

    <div class="admin-container">
        <div class="admin-sidebar">
            <div class="sidebar-header">
                <h2>Admin Panel</h2>
                <p>SUPER ADMIN ACCESS</p>
            </div>
            
            <ul class="nav-menu">
                <li class="nav-item">
                    <a class="nav-link active" onclick="showSection('closing', this)">
                        <i class="fas fa-file-export"></i> Closing Report
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Input & Output Report')">
                        <i class="fas fa-exchange-alt"></i> Input & Output Report
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Cutting Plan Sheet')">
                        <i class="fas fa-cut"></i> Cutting Plan Sheet
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Production Analysis')">
                        <i class="fas fa-chart-line"></i> Production Analysis
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" onclick="showComingSoon('Efficiency Tracker')">
                        <i class="fas fa-tachometer-alt"></i> Efficiency Tracker
                    </a>
                </li>
            </ul>
            
            <div class="admin-footer">
                <a href="/logout" class="nav-link" style="color: #ff7675;">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>

        <div class="admin-content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon bg-purple"><i class="fas fa-calendar-day"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ stats.today }}}}</h3>
                        <p>Today's Downloads</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon bg-orange"><i class="fas fa-calendar-alt"></i></div>
                    <div class="stat-info">
                        <h3>{{{{ stats.month }}}}</h3>
                        <p>Monthly Downloads</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon bg-green"><i class="fas fa-history"></i></div>
                    <div class="stat-info">
                        <h3 style="font-size: 16px; word-break: break-all;">{{{{ stats.last_booking }}}}</h3>
                        <p>Last Generated Booking</p>
                    </div>
                </div>
            </div>

            <div class="work-area" id="work-area">
                <div id="closing-section" style="width: 100%; max-width: 500px;">
                    <div class="glass-card" style="background: rgba(255,255,255,0.05); box-shadow: none; border: none;">
                        <h2 style="margin-bottom: 20px; font-weight: 500;"><i class="fas fa-file-export"></i> Generate Closing Report</h2>
                        <form action="/generate-report" method="post" onsubmit="startDownloadProcess()">
                            <div class="input-group">
                                <label for="ref_no">Internal Reference No</label>
                                <input type="text" id="ref_no" name="ref_no" placeholder="Enter Ref No (e.g. DFL/24/..)" required>
                                <input type="hidden" name="download_token" id="download_token">
                            </div>
                            <button type="submit">Generate Report</button>
                        </form>
                        {{% with messages = get_flashed_messages() %}}
                            {{% if messages %}}
                                <div class="flash" style="margin-top: 15px;">{{{{ messages[0] }}}}</div>
                            {{% endif %}}
                        {{% endwith %}}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // --- Coming Soon Alert ---
        function showComingSoon(featureName) {{
            swal({{
                title: "Feature Coming Soon!",
                text: "The '" + featureName + "' module will be launched very soon. Stay tuned!",
                icon: "info",
                button: "Got it!",
                className: "swal-dark"
            }});
        }}

        // --- Section Toggle Logic (Visual only since others are disabled) ---
        function showSection(sectionId, element) {{
            // Reset active class
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
        }}

        // --- Standard Scripts (Logout, Download) ---
        let timeout;
        function resetTimer() {{ clearTimeout(timeout); timeout = setTimeout(function() {{ alert("Session expired."); window.location.href = "/logout"; }}, 120000); }}
        document.onmousemove = resetTimer; document.onkeypress = resetTimer; document.onload = resetTimer; resetTimer();

        function getCookie(name) {{ let parts = document.cookie.split(name + "="); if (parts.length == 2) return parts.pop().split(";").shift(); return null; }}
        function startDownloadProcess() {{
            const overlay = document.getElementById('loading-overlay'); const loadingText = document.getElementById('loading-text'); const spinner = document.querySelector('.spinner'); const successIcon = document.querySelector('.success-icon'); const tokenInput = document.getElementById('download_token');
            const token = new Date().getTime(); tokenInput.value = token;
            overlay.style.display = 'flex'; overlay.className = ''; loadingText.innerHTML = "Processing data...<br><span style='font-size:12px; opacity:0.8'>Downloading will start automatically</span>"; spinner.style.display = 'block'; successIcon.style.display = 'none';
            let attempts = 0;
            const downloadTimer = setInterval(function() {{
                const cookieValue = getCookie("download_token");
                if (cookieValue == token) {{
                    clearInterval(downloadTimer);
                    overlay.classList.add('loader-success'); loadingText.innerHTML = "Successful Download Complete!";
                    
                    // Reload page to update stats after successful download
                    setTimeout(() => {{ 
                        window.location.reload(); 
                    }}, 2000);
                }}
                attempts++; if (attempts > 300) {{ clearInterval(downloadTimer); overlay.classList.add('loader-error'); spinner.style.display = 'none'; loadingText.innerHTML = "Server Timeout"; }}
            }}, 1000);
        }}
    </script>
</body>
</html>
"""

# --- Flask রুট ---

@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    else:
        # Check who is logged in
        if session.get('user') == 'Admin':
            stats = get_dashboard_summary()
            return render_template_string(ADMIN_DASHBOARD_TEMPLATE, stats=stats)
        else:
            return render_template_string(USER_DASHBOARD_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    user_1 = (username == 'KobirAhmed' and password == '11223')
    user_2 = (username == 'Admin' and password == '@Nijhum@12')

    if user_1 or user_2:
        session.permanent = True
        session['logged_in'] = True
        session['user'] = username
    else:
        flash('Incorrect Username or Password.')
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Session terminated.')
    return redirect(url_for('index'))

@app.route('/generate-report', methods=['POST'])
def generate_report():
    if not session.get('logged_in'):
        flash('Unauthorized access.')
        return redirect(url_for('index'))

    internal_ref_no = request.form['ref_no']
    download_token = request.form.get('download_token')

    if not internal_ref_no:
        flash("Ref No required.")
        return redirect(url_for('index'))

    active_session = get_authenticated_session("input2.clothing-cutting", "123456")
    if not active_session:
        flash("ERP Connection Failed.")
        return redirect(url_for('index'))

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
            except requests.exceptions.RequestException:
                continue
        if found_data:
            break
           
    if not found_data:
        flash(f"No data found for: {internal_ref_no}")
        return redirect(url_for('index'))

    report_data = parse_report_data(found_data)
    if not report_data:
        flash(f"Data parsing error for: {internal_ref_no}")
        return redirect(url_for('index'))

    excel_file_stream = create_formatted_excel_report(report_data, internal_ref_no)
    
    if excel_file_stream:
        # সফল ডাউনলোড হলে Stats আপডেট হবে
        update_stats(internal_ref_no)

        response = make_response(send_file(
            excel_file_stream,
            as_attachment=True,
            download_name=f"Closing-Report-{internal_ref_no.replace('/', '_')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ))
        
        if download_token:
            response.set_cookie('download_token', download_token, max_age=60, path='/')
            
        return response
    else:
        flash("Excel generation failed.")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)

