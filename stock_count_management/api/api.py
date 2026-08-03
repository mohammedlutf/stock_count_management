import frappe
from frappe import _
from frappe.utils import flt

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
def submit_count_payload(session, warehouse, item_code, selected_uom, conversion_factor, counted_quantity, batch_no=None, serial_no=None):
    item = frappe.get_doc("Item", item_code)

    # Process Serial Numbers
    serials_list = []
    if item.has_serial_no and serial_no:
        serials_list = [s.strip() for s in serial_no.replace('\n', ',').split(',') if s.strip()]
        counted_quantity = len(serials_list)

    added_qty_in_stock_uom = flt(counted_quantity) * flt(conversion_factor)
    entry_name = frappe.db.get_value("Count Entry", {"session": session, "item_code": item_code, "warehouse": warehouse})

    # Clear batch input if item does NOT have batch tracking
    clean_batch_no = batch_no if item.has_batch_no else None

    if entry_name:
        entry = frappe.get_doc("Count Entry", entry_name)
        entry.qty_in_stock_uom = flt(entry.qty_in_stock_uom) + added_qty_in_stock_uom
        
        if serials_list:
            existing_serials = [s.strip() for s in (entry.serial_no or "").split('\n') if s.strip()]
            combined_serials = list(set(existing_serials + serials_list))
            entry.serial_no = "\n".join(combined_serials)
            entry.qty_in_stock_uom = len(combined_serials)
            
        if clean_batch_no:
            entry.batch_no = clean_batch_no
    else:
        entry = frappe.new_doc("Count Entry")
        entry.session = session
        entry.warehouse = warehouse
        entry.item_code = item_code
        entry.item_name = item.item_name
        entry.stock_uom = item.stock_uom
        entry.current_erp_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0.0
        entry.qty_in_stock_uom = added_qty_in_stock_uom
        entry.batch_no = clean_batch_no
        if serials_list:
            entry.serial_no = "\n".join(serials_list)

    entry.counter = frappe.session.user
    entry.status = "Counted"  # Crucial for filtering during Reconciliation
    entry.save(ignore_permissions=True)

    # Recalculate session progress stats
    session_doc = frappe.get_doc("Stock Count Session", session)
    session_doc.recalculate_statistics()

    return {
        "status": "success",
        "new_total_stock_qty": entry.qty_in_stock_uom,
        "stock_uom": entry.stock_uom
    }