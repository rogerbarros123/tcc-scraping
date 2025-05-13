from enum import  Enum

class LogEnumList(Enum):
  @classmethod
  def list(cls):
    return [member.value for member in cls]

class LogLevels(LogEnumList):
  """Níveis de logging suportados"""
  INFO = "INFO"
  WARNING = "WARNING"
  ERROR = "ERROR"
  DEBUG = "DEBUG"