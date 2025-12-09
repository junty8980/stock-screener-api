from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import akshare as ak
import pandas as pd
import os

app = FastAPI(title="A股筛选器API")

# 允许Bubble调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境可替换为Bubble的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/screen")
async def screen_stocks(
    pe_max: float = 50,
    price_min: float = 0,
    price_max: float = 200,
    change_min: float = -10,
    sort_by: str = "change_pct"
):
    """核心筛选端点 (修复版)"""
    try:
        print("开始获取A股实时数据...")
        df = ak.stock_zh_a_spot()
        
        # --- 关键修复：打印列名，检查实际字段 ---
        print("数据列名:", df.columns.tolist())
        
        # 定义更灵活的字段名映射（尝试多个可能的列名）
        column_mapping = {}
        possible_names = {
            'symbol': ['代码', 'symbol'],
            'name': ['名称', 'name'],
            'price': ['最新价', 'current', 'close'],
            'change_pct': ['涨跌幅', '涨幅', 'changepercent'],
            'pe': ['市盈率-动态', '市盈率', 'pe', 'PE'],
            'pb': ['市净率', 'pb', 'PB'],
            'volume': ['成交量', 'volume', '成交']
        }
        
        for standard_name, possible_list in possible_names.items():
            for possible in possible_list:
                if possible in df.columns:
                    column_mapping[standard_name] = possible
                    print(f"映射: {standard_name} -> {possible}")
                    break
        
        # 应用列名映射
        df = df.rename(columns=column_mapping)
        print("重命名后的列:", df.columns.tolist())
        
        # --- 数据清洗 ---
        # 确保必要的列存在
        required_cols = ['symbol', 'name', 'price', 'change_pct']
        for col in required_cols:
            if col not in df.columns:
                return {"success": False, "error": f"数据源中未找到必要字段: '{col}'", "available_columns": df.columns.tolist()}
        
        # 转换为数值类型
        for col in ['price', 'change_pct', 'pe', 'pb']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            else:
                # 如果pe/pb不存在，创建全是NaN的列，这样筛选时会自动忽略
                df[col] = float('nan')
                print(f"注意: 字段 '{col}' 不存在，已创建空列。")
        
        # --- 应用筛选条件 (稳健版) ---
        condition = pd.Series(True, index=df.index)  # 初始为全True
        
        # 价格筛选
        if 'price' in df.columns:
            condition = condition & (df['price'].between(price_min, price_max))
        
        # 涨跌幅筛选
        if 'change_pct' in df.columns:
            condition = condition & (df['change_pct'] >= change_min)
        
        # 市盈率筛选 (只有当pe列存在且用户设置了条件时才应用)
        if 'pe' in df.columns and pd.notna(df['pe']).any():
            # 只对有效的pe值进行筛选
            pe_condition = (df['pe'] <= pe_max) | (df['pe'].isna())
            condition = condition & pe_condition
        
        result_df = df[condition].copy()
        print(f"筛选后剩余 {len(result_df)} 条记录")
        
        # 排序
        if sort_by in result_df.columns:
            result_df = result_df.sort_values(by=sort_by, ascending=False)
        
        # 准备返回数据
        stocks = result_df.head(100).to_dict(orient='records')
        
        return {
            "success": True,
            "count": len(stocks),
            "data": stocks,
            "filters_applied": {
                "pe_max": pe_max,
                "price_min": price_min,
                "price_max": price_max,
                "change_min": change_min
            }
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"筛选过程中发生错误: {error_trace}")
        return {"success": False, "error": str(e), "trace": error_trace}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
