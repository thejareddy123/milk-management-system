from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, make_response
from extensions import mysql, bcrypt
from functools import wraps
from services.email_service import send_approval_email, send_rejection_email
from services.pdf_service import generate_invoice_pdf
from datetime import datetime, date
import re

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')

def supplier_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'supplier':
            flash("Unauthorized access.", 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_supplier():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM suppliers WHERE id=%s", (session['user_id'],))
    s = cur.fetchone()
    cur.close()
    return s

# ──────────── DASHBOARD ────────────
@supplier_bp.route('/dashboard')
@supplier_required
def dashboard():
    sid = session['user_id']
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM providers WHERE supplier_id=%s AND status='approved'", (sid,))
    total_providers = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) AS cnt FROM providers WHERE supplier_id=%s AND status='pending'", (sid,))
    pending_providers = cur.fetchone()['cnt']
    
    cur.execute("""
        SELECT COALESCE(SUM(quantity),0) AS total,
               COALESCE(SUM(CASE WHEN session='morning' THEN quantity ELSE 0 END),0) AS morning,
               COALESCE(SUM(CASE WHEN session='evening' THEN quantity ELSE 0 END),0) AS evening,
               COALESCE(SUM(total),0) AS revenue
        FROM milk_entries WHERE supplier_id=%s AND MONTH(entry_date)=%s AND YEAR(entry_date)=%s
    """, (sid, month, year))
    stats = cur.fetchone()
    
    # Recent entries
    cur.execute("""
        SELECT me.*, p.name AS provider_name
        FROM milk_entries me JOIN providers p ON me.provider_id=p.id
        WHERE me.supplier_id=%s ORDER BY me.entry_date DESC, me.session LIMIT 10
    """, (sid,))
    recent = cur.fetchall()
    cur.close()
    
    return render_template('supplier/dashboard.html',
        supplier=get_supplier(), stats=stats, recent=recent,
        total_providers=total_providers, pending_providers=pending_providers,
        month=month, year=year
    )

# ──────────── PROVIDERS ────────────
@supplier_bp.route('/providers')
@supplier_required
def providers():
    sid = session['user_id']
    status_filter = request.args.get('status', 'all')
    cur = mysql.connection.cursor()
    if status_filter == 'all':
        cur.execute("SELECT * FROM providers WHERE supplier_id=%s ORDER BY created_at DESC", (sid,))
    else:
        cur.execute("SELECT * FROM providers WHERE supplier_id=%s AND status=%s ORDER BY created_at DESC", (sid, status_filter))
    providers = cur.fetchall()
    cur.close()
    return render_template('supplier/providers.html', providers=providers, status_filter=status_filter)

@supplier_bp.route('/providers/<int:pid>')
@supplier_required
def provider_detail(pid):
    sid = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM providers WHERE id=%s AND supplier_id=%s", (pid, sid))
    provider = cur.fetchone()
    if not provider:
        flash("Provider not found.", 'error')
        return redirect(url_for('supplier.providers'))
    cur.execute("""
        SELECT COALESCE(SUM(quantity),0) AS total_qty, COALESCE(SUM(total),0) AS total_income
        FROM milk_entries WHERE provider_id=%s
    """, (pid,))
    stats = cur.fetchone()
    cur.close()
    return render_template('supplier/provider_detail.html', provider=provider, stats=stats)

@supplier_bp.route('/providers/<int:pid>/approve', methods=['POST'])
@supplier_required
def approve_provider(pid):
    sid = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM providers WHERE id=%s AND supplier_id=%s", (pid, sid))
    provider = cur.fetchone()
    if provider:
        cur.execute("UPDATE providers SET status='approved' WHERE id=%s", (pid,))
        mysql.connection.commit()
        send_approval_email(provider['email'], provider['name'], 'Provider')
        flash(f"Provider {provider['name']} approved.", 'success')
    cur.close()
    return redirect(url_for('supplier.providers'))

