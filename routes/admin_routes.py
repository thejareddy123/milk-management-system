from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from extensions import mysql, bcrypt
from functools import wraps
from services.email_service import send_approval_email, send_rejection_email
import json
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Unauthorized access.", 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# ──────────── DasHBOARD ────────────
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("select count(*) as total FROM suppliers where  status='approved'")
    total_suppliers = cur.fetchone()['total']
    cur.execute("select count(*) as total FROM providers where  status='approved'")
    total_providers = cur.fetchone()['total']
    cur.execute("select count(*) as total FROM suppliers where  status='pending'")
    pending_suppliers = cur.fetchone()['total']
    cur.execute("select count(*) as total FROM providers where  status='pending'")
    pending_providers = cur.fetchone()['total']
    cur.execute("select COALESCE(SUM(quantity),0) as total FROM milk_entries")
    total_milk = cur.fetchone()['total']
    cur.execute("select COALESCE(SUM(total),0) as total FROM milk_entries")
    total_revenue = cur.fetchone()['total']
    cur.execute("select count(*) as total FROM feedback where status='pending'")
    pending_feedback = cur.fetchone()['total']
    
    # Recent milk entries
    cur.execute("""
        select me.*, p.name as provider_name, s.name as supplier_name
        FROM milk_entries me
        join providers p ON me.provider_id = p.id
        join suppliers s ON me.supplier_id = s.id
        order BY me.created_at DESC limit 10
    """)
    recent_entries = cur.fetchall()
    cur.close()
    
    return render_template('admin/dashboard.html',
        total_suppliers=total_suppliers, total_providers=total_providers,
        pending_suppliers=pending_suppliers, pending_providers=pending_providers,
        total_milk=total_milk, total_revenue=total_revenue,
        pending_feedback=pending_feedback, recent_entries=recent_entries
    )

# ──────────── SUPPLIER MANAGEMENT ────────────
@admin_bp.route('/suppliers')
@admin_required
def suppliers():
    status_filter = request.args.get('status', 'all')
    cur = mysql.connection.cursor()
    if status_filter == 'all':
        cur.execute("select * FROM suppliers order BY created_at DESC")
    else:
        cur.execute("select * FROM suppliers where status=%s order BY created_at DESC", (status_filter,))
    suppliers = cur.fetchall()
    cur.close()
    return render_template('admin/suppliers.html', suppliers=suppliers, status_filter=status_filter)

@admin_bp.route('/suppliers/<int:supplier_id>')
@admin_required
def supplier_detail(supplier_id):
    cur = mysql.connection.cursor()
    cur.execute("select * FROM suppliers where id=%s", (supplier_id,))
    supplier = cur.fetchone()
    if not supplier:
        flash("Supplier not found.", 'error')
        return redirect(url_for('admin.suppliers'))
    cur.execute("select count(*) as cnt FROM providers where supplier_id=%s AND status='approved'", (supplier_id,))
    provider_count = cur.fetchone()['cnt']
    cur.execute("select COALESCE(SUM(quantity),0) as total FROM milk_entries where supplier_id=%s", (supplier_id,))
    total_milk = cur.fetchone()['total']
    cur.close()
    return render_template('admin/supplier_detail.html', supplier=supplier, provider_count=provider_count, total_milk=total_milk)

@admin_bp.route('/suppliers/<int:supplier_id>/approve', methods=['POST'])
@admin_required
def approve_supplier(supplier_id):
    cur = mysql.connection.cursor()
    cur.execute("select * FROM suppliers where id=%s", (supplier_id,))
    supplier = cur.fetchone()
    if supplier:
        cur.execute("update suppliers SET status='approved' where id=%s", (supplier_id,))
        mysql.connection.commit()
        send_approval_email(supplier['email'], supplier['name'], 'Supplier')
        flash(f"Supplier {supplier['name']} approved successfully.", 'success')
    cur.close()
    return redirect(url_for('admin.suppliers'))

@admin_bp.route('/suppliers/<int:supplier_id>/reject', methods=['POST'])
@admin_required
def reject_supplier(supplier_id):
    reason = request.form.get('reason', '')
    cur = mysql.connection.cursor()
    cur.execute("select * FROM suppliers where id=%s", (supplier_id,))
    supplier = cur.fetchone()
    if supplier:
        cur.execute("update suppliers SET status='rejected', rejection_reason=%s where id=%s", (reason, supplier_id))
        # Log the rejection
        cur.execute("insert into registration_log (email, role, reason) VALUES (%s,'supplier',%s)", (supplier['email'], reason))
        mysql.connection.commit()
        send_rejection_email(supplier['email'], supplier['name'], 'Supplier', reason)
        flash(f"Supplier {supplier['name']} rejected.", 'info')
    cur.close()
    return redirect(url_for('admin.suppliers'))

