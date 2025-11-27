import os, re, json, shutil, time, requests, openpyxl, pypdf, pandas as pd, numpy as np
from flask import Flask, request, render_template_string, send_file, flash, session, redirect, url_for, make_response, jsonify
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.drawing.image import Image
from PIL import Image as PILImage
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'super-secret-secure-key-bd'
app.config.update(UPLOAD_FOLDER='uploads', PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])

# --- 1. Generic Database Handler (Modern Pattern) ---
class JsonStore:
    def __init__(self, filename, default_data):
        self.file = filename
        self.default = default_data
        if not os.path.exists(self.file): self.save(self.default)
    def load(self):
        try:
            with open(self.file, 'r') as f: return json.load(f)
        except: return self.default
    def save(self, data):
        with open(self.file, 'w') as f: json.dump(data, f, indent=4)
    def update(self, callback):
        data = self.load()
        updated_data = callback(data)
        self.save(updated_data)
        return updated_data

db_users = JsonStore('users.json', {"Admin": {"password": "@Nijhum@12", "role": "admin", "permissions": ["closing", "po_sheet", "user_manage", "view_history", "accessories"]}, "KobirAhmed": {"password": "11223", "role": "user", "permissions": ["closing"]}})
db_stats = JsonStore('stats.json', {"downloads": [], "last_booking": "None"})
db_acc = JsonStore('accessories_db.json', {})

# --- 2. Helper Functions & Logic ---
def get_erp_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    try:
        res = s.post('http://180.92.235.190:8022/erp/login.php', data={'txt_userid': 'input2.clothing-cutting', 'txt_password': '123456', 'submit': 'Login'}, timeout=10)
        return s if "dashboard.php" in res.url or "Invalid" not in res.text else None
    except: return None

def fetch_erp_data(ref):
    s = get_erp_session()
    if not s: return None
    url = 'http://180.92.235.190:8022/erp/prod_planning/reports/requires/cutting_lay_production_report_controller.php'
    payload = {'action': 'report_generate', 'cbo_wo_company_name': '2', 'cbo_location_name': '2', 'cbo_floor_id': '0', 'cbo_buyer_name': '0', 'txt_internal_ref_no': ref, 'reportType': '3'}
    for y, c in [(y, str(c)) for y in ['2025', '2024'] for c in range(1, 6)]:
        try:
            res = s.post(url, data={**payload, 'cbo_year_selection': y, 'cbo_company_name': c}, timeout=60)
            if res.ok and "Data not Found" not in res.text: return parse_html(res.text)
        except: continue
    return None

def parse_html(html):
    soup = BeautifulSoup(html, 'lxml')
    try:
        header_row = soup.select_one('thead tr:nth-of-type(2)')
        headers = [th.get_text(strip=True) for th in header_row.find_all('th') if 'total' not in th.get_text(strip=True).lower()]
        data, block = [], []
        for row in soup.select('div#scroll_body table tbody tr'):
            if row.get('bgcolor') == '#cddcdc': 
                if block: data.append(block); block = []
            else: block.append(row)
        if block: data.append(block)
        
        results = []
        for b in data:
            meta = {'style': 'N/A', 'color': 'N/A', 'buyer': 'N/A'}
            qtys = inputs = cuts = []
            for r in b:
                cells = r.find_all('td')
                if len(cells) <= 2: continue
                txt = cells[0].get_text(strip=True).lower()
                sub = cells[2].get_text(strip=True).lower()
                if "style" == txt: meta['style'] = cells[1].get_text(strip=True)
                elif "color" in txt: meta['color'] = cells[1].get_text(strip=True)
                elif "buyer" in txt: meta['buyer'] = cells[1].get_text(strip=True)
                if "gmts. color" in sub: qtys = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
                if "sewing input" in txt: inputs = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
                elif "sewing input" in sub: inputs = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
                if "cutting qc" in txt and "balance" not in txt: cuts = [c.get_text(strip=True) for c in cells[1:len(headers)+1]]
                elif "cutting qc" in sub and "balance" not in sub: cuts = [c.get_text(strip=True) for c in cells[3:len(headers)+3]]
            if qtys:
                p3 = [str(round(int(v.replace(',', '')) * 1.03)) if v.replace(',', '').isdigit() else v for v in qtys]
                results.append({**meta, 'headers': headers, 'gmts_qty': qtys, 'plus_3': p3, 'input': inputs or [], 'cut': cuts or []})
        return results
    except: return None

