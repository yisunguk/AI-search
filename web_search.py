"""
Web Search Helper using Bing Search API
Provides web search functionality for function calling
"""

import os
import requests
from typing import Optional

# Get Bing Search API key from environment
BING_SEARCH_KEY = os.getenv("BING_SEARCH_KEY", "")
BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

def perform_web_search(query: str, count: int = 5) -> str:
    """
    Perform web search using Bing Search API
    
    Args:
        query: Search query
        count: Number of results to return (default: 5)
        
    Returns:
        Formatted search results as a string
    """
    if not BING_SEARCH_KEY:
        return "웹 검색 API 키가 설정되지 않았습니다. Bing Search API 키를 추가해주세요."
    
    try:
        headers = {
            "Ocp-Apim-Subscription-Key": BING_SEARCH_KEY
        }
        params = {
            "q": query,
            "count": count,
            "mkt": "ko-KR",  # Korean market
            "responseFilter": "Webpages"
        }
        
        response = requests.get(BING_SEARCH_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()
        
        search_results = response.json()
        
        # Format results
        if "webPages" in search_results and "value" in search_results["webPages"]:
            results = []
            for result in search_results["webPages"]["value"][:count]:
                snippet = result.get("snippet", "설명 없음")
                url = result.get("url", "")
                name = result.get("name", "제목 없음")
                
                results.append(f"**{name}**\n{snippet}\n출처: {url}\n")
            
            return "\n".join(results)
        else:
            return "검색 결과가 없습니다."
            
    except Exception as e:
        return f"웹 검색 중 오류가 발생했습니다: {str(e)}"
