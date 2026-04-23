from flask_mail import Message
from extensions import mail
from flask import current_app, render_template_string
import logging

logger = logging.getLogger(__name__)

def send_email(to, subject, html_body):
    """Generic email sender with error handling."""
    try:
        msg = Message(subject=subject, recipients=[to], html=html_body)
        mail.send(msg)
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False

def send_otp_email(to_email, otp, name="User"):
    subject = "Your OTP - Milk Management System"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9;">
        <div style="background: #1a6b3c; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0;">🥛 Milk Management System</h1>
        </div>
        <div style="background: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #333;">Hello, {name}!</h2>
            <p style="color: #666;">Your One-Time Password (OTP) for verification is:</p>
            <div style="background: #f0f8f0; border: 2px solid #1a6b3c; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #1a6b3c;">{otp}</span>
            </div>
            <p style="color: #666;">This OTP is valid for <strong>5 minutes</strong>. Do not share it with anyone.</p>
            <p style="color: #999; font-size: 12px;">If you didn't request this OTP, please ignore this email.</p>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)

def send_approval_email(to_email, name, role):
    subject = "Account Approved - Milk Management System"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9;">
        <div style="background: #1a6b3c; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0;">🥛 Milk Management System</h1>
        </div>
        <div style="background: white; padding: 30px; border-radius: 0 0 8px 8px;">
            <h2 style="color: #1a6b3c;">🎉 Congratulations, {name}!</h2>
            <p>Your <strong>{role}</strong> account has been <strong style="color: #1a6b3c;">approved</strong>.</p>
            <p>You can now log in to the Milk Management System and start using all features.</p>
            <a href="#" style="display: inline-block; background: #1a6b3c; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin-top: 10px;">Login Now</a>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)

def send_rejection_email(to_email, name, role, reason=""):
    subject = "Account Status Update - Milk Management System"
    reason_text = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9;">
        <div style="background: #c0392b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0;">🥛 Milk Management System</h1>
        </div>
        <div style="background: white; padding: 30px; border-radius: 0 0 8px 8px;">
            <h2 style="color: #c0392b;">Account Not Approved</h2>
            <p>Dear {name},</p>
            <p>We regret to inform you that your <strong>{role}</strong> account registration has been <strong style="color: #c0392b;">rejected</strong>.</p>
            {reason_text}
            <p>You may re-register with updated information. If you believe this is an error, please contact support.</p>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)

def send_daily_summary_email(to_email, name, date, morning_qty, evening_qty, total_qty, total_income):
    subject = f"Daily Milk Summary - {date}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9;">
        <div style="background: #1a6b3c; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0;">🥛 Daily Summary</h1>
            <p style="color: #a8d5a2; margin: 5px 0 0;">{date}</p>
        </div>
        <div style="background: white; padding: 30px; border-radius: 0 0 8px 8px;">
            <p>Dear {name},</p>
            <p>Here is your milk collection summary for today:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background: #f0f8f0;">
                    <td style="padding: 12px; border: 1px solid #ddd;">🌅 Morning Collection</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: right;"><strong>{morning_qty} L</strong></td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd;">🌙 Evening Collection</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: right;"><strong>{evening_qty} L</strong></td>
                </tr>
                <tr style="background: #f0f8f0;">
                    <td style="padding: 12px; border: 1px solid #ddd;">📊 Total Collection</td>
                    <td style="padding: 12px; border: 1px solid #ddd; text-align: right;"><strong>{total_qty} L</strong></td>
                </tr>
                <tr style="background: #1a6b3c; color: white;">
                    <td style="padding: 12px; border: 1px solid #1a6b3c;">💰 Total Income</td>
                    <td style="padding: 12px; border: 1px solid #1a6b3c; text-align: right;"><strong>₹{total_income:.2f}</strong></td>
                </tr>
            </table>
        </div>
    </div>
    """
    return send_email(to_email, subject, html)
