import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "app"))
from api.auth import router
print(router.routes)