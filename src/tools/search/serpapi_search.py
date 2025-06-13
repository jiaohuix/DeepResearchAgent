import os
import serpapi
from typing import List, Any, Optional

from src.tools.search.base import WebSearchEngine, SearchItem
from src.logger import logger
from pydantic import Field, PrivateAttr

class SerpAPISearchEngine(WebSearchEngine):
    api_key: str = Field(default_factory=lambda: os.getenv("SERPAPI_API_KEY"), description="SerpAPI Key")
    _client: Any = PrivateAttr()

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        if api_key:
            self.api_key = api_key
        elif not self.api_key:
            logger.error("SerpAPI Key is not set. Please set SERPAPI_API_KEY environment variable or pass it to SerpAPISearchEngine.")
            raise ValueError("SerpAPI Key is not set.")
        self._client = serpapi.Client(api_key=self.api_key)

    async def perform_search(
        self, query: str, num_results: int = 10, *args, **kwargs
    ) -> List[SearchItem]:
        """
        使用 SerpAPI 执行搜索。
        """
        try:
            # SerpAPI 的 search 方法支持直接传入参数
            search_params = {
                "q": query,
                "num": num_results,
                "engine": "google", # SerpAPI 默认支持 Google，你也可以在这里设置其他引擎
            }
            # 传入额外的 kwargs
            search_params.update(kwargs)

            results = self._client.search(**search_params)

            search_items = []
            organic_results = results.get("organic_results", [])
            for idx, item in enumerate(organic_results):
                search_items.append(
                    SearchItem(
                        title=item.get("title", f"SerpAPI Result {idx+1}"),
                        url=item.get("link", ""),
                        description=item.get("snippet", ""),
                        position=idx + 1,
                        source="SerpAPI"
                    )
                )
            return search_items
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            return [] 