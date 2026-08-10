import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, get_link_to_form

class StockCountSession(Document):

    @frappe.whitelist()
    def generate_tasks(self, get_all_items=0):
        """ Pulls active stock balances for the warehouse and creates Count Entries """
        if self.status != "Draft":
            frappe.throw(_("Tasks can only be generated when Session is in Draft status."))

        # Clear previous pending entries if regenerating tasks
        frappe.db.delete("Count Entry", {"session": self.name})

        entries_to_insert = []

        if frappe.parse_json(get_all_items):
            bitems = frappe.db.sql("""
                SELECT
                    i.item_code,
                    i.item_name,
                    i.stock_uom,
                    COALESCE(b.actual_qty, 0) AS actual_qty
                FROM `tabItem` i
                LEFT JOIN `tabBin` b
                    ON b.item_code = i.item_code
                    AND b.warehouse = %(warehouse)s
                WHERE i.is_stock_item = 1
                ORDER BY i.item_code
            """, {
                "warehouse": self.warehouse
            }, as_dict=True)

            if not bitems:
                frappe.throw(_("No inventory records found for warehouse {0}").format(self.warehouse))
            for b in bitems:
                entries_to_insert.append((
                    frappe.generate_hash(length=10),
                    self.name,
                    b.item_code,
                    b.item_name,
                    self.warehouse,
                    b.item_uom,
                    b.actual_qty,
                    0.0,
                    (0.0 - flt(b.actual_qty)),
                    "Pending",
                    frappe.session.user,
                    now_datetime(),
                    now_datetime(),
                    frappe.session.user
                ))
        
        else:
            # Fetch active Bins for the warehouse
            bins = frappe.db.get_all(
                "Bin",
                filters={"warehouse": self.warehouse},
                fields=["item_code", "actual_qty"]
            )

            if not bins:
                frappe.throw(_("No inventory records found for warehouse {0}").format(self.warehouse))
            for b in bins:
                item_uom = frappe.db.get_value("Item", b.item_code, "stock_uom")
                item_name = frappe.db.get_value("Item", b.item_code, "item_name")
        
                entries_to_insert.append((
                    frappe.generate_hash(length=10),
                    self.name,
                    b.item_code,
                    item_name,
                    self.warehouse,
                    item_uom,
                    b.actual_qty,
                    0.0,
                    (0.0 - flt(b.actual_qty)),
                    "Pending",
                    frappe.session.user,
                    now_datetime(),
                    now_datetime(),
                    frappe.session.user
                ))

        frappe.db.bulk_insert(
            "Count Entry",
            fields=[
                "name", "session", "item_code", "item_name", "warehouse", 
                "stock_uom", "current_erp_qty", "qty_in_stock_uom", "difference_quantity", 
                "status", "owner", "creation", "modified", "modified_by"
            ],
            values=entries_to_insert
        )

        self.db_set("status", "In Progress")
        self.recalculate_statistics()
        frappe.msgprint(_("Generated {0} tasks successfully.").format(len(entries_to_insert)))

    @frappe.whitelist()
    def recalculate_statistics(self):
        """ Updates execution progress metrics cleanly via single SQL count """
        total = frappe.db.count("Count Entry", {"session": self.name})
        counted = frappe.db.count("Count Entry", {"session": self.name, "status": ["in", ["Counted", "Verified"]]})
        uncounted = total - counted

        self.db_set("total_items", total)
        self.db_set("counted_items", counted)
        self.db_set("uncounted_items", uncounted)
        self.db_set("completion_percent", (counted / total * 100.0) if total else 0.0)

    @frappe.whitelist()
    def get_uncounted_items(self):
        """ Returns list of items not yet scanned by counters """
        return frappe.db.get_all(
            "Count Entry",
            filters={"session": self.name, "status": "Pending"},
            fields=["item_code", "item_name", "current_erp_qty"]
        )

    @frappe.whitelist()
    def zero_out_uncounted_and_reconcile(self, zero_out_uncounted=0):
        """ Native ERPNext Stock Reconciliation Generator - Individual Batch Rows Mode """
        zero_out = frappe.parse_json(zero_out_uncounted)

        # 1. Bulk update uncounted entries directly in SQL ONLY if zero_out is checked
        if zero_out:
            frappe.db.sql("""
                UPDATE `tabCount Entry`
                SET qty_in_stock_uom = 0.0,
                    difference_quantity = 0.0 - current_erp_qty,
                    status = 'Counted'
                WHERE session = %s AND status = 'Pending'
            """, (self.name,))

        self.recalculate_statistics()

        # 2. Fetch Counted/Verified lines (if zero_out=0, Pending entries remain Pending and are ignored)
        entries = frappe.get_all(
            "Count Entry",
            filters={"session": self.name, "status": ["in", ["Counted", "Verified"]]},
            fields=["name", "item_code", "warehouse", "current_erp_qty", "qty_in_stock_uom", "batch_no", "serial_no"]
        )

        current_dt = now_datetime()
        posting_date = current_dt.strftime("%Y-%m-%d")
        posting_time = current_dt.strftime("%H:%M:%S")

        items_payload = []

        # 3. Expand items per batch into individual payload rows
        for entry in entries:
            entry_doc = frappe.get_doc("Count Entry", entry.name)
            item_doc = frappe.get_cached_doc("Item", entry.item_code)
            has_batch = item_doc.has_batch_no
            has_serial = item_doc.has_serial_no

            valuation_rate = frappe.db.get_value("Bin", {"item_code": entry.item_code, "warehouse": entry.warehouse}, "valuation_rate") or item_doc.valuation_rate or 1.0

            if has_batch:
                # Aggregate scanned quantities per batch from scan logs
                scanned_batch_map = {}
                for log in entry_doc.scan_logs:
                    if log.batch_no:
                        scanned_batch_map[log.batch_no] = scanned_batch_map.get(log.batch_no, 0.0) + flt(log.qty)

                if not scanned_batch_map and entry.batch_no:
                    scanned_batch_map[entry.batch_no] = flt(entry.qty_in_stock_uom)

                # Determine which batches to process
                if zero_out:
                    # Include scanned batches PLUS all active system batches (to zero them out)
                    all_system_batches = frappe.get_all(
                        "Batch",
                        filters={"item": entry.item_code, "disabled": 0,"batch_qty" : ['>', '0']},
                        pluck="name"
                    )
                    batches_to_process = set(scanned_batch_map.keys()).union(set(all_system_batches))
                else:
                    # STRICT: Only process batches that were actually scanned or recorded on entry
                    batches_to_process = set(scanned_batch_map.keys())

                for b_name in batches_to_process:
                    batch_target_qty = scanned_batch_map.get(b_name, 0.0)

                    # Ensure batch exists in tabBatch
                    if not frappe.db.exists("Batch", b_name):
                        b_doc = frappe.new_doc("Batch")
                        b_doc.batch_id = b_name
                        b_doc.item = entry.item_code
                        b_doc.save(ignore_permissions=True)

                    items_payload.append({
                        "item_code": entry.item_code,
                        "warehouse": entry.warehouse,
                        "qty": batch_target_qty,
                        "valuation_rate": valuation_rate,
                        "use_serial_batch_fields": 1,
                        "batch_no": b_name
                    })

            else:
                # Non-batched items
                items_payload.append({
                    "item_code": entry.item_code,
                    "warehouse": entry.warehouse,
                    "qty": flt(entry.qty_in_stock_uom),
                    "valuation_rate": valuation_rate,
                    "serial_no": entry.serial_no if has_serial else None
                })

        if not items_payload:
            frappe.throw(_("No variance or scanned items found for reconciliation in session {0}.").format(self.name))
       
        # 4. Create Stock Reconciliation with use_serial_batch_fields = 1
        recon = frappe.get_doc({
            "doctype": "Stock Reconciliation",
            "company": self.company,
            "purpose": "Stock Reconciliation",
            "posting_date": posting_date,
            "posting_time": posting_time,
            "items": items_payload
        })

        recon.insert(ignore_permissions=True)
        self.db_set("status", "Completed")

        frappe.msgprint(_("Stock Reconciliation Created: {0}").format(get_link_to_form("Stock Reconciliation", recon.name)))
        return recon.name

    @frappe.whitelist()
    def record_counter_scan(self, item_code, qty, conversion_factor=1.0, batch_no=None, serial_no=None):
        """ Records scan log per counter user and updates Count Entry """
        entry_name = frappe.db.get_value(
            "Count Entry", 
            {"session": self.name, "warehouse": self.warehouse, "item_code": item_code}
        )

        if not entry_name:
            frappe.throw(_("Count task not found for item {0} in this session.").format(item_code))

        entry_doc = frappe.get_doc("Count Entry", entry_name)
        converted_qty = flt(qty) * flt(conversion_factor or 1.0)

        has_batch_no, has_serial_no = frappe.db.get_value(
            "Item",
            item_code,
            ["has_batch_no", "has_serial_no"]
        )
        
        if  has_batch_no and batch_no == "":
            frappe.throw(_("Please Select or create a batch"))
        if not has_batch_no:  
            batch_no=None


        entry_doc.append("scan_logs", {
            "counter": frappe.session.user,
            "qty": converted_qty,
            "batch_no": batch_no,
            "serial_no": serial_no,
            "scan_timestamp": now_datetime()
        })

        total_qty = sum([flt(log.qty) for log in entry_doc.scan_logs])
        entry_doc.qty_in_stock_uom = total_qty
        entry_doc.difference_quantity = total_qty - flt(entry_doc.current_erp_qty)
        entry_doc.status = "Counted"

        # if batch_no:
        #     entry_doc.batch_no = batch_no

        # if serial_no:
        #     existing_serials = set([s.strip() for s in (entry_doc.serial_no or "").split("\n") if s.strip()])
        #     new_serials = [s.strip() for s in serial_no.replace(",", "\n").split("\n") if s.strip()]
        #     existing_serials.update(new_serials)
        #     entry_doc.serial_no = "\n".join(sorted(existing_serials))

        entry_doc.save(ignore_permissions=True)
        self.recalculate_statistics()

        return {"status": "success", "total_qty": total_qty}

def get_child_item_groups(parent_group):
    """ Returns parent group and all nested child item groups """
    groups = frappe.db.get_all(
        "Item Group",
        filters={
            "lft": (">=", frappe.db.get_value("Item Group", parent_group, "lft")),
            "rgt": ("<=", frappe.db.get_value("Item Group", parent_group, "rgt"))
        },
        pluck="name"
    )
    return groups if groups else [parent_group]