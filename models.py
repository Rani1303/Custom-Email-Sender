from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    date: str = ''
    author: str = ''

    @classmethod
    def from_serp(cls, result: Dict[str, Optional[str]]) -> 'SearchResult':
        return cls(
            title=result.get('title', ''),
            link=result.get('link', ''),
            snippet=result.get('snippet', ''),
            date=result.get('date', ''),
            author=result.get('author', '')
        )

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
            "date": self.date,
            "author": self.author,
        }

@dataclass
class ExtractionResult:
    entity: str
    extracted_info: List[str] = None
    source_urls: List[str] = None

    def __post_init__(self):
        self.extracted_info = self.extracted_info or []
        self.source_urls = self.source_urls or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "extracted_info": self.extracted_info,
            "source_urls": self.source_urls,
        }
