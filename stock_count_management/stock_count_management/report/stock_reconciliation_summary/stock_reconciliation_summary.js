frappe.query_reports["Stock Reconciliation Summary"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse"
        },
        {
            "fieldname": "docstatus",
            "label": __("Approval Status"),
            "fieldtype": "Select",
            "options": "\n0:Draft\n1:Submitted\n2:Cancelled",
            "default": ""
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        // Highlight Adjustment Totals and Variance %
        if (["total_adjustment_value", "variance_percent", "qty_difference"].includes(column.fieldname)) {
            let num = flt(data[column.fieldname]);
            if (num > 0) {
                value = `<span style="color: #2e7d32; font-weight: bold;">+${value}</span>`;
            } else if (num < 0) {
                value = `<span style="color: #c62828; font-weight: bold;">${value}</span>`;
            } else {
                value = `<span style="color: #757575;">${value}</span>`;
            }
        }

        // Positive Adjustment (Green)
        if (column.fieldname === "positive_adjustment" && flt(data.positive_adjustment) > 0) {
            value = `<span style="color: #2e7d32; font-weight: bold;">${value}</span>`;
        }

        // Negative Adjustment (Red)
        if (column.fieldname === "negative_adjustment" && flt(data.negative_adjustment) > 0) {
            value = `<span style="color: #c62828; font-weight: bold;">${value}</span>`;
        }

        // Approval Status Badges
        if (column.fieldname === "docstatus_label") {
            if (data.docstatus_label === "Approved") {
                value = `<span class="indicator-pill green">${value}</span>`;
            } else if (data.docstatus_label === "Pending Approval") {
                value = `<span class="indicator-pill orange">${value}</span>`;
            } else if (data.docstatus_label === "Rejected") {
                value = `<span class="indicator-pill red">${value}</span>`;
            }
        }

        return value;
    }
};