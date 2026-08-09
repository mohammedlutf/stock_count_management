import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": _("Time Period"), "fieldname": "period", "fieldtype": "Data", "width": 120},
        {"label": _("Total Sessions"), "fieldname": "total_sessions", "fieldtype": "Int", "width": 110},
        {"label": _("Total Items Audited"), "fieldname": "total_items", "fieldtype": "Int", "width": 130},
        {"label": _("Accurate Items"), "fieldname": "accurate_items", "fieldtype": "Int", "width": 120},
        {"label": _("Variance Items"), "fieldname": "variance_items", "fieldtype": "Int", "width": 120},
        {"label": _("IRA Accuracy %"), "fieldname": "ira_percent", "fieldtype": "Percent", "width": 130},
    ]

    group_by_format = "%%Y-%%m" if filters.get("frequency") == "Monthly" else "%%Y"

    conditions = []
    if filters.get("warehouse"):
        conditions.append("scs.warehouse = %(warehouse)s")
    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("DATE(scs.creation) BETWEEN %(from_date)s AND %(to_date)s")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    query = f"""
        SELECT
            DATE_FORMAT(scs.creation, '{group_by_format}') AS period,
            COUNT(DISTINCT scs.name) AS total_sessions,
            COUNT(ce.name) AS total_items,
            SUM(CASE WHEN ce.qty_in_stock_uom = ce.current_erp_qty THEN 1 ELSE 0 END) AS accurate_items,
            SUM(CASE WHEN ce.qty_in_stock_uom != ce.current_erp_qty THEN 1 ELSE 0 END) AS variance_items
        FROM `tabStock Count Session` scs
        INNER JOIN `tabCount Entry` ce ON ce.session = scs.name
        {where_clause}
        GROUP BY DATE_FORMAT(scs.creation, '{group_by_format}')
        ORDER BY period ASC
    """

    raw_data = frappe.db.sql(query, filters, as_dict=True)

    data = []
    periods = []
    ira_values = []

    for r in raw_data:
        total = flt(r.total_items)
        accurate = flt(r.accurate_items)
        ira_percent = (accurate / total * 100.0) if total else 0.0

        r["ira_percent"] = ira_percent
        data.append(r)

        periods.append(r["period"])
        ira_values.append(round(ira_percent, 2))

    chart = {
        "data": {
            "labels": periods,
            "datasets": [{"name": _("IRA Accuracy %"), "values": ira_values}],
        },
        "type": "line",
        "colors": ["#28a745"],
    }

    return columns, data, None, chart