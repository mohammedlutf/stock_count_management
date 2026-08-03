import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, get_link_to_form

class StockCountSession(Document):

    @frappe.whitelist()
    def generate_tasks(self):
        """ Pulls stock balances filtered by Warehouse, Item Group, and Brand for Cycle Counts """
        if self.status != "Draft":
            frappe.throw(_("Tasks can only be generated when Session is in Draft status."))

        # Clear previous pending entries if regenerating tasks
        frappe.db.delete("Count Entry", {"session": self.name})

        # Build dynamic SQL conditions based on selected filters
        conditions = ["bin.warehouse = %s", "item.disabled = 0"]
        params = [self.warehouse]

        if self.item_group:
            # Include child item groups recursively if nested
            item_groups = get_child_item_groups(self.item_group)
            conditions.append("item.item_group IN ({})".format(", ".join(["%s"] * len(item_groups))))
            params.extend(item_groups)

        if self.brand:
            conditions.append("item.brand = %s")
            params.append(self.brand)

        query = f"""
            SELECT 
                bin.item_code, 
                item.item_name, 
                item.stock_uom, 
                bin.actual_qty
            FROM `tabBin` bin
            INNER JOIN `tabItem` item ON bin.item_code = item.name
            WHERE {" AND ".join(conditions)}
        """

        bins = frappe.db.sql(query, tuple(params), as_dict=True)

        if not bins:
            frappe.throw(_("No matching inventory records found for warehouse {0} with the selected filters.")
                         .format(self.warehouse))

        entries_to_insert = []
        for b in bins:
            entries_to_insert.append((
                frappe.generate_hash(length=10),
                self.name,
                b.item_code,
                b.item_name,
                self.warehouse,
                b.stock_uom,
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
        frappe.msgprint(_("Generated {0} task(s) for Cycle Count.").format(len(entries_to_insert)))


    

    @frappe.whitelist()
    def recalculate_statistics(self):
        """ Updates execution progress metrics """
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

        # 1. Optionally zero out uncounted items
        if zero_out:
            uncounted_entries = frappe.get_all("Count Entry", filters={"session": self.name, "status": "Pending"})
            for u in uncounted_entries:
                doc = frappe.get_doc("Count Entry", u.name)
                doc.qty_in_stock_uom = 0.0
                doc.difference_quantity = 0.0 - flt(doc.current_erp_qty)
                doc.status = "Counted"
                doc.save(ignore_permissions=True)

        self.recalculate_statistics()

        # 2. Fetch all Counted/Verified lines
        entries = frappe.get_all(
            "Count Entry",
            filters={"session": self.name, "status": ["in", ["Counted", "Verified"]]},
            fields=["item_code", "warehouse", "current_erp_qty", "qty_in_stock_uom", "batch_no", "serial_no"]
        )

        # 3. Filter for entries with actual inventory variances
        reconcile_items = [e for e in entries if flt(e.qty_in_stock_uom) != flt(e.current_erp_qty)]

        if not reconcile_items:
            frappe.throw(_("No variance detected between physical count and system stock. No reconciliation is needed."))

        current_dt = now_datetime()
        posting_date = current_dt.strftime("%Y-%m-%d")
        posting_time = current_dt.strftime("%H:%M:%S")

        items_payload = []

        # 4. Construct payload and draft bundles
        for entry in reconcile_items:
            item_doc = frappe.get_cached_doc("Item", entry.item_code)
            has_batch = item_doc.has_batch_no
            has_serial = item_doc.has_serial_no

            item_row = {
                "item_code": entry.item_code,
                "warehouse": entry.warehouse,
                "qty": flt(entry.qty_in_stock_uom)
            }

            if has_batch or has_serial:
                bundle = frappe.new_doc("Serial and Batch Bundle")
                bundle.item_code = entry.item_code
                bundle.warehouse = entry.warehouse
                bundle.type_of_transaction = "Inward" if flt(entry.qty_in_stock_uom) >= flt(entry.current_erp_qty) else "Outward"
                bundle.voucher_type = "Stock Reconciliation"
                bundle.posting_date = posting_date
                bundle.posting_time = posting_time
                bundle.qty = flt(entry.qty_in_stock_uom)

                serials_list = []
                if has_serial and entry.serial_no:
                    serials_list = [s.strip() for s in entry.serial_no.replace('\n', ',').split(',') if s.strip()]

                if serials_list:
                    for s in serials_list:
                        bundle.append("entries", {
                            "serial_no": s,
                            "batch_no": entry.batch_no if has_batch else None,
                            "qty": 1.0
                        })
                elif has_batch and entry.batch_no:
                    bundle.append("entries", {
                        "batch_no": entry.batch_no,
                        "qty": flt(entry.qty_in_stock_uom)
                    })

                bundle.flags.ignore_mandatory = True
                bundle.save(ignore_permissions=True)

                item_row["serial_and_batch_bundle"] = bundle.name

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

def get_child_item_groups(parent_group):
        """ Returns parent group and all nested child item groups """
        groups = frappe.db.get_all(
            "Item Group",
            filters={"lft": (">=", frappe.db.get_value("Item Group", parent_group, "lft")),
                    "rgt": ("<=", frappe.db.get_value("Item Group", parent_group, "rgt"))},
            pluck="name"
        )
        return groups if groups else [parent_group]