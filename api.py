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

@app.get("/")
def root():
    return {"message": "A股筛选器API运行正常", "usage": "访问 /api/screen 进行筛选"}

@app.get("/api/screen")
async def screen_stocks(
    pe_max: float = 50,      # 最大市盈率
    price_min: float = 0,    # 最低价
    price_max: float = 200,  # 最高价
    change_min: float = -10, # 最小涨跌幅
    sort_by: str = "change_pct" # 排序字段
):
    """核心筛选端点"""
    try:
        # 1. 获取A股实时数据
        df = ak.stock_zh_a_spot()
        
        # 2. 清洗和重命名列
        df = df.rename(columns={
            '代码': 'symbol',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '市盈率-动态': 'pe',
            '市净率': 'pb',
            '成交量': 'volume'
        })
        
        # 3. 转换为数值类型
        numeric_cols = ['price', 'change_pct', 'pe', 'pb', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 4. 应用前端传入的筛选条件
        mask = (
            (df['price'].between(price_min, price_max)) &
            (df['change_pct'] >= change_min) &
            (df['pe'] <= pe_max)
        )
        result_df = df[mask].dropna()
        
        # 5. 排序
        if sort_by in result_df.columns:
            result_df = result_df.sort_values(by=sort_by, ascending=False)
        
        # 6. 转换为JSON
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
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
