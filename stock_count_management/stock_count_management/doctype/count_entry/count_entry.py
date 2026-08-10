import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

class CountEntry(Document):


    def validate(self):
        if self.session:
            session_status = frappe.db.get_value(
                "Stock Count Session",
                self.session,
                "status"
            )

            if session_status == "Completed":
                frappe.throw(
                    "This Stock Count Session is already Completed. "
                    "You cannot add or edit Count Entries."
                )
    def before_save(self):
        self.recalculate_variance()

    def on_update(self):
        if self.session :
                session = frappe.get_doc(
                    "Stock Count Session",
                    self.session
                )

                session.recalculate_statistics()
    def recalculate_variance(self):
        # Always force float casting to handle negative values correctly
        # counted = flt(self.qty_in_stock_uom)
        # erp_qty = flt(self.current_erp_qty)

        total_qty = sum([flt(log.qty) for log in self.scan_logs])
        self.qty_in_stock_uom = total_qty
        self.difference_quantity = total_qty - flt(self.current_erp_qty)
        
        
        if self.status == "Pending" and self.scan_logs:
            self.status = "Counted"
              
        # # Correct formula: Counted - (-30) = Counted + 30
        # self.difference_quantity = counted - erp_qty

        # Trigger Variance Investigation whenever there is a difference (positive or negative)
        if self.difference_quantity != 0 and self.status == "Counted":
            self.create_variance_investigation()

          

    def create_variance_investigation(self):
        existing = frappe.db.exists("Variance Investigation", {"count_entry": self.name})
        if existing:
            var_doc = frappe.get_doc("Variance Investigation", existing)
            var_doc.difference = self.difference_quantity
            var_doc.save(ignore_permissions=True)
        else:
            var = frappe.new_doc("Variance Investigation")
            var.count_entry = self.name
            var.item_code = self.item_code
            var.warehouse = self.warehouse
            var.difference = self.difference_quantity
            var.reason = "Unknown"
            var.insert(ignore_permissions=True)