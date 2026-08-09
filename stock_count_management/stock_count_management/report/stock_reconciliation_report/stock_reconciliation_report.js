frappe.query_reports["Stock Reconciliation Report"] = {

    filters: [
        {
            fieldname: "stock_reconciliation",
            label: __("Stock Reconciliation"),
            fieldtype: "Link",
            options: "Stock Reconciliation",
            reqd: 1
        },
        {
            fieldname: "variance_only",
            label: __("Variance Only"),
            fieldtype: "Check",
            default: 0
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        return default_formatter(value, row, column, data);
    },

    after_datatable_render: function() {
        setTimeout(function() {
            highlight_stock_rows();
        }, 100);
    }
};


function highlight_stock_rows() {

    const report = frappe.query_report;

    if (!report || !report.data) {
        return;
    }

    // Get actual DataTable rows
    $(".dt-row").each(function() {

        const $row = $(this);

        // DataTable row index
        const rowIndex = $row.attr("data-row-index");

        if (rowIndex === undefined) {
            return;
        }

        const data = report.data[parseInt(rowIndex)];

        if (!data) {
            return;
        }

        const variance = flt(data.variance_value);

        // Remove previous styles
        $row.find(".dt-cell").css({
            "background-color": "",
            "color": "",
            "font-weight": ""
        });

        // Negative = LOSS
        if (variance < 0) {

            $row.find(".dt-cell").css({
                "background-color": "#ffebee",
                "color": "#c62828"
            });

        }

        // Positive = GAIN
        else if (variance > 0) {

            $row.find(".dt-cell").css({
                "background-color": "#e8f5e9",
                "color": "#2e7d32"
            });

        }

    });
}
$(`<style>

.dt-row .dt-cell.stock-loss {
    background-color: #ffebee !important;
    color: #c62828 !important;
}

.dt-row .dt-cell.stock-gain {
    background-color: #e8f5e9 !important;
    color: #2e7d32 !important;
}

</style>`).appendTo("head");