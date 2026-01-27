"""
Data Processing Module
Xử lý dữ liệu đầu vào từ file CSV và tính toán các chỉ số kinh doanh.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import unicodedata
import re
from config.settings import (
    SALES_COLS, SALES_LY_COLS,
    MOH_THRESHOLD_LOW, MOH_THRESHOLD_HIGH, MOH_TARGET,
    BROKEN_THRESHOLD, 
    CATEGORY_MAP
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Xử lý tiếng Việt có dấu
def norm_text(text):
    """
    Chuyển đổi tiếng Việt có dấu thành không dấu, giữ lại chữ đ/Đ.
    Ví dụ: "Áo Đỏ" -> "Ao Đo"
    """
    if not isinstance(text, str): # Kiểm tra nếu không phải chuỗi (ví dụ: NaN, số)
        return str(text) if pd.notna(text) else ""

    # Chuẩn hóa NFD để tách dấu
    text_nfd = unicodedata.normalize('NFD', text)
    # Regex loại bỏ dấu (giữ lại ký tự gốc bao gồm cả đ/Đ vì đ không nằm trong dải dấu này)
    text_without_accent = re.sub(r'[\u0300-\u036f]', '', text_nfd)
    # Đưa về dạng NFC chuẩn
    return unicodedata.normalize('NFC', text_without_accent)


# =============================================================================
# DATA LOADING FUNCTIONS
# =============================================================================

def load_single_file(filepath: str, file_type: str = 'store', season: Optional[bool] = None) -> pd.DataFrame:
    """
    Đọc một file CSV và thực hiện tiền xử lý cơ bản.
    
    Args:
        filepath: Đường dẫn file CSV
        file_type: 'store' hoặc 'warehouse'
    
    Returns:
        DataFrame đã được tiền xử lý
    """
    # print(season)
    df = pd.read_csv(filepath)
    
    # Xác định loại hàng dựa vào ký tự đầu của Mã hàng
    df['Mã hàng'] = df['Mã hàng'].astype(str)
    df['Mã màu'] = df['Mã màu'].astype(str)
    df['Phân loại'] = df['Mã hàng'].str[0].map(CATEGORY_MAP).fillna('Khác')
    
    # Kiểm tra và xử lý file phụ kiện (có cột 'Loại phụ kiện', không có Size)
    detected_accessory = 'Loại phụ kiện' in df.columns
    
    if detected_accessory:
        df = df.drop('Loại phụ kiện', axis=1, errors='ignore')
        if 'Size' not in df.columns:
            df.insert(
                loc=df.columns.get_loc('Màu chi tiết') + 1,
                column='Size',
                value='0'
            )
    
    # Đảm bảo kiểu dữ liệu
    df['Size'] = df['Size'].astype(str)
    
    # Xử lý riêng cho store vs warehouse
    if file_type == 'store' and detected_accessory:
        # Nếu caller không truyền `season`, dùng giá trị phát hiện từ file (detected_accessory)
        season = season if season is not None else detected_accessory
        df = _process_store_file(df, season)
    elif file_type == 'store':
        df = _process_store_file(df)
    else:
        df = _process_warehouse_file(df)
    
    return df


def _process_store_file(df: pd.DataFrame, season: Optional[bool] = None) -> pd.DataFrame:
    """Xử lý file cửa hàng - tính các chỉ số kinh doanh.

    Trước khi tính toán, gộp (group) dữ liệu theo tổ hợp `Mã hàng`,
    `Màu chi tiết`, `Size`. Với các cột có thể tổng hợp (numeric hoặc có
    các từ khóa như 'Bán', 'Tồn', 'Demand', 'Supply') sẽ lấy `sum`,
    các cột khác giữ giá trị `first`.
    """
    # --- Group/aggregate by composite key first ---
    group_cols = [
        c for c in ['Mã hàng', 'Màu chi tiết', 'Mã màu', 'Size', 'Thuộc tính', 'Mã cửa hàng'] if c in df.columns
    ]
    if group_cols:
        agg_dict = {}
        for col in df.columns:
            if col in group_cols:
                continue
            # Heuristic: numeric columns or columns containing keywords should be summed
            if col.startswith(('Tồn', 'Bán')):
                agg_dict[col] = 'sum'
            elif 'SKC Limit' in col or 'SKC Trưng bày' in col:
                agg_dict[col] = 'max'
            else:
                agg_dict[col] = 'first'

        # Only perform groupby if there is something to aggregate
        if agg_dict:
            df = df.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()

    # Tính bán trung bình
    # Nếu season=True, dùng cột năm trước (mùa vụ/phụ kiện), ngược lại dùng cột bán hiện tại
    if season and df['Phân loại'].iloc[0] == 'Phụ kiện':
        # Kiểm tra xem có đủ cột năm trước không
        available_ly_cols = [c for c in SALES_LY_COLS if c in df.columns]
        if available_ly_cols:
            df['Bán TB'] = df[available_ly_cols].mean(axis=1).round(1)
        else:
            available_cols = [c for c in SALES_COLS if c in df.columns]
            df['Bán TB'] = df[available_cols].mean(axis=1).round(1) if available_cols else 0
    else:
        available_cols = [c for c in SALES_COLS if c in df.columns]
        if available_cols:
            df['Bán TB'] = df[available_cols].mean(axis=1).round(1)
        else:
            df['Bán TB'] = 0
    
    # Tính MOH (giới hạn max để tránh giá trị quá lớn khi Bán TB ~ 0)
    df['MOH'] = df['Tồn hiện tại'] / np.maximum(1, df['Bán TB'])
    df['MOH'] = df['MOH'].round(1)
    
    # Phân loại MOH Rating
    df['MOH Rating'] = np.where(
        df['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(df['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )
    
    # Tính Supply và Demand với điều kiện MOH
    # Demand: chỉ tính khi MOH < MOH_THRESHOLD_LOW (thiếu hàng)
    df['Demand'] = np.where(
        df['MOH'] < MOH_THRESHOLD_LOW,
        np.maximum(0, MOH_TARGET * df['Bán TB'] - df['Tồn hiện tại']),
        0
    )

    # Supply: chỉ tính khi MOH > MOH_THRESHOLD_HIGH (dư thừa)
    df['Supply'] = np.where(
        df['MOH'] > MOH_THRESHOLD_HIGH,
        np.maximum(0, df['Tồn hiện tại'] - MOH_TARGET * df['Bán TB']),
        0
    )
    
    # Làm tròn lên
    df['Demand'] = np.ceil(df['Demand']).astype(int)
    df['Supply'] = np.floor(df['Supply']).astype(int)

    # Loại bỏ các cột Bán và Tồn không cần thiết
    cols_to_drop = [c for c in df.columns if ('Bán' in c and c not in ['Bán TB']) 
                   or ('Tồn' in c and c != 'Tồn hiện tại')]
    df = df.drop(columns=cols_to_drop, errors='ignore')
    
    # Loại bỏ cột Năm gộp nếu có
    df = df.drop(columns=['Năm gộp'], errors='ignore')

    return df


def _process_warehouse_file(df: pd.DataFrame) -> pd.DataFrame:
    """Xử lý file kho."""

    # --- Group/aggregate by composite key first ---
    group_cols = [c for c in ['Mã hàng', 'Màu chi tiết', 'Size'] if c in df.columns]
    if group_cols:
        agg_dict = {}
        for col in df.columns:
            if col in group_cols:
                continue
            # Heuristic: numeric columns or columns containing keywords should be summed
            if col.startswith('Tồn'):
                agg_dict[col] = 'sum'
            else:
                agg_dict[col] = 'first'

        # Only perform groupby if there is something to aggregate
        if agg_dict:
            df = df.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()

    df = df.drop(columns=['Năm gộp'], errors='ignore')
    
    return df


def concat_files(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    """Gộp các DataFrame cửa hàng."""
    if not dfs:
        return pd.DataFrame()
    
    df = pd.concat(dfs, ignore_index=True)
    
    raw_sku_series = (
        df['Mã hàng'] + 
        df['Màu chi tiết'] + 
        df['Size']
    )

    processed_sku_series = raw_sku_series.apply(norm_text)
    print(processed_sku_series.head(5))

    try:
        loc_index = df.columns.get_loc('Size') + 1
    except KeyError:
        loc_index = len(df.columns) # Mặc định để cuối nếu không có cột Size

    df.insert(
        loc=loc_index,
        column='SKU_ID',
        value=processed_sku_series
    )

    return df


# =============================================================================
# BROKEN INDEX CALCULATION
# =============================================================================

def calculate_broken_index_for_skc(
    df_store_skc: pd.DataFrame,
    master_sizes: List[str]
) -> float:
    """
    Tính Broken Index cho một SKC tại một cửa hàng.
    
    Args:
        df_store_skc: DataFrame chứa các SKU của SKC tại 1 store
        master_sizes: Danh sách các size chuẩn từ kho
    
    Returns:
        Broken Index (0-100%)
    """
    if not master_sizes:
        return 0.0
    
    # Tạo vector encoding cho sizes có tồn
    sizes_with_stock = df_store_skc[df_store_skc['Tồn hiện tại'] > 0]['Size'].unique()
    
    # Đếm số size có trong master mà cũng có tồn
    count_available = sum(1 for s in master_sizes if s in sizes_with_stock)
    
    # Broken Index = 100 - (s��� size có / tổng size) * 100
    broken_index = 100 - (count_available / len(master_sizes)) * 100
    broken_index = round(broken_index, 2)
    
    return broken_index


def calculate_broken_index_all(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """
    Tính Broken Index cho tất cả SKC tại tất cả cửa hàng.
    
    Returns:
        DataFrame với columns: [Mã cửa hàng, Mã màu, Broken Index, Is Broken]
    """
    results = []
    
    # Lấy master sizes từ kho cho mỗi SKC
    master_sizes_dict = df_warehouse.groupby('Mã màu')['Size'].apply(
        lambda x: sorted(x.unique().tolist())
    ).to_dict()
    
    # Tính cho từng store và từng SKC
    for store_id in df_stores['Mã cửa hàng'].unique():
        df_store = df_stores[df_stores['Mã cửa hàng'] == store_id]
        
        for skc in df_store['Mã màu'].unique():
            df_skc = df_store[df_store['Mã màu'] == skc]
            
            # Phụ kiện (mã bắt đầu bằng 9) không tính gãy size
            if str(skc).startswith('9'):
                broken_idx = 0.0
            elif skc in master_sizes_dict:
                broken_idx = calculate_broken_index_for_skc(
                    df_skc, 
                    master_sizes_dict[skc]
                )
            else:
                broken_idx = 0.0
            
            results.append({
                'Mã cửa hàng': store_id,
                'Mã màu': skc,
                'Broken Index': broken_idx,
                'Is Broken': 1 if broken_idx >= BROKEN_THRESHOLD else 0
            })
    
    return pd.DataFrame(results)


# =============================================================================
# PROFILE CREATION FUNCTIONS
# =============================================================================

def create_store_profiles(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo bảng Store Profiles tổng hợp.
    
    Bảng này chứa thông tin tổng hợp của từng cửa hàng, bao gồm:
    - Thông tin cơ bản: Mã, tên, vùng miền, diện tích
    - Chỉ số theo từng nhóm hàng (Giày, Quần áo, Phụ kiện):
        + Bán TB, MOH, MOH Rating, Broken Index
    - Tổng tồn, demand, supply
    """
    # Lấy thông tin cơ bản của store
    # Note: SKC Limit / SKC Trưng bày sẽ được tính riêng theo category bên dưới
    store_info = df_stores.groupby('Mã cửa hàng').agg({
        'Cửa hàng': 'first',
        'Vùng miền': 'first',
        'Diện tích': 'first',
        'Tồn hiện tại': 'sum',
        'SKC Limit': 'max',
        'SKC Trưng bày': 'max',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()
    
    # Tính chỉ số theo từng nhóm hàng
    categories = ['Giày dép', 'Quần áo', 'Phụ kiện']
    
    for cat in categories:
        df_cat = df_stores[df_stores['Phân loại'] == cat]
        
        if df_cat.empty:
            store_info[f'Bán TB_{cat}'] = 0
            store_info[f'MOH_{cat}'] = 0
            store_info[f'MOH Rating_{cat}'] = 'N/A'
            store_info[f'Broken Index_{cat}'] = 0
            continue
        
        # Tính Bán TB và MOH theo nhóm
        cat_metrics = df_cat.groupby('Mã cửa hàng').agg({
            'Bán TB': 'mean',
            'MOH': 'mean'
        }).reset_index()
        cat_metrics.columns = ['Mã cửa hàng', f'Bán TB_{cat}', f'MOH_{cat}']
        
        store_info = store_info.merge(cat_metrics, on='Mã cửa hàng', how='left')
        store_info[f'Bán TB_{cat}'] = store_info[f'Bán TB_{cat}'].round(1)
        store_info[f'MOH_{cat}'] = store_info[f'MOH_{cat}'].round(1)
        
        # MOH Rating theo nhóm
        store_info[f'MOH Rating_{cat}'] = np.where(
            store_info[f'MOH_{cat}'] < MOH_THRESHOLD_LOW, 'Tốt',
            np.where(store_info[f'MOH_{cat}'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
        )
        
        # Broken Index trung bình theo nhóm
        df_cat_broken = df_broken.merge(
            df_stores[['Mã cửa hàng', 'Mã màu', 'Phân loại']].drop_duplicates(),
            on=['Mã cửa hàng', 'Mã màu'],
            how='left'
        )
        df_cat_broken = df_cat_broken[df_cat_broken['Phân loại'] == cat]
        
        if not df_cat_broken.empty:
            broken_avg = df_cat_broken.groupby('Mã cửa hàng')['Broken Index'].mean().reset_index()
            broken_avg.columns = ['Mã cửa hàng', f'Broken Index_{cat}']
            store_info = store_info.merge(broken_avg, on='Mã cửa hàng', how='left')
        else:
            store_info[f'Broken Index_{cat}'] = 0

        # --- SKC Limit / SKC Trưng bày per category ---
        if 'SKC Limit' in df_cat.columns or 'SKC Trưng bày' in df_cat.columns:
            limits = df_cat.groupby('Mã cửa hàng').agg({
                'SKC Limit': 'max' if 'SKC Limit' in df_cat.columns else (lambda x: 0),
                'SKC Trưng bày': 'max' if 'SKC Trưng bày' in df_cat.columns else (lambda x: 0)
            }).reset_index()

            # Normalize missing cols if aggregation returned functions
            if 'SKC Limit' not in limits.columns:
                limits['SKC Limit'] = 0
            if 'SKC Trưng bày' not in limits.columns:
                limits['SKC Trưng bày'] = 0

            limits = limits.rename(columns={
                'SKC Limit': f'SKC Limit_{cat}',
                'SKC Trưng bày': f'SKC Trưng bày_{cat}'
            })

            store_info = store_info.merge(limits, on='Mã cửa hàng', how='left')
        else:
            store_info[f'SKC Limit_{cat}'] = 0
            store_info[f'SKC Trưng bày_{cat}'] = 0
    
    # Fill NaN values
    store_info = store_info.fillna(0)
    
    # Đổi tên cột cho gọn (giữ tiếng Việt)
    store_info = store_info.rename(columns={
        'Mã cửa hàng': 'Store ID',  # Keep Store ID in English for optimizer compatibility
        'Demand': 'Tổng Nhu cầu',
        'Supply': 'Tổng Nguồn cung',
        'Tồn hiện tại': 'Tổng Tồn'
    })

    return store_info


def create_store_sku_view(
    df_stores: pd.DataFrame,
    store_id: str
) -> pd.DataFrame:
    """
    Tạo view SKU cho một cửa hàng cụ thể.
    Đây là slice của df_stores theo store_id.
    """
    df = df_stores[df_stores['Mã cửa hàng'] == store_id].copy()
    
    # Chọn các cột cần thiết
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size', 
            'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB', 
            'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in df.columns]
    
    return df[cols]


def create_store_skc_view(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    store_id: str
) -> pd.DataFrame:
    """
    Tạo view SKC cho một cửa hàng cụ thể.
    Gộp theo SKC, tính trung bình MOH và Bán TB.
    """
    df = df_stores[df_stores['Mã cửa hàng'] == store_id].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    # Gộp theo SKC
    skc_view = df.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Thuộc tính': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'B��n TB': 'sum',  # Tổng bán theo SKC
        'MOH': 'mean',    # MOH trung bình
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()
    
    skc_view['Bán TB'] = skc_view['Bán TB'].round(1)
    skc_view['MOH'] = skc_view['MOH'].round(1)

    # Thêm MOH Rating
    skc_view['MOH Rating'] = np.where(
        skc_view['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(skc_view['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )
    
    # Merge Broken Index
    df_broken_store = df_broken[df_broken['Mã cửa hàng'] == store_id]
    skc_view = skc_view.merge(
        df_broken_store[['Mã màu', 'Broken Index', 'Is Broken']],
        on='Mã màu',
        how='left'
    )
    skc_view['Broken Index'] = skc_view['Broken Index'].fillna(0)
    skc_view['Is Broken'] = skc_view['Is Broken'].fillna(0)

    # Reorder columns for consistent display
    cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Broken Index', 'Is Broken']
    cols = [c for c in cols if c in skc_view.columns]
    remaining = [c for c in skc_view.columns if c not in cols]
    cols.extend(remaining)
    skc_view = skc_view[cols]

    return skc_view


def create_warehouse_sku_view(
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """Tạo view SKU cho kho."""
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
            'Thuộc tính', 'Phân loại', 'Tồn hiện tại']
    cols = [c for c in cols if c in df_warehouse.columns]
    
    return df_warehouse[cols].copy()


def create_warehouse_skc_view(
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """Tạo view SKC cho kho - gộp theo SKC."""
    skc_view = df_warehouse.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Thuộc tính': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum'
    }).reset_index()
    
    # Đếm số size có tồn
    size_count = df_warehouse[df_warehouse['Tồn hiện tại'] > 0].groupby('Mã màu')['Size'].nunique()
    skc_view['Số Size Có Tồn'] = skc_view['Mã màu'].map(size_count).fillna(0).astype(int)
    
    # Tổng số size
    total_sizes = df_warehouse.groupby('Mã màu')['Size'].nunique()
    skc_view['Tổng Size'] = skc_view['Mã màu'].map(total_sizes).fillna(0).astype(int)

    # Reorder columns for consistent display
    cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
            'Tồn hiện tại', 'Số Size Có Tồn', 'Tổng Size']
    cols = [c for c in cols if c in skc_view.columns]
    remaining = [c for c in skc_view.columns if c not in cols]
    cols.extend(remaining)
    skc_view = skc_view[cols]

    return skc_view


def create_system_sku_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo SKU Profiles toàn hệ thống.
    Gộp stores + warehouse trước khi aggregate.

    Note: Warehouse chỉ có Tồn hiện tại, không có sales data.
    Bán TB, Demand, Supply chỉ lấy từ stores.
    """
    # Select columns from stores (has all data including MOH)
    stores_cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
                   'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB', 'MOH',
                   'Demand', 'Supply']
    df_stores_subset = df_stores[stores_cols].copy()

    # Select columns from warehouse (only has inventory, no sales)
    warehouse_cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
                      'Thuộc tính', 'Phân loại', 'Tồn hiện tại']
    df_warehouse_subset = df_warehouse[warehouse_cols].copy()

    # Add missing columns to warehouse
    # Supply = Tồn hiện tại (toàn bộ tồn kho có thể supply)
    # MOH = 0 (không tính MOH cho warehouse)
    df_warehouse_subset['Bán TB'] = 0
    df_warehouse_subset['MOH'] = 0
    df_warehouse_subset['Demand'] = 0
    df_warehouse_subset['Supply'] = df_warehouse_subset['Tồn hiện tại']

    # Concat stores + warehouse
    df_combined = pd.concat([df_stores_subset, df_warehouse_subset], ignore_index=True)

    # Aggregate by SKU_ID (sum across stores + warehouse)
    # MOH: lấy max để giữ giá trị từ stores (warehouse = 0)
    sku_profiles = df_combined.groupby('SKU_ID').agg({
        'Mã hàng': 'first',
        'Mã màu': 'first',
        'Màu chi tiết': 'first',
        'Size': 'first',
        'Thuộc tính': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'max',  # Giữ MOH từ stores (warehouse = 0)
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    sku_profiles['Bán TB'] = sku_profiles['Bán TB'].round(1)

    # Tính MOH Rating sau khi gộp
    sku_profiles['MOH Rating'] = np.where(
        sku_profiles['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(sku_profiles['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )
    
    # Đếm số store có SKU này
    store_count = df_stores.groupby('SKU_ID')['Mã cửa hàng'].nunique()
    sku_profiles['Số CH có Tồn'] = sku_profiles['SKU_ID'].map(store_count).fillna(0).astype(int)

    # Reorder columns for consistent display
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
            'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB',
            'MOH', 'MOH Rating', 'Demand', 'Supply', 'Số CH có Tồn']
    cols = [c for c in cols if c in sku_profiles.columns]
    remaining = [c for c in sku_profiles.columns if c not in cols]
    cols.extend(remaining)
    sku_profiles = sku_profiles[cols]

    return sku_profiles


def create_system_skc_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame,
    df_broken: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo SKC Profiles toàn hệ thống.
    Gộp stores + warehouse trước khi aggregate.

    Note: Warehouse chỉ có Tồn hiện tại, không có sales data.
    Bán TB, Demand, Supply chỉ lấy từ stores.
    """
    # Select columns from stores (has all data including MOH)
    stores_cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
                   'Tồn hiện tại', 'Bán TB', 'MOH', 'Demand', 'Supply']
    df_stores_subset = df_stores[stores_cols].copy()

    # Select columns from warehouse (only has inventory, no sales)
    warehouse_cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
                      'Tồn hiện tại']
    df_warehouse_subset = df_warehouse[warehouse_cols].copy()

    # Add missing columns to warehouse
    # Supply = Tồn hiện tại (toàn bộ tồn kho có thể supply)
    # MOH = 0 (không tính MOH cho warehouse)
    df_warehouse_subset['Bán TB'] = 0
    df_warehouse_subset['MOH'] = 0
    df_warehouse_subset['Demand'] = 0
    df_warehouse_subset['Supply'] = df_warehouse_subset['Tồn hiện tại']

    # Concat stores + warehouse
    df_combined = pd.concat([df_stores_subset, df_warehouse_subset], ignore_index=True)

    # Aggregate by Mã màu (SKC)
    # MOH: lấy max để giữ giá trị từ stores (warehouse = 0)
    skc_profiles = df_combined.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Thuộc tính': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'max',  # Giữ MOH từ stores (warehouse = 0)
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    skc_profiles['Bán TB'] = skc_profiles['Bán TB'].round(1)

    # Tính MOH Rating sau khi gộp
    skc_profiles['MOH Rating'] = np.where(
        skc_profiles['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(skc_profiles['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )
    
    # Tính Broken Index trung bình trên toàn hệ thống
    broken_avg = df_broken.groupby('Mã màu').agg({
        'Broken Index': 'mean',
        'Is Broken': 'sum'  # Số store bị gãy size
    }).reset_index()
    broken_avg.columns = ['Mã màu', 'Avg Broken Index', 'Stores Broken']
    
    skc_profiles = skc_profiles.merge(broken_avg, on='Mã màu', how='left')
    skc_profiles['Avg Broken Index'] = skc_profiles['Avg Broken Index'].fillna(0)
    skc_profiles['Stores Broken'] = skc_profiles['Stores Broken'].fillna(0).astype(int)
    
    # Đếm số store có SKC này
    store_count = df_stores.groupby('Mã màu')['Mã cửa hàng'].nunique()
    skc_profiles['Số CH có Tồn'] = skc_profiles['Mã màu'].map(store_count).fillna(0).astype(int)

    # Reorder columns for consistent display
    cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Avg Broken Index', 'Stores Broken', 'Số CH có Tồn']
    cols = [c for c in cols if c in skc_profiles.columns]
    remaining = [c for c in skc_profiles.columns if c not in cols]
    cols.extend(remaining)
    skc_profiles = skc_profiles[cols]

    return skc_profiles

def create_system_ma_hang_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame,
    df_broken: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo Mã hàng Profiles toàn hệ thống.
    Gộp stores + warehouse trước khi aggregate.

    Args:
        df_stores: DataFrame chứa dữ liệu tồn kho của các store
        df_warehouse: DataFrame chứa dữ liệu tồn kho ở kho
        df_broken: DataFrame chứa thông tin broken size

    Returns:
        DataFrame với columns: Mã hàng, Phân loại, Thuộc tính,
        Tồn hiện tại, Bán TB, MOH, MOH Rating, Demand, Supply,
        Avg Broken Index, Stores Broken, Số SKC, Số Store
    """
    # Combine stores + warehouse
    # Note: Warehouse chỉ có Tồn hiện tại, không có sales data.
    # Bán TB, Demand chỉ lấy từ stores. Supply warehouse = Tồn hiện tại.
    stores_cols = ['Mã hàng', 'Phân loại', 'Tồn hiện tại', 'Bán TB', 'MOH',
                   'Demand', 'Supply']
    df_stores_subset = df_stores[stores_cols].copy()

    # Select columns from warehouse (only has inventory, no sales)
    warehouse_cols = ['Mã hàng', 'Phân loại', 'Tồn hiện tại']
    df_warehouse_subset = df_warehouse[warehouse_cols].copy()

    # Add missing columns to warehouse
    # Supply = Tồn hiện tại (toàn bộ tồn kho có thể supply)
    # MOH = 0 (không tính MOH cho warehouse)
    df_warehouse_subset['Bán TB'] = 0
    df_warehouse_subset['MOH'] = 0
    df_warehouse_subset['Demand'] = 0
    df_warehouse_subset['Supply'] = df_warehouse_subset['Tồn hiện tại']

    # Concat stores + warehouse
    df_combined = pd.concat([df_stores_subset, df_warehouse_subset], ignore_index=True)

    # Group by Mã hàng và aggregate
    # MOH: lấy max để giữ giá trị từ stores (warehouse = 0)
    ma_hang_profiles = df_combined.groupby('Mã hàng').agg({
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'max',  # Giữ MOH từ stores (warehouse = 0)
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    # Round Bán TB
    ma_hang_profiles['Bán TB'] = ma_hang_profiles['Bán TB'].round(1)

    # Tính MOH Rating sau khi gộp
    ma_hang_profiles['MOH Rating'] = np.where(
        ma_hang_profiles['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(ma_hang_profiles['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )
    
    # Calculate Broken Index - extract Mã hàng từ Mã màu
    df_broken_copy = df_broken.copy()
    df_broken_copy['Mã hàng'] = df_broken_copy['Mã màu'].str[:7]
    
    # Average Broken Index và count Stores Broken per Mã hàng
    broken_agg = df_broken_copy.groupby('Mã hàng').agg({
        'Broken Index': 'mean',
        'Is Broken': 'sum'
    }).reset_index()
    broken_agg.columns = ['Mã hàng', 'Avg Broken Index', 'Stores Broken']
    
    # Count số SKC per Mã hàng (Mã màu là SKC)
    skc_count = df_stores.groupby('Mã hàng')['Mã màu'].nunique()
    ma_hang_profiles['Số SKC có Tồn'] = ma_hang_profiles['Mã hàng'].map(skc_count).fillna(0).astype(int)
    
    # Count số Store per Mã hàng
    store_count = df_stores.groupby('Mã hàng')['Mã cửa hàng'].nunique()
    ma_hang_profiles['Số CH có Tồn'] = ma_hang_profiles['Mã hàng'].map(store_count).fillna(0).astype(int)
    
    # Reorder columns
    cols = ['Mã hàng', 'Phân loại', 'Tồn hiện tại', 'Bán TB',
            'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Avg Broken Index', 'Số SKC có Tồn', 'Số CH có Tồn']
    
    # Handle optional 'Thuộc tính' column nếu có
    if 'Thuộc tính' in df_stores.columns:
        # Add Thuộc tính to aggregation if exists
        if 'Thuộc tính' not in ma_hang_profiles.columns:
            thuoc_tinh = df_stores.groupby('Mã hàng')['Thuộc tính'].first()
            ma_hang_profiles['Thuộc tính'] = ma_hang_profiles['Mã hàng'].map(thuoc_tinh)
        cols.insert(2, 'Thuộc tính')
    
    # Only keep columns that exist
    cols = [c for c in cols if c in ma_hang_profiles.columns]
    remaining = [c for c in ma_hang_profiles.columns if c not in cols]
    cols.extend(remaining)
    ma_hang_profiles = ma_hang_profiles[cols]
    
    return ma_hang_profiles


# =============================================================================
# LOCATION-BASED PRODUCT PROFILES (Detailed by Store/Warehouse)
# =============================================================================

def create_location_sku_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo SKU Profiles chi tiết theo vị trí (từng cửa hàng + kho).
    Không aggregate, giữ nguyên từng location riêng biệt.
    """
    # Select columns from stores
    stores_cols = ['SKU_ID', 'Mã cửa hàng', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
                   'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating',
                   'Demand', 'Supply']
    df_stores_subset = df_stores[stores_cols].copy()

    # Select columns from warehouse
    warehouse_cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
                      'Thuộc tính', 'Phân loại', 'Tồn hiện tại']
    df_warehouse_subset = df_warehouse[warehouse_cols].copy()

    # Add warehouse-specific columns
    df_warehouse_subset['Mã cửa hàng'] = 'Kho'
    df_warehouse_subset['Bán TB'] = 0
    df_warehouse_subset['MOH'] = 0
    df_warehouse_subset['MOH Rating'] = ''
    df_warehouse_subset['Demand'] = 0
    df_warehouse_subset['Supply'] = df_warehouse_subset['Tồn hiện tại']

    # Concat stores + warehouse (không aggregate)
    location_profiles = pd.concat([df_stores_subset, df_warehouse_subset], ignore_index=True)

    # Reorder columns
    cols = ['SKU_ID', 'Mã cửa hàng', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
            'Thuộc tính', 'Phân loại', 'Tồn hiện tại', 'Bán TB',
            'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in location_profiles.columns]
    location_profiles = location_profiles[cols]

    return location_profiles


def create_location_skc_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo SKC Profiles chi tiết theo vị trí.
    Aggregate theo (Mã cửa hàng, Mã màu).
    """
    # Get location SKU profiles first
    location_sku = create_location_sku_profiles(df_stores, df_warehouse)

    # Aggregate by (Mã cửa hàng, Mã màu)
    skc_profiles = location_sku.groupby(['Mã cửa hàng', 'Mã màu']).agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Thuộc tính': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'max',
        'MOH Rating': 'first',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    skc_profiles['Bán TB'] = skc_profiles['Bán TB'].round(1)

    # Reorder columns
    cols = ['Mã cửa hàng', 'Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in skc_profiles.columns]
    skc_profiles = skc_profiles[cols]

    return skc_profiles


def create_location_ma_hang_profiles(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame
) -> pd.DataFrame:
    """
    Tạo Mã hàng Profiles chi tiết theo vị trí.
    Aggregate theo (Mã cửa hàng, Mã hàng).
    """
    # Get location SKU profiles first
    location_sku = create_location_sku_profiles(df_stores, df_warehouse)

    # Aggregate by (Mã cửa hàng, Mã hàng)
    ma_hang_profiles = location_sku.groupby(['Mã cửa hàng', 'Mã hàng']).agg({
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'max',
        'MOH Rating': 'first',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    ma_hang_profiles['Bán TB'] = ma_hang_profiles['Bán TB'].round(1)

    # Reorder columns
    cols = ['Mã cửa hàng', 'Mã hàng', 'Phân loại',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in ma_hang_profiles.columns]
    ma_hang_profiles = ma_hang_profiles[cols]

    return ma_hang_profiles


# =============================================================================
# QUERY & FILTER FUNCTIONS
# =============================================================================

# -----------------------------------------------------------------------------
# A. Queries từ store_profiles
# -----------------------------------------------------------------------------

def get_stores_by_sales(
    store_profiles: pd.DataFrame,
    category: str = None,
    top_n: int = None,
    ascending: bool = False
) -> pd.DataFrame:
    """
    A1: DS store xếp theo doanh số bán.
    
    Args:
        store_profiles: Bảng store profiles
        category: 'Giày dép', 'Quần áo', 'Phụ kiện' hoặc None (tổng)
        top_n: Số lượng kết quả (None = tất cả)
        ascending: False = bán tốt nhất trước
    
    Example:
        get_stores_by_sales(store_profiles, 'Giày dép', top_n=5)
        get_stores_by_sales(store_profiles, ascending=True)  # bán kém nhất
    """
    df = store_profiles.copy()
    
    if category:
        sort_col = f'Bán TB_{category}'
    else:
        df['Bán TB_Tổng'] = (
            df.get('Bán TB_Giày dép', 0).fillna(0) + 
            df.get('Bán TB_Quần áo', 0).fillna(0) + 
            df.get('Bán TB_Phụ kiện', 0).fillna(0)
        )
        sort_col = 'Bán TB_Tổng'
    
    df = df.sort_values(sort_col, ascending=ascending)
    return df.head(top_n) if top_n else df


def get_stores_by_moh(
    store_profiles: pd.DataFrame,
    category: str = None,
    top_n: int = None,
    ascending: bool = True
) -> pd.DataFrame:
    """
    A2: DS store xếp theo MOH (tồn kho).
    
    Args:
        category: 'Giày dép', 'Quần áo', 'Phụ kiện' hoặc None
        ascending: True = MOH thấp nhất trước (cần nhập hàng)
    
    Example:
        get_stores_by_moh(store_profiles, 'Giày dép', top_n=5)  # tồn thấp
        get_stores_by_moh(store_profiles, ascending=False)  # tồn cao
    """
    df = store_profiles.copy()
    
    if category:
        sort_col = f'MOH_{category}'
    else:
        moh_cols = [c for c in df.columns if c.startswith('MOH_') and 'Rating' not in c]
        df['MOH_Tổng'] = df[moh_cols].mean(axis=1).round(1)
        sort_col = 'MOH_Tổng'
    
    df = df.sort_values(sort_col, ascending=ascending)
    return df.head(top_n) if top_n else df


def get_stores_by_broken(
    store_profiles: pd.DataFrame,
    category: str = None,
    top_n: int = None
) -> pd.DataFrame:
    """
    A3: DS store xếp theo mức độ gãy size (nặng nhất trước).
    
    Example:
        get_stores_by_broken(store_profiles, 'Giày dép', top_n=5)
    """
    df = store_profiles.copy()
    
    if category:
        sort_col = f'Broken Index_{category}'
    else:
        broken_cols = [c for c in df.columns if c.startswith('Broken Index_')]
        df['Broken Index_Tổng'] = df[broken_cols].mean(axis=1)
        sort_col = 'Broken Index_Tổng'
    
    df = df.sort_values(sort_col, ascending=False)
    return df.head(top_n) if top_n else df


def get_stores_need_import(
    store_profiles: pd.DataFrame,
    min_demand: float = 0
) -> pd.DataFrame:
    """
    A4: DS store cần nhập hàng (có Demand).
    
    Example:
        get_stores_need_import(store_profiles)
        get_stores_need_import(store_profiles, min_demand=100)
    """
    df = store_profiles[store_profiles['Total Demand'] > min_demand].copy()
    return df.sort_values('Total Demand', ascending=False)


def get_stores_need_export(
    store_profiles: pd.DataFrame,
    min_supply: float = 0
) -> pd.DataFrame:
    """
    A5: DS store cần xuất hàng (có Supply).
    
    Example:
        get_stores_need_export(store_profiles)
        get_stores_need_export(store_profiles, min_supply=50)
    """
    df = store_profiles[store_profiles['Total Supply'] > min_supply].copy()
    return df.sort_values('Total Supply', ascending=False)


def get_stores_by_region(
    store_profiles: pd.DataFrame,
    region: str
) -> pd.DataFrame:
    """
    A6: Filter store theo vùng miền.
    
    Args:
        region: 'S1 - Miền bắc', 'S3 - Miền trung', 'S4 - Miền nam', etc.
    
    Example:
        get_stores_by_region(store_profiles, 'S1 - Miền bắc')
    """
    return store_profiles[store_profiles['Region'].str.contains(region, case=False, na=False)]


# -----------------------------------------------------------------------------
# B. Queries từ df_stores (chi tiết SKU/SKC)
# -----------------------------------------------------------------------------

def get_sku_at_store(
    df_stores: pd.DataFrame,
    store_id: str,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B1: DS SKU tại 1 store.
    
    Args:
        sort_by: 'Bán TB', 'MOH', 'Demand', 'Supply', 'Tồn hiện tại'
    
    Example:
        get_sku_at_store(df_stores, 'CH-001', sort_by='Bán TB')
        get_sku_at_store(df_stores, 'CH-001', sort_by='Demand')
    """
    df = df_stores[df_stores['Mã cửa hàng'] == store_id].copy()
    
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size', 
            'Phân loại', 'Thuộc tính', 'Tồn hiện tại', 'Bán TB', 
            'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in df.columns]
    
    return df[cols].sort_values(sort_by, ascending=ascending)


def get_skc_at_store(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    store_id: str,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B2: DS SKC tại 1 store (gộp từ SKU).
    
    Args:
        sort_by: 'Bán TB', 'MOH', 'Demand', 'Broken Index'
    
    Example:
        get_skc_at_store(df_stores, df_broken, 'CH-001', sort_by='Broken Index')
    """
    df = df_stores[df_stores['Mã cửa hàng'] == store_id].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    skc_summary = df.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'mean',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    skc_summary['Bán TB'] = skc_summary['Bán TB'].round(1)
    skc_summary['MOH'] = skc_summary['MOH'].round(1)

    # Add MOH Rating
    skc_summary['MOH Rating'] = np.where(
        skc_summary['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(skc_summary['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )

    # Merge broken index - merged columns will be at the end
    broken_store = df_broken[df_broken['Mã cửa hàng'] == store_id][['Mã màu', 'Broken Index', 'Is Broken']]
    skc_summary = skc_summary.merge(broken_store, on='Mã màu', how='left')
    skc_summary['Broken Index'] = skc_summary['Broken Index'].fillna(0)
    skc_summary['Is Broken'] = skc_summary['Is Broken'].fillna(0)

    # Đếm số size có tồn
    size_count = df[df['Tồn hiện tại'] > 0].groupby('Mã màu')['Size'].nunique()
    skc_summary['Số Size Có Tồn'] = skc_summary['Mã màu'].map(size_count).fillna(0).astype(int)

    # Reorder columns for consistent display (merged columns at the end)
    cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Phân loại', 'Thuộc tính',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Broken Index', 'Is Broken', 'Số Size Có Tồn']
    cols = [c for c in cols if c in skc_summary.columns]
    remaining = [c for c in skc_summary.columns if c not in cols]
    cols.extend(remaining)
    skc_summary = skc_summary[cols]

    return skc_summary.sort_values(sort_by, ascending=ascending)


def get_ma_hang_at_store(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    store_id: str,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    Lấy danh sách Mã hàng tại 1 store (gộp từ SKC).

    Args:
        df_stores: DataFrame stores
        df_broken: DataFrame broken
        store_id: Mã cửa hàng
        sort_by: 'Bán TB', 'MOH', 'Demand', 'Broken Index'
        ascending: Sắp xếp tăng/giảm

    Returns:
        DataFrame với các Mã hàng tại store
    """
    df = df_stores[df_stores['Mã cửa hàng'] == store_id].copy()

    if df.empty:
        return pd.DataFrame()

    # Groupby theo Mã hàng
    ma_hang_summary = df.groupby('Mã hàng').agg({
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'mean',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()

    ma_hang_summary['Bán TB'] = ma_hang_summary['Bán TB'].round(1)
    ma_hang_summary['MOH'] = ma_hang_summary['MOH'].round(1)

    # Add MOH Rating
    ma_hang_summary['MOH Rating'] = np.where(
        ma_hang_summary['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(ma_hang_summary['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )

    # Tính Broken Index trung bình cho Mã hàng - merged columns will be at the end
    broken_store = df_broken[df_broken['Mã cửa hàng'] == store_id][['Mã màu', 'Broken Index']].copy()
    # Lấy Mã hàng từ Mã màu
    broken_store['Mã hàng'] = broken_store['Mã màu'].str[:7]
    broken_agg = broken_store.groupby('Mã hàng')['Broken Index'].mean().reset_index()

    ma_hang_summary = ma_hang_summary.merge(broken_agg, on='Mã hàng', how='left')
    ma_hang_summary['Broken Index'] = ma_hang_summary['Broken Index'].fillna(0).round(1)

    # Đếm số SKC cho mỗi Mã hàng
    skc_count = df.groupby('Mã hàng')['Mã màu'].nunique()
    ma_hang_summary['Số SKC'] = ma_hang_summary['Mã hàng'].map(skc_count).fillna(0).astype(int)

    # Reorder columns for consistent display (merged Broken Index at the end)
    cols = ['Mã hàng', 'Thuộc tính', 'Phân loại',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Broken Index']
    cols = [c for c in cols if c in ma_hang_summary.columns]
    remaining = [c for c in ma_hang_summary.columns if c not in cols]
    cols.extend(remaining)
    ma_hang_summary = ma_hang_summary[cols]

    return ma_hang_summary.sort_values(sort_by, ascending=ascending)


def get_stores_by_sku(
    df_stores: pd.DataFrame,
    sku_id: str,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B3: Nhập SKU → DS store có SKU đó.
    
    Args:
        sku_id: Format 'MãHàng_MàuChiTiết_Size' (vd: '7000000_Tím_37')
        sort_by: 'Bán TB', 'Demand', 'Supply', 'MOH'
    
    Example:
        get_stores_by_sku(df_stores, '7000000_Tím_37', sort_by='Bán TB')
        get_stores_by_sku(df_stores, '7000000_Tím_37', sort_by='Demand')
    """
    df = df_stores[df_stores['SKU_ID'] == sku_id].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    cols = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Tồn hiện tại', 
            'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in df.columns]
    
    return df[cols].sort_values(sort_by, ascending=ascending)


def get_stores_by_skc(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    skc: str,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B4: Nhập SKC → DS store có SKC đó.
    
    Args:
        skc: Mã màu (vd: '7000000Tim')
        sort_by: 'Bán TB', 'Demand', 'Broken Index', 'MOH'
    
    Example:
        get_stores_by_skc(df_stores, df_broken, '7000000Tim', sort_by='Broken Index')
    """
    df = df_stores[df_stores['Mã màu'] == skc].copy()
    
    if df.empty:
        return pd.DataFrame()
    
    store_summary = df.groupby('Mã cửa hàng').agg({
        'Cửa hàng': 'first',
        'Vùng miền': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'MOH': 'mean',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()
    
    store_summary['Bán TB'] = store_summary['Bán TB'].round(1)
    store_summary['MOH'] = store_summary['MOH'].round(1)

    # Add MOH Rating
    store_summary['MOH Rating'] = np.where(
        store_summary['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(store_summary['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )

    # Merge broken index - merged columns will be at the end
    broken_skc = df_broken[df_broken['Mã màu'] == skc][['Mã cửa hàng', 'Broken Index', 'Is Broken']]
    store_summary = store_summary.merge(broken_skc, on='Mã cửa hàng', how='left')
    store_summary['Broken Index'] = store_summary['Broken Index'].fillna(0)
    store_summary['Is Broken'] = store_summary['Is Broken'].fillna(0)

    # Đếm số size có tồn
    size_count = df[df['Tồn hiện tại'] > 0].groupby('Mã cửa hàng')['Size'].nunique()
    store_summary['Số Size Có Tồn'] = store_summary['Mã cửa hàng'].map(size_count).fillna(0).astype(int)

    # Reorder columns for consistent display (merged columns at the end)
    cols = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền',
            'Tồn hiện tại', 'Bán TB', 'MOH', 'MOH Rating', 'Demand', 'Supply',
            'Broken Index', 'Is Broken', 'Số Size Có Tồn']
    cols = [c for c in cols if c in store_summary.columns]
    remaining = [c for c in store_summary.columns if c not in cols]
    cols.extend(remaining)
    store_summary = store_summary[cols]

    return store_summary.sort_values(sort_by, ascending=ascending)


def get_top_sku_system(
    df_stores: pd.DataFrame,
    top_n: int = 10,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B5: Top SKU toàn hệ thống.
    
    Args:
        sort_by: 'Bán TB', 'Tồn hiện tại', 'Demand', 'Supply'
    
    Example:
        get_top_sku_system(df_stores, top_n=10, sort_by='Bán TB')  # bán chạy
        get_top_sku_system(df_stores, top_n=10, sort_by='Demand')  # cần nhập
    """
    sku_summary = df_stores.groupby('SKU_ID').agg({
        'Mã hàng': 'first',
        'Mã màu': 'first',
        'Màu chi tiết': 'first',
        'Size': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()
    
    sku_summary['Bán TB'] = sku_summary['Bán TB'].round(1)
    sku_summary['MOH'] = (sku_summary['Tồn hiện tại'] / 
                         np.maximum(1, sku_summary['Bán TB'])).round(1)
    
    # Đếm số store có SKU
    store_count = df_stores.groupby('SKU_ID')['Mã cửa hàng'].nunique()
    sku_summary['Số Store'] = sku_summary['SKU_ID'].map(store_count)
    
    return sku_summary.sort_values(sort_by, ascending=ascending).head(top_n)


def get_top_skc_system(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    top_n: int = 10,
    sort_by: str = 'Bán TB',
    ascending: bool = False
) -> pd.DataFrame:
    """
    B6: Top SKC toàn hệ thống.
    
    Args:
        sort_by: 'Bán TB', 'Tồn hiện tại', 'Demand', 'Avg Broken Index'
    
    Example:
        get_top_skc_system(df_stores, df_broken, top_n=10, sort_by='Bán TB')
        get_top_skc_system(df_stores, df_broken, sort_by='Avg Broken Index')
    """
    skc_summary = df_stores.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum',
        'Bán TB': 'sum',
        'Demand': 'sum',
        'Supply': 'sum'
    }).reset_index()
    
    skc_summary['Bán TB'] = skc_summary['Bán TB'].round(1)
    skc_summary['MOH'] = (skc_summary['Tồn hiện tại'] / 
                         np.maximum(1, skc_summary['Bán TB'])).round(1)
    
    # Tính Avg Broken Index
    broken_avg = df_broken.groupby('Mã màu').agg({
        'Broken Index': 'mean',
        'Is Broken': 'sum'
    }).reset_index()
    broken_avg.columns = ['Mã màu', 'Avg Broken Index', 'Stores Broken']
    skc_summary = skc_summary.merge(broken_avg, on='Mã màu', how='left')
    
    # Đếm số store có SKC
    store_count = df_stores.groupby('Mã màu')['Mã cửa hàng'].nunique()
    skc_summary['Số Store'] = skc_summary['Mã màu'].map(store_count)
    
    return skc_summary.sort_values(sort_by, ascending=ascending).head(top_n)


# -----------------------------------------------------------------------------
# C. Queries từ df_warehouse
# -----------------------------------------------------------------------------

def get_warehouse_sku_available(
    df_warehouse: pd.DataFrame,
    sku_id: str
) -> dict:
    """
    C2: Kiểm tra kho còn SKU không.
    
    Example:
        get_warehouse_sku_available(df_warehouse, '7000000_Tím_37')
        # Returns: {'available': True, 'stock': 77}
    """
    df = df_warehouse[df_warehouse['SKU_ID'] == sku_id]
    
    if df.empty:
        return {'available': False, 'stock': 0, 'sku_id': sku_id}
    
    stock = df['Tồn hiện tại'].sum()
    return {'available': stock > 0, 'stock': stock, 'sku_id': sku_id}


def get_warehouse_skc_available(
    df_warehouse: pd.DataFrame,
    skc: str
) -> dict:
    """
    Kiểm tra kho còn SKC (Mã màu) không.

    Example:
        get_warehouse_skc_available(df_warehouse, '7000000Tim')
        # Returns: {'available': True, 'stock': 123, 'skc': '7000000Tim'}
    """
    df = df_warehouse[df_warehouse['Mã màu'] == skc]

    if df.empty:
        return {'available': False, 'stock': 0, 'skc': skc}
    
    df = df.groupby('Mã màu').agg({'Tồn hiện tại': 'sum'}).reset_index()
    stock = df['Tồn hiện tại'].sum()

    return {'available': stock > 0, 'stock': int(stock), 'skc': skc}


def get_warehouse_ma_hang_available(
    df_warehouse: pd.DataFrame,
    sort_by: str = 'Tổng Tồn theo SKU',
    ascending: bool = False
) -> pd.DataFrame:
    """
    Lấy danh sách Mã hàng có trong warehouse (gộp từ SKC).

    Args:
        df_warehouse: DataFrame warehouse
        sort_by: 'Tồn hiện tại', 'Số SKC'
        ascending: Sắp xếp tăng/giảm

    Returns:
        DataFrame với các Mã hàng trong warehouse
    """
    if df_warehouse.empty:
        return pd.DataFrame()

    # Groupby theo Mã hàng
    ma_hang_summary = df_warehouse.groupby('Mã hàng').agg({
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum'
    }).reset_index()

    ma_hang_summary = ma_hang_summary.rename(columns={'Tồn hiện tại': 'Tổng Tồn theo SKU'})

    # Đếm số SKC cho mỗi Mã hàng
    skc_count = df_warehouse.groupby('Mã hàng')['Mã màu'].nunique()
    ma_hang_summary['Số SKC'] = ma_hang_summary['Mã hàng'].map(skc_count).fillna(0).astype(int)

    # Đếm số SKU cho mỗi Mã hàng
    sku_count = df_warehouse.groupby('Mã hàng')['SKU_ID'].nunique()
    ma_hang_summary['Số SKU'] = ma_hang_summary['Mã hàng'].map(sku_count).fillna(0).astype(int)

    # Reorder columns for consistent display
    cols = ['Mã hàng', 'Phân loại', 'Tổng Tồn theo SKU', 'Số SKC', 'Số SKU']
    cols = [c for c in cols if c in ma_hang_summary.columns]
    remaining = [c for c in ma_hang_summary.columns if c not in cols]
    cols.extend(remaining)
    ma_hang_summary = ma_hang_summary[cols]

    return ma_hang_summary.sort_values(sort_by, ascending=ascending)


def get_warehouse_skc(
    df_warehouse: pd.DataFrame,
    sort_by: str = 'Tổng Tồn theo SKU',
    ascending: bool = False
) -> pd.DataFrame:
    """
    Lấy danh sách SKC có trong warehouse với thông tin tổng hợp.

    Args:
        df_warehouse: DataFrame warehouse
        sort_by: 'Tổng Tồn theo SKU', 'Số Size'
        ascending: Sắp xếp tăng/giảm

    Returns:
        DataFrame với các SKC trong warehouse (Mã màu, Mã hàng, Màu chi tiết,
        Thuộc tính, Phân loại, Tổng Tồn theo SKU, Số Size)
    """
    if df_warehouse.empty:
        return pd.DataFrame()

    # Groupby theo SKC (Mã màu)
    skc_summary = df_warehouse.groupby('Mã màu').agg({
        'Mã hàng': 'first',
        'Màu chi tiết': 'first',
        'Phân loại': 'first',
        'Tồn hiện tại': 'sum'
    }).reset_index()

    skc_summary = skc_summary.rename(columns={'Tồn hiện tại': 'Tổng Tồn theo SKU'})

    # Đếm số Size cho mỗi SKC
    size_count = df_warehouse.groupby('Mã màu')['Size'].nunique()
    skc_summary['Số Size'] = skc_summary['Mã màu'].map(size_count).fillna(0).astype(int)

    # Reorder columns for consistent display
    cols = ['Mã màu', 'Mã hàng', 'Màu chi tiết', 'Thuộc tính', 'Phân loại', 'Tổng Tồn theo SKU']
    cols = [c for c in cols if c in skc_summary.columns]
    remaining = [c for c in skc_summary.columns if c not in cols]
    cols.extend(remaining)
    skc_summary = skc_summary[cols]

    return skc_summary.sort_values(sort_by, ascending=ascending)


# -----------------------------------------------------------------------------
# D. Queries từ df_broken
# -----------------------------------------------------------------------------

def get_broken_by_store(
    df_broken: pd.DataFrame,
    store_id: str
) -> pd.DataFrame:
    """
    D1: DS SKC gãy tại 1 store.
    
    Example:
        get_broken_by_store(df_broken, 'CH-001')
    """
    df = df_broken[df_broken['Mã cửa hàng'] == store_id].copy()
    return df.sort_values('Broken Index', ascending=False)


def get_broken_by_skc(
    df_broken: pd.DataFrame,
    df_stores: pd.DataFrame,
    skc: str
) -> pd.DataFrame:
    """
    D2: DS store gãy size của 1 SKC.

    Example:
        get_broken_by_skc(df_broken, df_stores, '7000000Tim')
    """
    df = df_broken[df_broken['Mã màu'] == skc].copy()

    if df.empty:
        return pd.DataFrame()

    # Merge thông tin store
    store_info = df_stores[['Mã cửa hàng', 'Cửa hàng', 'Vùng miền']].drop_duplicates()
    df = df.merge(store_info, on='Mã cửa hàng', how='left')

    cols = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Mã màu', 
            'Broken Index', 'Is Broken', 'Tồn hiện tại', 'Bán TB', 
            'MOH', 'MOH Rating', 'Demand', 'Supply', 'Số Size Có Tồn']
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    return df.sort_values('Broken Index', ascending=False)


def get_broken_sku_at_store(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    skc: str,
    store_id: str
) -> pd.DataFrame:
    """
    Lấy danh sách SKU broken của một SKC tại một store cụ thể.

    Args:
        df_stores: DataFrame stores
        df_broken: DataFrame broken
        skc: Mã màu (SKC)
        store_id: Mã cửa hàng

    Returns:
        DataFrame với các SKU của SKC tại store đó.
        Trả về DataFrame rỗng nếu:
        - Store không có SKC này
        - SKC không bị broken tại store này
    """
    # Kiểm tra store có broken SKC này không
    broken_check = df_broken[
        (df_broken['Mã màu'] == skc) &
        (df_broken['Mã cửa hàng'] == store_id)
    ]

    if broken_check.empty:
        # Store không có SKC này hoặc SKC không bị broken
        return pd.DataFrame()

    # Lấy tất cả SKU của SKC tại store này
    df = df_stores[
        (df_stores['Mã màu'] == skc) &
        (df_stores['Mã cửa hàng'] == store_id)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # Chọn các cột cần thiết
    cols = ['SKU_ID', 'Mã hàng', 'Mã màu', 'Màu chi tiết', 'Size',
            'Phân loại', 'Thuộc tính', 'Tồn hiện tại', 'Bán TB',
            'MOH', 'MOH Rating', 'Demand', 'Supply']
    cols = [c for c in cols if c in df.columns]

    return df[cols].sort_values('Size')


def get_most_broken_skc(
    df_broken: pd.DataFrame,
    top_n: int = 10
) -> pd.DataFrame:
    """
    D3: SKC bị gãy ở nhiều store nhất.
    
    Example:
        get_most_broken_skc(df_broken, top_n=10)
    """
    skc_broken = df_broken.groupby('Mã màu').agg({
        'Broken Index': 'mean',
        'Is Broken': 'sum',
        'Mã cửa hàng': 'count'
    }).reset_index()
    skc_broken.columns = ['Mã màu', 'Avg Broken Index', 'Stores Broken', 'Total Stores']
    skc_broken['% Stores Broken'] = (skc_broken['Stores Broken'] / skc_broken['Total Stores'] * 100).round(1)
    
    return skc_broken.sort_values('Stores Broken', ascending=False).head(top_n)


def get_heavy_broken_stores(
    df_broken: pd.DataFrame,
    df_stores: pd.DataFrame,
    threshold: float = 0.6
) -> pd.DataFrame:
    """
    D4: DS store gãy nặng (>threshold% SKC bị gãy).
    
    Args:
        threshold: Ngưỡng % SKC gãy (default 0.6 = 60%)
    
    Example:
        get_heavy_broken_stores(df_broken, df_stores)  # >60%
        get_heavy_broken_stores(df_broken, df_stores, threshold=0.5)  # >50%
    """
    store_broken = df_broken.groupby('Mã cửa hàng').agg({
        'Is Broken': ['sum', 'count']
    }).reset_index()
    store_broken.columns = ['Mã cửa hàng', 'SKC Broken', 'Total SKC']
    store_broken['% Broken'] = store_broken['SKC Broken'] / store_broken['Total SKC']
    
    # Filter heavy broken
    heavy = store_broken[store_broken['% Broken'] > threshold].copy()
    
    # Merge store info
    store_info = df_stores[['Mã cửa hàng', 'Cửa hàng', 'Vùng miền']].drop_duplicates()
    heavy = heavy.merge(store_info, on='Mã cửa hàng', how='left')
    
    return heavy.sort_values('% Broken', ascending=False)


# -----------------------------------------------------------------------------
# E. Queries kết hợp (cross-file)
# -----------------------------------------------------------------------------

def get_reallocation_candidates(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    sku_id: str
) -> dict:
    """
    E1: DS store có thể xuất/nhập SKU này.
    
    Returns:
        dict với 'suppliers' (có Supply) và 'receivers' (có Demand)
    
    Example:
        candidates = get_reallocation_candidates(df_stores, df_broken, '7000000_Tím_37')
        print(candidates['suppliers'])  # stores có thể xuất
        print(candidates['receivers'])  # stores cần nhập
    """
    df = df_stores[df_stores['SKU_ID'] == sku_id].copy()
    
    if df.empty:
        return {'suppliers': pd.DataFrame(), 'receivers': pd.DataFrame(), 'sku_id': sku_id}
    
    skc = df['Mã màu'].iloc[0]
    
    # Merge broken index
    broken_info = df_broken[df_broken['Mã màu'] == skc][['Mã cửa hàng', 'Broken Index']]
    df = df.merge(broken_info, on='Mã cửa hàng', how='left')
    
    cols = ['Mã cửa hàng', 'Cửa hàng', 'Vùng miền', 'Tồn hiện tại', 
            'Bán TB', 'MOH', 'Demand', 'Supply', 'Broken Index']
    cols = [c for c in cols if c in df.columns]
    
    suppliers = df[df['Supply'] > 0][cols].sort_values('Supply', ascending=False)
    receivers = df[df['Demand'] > 0][cols].sort_values('Demand', ascending=False)
    
    return {
        'suppliers': suppliers,
        'receivers': receivers,
        'sku_id': sku_id,
        'skc': skc
    }


def get_store_full_report(
    df_stores: pd.DataFrame,
    df_broken: pd.DataFrame,
    store_profiles: pd.DataFrame,
    store_id: str
) -> dict:
    """
    E2: Báo cáo tổng hợp 1 store.
    
    Example:
        report = get_store_full_report(df_stores, df_broken, store_profiles, 'CH-001')
        print(report['profile'])      # thông tin tổng quan
        print(report['top_sku'])      # SKU bán chạy
        print(report['broken_skc'])   # SKC gãy size
    """
    profile = store_profiles[store_profiles['Store ID'] == store_id]
    top_sku = get_sku_at_store(df_stores, store_id, sort_by='Bán TB').head(10)
    top_skc = get_skc_at_store(df_stores, df_broken, store_id, sort_by='Bán TB').head(10)
    broken_skc = get_broken_by_store(df_broken, store_id)
    broken_skc = broken_skc[broken_skc['Is Broken'] == 1]
    
    sku_need_import = get_sku_at_store(df_stores, store_id, sort_by='Demand')
    sku_need_import = sku_need_import[sku_need_import['Demand'] > 0].head(10)
    
    sku_can_export = get_sku_at_store(df_stores, store_id, sort_by='Supply')
    sku_can_export = sku_can_export[sku_can_export['Supply'] > 0].head(10)
    
    return {
        'store_id': store_id,
        'profile': profile,
        'top_sku': top_sku,
        'top_skc': top_skc,
        'broken_skc': broken_skc,
        'sku_need_import': sku_need_import,
        'sku_can_export': sku_can_export
    }


def get_sku_full_report(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame,
    df_broken: pd.DataFrame,
    sku_id: str
) -> dict:
    """
    E3: Báo cáo tổng hợp 1 SKU.
    
    Example:
        report = get_sku_full_report(df_stores, df_warehouse, df_broken, '7000000_Tím_37')
        print(report['warehouse'])    # tồn kho
        print(report['stores'])       # tồn tại các store
        print(report['candidates'])   # ứng viên điều phối
    """
    warehouse_stock = get_warehouse_sku_available(df_warehouse, sku_id)
    stores = get_stores_by_sku(df_stores, sku_id, sort_by='Bán TB')
    candidates = get_reallocation_candidates(df_stores, df_broken, sku_id)
    
    # Lấy SKC
    skc = df_stores[df_stores['SKU_ID'] == sku_id]['Mã màu'].iloc[0] if not stores.empty else None
    
    # Tổng hợp
    total_stock_stores = stores['Tồn hiện tại'].sum() if not stores.empty else 0
    total_demand = stores['Demand'].sum() if not stores.empty else 0
    total_supply = stores['Supply'].sum() if not stores.empty else 0
    
    return {
        'sku_id': sku_id,
        'skc': skc,
        'warehouse': warehouse_stock,
        'stores': stores,
        'candidates': candidates,
        'summary': {
            'warehouse_stock': warehouse_stock['stock'],
            'total_stock_stores': total_stock_stores,
            'total_demand': total_demand,
            'total_supply': total_supply,
            'num_stores': len(stores)
        }
    }


# =============================================================================
# Mới add
# =============================================================================

def get_warehouse_size_range(df_warehouse: pd.DataFrame, skc: str) -> dict:
    """
    Lấy dải size chuẩn từ kho theo SKC.
    """
    df = df_warehouse[df_warehouse['Mã màu'] == skc]
    if df.empty:
        return {'skc': skc, 'sizes': [], 'sizes_with_stock': [], 'total': 0}
    
    all_sizes = df['Size'].unique().tolist()
    sizes_with_stock = df[df['Tồn hiện tại'] > 0]['Size'].unique().tolist()
    
    return {
        'skc': skc,
        'sizes': sorted(all_sizes),
        'sizes_with_stock': sorted(sizes_with_stock),
        'total_stock': df['Tồn hiện tại'].sum()
    }


def get_top_stores_by_category(
    store_profiles: pd.DataFrame,
    category: str,
    top_n: int = 3
) -> pd.DataFrame:
    """
    Top N store bán chạy nhất theo category (MOH thấp nhất).
    """
    moh_col = f'MOH_{category}'
    if moh_col not in store_profiles.columns:
        return pd.DataFrame()
    
    df = store_profiles[store_profiles[moh_col].notna()].copy()
    df = df.sort_values(moh_col, ascending=True).head(top_n)
    
    cols = ['Store ID', 'Cửa hàng', 'Vùng miền', moh_col, f'Bán TB_{category}']
    cols = [c for c in cols if c in df.columns]
    return df[cols]


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================

def process_all_data(
    store_files: Dict[str, str],
    warehouse_files: Dict[str, str],
    season: Optional[bool] = None
) -> Dict[str, pd.DataFrame]:
    """
    Xử lý toàn bộ dữ liệu và tạo các profiles.
    
    Args:
        store_files: Dict mapping loại hàng -> filepath cho cửa hàng
        warehouse_files: Dict mapping loại hàng -> filepath cho kho
    
    Returns:
        Dict chứa các DataFrame:
        - df_stores: Dữ liệu cửa hàng đã xử lý
        - df_warehouse: Dữ liệu kho đã xử lý
        - df_broken: Broken Index cho tất cả SKC
        - store_profiles: Bảng tổng hợp cửa hàng
        - warehouse_sku: View SKU kho
        - warehouse_skc: View SKC kho
        - system_sku_profiles: SKU profiles toàn hệ thống
        - system_skc_profiles: SKC profiles toàn hệ thống
    """
    # Load và concat các file cửa hàng
    store_dfs = []
    for category, filepath in store_files.items():
        is_accessory = category.lower() in ['accessories', 'phụ kiện', 'phu_kien']
        season_to_use = season if season is not None else is_accessory
        df = load_single_file(filepath, file_type='store', season=season_to_use)
        store_dfs.append(df)
    
    df_stores = concat_files(store_dfs)
    
    # Load và concat các file kho
    warehouse_dfs = []
    for category, filepath in warehouse_files.items():
        df = load_single_file(filepath, file_type='warehouse')
        warehouse_dfs.append(df)
    
    df_warehouse = concat_files(warehouse_dfs)
    
    # Tính Broken Index
    df_broken = calculate_broken_index_all(df_stores, df_warehouse)
    
    # Tạo các profiles
    store_profiles = create_store_profiles(df_stores, df_broken)
    warehouse_sku = create_warehouse_sku_view(df_warehouse)
    warehouse_skc = create_warehouse_skc_view(df_warehouse)
    system_sku_profiles = create_system_sku_profiles(df_stores)
    system_skc_profiles = create_system_skc_profiles(df_stores, df_broken)
    
    return {
        'df_stores': df_stores,
        'df_warehouse': df_warehouse,
        'df_broken': df_broken,
        'store_profiles': store_profiles,
        'warehouse_sku': warehouse_sku,
        'warehouse_skc': warehouse_skc,
        'system_sku_profiles': system_sku_profiles,
        'system_skc_profiles': system_skc_profiles
    }


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_all_profiles(
    data: Dict[str, pd.DataFrame],
    output_dir: str = '.'
) -> List[str]:
    """
    Xuất tất cả profiles ra file CSV.
    
    Returns:
        List các filepath đã xuất
    """
    import os
    
    exported_files = []
    
    file_mapping = {
        'df_stores': 'processed_stores.csv',
        'df_warehouse': 'processed_warehouse.csv',
        'df_broken': 'broken_index.csv',
        'store_profiles': 'store_profiles.csv',
        'warehouse_sku': 'warehouse_sku.csv',
        'warehouse_skc': 'warehouse_skc.csv',
        'system_sku_profiles': 'system_sku_profiles.csv',
        'system_skc_profiles': 'system_skc_profiles.csv'
    }
    
    for key, filename in file_mapping.items():
        if key in data and data[key] is not None:
            filepath = os.path.join(output_dir, filename)
            data[key].to_csv(filepath, index=False, encoding='utf-8-sig')
            exported_files.append(filepath)
            print(f"   ✓ Đã xuất: {filename}")
    
    return exported_files