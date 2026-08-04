frappe.pages['mobile-scanner'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Mobile Stock Counter'),
        single_column: true
    });

    if (typeof Html5Qrcode === 'undefined') {
        let script = document.createElement('script');
        script.src = "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js";
        document.head.appendChild(script);
    }
    
    $(wrapper).find('.layout-main-section').html(frappe.render_template('mobile_scanner', {}));

    let current_item = null;
    let html5QrScanner = null;
    let sessions_map = {};

    // 1. Fetch In-Progress Sessions on Page Load
    loadActiveSessions();

    function loadActiveSessions() {
        frappe.call({
            method: 'stock_count_management.api.api.get_active_sessions',
            callback: function(r) {
                if (r.message) {
                    let select = $('#target-session-select').empty();
                    select.append(new Option(__('-- Select In-Progress Session --'), ''));
                    
                    r.message.forEach(s => {
                        sessions_map[s.name] = s.warehouse;
                        select.append(new Option(`${s.session_name} (${s.name})`, s.name));
                    });
                }
            }
        });
    }

    // Auto-populate warehouse when session is selected
    $('#target-session-select').on('change', function() {
        let selected_session = $(this).val();
        if (selected_session && sessions_map[selected_session]) {
            $('#target-warehouse-display').val(sessions_map[selected_session]);
        } else {
            $('#target-warehouse-display').val('');
        }
    });

    // 2. Camera controls
    $('#btn-camera-toggle').on('click', function() { startCamera(); });
    $('#btn-stop-camera').on('click', function() { stopCamera(); });

    function startCamera() {
        if (typeof Html5Qrcode === 'undefined') return;

        $('#camera-box').removeClass('d-none');
        $('#btn-camera-toggle').hide();

        if (!html5QrScanner) html5QrScanner = new Html5Qrcode("camera-render");

        html5QrScanner.start(
            { facingMode: "environment" },
            { fps: 15, qrbox: { width: 250, height: 150 } },
            (decodedText) => {
                $('#barcode-input').val(decodedText);
                stopCamera();
                fetchItem(decodedText);
            }
        ).catch(() => stopCamera());
    }

    function stopCamera() {
        if (html5QrScanner && html5QrScanner.isScanning) {
            html5QrScanner.stop().then(() => {
                $('#camera-box').addClass('d-none');
                $('#btn-camera-toggle').show();
            });
        } else {
            $('#camera-box').addClass('d-none');
            $('#btn-camera-toggle').show();
        }
    }

    // 3. Item Search (Barcode / Code / Name)
    $('#barcode-input').on('keypress', function(e) {
        if (e.which === 13) fetchItem($(this).val().trim());
    });

    $('#btn-fetch-item').on('click', function() {
        fetchItem($('#barcode-input').val().trim());
    });

    function fetchItem(search_query) {
        let session = $('#target-session-select').val();
        let warehouse = $('#target-warehouse-display').val();

        if (!session || !warehouse) {
            frappe.msgprint(__('Please select an active In-Progress Session first.'));
            return;
        }

        frappe.call({
            method: 'stock_count_management.api.api.scan_and_fetch_item',
            args: { search_query: search_query, warehouse: warehouse, session: session },
            callback: function(r) {
                if (r.message) {
                    current_item = r.message;
                    renderItemDetails(current_item);
                }
            }
        });
    }

    function renderItemDetails(item) {
        $('#disp-item-name').text(item.item_name);
        $('#disp-item-code').text(`${__("Code")} : ${item.item_code} | ${__("Primary UOM")}: ${item.stock_uom}`);
        $('#disp-accumulated-qty').text(item.accumulated_stock_qty);
        $('#disp-stock-uom').text(item.stock_uom);

        if (item.current_erp_qty !== null) {
            $('#disp-system-qty').text(` ${__("System Expected Balance")}: ${item.current_erp_qty}`).removeClass('d-none');
        } else {
            $('#disp-system-qty').addClass('d-none');
        }

        // Auto-select UOM matched from barcode
        let select = $('#uom-select').empty();
        item.available_uoms.forEach(u => {
            select.append(new Option(`${u.uom} (x${u.conversion_factor})`, u.uom, false, u.uom === item.auto_selected_uom));
        });

        // Toggle Batch Section
        if (item.has_batch) {
            $('#batch-section').removeClass('d-none');
            let batch_sel = $('#batch-select').empty();
            batch_sel.append(new Option(__('-- Select Existing Batch --'), ''));
            item.available_batches.forEach(b => {
                batch_sel.append(new Option(b, b, false, b === item.existing_batch));
            });
            batch_sel.append(new Option(__('+ Enter New Batch'), 'NEW'));
        } else {
            $('#batch-section').addClass('d-none');
        }

        // Toggle Serial Section
        if (item.has_serial) {
            $('#serial-section').removeClass('d-none');
            $('#serial-input').val(item.existing_serials);
            $('#qty-section').addClass('d-none'); // Hide Qty field - quantity calculated from serial count
        } else {
            $('#serial-section').addClass('d-none');
            $('#qty-section').removeClass('d-none');
        }

        $('#scanned-item-card').removeClass('d-none');
        if (!item.has_serial) $('#input-scan-qty').val(1.0).focus().select();
    }

    $('#batch-select').on('change', function() {
        if ($(this).val() === 'NEW') {
            $('#batch-manual-input').removeClass('d-none').focus();
        } else {
            $('#batch-manual-input').addClass('d-none');
        }
    });

    // 4. Save Count Payload
    $('#btn-save-count-entry').on('click', function() {
        if (!current_item) return;

        let selected_uom = $('#uom-select').val();
        let uom_obj = current_item.available_uoms.find(u => u.uom === selected_uom);

        let selected_batch = $('#batch-select').val();
        if (selected_batch === 'NEW') {
            selected_batch = $('#batch-manual-input').val().trim();
        }

        frappe.call({
            method: 'stock_count_management.api.api.submit_count_payload',
            args: {
                session: $('#target-session-select').val(),
                warehouse: $('#target-warehouse-display').val(),
                item_code: current_item.item_code,
                selected_uom: selected_uom,
                conversion_factor: uom_obj ? uom_obj.conversion_factor : 1.0,
                counted_quantity: parseFloat($('#input-scan-qty').val()) || 0,
                batch_no: selected_batch,
                serial_no: $('#serial-input').val().trim()
            },
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    frappe.show_alert({
                        message: __("Scanned Qty Added! Total: ") + r.message.new_total_stock_qty + ' ' + r.message.stock_uom,
                        indicator: 'green'
                    });
                    resetUI();
                }
            }
        });
    });

    function resetUI() {
        current_item = null;
        $('#scanned-item-card').addClass('d-none');
        $('#barcode-input').val('').focus();
    }
};