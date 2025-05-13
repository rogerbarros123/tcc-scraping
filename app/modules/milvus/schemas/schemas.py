from pydantic import BaseModel
from typing import List

class InsertDto(BaseModel):
    links: List[str]
    folder_name: str
