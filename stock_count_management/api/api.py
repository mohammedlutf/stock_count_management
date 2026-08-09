import frappe
from frappe import _
from frappe.utils import flt,getdate, today

@frappe.whitelist()
def get_active_sessions():
    """ Returns all 'In Progress' Stock Count Sessions for the mobile dropdown """
    return frappe.get_all(
        "Stock Count Session",
        filters={"status": "In Progress"},
        fields=["name", "session_name", "warehouse"]
    )

@frappe.whitelist()
def scan_and_fetch_item(search_query, warehouse, session):
    session_doc = frappe.get_doc("Stock Count Session", session)
    
    item_code = None
    scanned_uom = None

    # 1. Check Barcode mapping
    barcode_doc = frappe.db.get_value("Item Barcode", {"barcode": search_query}, ["parent", "uom"], as_dict=True)
    if barcode_doc:
        item_code = barcode_doc.parent
        scanned_uom = barcode_doc.uom

    # 2. Check Item Code directly
    if not item_code and frappe.db.exists("Item", search_query):
        item_code = search_query

    # 3. Check Item Name
    if not item_code:
        item_code = frappe.db.get_value("Item", {"item_name": ["like", f"%{search_query}%"]}, "name")

    if not item_code:
        frappe.throw(_("No item found matching: {0}").format(search_query))

    item = frappe.get_doc("Item", item_code)

    # Map UOMs
    uom_list = [{"uom": item.stock_uom, "conversion_factor": 1.0}]
    for u_row in item.uoms:
        if u_row.uom != item.stock_uom:
            uom_list.append({"uom": u_row.uom, "conversion_factor": u_row.conversion_factor})

    auto_uom = scanned_uom if scanned_uom else item.stock_uom

    # Fetch existing count entry details
    entry_name = frappe.db.get_value("Count Entry", {"session": session, "item_code": item_code, "warehouse": warehouse})
    
    existing_qty = 0.0
    existing_serials = ""
    existing_batch = ""
    
    if entry_name:
        entry_doc = frappe.get_doc("Count Entry", entry_name)
        existing_qty = entry_doc.qty_in_stock_uom or 0.0
        existing_serials = entry_doc.serial_no or ""
        # STRICT CHECK: Only assign batch if item actually has batch tracking
        if item.has_batch_no:
            existing_batch = entry_doc.batch_no or ""

    erp_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0.0

    # Fetch batches ONLY if item is batch-tracked
    available_batches = []
    if item.has_batch_no:
        available_batches = frappe.get_all("Batch", filters={"item": item_code, "disabled": 0}, pluck="name")

    return {
        "entry_name": entry_name,
        "item_code": item.name,
        "item_name": item.item_name,
        "stock_uom": item.stock_uom,
        "auto_selected_uom": auto_uom,
        "available_uoms": uom_list,
        "has_batch": item.has_batch_no,
        "has_serial": item.has_serial_no,
        "available_batches": available_batches,
        "existing_batch": existing_batch,
        "existing_serials": existing_serials,
        "accumulated_stock_qty": existing_qty,
        "current_erp_qty": None if session_doc.count_type == "Blind Count" else erp_qty
    }


@frappe.whitelist()
def submit_count_payload(session, warehouse, item_code, selected_uom, conversion_factor=1.0, counted_quantity=0, batch_no=None, serial_no=None):
    """ Routes mobile scan payloads directly through record_counter_scan on Stock Count Session """
    if not session or not item_code:
        frappe.throw(_("Session ID and Item Code are required."))

    # Load session document
    session_doc = frappe.get_doc("Stock Count Session", session)

    # Route scan payload to session instance method
    res = session_doc.record_counter_scan(
        item_code=item_code,
        qty=flt(counted_quantity),
        conversion_factor=flt(conversion_factor or 1.0),
        batch_no=batch_no,
        serial_no=serial_no
    )

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")

    return {
        "status": "success",
        "new_total_stock_qty": res.get("total_qty"),
        "stock_uom": stock_uom
    }

@frappe.whitelist()
def search_items(query, warehouse=None):
    """
    Wildcard substring search matching item_code, item_name, or barcode 
    anywhere in the text (%query%). Returns item details and UOM conversions.
    """
    if not query or len(query.strip()) < 2:
        return []

    search_term = f"%{query.strip()}%"

    sql_query = """
        SELECT DISTINCT
            item.name AS item_code,
            item.item_name,
            item.stock_uom,
            item.has_batch_no,
            item.has_serial_no,
            bc.barcode
        FROM `tabItem` item
        LEFT JOIN `tabItem Barcode` bc ON bc.parent = item.name
        WHERE item.disabled = 0
          AND (
              item.name LIKE %s 
              OR item.item_name LIKE %s 
              OR bc.barcode LIKE %s
          )
        ORDER BY 
            CASE 
                WHEN item.name LIKE %s THEN 1
                WHEN item.item_name LIKE %s THEN 2
                ELSE 3
            END
        LIMIT 15
    """

    exact_start = f"{query.strip()}%"
    results = frappe.db.sql(
        sql_query, 
        (search_term, search_term, search_term, exact_start, exact_start), 
        as_dict=True
    )

    # Attach UOM conversion factors for each matching item
    for item in results:
        uoms = frappe.db.get_all(
            "UOM Conversion Detail",
            filters={"parent": item.item_code},
            fields=["uom", "conversion_factor"]
        )
        
        # Ensure base stock_uom is present in list with factor 1.0
        uom_list = [{"uom": item.stock_uom, "conversion_factor": 1.0}]
        for u in uoms:
            if u.uom != item.stock_uom:
                uom_list.append({"uom": u.uom, "conversion_factor": flt(u.conversion_factor)})

        item["uoms"] = uom_list

    return results


@frappe.whitelist()
def validate_batch_expiry(batch_no, item_code=None):
    """
    Checks if a scanned batch number is expired and returns its details.
    """
    if not batch_no:
        return {"is_expired": False}

    batch = frappe.db.get_value(
        "Batch", 
        batch_no, 
        ["name", "expiry_date", "disabled"], 
        as_dict=True
    )

    if not batch:
        return {"exists": False, "is_expired": False, "message": _("Batch number does not exist.")}

    is_expired = False
    if batch.expiry_date and getdate(batch.expiry_date) < getdate(today()):
         is_expired = True

    return {
        "exists": True,
        "is_expired": is_expired,
        "expiry_date": str(batch.expiry_date) if batch.expiry_date else None,
        "disabled": batch.disabled,
        "message": _("Warning: Batch {0} expired on {1}!").format(batch_no, batch.expiry_date) if is_expired else _("Batch Valid")
    }    