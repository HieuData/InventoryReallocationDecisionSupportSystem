"""
Configuration settings for Inventory Optimization
"""

# =============================================================================
# MOH THRESHOLDS
# =============================================================================
MOH_THRESHOLD_LOW = 1.5      # MOH < 1.5 → Tốt (cần nhập)
MOH_THRESHOLD_HIGH = 3.5     # MOH > 3.5 → Kém (cần xuất)
MOH_TARGET = 2.5             # MOH mục tiêu

# Cột doanh số
SALES_COLS = ['Bán 90 ngày', 'Bán 60 ngày', 'Bán 30 ngày', 'Bán 14 ngày', 'Bán 7 ngày']
SALES_LY_COLS = [f'{c} năm trước' for c in SALES_COLS]

# =============================================================================
# BROKEN INDEX
# =============================================================================
BROKEN_THRESHOLD = 50        # % - SKC gãy nếu >= 50%
HEAVY_BROKEN_THRESHOLD = 0.6 # 60% SKC gãy → store gãy nặng

# =============================================================================
# LOGISTICS CONSTRAINTS
# =============================================================================
MAX_OUTBOUND_ROUTES = 7      # Mỗi store xuất tối đa 7 điểm đến
MAX_INBOUND_ROUTES = 5       # Mỗi store nhận tối đa 5 nguồn
MIN_SKU_PER_SHIPMENT = 6     # Tối thiểu 6 SKU/chuyến

# =============================================================================
# CATEGORY MAPPING
# =============================================================================
CATEGORY_MAP = {
    '5': 'Quần áo',
    '7': 'Giày dép',
    '9': 'Phụ kiện'
}

# =============================================================================
# REGION MAPPING (for seasonal constraint)
# =============================================================================
COLD_RESTRICTED_REGIONS = ['S3 - Miền trung', 'S4 - Miền nam', 'S5 - Đồng bằng SCL']

# =============================================================================
# OPTIMIZATION WEIGHTS
# =============================================================================
WEIGHT_BASE = 1.0
WEIGHT_DEST_BROKEN = 3.0     # Ưu tiên chuyển đến store đang gãy
WEIGHT_SOURCE_BROKEN = 2.0   # Ưu tiên giải phóng store đang gãy
WEIGHT_WAREHOUSE = 10.0      # Ưu tiên xuất từ kho

# =============================================================================
# SOLVER SETTINGS
# =============================================================================
SOLVER_TIME_LIMIT = 300      # seconds
SOLVER_GAP = 0.05            # 5% optimality gap
BIG_M = 100000               # Big-M constant

UPLOAD_FOLDER = './uploads'