@supplier_bp.route('/providers/<int:pid>/reject', methods=['POST'])
@supplier_required
def reject_provider(pid):
    sid = session['user_id']
    reason = request.form.get('reason', '')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM providers WHERE id=%s AND supplier_id=%s", (pid, sid))
    provider = cur.fetchone()
    if provider:
        cur.execute("UPDATE providers SET status='rejected', rejection_reason=%s WHERE id=%s", (reason, pid))
        cur.execute("INSERT INTO registration_log (email, role, reason) VALUES (%s,'provider',%s)", (provider['email'], reason))
        mysql.connection.commit()
        send_rejection_email(provider['email'], provider['name'], 'Provider', reason)
        flash(f"Provider {provider['name']} rejected.", 'info')
    cur.close()
    return redirect(url_for('supplier.providers'))

# ──────────── MILK ENTRY ────────────
@supplier_bp.route('/milk-entry', methods=['GET', 'POST'])
@supplier_required
def milk_entry():
    sid = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM providers WHERE supplier_id=%s AND status='approved' AND is_active=1", (sid,))
    providers = cur.fetchall()
    cur.execute("SELECT * FROM milk_rates WHERE is_active=1 ORDER BY fat_min, snf_min")
    rates = cur.fetchall()
    
    if request.method == 'POST':
        provider_id = request.form.get('provider_id')
        entry_date = request.form.get('entry_date', date.today().isoformat())
        entry_session = request.form.get('session')
        quantity = request.form.get('quantity')
        fat = request.form.get('fat')
        snf = request.form.get('snf')
        rate_id = request.form.get('rate_id')
        
        # Validate provider belongs to supplier
        cur.execute("SELECT id FROM providers WHERE id=%s AND supplier_id=%s AND status='approved'", (provider_id, sid))
        if not cur.fetchone():
            return jsonify({'success': False, 'message': 'Invalid provider.'})
        
        try:
            quantity = float(quantity)
            fat = float(fat)
            snf = float(snf)
            if quantity <= 0:
                return jsonify({'success': False, 'message': 'Quantity must be greater than 0.'})
            if fat <= 0 or fat > 10:
                return jsonify({'success': False, 'message': 'Fat % must be between 0 and 10.'})
            if snf <= 0 or snf > 15:
                return jsonify({'success': False, 'message': 'SNF % must be between 0 and 15.'})
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid numeric values.'})
        
        # Get rate
        if rate_id:
            cur.execute("SELECT * FROM milk_rates WHERE id=%s AND is_active=1", (rate_id,))
            rate = cur.fetchone()
        else:
            cur.execute("""
                SELECT * FROM milk_rates 
                WHERE fat_min<=%s AND fat_max>=%s AND snf_min<=%s AND snf_max>=%s AND is_active=1 LIMIT 1
            """, (fat, fat, snf, snf))
            rate = cur.fetchone()
        
        if not rate:
            cur.close()
            return jsonify({'success': False, 'message': 'No matching rate found for the given fat and SNF values. Please contact admin.'})
        
        price_per_liter = float(rate['price_per_liter'])
        total = quantity * price_per_liter
        
        # Check duplicate
        cur.execute("""
            SELECT id FROM milk_entries WHERE provider_id=%s AND entry_date=%s AND session=%s
        """, (provider_id, entry_date, entry_session))
        if cur.fetchone():
            cur.close()
            return jsonify({'success': False, 'message': f'Entry for this provider on {entry_date} ({entry_session}) already exists.'})
        
        cur.execute("""
            INSERT INTO milk_entries (provider_id, supplier_id, entry_date, session, quantity, fat, snf, rate_id, price_per_liter, total)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (provider_id, sid, entry_date, entry_session, quantity, fat, snf, rate['id'], price_per_liter, total))
        mysql.connection.commit()
        cur.close()
        return jsonify({'success': True, 'message': f'Milk entry added. Total: ₹{total:.2f}', 'total': total, 'price': price_per_liter})
    
    cur.close()
    return render_template('supplier/milk_entry.html', providers=providers, rates=rates, today=date.today().isoformat())

# ──────────── MILK DATA / REPORTS ────────────
@supplier_bp.route('/milk-data')
@supplier_required
def milk_data():
    sid = session['user_id']
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    provider_filter = request.args.get('provider_id', 'all')
    
    cur = mysql.connection.cursor()
    query = """
        SELECT me.*, p.name AS provider_name
        FROM milk_entries me JOIN providers p ON me.provider_id=p.id
        WHERE me.supplier_id=%s AND MONTH(me.entry_date)=%s AND YEAR(me.entry_date)=%s
    """
    params = [sid, month, year]
    if provider_filter != 'all':
        query += " AND me.provider_id=%s"
        params.append(provider_filter)
    query += " ORDER BY me.entry_date, me.session"
    
    cur.execute(query, params)
    entries = cur.fetchall()
    cur.execute("SELECT id, name FROM providers WHERE supplier_id=%s AND status='approved'", (sid,))
    providers = cur.fetchall()
    cur.close()
    
    # Stats
    total_qty = sum(float(e['quantity']) for e in entries)
    total_revenue = sum(float(e['total']) for e in entries)
    morning_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'morning')
    evening_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'evening')
    
    # Min/Max day by quantity
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
    
    return render_template('supplier/milk_data.html',
        entries=entries, month=month, year=year, providers=providers,
        provider_filter=provider_filter, total_qty=total_qty,
        total_revenue=total_revenue, morning_qty=morning_qty, evening_qty=evening_qty,
        max_day=max_day, min_day=min_day, max_day_qty=max_day_qty, min_day_qty=min_day_qty
    )

# ──────────── API: LOOKUP RATE ────────────
@supplier_bp.route('/api/lookup-rate')
@supplier_required
def api_lookup_rate():
    fat = request.args.get('fat', type=float)
    snf = request.args.get('snf', type=float)
    if fat is None or snf is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'})
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM milk_rates 
        WHERE fat_min<=%s AND fat_max>=%s AND snf_min<=%s AND snf_max>=%s AND is_active=1 LIMIT 1
    """, (fat, fat, snf, snf))
    rate = cur.fetchone()
    cur.close()
    if rate:
        return jsonify({'success': True, 'rate': float(rate['price_per_liter']), 'rate_id': rate['id'],
                        'fat_range': f"{rate['fat_min']}-{rate['fat_max']}",
                        'snf_range': f"{rate['snf_min']}-{rate['snf_max']}"})
    return jsonify({'success': False, 'message': 'No matching rate.'})

