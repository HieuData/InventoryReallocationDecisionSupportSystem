from flask import Blueprint, render_template, request, jsonify, session, send_file
import pandas as pd
import sys
import os
from io import BytesIO
sys.path.insert(0, '.')
from core.data_processor import (
    create_system_skc_profiles, create_system_sku_profiles, create_system_ma_hang_profiles,
    create_location_skc_profiles, create_location_sku_profiles, create_location_ma_hang_profiles
)

bp = Blueprint('product', __name__, url_prefix='/api/product')

def moh_filter(df, moh_range):
    """Apply MOH filter to the DataFrame based on the specified range."""
    if moh_range != 'all':
        if moh_range == '0-1.5':
            df = df[(df['MOH'] >= 0) & (df['MOH'] < 1.5)]
        elif moh_range == '1.5-2.5':
            df = df[(df['MOH'] >= 1.5) & (df['MOH'] < 2.5)]
        elif moh_range == '2.5-3.6':
            df = df[(df['MOH'] >= 2.5) & (df['MOH'] < 3.6)]
        elif moh_range == '3.6-max':
            df = df[df['MOH'] >= 3.6]
    return df

@bp.route('/skc')
def get_product_skc():
    """Get SKC (Style-Color) level product data"""
    if 'df_stores' not in session or 'df_warehouse' not in session or 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_system_skc_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse']),
        pd.DataFrame(session['df_broken'])
    )

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    # Đổi tên cột sang tiếng Việt
    df = df.rename(columns={
        'Avg Broken Index': 'Tình trạng Gãy Size TB',
        'Stores Broken': 'Số CH Gãy Size'
    })

    return jsonify(df.to_dict('records'))

@bp.route('/sku')
def get_product_sku():
    """Get SKU (Stock Keeping Unit) level product data"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_system_sku_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse'])
    )

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    return jsonify(df.to_dict('records'))

@bp.route('/ma_hang')
def get_product_ma_hang():
    """Get Mã hàng level product data"""
    if 'df_stores' not in session or 'df_warehouse' not in session or 'df_broken' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_system_ma_hang_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse']),
        pd.DataFrame(session['df_broken'])
    )

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    # Đổi tên cột sang tiếng Việt
    df = df.rename(columns={
        'Avg Broken Index': 'Tình trạng Gãy Size TB'
    })

    return jsonify(df.to_dict('records'))

@bp.route('/location_skc')
def get_location_product_skc():
    """Get SKC level product data by location"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_location_skc_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse'])
    )

    # Apply location filter if specified
    location = request.args.get('location', 'all')
    if location != 'all':
        df = df[df['Mã cửa hàng'] == location]

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    return jsonify(df.to_dict('records'))

@bp.route('/location_sku')
def get_location_product_sku():
    """Get SKU level product data by location"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_location_sku_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse'])
    )

    # Apply location filter if specified
    location = request.args.get('location', 'all')
    if location != 'all':
        df = df[df['Mã cửa hàng'] == location]

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    return jsonify(df.to_dict('records'))

@bp.route('/location_ma_hang')
def get_location_product_ma_hang():
    """Get Mã hàng level product data by location"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df = create_location_ma_hang_profiles(
        pd.DataFrame(session['df_stores']),
        pd.DataFrame(session['df_warehouse'])
    )

    # Apply location filter if specified
    location = request.args.get('location', 'all')
    if location != 'all':
        df = df[df['Mã cửa hàng'] == location]

    # Apply MOH filter if specified
    moh_range = request.args.get('moh', 'all')
    df = moh_filter(df, moh_range)

    return jsonify(df.to_dict('records'))

@bp.route('/location_list')
def get_location_list():
    """Get list of all locations (stores + warehouse) with optional product filtering"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_warehouse = pd.DataFrame(session['df_warehouse'])

    # Optional filters
    ma_hang = request.args.get('ma_hang', 'all')
    mau_chi_tiet = request.args.get('mau_chi_tiet', 'all')
    size = request.args.get('size', 'all')

    # Filter stores
    df_s = df_stores
    if ma_hang != 'all':
        df_s = df_s[df_s['Mã hàng'] == ma_hang]
    if mau_chi_tiet != 'all':
        df_s = df_s[df_s['Màu chi tiết'] == mau_chi_tiet]
    if size != 'all':
        df_s = df_s[df_s['Size'] == size]

    # Filter warehouse
    df_w = df_warehouse
    if ma_hang != 'all':
        df_w = df_w[df_w['Mã hàng'] == ma_hang]
    if mau_chi_tiet != 'all':
        df_w = df_w[df_w['Màu chi tiết'] == mau_chi_tiet]
    if size != 'all':
        df_w = df_w[df_w['Size'] == size]

    # Get unique store codes from filtered stores
    store_list = sorted(df_s['Mã cửa hàng'].unique().tolist())
    
    # Check if warehouse has the item
    location_list = store_list
    if not df_w.empty and (df_w['Tồn hiện tại'] > 0).any():
        location_list = location_list + ['Kho']

    return jsonify(location_list)

@bp.route('/ma_hang_list')
def get_ma_hang_list():
    """Get list of all Mã hàng"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_warehouse = pd.DataFrame(session['df_warehouse'])

    # Gộp stores + warehouse để lấy tất cả Mã hàng
    ma_hang_stores = set(df_stores['Mã hàng'].unique())
    ma_hang_warehouse = set(df_warehouse['Mã hàng'].unique())
    ma_hang_list = sorted(ma_hang_stores | ma_hang_warehouse)

    return jsonify(ma_hang_list)

