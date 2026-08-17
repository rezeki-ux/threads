"""Storage backends for scraped Threads records."""

from .base import Repository
from .memory import InMemoryRepository
from .postgres import PostgresRepository

__all__ = ["Repository", "InMemoryRepository", "PostgresRepository"]
