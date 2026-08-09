import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters or not filters.get("stock_reconciliation"):
        return [], []

    columns = [
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 130},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 160},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 130},
        {"fieldname": "batch_no", "label": _("Batch No"), "fieldtype": "Link", "options": "Batch", "width": 110},
        {"fieldname": "stock_uom", "label": _("Stock UOM"), "fieldtype": "Link", "options": "UOM", "width": 90},
        
        # Quantities
        {"fieldname": "current_qty", "label": _("ERP Qty"), "fieldtype": "Float", "width": 90},
        {"fieldname": "qty", "label": _("Counted Qty"), "fieldtype": "Float", "width": 95},
        {"fieldname": "difference_quantity", "label": _("Variance Qty"), "fieldtype": "Float", "width": 95},
        
        # Human-Readable Packaging Breakdown
        {"fieldname": "formatted_counted_uom", "label": _("Counted Breakdown"), "fieldtype": "Data", "width": 200},
        {"fieldname": "formatted_variance_uom", "label": _("Variance Breakdown"), "fieldtype": "Data", "width": 200},
        
        # Valuation & Values
        {"fieldname": "valuation_rate", "label": _("Valuation Rate"), "fieldtype": "Currency", "width": 110},
        {"fieldname": "current_amount", "label": _("ERP Value"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "amount", "label": _("Counted Value"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "amount_difference", "label": _("Variance Value"), "fieldtype": "Currency", "width": 120}
    ]

    conditions = ["item.parent = %(stock_reconciliation)s"]
    params = {"stock_reconciliation": filters.get("stock_reconciliation")}

    if filters.get("variance_only"):
        conditions.append("(item.qty - item.current_qty) != 0")

    data = frappe.db.sql(f"""
        SELECT 
            item.item_code,
            item.item_name,
            item.warehouse,
            item.batch_no,
            item.stock_uom,
            item.current_qty,
            item.qty,
            (item.qty - item.current_qty) as difference_quantity,
            IFNULL(item.valuation_rate, 0.0) as valuation_rate,
            item.current_amount,
            item.amount,
            item.amount_difference
        FROM `tabStock Reconciliation Item` item
        INNER JOIN `tabStock Reconciliation` rec ON rec.name = item.parent
        WHERE {" AND ".join(conditions)}
        ORDER BY ABS(item.qty - item.current_qty) DESC
    """, params, as_dict=True)

    # Pre-fetch and cache UOM conversion tables for items in this report
    item_uom_map = get_item_uoms_map([d.item_code for d in data])

    # Format human-readable packaging breakdown for each row
    for row in data:
        uoms = item_uom_map.get(row.item_code, [])
        row["formatted_counted_uom"] = format_quantity_breakdown(row.qty, row.stock_uom, uoms)
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