from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from extensions import mysql, bcrypt
from functools import wraps
from services.pdf_service import generate_invoice_pdf
from datetime import datetime
import re

provider_bp = Blueprint('provider', __name__, url_prefix='/provider')

def provider_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'provider':
            flash("Unauthorized access.", 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_provider():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.*, s.name AS supplier_name, s.business_name, s.location AS supplier_location, 
               s.phone AS supplier_phone, s.email AS supplier_email
        FROM providers p JOIN suppliers s ON p.supplier_id=s.id
        WHERE p.id=%s
    """, (session['user_id'],))
    p = cur.fetchone()
    cur.close()
    return p

# ──────────── DASHBOARD ────────────
@provider_bp.route('/dashboard')
@provider_required
def dashboard():
    pid = session['user_id']
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN session='morning' THEN quantity ELSE 0 END),0) AS morning_qty,
            COALESCE(SUM(CASE WHEN session='evening' THEN quantity ELSE 0 END),0) AS evening_qty,
            COALESCE(SUM(quantity),0) AS total_qty,
            COALESCE(SUM(total),0) AS total_income,
            COALESCE(SUM(CASE WHEN session='morning' THEN total ELSE 0 END),0) AS morning_income,
            COALESCE(SUM(CASE WHEN session='evening' THEN total ELSE 0 END),0) AS evening_income
        FROM milk_entries WHERE provider_id=%s AND MONTH(entry_date)=%s AND YEAR(entry_date)=%s
    """, (pid, month, year))
    stats = cur.fetchone()
    
    # Today's entries
    today = datetime.now().date()
    cur.execute("""
        SELECT * FROM milk_entries WHERE provider_id=%s AND entry_date=%s ORDER BY session
    """, (pid, today))
    today_entries = cur.fetchall()
    
    # Recent entries
    cur.execute("""
        SELECT * FROM milk_entries WHERE provider_id=%s 
        ORDER BY entry_date DESC, session LIMIT 10
    """, (pid,))
    recent = cur.fetchall()
    cur.close()
    
    provider = get_provider()
    return render_template('provider/dashboard.html',
        provider=provider, stats=stats, today_entries=today_entries,
        recent=recent, month=month, year=year, today=today
    )

# ──────────── REPORTS ────────────
@provider_bp.route('/reports')
@provider_required
def reports():
    pid = session['user_id']
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM milk_entries WHERE provider_id=%s 
        AND MONTH(entry_date)=%s AND YEAR(entry_date)=%s
        ORDER BY entry_date, session
    """, (pid, month, year))
    entries = cur.fetchall()
    cur.close()
    
    total_qty = sum(float(e['quantity']) for e in entries)
    total_income = sum(float(e['total']) for e in entries)
    morning_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'morning')
    evening_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'evening')
    
    if entries:
        by_date = {}
        for e in entries:
            d = str(e['entry_date'])
            by_date[d] = by_date.get(d, 0) + float(e['quantity'])
        max_day = max(by_date, key=by_date.get)
        min_day = min(by_date, key=by_date.get)
        max_day_qty = by_date[max_day]
        min_day_qty = by_date[min_day]
    else:
        max_day = min_day = max_day_qty = min_day_qty = None
    
    provider = get_provider()
    return render_template('provider/reports.html',
        provider=provider, entries=entries, month=month, year=year,
        total_qty=total_qty, total_income=total_income,
        morning_qty=morning_qty, evening_qty=evening_qty,
        max_day=max_day, min_day=min_day,
        max_day_qty=max_day_qty, min_day_qty=min_day_qty
    )

# ──────────── DOWNLOAD INVOICE ────────────
@provider_bp.route('/invoice/download')
@provider_required
def download_invoice():
    pid = session['user_id']
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.*, s.name AS supplier_name, s.business_name, s.location, s.phone AS supplier_phone
        FROM providers p JOIN suppliers s ON p.supplier_id=s.id WHERE p.id=%s
    """, (pid,))
    provider = cur.fetchone()
    
    cur.execute("""
        SELECT s.* FROM suppliers s 
        JOIN providers p ON p.supplier_id=s.id WHERE p.id=%s
    """, (pid,))
    supplier = cur.fetchone()
    
    cur.execute("""
        SELECT * FROM milk_entries WHERE provider_id=%s 
        AND MONTH(entry_date)=%s AND YEAR(entry_date)=%s
        ORDER BY entry_date, session
    """, (pid, month, year))
    entries = cur.fetchall()
    cur.close()
    
    if not entries:
        flash("No entries found for the selected period.", 'warning')
        return redirect(url_for('provider.reports'))
    
    summary = {
        'total_qty': sum(float(e['quantity']) for e in entries),
        'total_income': sum(float(e['total']) for e in entries)
    }
    
    pdf_bytes = generate_invoice_pdf(provider, supplier, entries, month, year, summary)
    month_name = datetime(year, month, 1).strftime('%B_%Y')
    filename = f"Invoice_{provider['name']}_{month_name}.pdf"
    
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# ──────────── PROFILE ────────────
@provider_bp.route('/profile', methods=['GET', 'POST'])
@provider_required
def profile():
    pid = session['user_id']
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not re.match(r'^[a-zA-Z\s]+$', name) or len(name) < 2:
            flash("Invalid name.", 'error')
        elif not re.match(r'^[6-9]\d{9}$', phone):
            flash("Invalid phone number.", 'error')
        else:
            cur.execute("UPDATE providers SET name=%s, phone=%s WHERE id=%s", (name, phone, pid))
            mysql.connection.commit()
            session['name'] = name
            flash("Profile updated successfully.", 'success')
    
    provider = get_provider()
    cur.close()
    return render_template('provider/profile.html', provider=provider)

# ──────────── FEEDBACK ────────────
@provider_bp.route('/feedback', methods=['GET', 'POST'])
@provider_required
def feedback():
    pid = session['user_id']
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')
        if not message.strip():
            flash("Message cannot be empty.", 'error')
        else:
            cur.execute("INSERT INTO feedback (user_id, user_type, subject, message) VALUES (%s,'provider',%s,%s)",
                        (pid, subject, message))
            mysql.connection.commit()
            flash("Feedback submitted.", 'success')
    cur.execute("SELECT * FROM feedback WHERE user_id=%s AND user_type='provider' ORDER BY created_at DESC", (pid,))
    feedbacks = cur.fetchall()
    cur.close()
    provider = get_provider()
    return render_template('provider/feedback.html', provider=provider, feedbacks=feedbacks)
