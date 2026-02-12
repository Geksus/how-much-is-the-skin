import asyncio
import aiohttp
import random
import time
from curl_cffi import requests as crequests

from database import init_db, SessionLocal, update_skin_price

# --- НАЛАШТУВАННЯ ---
HOT_KEYWORDS = ["AK-47", "M4A4", "M4A1-S", "AWP", "USP-S", "Glock-18", "Desert Eagle"]
HOT_REFRESH_RATE = 300  # 5 хвилин (в секундах)
COLD_REFRESH_RATE = 3600  # 1 година (в секундах)

# Ліміти безпеки
MAX_CONCURRENT_REQUESTS = 5  # Для 10 проксі краще не ставити більше 5-10

STEAM_MARKET_URL = "https://steamcommunity.com/market/priceoverview/"
SKINPORT_API_URL = "https://api.skinport.com/v1/items"


# --- ПРОКСІ МЕНЕДЖЕР ---
class ProxyManager:
    def __init__(self, filepath):
        self.proxies = []
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    parts = line.split(":")
                    if len(parts) == 4:
                        ip, port, user, password = parts
                        self.proxies.append(f"http://{user}:{password}@{ip}:{port}")
            print(f"✅ Завантажено проксі: {len(self.proxies)}")
        except FileNotFoundError:
            print("⚠️ Файл проксі не знайдено.")

    def get_random(self):
        return random.choice(self.proxies) if self.proxies else None


proxy_manager = ProxyManager("Webshare 10 proxies.txt")


# --- КРОК 1: Отримання списку предметів (Skinport) ---
def get_all_items_and_sort():
    print("🌍 Завантажуємо базу предметів зі Skinport...")
    params = {"app_id": 730, "currency": "USD", "tradable": 0}

    try:
        # Bypass Cloudflare
        response = crequests.get(SKINPORT_API_URL, params=params, impersonate="chrome110", timeout=30)

        if response.status_code == 200:
            data = response.json()
            hot_items = []
            cold_items = []
            prices = {}

            for item in data:
                name = item['market_hash_name']
                price = item['min_price']

                # Зберігаємо ціну Skinport
                prices[name] = price

                # Сортуємо: Hot чи Cold?
                # Якщо ціна менше $200 і в назві є популярна зброя -> Hot
                is_hot = False
                if price and price < 200:
                    for keyword in HOT_KEYWORDS:
                        if keyword in name:
                            is_hot = True
                            break

                if is_hot:
                    hot_items.append(name)
                else:
                    cold_items.append(name)

            print(f"📊 Аналіз завершено: {len(hot_items)} Hot items / {len(cold_items)} Cold items")
            return hot_items, cold_items, prices
        else:
            print(f"❌ Skinport Error: {response.status_code}")
            return [], [], {}
    except Exception as e:
        print(f"❌ Skinport Connection Error: {e}")
        return [], [], {}


# --- КРОК 2: Воркер для Steam ---
async def fetch_steam_price(session, item_name, semaphore):
    params = {"country": "US", "currency": 1, "appid": 730, "market_hash_name": item_name}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    proxy = proxy_manager.get_random()

    async with semaphore:
        # Випадкова затримка, щоб запити йшли "хвилями", а не стіною
        await asyncio.sleep(random.uniform(1.0, 3.0))

        try:
            async with session.get(STEAM_MARKET_URL, params=params, headers=headers, proxy=proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and 'lowest_price' in data:
                        try:
                            price_val = float(data['lowest_price'].replace('$', '').replace(',', ''))
                            # print(f"✅ Steam: {item_name} -> ${price_val}") # Спамить у консоль, можна вимкнути

                            async with SessionLocal() as db:
                                await update_skin_price(db, item_name, price_val, "steam")
                        except ValueError:
                            pass
                elif response.status == 429:
                    print(f"⚠️ 429 Rate Limit (Proxy: {proxy[-10:]}...)")
                    # Якщо зловили бан, чекаємо довше
                    await asyncio.sleep(10)
        except Exception as e:
            # print(f"Network Error: {e}")
            pass


# --- ЦИКЛИ СКАНУВАННЯ ---
async def run_scan_loop(session, items, label, refresh_rate, semaphore):
    """
    Універсальна функція циклу.
    label: "HOT" або "COLD"
    refresh_rate: скільки чекати перед повторним скануванням списку
    """
    while True:
        start_time = time.time()
        print(f"🚀 [{label}] Початок циклу сканування ({len(items)} предметів)...")

        tasks = []
        for item in items:
            tasks.append(fetch_steam_price(session, item, semaphore))

        # Запускаємо пачками, щоб не переповнити пам'ять, якщо предметів дуже багато
        # Розбиваємо список на чанки по 50 завдань
        chunk_size = 50
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i + chunk_size]
            await asyncio.gather(*chunk)
            # Мікро-пауза між пачками
            await asyncio.sleep(1)

        duration = time.time() - start_time
        print(f"🏁 [{label}] Цикл завершено за {duration:.1f} сек. Чекаємо {refresh_rate} сек...")

        await asyncio.sleep(refresh_rate)


async def main():
    await init_db()

    # 1. Завантажуємо всі предмети і сортуємо їх
    hot_items, cold_items, skinport_prices = get_all_items_and_sort()

    if not hot_items:
        print("❌ Не вдалося отримати предмети. Зупинка.")
        return

    # 2. Зберігаємо початкові ціни Skinport
    print("💾 Зберігаємо ціни Skinport...")
    async with SessionLocal() as db:
        # Це може зайняти час, тому робимо це один раз на старті
        for name, price in skinport_prices.items():
            if price:
                await update_skin_price(db, name, float(price), "skinport")
    print("✅ Ціни Skinport збережено.")

    # 3. Запускаємо паралельні цикли
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        print("🔥 Запуск двигунів...")

        # Створюємо два незалежних завдання
        task_hot = asyncio.create_task(run_scan_loop(session, hot_items, "HOT", HOT_REFRESH_RATE, semaphore))
        task_cold = asyncio.create_task(run_scan_loop(session, cold_items, "COLD", COLD_REFRESH_RATE, semaphore))

        # Чекаємо вічно (скрипт працюватиме поки не зупиниш Ctrl+C)
        await asyncio.gather(task_hot, task_cold)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Скрипт зупинено користувачем.")