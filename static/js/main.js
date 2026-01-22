$(document).ready(function() {
    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    // Initialize all tables with empty state (navigation controls visible)
    initializeAllTables();

    // Check data status on load
    checkDataStatus();

    // =========================================================================
    // TAB NAVIGATION
    // =========================================================================
    $('.tab-btn').click(function() {
        const tab = $(this).data('tab');
        $('.tab-btn').removeClass('active');
        $(this).addClass('active');
        $('.tab-pane').removeClass('active');
        $('#' + tab).addClass('active');

        // Check after-effect tab
        if (tab === 'after-effect') {
            checkOptimizationStatus();
        }
    });
    
    // Layer tabs
    $(document).on('click', '.layer-btn', function() {
        const layer = $(this).data('layer');
        const container = $(this).closest('.table-container');
        container.find('.layer-btn').removeClass('active');
        $(this).addClass('active');
        container.find('.layer-pane').removeClass('active');
        container.find('#layer-' + layer).addClass('active');
    });
    
    // =========================================================================
    // DATA TABLES INITIALIZATION
    // =========================================================================

    /**
     * Initialize all tables with empty state on page load
     * This ensures navigation controls are always visible
     */
    function initializeAllTables() {
        const emptyColumns = [{ title: 'No Data', data: null }];

        // Overview tables
        initDataTable('table-profiles', [], emptyColumns);
        initDataTable('table-ma-hang', [], emptyColumns);
        initDataTable('table-skc', [], emptyColumns);
        initDataTable('table-sku', [], emptyColumns);
        initDataTable('table-wh-ma-hang', [], emptyColumns);
        initDataTable('table-wh-skc', [], emptyColumns);
        initDataTable('table-wh-sku', [], emptyColumns);

        // Product Overview tables (separate for Mã hàng, SKC and SKU layers)
        initDataTable('table-product-ma-hang', [], emptyColumns);
        initDataTable('table-product-skc', [], emptyColumns);
        initDataTable('table-product-sku', [], emptyColumns);


        // Broken Analysis tables
        initDataTable('table-top-stores', [], emptyColumns);
        initDataTable('table-broken-store', [], emptyColumns);
        initDataTable('table-broken-skc-detail', [], emptyColumns);
        initDataTable('table-broken-by-skc', [], emptyColumns);

        // After Effect tables
        initDataTable('table-profiles-after', [], emptyColumns);
        initDataTable('table-ma-hang-after', [], emptyColumns);
        initDataTable('table-skc-after', [], emptyColumns);
        initDataTable('table-sku-after', [], emptyColumns);
        initDataTable('table-wh-ma-hang-after', [], emptyColumns);
        initDataTable('table-wh-skc-after', [], emptyColumns);
        initDataTable('table-wh-sku-after', [], emptyColumns);
        initDataTable('table-broken-after', [], emptyColumns);
        initDataTable('table-broken-skc-after', [], emptyColumns);

        // Audit panels
        initDataTable('table-warehouse-transfers', [], emptyColumns);
        initDataTable('table-store-transfers', [], emptyColumns);
        initDataTable('table-source-destinations', [], emptyColumns);
        initDataTable('table-destination-sources', [], emptyColumns);
    }

    /**
     * Initialize DataTable with navigation controls always visible
     * Two states:
     * - Inactive: Empty data, controls disabled but visible
     * - Active: Has data, controls fully functional
     */
    function initDataTable(tableId, data, columns) {
        // Destroy existing table if any
        if ($.fn.DataTable.isDataTable('#' + tableId)) {
            $('#' + tableId).DataTable().destroy();
        }
        $('#' + tableId).empty();

        // If no data, use empty array but still initialize DataTable
        const tableData = data && data.length > 0 ? data : [];
        const tableColumns = columns && columns.length > 0 ? columns : [{ title: 'No Data', data: null }];

        // Always initialize DataTable (even with empty data)
        const table = $('#' + tableId).DataTable({
            data: tableData,
            columns: tableColumns,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Tất cả"]],
            scrollX: true,  // Enable horizontal scroll for wide tables
            scrollY: '400px',  // Default height - CSS overrides per section
            scrollCollapse: false,  // Keep height fixed even with less data
            order: [],
            autoWidth: true,  // Enable auto column width adjustment for header alignment
            dom: '<"top"lf>rt<"bottom"ip><"clear">',
            language: {
                search: "Tìm kiếm:",
                lengthMenu: "Hiển thị _MENU_ dòng",
                info: "Hiển thị _START_ đến _END_ / _TOTAL_ dòng",
                infoEmpty: "Không có dữ liệu",
                emptyTable: "Không có dữ liệu",
                zeroRecords: "Không tìm thấy kết quả",
                infoFiltered: "(lọc từ _MAX_ dòng)",
                paginate: {
                    first: "Đầu",
                    last: "Cuối",
                    next: "Sau",
                    previous: "Trước"
                }
            },
            drawCallback: function(settings) {
                // Adjust column widths to ensure header/body alignment
                this.api().columns.adjust();

                // Force pagination always visible for table-top-stores
                if (tableId === 'table-top-stores') {
                    const wrapper = $('#' + tableId).closest('.dataTables_wrapper');
                    wrapper.find('.dataTables_paginate').show();
                    wrapper.find('.dataTables_info').show();
                }
            }
        });

        setTimeout(function() {
            $('#' + tableId).DataTable().columns.adjust().draw();
        }, 100);
    }
    
    // =========================================================================
    // API CALLS
    // =========================================================================
    
    // Load Store Profiles
    function loadStoreProfiles() {
        const category = $('#category-filter-overview').val();
        $.get('/api/overview/store_profiles', { category: category }, function(data) {
            if (data.error) {
                $('#table-profiles').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            // Define column order explicitly
            const columnOrder = [
                'Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Diện tích',
                'Tổng Tồn', 'Tổng Nhu cầu', 'Tổng Nguồn cung',
                `Bán TB_${category}`, `MOH_${category}`, `MOH Rating_${category}`,
                `Tình trạng Gãy Size_${category}`, `SKC Limit_${category}`, `SKC Trưng bày_${category}`
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));

            initDataTable('table-profiles', data, columns);
        });
    }
    
    // Load SKC at Store
    function loadSKCAtStore(storeId) {
        $.get('/api/overview/store_skc/' + storeId, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Phân loại', 'Tồn hiện tại', 
                'Số Size Có Tồn', 'Bán TB', 'Demand', 'Supply', 'MOH','MOH Rating', 
                'Broken Index', 'IsBroken'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-skc', data, columns);
        });
    }
    
    // Load SKU at Store
    function loadSKUAtStore(storeId) {
        $.get('/api/overview/store_sku/' + storeId, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size', 'SKU_ID', 'Phân loại', 
                'Thuộc tính', 'Tồn hiện tại', 'Bán TB', 'Demand', 'Supply', 
                'MOH','MOH Rating'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-sku', data, columns);
        });
    }

    // Load Mã hàng at Store
    function loadMaHangAtStore(storeId) {
        $.get('/api/overview/store_ma_hang/' + storeId, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã hàng', 'Phân loại','Tồn hiện tại',
                'Bán TB', 'Demand', 'Supply', 'MOH','MOH Rating', 'Broken Index'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-ma-hang', data, columns);
        });
    }

    // Load Warehouse Mã hàng
    function loadWarehouseMaHang() {
        $.get('/api/overview/warehouse_ma_hang', function(data) {
            if (data.error) {
                $('#table-wh-ma-hang').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Phân loại', 'Số SKC', 'Số SKU', 'Tổng Tồn theo SKU'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-wh-ma-hang', data, columns);
        });
    }

    // Load Warehouse SKC
    function loadWarehouseSKC() {
        $.get('/api/overview/warehouse_skc', function(data) {
            if (data.error) {
                $('#table-wh-skc').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Số Size', 'Phân loại', 'Tổng Tồn theo SKU'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-wh-skc', data, columns);
        });
    }

    // Load Warehouse SKU by SKC
    function loadWarehouseSKU(skc) {
        console.log('loadWarehouseSKU called with SKC:', skc);
        $.get('/api/overview/warehouse_sku/' + skc, function(data) {
            console.log('Warehouse SKU API response:', data);
            if (data.error) {
                console.error('Warehouse SKU error:', data.error);
                $('#table-wh-sku').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size','SKU_ID', 
                'Phân loại', 'Thuộc tính', 'Tồn hiện tại'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-wh-sku', data, columns);
            console.log('Warehouse SKU table updated');
        }).fail(function(xhr, status, error) {
            console.error('Warehouse SKU API call failed:', status, error, xhr.responseText);
        });
    }
    
    // Load Broken by Store
    function loadBrokenByStore(storeId) {
        $.get('/api/broken/by_store/' + storeId, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã cửa hàng', 'Mã màu', 'Tình trạng Gãy Size', 'Gãy Size'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-broken-store', data, columns);
        });
        
        $.get('/api/broken/skc_at_store/' + storeId, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
                'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
                'Tình trạng Gãy Size', 'Gãy Size', 'Số Size Có Tồn'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));

            initDataTable('table-broken-skc-detail', data, columns);
        });
    }
    
    // Load Reference section (Size Range + Top 3 Stores)
    function loadReference(skc) {
        console.log('loadReference called with SKC:', skc);

        // Load size range
        $.get('/api/broken/size_range/' + skc, function(data) {
            console.log('Size Range API response:', data);
            if (data.error) {
                console.error('Size Range error:', data.error);
                $('#size-range-display').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            let html = '<p><strong>SKC:</strong> ' + data.skc + '</p>';
            html += '<p><strong>Dải Size:</strong> ' + data.sizes.join(', ') + '</p>';
            html += '<p><strong>Size có Tồn:</strong> ' + data.sizes_with_stock.join(', ') + '</p>';
            html += '<p><strong>Tổng Tồn hiện tại:</strong> ' + data.total_stock + '</p>';
            $('#size-range-display').html(html);
            console.log('Size Range updated');
        }).fail(function(xhr, status, error) {
            console.error('Size Range API call failed:', status, error, xhr.responseText);
        });

        // Load top stores
        $.get('/api/broken/top_stores/' + skc, function(data) {
            console.log('Top Stores API response:', data);
            if (data.error) {
                console.error('Top Stores error:', data.error);
                return;
            }

            const columnOrder = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền'];
            const availableKeys = Object.keys(data[0] || {});
            const orderedKeys = columnOrder.filter(col => availableKeys.includes(col));
            const remainingKeys = availableKeys.filter(col => !columnOrder.includes(col));
            const columns = [...orderedKeys, ...remainingKeys].map(k => ({ title: k, data: k }));
            initDataTable('table-top-stores', data, columns);
            console.log('Top Stores table updated');
        }).fail(function(xhr, status, error) {
            console.error('Top Stores API call failed:', status, error, xhr.responseText);
        });
    }

    // Load Broken by SKC (only the table, not Size Range or Top 3 Stores)
    function loadBrokenBySKC(skc) {
        const storeFilter = $('#store-filter-broken').val();

        if (storeFilter === 'all') {
            // Load all stores broken by SKC
            $.get('/api/broken/by_skc/' + skc, function(data) {
                if (data.error) return;
                const columnOrder = [
                    'Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Mã màu',
                    'Tình trạng Gãy Size', 'Gãy Size'
                ];

                const availableKeys = Object.keys(data[0] || {});
                const columns = columnOrder
                    .filter(col => availableKeys.includes(col))
                    .map(k => ({ title: k, data: k }));
                initDataTable('table-broken-by-skc', data, columns);
            });
        } else {
            // Load SKU at specific store for this SKC
            $.get('/api/broken/sku_at_store/' + skc + '/' + storeFilter, function(data) {
                if (data.length === 0) {
                    // No broken data at this store
                    $('#table-broken-by-skc').html('<p class="placeholder">Không có dữ liệu</p>');
                    return;
                }
                const columnOrder = [
                    'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size', 'SKU_ID', 'Phân loại',
                    'Tồn hiện tại', 'Bán TB', 'Demand', 'Supply', 'MOH', 'MOH Rating',
                    'Tình trạng Gãy Size'
                ];

                const availableKeys = Object.keys(data[0] || {});
                const columns = columnOrder
                    .filter(col => availableKeys.includes(col))
                    .map(k => ({ title: k, data: k }));
                initDataTable('table-broken-by-skc', data, columns);
            });
        }
    }

    // Load store list for dropdown
    function loadStoreList() {
        $.get('/api/broken/store_list', function(data) {
            const select = $('#store-filter-broken');
            select.empty();
            select.append('<option value="all">Tất cả</option>');
            data.forEach(function(store) {
                select.append('<option value="' + store['Mã cửa hàng'] + '">' +
                             store['Mã cửa hàng'] + ' - ' + store['Cửa hàng'] + '</option>');
            });
        });
    }

    // =========================================================================
    // RUN OPTIMIZATION
    // =========================================================================
    $('#btn-run-optimization').click(function() {
        // Check if data is loaded
        $.get('/api/upload/status', function(status) {
            if (!status.has_data) {
                alert('Vui lòng upload file CSV trước khi chạy optimization');
                return;
            }

            const params = {
                time_limit: parseInt($('#time-limit').val()) || 300,
                gap: parseFloat($('#gap').val()) || 0.05,
                season: $('#season').val() === 'true'
            };

            $('#run-status').text('⏳ Đang chạy...');
            $('#btn-run-optimization').prop('disabled', true);

            $.ajax({
                url: '/api/reallocation/run',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(params),
                success: function(response) {
                    $('#run-status').text('✅ Hoàn thành!');
                    $('#btn-run-optimization').prop('disabled', false);
                    updateDataStatus(true);
                    loadSummary(response.summary);
                    loadReallocationPlan();
                    // Load audit panels
                    loadWarehouseTransfers();
                    loadStoreTransfers();
                    loadSourceDestinations();
                    loadDestinationSources();
                },
                error: function(xhr) {
                    $('#run-status').text('❌ Lỗi: ' + xhr.responseJSON?.error);
                    $('#btn-run-optimization').prop('disabled', false);
                }
            });
        });
    });
    
    function loadSummary(summary) {
        // Chỉ hiển thị các key này
        const displayOrder = ['objective', 'status', 
                            'total_demand_before', 'total_supply_before', 'total_quantity', 
                            'total_transfers', 'store_to_store', 'warehouse_to_store',
                            'unmet_rate'
                        ];
        
        let html = '';
        for (const key of displayOrder) {
            if (summary[key] !== undefined) {
                html += `<div class="summary-item">
                    <div class="value">${summary[key]}</div>
                    <div class="label">${key}</div>
                </div>`;
            }
        }
        $('#summary-content').html(html);
    }

    
    function loadReallocationPlan() {
        $.get('/api/reallocation/plan', function(data) {
            if (data.error) return;
            const columns = Object.keys(data[0] || {}).map(k => ({ title: k, data: k }));
            initDataTable('table-reallocation', data, columns);
        });
    }

    // =========================================================================
    // AUDIT PANELS
    // =========================================================================

    // Load Audit Panel 1: Warehouse Transfers
    function loadWarehouseTransfers() {
        $.get('/api/reallocation/audit/warehouse_transfers', function(data) {
            if (data.error) {
                $('#table-warehouse-transfers').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            // Define column order
            const columnOrder = [
                'Nguồn', 'SKC', 'SKU_ID', 'Thuộc tính', 'Số lượng điều chuyển',
                'Tồn tại Kho', 'Đích', 'Vùng miền Đích', 'Demand Đích', 
                'SKC Limit tại Đích', 'SKC Trưng bày tại Đích', 'Số SKC Đích nhận'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));

            initDataTable('table-warehouse-transfers', data, columns);
        });
    }

    // Load Audit Panel 2: Store Transfers
    function loadStoreTransfers() {
        $.get('/api/reallocation/audit/store_transfers', function(data) {
            if (data.error) {
                $('#table-store-transfers').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            const columnOrder = [
                'Nguồn', 'Vùng miền Nguồn', 'SKC', 
                'SKU_ID', 'Thuộc tính', 'Số lượng điều chuyển', 
                'Supply Nguồn', 'MOH tại Nguồn',
                'Đích', 'Vùng miền Đích', 'Demand Đích', 
                'SKC Limit tại Đích', 'SKC Trưng bày tại Đích', 'Số SKC Đích nhận'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));

            initDataTable('table-store-transfers', data, columns);
        });
    }

    // Load Audit Panel 3A: Source → Destinations
    function loadSourceDestinations() {
        $.get('/api/reallocation/audit/source_destinations', function(data) {
            if (data.error) {
                $('#table-source-destinations').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            const columns = [
                { title: 'Nguồn', data: 'Nguồn' },
                { title: 'Số Đích đến', data: 'Số Đích đến' }
            ];

            initDataTable('table-source-destinations', data, columns);
        });
    }

    // Load Audit Panel 3B: Destination ← Sources
    function loadDestinationSources() {
        $.get('/api/reallocation/audit/destination_sources', function(data) {
            if (data.error) {
                $('#table-destination-sources').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            const columns = [
                { title: 'Đích', data: 'Đích' },
                { title: 'Số Nguồn Nhận', data: 'Số Nguồn Nhận' }
            ];

            initDataTable('table-destination-sources', data, columns);
        });
    }

    // =========================================================================
    // SENSITIVITY ANALYSIS
    // =========================================================================
    $('.sens-btn').click(function() {
        const sensId = $(this).data('sens');
        $('.sens-btn').removeClass('active');
        $(this).addClass('active');

        $.get('/api/reallocation/sensitivity', function(response) {
            if (response.error) {
                $('#sensitivity-content').html('<p class="placeholder">' + response.error + '</p>');
                return;
            }

            // Parse content
            const content = response.content;
            const separator = '='.repeat(60);
            const parts = content.split(separator);

            for (let i = 1; i < parts.length - 1; i += 2) {
                const name = parts[i].trim();
                if (name.startsWith(sensId + '_')) {
                    const csvData = parts[i + 1].trim();
                    const rows = csvData.split('\n').filter(row => row.trim() !== '');

                    if (rows.length === 0) {
                        $('#sensitivity-content').html('<p class="placeholder">No data available</p>');
                        return;
                    }

                    // Parse CSV properly (handle quoted values)
                    const headers = parseCSVLine(rows[0]);
                    const data = rows.slice(1).map(row => {
                        const values = parseCSVLine(row);
                        const obj = {};
                        headers.forEach((h, idx) => {
                            obj[h.trim()] = values[idx] ? values[idx].trim() : '';
                        });
                        return obj;
                    });

                    const tableHtml = '<table id="table-sensitivity" class="display"></table>';
                    $('#sensitivity-content').html(tableHtml);
                    const columns = headers.map(h => ({ title: h.trim(), data: h.trim() }));
                    initDataTable('table-sensitivity', data, columns);
                    return;
                }
            }

            $('#sensitivity-content').html('<p class="placeholder">No data found for this section</p>');
        });
    });

    // Helper function to parse CSV line (handle quoted values)
    function parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];

            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                result.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        result.push(current);

        return result;
    }

    // =========================================================================
    // DIAGNOSTICS
    // =========================================================================
    $('#btn-check-unused').click(function() {
        $('#diagnostics-content').html('<p class="placeholder">⏳ Loading...</p>');

        $.get('/api/reallocation/diagnostics/unused_variables', function(data) {
            if (data.error) {
                $('#diagnostics-content').html('<p class="placeholder">❌ ' + data.error + '</p>');
                return;
            }

            // Check if data has error/message columns
            if (data.length > 0 && (data[0].error || data[0].message)) {
                const msg = data[0].error || data[0].message;
                $('#diagnostics-content').html('<p class="placeholder">ℹ️ ' + msg + '</p>');
                return;
            }

            if (data.length === 0) {
                $('#diagnostics-content').html('<p class="placeholder">✅ All variables are used (non-zero)</p>');
                return;
            }

            const tableHtml = '<table id="table-diagnostics" class="display"></table>';
            $('#diagnostics-content').html(tableHtml);
            const columns = Object.keys(data[0]).map(k => ({ title: k, data: k }));
            initDataTable('table-diagnostics', data, columns);
        }).fail(function(xhr) {
            $('#diagnostics-content').html('<p class="placeholder">❌ Error: ' + (xhr.responseJSON?.error || 'Unknown error') + '</p>');
        });
    });

    $('#btn-check-violated').click(function() {
        $('#diagnostics-content').html('<p class="placeholder">⏳ Loading...</p>');

        $.get('/api/reallocation/diagnostics/violated_constraints', function(data) {
            if (data.error) {
                $('#diagnostics-content').html('<p class="placeholder">❌ ' + data.error + '</p>');
                return;
            }

            // Check if data has error/message columns
            if (data.length > 0 && (data[0].error || data[0].message)) {
                const msg = data[0].error || data[0].message;
                $('#diagnostics-content').html('<p class="placeholder">ℹ️ ' + msg + '</p>');
                return;
            }

            if (data.length === 0) {
                $('#diagnostics-content').html('<p class="placeholder">✅ No violated constraints (model is feasible)</p>');
                return;
            }

            const tableHtml = '<table id="table-diagnostics" class="display"></table>';
            $('#diagnostics-content').html(tableHtml);
            const columns = Object.keys(data[0]).map(k => ({ title: k, data: k }));
            initDataTable('table-diagnostics', data, columns);
        }).fail(function(xhr) {
            $('#diagnostics-content').html('<p class="placeholder">❌ Error: ' + (xhr.responseJSON?.error || 'Unknown error') + '</p>');
        });
    });

    $('#btn-export-lp').click(function() {
        // Open download link
        window.open('/api/reallocation/diagnostics/export_lp', '_blank');
    });

    // =========================================================================
    // AFTER EFFECT
    // =========================================================================
    function checkOptimizationStatus() {
        $.get('/api/after/check', function(response) {
            if (response.optimization_done) {
                $('#after-warning').hide();
                $('#after-content').show();
                loadAfterData();
            } else {
                $('#after-warning').show();
                $('#after-content').hide();
            }
        });
    }
    
    function loadAfterData() {
        const category = $('#category-filter-overview').val();

        // Load Store Profiles After
        $.get('/api/after/store_profiles', { category: category }, function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Diện tích',
                'Tổng Tồn', 'Tổng Nhu cầu', 'Tổng Nguồn cung',
                `Bán TB_${category}`, `MOH_${category}`, `MOH Rating_${category}`,
                `Tình trạng Gãy Size_${category}`, `SKC Limit_${category}`, `SKC Trưng bày_${category}`
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-profiles-after', data, columns);
        });

        // Load Warehouse Mã hàng After
        $.get('/api/after/warehouse_ma_hang', function(data) {
            if (data.error) return;
            const columns = Object.keys(data[0] || {}).map(k => ({ title: k, data: k }));
            initDataTable('table-wh-ma-hang-after', data, columns);
        });

        // Load Warehouse SKC After
        $.get('/api/after/warehouse', function(data) {
            if (data.error) return;
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 
                'Phân loại', 'Số Size', 'Tổng Tồn theo SKU'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-wh-skc-after', data, columns);
        });
    }

    // Load After Effect Store Mã hàng
    function loadMaHangAtStoreAfter(storeId) {
        $.get('/api/after/store_ma_hang/' + storeId, function(data) {
            if (data.error) {
                $('#table-ma-hang-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Phân loại', 'Tồn hiện tại',
                'Bán TB', 'Demand', 'Supply', 'MOH','MOH Rating', 'Broken Index'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-ma-hang-after', data, columns);
        }).fail(function(xhr) {
            console.error('Failed to load Mã hàng After:', xhr);
            $('#table-ma-hang-after').html(
                '<p class="placeholder">Error loading data: ' +
                (xhr.responseJSON?.error || 'Unknown error') + '</p>'
            );
        });
    }

    // Load After Effect Store SKC
    function loadSKCAtStoreAfter(storeId) {
        $.get('/api/after/store_skc/' + storeId, function(data) {
            if (data.error) {
                $('#table-skc-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Phân loại', 'Tồn hiện tại',
                'Số Size Có Tồn', 'Bán TB', 'Demand', 'Supply', 'MOH','MOH Rating',
                'Broken Index'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-skc-after', data, columns);
        }).fail(function(xhr) {
            console.error('Failed to load SKC After:', xhr);
            $('#table-skc-after').html(
                '<p class="placeholder">Error: ' +
                (xhr.responseJSON?.error || 'Failed to load data') + '</p>'
            );
        });
    }

    // Load After Effect Store SKU
    function loadSKUAtStoreAfter(storeId) {
        $.get('/api/after/store_sku/' + storeId, function(data) {
            if (data.error) {
                $('#table-sku-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size', 'SKU_ID', 'Phân loại',
                'Thuộc tính', 'Tồn hiện tại', 'Bán TB', 'Demand', 'Supply',
                'MOH','MOH Rating'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-sku-after', data, columns);
        }).fail(function(xhr) {
            console.error('Failed to load SKU After:', xhr);
            $('#table-sku-after').html(
                '<p class="placeholder">Error: ' +
                (xhr.responseJSON?.error || 'Failed to load data') + '</p>'
            );
        });
    }

    // Load After Effect Warehouse SKU
    function loadWarehouseSKUAfter(skc) {
        $.get('/api/after/warehouse_sku/' + skc, function(data) {
            if (data.error) {
                $('#table-wh-sku-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            // Check empty array
            if (!data || data.length === 0) {
                $('#table-wh-sku-after').html('<p class="placeholder">No data available for this SKC</p>');
                return;
            }

            const columnOrder = [
                'Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size', 'SKU_ID',
                'Phân loại', 'Thuộc tính', 'Tồn hiện tại',
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-wh-sku-after', data, columns);
        }).fail(function(xhr) {
            console.error('Failed to load Warehouse SKU After:', xhr);
            $('#table-wh-sku-after').html(
                '<p class="placeholder">Error: ' +
                (xhr.responseJSON?.error || 'Failed to load data') + '</p>'
            );
        });
    }

    // Load After Effect Broken by Store
    function loadBrokenByStoreAfter(storeId) {
        $.get('/api/after/broken_by_store/' + storeId, function(data) {
            if (data.error) {
                $('#table-broken-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            const columnOrder = [
                'Mã cửa hàng', 'Mã màu', 'Broken Index_before', 'Broken Index_after'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-broken-after', data, columns);
        });
    }

    // Load After Effect Broken by SKC
    function loadBrokenBySKCAfter(skc) {
        $.get('/api/after/broken_by_skc/' + skc, function(data) {
            if (data.error) {
                $('#table-broken-skc-after').html('<p class="placeholder">' + data.error + '</p>');
                return;
            }
            if (!data || data.length === 0) {
                $('#table-broken-skc-after').html('<p class="placeholder">No data available for this SKC</p>');
                return;
            }
            const columnOrder = [
                'Mã cửa hàng', 'Mã màu', 'Broken Index_before', 'Broken Index_after'
            ];

            const availableKeys = Object.keys(data[0] || {});
            const columns = columnOrder
                .filter(col => availableKeys.includes(col))
                .map(k => ({ title: k, data: k }));
            initDataTable('table-broken-skc-after', data, columns);
        });
    }
    
    // =========================================================================
    // EVENT HANDLERS
    // =========================================================================
    
    // Category filter change
    $('#category-filter-overview').change(function() {
        loadStoreProfiles();
        if ($('#after-content').is(':visible')) {
            loadAfterData();
        }
    });
    
    // Store ID inputs
    $('#store-id-skc').on('keypress', function(e) {
        if (e.which === 13) loadSKCAtStore($(this).val());
    });
    
    $('#store-id-sku').on('keypress', function(e) {
        if (e.which === 13) loadSKUAtStore($(this).val());
    });
    
    $('#store-id-broken').on('keypress', function(e) {
        if (e.which === 13) loadBrokenByStore($(this).val());
    });
    
    // Reference section input (Size Range + Top 3 Stores)
    $('#skc-input-reference').on('keypress', function(e) {
        if (e.which === 13) {
            const skc = $(this).val();
            console.log('Reference input - Loading SKC:', skc);
            loadReference(skc);
        }
    });

    // SKC inputs
    $('#skc-input-broken').on('keypress', function(e) {
        if (e.which === 13) loadBrokenBySKC($(this).val());
    });

    $('#skc-input-wh').on('keypress', function(e) {
        if (e.which === 13) loadWarehouseSKU($(this).val());
    });

    // Mã hàng inputs
    $('#store-id-ma-hang').on('keypress', function(e) {
        if (e.which === 13) loadMaHangAtStore($(this).val());
    });

    // Store filter for Broken by SKC
    $('#store-filter-broken').on('change', function() {
        const skc = $('#skc-input-broken').val();
        if (skc) {
            loadBrokenBySKC(skc);
        }
    });

    // After Effect inputs
    $('#store-id-ma-hang-after').on('keypress', function(e) {
        if (e.which === 13) loadMaHangAtStoreAfter($(this).val());
    });
    $('#store-id-skc-after').on('keypress', function(e) {
        if (e.which === 13) loadSKCAtStoreAfter($(this).val());
    });

    $('#store-id-sku-after').on('keypress', function(e) {
        if (e.which === 13) loadSKUAtStoreAfter($(this).val());
    });

    $('#skc-input-wh-after').on('keypress', function(e) {
        if (e.which === 13) loadWarehouseSKUAfter($(this).val());
    });

    $('#store-id-broken-after').on('keypress', function(e) {
        if (e.which === 13) loadBrokenByStoreAfter($(this).val());
    });

    $('#skc-input-broken-after').on('keypress', function(e) {
        if (e.which === 13) loadBrokenBySKCAfter($(this).val());
    });

    function updateDataStatus(loaded) {
        if (loaded) {
            $('#data-status').html('<span class="status-dot green"></span> Data loaded');
        } else {
            $('#data-status').html('<span class="status-dot red"></span> No data loaded');
        }
    }

    // =========================================================================
    // FILE UPLOAD
    // =========================================================================
    function checkDataStatus() {
        console.log('Checking data status...');
        $.get('/api/upload/status', function(response) {
            console.log('Status response:', response);
            updateDataStatus(response.has_data);
            if (response.has_data) {
                console.log('Data is loaded, loading tables...');
                // Load initial data for overview tab
                loadStoreProfiles();
                loadWarehouseMaHang();
                loadWarehouseSKC();
                // Load store list for Broken by SKC filter
                loadStoreList();
                // Load product filters (don't load data until filter selected)
                loadProductFilters('ma-hang');
                loadProductFilters('skc');
                loadProductFilters('sku');
            } else {
                console.log('No data loaded yet');
            }
        }).fail(function(xhr) {
            console.error('Failed to check status:', xhr);
        });
    }

    // File upload handler
    $('#store-files, #warehouse-files').change(function() {
        const storeFiles = $('#store-files')[0].files;
        const warehouseFiles = $('#warehouse-files')[0].files;

        console.log('Files selected - Store:', storeFiles.length, 'Warehouse:', warehouseFiles.length);

        if (storeFiles.length > 0 && warehouseFiles.length > 0) {
            uploadFiles();
        }
    });

    function uploadFiles() {
        const formData = new FormData();
        const storeFiles = $('#store-files')[0].files;
        const warehouseFiles = $('#warehouse-files')[0].files;
        const season = $('#season').val();

        console.log('Preparing upload...');
        console.log('Store files:', storeFiles.length);
        console.log('Warehouse files:', warehouseFiles.length);
        console.log('Season:', season);

        for (let i = 0; i < storeFiles.length; i++) {
            formData.append('store_files', storeFiles[i]);
            console.log('Added store file:', storeFiles[i].name);
        }
        for (let i = 0; i < warehouseFiles.length; i++) {
            formData.append('warehouse_files', warehouseFiles[i]);
            console.log('Added warehouse file:', warehouseFiles[i].name);
        }
        formData.append('season', season);

        $('#data-status').html('<span class="status-dot orange"></span> Uploading...');

        $.ajax({
            url: '/api/upload/files',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                console.log('Upload success:', response);
                updateDataStatus(true);
                alert('Files uploaded successfully!\n' +
                    'Stores: ' + response.stores + '\n' +
                    'Warehouse items: ' + response.warehouse_items + '\n' +
                    'Broken combinations: ' + response.broken_combinations);
                // Load data to overview section
                console.log('Loading overview data...');
                loadStoreProfiles();
                loadWarehouseMaHang();
                loadWarehouseSKC();
                // Load store list for filter
                loadStoreList();
                // Load product filters (don't load data until filter selected)
                loadProductFilters('ma-hang');
                loadProductFilters('skc');
                loadProductFilters('sku');
            },
            error: function(xhr) {
                console.error('Upload failed:', xhr);
                updateDataStatus(false);
                alert('Upload failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
            }
        });
    }

    // =========================================================================
    // CLEAR DATA
    // =========================================================================
    $('#btn-clear-data').click(function() {
        if (!confirm('Bạn có chắc muốn xóa tất cả dữ liệu và files đã upload?\nHành động này không thể hoàn tác.')) {
            return;
        }

        console.log('Clearing all data...');
        $('#data-status').html('<span class="status-dot orange"></span> Clearing...');

        $.ajax({
            url: '/api/upload/clear',
            method: 'POST',
            success: function(response) {
                console.log('Clear success:', response);
                updateDataStatus(false);
                alert('Đã xóa thành công!\nFiles deleted: ' + response.files_deleted);

                // Clear file inputs
                $('#store-files').val('');
                $('#warehouse-files').val('');

                // Reload page to clear all tables
                location.reload();
            },
            error: function(xhr) {
                console.error('Clear failed:', xhr);
                alert('Clear failed: ' + (xhr.responseJSON?.error || 'Unknown error'));
                checkDataStatus(); // Recheck status
            }
        });
    });

    // =========================================================================
    // PRODUCT OVERVIEW
    // =========================================================================

    /**
     * Load dropdown lists for filters (Mã hàng, Màu chi tiết)
     * @param {string} layer - 'skc' or 'sku'
     */
    function loadProductFilters(layer) {
        // Load Mã hàng list
        $.get('/api/product/ma_hang_list', function(data) {
            const select = $('#filter-ma-hang-' + layer);
            select.empty();
            select.append('<option value="all">Tất cả</option>');
            data.forEach(function(maHang) {
                select.append('<option value="' + maHang + '">' + maHang + '</option>');
            });
        });

        // Only initialize Màu chi tiết filter for SKC and SKU layers (not for ma-hang)
        if (layer === 'skc' || layer === 'sku') {
            updateMauChiTietList(layer, 'all');
        }

        // Initialize Size filter for SKU only
        if (layer === 'sku') {
            updateSizeList(layer, 'all', 'all');
        }

        // Load default data for this layer
        loadProductData(layer);
    }

    /**
     * Update Màu chi tiết dropdown based on Mã hàng
     */
    function updateMauChiTietList(layer, maHang) {
        const url = '/api/product/mau_list' + (maHang !== 'all' ? '?ma_hang=' + maHang : '');
        $.get(url, function(data) {
            const select = $('#filter-mau-chi-tiet-' + layer);
            select.empty();
            select.append('<option value="all">Tất cả</option>');
            data.forEach(function(mau) {
                select.append('<option value="' + mau + '">' + mau + '</option>');
            });
        });
    }

    /**
     * Update Size dropdown based on Mã hàng and Màu chi tiết
     */
    function updateSizeList(layer, maHang, mauChiTiet) {
        let url = '/api/product/size_list?';
        const params = [];
        if (maHang !== 'all') params.push('ma_hang=' + maHang);
        if (mauChiTiet !== 'all') params.push('mau_chi_tiet=' + mauChiTiet);
        url += params.join('&');

        $.get(url, function(data) {
            const select = $('#filter-size-' + layer);
            select.empty();
            select.append('<option value="all">Tất cả</option>');
            data.forEach(function(size) {
                select.append('<option value="' + size + '">' + size + '</option>');
            });
        });
    }

    /**
     * Load Product data for specific layer (Mã hàng, SKC or SKU)
     */
    function loadProductData(layer) {
        const maHang = $('#filter-ma-hang-' + layer).val() || 'all';
        const moh = $('#filter-moh-' + layer).val() || 'all';

        // Build endpoint URL based on layer
        let endpoint;
        if (layer === 'ma-hang') {
            endpoint = '/api/product/ma_hang';
        } else if (layer === 'skc') {
            endpoint = '/api/product/skc';
        } else {
            endpoint = '/api/product/sku';
        }

        let url = endpoint + '?';
        if (moh !== 'all') url += 'moh=' + moh;

        $.get(url, function(data) {
            if (data.error) {
                $('#table-product-' + layer).html('<p class="placeholder">' + data.error + '</p>');
                return;
            }

            // Filter data on frontend based on filters
            let filteredData = data;

            // Mã hàng filter (applies to all layers)
            if (maHang !== 'all') {
                filteredData = filteredData.filter(row => row['Mã hàng'] === maHang);
            }

            // Màu chi tiết filter (only for SKC and SKU, not for ma-hang)
            if (layer === 'skc' || layer === 'sku') {
                const mauChiTiet = $('#filter-mau-chi-tiet-' + layer).val() || 'all';
                if (mauChiTiet !== 'all') {
                    filteredData = filteredData.filter(row => row['Màu chi tiết'] === mauChiTiet);
                }
            }

            // Size filter (only for SKU)
            if (layer === 'sku') {
                const size = $('#filter-size-sku').val() || 'all';
                if (size !== 'all') {
                    filteredData = filteredData.filter(row => row['Size'] === size);
                }
            }

            if (filteredData.length === 0) {
                $('#table-product-' + layer).html('<p class="placeholder">Không có dữ liệu</p>');
                return;
            }

            // Định nghĩa thứ tự cột mong muốn theo layer
            let columnOrder;
            if (layer === 'skc') {
                columnOrder = [
                    'Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
                    'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
                    'TB Tình trạng Gãy Size', 'Số CH Gãy Size', 'Số Store'
                ];
            } else if (layer === 'sku') {
                columnOrder = [
                    'SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
                    'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB',
                    'MOH', 'MOH Rating', 'Demand', 'Supply', 'Số Store'
                ];
            } else {
                // ma-hang layer - keep current order
                columnOrder = ['Mã hàng', 'MOH', 'MOH Rating', 'Tồn hiện tại', 'Bán TB'];
            }

            const allKeys = Object.keys(filteredData[0]);
            const orderedKeys = columnOrder.filter(k => allKeys.includes(k));
            const remainingKeys = allKeys.filter(k => !columnOrder.includes(k));
            const finalKeys = [...orderedKeys, ...remainingKeys];
            const columns = finalKeys.map(k => ({ title: k, data: k }));

            initDataTable('table-product-' + layer, filteredData, columns);
        });
    }

    // Initialize filters and load data for all three layers on page load
    loadProductFilters('ma-hang');
    loadProductFilters('skc');
    loadProductFilters('sku');


    // Filter change handlers for SKC layer
    $('#filter-ma-hang-skc').on('change', function() {
        const maHang = $(this).val();
        updateMauChiTietList('skc', maHang);
        $('#filter-mau-chi-tiet-skc').val('all');
        loadProductData('skc');
    });

    $('#filter-mau-chi-tiet-skc').on('change', function() {
        loadProductData('skc');
    });

    $('#filter-moh-skc').on('change', function() {
        loadProductData('skc');
    });

    // Filter change handlers for Mã hàng layer
    $('#filter-ma-hang-ma-hang').on('change', function() {
        loadProductData('ma-hang');
    });

    $('#filter-moh-ma-hang').on('change', function() {
        loadProductData('ma-hang');
    });

    // Filter change handlers for SKU layer
    $('#filter-ma-hang-sku').on('change', function() {
        const maHang = $(this).val();
        updateMauChiTietList('sku', maHang);
        $('#filter-mau-chi-tiet-sku').val('all');
        
        // Update Size list based on new Mã hàng
        const mauChiTiet = $('#filter-mau-chi-tiet-sku').val() || 'all';
        updateSizeList('sku', maHang, mauChiTiet);
        $('#filter-size-sku').val('all');
        
        loadProductData('sku');
    });

    $('#filter-mau-chi-tiet-sku').on('change', function() {
        const maHang = $('#filter-ma-hang-sku').val() || 'all';
        const mauChiTiet = $(this).val();
        
        // Update Size list based on Mã hàng + Màu chi tiết
        updateSizeList('sku', maHang, mauChiTiet);
        $('#filter-size-sku').val('all');
        
        loadProductData('sku');
    });

    $('#filter-size-sku').on('change', function() {
        loadProductData('sku');
    });

    $('#filter-moh-sku').on('change', function() {
        loadProductData('sku');
    });

    // =========================================================================
    // EXPORT PRODUCT OVERVIEW SKU TO CSV
    // =========================================================================
//     $('#btn-export-sku-csv').click(function() {
//         // Get current filter values
//         const maHang = $('#filter-ma-hang-sku').val() || 'all';
//         const mauChiTiet = $('#filter-mau-chi-tiet-sku').val() || 'all';
//         const size = $('#filter-size-sku').val() || 'all';
//         const moh = $('#filter-moh-sku').val() || 'all';

//         // Build URL with query parameters
//         const params = new URLSearchParams({
//             ma_hang: maHang,
//             mau_chi_tiet: mauChiTiet,
//             size: size,
//             moh: moh
//         });

//         // Open download link in new tab
//         const exportUrl = '/api/product/export_sku_csv?' + params.toString();
//         window.open(exportUrl, '_blank');
//     });

});