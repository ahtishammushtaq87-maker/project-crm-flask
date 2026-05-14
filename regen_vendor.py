import re

with open(r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\app\routes\purchase.py', 'r', encoding='utf-8') as f:
    orig = f.read()

f_sales = open(r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\app\routes\sales.py', 'r', encoding='utf-8')
sales_py = f_sales.read()
f_sales.close()

def extract_func(src, name):
    lines = src.split('\n')
    start = -1
    for i, line in enumerate(lines):
        if line.startswith(f"def {name}("):
            start = i
            break
    end = start
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("def ") or lines[i].startswith("@bp.route"):
            if "customer_advances_json" in lines[i] or "public_purchase" in lines[i]:
                end = i
                while lines[end-1].strip() == '':
                    end -= 1
                return '\n'.join(lines[start:end])

cust_func = extract_func(sales_py, "customer_export_pdf")

replacements = [
    ("customer_export_pdf", "vendor_export_pdf"),
    ("Export customer profile", "Export vendor profile"),
    ("Customer", "Vendor"),
    ("customer.", "vendor."),
    ("customer = Vendor.query", "vendor = Vendor.query"), 
    ("customer_", "vendor_"),
    ("customer", "vendor"),
    ("InvoiceSettings", "PurchaseSettings"),
    ("Invoice design", "Purchase Bill design"),
    ("all_sales = sorted(vendor.sales", "all_bills = sorted(vendor.bills"),
    ("sales =", "bills ="),
    ("for sale in", "for bill in"),
    ("sale.", "bill."),
    ("sales", "bills"),
    ("Customer ID:", "Vendor ID:"),
    ("CUSTOMER PROFILE", "VENDOR PROFILE"),
    ("CUSTOMER DETAILS", "VENDOR DETAILS"),
    ("sales found", "bills found"),
    ("sale in bills:", "bill in bills:"), 
    ("invoice_number", "bill_number"),
    ("Invoice #", "Bill #"),
    ("tot_sales = sum(s.total", "tot_bills = sum(b.total"),
    ("tot_disc = sum(s.discount", "tot_disc = sum(b.discount"),
    ("for s in bills", "for b in bills"),
    ("tot_adv = vendor.total_advances_received", "tot_adv = vendor.total_advances_given"),
    ("Total Sales", "Total Purchases"),
    ("tot_sales", "tot_bills"),
    ("customer.company_name", "vendor.company_name"), # just in case
]

new_func = cust_func
for a, b in replacements:
    new_func = new_func.replace(a, b)

start_match = re.search(r"def vendor_export_pdf\(id\):", orig)
end_match = re.search(r"@bp\.route\('/public/purchase/<token>'\)", orig)

before = orig[:start_match.start()]
after = orig[end_match.start():]

with open(r'd:\prefex_flask\project_crm_flask\for table\project_crm_flask\app\routes\purchase.py', 'w', encoding='utf-8') as f:
    f.write(before + new_func + "\n\n" + after)

print("done")
