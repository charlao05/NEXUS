"""Migrate DB: add role + communication_preference columns, promote owner to admin."""
# pyright: reportMissingImports=false
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, User, engine  # noqa: E402
from sqlalchemy import inspect, text

def migrate():
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("users")]
    
    with engine.connect() as conn:
        if "role" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
            conn.commit()
            print("Added column: role")
        else:
            print("Column role already exists")
        
        if "communication_preference" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN communication_preference VARCHAR(20) DEFAULT 'email'"))
            conn.commit()
            print("Added column: communication_preference")
        else:
            print("Column communication_preference already exists")
    
    # Promote owner
    db = SessionLocal()
    user = db.query(User).filter(User.email == "appnexxus.app@gmail.com").first()
    if user:
        user.role = "admin"
        user.plan = "enterprise"
        db.commit()
        print(f"Promoted {user.email} to admin with enterprise plan")
    else:
        print("User appnexxus.app@gmail.com not found")
    db.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
