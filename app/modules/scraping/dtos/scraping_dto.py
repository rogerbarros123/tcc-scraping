from pydantic import BaseModel

class ScrapingDto(BaseModel):
  url: str
  folderName: str