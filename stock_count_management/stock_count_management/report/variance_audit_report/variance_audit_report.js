frappe.query_reports["Variance Audit Report"] = {
    "filters": [
        {
            "fieldname": "session",
            "label": __("Stock Count Session"),
            "fieldtype": "Link",
            "options": "Stock Count Session",
            "reqd": 1
        },
        {
            "fieldname": "variance_only",
            "label": __("Show Variances Only"),
            "fieldtype": "Check",
            "default": 1
        }
    ]
};