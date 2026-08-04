import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {"fieldname": "session", "label": _("Session ID"), "fieldtype": "Link", "options": "Stock Count Session", "width": 160},
        {"fieldname": "session_name", "label": _("Session Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "count_type", "label": _("Count Type"), "fieldtype": "Data", "width": 120},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 110},
        {"fieldname": "total_items", "label": _("Total Items"), "fieldtype": "Int", "width": 100},
        {"fieldname": "counted_items", "label": _("Counted Items"), "fieldtype": "Int", "width": 110},
        {"fieldname": "uncounted_items", "label": _("Uncounted Items"), "fieldtype": "Int", "width": 120},
        {"fieldname": "completion_percent", "label": _("Completion %"), "fieldtype": "Percent", "width": 120}
    ]

    conditions = ["1=1"]
    params = {}

    if filters.get("company"):
        conditions.append("company = %(company)s")
        params["company"] = filters.get("company")

    if filters.get("warehouse"):
        conditions.append("warehouse = %(warehouse)s")
        params["warehouse"] = filters.get("warehouse")

    if filters.get("status"):
        conditions.append("status = %(status)s")
        params["status"] = filters.get("status")

    data = frappe.db.sql(f"""
        SELECT 
            name as session,
            session_name,
            count_type,
            warehouse,
            status,
            total_items,
            counted_items,
            uncounted_items,
            completion_percent
        FROM `tabStock Count Session`
        WHERE {" AND ".join(conditions)}
        ORDER BY creation DESC
    """, params, as_dict=True)

    return columns, data