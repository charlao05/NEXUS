import sys
import os
from pathlib import Path

# Adicionar backend ao path
backend_dir = Path('/home/ubuntu/NEXUS/backend')
sys.path.append(str(backend_dir))

from database.models import get_session, User
from app.api.auth import hash_password

def create_admin():
    session = get_session()
    try:
        # Verificar se já existe
        email = 'appnexxus.app@gmail.com'
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            print(f"Usuário {email} já existe.")
            return

        user = User(
            email=email,
            password_hash=hash_password('Admin@123'),
            full_name='NEXUS Admin',
            plan='completo',
            role='admin',
            status='active',
            email_verified=True
        )
        session.add(user)
        session.commit()
        print(f"Usuário {email} criado com sucesso!")
    except Exception as e:
        session.rollback()
        print(f"Erro ao criar usuário: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    create_admin()
