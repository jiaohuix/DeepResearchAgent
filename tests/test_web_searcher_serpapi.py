import warnings
warnings.simplefilter("ignore", DeprecationWarning)

import os
import sys
from pathlib import Path
import asyncio

# 将项目根目录添加到 Python 路径
root = str(Path(__file__).resolve().parents[1])
sys.path.append(root)

from src.tools.web_searcher import WebSearcherTool
from src.models import model_manager
from src.config import config # 导入 config 来初始化配置

if __name__ == "__main__":
    # 初始化配置和模型（WebSearcherTool 需要这些）
    # 注意：这里我们使用 config_example_my.toml，确保你的 SERPAPI_API_KEY 在环境变量中
    # 或者你需要在 SerpAPISearchEngine 的 __init__ 中硬编码 Key (不推荐)
    config.init_config(config_path=os.path.join(root, "configs/config_example_my.toml"))
    model_manager.init_models(use_local_proxy=False)
    
    web_search = WebSearcherTool()
    web_search.fetch_content = True # 如果需要抓取页面内容，设置为 True

    # *** 关键：强制设置主搜索引擎为 SerpAPI ***
    web_search.searcher_config.engine = "SerpAPI"
    web_search.searcher_config.fallback_engines = ["Google", "DuckDuckGo", "Baidu", "Bing"] # 备用引擎也可以设置

    # 定义测试查询
    query_text = "AI Agent 最新发展"

    print(f"正在使用 WebSearcherTool (SerpAPI) 搜索: '{query_text}'\n")
    
    try:
        search_response = asyncio.run(web_search.forward(
            query=query_text,
        ))

        if search_response.error:
            print(f"WebSearcherTool (SerpAPI) 搜索失败: {search_response.error}")
        else:
            print("WebSearcherTool (SerpAPI) 搜索成功！\n")
            print(search_response.output)
            print(f"\n总共找到 {len(search_response.results)} 条结果。")

    except Exception as e:
        print(f"运行测试脚本时发生未预期的错误: {e}")
        print("请确保 SerpAPI Key 已正确设置在环境变量中，并且网络连接正常。")
