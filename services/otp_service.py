import hashlib
import random
import string
from datetime import datetime, timedelta
from extensions import mysql
from services.email_service import send_otp_email
from flask import current_app

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def send_otp(email, name, purpose='register'):
    """Generate, store, and send OTP. Returns (success, message)."""
    cur = mysql.connection.cursor()
    
    # Check resend cooldown
    cur.execute("""
        SELECT last_sent_at FROM otp_store 
        WHERE email=%s AND purpose=%s 
        ORDER BY created_at DESC LIMIT 1
    """, (email, purpose))
    existing = cur.fetchone()
    
    cooldown = current_app.config['OTP_RESEND_COOLDOWN_SECONDS']
    if existing:
        last_sent = existing['last_sent_at']
        if isinstance(last_sent, str):
            last_sent = datetime.strptime(last_sent, '%Y-%m-%d %H:%M:%S')
        elapsed = (datetime.now() - last_sent).total_seconds()
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            cur.close()
            return False, f"Please wait {remaining} seconds before resending OTP."
    
    otp = generate_otp()
    otp_hash = hash_otp(otp)
    expiry = datetime.now() + timedelta(minutes=current_app.config['OTP_EXPIRY_MINUTES'])
    now = datetime.now()
    
    # Delete old OTPs for this email+purpose
    cur.execute("DELETE FROM otp_store WHERE email=%s AND purpose=%s", (email, purpose))
    
    # Insert new OTP
    cur.execute("""
        INSERT INTO otp_store (email, otp_hash, purpose, expires_at, last_sent_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (email, otp_hash, purpose, expiry, now))
    mysql.connection.commit()
    cur.close()
    
    # Send email
    email_sent = send_otp_email(email, otp, name)
    if not email_sent:
        return False, "Failed to send OTP email. Please try again."
    
    return True, "OTP sent successfully."

def verify_otp(email, otp_input, purpose='register'):
    """Verify OTP. Returns (success, message)."""
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT otp_hash, expires_at FROM otp_store 
        WHERE email=%s AND purpose=%s 
        ORDER BY created_at DESC LIMIT 1
    """, (email, purpose))
    record = cur.fetchone()
    
    if not record:
        cur.close()
        return False, "OTP not found. Please request a new OTP."
    
    expires_at = record['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
    
    if datetime.now() > expires_at:
        cur.execute("DELETE FROM otp_store WHERE email=%s AND purpose=%s", (email, purpose))
        mysql.connection.commit()
        cur.close()
        return False, "OTP has expired. Please request a new OTP."
    
    if hash_otp(otp_input) != record['otp_hash']:
        cur.close()
        return False, "Invalid OTP. Please check and try again."
    
    # OTP verified - delete it
    cur.execute("DELETE FROM otp_store WHERE email=%s AND purpose=%s", (email, purpose))
    mysql.connection.commit()
    cur.close()
    return True, "OTP verified successfully."
