import sys
import os

# Adicionar diretório do projeto ao path
project_home = '/home/frotaventure/lal-api'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Importar o app Flask
from app import app as application  # noqa

# Inicializar banco se necessario
from database import init_db, DB_PATH
if not os.path.exists(DB_PATH):
    init_db()
