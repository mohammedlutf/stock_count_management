import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters or not filters.get("stock_reconciliation"):
        return [], []

    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item", "width": 140},
        {"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data", "width": 180},
        {"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group", "width": 130},
        {"fieldname": "warehouse", "label": _("Warehouse"), "fieldtype": "Link", "options": "Warehouse", "width": 140},
        {"fieldname": "stock_uom", "label": _("Stock UOM"), "fieldtype": "Link", "options": "UOM", "width": 100},
        {"fieldname": "system_qty", "label": _("System Stock Qty"), "fieldtype": "Float", "width": 120},
        {"fieldname": "valuation_rate", "label": _("Valuation Rate"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "uncounted_stock_value", "label": _("Uncounted Stock Value"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120}
    ]

def get_data(filters):
    # Fetch details from target Stock Reconciliation
    sr_doc = frappe.get_doc("Stock Reconciliation", filters.get("stock_reconciliation"))
    
    # Resolve Warehouse: Filter value > Header Warehouse > Default Warehouse
    target_warehouse = filters.get("warehouse") or sr_doc.warehouse or get_default_warehouse(sr_doc.company)

    if not target_warehouse:
        frappe.throw(_("Warehouse could not be determined. Please specify a Warehouse filter or configure a default Warehouse in Stock Settings."))

    params = {
        "stock_reconciliation": filters.get("stock_reconciliation"),
        "warehouse": target_warehouse,
        "company": sr_doc.company
    }

    # Additional Dynamic Conditions
    additional_conditions = []

    # Filter: Item Group
    if filters.get("item_group"):
        additional_conditions.append("item.item_group = %(item_group)s")
        params["item_group"] = filters.get("item_group")

    # Filter: Exclude Zero Stock Items
    if filters.get("ignore_zero_stock"):
        additional_conditions.append("IFNULL(bin.actual_qty, 0.0) != 0")

    where_extra = ("AND " + " AND ".join(additional_conditions)) if additional_conditions else ""

    query = f"""
        SELECT 
            item.name AS item_code,
            item.item_name,
            item.item_group,
            %(warehouse)s AS warehouse,
            item.stock_uom,
            IFNULL(bin.actual_qty, 0.0) AS system_qty,
            IFNULL(bin.valuation_rate, item.valuation_rate) AS valuation_rate,
            (IFNULL(bin.actual_qty, 0.0) * IFNULL(bin.valuation_rate, item.valuation_rate)) AS uncounted_stock_value,
            'Uncounted' AS status
        FROM `tabItem` item
        LEFT JOIN `tabBin` bin 
            ON bin.item_code = item.name 
           AND bin.warehouse = %(warehouse)s
        WHERE item.disabled = 0 
          AND item.is_stock_item = 1
          {where_extra}
          -- Exclude items already present in the Stock Reconciliation child table
          AND item.name NOT IN (
              SELECT DISTINCT sri.item_code 
              FROM `tabStock Reconciliation Item` sri
              WHERE sri.parent = %(stock_reconciliation)s
                AND (sri.warehouse = %(warehouse)s OR sri.warehouse IS NULL OR sri.warehouse = '')
          )
        ORDER BY bin.actual_qty DESC, item.name ASC
    """

    return frappe.db.sql(query, params, as_dict=True)

def get_default_warehouse(company):
    """ Falls back to Company Default Warehouse or Stock Settings Default Warehouse """
    default_wh = frappe.db.get_value("Company", company, "default_warehouse") if company else None
    if not default_wh:
        default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    return default_wh