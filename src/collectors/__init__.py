"""采集器工厂（V2）"""
from .base import Collector, NoteRecord, normalize
from .favorites import FavoritesCollector
from .search import SearchCollector
from .user_notes import UserNotesCollector
from .feed import FeedCollector

__all__ = ["Collector", "NoteRecord", "normalize", "FavoritesCollector",
           "SearchCollector", "UserNotesCollector", "FeedCollector"]
