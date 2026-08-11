frappe.query_reports["Uncounted Items"] = {
    "filters": [
        {
            "fieldname": "stock_reconciliation",
            "label": __("Stock Reconciliation"),
            "fieldtype": "Link",
            "options": "Stock Reconciliation",
            "reqd": 1,
            "on_change": function() {
                let sr = frappe.query_report.get_filter_value("stock_reconciliation");
                if (sr) {
                    frappe.db.get_value("Stock Reconciliation", sr, ["warehouse", "company"], (r) => {
                        if (r && r.warehouse) {
                            frappe.query_report.set_filter_value("warehouse", r.warehouse);
                        } else if (r && r.company) {
                            // Fetch Default Warehouse for Company if empty
                            frappe.db.get_value("Company", r.company, "default_warehouse", (comp) => {
                                if (comp && comp.default_warehouse) {
                                    frappe.query_report.set_filter_value("warehouse", comp.default_warehouse);
                                }
                            });
                        }
                    });
                }
            }
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Link",
            "options": "Warehouse"
        },
        {
            "fieldname": "item_group",
            "label": __("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group"
        },
        {
            "fieldname": "ignore_zero_stock",
            "label": __("Hide Zero Stock Items"),
            "fieldtype": "Check",
            "default": 0
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        if (column.fieldname === "system_qty") {
            let qty = flt(data.system_qty);
            if (qty > 0) {
                value = `<span style="color: #c62828; font-weight: bold;">${value}</span>`;
            } else if (qty === 0) {
                value = `<span style="color: #757575;">${value}</span>`;
            }
        }

        if (column.fieldname === "status") {
            value = `<span class="indicator-pill orange">${value}</span>`;
        }

        return value;
    }
};