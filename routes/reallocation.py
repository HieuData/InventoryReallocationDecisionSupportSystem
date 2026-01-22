from flask import Blueprint, render_template, request, jsonify, session
import os
import sys
sys.path.insert(0, '.')
from services.optimization_service import run_optimization, calculate_after_state
from core.data_processor import (
    load_single_file, concat_files,
    calculate_broken_index_all, create_store_profiles
)

bp = Blueprint('reallocation', __name__, url_prefix='/api/reallocation')

@bp.route('/run', methods=['POST'])
def run():
    """Chạy optimization"""
    # Kiểm tra dữ liệu đã được upload chưa
    if 'store_files' not in session or 'warehouse_files' not in session:
        return jsonify({'error': 'No data loaded. Please upload CSV files first.'}), 400

    data = request.json
    store_files = session['store_files']
    warehouse_files = session['warehouse_files']
    time_limit = data.get('time_limit', 300)
    gap = data.get('gap', 0.05)
    season = data.get('season', False)

    try:
        output_dir = './output'
        os.makedirs(output_dir, exist_ok=True)

        result = run_optimization(
            store_files=store_files,
            warehouse_files=warehouse_files,
            output_dir=output_dir,
            time_limit=time_limit,
            gap=gap,
            season=season
        )

        # Cập nhật session với kết quả mới
        session['df_stores'] = result['data']['df_stores'].to_dict('records')
        session['df_warehouse'] = result['data']['df_warehouse'].to_dict('records')
        session['df_broken'] = result['data']['df_broken'].to_dict('records')
        session['store_profiles'] = result['data']['store_profiles'].to_dict('records')
        session['reallocation_plan'] = result['reallocation_plan'].to_dict('records')
        session['summary'] = result['summary']

        # Tính after state
        after = calculate_after_state(
            result['data']['df_stores'],
            result['data']['df_warehouse'],
            result['reallocation_plan']
        )
        session['df_stores_after'] = after['df_stores_after'].to_dict('records')
        session['df_warehouse_after'] = after['df_warehouse_after'].to_dict('records')
        session['optimization_done'] = True

        return jsonify({
            'status': 'success',
            'summary': result['summary']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/plan')
def plan():
    """Lấy reallocation plan"""
    if 'reallocation_plan' not in session:
        return jsonify({'error': 'No optimization result'}), 400
    
    return jsonify(session['reallocation_plan'])

@bp.route('/summary')
def summary():
    """Lấy summary"""
    if 'summary' not in session:
        return jsonify({'error': 'No optimization result'}), 400
    
    return jsonify(session['summary'])

@bp.route('/sensitivity')
def sensitivity():
    """Lấy sensitivity report"""
    report_path = './output/sensitivity_report.csv'
    if not os.path.exists(report_path):
        return jsonify({'error': 'No sensitivity report'}), 400

    with open(report_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    return jsonify({'content': content})

@bp.route('/diagnostics/unused_variables')
def unused_variables():
    """Kiểm tra biến không sử dụng"""
    import pandas as pd

    file_path = './output/diagnostic_unused_vars.csv'

    if not os.path.exists(file_path):
        return jsonify({'error': 'No diagnostic data. Run optimization first.'}), 400

    df = pd.read_csv(file_path, encoding='utf-8-sig')

    return jsonify(df.to_dict('records'))

@bp.route('/diagnostics/violated_constraints')
def violated_constraints():
    """Kiểm tra ràng buộc bị vi phạm"""
    import pandas as pd

    file_path = './output/diagnostic_violated_constraints.csv'

    if not os.path.exists(file_path):
        return jsonify({'error': 'No diagnostic data. Run optimization first.'}), 400

    df = pd.read_csv(file_path, encoding='utf-8-sig')

    return jsonify(df.to_dict('records'))

@bp.route('/diagnostics/export_lp')
def export_lp():
    """Export mô hình LP"""
    lp_path = './output/model.lp'

    if not os.path.exists(lp_path):
        return jsonify({'error': 'No LP model file found. Run optimization first.'}), 400

    # Return file for download
    from flask import send_file
    return send_file(lp_path, as_attachment=True, download_name='model.lp')

# ====================================================================================
# AUDIT ENDPOINTS
# ====================================================================================

@bp.route('/audit/warehouse_transfers')
def warehouse_transfers():
    """Điều chuyển từ kho với merged data"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    import pandas as pd

    # Get data from session
    realloc_plan = pd.DataFrame(session['reallocation_plan'])
    df_warehouse = pd.DataFrame(session['df_warehouse'])
    df_stores = pd.DataFrame(session['df_stores'])

    # Filter warehouse transfers
    wh_transfers = realloc_plan[realloc_plan['Loại'] == 'Chuyển từ kho'].copy()

    if wh_transfers.empty:
        return jsonify([])

    # Drop Loại column
    wh_transfers = wh_transfers.drop(columns=['Loại'])

    # Merge warehouse stock
    wh_transfers = wh_transfers.merge(
        df_warehouse[['SKU_ID', 'Tồn hiện tại']],
        on='SKU_ID',
        how='left',
        suffixes=('', '_Kho')
    )

    # Merge destination store data
    dest_data = df_stores[['Mã cửa hàng', 'SKU_ID', 'Demand', 'SKC Limit', 'SKC Trưng bày']].copy()
    wh_transfers = wh_transfers.merge(
        dest_data,
        left_on=['Đích', 'SKU_ID'],
        right_on=['Mã cửa hàng', 'SKU_ID'],
        how='left',
        suffixes=('', '_Đích')
    ).drop(columns=['Mã cửa hàng'], errors='ignore')

    # Calculate Số SKC nhận
    skc_count = wh_transfers.groupby('Đích')['SKC'].nunique().rename('Số SKC nhận')
    wh_transfers = wh_transfers.merge(skc_count, left_on='Đích', right_index=True, how='left')

    wh_transfers = wh_transfers.rename(columns={
        'Số lượng': 'Số lượng điều chuyển',
        'Tồn hiện tại': 'Tồn tại Kho',
        'Demand': 'Demand Đích',
        'SKC Limit': 'SKC Limit tại Đích',
        'SKC Trưng bày': 'SKC Trưng bày tại Đích',
        'Số SKC nhận': 'Số SKC Đích nhận'
    })
    # Reorder columns
    cols = ['Nguồn', 'Vùng miền Nguồn', 'Đích', 'Vùng miền Đích',
            'SKU_ID', 'SKC', 'Thuộc tính', 'Số lượng điều chuyển',
            'Tồn tại Kho', 'Demand Đích', 'SKC Limit tại Đích', 
            'SKC Trưng bày tại Đích', 'Số SKC Đích nhận'
    ]
    cols = [c for c in cols if c in wh_transfers.columns]
    wh_transfers = wh_transfers[cols]

    return jsonify(wh_transfers.to_dict('records'))


@bp.route('/audit/store_transfers')
def store_transfers():
    """Điều chuyển từ cửa hàng với merged data"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    import pandas as pd

    realloc_plan = pd.DataFrame(session['reallocation_plan'])
    df_stores = pd.DataFrame(session['df_stores'])

    # Filter store-to-store transfers
    store_transfers = realloc_plan[realloc_plan['Loại'] == 'Chuyển cửa hàng'].copy()

    if store_transfers.empty:
        return jsonify([])

    store_transfers = store_transfers.drop(columns=['Loại'])

    # Merge source store data
    source_data = df_stores[['Mã cửa hàng', 'SKU_ID', 'Supply', 'MOH']].copy()
    store_transfers = store_transfers.merge(
        source_data,
        left_on=['Nguồn', 'SKU_ID'],
        right_on=['Mã cửa hàng', 'SKU_ID'],
        how='left',
        suffixes=('', '_Nguồn')
    ).drop(columns=['Mã cửa hàng'], errors='ignore')

    # Merge destination store data
    dest_data = df_stores[['Mã cửa hàng', 'SKU_ID', 'Demand', 'SKC Limit', 'SKC Trưng bày']].copy()
    store_transfers = store_transfers.merge(
        dest_data,
        left_on=['Đích', 'SKU_ID'],
        right_on=['Mã cửa hàng', 'SKU_ID'],
        how='left',
        suffixes=('', '_Đích')
    ).drop(columns=['Mã cửa hàng'], errors='ignore')

    # Calculate Số SKC nhận
    skc_count = store_transfers.groupby('Đích')['SKC'].nunique().rename('Số SKC nhận')
    store_transfers = store_transfers.merge(skc_count, left_on='Đích', right_index=True, how='left')

    store_transfers = store_transfers.rename(columns={
        'Số lượng': 'Số lượng điều chuyển',
        'Supply': 'Supply Nguồn',
        'MOH': 'MOH tại Nguồn',
        'Demand': 'Demand Đích',
        'SKC Limit': 'SKC Limit tại Đích',
        'SKC Trưng bày': 'SKC Trưng bày tại Đích',
        'Số SKC nhận': 'Số SKC Đích nhận'
    })
    # Reorder columns
    cols = ['Nguồn', 'Vùng miền Nguồn', 'Supply Nguồn', 'MOH tại Nguồn',
            'Đích', 'Vùng miền Đích', 'Demand Đích', 
            'SKC Limit tại Đích', 'SKC Trưng bày tại Đích',
            'SKU_ID', 'SKC', 'Thuộc tính', 'Số lượng điều chuyển', 'Số SKC Đích nhận'
    ]
    cols = [c for c in cols if c in store_transfers.columns]
    store_transfers = store_transfers[cols]

    return jsonify(store_transfers.to_dict('records'))


@bp.route('/audit/source_destinations')
def source_destinations():
    """Số đích đến của mỗi nguồn (excluding warehouse)"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    import pandas as pd

    realloc_plan = pd.DataFrame(session['reallocation_plan'])

    # Filter out warehouse sources
    store_sources = realloc_plan[realloc_plan['Nguồn'] != 'Kho'].copy()

    if store_sources.empty:
        return jsonify([])

    # Group by source, count unique destinations
    result = store_sources.groupby('Nguồn').agg({
        'Đích': 'nunique'
    }).reset_index()

    result.columns = ['Nguồn', 'Số Đích đến']
    result = result.sort_values('Số Đích đến', ascending=False)

    return jsonify(result.to_dict('records'))


@bp.route('/audit/destination_sources')
def destination_sources():
    """Số nguồn nhận của mỗi đích"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    import pandas as pd

    realloc_plan = pd.DataFrame(session['reallocation_plan'])

    # Group by destination, count unique sources
    result = realloc_plan.groupby('Đích').agg({
        'Nguồn': 'nunique'
    }).reset_index()

    result.columns = ['Đích', 'Số Nguồn Nhận']
    result = result.sort_values('Số Nguồn Nhận', ascending=False)

    return jsonify(result.to_dict('records'))