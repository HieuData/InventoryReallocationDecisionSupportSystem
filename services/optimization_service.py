"""
Optimization Service
Orchestrator để chạy toàn bộ quy trình tối ưu hóa.
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from core.data_processor import (
    load_single_file,
    concat_files,
    concat_files,
    calculate_broken_index_all,
    create_store_profiles,
    export_all_profiles
)
from core.optimizer import InventoryOptimizer
from config.settings import (
    MOH_THRESHOLD_LOW, MOH_THRESHOLD_HIGH, MOH_TARGET
)
def run_optimization(
    store_files: List[str],
    warehouse_files: List[str],
    output_dir: str = './output',
    time_limit: int = 300,
    gap: float = 0.05,
    season: Optional[bool] = None
) -> Dict:
    """
    Chạy toàn bộ quy trình tối ưu hóa.
    
    Args:
        store_files: List đường dẫn file CSV cửa hàng
        warehouse_files: List đường dẫn file CSV kho
        output_dir: Thư mục xuất kết quả
        time_limit: Giới hạn thời gian solve (seconds)
        gap: Optimality gap
    
    Returns:
        Dict chứa kết quả và metrics
    
    Example:
        result = run_optimization(
            store_files=[
                'Cua_Hang_Giay.csv',
                'Cua_Hang_Quan_Ao.csv',
                'Cua_Hang_Phu_Kien.csv'
            ],
            warehouse_files=[
                'Kho_Giay.csv',
                'Kho_Quan_Ao.csv',
                'Kho_Phu_Kien.csv'
            ],
            output_dir='./output'
        )
        print(result['summary'])
        print(result['reallocation_plan'])
    """
    
    print("=" * 60)
    print("INVENTORY OPTIMIZATION SERVICE")
    print("=" * 60)
    
    # Tạo output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # =========================================================================
    # STEP 1: Load và xử lý dữ liệu
    # =========================================================================
    print("\n[Step 1] Loading data...")

    store_dfs = [load_single_file(f, 'store', season=season) for f in store_files]
    wh_dfs = [load_single_file(f, 'warehouse') for f in warehouse_files]
    
    df_stores = concat_files(store_dfs)
    print(df_stores['Demand'].sum(), df_stores['Supply'].sum())
    df_warehouse = concat_files(wh_dfs)
    
    print(f"   ✓ Stores: {len(df_stores)} rows, {df_stores['Mã cửa hàng'].nunique()} stores")
    print(f"   ✓ Warehouse: {len(df_warehouse)} rows")
    
    # =========================================================================
    # STEP 2: Tính toán profiles và broken index
    # =========================================================================
    print("\n[Step 2] Calculating profiles...")
    
    df_broken = calculate_broken_index_all(df_stores, df_warehouse)
    store_profiles = create_store_profiles(df_stores, df_broken)
    
    print(f"   ✓ Broken index: {len(df_broken)} store-SKC combinations")
    print(f"   ✓ Broken SKCs: {df_broken['Is Broken'].sum()}")
    
    # =========================================================================
    # STEP 3: Chạy optimizer
    # =========================================================================
    print("\n[Step 3] Running optimization...")
    
    optimizer = InventoryOptimizer(
        df_stores=df_stores,
        df_warehouse=df_warehouse,
        df_broken=df_broken,
        store_profiles=store_profiles
    )
    
    solve_result = optimizer.solve(time_limit=time_limit, gap=gap)
    
    # =========================================================================
    # STEP 4: Xuất kết quả
    # =========================================================================
    print("\n[Step 4] Exporting results...")
    
    # Export data profiles
    data = {
        'df_stores': df_stores,
        'df_warehouse': df_warehouse,
        'df_broken': df_broken,
        'store_profiles': store_profiles
    }
    export_all_profiles(data, output_dir)
    
    # Export optimization results
    optimizer.export_results(output_dir)

    # Export diagnostic data
    print("\n[Step 4.5] Exporting diagnostics...")

    # 1. Export model LP file
    try:
        print("   [1/3] Exporting model.lp...")
        lp_path = optimizer.export_model_lp(output_dir)
        if os.path.exists(lp_path):
            size = os.path.getsize(lp_path)
            print(f"   ✓ Exported: model.lp ({size:,} bytes)")
        else:
            print(f"   ⚠ model.lp was not created")
    except Exception as e:
        print(f"   ⚠ Error exporting model.lp: {e}")
        with open(os.path.join(output_dir, 'model.lp'), 'w') as f:
            f.write(f"\\* Export failed: {e} *\\\n")

    # 2. Export unused variables (limit to first 10000 rows)
    try:
        print("   [2/3] Checking unused variables...")
        df_unused = optimizer.check_unused_variables()
        unused_path = os.path.join(output_dir, 'diagnostic_unused_vars.csv')

        if 'error' in df_unused.columns:
            print(f"   ⚠ {df_unused['error'].iloc[0]}")
            df_unused.to_csv(unused_path, index=False, encoding='utf-8-sig')
        elif 'message' in df_unused.columns:
            print(f"   ℹ {df_unused['message'].iloc[0]}")
            df_unused.to_csv(unused_path, index=False, encoding='utf-8-sig')
        else:
            # Limit to 10000 rows to avoid memory issues
            rows_to_export = min(len(df_unused), 10000)
            df_unused.head(rows_to_export).to_csv(unused_path, index=False, encoding='utf-8-sig')
            if len(df_unused) > 10000:
                print(f"   ✓ Exported: diagnostic_unused_vars.csv ({rows_to_export:,} of {len(df_unused):,} rows)")
            else:
                print(f"   ✓ Exported: diagnostic_unused_vars.csv ({rows_to_export:,} rows)")
    except Exception as e:
        print(f"   ⚠ Error checking unused variables: {e}")
        pd.DataFrame({'error': [str(e)]}).to_csv(
            os.path.join(output_dir, 'diagnostic_unused_vars.csv'),
            index=False, encoding='utf-8-sig'
        )

    # 3. Export violated constraints (limit to first 10000 rows)
    try:
        print("   [3/3] Checking violated constraints...")
        df_violated = optimizer.check_violated_constraints()
        violated_path = os.path.join(output_dir, 'diagnostic_violated_constraints.csv')

        if 'error' in df_violated.columns:
            print(f"   ⚠ {df_violated['error'].iloc[0]}")
            df_violated.to_csv(violated_path, index=False, encoding='utf-8-sig')
        elif 'message' in df_violated.columns:
            print(f"   ℹ {df_violated['message'].iloc[0]}")
            df_violated.to_csv(violated_path, index=False, encoding='utf-8-sig')
        else:
            # Limit to 10000 rows
            rows_to_export = min(len(df_violated), 10000)
            df_violated.head(rows_to_export).to_csv(violated_path, index=False, encoding='utf-8-sig')
            if len(df_violated) > 10000:
                print(f"   ✓ Exported: diagnostic_violated_constraints.csv ({rows_to_export:,} of {len(df_violated):,} rows)")
            else:
                print(f"   ✓ Exported: diagnostic_violated_constraints.csv ({rows_to_export:,} rows)")
    except Exception as e:
        print(f"   ⚠ Error checking violated constraints: {e}")
        pd.DataFrame({'error': [str(e)]}).to_csv(
            os.path.join(output_dir, 'diagnostic_violated_constraints.csv'),
            index=False, encoding='utf-8-sig'
        )

    print("   ℹ Diagnostics export completed")
    
    # =========================================================================
    # STEP 5: Tổng kết
    # =========================================================================
    print("\n" + "=" * 60)
    print("OPTIMIZATION COMPLETE")
    print("=" * 60)
    
    summary = optimizer.get_summary()
    for key, val in summary.items():
        print(f"   {key}: {val}")
    
    return {
        'status': solve_result['status'],
        'summary': summary,
        'reallocation_plan': optimizer.get_reallocation_plan(),
        'store_impact': optimizer.get_store_impact(),
        'data': {
            'df_stores': df_stores,
            'df_warehouse': df_warehouse,
            'df_broken': df_broken,
            'store_profiles': store_profiles
        }
    }


def run_optimization_from_dataframes(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame,
    df_broken: pd.DataFrame,
    store_profiles: pd.DataFrame,
    output_dir: str = './output',
    time_limit: int = 300,
    gap: float = 0.05,
) -> Dict:
    """
    Chạy tối ưu hóa từ DataFrames đã có sẵn.
    Phù hợp cho web app khi data đã được load trước.
    
    Example:
        # Trong web app
        result = run_optimization_from_dataframes(
            df_stores=session['df_stores'],
            df_warehouse=session['df_warehouse'],
            df_broken=session['df_broken'],
            store_profiles=session['store_profiles']
        )
    """
    
    print("=" * 60)
    print("INVENTORY OPTIMIZATION (FROM DATAFRAMES)")
    print("=" * 60)
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n[Step 1] Initializing optimizer...")
    optimizer = InventoryOptimizer(
        df_stores=df_stores,
        df_warehouse=df_warehouse,
        df_broken=df_broken,
        store_profiles=store_profiles
    )
    
    print("\n[Step 2] Solving...")
    solve_result = optimizer.solve(time_limit=time_limit, gap=gap)
    
    print("\n[Step 3] Exporting...")
    optimizer.export_results(output_dir)
    
    summary = optimizer.get_summary()
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    
    return {
        'status': solve_result['status'],
        'summary': summary,
        'reallocation_plan': optimizer.get_reallocation_plan(),
        'store_impact': optimizer.get_store_impact()
    }

def calculate_after_state(
    df_stores: pd.DataFrame,
    df_warehouse: pd.DataFrame,
    reallocation_plan: pd.DataFrame
) -> dict:
    """
    Apply reallocation plan để tính trạng thái sau điều chuyển.
    """
    df_stores_after = df_stores.copy()
    df_warehouse_after = df_warehouse.copy()
    
    if reallocation_plan.empty:
        return {
            'df_stores_after': df_stores_after,
            'df_warehouse_after': df_warehouse_after
        }
    
    # Apply từng lệnh điều chuyển
    for _, row in reallocation_plan.iterrows():
        source = row['Nguồn']
        dest = row['Đích']
        sku = row['SKU_ID']
        qty = row['Số lượng']
        
        # Giảm tồn nguồn
        if source == 'Kho':
            mask = df_warehouse_after['SKU_ID'] == sku
            df_warehouse_after.loc[mask, 'Tồn hiện tại'] -= qty
        else:
            mask = (df_stores_after['Mã cửa hàng'] == source) & (df_stores_after['SKU_ID'] == sku)
            df_stores_after.loc[mask, 'Tồn hiện tại'] -= qty
        
        # Tăng tồn đích
        mask = (df_stores_after['Mã cửa hàng'] == dest) & (df_stores_after['SKU_ID'] == sku)
        df_stores_after.loc[mask, 'Tồn hiện tại'] += qty
    
    # Recalculate MOH, Demand, Supply
    df_stores_after['MOH'] = (
        df_stores_after['Tồn hiện tại'] / 
        np.maximum(1, df_stores_after['Bán TB'])
    ).round(1)
    
    df_stores_after['MOH Rating'] = np.where(
        df_stores_after['MOH'] < MOH_THRESHOLD_LOW, 'Tốt',
        np.where(df_stores_after['MOH'] <= MOH_THRESHOLD_HIGH, 'Trung bình', 'Kém')
    )

    df_stores_after['Demand'] = np.maximum(0, MOH_TARGET * df_stores_after['Bán TB'] - df_stores_after['Tồn hiện tại'])
    df_stores_after['Supply'] = np.maximum(0, df_stores_after['Tồn hiện tại'] - MOH_TARGET * df_stores_after['Bán TB'])

    df_stores_after['Demand'] = np.ceil(df_stores_after['Demand']).astype(int)
    df_stores_after['Supply'] = np.floor(df_stores_after['Supply']).astype(int)

    return {
        'df_stores_after': df_stores_after,
        'df_warehouse_after': df_warehouse_after
    }

# =============================================================================
# CLI USAGE
# =============================================================================

if __name__ == "__main__":
    # Example usage
    result = run_optimization(
        store_files=['Cua_Hang_Giay_Bang_Hien_Thi.csv'],
        warehouse_files=['Kho_Giay_Bang_Hien_Thi.csv'],
        output_dir='./output'
    )
