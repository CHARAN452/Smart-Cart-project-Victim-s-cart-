from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
from datetime import datetime

def generate_pdf(order, items, address=None, grand_total=0):

    file_path = f"invoice_{order['id']}.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = []

    # 🔹 Title
    elements.append(Paragraph("<b>VICTIM'S CART INVOICE</b>", styles['Title']))
    elements.append(Spacer(1, 10))

    # 🔹 Invoice Info
    elements.append(Paragraph(f"Invoice ID: INV-{order['id']:04d}", styles['Normal']))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y')}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 🔹 Customer Info
    elements.append(Paragraph("<b>Bill To:</b>", styles['Heading3']))
    elements.append(Paragraph(f"User ID: {order['user_id']}", styles['Normal']))

    # 🔹 ADDRESS (NEW)
    if address:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Delivery Address:</b>", styles['Heading3']))
        elements.append(Paragraph(
            f"{address['house_no']}, {address['area']}, {address['city']} - {address['pincode']}",
            styles['Normal']
        ))

    elements.append(Spacer(1, 15))

    # 🔹 Table Data
    data = [["Product", "Qty", "Unit Price", "Total"]]

    total = 0

    for item in items:
        amount = float(item['price']) * int(item['quantity'])
        total += amount

        data.append([
            item['product_name'],
            str(item['quantity']),
            f"₹{item['price']}",
            f"₹{amount}"
        ])

    # 🔹 Total Row
    data.append(["", "", "TOTAL", f"₹{total}"])

    # 🔹 Table
    table = Table(data, colWidths=[200, 80, 100, 100])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN',(1,1),(-1,-1),'CENTER'),
    ]))

    elements.append(table)

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Thank you for shopping with Victim's Cart ❤️", styles['Normal']))

    # Build PDF
    doc.build(elements)

    # 🔥 RETURN FILE (FIXED)
    return send_file(file_path, as_attachment=True)