@bp.route('/mau_list')
def get_mau_list():
    """Get list of Màu chi tiết, optionally filtered by Mã hàng"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_warehouse = pd.DataFrame(session['df_warehouse'])
    ma_hang = request.args.get('ma_hang', 'all')

    # Filter stores
    if ma_hang != 'all':
        df_stores_filtered = df_stores[df_stores['Mã hàng'] == ma_hang]
        df_warehouse_filtered = df_warehouse[df_warehouse['Mã hàng'] == ma_hang]
    else:
        df_stores_filtered = df_stores
        df_warehouse_filtered = df_warehouse

    # Gộp stores + warehouse để lấy tất cả Màu chi tiết
    mau_stores = set(df_stores_filtered['Màu chi tiết'].unique())
    mau_warehouse = set(df_warehouse_filtered['Màu chi tiết'].unique())
    mau_list = sorted(mau_stores | mau_warehouse)

    return jsonify(mau_list)

@bp.route('/size_list')
def get_size_list():
    """Get list of sizes, optionally filtered by Mã hàng and Màu chi tiết"""
    if 'df_stores' not in session or 'df_warehouse' not in session:
        return jsonify({'error': 'No data loaded'}), 400

    df_stores = pd.DataFrame(session['df_stores'])
    df_warehouse = pd.DataFrame(session['df_warehouse'])
    ma_hang = request.args.get('ma_hang', 'all')
    mau_chi_tiet = request.args.get('mau_chi_tiet', 'all')

    # Filter stores
    df_stores_filtered = df_stores
    df_warehouse_filtered = df_warehouse

    if ma_hang != 'all':
        df_stores_filtered = df_stores_filtered[df_stores_filtered['Mã hàng'] == ma_hang]
        df_warehouse_filtered = df_warehouse_filtered[df_warehouse_filtered['Mã hàng'] == ma_hang]

    if mau_chi_tiet != 'all':
        df_stores_filtered = df_stores_filtered[df_stores_filtered['Màu chi tiết'] == mau_chi_tiet]
        df_warehouse_filtered = df_warehouse_filtered[df_warehouse_filtered['Màu chi tiết'] == mau_chi_tiet]

    # Gộp stores + warehouse để lấy tất cả Size
    size_stores = set(df_stores_filtered['Size'].unique())
    size_warehouse = set(df_warehouse_filtered['Size'].unique())
    size_list = sorted(size_stores | size_warehouse)

    return jsonify(size_list)

# @bp.route('/export_sku_csv')
# def export_sku_csv():
#     """Export Product Overview SKU layer data to CSV"""
#     if 'df_stores' not in session:
#         return jsonify({'error': 'No data loaded'}), 400

#     try:
#         # Create SKU profiles
#         df = create_system_sku_profiles(
#             pd.DataFrame(session['df_stores'])
#         )

#         # Apply filters from request args
#         ma_hang = request.args.get('ma_hang', 'all')
#         mau_chi_tiet = request.args.get('mau_chi_tiet', 'all')
#         size = request.args.get('size', 'all')
#         moh_range = request.args.get('moh', 'all')

#         # Filter by Mã hàng
#         if ma_hang != 'all':
#             df = df[df['Mã hàng'] == ma_hang]

#         # Filter by Màu chi tiết
#         if mau_chi_tiet != 'all':
#             df = df[df['Màu chi tiết'] == mau_chi_tiet]

#         # Filter by Size
#         if size != 'all':
#             df = df[df['Size'] == size]

#         # Filter by MOH
#         df = moh_filter(df, moh_range)

#         # Create CSV in memory
#         output = BytesIO()
#         df.to_csv(output, index=False, encoding='utf-8-sig')
#         output.seek(0)

#         # Generate filename based on filters
#         filename_parts = ['product_overview_sku']
#         if ma_hang != 'all':
#             filename_parts.append(f'ma_{ma_hang}')
#         if mau_chi_tiet != 'all':
#             filename_parts.append(f'mau_{mau_chi_tiet}')
#         if size != 'all':
#             filename_parts.append(f'size_{size}')
#         if moh_range != 'all':
#             filename_parts.append(f'moh_{moh_range}')

#         filename = '_'.join(filename_parts) + '.csv'

#         return send_file(
#             output,
#             mimetype='text/csv',
#             as_attachment=True,
#             download_name=filename
#         )

#     except Exception as e:
#         print(f"Error exporting SKU CSV: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': str(e)}), 500
