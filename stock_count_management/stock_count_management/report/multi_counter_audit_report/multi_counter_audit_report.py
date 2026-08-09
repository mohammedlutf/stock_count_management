import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": _("Timestamp"), "fieldname": "scan_timestamp", "fieldtype": "Datetime", "width": 160},
        {"label": _("Session"), "fieldname": "session", "fieldtype": "Link", "options": "Stock Count Session", "width": 140},
        {"label": _("Counter User"), "fieldname": "counter", "fieldtype": "Link", "options": "User", "width": 160},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130},
        {"label": _("Batch No"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 120},
        {"label": _("Serial No"), "fieldname": "serial_no", "fieldtype": "Data", "width": 120},
        {"label": _("Scanned Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 110},
    ]

    conditions = []
    if filters.get("session"):
        conditions.append("ce.session = %(session)s")
    if filters.get("counter"):
        conditions.append("csl.counter = %(counter)s")
    if filters.get("warehouse"):
        conditions.append("ce.warehouse = %(warehouse)s")
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("DATE(csl.scan_timestamp) BETWEEN %(from_date)s AND %(to_date)s")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    query = f"""
        SELECT
            csl.scan_timestamp,
            ce.session,
            csl.counter,
            ce.item_code,
            ce.item_name,
            ce.warehouse,
            csl.batch_no,
            csl.serial_no,
            csl.qty
        FROM `tabCount Scan Log` csl
        INNER JOIN `tabCount Entry` ce ON ce.name = csl.parent
        {where_clause}
        ORDER BY csl.scan_timestamp DESC
    """

    data = frappe.db.sql(query, filters, as_dict=True)
    return columns, data