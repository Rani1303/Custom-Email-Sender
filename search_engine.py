import requests
from typing import List
from models import SearchResult
from config import Config

# Load environment variables
load_dotenv()

# Initialize configuration
config = Config.from_env()

class SearchEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str) -> List[SearchResult]:
        url = f"https://serpapi.com/search.json?q={query}&api_key={self.api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            results = response.json().get("organic_results", [])
            return [SearchResult.from_serp(result) for result in results]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Search failed: {str(e)}")