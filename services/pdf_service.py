from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
from datetime import datetime

def generate_invoice_pdf(provider, supplier, entries, month, year, summary):
    """
    Generate PDF invoice for a provider's monthly milk entries.
    Returns bytes of the PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    GREEN = colors.HexColor('#1a6b3c')
    LIGHT_GREEN = colors.HexColor('#e8f5e9')
    DARK = colors.HexColor('#1a1a1a')
    GRAY = colors.HexColor('#666666')
    
    styles = getSampleStyleSheet()
    story = []
    
    # Header
    title_style = ParagraphStyle('Title', fontSize=22, textColor=GREEN, alignment=TA_CENTER, spaceAfter=4, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Sub', fontSize=11, textColor=GRAY, alignment=TA_CENTER, spaceAfter=2)
    label_style = ParagraphStyle('Label', fontSize=10, textColor=GRAY, fontName='Helvetica')
    value_style = ParagraphStyle('Value', fontSize=10, textColor=DARK, fontName='Helvetica-Bold')
    
    story.append(Paragraph("🥛 MILK MANAGEMENT SYSTEM", title_style))
    story.append(Paragraph("Monthly Milk Invoice", subtitle_style))
    month_name = datetime(year, month, 1).strftime('%B %Y')
    story.append(Paragraph(f"Period: {month_name}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=12))
    
    # Provider and Supplier details in two columns
    detail_data = [
        [Paragraph("<b>PROVIDER DETAILS</b>", ParagraphStyle('h', fontSize=11, textColor=GREEN, fontName='Helvetica-Bold')),
         Paragraph("<b>SUPPLIER DETAILS</b>", ParagraphStyle('h', fontSize=11, textColor=GREEN, fontName='Helvetica-Bold'))],
        [Paragraph(f"Name: {provider['name']}", label_style), Paragraph(f"Business: {supplier['business_name']}", label_style)],
        [Paragraph(f"Email: {provider['email']}", label_style), Paragraph(f"Name: {supplier['name']}", label_style)],
        [Paragraph(f"Phone: {provider['phone']}", label_style), Paragraph(f"Location: {supplier['location']}", label_style)],
        [Paragraph(f"Invoice Date: {datetime.now().strftime('%d-%m-%Y')}", label_style), Paragraph(f"Phone: {supplier['phone']}", label_style)],
    ]
    detail_table = Table(detail_data, colWidths=[9*cm, 9*cm])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), LIGHT_GREEN),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fafafa')]),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#eeeeee')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 0.4*cm))
    
    # Entries table
    story.append(Paragraph("<b>MILK COLLECTION DETAILS</b>", ParagraphStyle('h2', fontSize=12, textColor=GREEN, fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=6)))
    
    table_data = [['#', 'Date', 'Session', 'Qty (L)', 'Fat %', 'SNF %', 'Rate (₹/L)', 'Total (₹)']]
    total_qty = 0
    total_amount = 0
    morning_qty = 0
    evening_qty = 0
    
    for i, entry in enumerate(entries, 1):
        session_label = entry['session'].capitalize()
        row = [
            str(i),
            entry['entry_date'].strftime('%d-%m-%Y') if hasattr(entry['entry_date'], 'strftime') else str(entry['entry_date']),
            session_label,
            f"{float(entry['quantity']):.2f}",
            f"{float(entry['fat']):.2f}",
            f"{float(entry['snf']):.2f}",
            f"₹{float(entry['price_per_liter']):.2f}",
            f"₹{float(entry['total']):.2f}",
        ]
        table_data.append(row)
        total_qty += float(entry['quantity'])
        total_amount += float(entry['total'])
        if entry['session'] == 'morning':
            morning_qty += float(entry['quantity'])
        else:
            evening_qty += float(entry['quantity'])
    
    # Total row
    table_data.append(['', '', 'TOTAL', f"{total_qty:.2f} L", '', '', '', f"₹{total_amount:.2f}"])
    
    col_widths = [1*cm, 2.5*cm, 2*cm, 2*cm, 1.8*cm, 1.8*cm, 2.5*cm, 2.7*cm]
    entries_table = Table(table_data, colWidths=col_widths)
    entries_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), GREEN),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, LIGHT_GREEN]),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#c8e6c9')),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bbbbbb')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(entries_table)
    story.append(Spacer(1, 0.4*cm))
    
    # Summary Box
    summary_data = [
        [Paragraph('<b>PAYMENT SUMMARY</b>', ParagraphStyle('ps', fontSize=12, textColor=GREEN, fontName='Helvetica-Bold')), ''],
        ['Morning Collection', f"{morning_qty:.2f} L"],
        ['Evening Collection', f"{evening_qty:.2f} L"],
        ['Total Collection', f"{total_qty:.2f} L"],
        ['Total Entries', str(len(entries))],
        [Paragraph('<b>TOTAL PAYABLE</b>', ParagraphStyle('tp', fontName='Helvetica-Bold')), Paragraph(f'<b>₹{total_amount:.2f}</b>', ParagraphStyle('ta', fontName='Helvetica-Bold', textColor=GREEN, alignment=TA_RIGHT))],
    ]
    summary_table = Table(summary_data, colWidths=[10*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), LIGHT_GREEN),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#fafafa')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#c8e6c9')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cccccc')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#eeeeee')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))
    story.append(summary_table)
    
    # Footer
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
    footer_style = ParagraphStyle('footer', fontSize=8, textColor=GRAY, alignment=TA_CENTER, spaceBefore=6)
    story.append(Paragraph("This is a system-generated invoice. Milk Management System © 2024", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
