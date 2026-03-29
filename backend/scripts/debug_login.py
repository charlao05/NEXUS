# pyright: reportMissingImports=false
"""Debug login issue."""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, User

db = SessionLocal()
try:
    email = "appnexxus.app@gmail.com"
    password = "Teste1234"
    
    print("1. Querying user...")
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        print("   USER NOT FOUND!")
        sys.exit(1)
    
    print(f"   Found: id={user.id}, email={user.email}, full_name={user.full_name}")
    print(f"   plan={user.plan}, role={user.role}, status={user.status}")
    print(f"   password_hash type: {type(user.password_hash)}")
    print(f"   password_hash[:20]: {str(user.password_hash)[:20]}...")
    
    print("\n2. Testing password verification...")
    try:
        import bcrypt
        pw_hash = str(user.password_hash)
        result = bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8'))
        print(f"   bcrypt.checkpw result: {result}")
    except Exception as e:
        print(f"   bcrypt ERROR: {e}")
        traceback.print_exc()
    
    print("\n3. Testing verify_password from auth...")
    try:
        from app.api.auth import verify_password
        result2 = verify_password(password, str(user.password_hash))
        print(f"   verify_password result: {result2}")
    except Exception as e:
        print(f"   verify_password ERROR: {e}")
        traceback.print_exc()
    
    print("\n4. Testing create_jwt_token...")
    try:
        from app.api.auth import create_jwt_token
        token = create_jwt_token(user.id, email, str(user.plan or "free"))
        print(f"   Token created: {token[:50]}...")
    except Exception as e:
        print(f"   create_jwt ERROR: {e}")
        traceback.print_exc()
    
    print("\n5. Testing create_refresh_token...")
    try:
        from app.api.auth import create_refresh_token
        refresh = create_refresh_token(user.id, email)
        print(f"   Refresh created: {refresh[:50]}...")
    except Exception as e:
        print(f"   create_refresh ERROR: {e}")
        traceback.print_exc()
    
    print("\n6. Testing TokenResponse model...")
    try:
        from app.api.auth import TokenResponse
        resp = TokenResponse(
            access_token="test",
            token_type="bearer",
            user_id=str(user.id),
            email=email,
            plan=str(user.plan or "free"),
            refresh_token="test_refresh",
        )
        print(f"   TokenResponse OK: {resp}")
    except Exception as e:
        print(f"   TokenResponse ERROR: {e}")
        traceback.print_exc()

    print("\n7. Testing last_login assignment...")
    try:
        from datetime import datetime, timezone
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        print(f"   last_login updated OK")
    except Exception as e:
        print(f"   last_login ERROR: {e}")
        traceback.print_exc()
        db.rollback()

except Exception as e:
    print(f"\nUNEXPECTED ERROR: {e}")
    traceback.print_exc()
finally:
    db.close()
    print("\nDone.")
