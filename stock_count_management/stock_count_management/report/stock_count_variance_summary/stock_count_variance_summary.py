import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    chart = get_chart(data)
    summary = get_summary(data)

    return columns, data, None, chart, summary


def get_columns():
    return [
        {"label": _("Session"), "fieldname": "session", "fieldtype": "Link", "options": "Stock Count Session", "width": 140},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Batch No"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 110},
        {"label": _("ERP Qty"), "fieldname": "erp_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Physical Qty"), "fieldname": "physical_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Variance Qty"), "fieldname": "variance_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 110},
        {"label": _("Valuation Impact"), "fieldname": "valuation_impact", "fieldtype": "Currency", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
    ]


def get_data(filters):
    conditions = []
    if filters.get("session"):
        conditions.append("ce.session = %(session)s")
    if filters.get("warehouse"):
        conditions.append("ce.warehouse = %(warehouse)s")
    if filters.get("only_variances"):
        conditions.append("ce.qty_in_stock_uom != ce.current_erp_qty")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "AND " + where_clause

    query = f"""
        SELECT
            ce.session,
            ce.warehouse,
            ce.item_code,
            ce.item_name,
            csl.batch_no,
            ce.current_erp_qty AS erp_qty,
            COALESCE(csl.scanned_qty, ce.qty_in_stock_uom) AS physical_qty,
            (COALESCE(csl.scanned_qty, ce.qty_in_stock_uom) - ce.current_erp_qty) AS variance_qty,
            COALESCE(bin.valuation_rate, item.valuation_rate, 0.0) AS valuation_rate,
            ((COALESCE(csl.scanned_qty, ce.qty_in_stock_uom) - ce.current_erp_qty) * COALESCE(bin.valuation_rate, item.valuation_rate, 0.0)) AS valuation_impact,
            ce.status
        FROM `tabCount Entry` ce
        LEFT JOIN `tabItem` item ON item.name = ce.item_code
        LEFT JOIN `tabBin` bin ON bin.item_code = ce.item_code AND bin.warehouse = ce.warehouse
        LEFT JOIN (
            SELECT parent, batch_no, SUM(qty) AS scanned_qty
            FROM `tabCount Scan Log`
            GROUP BY parent, batch_no
        ) csl ON csl.parent = ce.name
        WHERE 1=1 {where_clause}
        ORDER BY ce.session DESC, ABS(COALESCE(csl.scanned_qty, ce.qty_in_stock_uom) - ce.current_erp_qty) DESC
    """
    return frappe.db.sql(query, filters, as_dict=True)


def get_summary(data):
    if not data:
        return []

    total_surplus = sum([flt(d.valuation_impact) for d in data if flt(d.valuation_impact) > 0])
    total_shortage = sum([flt(d.valuation_impact) for d in data if flt(d.valuation_impact) < 0])
    net_impact = total_surplus + total_shortage

    return [
        {"label": _("Total Surplus"), "value": total_surplus, "indicator": "Green"},
        {"label": _("Total Shortage"), "value": abs(total_shortage), "indicator": "Red"},
        {"label": _("Net Valuation Impact"), "value": net_impact, "indicator": "Blue" if net_impact >= 0 else "Red"},
    ]


def get_chart(data):
    if not data:
        return None

    surplus_count = sum(1 for d in data if flt(d.variance_qty) > 0)
    shortage_count = sum(1 for d in data if flt(d.variance_qty) < 0)
    matched_count = sum(1 for d in data if flt(d.variance_qty) == 0)

    return {
        "data": {
            "labels": [_("Matched"), _("Surplus"), _("Shortage")],
            "datasets": [{"values": [matched_count, surplus_count, shortage_count]}],
        },
        "type": "donut",
        "colors": ["#28a745", "#ffc107", "#dc3545"],
    }