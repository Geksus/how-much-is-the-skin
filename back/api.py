from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import SessionLocal, Skin  # Імпортуємо нашу модель з минулого кроку

app = FastAPI()

# 1. Дозвіл для React (CORS)
# Це критично, щоб твій фронтенд міг "стукати" до бекенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшені тут буде домен твого сайту
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Залежність для отримання сесії БД
async def get_db():
    async with SessionLocal() as session:
        yield session


# 3. Головний ендпоінт: /deals
@app.get("/deals")
async def get_profitable_deals(min_profit: float = 1.0, db: AsyncSession = Depends(get_db)):
    """
    Повертає скіни, де прибуток більше ніж min_profit доларів.
    Формула: (Steam Price / 1.15) - Skinport Price > 0
    """

    # Складний SQL-запит простими словами:
    # "Дай мені всі скіни"
    query = select(Skin)
    result = await db.execute(query)
    skins = result.scalars().all()

    profitable_items = []

    for skin in skins:
        # Пропускаємо скіни з нульовою ціною (якщо парсер помилився)
        if skin.steam_price == 0 or skin.skinport_price == 0:
            continue

        # Рахуємо "чисті" гроші після комісії Steam (13% + фікс)
        steam_net = skin.steam_price / 1.15
        profit = steam_net - skin.skinport_price

        # Якщо прибуток вище заданого (за замовчуванням $1)
        if profit >= min_profit:
            roi = (profit / skin.skinport_price) * 100
            profitable_items.append({
                "name": skin.name,
                "buy_at": skin.skinport_price,
                "sell_at": skin.steam_price,
                "profit": round(profit, 2),
                "roi": round(roi, 1)  # Return on Investment у відсотках
            })

    # Сортуємо: спочатку найвигідніші
    profitable_items.sort(key=lambda x: x['profit'], reverse=True)

    return profitable_items