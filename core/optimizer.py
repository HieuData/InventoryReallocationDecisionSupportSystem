"""
Inventory Optimization LP Solver
Mô hình tối ưu hóa điều phối hàng tồn kho giữa các cửa hàng và kho.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from pulp import (
    LpProblem, LpMaximize, LpVariable, LpInteger, LpBinary,
    lpSum, LpStatus, value, PULP_CBC_CMD
)

from config.settings import (
    MOH_TARGET, BROKEN_THRESHOLD, HEAVY_BROKEN_THRESHOLD,
    MAX_OUTBOUND_ROUTES, MAX_INBOUND_ROUTES, MIN_SKU_PER_SHIPMENT,
    COLD_RESTRICTED_REGIONS, WEIGHT_BASE, WEIGHT_DEST_BROKEN,
    WEIGHT_SOURCE_BROKEN, WEIGHT_WAREHOUSE, SOLVER_TIME_LIMIT,
    SOLVER_GAP, BIG_M
)


class InventoryOptimizer:
    """
    LP-based Inventory Optimization Solver.
    
    Tối ưu hóa điều phối hàng giữa:
    - Kho → Cửa hàng
    - Cửa hàng → Cửa hàng
    
    Mục tiêu: Cân bằng tồn kho, giảm gãy size, đáp ứng demand.
    """
    
    def __init__(
        self,
        df_stores: pd.DataFrame,
        df_warehouse: pd.DataFrame,
        df_broken: pd.DataFrame,
        store_profiles: pd.DataFrame
    ):
        """
        Khởi tạo optimizer với dữ liệu đầu vào.
        
        Args:
            df_stores: DataFrame cửa hàng (từ concat_files)
            df_warehouse: DataFrame kho (từ concat_files)
            df_broken: DataFrame broken index (từ calculate_broken_index_all)
            store_profiles: DataFrame store profiles (từ create_store_profiles)
        """
        self.df_stores = df_stores.copy()
        self.df_warehouse = df_warehouse.copy()
        self.df_broken = df_broken.copy()
        self.store_profiles = store_profiles.copy()
        
        # Model và kết quả
        self.model = None
        self.variables = {}
        self.solution = None
        self.status = None
        
        # Tập chỉ số
        self.stores = None
        self.skus = None
        self.skcs = None
        
        # Tham số tính toán
        self.supply = {}
        self.demand = {}
        self.warehouse_stock = {}
        self.is_broken = {}
        self.heavy_broken_stores = set()
        self.best_stores = {}
        self.skc_limit = {}
        self.skc_current = {}
        self.store_skcs = {}  # SKC hiện có tại mỗi store
        self.sku_to_skc = {}
        self.sku_attr = {}
        self.store_region = {}
        self.has_stock = {}
        
        # Khởi tạo
        self._prepare_indices()
        self._prepare_parameters()
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def _prepare_indices(self):
        """Chuẩn bị tập chỉ số."""
        self.stores = self.df_stores['Mã cửa hàng'].unique().tolist()
        self.skus = self.df_stores['SKU_ID'].unique().tolist()
        self.skcs = self.df_stores['Mã màu'].unique().tolist()
        
        print(f"[Init] Stores: {len(self.stores)}, SKUs: {len(self.skus)}, SKCs: {len(self.skcs)}")
    
    def _prepare_parameters(self):
        """Chuẩn bị tham số từ dữ liệu."""
        
        # 1. Supply & Demand từ df_stores
        for _, row in self.df_stores.iterrows():
            store = row['Mã cửa hàng']
            sku = row['SKU_ID']
            
            # Mới (Đúng): Cộng dồn (Accumulate)
            self.supply[(store, sku)] = self.supply.get((store, sku), 0) + row.get('Supply', 0)
            self.demand[(store, sku)] = self.demand.get((store, sku), 0) + row.get('Demand', 0)
            
            # Logic Has Stock: Nếu bất kỳ dòng nào có tồn > 0 thì coi là có tồn
            current_stock_flag = 1 if row.get('Tồn hiện tại', 0) > 0 else 0
            self.has_stock[(store, sku)] = max(self.has_stock.get((store, sku), 0), current_stock_flag)
            
            # Mapping SKU → SKC (Giữ nguyên vì SKU_ID là duy nhất mapping với SKC)
            self.sku_to_skc[sku] = row['Mã màu']
            self.sku_attr[sku] = row.get('Thuộc tính', '')
        
        # 2. Warehouse stock
        for _, row in self.df_warehouse.iterrows():
            sku = row['SKU_ID']
            self.warehouse_stock[sku] = row.get('Tồn hiện tại', 0)
        
        # 3. Broken index
        for _, row in self.df_broken.iterrows():
            store = row['Mã cửa hàng']
            skc = row['Mã màu']
            self.is_broken[(store, skc)] = row.get('Is Broken', 0)
        
        # 4. Heavy broken stores (>60% SKC gãy)
        store_broken_stats = self.df_broken.groupby('Mã cửa hàng').agg({
            'Is Broken': ['sum', 'count']
        }).reset_index()
        store_broken_stats.columns = ['Mã cửa hàng', 'broken_count', 'total_count']
        store_broken_stats['broken_ratio'] = store_broken_stats['broken_count'] / store_broken_stats['total_count']
        
        self.heavy_broken_stores = set(
            store_broken_stats[store_broken_stats['broken_ratio'] > HEAVY_BROKEN_THRESHOLD]['Mã cửa hàng'].tolist()
        )
        print(f"[Init] Heavy broken stores: {len(self.heavy_broken_stores)}")
        
        # 5. Best stores theo category
        for cat in ['Giày dép', 'Quần áo', 'Phụ kiện']:
            col = f'Bán TB_{cat}'
            if col in self.store_profiles.columns:
                best = self.store_profiles.nlargest(1, col)
                if not best.empty:
                    self.best_stores[cat] = best.iloc[0]['Store ID']
        print(f"[Init] Best stores: {self.best_stores}")
        
        # 6. SKC Limit và Current
        for _, row in self.store_profiles.iterrows():
            store = row['Store ID']
            self.skc_limit[store] = row.get('SKC Limit', 999)
            self.skc_current[store] = row.get('SKC Trưng bày', 0)
        
        # 7. Store regions
        store_regions = self.df_stores[['Mã cửa hàng', 'Vùng miền']].drop_duplicates()
        for _, row in store_regions.iterrows():
            self.store_region[row['Mã cửa hàng']] = row['Vùng miền']
        
        # 8. SKC hiện có tại mỗi store
        for store in self.stores:
            store_data = self.df_stores[
                (self.df_stores['Mã cửa hàng'] == store) & 
                (self.df_stores['Tồn hiện tại'] > 0)
            ]
            self.store_skcs[store] = set(store_data['Mã màu'].unique())
        
        print("[Init] Parameters prepared.")
    
    # =========================================================================
    # MODEL BUILDING
    # =========================================================================
    
    def _build_model(self):
        """Xây dựng mô hình LP."""
        
        print("[Build] Creating LP model...")
        self.model = LpProblem("Inventory_Reallocation", LpMaximize)
        
        # -----------------------------------------------------------------
        # DECISION VARIABLES
        # -----------------------------------------------------------------
        
        # x[i,j,p]: Số lượng SKU p chuyển từ store i → store j
        self.variables['x'] = {}
        for i in self.stores:
            for j in self.stores:
                if i != j:
                    for p in self.skus:
                        supply_ip = self.supply.get((i, p), 0)
                        demand_jp = self.demand.get((j, p), 0)
                        if supply_ip > 0 and demand_jp > 0:
                            self.variables['x'][(i, j, p)] = LpVariable(
                                f"x_{i}_{j}_{p}", 
                                lowBound=0, 
                                cat=LpInteger
                            )
        
        # y[j,p]: Số lượng SKU p chuyển từ kho → store j
        self.variables['y'] = {}
        for j in self.stores:
            for p in self.skus:
                wh_stock = self.warehouse_stock.get(p, 0)
                demand_jp = self.demand.get((j, p), 0)
                if wh_stock > 0 and demand_jp > 0:
                    self.variables['y'][(j, p)] = LpVariable(
                        f"y_{j}_{p}", 
                        lowBound=0, 
                        cat=LpInteger
                    )
        
        # z_store[i,j]: Binary - có route từ store i → j không
        self.variables['z_store'] = {}
        for i in self.stores:
            for j in self.stores:
                if i != j:
                    # Chỉ tạo nếu có ít nhất 1 cặp (i,j,p) khả thi
                    has_route = any(
                        (i, j, p) in self.variables['x'] for p in self.skus
                    )
                    if has_route:
                        self.variables['z_store'][(i, j)] = LpVariable(
                            f"z_store_{i}_{j}", 
                            cat=LpBinary
                        )
        
        # z_wh[j]: Binary - có route từ kho → j không
        self.variables['z_wh'] = {}
        for j in self.stores:
            has_route = any((j, p) in self.variables['y'] for p in self.skus)
            if has_route:
                self.variables['z_wh'][j] = LpVariable(
                    f"z_wh_{j}", 
                    cat=LpBinary
                )
        
        # u[j,k]: Binary - SKC k được nhập MỚI vào store j
        self.variables['u'] = {}
        for j in self.stores:
            for k in self.skcs:
                # Chỉ tạo cho SKC mà store chưa có
                if k not in self.store_skcs.get(j, set()):
                    self.variables['u'][(j, k)] = LpVariable(
                        f"u_{j}_{k}", 
                        cat=LpBinary
                    )
        
        print(f"[Build] Variables: x={len(self.variables['x'])}, y={len(self.variables['y'])}, "
              f"z_store={len(self.variables['z_store'])}, z_wh={len(self.variables['z_wh'])}, "
              f"u={len(self.variables['u'])}")
    
    def _add_objective(self):
        """Thêm hàm mục tiêu."""
        
        print("[Build] Adding objective function...")
        
        obj_terms = []
        
        # Warehouse → Store
        for (j, p), var in self.variables['y'].items():
            skc = self.sku_to_skc.get(p, '')
            is_broken_j = self.is_broken.get((j, skc), 0)
            weight = WEIGHT_WAREHOUSE + WEIGHT_DEST_BROKEN * is_broken_j
            obj_terms.append(weight * var)
        
        # Store → Store
        for (i, j, p), var in self.variables['x'].items():
            skc = self.sku_to_skc.get(p, '')
            is_broken_i = self.is_broken.get((i, skc), 0)
            is_broken_j = self.is_broken.get((j, skc), 0)
            weight = WEIGHT_BASE + WEIGHT_DEST_BROKEN * is_broken_j + WEIGHT_SOURCE_BROKEN * is_broken_i
            obj_terms.append(weight * var)
        
        self.model += lpSum(obj_terms), "Total_Weighted_Transfer"
    
    def _add_constraints(self):
        """Thêm tất cả ràng buộc."""
        
        print("[Build] Adding constraints...")
        
        self._add_c1_warehouse_limit()
        self._add_c2_supply_demand_balance()
        self._add_c3_logistics()
        self._add_c4_skc_limit()
        self._add_c5_seasonal()
        self._add_c6_no_new_broken()
        self._add_c8_heavy_broken_to_best()
    
    def _add_c1_warehouse_limit(self):
        """C1: Giới hạn tồn kho."""
        
        for p in self.skus:
            wh_stock = self.warehouse_stock.get(p, 0)
            if wh_stock > 0:
                terms = [
                    self.variables['y'][(j, p)]
                    for j in self.stores
                    if (j, p) in self.variables['y']
                ]
                if terms:
                    self.model += lpSum(terms) <= wh_stock, f"C1_wh_limit_{p}"
    
    def _add_c2_supply_demand_balance(self):
        """C2: Cân đối cung - cầu."""
        
        # Demand limit tại mỗi store
        for j in self.stores:
            for p in self.skus:
                demand_jp = self.demand.get((j, p), 0)
                if demand_jp > 0:
                    terms = []
                    
                    # Từ kho
                    if (j, p) in self.variables['y']:
                        terms.append(self.variables['y'][(j, p)])
                    
                    # Từ các store khác
                    for i in self.stores:
                        if i != j and (i, j, p) in self.variables['x']:
                            terms.append(self.variables['x'][(i, j, p)])
                    
                    if terms:
                        self.model += lpSum(terms) <= demand_jp, f"C2_demand_{j}_{p}"
        
        # Supply limit từ mỗi store
        for i in self.stores:
            for p in self.skus:
                supply_ip = self.supply.get((i, p), 0)
                if supply_ip > 0:
                    terms = [
                        self.variables['x'][(i, j, p)]
                        for j in self.stores
                        if (i, j, p) in self.variables['x']
                    ]
                    if terms:
                        self.model += lpSum(terms) <= supply_ip, f"C2_supply_{i}_{p}"
    
    def _add_c3_logistics(self):
        """C3: Ràng buộc logistics."""
        
        # Max outbound routes per store
        for i in self.stores:
            terms = [
                self.variables['z_store'][(i, j)]
                for j in self.stores
                if (i, j) in self.variables['z_store']
            ]
            if terms:
                self.model += lpSum(terms) <= MAX_OUTBOUND_ROUTES, f"C3_max_out_{i}"
        
        # Max inbound routes per store
        for j in self.stores:
            terms = []
            for i in self.stores:
                if (i, j) in self.variables['z_store']:
                    terms.append(self.variables['z_store'][(i, j)])
            if j in self.variables['z_wh']:
                terms.append(self.variables['z_wh'][j])
            
            if terms:
                self.model += lpSum(terms) <= MAX_INBOUND_ROUTES, f"C3_max_in_{j}"
        
        # Min SKU per shipment (Big-M linking)
        for (i, j), z_var in self.variables['z_store'].items():
            sku_terms = [
                self.variables['x'][(i, j, p)]
                for p in self.skus
                if (i, j, p) in self.variables['x']
            ]
            if sku_terms:
                # Nếu z = 1 thì tổng SKU >= MIN_SKU_PER_SHIPMENT
                self.model += lpSum(sku_terms) >= MIN_SKU_PER_SHIPMENT * z_var, f"C3_min_sku_{i}_{j}"
                # Nếu có transfer thì z = 1
                self.model += lpSum(sku_terms) <= BIG_M * z_var, f"C3_link_{i}_{j}"
        
        for j, z_var in self.variables['z_wh'].items():
            sku_terms = [
                self.variables['y'][(j, p)]
                for p in self.skus
                if (j, p) in self.variables['y']
            ]
            if sku_terms:
                self.model += lpSum(sku_terms) >= MIN_SKU_PER_SHIPMENT * z_var, f"C3_min_sku_wh_{j}"
                self.model += lpSum(sku_terms) <= BIG_M * z_var, f"C3_link_wh_{j}"
    
    def _add_c4_skc_limit(self):
        """C4: Giới hạn sức chứa SKC."""
        
        for j in self.stores:
            limit = self.skc_limit.get(j, 999)
            current = len(self.store_skcs.get(j, set()))  # Số SKC hiện có
            available = limit - current
            
            if available <= 0:
                # Store đã đầy → không nhận SKC mới
                for k in self.skcs:
                    if (j, k) in self.variables['u']:
                        self.model += self.variables['u'][(j, k)] == 0, f"C4_full_{j}_{k}"
            else:
                # Tổng SKC mới <= available
                terms = [
                    self.variables['u'][(j, k)]
                    for k in self.skcs
                    if (j, k) in self.variables['u']
                ]
                if terms:
                    self.model += lpSum(terms) <= available, f"C4_limit_{j}"
            
            # Linking: u[j,k] = 1 nếu có nhận SKU thuộc SKC k (mà store chưa có)
            for k in self.skcs:
                if (j, k) in self.variables['u']:
                    # Lấy các SKU thuộc SKC k
                    skus_in_k = [p for p, skc in self.sku_to_skc.items() if skc == k]
                    
                    terms = []
                    for p in skus_in_k:
                        if (j, p) in self.variables['y']:
                            terms.append(self.variables['y'][(j, p)])
                        for i in self.stores:
                            if (i, j, p) in self.variables['x']:
                                terms.append(self.variables['x'][(i, j, p)])
                    
                    if terms:
                        # Nếu có nhận bất kỳ SKU nào của SKC k → u = 1
                        self.model += lpSum(terms) <= BIG_M * self.variables['u'][(j, k)], f"C4_link_{j}_{k}"
    
    def _add_c5_seasonal(self):
        """C5: Ràng buộc mùa vụ - không chuyển hàng Lạnh về MT/MN."""
        
        for j in self.stores:
            region = self.store_region.get(j, '')
            if any(r in region for r in COLD_RESTRICTED_REGIONS):
                for p in self.skus:
                    attr = self.sku_attr.get(p, '')
                    if attr == 'Lạnh':
                        # Từ kho
                        if (j, p) in self.variables['y']:
                            self.model += self.variables['y'][(j, p)] == 0, f"C5_cold_wh_{j}_{p}"
                        # Từ store khác
                        for i in self.stores:
                            if (i, j, p) in self.variables['x']:
                                self.model += self.variables['x'][(i, j, p)] == 0, f"C5_cold_{i}_{j}_{p}"
    
    def _add_c6_no_new_broken(self):
        """
        C6: Không gây gãy size mới.
        
        Cách tiếp cận: Với mỗi store i, nếu xuất toàn bộ supply của 1 SKU
        mà không xuất hết các size khác của SKC đó → có thể gây gãy.
        
        Đơn giản hóa: Nếu store i có SKC k không gãy, và xuất 1 size bất kỳ,
        phải giữ lại ít nhất 1 đơn vị hoặc xuất hết toàn bộ SKC.
        
        Tạm thời: Chỉ cho phép xuất từ store đã gãy hoặc xuất hết SKC.
        """
        # Tạm thời bỏ qua ràng buộc phức tạp này
        # Có thể implement sau khi có ràng buộc chuyển theo SKC đầy đủ
        pass

    # def _add_c6_no_new_broken(self):
    #     """
    #     C6: Không tạo ra broken mới tại destination
    #     """
    #     for j in self.stores:
    #         for skc in self.skcs:
    #             is_broken_before = self.is_broken.get((j, skc), 0)
                
    #             if is_broken_before == 0:  # Chưa broken
    #                 skus_in_skc = [p for p in self.skus if self.sku_to_skc.get(p) == skc]
                    
    #                 # ✅ SỬA: Dùng df_stores thay vì stores_data
    #                 sizes_with_stock = 0
    #                 for p in skus_in_skc:
    #                     # Check trong df_stores
    #                     mask = (self.df_stores['Mã cửa hàng'] == j) & (self.df_stores['SKU_ID'] == p)
    #                     if not self.df_stores[mask].empty:
    #                         stock = self.df_stores[mask]['Tồn hiện tại'].iloc[0]
    #                         if stock > 0:
    #                             sizes_with_stock += 1
                    
    #                 total_sizes = len(skus_in_skc)
                    
    #                 if sizes_with_stock == total_sizes:
    #                     for p in skus_in_skc:
    #                         if (j, p) in self.variables['y']:
    #                             self.model += self.variables['y'][(j, p)] == 0, f"no_new_broken_wh_{j}_{p}"
                            
    #                         for i in self.stores:
    #                             if i != j and (i, j, p) in self.variables['x']:
    #                                 self.model += self.variables['x'][(i, j, p)] == 0, f"no_new_broken_{i}_{j}_{p}"

    def _add_c8_heavy_broken_to_best(self):
        """C8: Store gãy nặng → chỉ chuyển về BestStore."""
        
        for i in self.heavy_broken_stores:
            for p in self.skus:
                # Xác định category của SKU
                skc = self.sku_to_skc.get(p, '')
                category = None
                if skc.startswith('5'):
                    category = 'Quần áo'
                elif skc.startswith('7'):
                    category = 'Giày dép'
                elif skc.startswith('9'):
                    category = 'Phụ kiện'
                
                best_store = self.best_stores.get(category, None)
                
                for j in self.stores:
                    if (i, j, p) in self.variables['x']:
                        if best_store and j != best_store:
                            # Không cho phép chuyển đến store khác BestStore
                            self.model += self.variables['x'][(i, j, p)] == 0, f"C8_heavy_{i}_{j}_{p}"
    
    # =========================================================================
    # SOLVING
    # =========================================================================
    
    def solve(self, time_limit: int = None, gap: float = None) -> dict:
        """
        Giải mô hình LP.
        
        Args:
            time_limit: Giới hạn thời gian (seconds)
            gap: Optimality gap cho phép
        
        Returns:
            dict với status, objective, và statistics
        """
        if self.model is None:
            self._build_model()
            self._add_objective()
            self._add_constraints()
        
        # Solver settings
        time_limit = time_limit or SOLVER_TIME_LIMIT
        gap = gap or SOLVER_GAP
        
        print(f"[Solve] Solving with time_limit={time_limit}s, gap={gap}...")
        
        solver = PULP_CBC_CMD(
            timeLimit=time_limit,
            gapRel=gap,
            msg=1
        )
        
        self.model.solve(solver)
        self.status = LpStatus[self.model.status]
        
        print(f"[Solve] Status: {self.status}")
        print(f"[Solve] Objective: {value(self.model.objective):.2f}")
        
        # Extract solution
        self._extract_solution()
        
        return {
            'status': self.status,
            'objective': value(self.model.objective),
            'num_transfers': len(self.solution) if self.solution is not None else 0
        }
    
    def _extract_solution(self):
        """Trích xuất kết quả từ solution."""
        
        if self.status != 'Optimal':
            self.solution = pd.DataFrame()
            return
        
        results = []
        
        # Store → Store transfers
        for (i, j, p), var in self.variables['x'].items():
            qty = value(var)
            if qty and qty > 0:
                skc = self.sku_to_skc.get(p, '')
                results.append({
                    'Nguồn': i,
                    'Vùng miền Nguồn': self.store_region.get(i, ''),
                    'Đích': j,
                    'Vùng miền Đích': self.store_region.get(j, ''),
                    'SKU_ID': p,
                    'SKC': skc,
                    'Thuộc tính': self.sku_attr.get(p, ''),
                    'Số lượng': int(qty),
                    'Loại': 'Chuyển cửa hàng'
                })
        
        # Warehouse → Store transfers
        for (j, p), var in self.variables['y'].items():
            qty = value(var)
            if qty and qty > 0:
                skc = self.sku_to_skc.get(p, '')
                results.append({
                    'Nguồn': 'Kho',
                    'Vùng miền Nguồn': '',
                    'Đích': j,
                    'Vùng miền Đích': self.store_region.get(j, ''),
                    'SKU_ID': p,
                    'SKC': skc,
                    'Thuộc tính': self.sku_attr.get(p, ''),
                    'Số lượng': int(qty),
                    'Loại': 'Chuyển từ kho'
                })
        
        self.solution = pd.DataFrame(results)
        print(f"[Solve] Extracted {len(self.solution)} transfer orders.")
    
    # =========================================================================
    # RESULTS
    # =========================================================================
    
    def get_reallocation_plan(self) -> pd.DataFrame:
        """Lấy kế hoạch điều phối."""
        return self.solution.copy() if self.solution is not None else pd.DataFrame()
    
    def get_summary(self) -> dict:
        """Lấy tổng kết kết quả."""
        
        if self.solution is None or self.solution.empty:
            return {'status': self.status, 'transfers': 0}
        # Basic stats from solution
        total_transfers = len(self.solution)
        total_quantity = int(self.solution['Số lượng'].sum()) if not self.solution.empty else 0
        store_to_store_count = len(self.solution[self.solution['Loại'] == 'Chuyển cửa hàng'])
        wh_to_store_count = len(self.solution[self.solution['Loại'] == 'Chuyển từ kho'])
        store_to_store_qty = int(self.solution[self.solution['Loại'] == 'Chuyển cửa hàng']['Số lượng'].sum()) if store_to_store_count > 0 else 0
        wh_to_store_qty = int(self.solution[self.solution['Loại'] == 'Chuyển từ kho']['Số lượng'].sum()) if wh_to_store_count > 0 else 0

        # Compute total demand before and unmet after allocations
        total_demand_before = sum(v for v in self.demand.values() if v is not None)
        total_demand_after = total_demand_before - total_quantity
        total_supply_before = sum(v for v in self.supply.values() if v is not None)
        total_supply_after = total_supply_before - total_quantity
        total_fulfilled = 0
        # iterate over demand keys (store, sku) to compute received
        for (store, sku), demand_val in self.demand.items():
            if not demand_val or demand_val <= 0:
                continue
            received = 0
            # from warehouse
            yvar = self.variables.get('y', {}).get((store, sku), None)
            if yvar is not None:
                received += value(yvar) or 0
            # from other stores
            for i in self.stores:
                if i == store:
                    continue
                xvar = self.variables.get('x', {}).get((i, store, sku), None)
                if xvar is not None:
                    received += value(xvar) or 0

            # cap by demand
            total_fulfilled += min(received, demand_val)

        total_unmet = max(0, total_demand_before - total_fulfilled)
        unmet_rate = (total_unmet / total_demand_before) if total_demand_before > 0 else 0.0

        summary = {
            'status': self.status,
            'objective': value(self.model.objective),
            'total_transfers': total_transfers,
            'total_quantity': total_quantity,
            'store_to_store': store_to_store_count,
            'warehouse_to_store': wh_to_store_count,
            'store_to_store_qty': store_to_store_qty,
            'warehouse_to_store_qty': wh_to_store_qty,
            'total_demand_before': int(total_demand_before),
            'total_demand_after': int(total_demand_after),
            'total_supply_before': int(total_supply_before),
            'total_supply_after': int(total_supply_after),
            'unmet_rate': round(float(unmet_rate), 4)
        }

        return summary
    
    def get_store_impact(self) -> pd.DataFrame:
        """Tính toán tác động lên từng store."""
        
        if self.solution is None or self.solution.empty:
            return pd.DataFrame()
        
        # Tính inbound và outbound cho mỗi store
        outbound = self.solution[self.solution['Nguồn'] != 'Kho'].groupby('Nguồn')['Số lượng'].sum()
        inbound = self.solution.groupby('Đích')['Số lượng'].sum()

        impact = pd.DataFrame({
            'Mã cửa hàng': self.stores
        })
        impact['Xuất đi'] = impact['Mã cửa hàng'].map(outbound).fillna(0).astype(int)
        impact['Nhận vào'] = impact['Mã cửa hàng'].map(inbound).fillna(0).astype(int)
        impact['Thay đổi'] = impact['Nhận vào'] - impact['Xuất đi']
        
        return impact
    
    def export_results(self, output_dir: str = '.') -> List[str]:
        """Xuất kết quả ra files."""
        
        import os
        exported = []
        
        # Reallocation plan
        if self.solution is not None and not self.solution.empty:
            path = os.path.join(output_dir, 'reallocation_plan.csv')
            self.solution.to_csv(path, index=False, encoding='utf-8-sig')
            exported.append(path)
            print(f"   ✓ Exported: reallocation_plan.csv")
        
        # Store impact
        impact = self.get_store_impact()
        if not impact.empty:
            path = os.path.join(output_dir, 'store_impact.csv')
            impact.to_csv(path, index=False, encoding='utf-8-sig')
            exported.append(path)
            print(f"   ✓ Exported: store_impact.csv")
        
        # Summary
        summary = self.get_summary()
        path = os.path.join(output_dir, 'optimization_summary.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("INVENTORY OPTIMIZATION SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            for key, val in summary.items():
                f.write(f"{key}: {val}\n")
        exported.append(path)
        print(f"   ✓ Exported: optimization_summary.txt")
        
        # Sensitivity report
        sensitivity = self.get_sensitivity_report()
        if sensitivity:
            path = os.path.join(output_dir, 'sensitivity_report.csv')
            # Gộp tất cả bảng vào 1 file
            with open(path, 'w', encoding='utf-8-sig') as f:
                for name, df in sensitivity.items():
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        f.write(f"\n{'='*60}\n")
                        f.write(f"{name}\n")
                        f.write(f"{'='*60}\n")
                        df.to_csv(f, index=False)
                        f.write("\n")
            exported.append(path)
            print(f"   ✓ Exported: sensitivity_report.csv")
        
        return exported

    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================

    def check_unused_variables(self) -> pd.DataFrame:
        """
        Kiểm tra biến không được sử dụng (value = 0 sau khi solve).

        Returns:
            DataFrame với các biến có giá trị = 0
        """
        if self.model is None:
            return pd.DataFrame({'error': ['Model not built yet']})

        if self.status != 'Optimal':
            return pd.DataFrame({'error': ['Model not solved optimally']})

        unused = []

        # Check x variables (store-to-store)
        for (i, j, p), var in self.variables['x'].items():
            val = value(var)
            if val == 0 or val is None:
                unused.append({
                    'Loại biến': 'x (Chuyển cửa hàng)',
                    'Tên biến': var.name,
                    'Nguồn': i,
                    'Đích': j,
                    'SKU': p,
                    'Giá trị': 0
                })

        # Check y variables (warehouse-to-store)
        for (j, p), var in self.variables['y'].items():
            val = value(var)
            if val == 0 or val is None:
                unused.append({
                    'Loại biến': 'y (Chuyển từ kho)',
                    'Tên biến': var.name,
                    'Nguồn': 'Kho',
                    'Đích': j,
                    'SKU': p,
                    'Giá trị': 0
                })

        df = pd.DataFrame(unused)

        if df.empty:
            return pd.DataFrame({'message': ['All variables are used (non-zero)']})

        return df

    def check_violated_constraints(self) -> pd.DataFrame:
        """
        Kiểm tra ràng buộc bị VI PHẠM (LHS không thỏa mãn điều kiện với RHS).

        Returns:
            DataFrame với các ràng buộc violated (nếu có)
        """
        if self.model is None:
            return pd.DataFrame({'error': ['Model not built yet']})

        if self.status == 'Infeasible':
            return pd.DataFrame({'error': ['Model is infeasible - constraints are violated but cannot identify which ones']})

        if self.status != 'Optimal':
            return pd.DataFrame({'error': ['Model not solved optimally']})

        violated = []

        for name, constraint in self.model.constraints.items():
            # Calculate LHS (Left Hand Side)
            lhs = sum(
                var.varValue * coef
                for var, coef in constraint.items()
                if var.varValue is not None
            )

            rhs = -constraint.constant  # RHS (Right Hand Side)
            sense = constraint.sense  # -1 (<=), 0 (==), 1 (>=)

            # Check if violated
            is_violated = False
            violation = 0

            if sense == -1:  # <= constraint
                if lhs > rhs + 1e-6:
                    is_violated = True
                    violation = lhs - rhs
            elif sense == 0:  # == constraint
                if abs(lhs - rhs) > 1e-6:
                    is_violated = True
                    violation = abs(lhs - rhs)
            elif sense == 1:  # >= constraint
                if lhs < rhs - 1e-6:
                    is_violated = True
                    violation = rhs - lhs

            if is_violated:
                sense_str = '<=' if sense == -1 else ('==' if sense == 0 else '>=')
                violated.append({
                    'Tên ràng buộc': name,
                    'Loại': sense_str,
                    'LHS': round(lhs, 2),
                    'RHS': round(rhs, 2),
                    'Vi phạm': round(violation, 6),
                    'Trạng thái': 'VI PHẠM'
                })

        df = pd.DataFrame(violated)

        if df.empty:
            return pd.DataFrame({'message': ['No violated constraints (model is feasible)']})

        return df

    def export_model_lp(self, output_dir: str = '.') -> str:
        """
        Export mô hình LP ra file .lp format (human-readable).

        Args:
            output_dir: Thư mục lưu file

        Returns:
            Đường dẫn đến file .lp
        """
        import os

        if self.model is None:
            raise ValueError("Model not built yet")

        # Debug info
        num_vars = len(self.model.variables())
        num_constraints = len(self.model.constraints)
        print(f"[Export LP] Model has {num_vars:,} variables")
        print(f"[Export LP] Model has {num_constraints:,} constraints")

        path = os.path.join(output_dir, 'model.lp')

        try:
            # PuLP writeLP() doesn't support Unicode
            self.model.writeLP(path)
        except UnicodeEncodeError as e:
            print(f"[Export LP] Unicode error: {e}")
            # Create a summary file instead
            with open(path, 'w', encoding='utf-8') as f:
                f.write("\\* Inventory_Reallocation *\\\n")
                f.write("\\* Cannot export full model due to Unicode characters *\\\n\n")
                f.write(f"Model Summary:\n")
                f.write(f"  Variables: {num_vars:,}\n")
                f.write(f"  Constraints: {num_constraints:,}\n\n")
                f.write("Note: .lp format does not support Vietnamese characters\n")

        # Verify file size
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"[Export LP] File size: {size:,} bytes")

        return path
    
    def get_sensitivity_report(self) -> Dict:
        """
        Tạo Sensitivity Report tương tự Excel Solver.
        
        Bao gồm:
        1. Variable Cells: Giá trị biến, reduced cost
        2. Constraints: Shadow price, slack, allowable increase/decrease
        
        Returns:
            Dict chứa các DataFrame báo cáo
        """
        if self.model is None or self.status != 'Optimal':
            return {}
        
        # =====================================================================
        # 1. VARIABLE CELLS (Decision Variables Report)
        # =====================================================================
        var_data = []
        
        # x variables (Store → Store)
        for (i, j, p), var in self.variables['x'].items():
            final_value = value(var) or 0
            # Reduced cost = coefficient in objective - actual contribution
            skc = self.sku_to_skc.get(p, '')
            is_broken_i = self.is_broken.get((i, skc), 0)
            is_broken_j = self.is_broken.get((j, skc), 0)
            obj_coef = WEIGHT_BASE + WEIGHT_DEST_BROKEN * is_broken_j + WEIGHT_SOURCE_BROKEN * is_broken_i
            
            var_data.append({
                'Biến': f'x_{i}_{j}_{p}',
                'Loại': 'Chuyển cửa hàng',
                'Nguồn': i,
                'Đích': j,
                'SKU': p,
                'Giá trị': final_value,
                'Hệ số mục tiêu': obj_coef,
                'Đóng góp': final_value * obj_coef,
                'Cận dưới': 0,
                'Cận trên': min(self.supply.get((i, p), 0), self.demand.get((j, p), 0))
            })
        
        # y variables (Warehouse → Store)
        for (j, p), var in self.variables['y'].items():
            final_value = value(var) or 0
            skc = self.sku_to_skc.get(p, '')
            is_broken_j = self.is_broken.get((j, skc), 0)
            obj_coef = WEIGHT_WAREHOUSE + WEIGHT_DEST_BROKEN * is_broken_j
            
            var_data.append({
                'Biến': f'y_{j}_{p}',
                'Loại': 'Chuyển từ kho',
                'Nguồn': 'Kho',
                'Đích': j,
                'SKU': p,
                'Giá trị': final_value,
                'Hệ số mục tiêu': obj_coef,
                'Đóng góp': final_value * obj_coef,
                'Cận dưới': 0,
                'Cận trên': min(self.warehouse_stock.get(p, 0), self.demand.get((j, p), 0))
            })
        
        df_variables = pd.DataFrame(var_data)
        
        # =====================================================================
        # 2. CONSTRAINTS REPORT
        # =====================================================================
        constraint_data = []
        
        for name, constraint in self.model.constraints.items():
            slack = constraint.slack if hasattr(constraint, 'slack') else None
            pi = constraint.pi if hasattr(constraint, 'pi') else None  # Shadow price
            
            # Tính RHS và LHS
            rhs = -constraint.constant if constraint.constant else 0
            
            constraint_data.append({
                'Constraint': name,
                'Shadow Price': pi,
                'Slack': slack,
                'RHS': rhs,
                'Status': 'Binding' if slack == 0 else 'Not Binding'
            })
        
        df_constraints = pd.DataFrame(constraint_data)

        # =====================================================================
        # 3. SUMMARY BY TYPE
        # =====================================================================
        
        # Tổng hợp theo loại transfer
        if not df_variables.empty:
            summary_by_type = df_variables.groupby('Loại').agg({
                'Giá trị': 'sum',
                'Đóng góp': 'sum',
                'Biến': 'count'
            }).reset_index()
            summary_by_type.columns = ['Loại', 'Tổng số lượng', 'Tổng đóng góp', 'Số biến']
        else:
            summary_by_type = pd.DataFrame()

        # Tổng hợp theo Store (destination)
        if not df_variables.empty:
            summary_by_dest = df_variables.groupby('Đích').agg({
                'Giá trị': 'sum',
                'Đóng góp': 'sum',
                'Biến': 'count'
            }).reset_index()
            summary_by_dest.columns = ['Đích', 'Tổng nhận vào', 'Tổng đóng góp', 'Số lần chuyển']
        else:
            summary_by_dest = pd.DataFrame()
        
        # Binding constraints summary
        if not df_constraints.empty:
            binding_constraints = df_constraints[df_constraints['Status'] == 'Binding']
            binding_summary = binding_constraints.groupby(
                binding_constraints['Constraint'].str.split('_').str[0]
            ).size().reset_index()
            binding_summary.columns = ['Constraint Type', 'Num Binding']
        else:
            binding_summary = pd.DataFrame()
        
        # =====================================================================
        # 4. UTILIZATION REPORT
        # =====================================================================
        
        # Supply utilization
        supply_util = []
        for i in self.stores:
            for p in self.skus:
                supply_ip = self.supply.get((i, p), 0)
                if supply_ip > 0:
                    used = sum(
                        value(self.variables['x'].get((i, j, p), 0)) or 0
                        for j in self.stores if j != i
                    )
                    supply_util.append({
                        'Store': i,
                        'SKU': p,
                        'Supply': supply_ip,
                        'Used': used,
                        'Remaining': supply_ip - used,
                        'Utilization %': round(used / supply_ip * 100, 1) if supply_ip > 0 else 0
                    })
        df_supply_util = pd.DataFrame(supply_util)
        
        # Demand fulfillment
        demand_fulfill = []
        for j in self.stores:
            for p in self.skus:
                demand_jp = self.demand.get((j, p), 0)
                if demand_jp > 0:
                    received = (value(self.variables['y'].get((j, p), 0)) or 0) + sum(
                        value(self.variables['x'].get((i, j, p), 0)) or 0
                        for i in self.stores if i != j
                    )
                    demand_fulfill.append({
                        'Store': j,
                        'SKU': p,
                        'Demand': demand_jp,
                        'Fulfilled': received,
                        'Unmet': demand_jp - received,
                        'Fulfillment %': round(received / demand_jp * 100, 1) if demand_jp > 0 else 0
                    })
        df_demand_fulfill = pd.DataFrame(demand_fulfill)
        
        # Warehouse utilization
        wh_util = []
        for p in self.skus:
            stock = self.warehouse_stock.get(p, 0)
            if stock > 0:
                used = sum(
                    value(self.variables['y'].get((j, p), 0)) or 0
                    for j in self.stores
                )
                wh_util.append({
                    'SKU': p,
                    'Stock': stock,
                    'Used': used,
                    'Remaining': stock - used,
                    'Utilization %': round(used / stock * 100, 1) if stock > 0 else 0
                })
        df_wh_util = pd.DataFrame(wh_util)
        
        return {
            '1_Variable_Cells': df_variables,
            '2_Constraints': df_constraints,
            '3_Summary_By_Type': summary_by_type,
            '4_Summary_By_Destination': summary_by_dest,
            '5_Binding_Constraints': binding_summary,
            '6_Supply_Utilization': df_supply_util,
            '7_Demand_Fulfillment': df_demand_fulfill,
            '8_Warehouse_Utilization': df_wh_util
        }
