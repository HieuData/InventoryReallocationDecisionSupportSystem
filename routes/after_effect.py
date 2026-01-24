from flask import Blueprint, request, jsonify, session
import pandas as pd
import sys
sys.path.insert(0, '.')
from core.data_processor import (
    calculate_broken_index_all, create_store_profiles,
    get_skc_at_store, get_sku_at_store,
    get_warehouse_skc,
    get_ma_hang_at_store, get_warehouse_ma_hang_available
)

bp = Blueprint('after_effect', __name__, url_prefix='/api/after')

@bp.route('/check')
def check():
    """Kiểm tra đã chạy optimization chưa"""
    done = session.get('optimization_done', False)
    return jsonify({'optimization_done': done})

@bp.route('/store_profiles')
def store_profiles_after():
    """Store profiles sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400
    
    category = request.args.get('category', 'Giày dép')
    
    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    
    # Recalculate broken và profiles
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)
    store_profiles_after = create_store_profiles(df_stores_after, df_broken_after)
    
    # Lấy profiles trước để so sánh
    store_profiles_before = pd.DataFrame(session['store_profiles'])
    
    # Merge thêm cột _after
    moh_col = f'MOH_{category}'
    rating_col = f'MOH Rating_{category}'
    
    result = store_profiles_after.copy()
    
    cols = ['Store ID', 'Cửa hàng', 'Vùng miền', 'Diện tích', 
            'Tổng Tồn', 'Tổng Nhu cầu', 'Tổng Nguồn cung', moh_col, rating_col,
            f'Broken Index_{category}', f'SKC Limit_{category}', f'SKC Trưng bày_{category}'
    ]
    cols = [c for c in cols if c in result.columns]

    # Đổi tên cột sang tiếng Việt trước khi trả về
    final = result[cols].rename(columns={
        'Store ID': 'Mã cửa hàng',
        f'Broken Index_{category}': f'Tình trạng Gãy Size_{category}'
    })

    return jsonify(final.to_dict('records'))

@bp.route('/warehouse')
def warehouse_after():
    """Warehouse SKC sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400
    
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    result = get_warehouse_skc(df_warehouse_after)  # ← Group by SKC
    return jsonify(result.to_dict('records'))

@bp.route('/broken')
def broken_after():
    """Broken index sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)

    # Merge với broken before
    df_broken_before = pd.DataFrame(session['df_broken'])

    result = df_broken_after.merge(
        df_broken_before[['Mã cửa hàng', 'Mã màu', 'Broken Index']],
        on=['Mã cửa hàng', 'Mã màu'],
        how='left',
        suffixes=('', '_before')
    )

    return jsonify(result.to_dict('records'))

@bp.route('/store_skc/<store_id>')
def store_skc_after(store_id):
    """SKC tại store sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_stores_before = pd.DataFrame(session['df_stores'])

    # Calculate broken for after state
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)

    # Calculate broken for before state
    df_warehouse_before = pd.DataFrame(session['df_warehouse'])
    df_broken_before = calculate_broken_index_all(df_stores_before, df_warehouse_before)

    result_after = get_skc_at_store(df_stores_after, df_broken_after, store_id)
    result_before = get_skc_at_store(df_stores_before, df_broken_before, store_id)

    # Merge before and after
    result = result_after

    return jsonify(result.to_dict('records'))

@bp.route('/store_sku/<store_id>')
def store_sku_after(store_id):
    """SKU tại store sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    result = get_sku_at_store(df_stores_after, store_id)
    return jsonify(result.to_dict('records'))

@bp.route('/warehouse_sku/<skc>')
def warehouse_sku_after(skc):
    """Warehouse SKU theo SKC sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])

    # Filter SKUs by SKC (Mã màu)
    result = df_warehouse_after[df_warehouse_after['Mã màu'] == skc].copy()

    if result.empty:
        return jsonify({'error': f'No SKU found for SKC: {skc}'}), 404

    # Select relevant columns
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size', 'Tồn hiện tại']
    cols = [c for c in cols if c in result.columns]
    result = result[cols]

    return jsonify(result.to_dict('records'))

@bp.route('/store_ma_hang/<store_id>')
def store_ma_hang_after(store_id):
    """Mã hàng tại store sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)

    result = get_ma_hang_at_store(df_stores_after, df_broken_after, store_id)
    return jsonify(result.to_dict('records'))

@bp.route('/warehouse_ma_hang')
def warehouse_ma_hang_after():
    """Warehouse Mã hàng sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    result = get_warehouse_ma_hang_available(df_warehouse_after)
    return jsonify(result.to_dict('records'))

@bp.route('/broken_by_store/<store_id>')
def broken_by_store_after(store_id):
    """Broken index by store sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)

    # Get broken before
    df_broken_before = pd.DataFrame(session['df_broken'])

    # Filter by store
    result_after = df_broken_after[df_broken_after['Mã cửa hàng'] == store_id]
    result_before = df_broken_before[df_broken_before['Mã cửa hàng'] == store_id]

    # Merge before and after
    if not result_before.empty and not result_after.empty:
        result = result_after.merge(
            result_before[['Mã màu', 'Broken Index']],
            on='Mã màu',
            how='left',
            suffixes=('_after', '_before')
        )

        # Reorder columns for frontend
        cols = ['Mã cửa hàng', 'Mã màu', 'Broken Index_before', 'Broken Index']
        cols = [c for c in cols if c in result.columns]
        remaining = [c for c in result.columns if c not in cols]
        cols.extend(remaining)
        result = result[cols]
    else:
        result = result_after

    return jsonify(result.to_dict('records'))

@bp.route('/broken_by_skc/<skc>')
def broken_by_skc_after(skc):
    """Broken index by SKC sau điều chuyển"""
    if not session.get('optimization_done'):
        return jsonify({'error': 'Run optimization first'}), 400

    df_stores_after = pd.DataFrame(session['df_stores_after'])
    df_warehouse_after = pd.DataFrame(session['df_warehouse_after'])
    df_broken_after = calculate_broken_index_all(df_stores_after, df_warehouse_after)

    # Get broken before
    df_broken_before = pd.DataFrame(session['df_broken'])
    df_stores_before = pd.DataFrame(session['df_stores'])

    # Filter by SKC
    result_after = df_broken_after[df_broken_after['Mã màu'] == skc]
    result_before = df_broken_before[df_broken_before['Mã màu'] == skc]

    # Merge before and after
    if not result_before.empty and not result_after.empty:
        result = result_after.merge(
            result_before[['Mã cửa hàng', 'Broken Index']],
            on='Mã cửa hàng',
            how='left',
            suffixes=('_after', '_before')
        )

        # Merge store info for display
        store_info = df_stores_before[['Mã cửa hàng', 'Cửa hàng', 'Vùng miền']].drop_duplicates()
        result = result.merge(store_info, on='Mã cửa hàng', how='left')

        # Reorder columns for frontend
        cols = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Mã màu',
                'Broken Index_before', 'Broken Index', 'Is Broken']
        cols = [c for c in cols if c in result.columns]
        remaining = [c for c in result.columns if c not in cols]
        cols.extend(remaining)
        result = result[cols]
    else:
        result = result_after

    return jsonify(result.to_dict('records'))