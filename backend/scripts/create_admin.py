"""Create owner admin account."""
# pyright: reportMissingImports=false
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, User  # noqa: E402
from datetime import datetime, timedelta, timezone
import bcrypt  # noqa: E402

def create_admin():
    db = SessionLocal()
    
    email = "appnexxus.app@gmail.com"
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        existing.role = "admin"
        existing.plan = "enterprise"
        db.commit()
        print(f"User {email} already exists — promoted to admin/enterprise")
        db.close()
        return
    
    password = "Teste1234"
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
    
    user = User(
        email=email,
        password_hash=pw_hash,
        full_name="Charles Silva",
        plan="enterprise",
        status="active",
        role="admin",
        communication_preference="email",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=365*10),
        lgpd_consent=True,
        lgpd_consent_at=datetime.now(timezone.utc),
        email_verified=True,
    )
    db.add(user)
    db.commit()
    print(f"Created admin account: {email} (password: {password})")
    print(f"  role=admin, plan=enterprise, trial=10 years")
    db.close()

if __name__ == "__main__":
    create_admin()
