from pydantic import BaseModel

class DownloadFilesDto(BaseModel):
  companyId: int
  groupId: int
  downloadPage: str 
  links: list[str]
