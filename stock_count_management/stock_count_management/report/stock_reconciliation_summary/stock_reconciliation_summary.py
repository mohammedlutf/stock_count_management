import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {"fieldname": "name", "label": _("Reconciliation No"), "fieldtype": "Link", "options": "Stock Reconciliation", "width": 160},
        {"fieldname": "posting_datetime", "label": _("Date / Time"), "fieldtype": "Datetime", "width": 140},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
        {"fieldname": "owner", "label": _("Created By"), "fieldtype": "Link", "options": "User", "width": 130},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
        
        # Item Counts
        {"fieldname": "total_items", "label": _("Total Items"), "fieldtype": "Int", "width": 90},
        {"fieldname": "counted_items", "label": _("Counted Items"), "fieldtype": "Int", "width": 100},
        {"fieldname": "uncounted_items", "label": _("Uncounted Items"), "fieldtype": "Int", "width": 110},
        
        # Quantity & Financial Variance
        {"fieldname": "qty_difference", "label": _("Quantity Difference"), "fieldtype": "Float", "width": 120},
        {"fieldname": "positive_adjustment", "label": _("Positive Adjustment"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "negative_adjustment", "label": _("Negative Adjustment"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "total_adjustment_value", "label": _("Total Adjustment Value"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "variance_percent", "label": _("Variance %"), "fieldtype": "Percent", "width": 90},
        
        {"fieldname": "docstatus_label", "label": _("Approval Status"), "fieldtype": "Data", "width": 110}
    ]

def get_data(filters):
    conditions = []
    params = {}

    if filters.get("from_date"):
        conditions.append("sr.posting_date >= %(from_date)s")
        params["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions.append("sr.posting_date <= %(to_date)s")
        params["to_date"] = filters.get("to_date")

    if filters.get("company"):
        conditions.append("sr.company = %(company)s")
        params["company"] = filters.get("company")

    if filters.get("warehouse"):
        conditions.append("sr.warehouse = %(warehouse)s")
        params["warehouse"] = filters.get("warehouse")

    if filters.get("docstatus") is not None and filters.get("docstatus") != "":
        conditions.append("sr.docstatus = %(docstatus)s")
        params["docstatus"] = filters.get("docstatus")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT 
            sr.name,
            TIMESTAMP(sr.posting_date, sr.posting_time) AS posting_datetime,
            sri.warehouse,
            sr.owner,
            CASE 
                WHEN sr.docstatus = 0 THEN 'Draft'
                WHEN sr.docstatus = 1 THEN 'Submitted'
                WHEN sr.docstatus = 2 THEN 'Cancelled'
            END AS status,
            
            -- Item Counts
            COUNT(sri.name) AS total_items,
            SUM(CASE WHEN sri.qty IS NOT NULL AND sri.qty > 0 THEN 1 ELSE 0 END) AS counted_items,
            SUM(CASE WHEN sri.qty IS NULL OR sri.qty = 0 THEN 1 ELSE 0 END) AS uncounted_items,
            
            -- Qty Difference
            SUM(sri.qty - sri.current_qty) AS qty_difference,
            
            -- Positive, Negative, and Net Valuation Values
            SUM(CASE WHEN sri.amount_difference > 0 THEN sri.amount_difference ELSE 0 END) AS positive_adjustment,
            SUM(CASE WHEN sri.amount_difference < 0 THEN ABS(sri.amount_difference) ELSE 0 END) AS negative_adjustment,
            SUM(sri.amount_difference) AS total_adjustment_value,
            
            -- Total System Value before adjustment for variance percentage
            SUM(sri.current_amount) AS total_erp_value,
            
            CASE 
                WHEN sr.docstatus = 0 THEN 'Pending Approval'
                WHEN sr.docstatus = 1 THEN 'Approved'
                WHEN sr.docstatus = 2 THEN 'Rejected'
            END AS docstatus_label
            
        FROM `tabStock Reconciliation` sr
        INNER JOIN `tabStock Reconciliation Item` sri ON sri.parent = sr.name
        {where_clause}
        GROUP BY sr.name
        ORDER BY sr.posting_date DESC, sr.posting_time DESC
    """

    raw_data = frappe.db.sql(query, params, as_dict=True)

    for row in raw_data:
        total_erp = flt(row.get("total_erp_value"))
        total_adj = flt(row.get("total_adjustment_value"))

        # Calculate Variance %
        if total_erp != 0:
            row["variance_percent"] = (total_adj / total_erp) * 100
        else:
            row["variance_percent"] = 100.0 if total_adj != 0 else 0.0

    return raw_data