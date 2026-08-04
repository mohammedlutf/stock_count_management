import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters.get("session"):
        return [], []

    columns = [
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 130},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 160},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 130},
        {"fieldname": "batch_no", "label": _("Batch No"), "fieldtype": "Link", "options": "Batch", "width": 110},
        {"fieldname": "stock_uom", "label": _("Stock UOM"), "fieldtype": "Link", "options": "UOM", "width": 90},
        
        # Quantities
        {"fieldname": "current_erp_qty", "label": _("ERP Qty"), "fieldtype": "Float", "width": 90},
        {"fieldname": "qty_in_stock_uom", "label": _("Counted Qty"), "fieldtype": "Float", "width": 95},
        {"fieldname": "difference_quantity", "label": _("Variance Qty"), "fieldtype": "Float", "width": 95},
        
        # Human-Readable Packaging Breakdown
        {"fieldname": "formatted_counted_uom", "label": _("Counted Breakdown"), "fieldtype": "Data", "width": 200},
        {"fieldname": "formatted_variance_uom", "label": _("Variance Breakdown"), "fieldtype": "Data", "width": 200},
        
        # Valuation & Values
        {"fieldname": "valuation_rate", "label": _("Valuation Rate"), "fieldtype": "Currency", "width": 110},
        {"fieldname": "erp_value", "label": _("ERP Value"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "counted_value", "label": _("Counted Value"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "variance_value", "label": _("Variance Value"), "fieldtype": "Currency", "width": 120},
        
        {"fieldname": "counter", "label": _("Counter User"), "fieldtype": "Link", "options": "User", "width": 130}
    ]

    conditions = ["entry.session = %(session)s", "entry.status IN ('Counted', 'Verified')"]
    params = {"session": filters.get("session")}

    if filters.get("variance_only"):
        conditions.append("entry.difference_quantity != 0")

    data = frappe.db.sql(f"""
        SELECT 
            entry.item_code,
            entry.item_name,
            entry.warehouse,
            entry.batch_no,
            entry.stock_uom,
            entry.current_erp_qty,
            entry.qty_in_stock_uom,
            entry.difference_quantity,
            IFNULL(item_val.valuation_rate, 0.0) as valuation_rate,
            (entry.current_erp_qty * IFNULL(item_val.valuation_rate, 0.0)) as erp_value,
            (entry.qty_in_stock_uom * IFNULL(item_val.valuation_rate, 0.0)) as counted_value,
            (entry.difference_quantity * IFNULL(item_val.valuation_rate, 0.0)) as variance_value,
            entry.counter
        FROM `tabCount Entry` entry
        LEFT JOIN `tabBin` item_val 
            ON entry.item_code = item_val.item_code 
           AND entry.warehouse = item_val.warehouse
        WHERE {" AND ".join(conditions)}
        ORDER BY ABS(entry.difference_quantity) DESC
    """, params, as_dict=True)

    # Pre-fetch and cache UOM conversion tables for items in this report
    item_uom_map = get_item_uoms_map([d.item_code for d in data])

    # Format human-readable packaging breakdown for each row
    for row in data:
        uoms = item_uom_map.get(row.item_code, [])
        row["formatted_counted_uom"] = format_quantity_breakdown(row.qty_in_stock_uom, row.stock_uom, uoms)
        row["formatted_variance_uom"] = format_quantity_breakdown(row.difference_quantity, row.stock_uom, uoms)

    return columns, data


def get_item_uoms_map(item_codes):
    """ Builds sorted UOM conversion mapping for items (largest conversion first) """
    if not item_codes:
        return {}

    uom_rows = frappe.db.sql("""
        SELECT parent as item_code, uom, conversion_factor
        FROM `tabUOM Conversion Detail`
        WHERE parent IN %s AND conversion_factor > 1.0
        ORDER BY conversion_factor DESC
    """, (tuple(set(item_codes)),), as_dict=True)

    uom_map = {}
    for r in uom_rows:
        if r.item_code not in uom_map:
            uom_map[r.item_code] = []
        uom_map[r.item_code].append(r)

    return uom_map


def format_quantity_breakdown(raw_qty, stock_uom, uom_conversions):
    """
    Converts stock qty into hierarchy breakdown.
    Example: 120 Nos (where Bag=24 Nos, Carton=96 Nos) -> '1 Carton, 1 Bag, 0 Nos'
    """
    if not raw_qty:
        return f"0 {stock_uom}"

    is_negative = raw_qty < 0
    remaining_qty = abs(flt(raw_qty))
    
    parts = []

    # Iterate through larger UOMs (Carton, Bag, etc.)
    for uom_info in uom_conversions:
        factor = flt(uom_info.conversion_factor)
        if factor > 1.0 and remaining_qty >= factor:
            uom_count = int(remaining_qty // factor)
            remaining_qty = remaining_qty % factor
            parts.append(f"{uom_count} {uom_info.uom}")

    # Remaining base unit quantity (e.g., Nos)
    base_qty = int(remaining_qty) if remaining_qty.is_integer() else round(remaining_qty, 2)
    parts.append(f"{base_qty} {stock_uom}")

    formatted_str = ", ".join(parts)
    return f"-({formatted_str})" if is_negative else formatted_str