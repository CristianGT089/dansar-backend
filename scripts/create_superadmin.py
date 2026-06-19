"""
Ejecutar una sola vez en producción para crear el primer superadmin:
    python scripts/create_superadmin.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.core.models_registry  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.modules.users.models import User
from sqlalchemy import select


async def main():
    email = input("Email del superadmin: ").strip()
    full_name = input("Nombre completo: ").strip()
    password = input("Contraseña (mín. 8 caracteres): ").strip()

    if len(password) < 8:
        print("Error: la contraseña debe tener al menos 8 caracteres")
        return

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"Error: ya existe un usuario con el email {email}")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_superadmin=True,
        )
        db.add(user)
        await db.commit()
        print(f"Superadmin creado exitosamente: {email}")


asyncio.run(main())