# --- 3. PDF Parsing Helpers ---
def extract_pdf_data(path):
    try:
        reader = pypdf.PdfReader(path)
        p1 = reader.pages[0].extract_text()
        meta = {'buyer': 'N/A', 'booking': 'N/A', 'style': 'N/A', 'season': 'N/A', 'dept': 'N/A', 'item': 'N/A'}
        
        if "KIABI" in p1.upper(): meta['buyer'] = "KIABI"
        else: 
            m = re.search(r"Buyer.*?Name[\s\S]*?([\w\s&]+)(?:\n|$)", p1)
            if m: meta['buyer'] = m.group(1).strip()
        
        patterns = {
            'booking': r"(?:Internal )?Booking NO\.?[:\s]*([\s\S]*?)(?:System NO|Control No|Buyer)",
            'style': r"Style (?:Ref|Des)\.?[:\s]*([\w-]+)",
            'season': r"Season\s*[:\n\"]*([\w\d-]+)",
            'dept': r"Dept\.?[\s\n:]*([A-Za-z]+)",
            'item': r"Garments? Item[\s\n:]*([^\n\r]+)"
        }
        for k, pat in patterns.items():
            m = re.search(pat, p1, re.IGNORECASE)
            if m: 
                val = m.group(1).strip()
                if k == 'booking': val = val.replace('\n', '').replace(' ', '').split("System")[0]
                if k == 'item': val = val.split("Style")[0].strip()
                meta[k] = val
        
        if "Fabric Booking" in p1: return [], meta

        data = []
        ord_no = (re.search(r"Order (?:no)?\D*(\d+)", p1, re.I) or re.search(r"Order\s*[:\.]?\s*(\d+)", p1, re.I))
        ord_val = ord_no.group(1).strip()[:-2] if ord_no and ord_no.group(1).strip().endswith("00") else (ord_no.group(1).strip() if ord_no else "Unknown")

        for page in reader.pages:
            lines = page.extract_text().split('\n')
            sizes, capture = [], False
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue
                if ("Colo" in line or "Size" in line) and "Total" in line:
                    parts = line.split()
                    try: 
                        sizes = [s for s in parts[:parts.index('Total')] if s not in ["Colo", "/", "Size", "Colo/Size", "Colo/"]]
                        capture = True
                    except: pass
                    continue
                if capture:
                    if "Total" in line or "currency" in line.lower(): capture = False; continue
                    clean = line.replace("Spec", "").replace("price", "").strip()
                    if not re.search(r'[a-zA-Z]', clean) or "Assortment" in clean: continue
                    nums = [int(n) for n in re.findall(r'\b\d+\b', line)]
                    col = re.sub(r'\s\d+$', '', clean).strip()
                    if not nums or not col: continue
                    
                    qtys = nums[:-1] if len(nums) == len(sizes) + 1 else nums[:len(sizes)]
                    if len(qtys) < len(sizes):
                         # Look ahead for vertical values
                         v_qtys = []
                         for nl in lines[i+1:]:
                             if "Total" in nl or re.search(r'[a-zA-Z]', nl.replace("Spec","")): break
                             if re.match(r'^\d+$', nl.strip()): v_qtys.append(int(nl.strip()))
                         if len(v_qtys) >= len(sizes): qtys = v_qtys[:len(sizes)]

                    for idx, sz in enumerate(sizes):
                        if idx < len(qtys): data.append({'P.O NO': ord_val, 'Color': col, 'Size': sz, 'Quantity': qtys[idx]})
        return data, meta
    except: return [], {}

