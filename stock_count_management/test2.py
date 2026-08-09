import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, get_link_to_form

class StockCountSession(Document):

    @frappe.whitelist()
    def generate_tasks(self):
        """ Pulls active stock balances for the warehouse and creates Count Entries """
        if self.status != "Draft":
            frappe.throw(_("Tasks can only be generated when Session is in Draft status."))

        # Clear previous pending entries if regenerating tasks
        frappe.db.delete("Count Entry", {"session": self.name})

        # Fetch active Bins for the warehouse
        bins = frappe.db.get_all(
            "Bin",
            filters={"warehouse": self.warehouse},
            fields=["item_code", "actual_qty"]
        )

        if not bins:
            frappe.throw(_("No inventory records found for warehouse {0}").format(self.warehouse))

        entries_to_insert = []
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
        """ Native ERPNext 15 Stock Reconciliation Generator """
        zero_out = frappe.parse_json(zero_out_uncounted)

        # 1. Bulk update uncounted items directly in SQL if requested
        if zero_out:
            frappe.db.sql("""
                UPDATE `tabCount Entry`
                SET qty_in_stock_uom = 0.0,
                    difference_quantity = 0.0 - current_erp_qty,
                    status = 'Counted'
                WHERE session = %s AND status = 'Pending'
            """, (self.name,))

        self.recalculate_statistics()

        # 2. Fetch all Counted/Verified lines for this session
        entries = frappe.get_all(
            "Count Entry",
            filters={"session": self.name, "status": ["in", ["Counted", "Verified"]]},
            fields=["name", "item_code", "warehouse", "current_erp_qty", "qty_in_stock_uom", "batch_no", "serial_no"]
        )

        # 3. Filter for entries with actual inventory variances
        reconcile_items = [e for e in entries if flt(e.qty_in_stock_uom) != flt(e.current_erp_qty)]

        if not reconcile_items:
            frappe.throw(_("No variance detected between physical count and system stock for session {0}.").format(self.name))

        current_dt = now_datetime()
        posting_date = current_dt.strftime("%Y-%m-%d")
        posting_time = current_dt.strftime("%H:%M:%S")

        items_payload = []

        # 4. Construct item rows and valid non-zero batch bundles
        for entry in reconcile_items:
            item_doc = frappe.get_cached_doc("Item", entry.item_code)
            has_batch = item_doc.has_batch_no
            has_serial = item_doc.has_serial_no

            counted_qty = flt(entry.qty_in_stock_uom)
            erp_qty = flt(entry.current_erp_qty)
            diff_qty = counted_qty - erp_qty

            valuation_rate = frappe.db.get_value("Bin", {"item_code": entry.item_code, "warehouse": entry.warehouse}, "valuation_rate") or item_doc.valuation_rate or 0.0

            item_row = {
                "item_code": entry.item_code,
                "warehouse": entry.warehouse,
                "qty": counted_qty,
                "valuation_rate": valuation_rate
            }

            if has_batch or has_serial:
                is_inward = diff_qty >= 0
                batch_map = {}

                if is_inward:
                    # Physical count comes from scanned batches
                    scan_logs = frappe.get_all(
                        "Count Scan Log",
                        filters={"parent": entry.name},
                        fields=["batch_no", "qty"]
                    )

                    for log in scan_logs:
                        if log.batch_no:
                            batch_map[log.batch_no] = batch_map.get(log.batch_no, 0.0) + flt(log.qty)

                    if not batch_map and entry.batch_no:
                        batch_map[entry.batch_no] = counted_qty

                else:
                    # Query active system batches for Outward stock reduction
                    batch_rows = frappe.db.sql("""
                        SELECT
                            sbe.batch_no,
                            SUM(sbe.qty) AS qty
                        FROM `tabStock Ledger Entry` sle
                        INNER JOIN `tabSerial and Batch Bundle` sabb
                            ON sabb.name = sle.serial_and_batch_bundle
                        INNER JOIN `tabSerial and Batch Entry` sbe
                            ON sbe.parent = sabb.name
                        WHERE
                            sle.item_code = %s
                            AND sle.warehouse = %s
                            AND sabb.type_of_transaction = 'Inward'
                            AND IFNULL(sbe.batch_no,'') != ''
                        GROUP BY sbe.batch_no
                        HAVING qty > 0
                    """, (entry.item_code, entry.warehouse), as_dict=True)

                    for row in batch_rows:
                        batch_map[row.batch_no] = flt(row.qty)

                # Filter strictly positive quantities (> 0)
                valid_batch_entries = {}
                for batch_no, qty in batch_map.items():
                    if qty <= 0:
                        continue

                    valid_batch_entries[batch_no] = qty

                    if is_inward and not frappe.db.exists("Batch", batch_no):
                        batch = frappe.new_doc("Batch")
                        batch.batch_id = batch_no
                        batch.item = entry.item_code
                        batch.insert(ignore_permissions=True)

                serials_list = []
                if has_serial and entry.serial_no:
                    serials_list = [s.strip() for s in entry.serial_no.replace("\n", ",").split(",") if s.strip()]

                # Only create bundle if valid batch entries or serial numbers exist
                if valid_batch_entries or serials_list:
                    bundle = frappe.new_doc("Serial and Batch Bundle")
                    bundle.item_code = entry.item_code
                    bundle.warehouse = entry.warehouse
                    bundle.type_of_transaction = "Inward" if is_inward else "Outward"
                    bundle.voucher_type = "Stock Reconciliation"
                    bundle.posting_date = posting_date
                    bundle.posting_time = posting_time

                    if serials_list:
                        for serial in serials_list:
                            bundle.append("entries", {
                                "serial_no": serial,
                                "batch_no": list(valid_batch_entries.keys())[0] if valid_batch_entries else None,
                                "qty": 1.0
                            })
                    elif has_batch:
                        for batch_no, qty in valid_batch_entries.items():
                            bundle.append("entries", {
                                "batch_no": batch_no,
                                "qty": qty
                            })

                    bundle.qty = sum([flt(e.get("qty", 0)) for e in bundle.entries])
                    bundle.flags.ignore_mandatory = True
                    bundle.flags.ignore_validate_update_after_submit = True
                    bundle.save(ignore_permissions=True)

                    item_row["serial_and_batch_bundle"] = bundle.name

                    # ------------------------------------------------------------------
                    # 📌 FIX: Align item_row["qty"] with Outward bundle qty on zero-out
                    # ------------------------------------------------------------------
                    if not is_inward:
                        item_row["qty"] = bundle.qty

            items_payload.append(item_row)

        # 5. Create native Stock Reconciliation document
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

        if batch_no:
            entry_doc.batch_no = batch_no

        if serial_no:
            existing_serials = set([s.strip() for s in (entry_doc.serial_no or "").split("\n") if s.strip()])
            new_serials = [s.strip() for s in serial_no.replace(",", "\n").split("\n") if s.strip()]
            existing_serials.update(new_serials)
            entry_doc.serial_no = "\n".join(sorted(existing_serials))

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



<div style="margin-top:30px; display:flex; align-items:flex-start;">
    <!-- Sender Signature -->
    <div style="text-align:left;">
        <h3> Sender Signature:</h3>
        <p style="font-weight: bold;">Asem Abdualaziz</p>
        <p>AuTech General Manager</p>
        <!-- Signature + Stamp -->
    <div style="display:flex; align-items:center;">
    <img src="/files/asem_sign.png" style="width:150px; height:120px;">

    <img src="/files/autech stamp.png" style="width:150px; height:120px; margin-left:-25px;">
</div>
    </div>

    <!-- Vertical line + Receiver -->
    <div style="display:flex; align-items:flex-start;">
        <!-- Vertical line -->
        <div style="border-left:2px solid black;"></div>

        <!-- Receiver Signature -->
        <div style="text-align:left; padding-left:300px;">
            <h3> Receiver Signature:</h3>
            <p style="font-weight: bold;">_________________________</p>
        </div>
    </div>
</div>




