frappe.ui.form.on('Stock Count Session', {
    refresh: function(frm) {
        // Toggle field visibility depending on Count Type
        frm.toggle_display(['item_group', 'brand'], frm.doc.count_type === 'Cycle Count');

        if (frm.doc.status === 'Draft') {
            frm.add_custom_button(__('Generate Count Tasks'), function() {
                frappe.call({
                    method: 'generate_tasks',
                    doc: frm.doc,
                    callback: function() { frm.reload_doc(); }
                });
            }).addClass('btn-primary');
        }

        if (frm.doc.status === 'In Progress') {
            frm.add_custom_button(__('Check Uncounted Items'), function() {
                frappe.call({
                    method: 'get_uncounted_items',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            let msg = "<b>The following items are not yet scanned:</b><br><ul>";
                            r.message.forEach(i => {
                                msg += `<li>${i.item_code} - ${i.item_name} (Expected ERP Qty: ${i.current_erp_qty})</li>`;
                            });
                            msg += "</ul>";
                            frappe.msgprint(msg, "Uncounted Items Alert");
                        } else {
                            frappe.msgprint("All expected items have been counted!", "Complete Audit");
                        }
                    }
                });
            });

            frm.add_custom_button(__('Finalize & Create Stock Reconciliation'), function() {
                let d = new frappe.ui.Dialog({
                    title: __('Confirm Stock Reconciliation'),
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'warning_text',
                            options: '<p>Are you ready to generate the Stock Reconciliation document?</p>'
                        },
                        {
                            label: __('Zero out uncounted items'),
                            fieldname: 'zero_out_uncounted',
                            fieldtype: 'Check',
                            default: (frm.doc.count_type === 'Full Count' ? 1 : 0),
                            description: __('For Cycle Counts, leave this unchecked to only update scanned items.')
                        }
                    ],
                    primary_action_label: __('Proceed & Create'),
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: 'zero_out_uncounted_and_reconcile',
                            doc: frm.doc,
                            args: { zero_out_uncounted: values.zero_out_uncounted },
                            callback: function() { frm.reload_doc(); }
                        });
                    }
                });
                d.show();
            }).addClass('btn-success');
        }
    },

    count_type: function(frm) {
        // Show/hide filter fields when count_type changes
        frm.toggle_display(['item_group', 'brand'], frm.doc.count_type === 'Cycle Count');
    }
});