import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    columns = [
        {"label": _("Session"), "fieldname": "session", "fieldtype": "Link", "options": "Stock Count Session", "width": 140},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 130},
        {"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
        {"label": _("System Qty"), "fieldname": "current_erp_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Physical Qty"), "fieldname": "qty_in_stock_uom", "fieldtype": "Float", "width": 100},
        {"label": _("Variance Qty"), "fieldname": "difference_quantity", "fieldtype": "Float", "width": 100},
        {"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 110},
        {"label": _("System Value"), "fieldname": "system_value", "fieldtype": "Currency", "width": 120},
        {"label": _("Physical Value"), "fieldname": "physical_value", "fieldtype": "Currency", "width": 120},
        {"label": _("Valuation Impact"), "fieldname": "valuation_impact", "fieldtype": "Currency", "width": 130},
    ]

    conditions = []
    if filters.get("session"):
        conditions.append("ce.session = %(session)s")
    if filters.get("warehouse"):
        conditions.append("ce.warehouse = %(warehouse)s")
    if filters.get("only_variances"):
        conditions.append("ce.qty_in_stock_uom != ce.current_erp_qty")

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    query = f"""
        SELECT
            ce.session,
            ce.warehouse,
            ce.item_code,
            ce.item_name,
            ce.stock_uom,
            ce.current_erp_qty,
            ce.qty_in_stock_uom,
            ce.difference_quantity,
            COALESCE(bin.valuation_rate, item.valuation_rate, 0.0) AS valuation_rate,
            (ce.current_erp_qty * COALESCE(bin.valuation_rate, item.valuation_rate, 0.0)) AS system_value,
            (ce.qty_in_stock_uom * COALESCE(bin.valuation_rate, item.valuation_rate, 0.0)) AS physical_value,
            (ce.difference_quantity * COALESCE(bin.valuation_rate, item.valuation_rate, 0.0)) AS valuation_impact
        FROM `tabCount Entry` ce
        LEFT JOIN `tabItem` item ON item.name = ce.item_code
        LEFT JOIN `tabBin` bin ON bin.item_code = ce.item_code AND bin.warehouse = ce.warehouse
        {where_clause}
        ORDER BY ABS(ce.difference_quantity * COALESCE(bin.valuation_rate, item.valuation_rate, 0.0)) DESC
    """

    data = frappe.db.sql(query, filters, as_dict=True)

    # Compute Summary Dashboard Widgets
    total_surplus = sum([flt(d.valuation_impact) for d in data if flt(d.valuation_impact) > 0])
    total_shortage = sum([flt(d.valuation_impact) for d in data if flt(d.valuation_impact) < 0])
    net_impact = total_surplus + total_shortage

    summary = [
        {"label": _("Total Surplus Value"), "value": total_surplus, "indicator": "Green"},
        {"label": _("Total Shortage Value"), "value": abs(total_shortage), "indicator": "Red"},
        {"label": _("Net Financial Adjustment"), "value": net_impact, "indicator": "Blue" if net_impact >= 0 else "Red"},
    ]

    return columns, data, None, None, summary