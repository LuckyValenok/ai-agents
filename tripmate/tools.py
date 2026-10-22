"""Инструменты ассистента путешественника.

Все данные — захардкоженные константы (кроме текущего времени, которое
считается по фиксированной таблице часовых поясов).
Ошибки возвращаются как {"error": ...}, чтобы модель могла на них реагировать.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

CITIES = {
    "moscow": {
        "name": "Москва", "aliases": ["москва", "москве", "москву", "moscow", "мск"],
        "tz": "Europe/Moscow",
        "weather": {"temp_c": 6, "condition": "пасмурно, небольшой дождь", "wind_ms": 5, "humidity": 85},
        "attractions": ["Красная площадь и Кремль", "Парк Зарядье", "Третьяковская галерея", "ВДНХ"],
    },
    "spb": {
        "name": "Санкт-Петербург", "aliases": ["санкт-петербург", "петербург", "питер", "спб", "петербурге",
                                               "питере", "saint petersburg", "st. petersburg", "st petersburg"],
        "tz": "Europe/Moscow",
        "weather": {"temp_c": 4, "condition": "облачно, ветрено", "wind_ms": 9, "humidity": 88},
        "attractions": ["Эрмитаж", "Петергоф", "Исаакиевский собор", "Развод мостов"],
    },
    "paris": {
        "name": "Париж", "aliases": ["париж", "париже", "paris"],
        "tz": "Europe/Paris",
        "weather": {"temp_c": 14, "condition": "переменная облачность", "wind_ms": 4, "humidity": 70},
        "attractions": ["Эйфелева башня", "Лувр", "Монмартр", "Музей Орсе"],
    },
    "rome": {
        "name": "Рим", "aliases": ["рим", "риме", "rome", "roma"],
        "tz": "Europe/Rome",
        "weather": {"temp_c": 21, "condition": "солнечно", "wind_ms": 3, "humidity": 60},
        "attractions": ["Колизей", "Ватикан и Сикстинская капелла", "Фонтан Треви", "Пантеон"],
    },
    "istanbul": {
        "name": "Стамбул", "aliases": ["стамбул", "стамбуле", "istanbul"],
        "tz": "Europe/Istanbul",
        "weather": {"temp_c": 19, "condition": "ясно", "wind_ms": 6, "humidity": 65},
        "attractions": ["Собор Святой Софии", "Голубая мечеть", "Гранд-базар", "Прогулка по Босфору"],
    },
    "tokyo": {
        "name": "Токио", "aliases": ["токио", "tokyo"],
        "tz": "Asia/Tokyo",
        "weather": {"temp_c": 18, "condition": "облачно", "wind_ms": 4, "humidity": 72},
        "attractions": ["Храм Сэнсо-дзи", "Перекрёсток Сибуя", "Телебашня Skytree", "Рынок Цукидзи"],
    },
    "dubai": {
        "name": "Дубай", "aliases": ["дубай", "дубае", "dubai"],
        "tz": "Asia/Dubai",
        "weather": {"temp_c": 32, "condition": "солнечно, жарко", "wind_ms": 3, "humidity": 50},
        "attractions": ["Бурдж-Халифа", "Dubai Mall и фонтаны", "Старый район Аль-Фахиди", "Сафари в пустыне"],
    },
    "barcelona": {
        "name": "Барселона", "aliases": ["барселона", "барселоне", "barcelona"],
        "tz": "Europe/Madrid",
        "weather": {"temp_c": 22, "condition": "солнечно", "wind_ms": 4, "humidity": 62},
        "attractions": ["Саграда Фамилия", "Парк Гуэль", "Бульвар Рамбла", "Готический квартал"],
    },
}

# Курс: сколько рублей стоит 1 единица валюты (фиксированные значения).
RATES_RUB = {"RUB": 1.0, "USD": 92.5, "EUR": 100.3, "GBP": 118.4, "TRY": 2.7, "JPY": 0.62, "AED": 25.2, "CNY": 12.8}
RATES_DATE = "2026-10-20"
CURRENCY_STEMS = {
    "RUB": ["rub", "руб", "₽"],
    "USD": ["usd", "доллар", "dollar", "бакс", "$"],
    "EUR": ["eur", "евро", "€"],
    "GBP": ["gbp", "фунт", "pound", "£"],
    "TRY": ["try", "лир", "lira"],
    "JPY": ["jpy", "иен", "йен", "yen", "¥"],
    "AED": ["aed", "дирхам", "dirham"],
    "CNY": ["cny", "юан", "yuan"],
}

# Рейсы, цены в рублях за билет в одну сторону.
FLIGHTS = {
    ("moscow", "istanbul"): [
        {"airline": "Turkish Airlines", "depart": "08:15", "duration": "3ч 40м", "stops": 0, "price_rub": 27900},
        {"airline": "Pegasus", "depart": "22:50", "duration": "3ч 55м", "stops": 0, "price_rub": 21400},
    ],
    ("moscow", "dubai"): [
        {"airline": "Emirates", "depart": "10:05", "duration": "5ч 15м", "stops": 0, "price_rub": 41200},
        {"airline": "flydubai", "depart": "01:30", "duration": "5ч 20м", "stops": 0, "price_rub": 33800},
    ],
    ("moscow", "rome"): [
        {"airline": "Turkish Airlines", "depart": "08:15", "duration": "8ч 05м", "stops": 1, "price_rub": 38600},
    ],
    ("moscow", "paris"): [
        {"airline": "Air Serbia", "depart": "06:40", "duration": "7ч 30м", "stops": 1, "price_rub": 44300},
        {"airline": "Turkish Airlines", "depart": "08:15", "duration": "8ч 50м", "stops": 1, "price_rub": 39900},
    ],
    ("moscow", "tokyo"): [
        {"airline": "China Eastern", "depart": "19:20", "duration": "15ч 10м", "stops": 1, "price_rub": 62500},
    ],
    ("moscow", "spb"): [
        {"airline": "Аэрофлот", "depart": "09:00", "duration": "1ч 25м", "stops": 0, "price_rub": 5900},
        {"airline": "Победа", "depart": "14:35", "duration": "1ч 30м", "stops": 0, "price_rub": 3200},
    ],
}


def _city(raw: str) -> tuple[str, dict]:
    s = str(raw).strip().lower().replace("ё", "е")
    for key, city in CITIES.items():
        if s == key or s in city["aliases"]:
            return key, city
    known = ", ".join(c["name"] for c in CITIES.values())
    raise ValueError(f"нет данных по городу «{raw}». Есть данные только по: {known}")


def _currency(raw: str) -> str:
    s = str(raw).strip().lower()
    for code, stems in CURRENCY_STEMS.items():
        if any(s.startswith(stem) for stem in stems):
            return code
    raise ValueError(f"неизвестная валюта «{raw}». Доступны: {', '.join(RATES_RUB)}")


def get_weather(city: str) -> dict:
    _, c = _city(city)
    return {"city": c["name"], **c["weather"]}


def get_local_time(city: str) -> dict:
    _, c = _city(city)
    now = datetime.now(ZoneInfo(c["tz"]))
    offset = now.strftime("%z")
    return {
        "city": c["name"],
        "local_time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "utc_offset": f"{offset[:3]}:{offset[3:]}",
    }


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    try:
        value = float(str(amount).replace(",", ".").replace(" ", ""))
    except ValueError:
        raise ValueError(f"amount должно быть числом, получено «{amount}»") from None
    src, dst = _currency(from_currency), _currency(to_currency)
    rate = RATES_RUB[src] / RATES_RUB[dst]
    return {
        "amount": value, "from": src, "to": dst,
        "rate": round(rate, 4), "result": round(value * rate, 2), "rates_date": RATES_DATE,
    }


def get_attractions(city: str) -> dict:
    _, c = _city(city)
    return {"city": c["name"], "attractions": c["attractions"]}


def search_flights(origin: str, destination: str) -> dict:
    src, a = _city(origin)
    dst, b = _city(destination)
    flights = FLIGHTS.get((src, dst)) or FLIGHTS.get((dst, src))
    if not flights:
        return {"origin": a["name"], "destination": b["name"], "error": "прямых предложений по этому маршруту нет"}
    return {
        "origin": a["name"], "destination": b["name"], "currency": "RUB",
        "flights": flights, "cheapest_price_rub": min(f["price_rub"] for f in flights),
    }


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    params: dict[str, str]  # имя параметра -> описание
    fn: Callable[..., dict]
    example: dict


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_weather", "текущая погода в городе",
         {"city": "название города"}, get_weather, {"city": "Париж"}),
    Tool("get_local_time", "текущее местное время и дата в городе",
         {"city": "название города"}, get_local_time, {"city": "Токио"}),
    Tool("convert_currency", "перевод суммы из одной валюты в другую по текущему курсу",
         {"amount": "сумма (число)", "from_currency": "код валюты, например USD",
          "to_currency": "код валюты, например RUB"},
         convert_currency, {"amount": 100, "from_currency": "USD", "to_currency": "RUB"}),
    Tool("get_attractions", "главные достопримечательности города",
         {"city": "название города"}, get_attractions, {"city": "Рим"}),
    Tool("search_flights", "авиабилеты между двумя городами с ценами в рублях",
         {"origin": "город вылета", "destination": "город прилёта"},
         search_flights, {"origin": "Москва", "destination": "Стамбул"}),
]}


def execute(name: str, arguments: dict) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"неизвестный инструмент «{name}». Доступны: {', '.join(TOOLS)}"}
    if not isinstance(arguments, dict):
        return {"error": "arguments должен быть JSON-объектом"}
    missing = [p for p in tool.params if p not in arguments]
    if missing:
        return {"error": f"не хватает аргументов: {', '.join(missing)}. Пример: {tool.example}"}
    try:
        return tool.fn(**{p: arguments[p] for p in tool.params})
    except ValueError as e:
        return {"error": str(e)}
