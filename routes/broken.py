from flask import Blueprint, render_template, request, jsonify, session
import pandas as pd
import sys
sys.path.insert(0, '.')
from core.data_processor import (
    get_broken_by_store, get_broken_by_skc, get_skc_at_store,
    get_warehouse_size_range, get_top_stores_by_category,
    get_broken_sku_at_store
)
from config.settings import CATEGORY_MAP

bp = Blueprint('broken', __name__, url_prefix='/api/broken')

@bp.route('/by_store/<store_id>')
def by_store(store_id):
    """Bảng 2 Layer 1: Broken by store"""
    if 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_broken = pd.DataFrame(session['df_broken'])
    result = get_broken_by_store(df_broken, store_id)

    # Đổi tên cột sang tiếng Việt
    result = result.rename(columns={
        'Broken Index': 'Tình trạng Gãy Size',
        'Is Broken': 'Gãy Size'
    })

    return jsonify(result.to_dict('records'))

@bp.route('/skc_at_store/<store_id>')
def skc_at_store(store_id):
    """Bảng 2 Layer 2: SKC detail tại store"""
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

@bp.route('/by_skc/<skc>')
def by_skc(skc):
    """Bảng 3: Broken by SKC"""
    if 'df_broken' not in session or 'df_stores' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_broken = pd.DataFrame(session['df_broken'])
    df_stores = pd.DataFrame(session['df_stores'])
    result = get_broken_by_skc(df_broken, df_stores, skc)

    # Đổi tên cột sang tiếng Việt
    result = result.rename(columns={
        'Broken Index': 'Tình trạng Gãy Size',
        'Is Broken': 'Gãy Size'
    })

    return jsonify(result.to_dict('records'))

@bp.route('/size_range/<skc>')
def size_range(skc):
    """Bảng 1 nửa trên: Dải size chuẩn từ kho"""
    if 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_warehouse = pd.DataFrame(session['df_warehouse'])
    result = get_warehouse_size_range(df_warehouse, skc)

    # Convert numpy types to Python native types for JSON serialization
    def convert_to_native(obj):
        if hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        elif isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        return obj

    result = convert_to_native(result)
    return jsonify(result)

@bp.route('/top_stores/<skc>')
def top_stores(skc):
    """Bảng 1 nửa dưới: Top 3 store bán chạy theo category của SKC"""
    if 'store_profiles' not in session or 'df_stores' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    # Lấy category từ SKC (ký tự đầu)
    first_char = skc[0] if skc else ''
    category = CATEGORY_MAP.get(first_char, 'Giày dép')

    store_profiles = pd.DataFrame(session['store_profiles'])
    result = get_top_stores_by_category(store_profiles, category, top_n=3)
    print(result)
    # Đổi tên cột sang tiếng Việt
    result = result.rename(columns={
        'Store ID': 'Mã cửa hàng'
    })

    return jsonify(result.to_dict('records'))

@bp.route('/sku_at_store/<skc>/<store_id>')
def sku_at_store(skc, store_id):
    """Lấy SKU broken của SKC tại một store cụ thể"""
    if 'df_stores' not in session or 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_broken = pd.DataFrame(session['df_broken'])
    result = get_broken_sku_at_store(df_stores, df_broken, skc, store_id)

    if result.empty:
        return jsonify([])

    return jsonify(result.to_dict('records'))

@bp.route('/store_list')
def store_list():
    """Lấy danh sách tất cả các store"""
    if 'df_stores' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    stores = df_stores[['Mã cửa hàng', 'Cửa hàng']].drop_duplicates()
    stores = stores.sort_values('Mã cửa hàng')
    return jsonify(stores.to_dict('records'))