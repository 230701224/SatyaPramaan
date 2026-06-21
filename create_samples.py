import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_genuine():
    os.makedirs('samples', exist_ok=True)
    c = canvas.Canvas("samples/sample_genuine.pdf", pagesize=letter)
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "APEX TECH SOLUTIONS PVT LTD")
    c.setFont("Helvetica", 9)
    c.drawString(100, 685, "Regd. Office: 44, Electronic City, Bangalore")
    
    c.line(100, 675, 500, 675)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 650, "PAY SLIP FOR NOVEMBER 2025")
    
    # Details
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 620, "Employee Name:")
    c.setFont("Helvetica", 10)
    c.drawString(200, 620, "Karan Singh")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 600, "PAN Card No:")
    c.setFont("Helvetica", 10)
    c.drawString(200, 600, "BPHPS2930K")
    
    # Financial details
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 560, "Basic Salary:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 560, "85,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 540, "House Rent Allowance:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 540, "35,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 520, "Special Allowance:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 520, "25,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 500, "Gross Earnings:")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(400, 500, "1,45,000.00")
    
    c.line(100, 490, 500, 490)
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 470, "Total Deductions:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 470, "12,000.00")
    
    c.line(100, 460, 500, 460)
    
    # Net Pay
    c.setFont("Helvetica-Bold", 11)
    c.drawString(100, 430, "NET PAYOUT VALUE:")
    c.drawRightString(400, 430, "Rs. 1,33,000.00")
    
    c.save()
    print("Genuine sample PDF created at samples/sample_genuine.pdf")

def create_tampered():
    os.makedirs('samples', exist_ok=True)
    c = canvas.Canvas("samples/sample_tampered.pdf", pagesize=letter)
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "APEX TECH SOLUTIONS PVT LTD")
    c.setFont("Helvetica", 9)
    c.drawString(100, 685, "Regd. Office: 44, Electronic City, Bangalore")
    
    c.line(100, 675, 500, 675)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 650, "PAY SLIP FOR NOVEMBER 2025")
    
    # Details
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 620, "Employee Name:")
    c.setFont("Helvetica", 10)
    c.drawString(200, 620, "Karan Singh")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 600, "PAN Card No:")
    c.setFont("Helvetica", 10)
    c.drawString(200, 600, "BPHPS2930K")
    
    # Financial details
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 560, "Basic Salary:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 560, "85,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 540, "House Rent Allowance:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 540, "35,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 520, "Special Allowance:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 520, "25,000.00")
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 500, "Gross Earnings:")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(400, 500, "1,45,000.00")
    
    c.line(100, 490, 500, 490)
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(100, 470, "Total Deductions:")
    c.setFont("Helvetica", 10)
    c.drawRightString(400, 470, "12,000.00")
    
    c.line(100, 460, 500, 460)
    
    # Net Pay with Forged Number (Times-Roman instead of Helvetica)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(100, 430, "NET PAYOUT VALUE:")
    
    # Write the currency in Helvetica-Bold, and the forged amount in Times-Roman
    c.setFont("Helvetica-Bold", 11)
    c.drawString(275, 430, "Rs.")
    
    # The forged value: 2,33,000.00 instead of 1,33,000.00
    c.setFont("Times-Roman", 11)
    c.drawString(300, 430, "2,33,000.00")
    
    c.save()
    print("Tampered sample PDF created at samples/sample_tampered.pdf")

if __name__ == '__main__':
    create_genuine()
    create_tampered()
