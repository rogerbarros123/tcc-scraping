import logging

try:
  from colorlog import ColoredFormatter
except ImportError:
  ColoredFormatter = None

from app.config.settings import settings
from app.core.enums import LogLevels

def configure_logging():
  level_mapping = {
    LogLevels.DEBUG: logging.DEBUG,
    LogLevels.INFO: logging.INFO,
    LogLevels.WARNING: logging.WARNING,
    LogLevels.ERROR: logging.ERROR
  }

  log_level_str = settings.LOG_LEVEL.upper()
  
  # Convert string to enum member
  if log_level_str not in LogLevels.list():
    log_level_enum = LogLevels.ERROR
  else:
    log_level_enum = getattr(LogLevels, log_level_str)
  
  log_level = level_mapping[log_level_enum]
  
  # Escolha o formato detalhado para DEBUG, simples para os demais
  if log_level_enum == LogLevels.DEBUG:
    log_format = (
      "[%(log_color)s%(asctime)s] [%(levelname)s] [%(name)s] %(message)s "
      "(%(pathname)s:%(funcName)s:%(lineno)d)"
    )
  else:
    log_format = "[%(log_color)s%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
  
  date_format = "%Y-%m-%d %H:%M:%S"

  # Se o colorlog estiver disponível, utiliza ele para formatar com cores
  if ColoredFormatter:
    formatter = ColoredFormatter(
      log_format,
      datefmt=date_format,
      log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
      },
      reset=True,
      style='%'
    )
  else:
    # Fallback sem cores (remove o placeholder de cor)
    formatter = logging.Formatter(log_format.replace("%(log_color)s", ""), datefmt=date_format)

  # Configuração do handler de stream
  handler = logging.StreamHandler()
  handler.setFormatter(formatter)

  # Configuração do logger raiz: limpa handlers antigos e aplica o novo
  root_logger = logging.getLogger()
  root_logger.setLevel(log_level)
  root_logger.handlers.clear()
  root_logger.addHandler(handler)
  
  logger = logging.getLogger(__name__)
  logger.info("Logging configurado com nível: %s", log_level_enum.value)
