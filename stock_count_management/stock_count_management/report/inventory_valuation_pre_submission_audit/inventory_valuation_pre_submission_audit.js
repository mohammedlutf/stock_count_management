frappe.query_reports["Inventory Valuation & Pre-Submission Audit Report"] = {
    "filters": [
        {
            "fieldname": "session",
            "label": __("Stock Count Session"),
            "fieldtype": "Link",
            "options": "Stock Count Session",
            "reqd": 1
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse"
        },
        {
            "fieldname": "only_variances",
            "label": __("Only Show Variances"),
            "fieldtype": "Check",
            "default": 1
        }
    ]
};