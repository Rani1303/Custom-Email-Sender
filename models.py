from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str

    @classmethod
    def from_serp(cls, result: Dict[str, Any]) -> 'SearchResult':
        return cls(
            title=result.get('title', ''),
            link=result.get('link', ''),
            snippet=result.get('snippet', '')
        )

@dataclass
class ExtractionResult:
    entity: str
    extracted_info: List[str]
    source_urls: List[str]