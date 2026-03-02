# pyright: reportMissingImports=false
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import SessionLocal, User

db = SessionLocal()
u = db.query(User).filter(User.email == "charles.rsilva05@gmail.com").first()
if u:
    print(f"full_name: {u.full_name}")
    print(f"role: {u.role}")
    print(f"plan: {u.plan}")
    print(f"status: {u.status}")
    # Fix full_name if empty
    needs_fix = False
    if not u.full_name or u.full_name in ("Usuario", "Usuário", ""):
        u.full_name = "Charles Silva"
        needs_fix = True
    if u.role != "admin":
        u.role = "admin"
        needs_fix = True
    if u.plan != "enterprise":
        u.plan = "enterprise"
        needs_fix = True
    if needs_fix:
        db.commit()
        print(">> FIXED: updated name/role/plan")
    else:
        print(">> All good!")
else:
    print("NOT FOUND")
db.close()
