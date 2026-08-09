frappe.query_reports["Historical Inventory Accuracy Trend Report"] = {
    "filters": [
        {
            "fieldname": "frequency",
            "label": __("Frequency"),
            "fieldtype": "Select",
            "options": ["Monthly", "Yearly"],
            "default": "Monthly",
            "reqd": 1
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