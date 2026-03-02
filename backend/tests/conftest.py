"""
NEXUS — Configuração global de testes (backend)
=================================================
Garante que ENVIRONMENT=test está setado antes de qualquer teste,
desabilitando rate limiting e outros comportamentos de produção.
"""

import os
import sys
from pathlib import Path

# Garantir que ENVIRONMENT=test está setado (desabilita rate limiter)
os.environ.setdefault("ENVIRONMENT", "test")

# Garantir que backend está no PYTHONPATH
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