@admin_bp.route('/suppliers/<int:supplier_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_supplier_active(supplier_id):
    cur = mysql.connection.cursor()
    cur.execute("select is_active FROM suppliers where id=%s", (supplier_id,))
    s = cur.fetchone()
    if s:
        new_status = not s['is_active']
        cur.execute("update suppliers SET is_active=%s where id=%s", (new_status, supplier_id))
        mysql.connection.commit()
        flash("Supplier status updated.", 'success')
    cur.close()
    return redirect(url_for('admin.suppliers'))

# ──────────── PROVIDER MANAGEMENT ────────────
@admin_bp.route('/providers')
@admin_required
def providers():
    status_filter = request.args.get('status', 'all')
    cur = mysql.connection.cursor()
    if status_filter == 'all':
        cur.execute("""
            select p.*, s.name as supplier_name, s.business_name 
            FROM providers p join suppliers s ON p.supplier_id=s.id 
            order BY p.created_at DESC
        """)
    else:
        cur.execute("""
            select p.*, s.name as supplier_name, s.business_name 
            FROM providers p join suppliers s ON p.supplier_id=s.id 
            where p.status=%s order BY p.created_at DESC
        """, (status_filter,))
    providers = cur.fetchall()
    cur.close()
    return render_template('admin/providers.html', providers=providers, status_filter=status_filter)

@admin_bp.route('/providers/<int:provider_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_provider_active(provider_id):
    cur = mysql.connection.cursor()
    cur.execute("select is_active FROM providers where id=%s", (provider_id,))
    p = cur.fetchone()
    if p:
        new_status = not p['is_active']
        cur.execute("update providers SET is_active=%s where id=%s", (new_status, provider_id))
        mysql.connection.commit()
        flash("Provider status updated.", 'success')
    cur.close()
    return redirect(url_for('admin.providers'))

# ──────────── MILK RATES ────────────
@admin_bp.route('/rates')
@admin_required
def rates():
    cur = mysql.connection.cursor()
    cur.execute("select * FROM milk_rates order BY fat_min, snf_min")
    rates = cur.fetchall()
    cur.close()
    return render_template('admin/rates.html', rates=rates)

@admin_bp.route('/rates/add', methods=['POST'])
@admin_required
def add_rate():
    fat_min = request.form.get('fat_min')
    fat_max = request.form.get('fat_max')
    snf_min = request.form.get('snf_min')
    snf_max = request.form.get('snf_max')
    price = request.form.get('price_per_liter')
    
    try:
        fat_min, fat_max = float(fat_min), float(fat_max)
        snf_min, snf_max = float(snf_min), float(snf_max)
        price = float(price)
        if fat_min >= fat_max or snf_min >= snf_max or price <= 0:
            raise ValueError()
    except:
        flash("Invalid rate values. Ensure min < max and price > 0.", 'error')
        return redirect(url_for('admin.rates'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        insert into milk_rates (fat_min, fat_max, snf_min, snf_max, price_per_liter)
        VALUES (%s,%s,%s,%s,%s)
    """, (fat_min, fat_max, snf_min, snf_max, price))
    mysql.connection.commit()
    cur.close()
    flash("Rate added successfully.", 'success')
    return redirect(url_for('admin.rates'))

@admin_bp.route('/rates/<int:rate_id>/edit', methods=['POST'])
@admin_required
def edit_rate(rate_id):
    fat_min = request.form.get('fat_min')
    fat_max = request.form.get('fat_max')
    snf_min = request.form.get('snf_min')
    snf_max = request.form.get('snf_max')
    price = request.form.get('price_per_liter')
    is_active = 1 if request.form.get('is_active') else 0
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            update milk_rates SET fat_min=%s,fat_max=%s,snf_min=%s,snf_max=%s,price_per_liter=%s,is_active=%s
            where id=%s
        """, (fat_min, fat_max, snf_min, snf_max, price, is_active, rate_id))
        mysql.connection.commit()
        cur.close()
        flash("Rate updated.", 'success')
    except Exception as e:
        flash("Failed to update rate.", 'error')
    return redirect(url_for('admin.rates'))

@admin_bp.route('/rates/<int:rate_id>/delete', methods=['POST'])
@admin_required
def delete_rate(rate_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM milk_rates where id=%s", (rate_id,))
    mysql.connection.commit()
    cur.close()
    flash("Rate deleted.", 'info')
    return redirect(url_for('admin.rates'))

# ──────────── ALL MILK ENTRIES ────────────
@admin_bp.route('/milk-entries')
@admin_required
def milk_entries():
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    supplier_filter = request.args.get('supplier_id', 'all')
    
    cur = mysql.connection.cursor()
    query = """
        select me.*, p.name as provider_name, s.name as supplier_name, s.business_name
        FROM milk_entries me
        join providers p ON me.provider_id = p.id
        join suppliers s ON me.supplier_id = s.id
        where MONTH(me.entry_date)=%s AND YEAR(me.entry_date)=%s
    """
    params = [month, year]
    if supplier_filter != 'all':
        query += " AND me.supplier_id=%s"
        params.append(supplier_filter)
    query += " order BY me.entry_date, me.session"
    
    cur.execute(query, params)
    entries = cur.fetchall()
    cur.execute("select id, name, business_name FROM suppliers where status='approved'")
    suppliers = cur.fetchall()
    cur.close()
    
    # Stats
    total_qty = sum(float(e['quantity']) for e in entries)
    total_revenue = sum(float(e['total']) for e in entries)
    morning_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'morning')
    evening_qty = sum(float(e['quantity']) for e in entries if e['session'] == 'evening')
    
    return render_template('admin/milk_entries.html',
        entries=entries, month=month, year=year, suppliers=suppliers,
        supplier_filter=supplier_filter, total_qty=total_qty, total_revenue=total_revenue,
        morning_qty=morning_qty, evening_qty=evening_qty
    )

# ──────────── FEEDBACK ────────────
@admin_bp.route('/feedback')
@admin_required
def feedback():
    cur = mysql.connection.cursor()
    cur.execute("select * FROM feedback order BY created_at DESC")
    feedbacks = cur.fetchall()
    cur.close()
    return render_template('admin/feedback.html', feedbacks=feedbacks)

@admin_bp.route('/feedback/<int:fid>/respond', methods=['POST'])
@admin_required
def respond_feedback(fid):
    response = request.form.get('response', '')
    cur = mysql.connection.cursor()
    cur.execute("update feedback SET status='resolved', admin_response=%s where id=%s", (response, fid))
    mysql.connection.commit()
    cur.close()
    flash("Response sent.", 'success')
    return redirect(url_for('admin.feedback'))

# ──────────── ADD SUPPLIER MANUALLY ────────────
@admin_bp.route('/add-supplier', methods=['GET', 'POST'])
@admin_required
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        aadhaar = request.form.get('aadhaar', '').strip()
        business_name = request.form.get('business_name', '').strip()
        location = request.form.get('location', '').strip()
        password = request.form.get('password', '')
        
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                insert into suppliers (name,email,phone,aadhaar,business_name,location,password,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'approved')
            """, (name, email, phone, aadhaar, business_name, location, hashed))
            mysql.connection.commit()
            flash("Supplier added and approved.", 'success')
        except Exception as e:
            flash(f"Error: {e}", 'error')
        cur.close()
        return redirect(url_for('admin.suppliers'))
    return render_template('admin/add_supplier.html')

# ──────────── ADD PROVIDER MANUALLY ────────────
@admin_bp.route('/add-provider', methods=['GET', 'POST'])
@admin_required
def add_provider():
    cur = mysql.connection.cursor()
    cur.execute("select id, name, business_name FROM suppliers where status='approved'")
    suppliers = cur.fetchall()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        aadhaar = request.form.get('aadhaar', '').strip()
        supplier_id = request.form.get('supplier_id', '')
        password = request.form.get('password', '')
        
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        try:
            cur.execute("""
                insert into providers (name,email,phone,aadhaar,supplier_id,password,status)
                VALUES (%s,%s,%s,%s,%s,%s,'approved')
            """, (name, email, phone, aadhaar, supplier_id, hashed))
            mysql.connection.commit()
            flash("Provider added and approved.", 'success')
            cur.close()
            return redirect(url_for('admin.providers'))
        except Exception as e:
            flash(f"Error: {e}", 'error')
    
    cur.close()
    return render_template('admin/add_provider.html', suppliers=suppliers)

# ──────────── API: GET RATE FOR FAT/SNF ────────────
@admin_bp.route('/api/get-rate')
@admin_required
def api_get_rate():
    fat = request.args.get('fat', type=float)
    snf = request.args.get('snf', type=float)
    if fat is None or snf is None:
        return jsonify({'success': False, 'message': 'Invalid parameters'})
    cur = mysql.connection.cursor()
    cur.execute("""
        select * FROM milk_rates 
        where fat_min <= %s AND fat_max >= %s 
        AND snf_min <= %s AND snf_max >= %s 
        AND is_active=1 limit 1
    """, (fat, fat, snf, snf))
    rate = cur.fetchone()
    cur.close()
    if rate:
        return jsonify({'success': True, 'rate': float(rate['price_per_liter']), 'rate_id': rate['id']})
    return jsonify({'success': False, 'message': 'No matching rate found for given fat/SNF values.'})
