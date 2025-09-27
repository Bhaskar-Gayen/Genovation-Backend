from pydantic import BaseModel
from typing import TypeVar, Generic, List

ItemT = TypeVar("ItemT")

class Pagination(BaseModel):
    page: int
    size: int

class PaginatedResponse(BaseModel, Generic[ItemT]): 
    total: int
    page: int
    size: int
    items: List[ItemT]