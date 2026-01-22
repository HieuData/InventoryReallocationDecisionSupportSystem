from flask import Blueprint, render_template, request, jsonify, session
import pandas as pd
import sys
sys.path.insert(0, '.')
from core.data_processor import (
    get_stores_by_sales, get_skc_at_store, get_sku_at_store,
    get_warehouse_sku_available, get_ma_hang_at_store,
    get_warehouse_ma_hang_available, get_warehouse_skc
)

bp = Blueprint('overview', __name__, url_prefix='/api/overview')

@bp.route('/store_profiles')
def store_profiles():
    """Layer 1: Store profiles"""
    if 'store_profiles' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    category = request.args.get('category', 'Giày dép')
    df = pd.DataFrame(session['store_profiles'])

    cols = ['Store ID', 'Cửa hàng', 'Vùng miền', 'Diện tích',
            'Tổng Tồn', 'Tổng Nhu cầu', 'Tổng Nguồn cung',
            f'Bán TB_{category}', f'MOH_{category}', f'MOH Rating_{category}',
            f'Broken Index_{category}', f'SKC Limit_{category}', f'SKC Trưng bày_{category}']

    cols = [c for c in cols if c in df.columns]

    # Đổi tên cột sang tiếng Việt trước khi trả về
    result = df[cols].rename(columns={
        'Store ID': 'Mã cửa hàng',
        f'Broken Index_{category}': f'Tình trạng Gãy Size_{category}'
    })

    return jsonify(result.to_dict('records'))

@bp.route('/store_skc/<store_id>')
def store_skc(store_id):
    """Layer 2: SKC tại store"""
    if 'df_stores' not in session or 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_broken = pd.DataFrame(session['df_broken'])
    result = get_skc_at_store(df_stores, df_broken, store_id)

    # Đổi tên cột sang tiếng Việt
    result = result.rename(columns={
        'Broken Index': 'Tình trạng Gãy Size',
        'Is Broken': 'Gãy Size'
    })

    return jsonify(result.to_dict('records'))

@bp.route('/store_sku/<store_id>')
def store_sku(store_id):
    """Layer 3: SKU tại store"""
    if 'df_stores' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    result = get_sku_at_store(df_stores, store_id)
    return jsonify(result.to_dict('records'))

@bp.route('/warehouse_skc')
def warehouse_skc():
    """Warehouse Layer 1: SKC"""
    if 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_warehouse = pd.DataFrame(session['df_warehouse'])
    result = get_warehouse_skc(df_warehouse)

    return jsonify(result.to_dict('records'))

@bp.route('/warehouse_sku/<skc>')
def warehouse_sku(skc):
    """Warehouse Layer 2: SKU theo SKC"""
    if 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_warehouse = pd.DataFrame(session['df_warehouse'])

    # Filter SKUs by SKC (Mã màu)
    result = df_warehouse[df_warehouse['Mã màu'] == skc].copy()

    if result.empty:
        return jsonify([])

    # Select relevant columns
    cols = [
        'SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size', 'Phân loại', 'Thuộc tính', 'Tồn hiện tại'
    ]
    cols = [c for c in cols if c in result.columns]
    result = result[cols]

    return jsonify(result.to_dict('records'))

@bp.route('/store_ma_hang/<store_id>')
def store_ma_hang(store_id):
    """Layer 2: Mã hàng tại store"""
    if 'df_stores' not in session or 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_broken = pd.DataFrame(session['df_broken'])
    result = get_ma_hang_at_store(df_stores, df_broken, store_id)

    # Đổi tên cột sang tiếng Việt
    result = result.rename(columns={'Broken Index': 'Tình trạng Gãy Size'})

    return jsonify(result.to_dict('records'))

@bp.route('/warehouse_ma_hang')
def warehouse_ma_hang():
    """Warehouse Layer 1: Mã hàng"""
    if 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_warehouse = pd.DataFrame(session['df_warehouse'])
    result = get_warehouse_ma_hang_available(df_warehouse)
    return jsonify(result.to_dict('records'))