from pydantic import BaseModel 
from typing import Optional, Generic, TypeVar, List, Union

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    errors: Optional[Union[str, List[str]]] = None