# ──────────── PROFILE ────────────
@supplier_bp.route('/profile', methods=['GET', 'POST'])
@supplier_required
def profile():
    sid = session['user_id']
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        business_name = request.form.get('business_name', '').strip()
        location = request.form.get('location', '').strip()
        
        if not re.match(r'^[a-zA-Z\s]+$', name) or len(name) < 2:
            flash("Invalid name.", 'error')
        elif not re.match(r'^[6-9]\d{9}$', phone):
            flash("Invalid phone number.", 'error')
        elif len(business_name) < 2:
            flash("Invalid business name.", 'error')
        elif len(location) < 3:
            flash("Invalid location.", 'error')
        else:
            cur.execute("UPDATE suppliers SET name=%s, phone=%s, business_name=%s, location=%s WHERE id=%s",
                        (name, phone, business_name, location, sid))
            mysql.connection.commit()
            session['name'] = name
            flash("Profile updated successfully.", 'success')
    
    cur.execute("SELECT * FROM suppliers WHERE id=%s", (sid,))
    supplier = cur.fetchone()
    cur.close()
    return render_template('supplier/profile.html', supplier=supplier)

# ──────────── FEEDBACK ────────────
@supplier_bp.route('/feedback', methods=['GET', 'POST'])
@supplier_required
def feedback():
    sid = session['user_id']
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')
        if not message.strip():
            flash("Message cannot be empty.", 'error')
        else:
            cur.execute("INSERT INTO feedback (user_id, user_type, subject, message) VALUES (%s,'supplier',%s,%s)",
                        (sid, subject, message))
            mysql.connection.commit()
            flash("Feedback submitted.", 'success')
    cur.execute("SELECT * FROM feedback WHERE user_id=%s AND user_type='supplier' ORDER BY created_at DESC", (sid,))
    feedbacks = cur.fetchall()
    cur.close()
    return render_template('supplier/feedback.html', feedbacks=feedbacks)
