from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.future import select
from dotenv import load_dotenv
import os

load_dotenv()

# 1. Налаштування з'єднання
# Формат: postgresql+asyncpg://user:password@localhost/dbname
DATABASE_USER = os.getenv("DB_USER")
DATABASE_PASSWORD = os.getenv("DB_PASSWORD")
DATABASE_NAME = os.getenv("DB_NAME")
DATABASE_URL = f"postgresql+asyncpg://{DATABASE_USER}:{DATABASE_PASSWORD}@127.0.0.1/{DATABASE_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


# 2. Визначення таблиці (Модель)
class Skin(Base):
    __tablename__ = "skins"

    # id - унікальний номер кожного запису (автоматичний)
    id = Column(Integer, primary_key=True, index=True)

    # market_hash_name - точна назва скіна (наприклад, "AK-47 | Slate (Field-Tested)")
    # unique=True означає, що ми не можемо мати два рядки з однаковою назвою
    name = Column(String, unique=True, index=True)

    steam_price = Column(Float, default=0.0)  # Ціна продажу на Steam
    skinport_price = Column(Float, default=0.0)  # Ціна купівлі на Skinport

    # last_updated - коли ми востаннє оновлювали ціну (важливо для користувача)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# 3. Функція для створення таблиць при запуску
async def init_db():
    async with engine.begin() as conn:
        # Це створить таблицю, якщо її ще немає
        await conn.run_sync(Base.metadata.create_all)


async def update_skin_price(db: AsyncSession, skin_name: str, price: float, source: str):
    """
    db: сесія бази даних
    skin_name: назва скіна
    price: нова ціна
    source: 'steam' або 'skinport'
    """

    # 1. Шукаємо, чи є такий скін у базі
    result = await db.execute(select(Skin).where(Skin.name == skin_name))
    skin_in_db = result.scalars().first()

    if not skin_in_db:
        # Якщо немає - створюємо новий
        new_skin = Skin(name=skin_name)
        if source == 'steam':
            new_skin.steam_price = price
        else:
            new_skin.skinport_price = price
        db.add(new_skin)
        print(f"🆕 New skin added: {skin_name}")
    else:
        # Якщо є - оновлюємо тільки потрібну ціну
        if source == 'steam':
            skin_in_db.steam_price = price
        else:
            skin_in_db.skinport_price = price
        # updated_at оновиться автоматично завдяки налаштуванням моделі
        print(f"🔄 Price updated: {skin_name}")

    # Зберігаємо зміни
    await db.commit()