# --- 4. Excel Generator (Optimized) ---
def generate_excel(data, ref):
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Closing Report"
    # Styles
    fonts = {'title': Font(size=32, bold=True, color="7B261A"), 'head': Font(size=15, bold=True), 'bold': Font(bold=True), 'white': Font(size=16.5, bold=True, color="FFFFFF")}
    aligns = {'c': Alignment(horizontal='center', vertical='center'), 'l': Alignment(horizontal='left', vertical='center')}
    borders = {'thin': Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin')), 'med': Border(left=Side('medium'), right=Side('medium'), top=Side('medium'), bottom=Side('medium'))}
    fills = {k: PatternFill('solid', fgColor=c) for k, c in {'ir': "7B261A", 'h': "DE7465", 'lb': "B9C2DF", 'lg': "C4D09D", 'dg': "f1f2e8"}.items()}
    
    def set_cell(r, c, val, f=None, a=None, b=None, fill=None, merge=None, fmt=None):
        cell = ws.cell(r, c, val)
        if f: cell.font = f
        if a: cell.alignment = a
        if b: cell.border = b
        if fill: cell.fill = fill
        if fmt: cell.number_format = fmt
        if merge: ws.merge_cells(start_row=r, start_column=c, end_row=r+merge[0], end_column=c+merge[1])
        return cell

    ws.merge_cells('A1:I1'); set_cell(1, 1, "COTTON CLOTHING BD LTD", fonts['title'], aligns['c'])
    ws.merge_cells('A2:I2'); set_cell(2, 1, "CLOSING REPORT [ INPUT SECTION ]", fonts['head'], aligns['c'])
    ws.row_dimensions[3].height = 6

    meta = data[0]
    info = [('BUYER', meta['buyer']), ('IR/IB NO', ref.upper()), ('STYLE NO', meta['style'])]
    for i, (k, v) in enumerate(info, 4):
        set_cell(i, 1, k, fonts['bold'], aligns['l'], borders['thin'], fills['dg'])
        set_cell(i, 2, v, fonts['white'] if i==5 else fonts['bold'], aligns['l'], borders['thin'], fills['ir'] if i==5 else fills['dg'])
        ws.merge_cells(f'B{i}:G{i}')
    
    dates = [('CLOSING DATE', datetime.now().strftime("%d/%m/%Y")), ('SHIPMENT', 'ALL'), ('PO NO', 'ALL')]
    for i, (k, v) in enumerate(dates, 4):
        set_cell(i, 8, k, fonts['bold'], aligns['l'], borders['thin'], fills['dg'])
        set_cell(i, 9, v, fonts['bold'], aligns['l'], borders['thin'], fills['dg'])

    cr = 8
    for blk in data:
        headers = ["COLOUR NAME", "SIZE", "ORDER QTY 3%", "ACTUAL QTY", "CUTTING QC", "INPUT QTY", "BALANCE", "SHORT/PLUS QTY", "Percentage %"]
        for i, h in enumerate(headers, 1): set_cell(cr, i, h, fonts['bold'], aligns['c'], borders['med'], fills['h'])
        cr += 1
        sr = cr
        for i, sz in enumerate(blk['headers']):
            col = blk['color'] if i == 0 else ""
            act = int(blk['gmts_qty'][i].replace(',', '') or 0)
            inp = int(blk['input'][i].replace(',', '') or 0) if i < len(blk['input']) else 0
            cut = int(blk['cut'][i].replace(',', '') or 0) if i < len(blk['cut']) else 0
            
            set_cell(cr, 1, col, fonts['bold'], aligns['c'], borders['thin'], fills['dg'])
            set_cell(cr, 2, sz, fonts['bold'], aligns['c'], borders['med'], fills['dg'])
            set_cell(cr, 3, f"=ROUND(D{cr}*1.03, 0)", fonts['bold'], aligns['c'], borders['thin'], fills['lb'])
            set_cell(cr, 4, act, None, aligns['c'], borders['thin'], fills['dg'])
            set_cell(cr, 5, cut, None, aligns['c'], borders['thin'], fills['dg'])
            set_cell(cr, 6, inp, fonts['bold'], aligns['c'], borders['thin'], fills['lg'])
            set_cell(cr, 7, f"=E{cr}-F{cr}", None, aligns['c'], borders['thin'], fills['dg'])
            set_cell(cr, 8, f"=F{cr}-C{cr}", None, aligns['c'], borders['thin'], fills['dg'])
            set_cell(cr, 9, f'=IF(C{cr}<>0, H{cr}/C{cr}, 0)', fonts['bold'], aligns['c'], borders['thin'], fills['dg'], fmt='0.00%')
            cr += 1
        
        ws.merge_cells(f'A{sr}:A{cr-1}')
        ws.merge_cells(f'A{cr}:B{cr}'); set_cell(cr, 1, "TOTAL", fonts['bold'], aligns['c'], borders['med'], fills['h'])
        cols = "CDEFGH"
        for idx, char in enumerate(cols, 3):
            set_cell(cr, idx, f"=SUM({char}{sr}:{char}{cr-1})", fonts['bold'], aligns['c'], borders['med'], fills['h'])
        set_cell(cr, 9, f"=IF(C{cr}<>0, H{cr}/C{cr}, 0)", fonts['bold'], aligns['c'], borders['med'], fills['h'], fmt='0.00%')
        cr += 2

    # Image & Signatures
    try:
        r = requests.get('https://i.ibb.co/v6bp0jQW/rockybilly-regular.webp')
        img = Image(BytesIO(r.content)); img.width = 95; img.height = int(img.width * (PILImage.open(BytesIO(r.content)).height / PILImage.open(BytesIO(r.content)).width))
        ws.add_image(img, f'A{cr}')
    except: pass
    
    cr += 1
    ws.merge_cells(f'A{cr}:I{cr}')
    sigs = "                 ".join(["Prepared By", "Input Incharge", "Cutting Incharge", "IE & Planning", "Sewing Manager", "Cutting Manager"])
    set_cell(cr, 1, sigs, fonts['head'], aligns['c'])
    
    # Final Adjustments
    ws.column_dimensions.update({k: v for k, v in zip('ABCDEFGHI', [23, 8.5, 20, 17, 17, 15, 13.5, 23, 18])})
    bio = BytesIO(); wb.save(bio); bio.seek(0)
    return bio

# --- 5. Routes & Controllers ---
@app.before_request
def check_session():
    if request.endpoint not in ['login', 'index', 'static'] and not session.get('logged_in'):
        return redirect(url_for('index'))

@app.route('/')
def index():
    if not session.get('logged_in'): return render_template_string(TEMPLATES['login'])
    if session.get('role') == 'admin':
        data = db_stats.load()
        today = datetime.now().strftime('%Y-%m-%d')
        stats = {
            "today": sum(1 for d in data['downloads'] if d['date'] == today),
            "month": sum(1 for d in data['downloads'] if d['date'].startswith(today[:7])),
            "last_booking": data['last_booking'],
            "history": data['downloads']
        }
        return render_template_string(TEMPLATES['admin_dash'], stats=stats)
    return render_template_string(TEMPLATES['user_dash'])

@app.route('/login', methods=['POST'])
def login():
    u, p = request.form.get('username'), request.form.get('password')
    users = db_users.load()
    if u in users and users[u]['password'] == p:
        session.update(logged_in=True, user=u, role=users[u]['role'], permissions=users[u].get('permissions', []))
        return redirect(url_for('index'))
    flash('Incorrect Credentials'); return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

# --- Admin User Management ---
@app.route('/admin/get-users')
def get_users_api(): return jsonify(db_users.load()) if session.get('role') == 'admin' else jsonify({})

@app.route('/admin/save-user', methods=['POST'])
def save_user_api():
    if session.get('role') != 'admin': return jsonify({'status': 'error', 'message': 'Unauthorized'})
    d = request.json
    def update_logic(users):
        if d['action_type'] == 'create':
            if d['username'] in users: raise Exception('Exists')
            users[d['username']] = {"password": d['password'], "role": "user", "permissions": d['permissions']}
        else:
            if d['username'] not in users: raise Exception('Not Found')
            users[d['username']].update({"password": d['password'], "permissions": d['permissions']})
        return users
    try: db_users.update(update_logic); return jsonify({'status': 'success'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/delete-user', methods=['POST'])
def delete_user_api():
    if session.get('role') != 'admin': return jsonify({'status': 'error'})
    u = request.json.get('username')
    if u == 'Admin': return jsonify({'status': 'error', 'message': 'Cannot delete root'})
    db_users.update(lambda users: {k:v for k,v in users.items() if k != u})
    return jsonify({'status': 'success'})

# --- Reports ---
@app.route('/generate-report', methods=['POST'])
def gen_report():
    if 'closing' not in session.get('permissions', []): return redirect(url_for('index'))
    ref = request.form['ref_no']
    data = fetch_erp_data(ref)
    if not data: flash("No data found"); return redirect(url_for('index'))
    return render_template_string(TEMPLATES['closing_preview'], report_data=data, ref_no=ref)

@app.route('/download-closing-excel')
def dl_excel():
    ref = request.args.get('ref_no')
    data = fetch_erp_data(ref)
    if not data: return redirect(url_for('index'))
    
    def update_stats_cb(s):
        s['downloads'].insert(0, {"ref": ref, "user": session.get('user'), "date": datetime.now().strftime('%Y-%m-%d'), "time": datetime.now().strftime('%I:%M %p')})
        s['last_booking'] = ref
        return s
    db_stats.update(update_stats_cb)
    
    return make_response(send_file(generate_excel(data, ref), as_attachment=True, download_name=f"Report_{ref.replace('/','_')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))

# --- Accessories ---
@app.route('/admin/accessories', methods=['GET'])
def acc_search(): return render_template_string(TEMPLATES['acc_search'])

@app.route('/admin/accessories/input', methods=['POST'])
def acc_input():
    ref = request.form.get('ref_no')
    db = db_acc.load()
    if ref not in db:
        api = fetch_erp_data(ref)
        if not api: flash("Not found"); return redirect(url_for('acc_search'))
        db[ref] = {"style": api[0]['style'], "buyer": api[0]['buyer'], "colors": sorted(list(set(i['color'] for i in api))), "challans": []}
        db_acc.save(db)
    return render_template_string(TEMPLATES['acc_input'], ref=ref, **db[ref])

@app.route('/admin/accessories/save', methods=['POST'])
def acc_save():
    ref, line, col, sz, qty, itm = request.form.get('ref'), request.form.get('line_no'), request.form.get('color'), request.form.get('size'), request.form.get('qty'), request.form.get('item_type')
    def update(db):
        if itm: db[ref]['item_type'] = itm
        for c in db[ref]['challans']: c['status'] = "✔"
        db[ref]['challans'].append({"date": datetime.now().strftime("%d-%m-%Y"), "line": line, "color": col, "size": sz, "qty": qty, "status": ""})
        return db
    db_acc.update(update)
    return redirect(url_for('acc_print', ref=ref))

@app.route('/admin/accessories/print')
def acc_print():
    ref = request.args.get('ref')
    d = db_acc.load().get(ref)
    if not d: return redirect(url_for('acc_search'))
    summary = {}
    for c in d['challans']: summary[c['line']] = summary.get(c['line'], 0) + int(c['qty'])
    return render_template_string(TEMPLATES['acc_report'], ref=ref, challans=d['challans'], line_summary=dict(sorted(summary.items())), count=len(d['challans']), today=datetime.now().strftime("%d-%m-%Y"), **d)

@app.route('/admin/accessories/action', methods=['POST']) # Merged Delete/Update
def acc_action():
    act, ref, idx = request.args.get('action'), request.form.get('ref'), int(request.form.get('index') or request.args.get('index', -1))
    if request.method == 'GET' and act == 'edit': # Show Edit Form
        d = db_acc.load().get(ref)
        return render_template_string(TEMPLATES['acc_edit'], ref=ref, index=idx, item=d['challans'][idx])
    
    def update(db):
        if act == 'delete': del db[ref]['challans'][idx]
        elif act == 'update':
            db[ref]['challans'][idx].update({k: request.form.get(v) for k,v in {'qty':'qty', 'line':'line_no', 'color':'color', 'size':'size'}.items()})
        return db
    db_acc.update(update)
    return redirect(url_for('acc_print', ref=ref))

# --- PO Generator ---
@app.route('/generate-po-report', methods=['POST'])
def po_gen():
    if 'po_sheet' not in session.get('permissions', []): return redirect(url_for('index'))
    files = request.files.getlist('pdf_files')
    if os.path.exists('uploads'): shutil.rmtree('uploads'); os.makedirs('uploads')
    
    all_data, meta = [], {}
    for f in files:
        p = os.path.join('uploads', f.filename); f.save(p)
        d, m = extract_pdf_data(p)
        if m.get('buyer') != 'N/A': meta = m
        all_data.extend(d)
    
    if not all_data: return render_template_string(TEMPLATES['po_report'], tables=None, message="No Data")
    
    df = pd.DataFrame(all_data)
    df = df[df['Color'].str.strip() != ""]
    tables = []
    gt = 0
    for col in df['Color'].unique():
        piv = df[df['Color'] == col].pivot_table(index='P.O NO', columns='Size', values='Quantity', aggfunc='sum', fill_value=0)
        piv = piv[sorted(piv.columns, key=lambda s: (0, ['XXS','XS','S','M','L','XL','XXL'].index(s)) if s in ['XXS','XS','S','M','L','XL','XXL'] else (1, s))]
        piv['Total'] = piv.sum(axis=1); gt += piv['Total'].sum()
        act = piv.sum().to_frame().T; act.index = ['Actual Qty']
        p3 = (act * 1.03).round().astype(int); p3.index = ['3% Order Qty']
        final = pd.concat([piv, act, p3]).reset_index().rename(columns={'index': 'P.O NO'})
        
        html = final.to_html(classes='table table-bordered table-striped', index=False, border=0)
        html = html.replace('<th>Total</th>', '<th class="tot">Total</th>').replace('<td>Total</td>', '<td class="tot">Total</td>')
        tables.append({'color': col, 'table': html})

    return render_template_string(TEMPLATES['po_report'], tables=tables, meta=meta, grand_total=f"{gt:,}")

# --- 6. Compressed Templates (The "Inches" kept intact) ---
CSS = """<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Poppins',sans-serif}body{background:#2c3e50 url('https://i.ibb.co.com/v64Lz1gj/Picsart-25-11-19-15-49-43-423.jpg') no-repeat center fixed;background-size:cover;min-height:100vh}body::before{content:"";position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:-1}.glass-card{background:rgba(255,255,255,0.15);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.2);padding:40px;border-radius:16px;color:white;box-shadow:0 8px 32px rgba(31,38,135,0.37)}.center-container{display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}input,select{width:100%;padding:12px;background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.3);border-radius:8px;color:#fff;margin-bottom:15px;outline:none}option{color:black}button{width:100%;padding:12px;background:linear-gradient(135deg,#667eea,#764ba2);border:none;border-radius:8px;color:white;font-weight:600;cursor:pointer}button:hover{transform:translateY(-2px)}.admin-container{display:flex;height:100vh;position:fixed;width:100%}.admin-sidebar{width:280px;background:rgba(255,255,255,0.1);backdrop-filter:blur(15px);padding:25px;display:flex;flex-direction:column}.nav-link{display:flex;align-items:center;padding:12px;color:rgba(255,255,255,0.7);text-decoration:none;margin-bottom:10px;border-radius:10px;transition:0.3s}.nav-link:hover,.nav-link.active{background:linear-gradient(90deg,rgba(108,92,231,0.8),rgba(118,75,162,0.8));color:white}.stat-card{background:rgba(255,255,255,0.1);padding:20px;border-radius:15px;display:flex;align-items:center}.user-table{width:100%;color:white;border-collapse:collapse}.user-table th,.user-table td{padding:10px;border-bottom:1px solid rgba(255,255,255,0.1)}.btn-sm{padding:5px 10px;font-size:12px;width:auto;margin:2px}.tot{background:#e8f6f3!important;color:#000!important;font-weight:900;border:1px solid #000}</style>"""

TEMPLATES = {
    'login': f"""<!doctype html><html><head><title>Login</title>{CSS}</head><body><div class="center-container"><div class="glass-card" style="width:400px"><h1>System Access</h1><form action="/login" method="post"><input type="text" name="username" placeholder="Username" required><input type="password" name="password" placeholder="Password" required><button>Enter</button></form>{{% with m=get_flashed_messages() %}}{{% if m %}}<p style="color:#e74c3c;margin-top:10px">{{{{m[0]}}}}</p>{{% endif %}}{{% endwith %}}</div></div></body></html>""",
    
    'user_dash': f"""<!doctype html><html><head><title>User Dash</title>{CSS}</head><body><div class="center-container"><div class="glass-card" style="width:500px"><h1>Welcome {{{{session.user}}}}</h1><br>
    {{% if 'closing' in session.permissions %}}<h4>Closing Report</h4><form action="/generate-report" method="post"><input name="ref_no" placeholder="Booking Ref.." required><button>Generate</button></form><br>{{% endif %}}
    {{% if 'po_sheet' in session.permissions %}}<h4>PO Sheet</h4><form action="/generate-po-report" method="post" enctype="multipart/form-data"><input type="file" name="pdf_files" multiple accept=".pdf" required><button style="background:#11998e">Generate</button></form>{{% endif %}}
    <a href="/logout" style="color:#fff;display:block;margin-top:20px;text-align:center">Logout</a></div></div></body></html>""",
    
    'admin_dash': f"""<!doctype html><html><head><title>Admin</title>{CSS}<script src="https://unpkg.com/sweetalert/dist/sweetalert.min.js"></script></head><body><div class="admin-container"><div class="admin-sidebar"><h2>Admin Panel</h2><br>
    <a class="nav-link active" onclick="show('closing',this)"><i class="fas fa-file-export"></i> Closing Report</a>
    <a class="nav-link" href="/admin/accessories"><i class="fas fa-box"></i> Accessories</a>
    <a class="nav-link" onclick="show('po',this)"><i class="fas fa-file-invoice"></i> PO Sheet</a>
    <a class="nav-link" onclick="show('users',this)"><i class="fas fa-users"></i> Users</a>
    <a href="/logout" class="nav-link" style="margin-top:auto;color:#ff7675">Logout</a></div>
    <div style="flex:1;padding:30px;overflow:auto"><div class="stats-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:30px">
    <div class="stat-card"><h3>{{{{stats.today}}}}</h3><p>Today</p></div><div class="stat-card"><h3>{{{{stats.month}}}}</h3><p>Month</p></div><div class="stat-card"><h3>{{{{stats.last_booking}}}}</h3><p>Last</p></div></div>
    <div id="work-area">
        <div id="closing" class="sec"><div class="glass-card"><h2>Closing Report</h2><form action="/generate-report" method="post"><input name="ref_no" placeholder="Ref No" required><button>Generate</button></form></div></div>
        <div id="po" class="sec" style="display:none"><div class="glass-card"><h2>PO Generator</h2><form action="/generate-po-report" method="post" enctype="multipart/form-data"><input type="file" name="pdf_files" multiple required><button>Generate</button></form></div></div>
        <div id="users" class="sec" style="display:none"><div class="glass-card"><h2>Users</h2><form id="uForm"><input id="un" placeholder="User"><input id="pw" placeholder="Pass"><div style="margin:10px">Permissions: <input type="checkbox" id="p1" value="closing" style="width:auto">Closing <input type="checkbox" id="p2" value="po_sheet" style="width:auto">PO <input type="checkbox" id="p3" value="accessories" style="width:auto">Acc</div><button type="button" onclick="saveU('create')">Create</button></form><table class="user-table"><tbody id="uTab"></tbody></table></div></div>
    </div></div></div><script>
    function show(id,el){{document.querySelectorAll('.sec').forEach(d=>d.style.display='none');document.getElementById(id).style.display='block';document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));el.classList.add('active');if(id=='users')loadU()}}
    function loadU(){{fetch('/admin/get-users').then(r=>r.json()).then(d=>{{let h='';for(let u in d)h+=`<tr><td>${{u}}</td><td>${{d[u].role}}</td><td><button class="btn-sm" style="background:#f39c12" onclick="editU('${{u}}','${{d[u].password}}')">Edit</button><button class="btn-sm" style="background:#e74c3c" onclick="delU('${{u}}')">Del</button></td></tr>`;document.getElementById('uTab').innerHTML=h}})}}
    function saveU(act){{let p=[];if(document.getElementById('p1').checked)p.push('closing');if(document.getElementById('p2').checked)p.push('po_sheet');if(document.getElementById('p3').checked)p.push('accessories');
    fetch('/admin/save-user',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:document.getElementById('un').value,password:document.getElementById('pw').value,permissions:p,action_type:act}})}}).then(r=>r.json()).then(d=>{{swal(d.status,d.message||"Saved","success");loadU()}})}}
    function delU(u){{if(confirm('Delete?'))fetch('/admin/delete-user',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{username:u}})}}).then(()=>loadU())}}
    function editU(u,p){{document.getElementById('un').value=u;document.getElementById('pw').value=p;document.querySelector('button[onclick]').onclick=()=>saveU('update');document.querySelector('button[onclick]').innerText="Update"}}
    </script></body></html>""",

    'closing_preview': f"""<!doctype html><html><head><title>Preview</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#f8f9fa;padding:30px}}.comp{{font-size:2.2rem;font-weight:800;color:#2c3e50;text-align:center}}.tbl th{{background:#fff!important;color:#000!important;border:1px solid #000;text-align:center;font-weight:900}}.tbl td{{border:1px solid #000;text-align:center;font-weight:600}}@media print{{.no-print{{display:none}}.col-head{{background:#2c3e50!important;color:#fff!important;-webkit-print-color-adjust:exact}}}}</style></head><body><div class="container">
    <div class="d-flex justify-content-end gap-2 no-print"><a href="/" class="btn btn-secondary">Back</a><a href="/download-closing-excel?ref_no={{{{ref_no}}}}" class="btn btn-success">Download Excel</a><button onclick="print()" class="btn btn-dark">Print</button></div>
    <div class="comp">COTTON CLOTHING BD LTD</div><h4 class="text-center">CLOSING REPORT [INPUT]</h4>
    <div class="d-flex justify-content-between p-3 bg-white mb-3 border"><div><h5>Buyer: {{{{report_data[0].buyer}}}}</h5><h5>Style: {{{{report_data[0].style}}}}</h5></div><div class="bg-dark text-white p-3 rounded"><h3>{{{{ref_no}}}}</h3></div></div>
    {{% for b in report_data %}}<div class="card mb-4 border-0"><div class="p-2 fw-bold text-white col-head" style="background:#2c3e50;font-size:1.4rem">COLOR: {{{{b.color}}}}</div><table class="table tbl mb-0"><thead><tr><th>SIZE</th><th>ORDER 3%</th><th>ACTUAL</th><th>CUT QC</th><th>INPUT</th><th>BALANCE</th><th>SHORT/PLUS</th><th>%</th></tr></thead><tbody>
    {{% set ns=namespace(t3=0,ta=0,tc=0,ti=0) %}}{{% for i in range(b.headers|length) %}}{{% set a=b.gmts_qty[i]|replace(',','')|int %}}{{% set p3=(a*1.03)|round|int %}}{{% set c=b.cut[i]|replace(',','')|int if i<b.cut|length else 0 %}}{{% set inp=b.input[i]|replace(',','')|int if i<b.input|length else 0 %}}{{% set ns.t3=ns.t3+p3 %}}{{% set ns.ta=ns.ta+a %}}{{% set ns.tc=ns.tc+c %}}{{% set ns.ti=ns.ti+inp %}}
    <tr><td>{{{{b.headers[i]}}}}</td><td style="background:#B9C2DF">{{{{p3}}}}</td><td>{{{{a}}}}</td><td>{{{{c}}}}</td><td style="background:#C4D09D">{{{{inp}}}}</td><td style="color:#c0392b">{{{{c-inp}}}}</td><td style="color:{{{{'green' if (inp-p3)>=0 else 'red'}}}}">{{{{inp-p3}}}}</td><td>{{{{ "%.2f"|format((inp-p3)/p3*100) if p3 else 0 }}}}%</td></tr>{{% endfor %}}
    <tr style="border-top:2px solid #000;font-size:1.2rem"><td>TOTAL</td><td>{{{{ns.t3}}}}</td><td>{{{{ns.ta}}}}</td><td>{{{{ns.tc}}}}</td><td>{{{{ns.ti}}}}</td><td>{{{{ns.tc-ns.ti}}}}</td><td>{{{{ns.ti-ns.t3}}}}</td><td>{{{{ "%.2f"|format((ns.ti-ns.t3)/ns.t3*100) if ns.t3 else 0 }}}}%</td></tr></tbody></table></div>{{% endfor %}}</div></body></html>""",

    'acc_search': f"""<!doctype html><html><head><title>Accessories</title>{CSS}</head><body><div class="center-container"><div class="glass-card" style="width:400px"><h1>Find Booking</h1><form action="/admin/accessories/input" method="post"><input name="ref_no" placeholder="Booking Ref.." required><button>Proceed</button></form><br><a href="/" style="color:#fff">Back</a></div></div></body></html>""",
    
    'acc_input': f"""<!doctype html><html><head><title>Entry</title>{CSS}</head><body><div class="center-container"><div class="glass-card" style="width:500px"><h1>New Challan</h1><p>Ref: {{{{ref}}}} | {{{{style}}}}</p><form action="/admin/accessories/save" method="post"><input type="hidden" name="ref" value="{{{{ref}}}}"><select name="item_type"><option value="">-- Item (Top/Btm) --</option><option value="Top">Top</option><option value="Bottom">Bottom</option></select><select name="color" required><option value="">-- Color --</option>{{% for c in colors %}}<option value="{{{{c}}}}">{{{{c}}}}</option>{{% endfor %}}</select><input name="line_no" placeholder="Line No" required><input name="size" placeholder="Size" value="-"><input type="number" name="qty" placeholder="Qty" required><button>Save</button></form><a href="/admin/accessories/print?ref={{{{ref}}}}" style="color:#a29bfe">View Only</a></div></div></body></html>""",
    
    'acc_report': f"""<!doctype html><html><head><title>Challan</title>{CSS}<style>body{{background:#fff;color:#000}}.cont{{border:2px solid #000;padding:20px;max-width:1000px;margin:auto}}.row{{display:flex;justify-content:space-between}}.inf{{border:1px dashed #555;padding:10px;flex:2}}.summ{{border:2px solid #000;background:#f9f9f9;padding:10px;margin:10px 0}}.tbl{{width:100%;border-collapse:collapse;margin-top:20px}}.tbl th{{background:#2c3e50;color:#fff;padding:10px;border:1px solid #000}}.tbl td{{border:1px solid #000;text-align:center;padding:5px;font-weight:600}}@media print{{.no-print{{display:none}}.cont{{border:none}}}}</style></head><body><div class="no-print" style="text-align:right;padding:10px"><a href="/admin/accessories" class="btn-sm" style="background:#555;color:#fff;text-decoration:none">Back</a> <form action="/admin/accessories/input" method="post" style="display:inline"><input type="hidden" name="ref_no" value="{{{{ref}}}}"><button style="width:auto;padding:5px">Add New</button></form> <button onclick="print()" style="width:auto;padding:5px;background:#2c3e50">Print</button></div><div class="cont"><h2 style="text-align:center">COTTON CLOTHING BD LTD</h2><p style="text-align:center">Kazi Tower, Tongi, Gazipur</p><div style="text-align:center;margin:10px"><span style="background:#2c3e50;color:#fff;padding:5px 20px;font-weight:bold">ACCESSORIES DELIVERY REPORT</span></div><div class="row"><div class="inf">Booking: <b>{{{{ref}}}}</b><br>Buyer: <b>{{{{buyer}}}}</b><br>Style: <b>{{{{style}}}}</b></div><div style="flex:1;text-align:right">Store: General<br>Send: Cutting<br>Item: <b style="border:1px solid #000;padding:2px">{{{{item_type or 'Top/Btm'}}}}</b></div></div><div class="summ"><center><b>LINE SUMMARY</b></center><div style="display:flex;flex-wrap:wrap;gap:15px;justify-content:center">{{% for l,q in line_summary.items() %}}<span>{{{{l}}}}: {{{{q}}}}</span>{{% endfor %}}</div></div><table class="tbl"><thead><tr><th>DATE</th><th>LINE</th><th>COLOR</th><th>SIZE</th><th>STS</th><th>QTY</th><th class="no-print">ACT</th></tr></thead><tbody>{{% set ns=namespace(t=0) %}}{{% for c in challans %}}{{% set ns.t=ns.t+c.qty|int %}}<tr><td>{{{{c.date}}}}</td><td>{{{{c.line}}}}</td><td>{{{{c.color}}}}</td><td>{{{{c.size}}}}</td><td style="color:green;font-size:1.2em">{{{{c.status}}}}</td><td>{{{{c.qty}}}}</td><td class="no-print"><a href="/admin/accessories/action?action=edit&ref={{{{ref}}}}&index={{{{loop.index0}}}}">✎</a> <form action="/admin/accessories/action?action=delete&index={{{{loop.index0}}}}" method="post" style="display:inline"><input type="hidden" name="ref" value="{{{{ref}}}}"><button style="padding:0;width:auto;background:none;color:red;font-size:1.2em">🗑</button></form></td></tr>{{% endfor %}}</tbody></table><div style="text-align:right;margin-top:10px;font-size:1.5em;font-weight:bold">TOTAL: {{{{ns.t}}}}</div><div style="display:flex;justify-content:space-between;margin-top:50px;text-align:center;font-weight:bold"><div>Store Incharge</div><div>Received By</div><div>Cutting Incharge</div></div></div></body></html>""",
    
    'acc_edit': f"""<!doctype html><html><head><title>Edit</title>{CSS}</head><body><div class="center-container"><div class="glass-card"><h1>Edit Entry</h1><form action="/admin/accessories/action?action=update&index={{{{index}}}}" method="post"><input type="hidden" name="ref" value="{{{{ref}}}}"><input name="line_no" value="{{{{item.line}}}}"><input name="color" value="{{{{item.color}}}}"><input name="size" value="{{{{item.size}}}}"><input name="qty" value="{{{{item.qty}}}}"><button>Update</button></form><a href="/admin/accessories/print?ref={{{{ref}}}}" style="color:#fff">Cancel</a></div></div></body></html>""",
    
    'po_report': f"""<!doctype html><html><head><title>PO Report</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{padding:20px}}.tot{{background-color:#e8f6f3!important;border:2px solid #000!important}}.tbl th{{background:#2c3e50;color:#fff}}@media print{{.no-print{{display:none}}.tbl th{{color:#000!important;border:1px solid #000}}}}</style></head><body><div class="container"><div class="no-print text-end mb-3"><a href="/" class="btn btn-secondary">Back</a> <button onclick="print()" class="btn btn-dark">Print</button></div><h2 class="text-center fw-bold">COTTON CLOTHING BD LTD</h2><p class="text-center">Purchase Order Summary</p>{{% if tables %}}<div class="row border p-2 mb-3"><div class="col-8 fw-bold">Buyer: {{{{meta.buyer}}}}<br>Booking: {{{{meta.booking}}}}<br>Style: {{{{meta.style}}}}</div><div class="col-4 text-end bg-dark text-white p-2 rounded"><h2>{{{{grand_total}}}}</h2><small>Pieces</small></div></div>{{% for t in tables %}}<div class="mb-4"><h4>COLOR: {{{{t.color}}}}</h4>{{{{t.table|safe}}}}</div>{{% endfor %}}{{% else %}}<h3>No Data Found</h3>{{% endif %}}</div></body></html>"""
}

if __name__ == '__main__':
    app.run(debug=True)
