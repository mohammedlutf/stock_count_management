frappe.query_reports["Multi-Counter Audit Report"] = {
    "filters": [
        {
            "fieldname": "session",
            "label": __("Session"),
            "fieldtype": "Link",
            "options": "Stock Count Session"
        },
        {
            "fieldname": "counter",
            "label": __("Counter User"),
            "fieldtype": "Link",
            "options": "User"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse"
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date"
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date"
        }
    ]
};