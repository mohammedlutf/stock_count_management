import frappe
from frappe import _

def execute(filters=None):
    if not filters.get("session"):
        return [], []

    columns = [
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 150},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 220},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM", "width": 100},
        {"fieldname": "current_erp_qty", "label": _("Expected ERP Qty"), "fieldtype": "Float", "width": 140},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 110}
    ]

    data = frappe.db.sql("""
        SELECT 
            item_code,
            item_name,
            warehouse,
            stock_uom,
            current_erp_qty,
            status
        FROM `tabCount Entry`
        WHERE session = %s AND status = 'Pending'
        ORDER BY item_code ASC
    """, (filters.get("session")), as_dict=True)

    return columns, data