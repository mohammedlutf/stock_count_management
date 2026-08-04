frappe.query_reports["Uncounted Items Exception Report"] = {
    "filters": [
        {
            "fieldname": "session",
            "label": __("Stock Count Session"),
            "fieldtype": "Link",
            "options": "Stock Count Session",
            "reqd": 1
        }
    ]
};