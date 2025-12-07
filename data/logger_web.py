# logger_web.py
import logging
from collections import deque

# Buffer circular: guarda las últimas 50 líneas.
# Cuando entra la 51, borra la más antigua automáticamente.
log_buffer = deque(maxlen=50)

class BufferHandler(logging.Handler):
    """
    Handler personalizado que envía los logs a nuestra lista en memoria
    en lugar de a un archivo.
    """
    def emit(self, record):
        try:
            msg = self.format(record)
            log_buffer.append(msg)
        except Exception:
            self.handleError(record)

def get_logger():
    """
    Configura y devuelve el logger compartido.
    """
    logger = logging.getLogger("hidroponia_logger")
    
    # Si ya tiene handlers, no se los volvemos a añadir (evita duplicados al recargar)
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Formato: [HORA] MENSAJE
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

    # 1. Salida por Consola (para que lo sigas viendo en terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Salida a Web (Buffer)
    web_handler = BufferHandler()
    web_handler.setFormatter(formatter)
    logger.addHandler(web_handler)
    
    return logger

# Instancia lista para importar
logger = get_logger()