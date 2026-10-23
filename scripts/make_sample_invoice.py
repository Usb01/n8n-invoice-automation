"""Creates samples/sample-invoice.pdf – a fictional supplier invoice for testing the upload webhook."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

out = Path(__file__).resolve().parent.parent / "samples" / "sample-invoice.pdf"
s = getSampleStyleSheet()
rows = [["Description", "Qty", "Unit price", "Amount"],
        ["Dell Latitude 5450 laptop", "4", "2,250.00", "9,000.00"],
        ["USB-C docking station", "4", "250.00", "1,000.00"],
        ["", "", "Subtotal", "10,000.00"], ["", "", "VAT 15%", "1,500.00"], ["", "", "Total (SAR)", "11,500.00"]]
t = Table(rows, colWidths=[240, 50, 90, 90])
t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                       ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                       ("LINEBELOW", (0, 0), (-1, 2), 0.5, colors.grey), ("FONTNAME", (2, 5), (-1, 5), "Helvetica-Bold")]))
story = [Paragraph("Gulf Tech Supplies", s["Title"]),
         Paragraph("VAT No. 310123456700003 · Dammam, Saudi Arabia (fictional company)", s["Normal"]),
         Spacer(1, 16),
         Paragraph("<b>TAX INVOICE</b> INV-2026-0412", s["Heading2"]),
         Paragraph("Invoice date: 05/10/2026 &nbsp;&nbsp; Due date: 04/11/2026", s["Normal"]),
         Paragraph("Bill to: Falcon Freight, Al Khobar", s["Normal"]), Spacer(1, 14), t]
SimpleDocTemplate(str(out), pagesize=A4, title="INV-2026-0412").build(story)
print("wrote", out)
