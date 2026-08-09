frappe.query_reports["Stock Count Variance Summary"] = {
    "filters": [
        {
            "fieldname": "session",
            "label": __("Stock Count Session"),
            "fieldtype": "Link",
            "options": "Stock Count Session",
            "default": ""
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