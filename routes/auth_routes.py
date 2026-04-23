from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from extensions import mysql, bcrypt
from services.otp_service import send_otp, verify_otp
from services.email_service import send_approval_email
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

# ──────────────────────────── HELPERS ────────────────────────────
def validate_phone(phone):
    return re.match(r'^[6-9]\d{9}$', phone)

def validate_aadhaar(aadhaar):
    return re.match(r'^\d{12}$', aadhaar)

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number."
    return True, ""

def validate_name(name):
    if not name or len(name.strip()) < 2:
        return False, "Name must be at least 2 characters."
    if not re.match(r'^[a-zA-Z\s]+$', name):
        return False, "Name must contain only letters and spaces."
    return True, ""

def email_exists_in_db(email):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM suppliers WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        return True
    cur.execute("SELECT id FROM providers WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        return True
    cur.execute("SELECT id FROM admins WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        return True
    cur.close()
    return False

# ──────────────────────────── INDEX ────────────────────────────
@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

# ──────────────────────────── LOGIN ────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', '')

        generic_error = "Invalid email or password."

        if role == 'admin':
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
            admin = cur.fetchone()
            cur.close()
            if admin and bcrypt.check_password_hash(admin['password'], password):
                session.clear()
                session['user_id'] = admin['id']
                session['role'] = 'admin'
                session['name'] = admin['name']
                session.permanent = True
                return redirect(url_for('admin.dashboard'))
            flash(generic_error, 'error')
            return render_template('auth/login.html')

        elif role == 'supplier':
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM suppliers WHERE email=%s", (email,))
            user = cur.fetchone()
            cur.close()
            if user and bcrypt.check_password_hash(user['password'], password):
                if user['status'] == 'pending':
                    flash("Your account is pending admin approval. Please wait.", 'warning')
                    return render_template('auth/login.html')
                elif user['status'] == 'rejected':
                    flash("Your account has been rejected. Please contact support or re-register.", 'error')
                    return render_template('auth/login.html')
                elif not user['is_active']:
                    flash("Your account has been deactivated. Please contact admin.", 'error')
                    return render_template('auth/login.html')
                session.clear()
                session['user_id'] = user['id']
                session['role'] = 'supplier'
                session['name'] = user['name']
                session.permanent = True
                return redirect(url_for('supplier.dashboard'))
            flash(generic_error, 'error')
            return render_template('auth/login.html')

        elif role == 'provider':
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM providers WHERE email=%s", (email,))
            user = cur.fetchone()
            cur.close()
            if user and bcrypt.check_password_hash(user['password'], password):
                if user['status'] == 'pending':
                    flash("Your account is pending supplier approval. Please wait.", 'warning')
                    return render_template('auth/login.html')
                elif user['status'] == 'rejected':
                    flash("Your account has been rejected. Please contact your supplier or re-register.", 'error')
                    return render_template('auth/login.html')
                elif not user['is_active']:
                    flash("Your account has been deactivated. Please contact your supplier.", 'error')
                    return render_template('auth/login.html')
                session.clear()
                session['user_id'] = user['id']
                session['role'] = 'provider'
                session['name'] = user['name']
                session.permanent = True
                return redirect(url_for('provider.dashboard'))
            flash(generic_error, 'error')
            return render_template('auth/login.html')

        flash("Please select a valid role.", 'error')
    return render_template('auth/login.html')

# ──────────────────────────── LOGOUT ────────────────────────────
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", 'success')
    return redirect(url_for('auth.login'))

# ──────────────────────────── SUPPLIER REGISTER ────────────────────────────
@auth_bp.route('/register/supplier', methods=['GET', 'POST'])
def register_supplier():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        aadhaar = request.form.get('aadhaar', '').strip()
        business_name = request.form.get('business_name', '').strip()
        location = request.form.get('location', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = request.form.get('terms')

        # Validations
        valid_name, name_err = validate_name(name)
        if not valid_name:
            flash(name_err, 'error'); return render_template('auth/register_supplier.html')
        
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
            flash("Invalid email format.", 'error'); return render_template('auth/register_supplier.html')
        
        if not validate_phone(phone):
            flash("Phone must be 10 digits and start with 6-9.", 'error'); return render_template('auth/register_supplier.html')
        
        if not validate_aadhaar(aadhaar):
            flash("Aadhaar must be exactly 12 digits.", 'error'); return render_template('auth/register_supplier.html')
        
        if not business_name or len(business_name) < 2:
            flash("Business name must be at least 2 characters.", 'error'); return render_template('auth/register_supplier.html')
        
        if not location or len(location) < 3:
            flash("Location must be at least 3 characters.", 'error'); return render_template('auth/register_supplier.html')
        
        valid_pw, pw_err = validate_password(password)
        if not valid_pw:
            flash(pw_err, 'error'); return render_template('auth/register_supplier.html')
        
        if password != confirm_password:
            flash("Passwords do not match.", 'error'); return render_template('auth/register_supplier.html')
        
        if not terms:
            flash("You must accept the Terms & Conditions.", 'error'); return render_template('auth/register_supplier.html')
        
        if email_exists_in_db(email):
            flash("This email is already registered.", 'error'); return render_template('auth/register_supplier.html')
        
        # Store in session and send OTP
        session['reg_supplier'] = {
            'name': name, 'email': email, 'phone': phone, 'aadhaar': aadhaar,
            'business_name': business_name, 'location': location,
            'password': bcrypt.generate_password_hash(password).decode('utf-8')
        }
        
        ok, msg = send_otp(email, name, purpose='register')
        if not ok:
            flash(msg, 'error'); return render_template('auth/register_supplier.html')
        
        session['otp_email'] = email
        session['otp_purpose'] = 'register'
        session['otp_role'] = 'supplier'
        flash("OTP sent to your email. Please verify.", 'info')
        return redirect(url_for('auth.verify_otp_page'))
    
    return render_template('auth/register_supplier.html')

# ──────────────────────────── PROVIDER REGISTER ────────────────────────────
@auth_bp.route('/register/provider', methods=['GET', 'POST'])
def register_provider():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, business_name FROM suppliers WHERE status='approved' AND is_active=1")
    suppliers = cur.fetchall()
    cur.close()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        aadhaar = request.form.get('aadhaar', '').strip()
        supplier_id = request.form.get('supplier_id', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        terms = request.form.get('terms')

        valid_name, name_err = validate_name(name)
        if not valid_name:
            flash(name_err, 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w{2,}$', email):
            flash("Invalid email format.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if not validate_phone(phone):
            flash("Phone must be 10 digits and start with 6-9.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if not validate_aadhaar(aadhaar):
            flash("Aadhaar must be exactly 12 digits.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if not supplier_id:
            flash("Please select a supplier.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        valid_pw, pw_err = validate_password(password)
        if not valid_pw:
            flash(pw_err, 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if password != confirm_password:
            flash("Passwords do not match.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if not terms:
            flash("You must accept the Terms & Conditions.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        if email_exists_in_db(email):
            flash("This email is already registered.", 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        # Store in session
        session['reg_provider'] = {
            'name': name, 'email': email, 'phone': phone, 'aadhaar': aadhaar,
            'supplier_id': supplier_id,
            'password': bcrypt.generate_password_hash(password).decode('utf-8')
        }
        
        ok, msg = send_otp(email, name, purpose='register')
        if not ok:
            flash(msg, 'error'); return render_template('auth/register_provider.html', suppliers=suppliers)
        
        session['otp_email'] = email
        session['otp_purpose'] = 'register'
        session['otp_role'] = 'provider'
        flash("OTP sent to your email. Please verify.", 'info')
        return redirect(url_for('auth.verify_otp_page'))
    
    return render_template('auth/register_provider.html', suppliers=suppliers)

# ──────────────────────────── OTP VERIFY ────────────────────────────
@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp_page():
    if 'otp_email' not in session:
        flash("Session expired. Please register again.", 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        email = session.get('otp_email')
        purpose = session.get('otp_purpose', 'register')
        role = session.get('otp_role', '')
        
        ok, msg = verify_otp(email, otp_input, purpose)
        if not ok:
            flash(msg, 'error')
            return render_template('auth/verify_otp.html', email=email, purpose=purpose)
        
        if purpose == 'register':
            cur = mysql.connection.cursor()
            if role == 'supplier':
                data = session.get('reg_supplier')
                if not data:
                    flash("Session lost. Please register again.", 'error')
                    return redirect(url_for('auth.register_supplier'))
                cur.execute("""
                    INSERT INTO suppliers (name, email, phone, aadhaar, business_name, location, password)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (data['name'], data['email'], data['phone'], data['aadhaar'],
                      data['business_name'], data['location'], data['password']))
                mysql.connection.commit()
                session.pop('reg_supplier', None)
                flash("Registration successful! Your account is pending admin approval.", 'success')
            
            elif role == 'provider':
                data = session.get('reg_provider')
                if not data:
                    flash("Session lost. Please register again.", 'error')
                    return redirect(url_for('auth.register_provider'))
                cur.execute("""
                    INSERT INTO providers (name, email, phone, aadhaar, supplier_id, password)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (data['name'], data['email'], data['phone'], data['aadhaar'],
                      data['supplier_id'], data['password']))
                mysql.connection.commit()
                session.pop('reg_provider', None)
                flash("Registration successful! Your account is pending supplier approval.", 'success')
            cur.close()
        
        elif purpose == 'forgot_password':
            session['pw_reset_email'] = email
            session['pw_reset_role'] = role
            return redirect(url_for('auth.reset_password'))
        
        session.pop('otp_email', None)
        session.pop('otp_purpose', None)
        session.pop('otp_role', None)
        return redirect(url_for('auth.login'))
    
    return render_template('auth/verify_otp.html', email=session.get('otp_email'), purpose=session.get('otp_purpose'))

# ──────────────────────────── RESEND OTP ────────────────────────────
@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('otp_email')
    purpose = session.get('otp_purpose', 'register')
    role = session.get('otp_role', '')
    
    if not email:
        return jsonify({'success': False, 'message': 'Session expired.'})
    
    # Get name
    name = 'User'
    reg_data = session.get(f'reg_{role}')
    if reg_data:
        name = reg_data.get('name', 'User')
    
    ok, msg = send_otp(email, name, purpose)
    return jsonify({'success': ok, 'message': msg})

# ──────────────────────────── FORGOT PASSWORD ────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '').strip()
        
        # Always show same message for security (even if not found)
        flash("If the email exists, an OTP has been sent to it.", 'info')
        
        # Find user
        cur = mysql.connection.cursor()
        user = None
        if role == 'supplier':
            cur.execute("SELECT * FROM suppliers WHERE email=%s", (email,))
            user = cur.fetchone()
        elif role == 'provider':
            cur.execute("SELECT * FROM providers WHERE email=%s", (email,))
            user = cur.fetchone()
        elif role == 'admin':
            cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
            user = cur.fetchone()
        cur.close()
        
        if user:
            ok, msg = send_otp(email, user['name'], purpose='forgot_password')
            if ok:
                session['otp_email'] = email
                session['otp_purpose'] = 'forgot_password'
                session['otp_role'] = role
                return redirect(url_for('auth.verify_otp_page'))
        else:
            # Still show the "OTP sent" message but don't actually do anything
            # Edge case: email not registered
            pass
        
        return render_template('auth/forgot_password.html')
    
    return render_template('auth/forgot_password.html')

# ──────────────────────────── RESET PASSWORD ────────────────────────────
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'pw_reset_email' not in session:
        flash("Session expired. Please try again.", 'error')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        valid_pw, pw_err = validate_password(password)
        if not valid_pw:
            flash(pw_err, 'error')
            return render_template('auth/reset_password.html')
        
        if password != confirm_password:
            flash("Passwords do not match.", 'error')
            return render_template('auth/reset_password.html')
        
        email = session['pw_reset_email']
        role = session.get('pw_reset_role', '')
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        
        cur = mysql.connection.cursor()
        if role == 'supplier':
            cur.execute("UPDATE suppliers SET password=%s WHERE email=%s", (hashed, email))
        elif role == 'provider':
            cur.execute("UPDATE providers SET password=%s WHERE email=%s", (hashed, email))
        elif role == 'admin':
            cur.execute("UPDATE admins SET password=%s WHERE email=%s", (hashed, email))
        mysql.connection.commit()
        cur.close()
        
        session.pop('pw_reset_email', None)
        session.pop('pw_reset_role', None)
        flash("Password reset successful! You can now login.", 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')

# ──────────────────────────── TERMS ────────────────────────────
@auth_bp.route('/terms')
def terms():
    return render_template('auth/terms.html')
