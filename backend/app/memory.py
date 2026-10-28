"""What the agent remembers about the traveller: gathered from their earlier trips in this browser, kept nowhere
else.

The browser lists its chats; with a request it sends the others (`history`). Their briefs say who travelled, on
what budget, what mattered about the hotel, and what was booked or looked at. Nothing here goes into a new trip
by itself: the question cards offer it as «как в прошлый раз», the agent may mention it once, one quick reply
suggests it, and the start screen turns it into ideas. Deleting a chat forgets what came from it; one fact can
also be hidden on its own (its key comes back in `forget`).
"""

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from app.catalog.catalog import KIND_LABELS, load_catalog
from app.catalog.search import MONTHS, MONTHS_IN
from app.hotels.evidence import hotel_wishes
from app.money import CURRENCIES, current_currency
from app.trip.brief import BUDGET_LABELS, TripBrief, plural

MAX_CHATS = 20  # the newest trips say who the traveller is now
BUDGET_KEPT_DAYS = 183  # an older budget is asked again, not offered
SEEN_DAYS = 30  # cards looked at this recently are worth coming back to
SOON_DAYS = 60  # a booked trip this close shows on the start screen
TASTE_TRIPS = 2  # a kind of trip chosen this often is a taste, not a one-off
MAX_WISHES = 4
MAX_IDEAS = 3
ALONE = {1: "один", 2: "вдвоём"}
WITH_KIDS = {1: "взрослый", 2: "двое взрослых"}  # «вдвоём с ребёнком» could be one adult and the child
# a kind of trip as an idea for the start screen: (its label, what «хочу …» it is)
KIND_IDEAS = {
    "sea": ("Море", "к тёплому морю"),
    "mountains": ("Горы", "в горы"),
    "city": ("Города", "посмотреть города"),
    "nature": ("Природа", "на природу"),
    "ski": ("Лыжи", "покататься на лыжах"),
}


@dataclass(frozen=True)
class Fact:
    key: str  # «party», «budget», «wish:с видом на море», «trip:<chat id>»: what `forget` hides
    label: str  # «Кто едет»
    text: str  # «вдвоём + ребёнок 6 лет»
    source: str  # the trip it comes from: «Хургада · ноябрь»
    chat_id: str

    def view(self) -> dict:
        return asdict(self)

    def for_model(self) -> str:
        return f"{self.label}: {self.text} (поездка «{self.source}»)"


@dataclass
class Memory:
    facts: list[Fact] = field(default_factory=list)
    party: dict | None = None  # {"adults", "children", "children_ages"}, the ages as they are today
    budget: dict | None = None  # {"budget_level"} or {"budget_total", "budget_currency"}
    visa_free_only: bool | None = None
    by_land: bool = False
    multi_country: bool = False
    wishes: list[str] = field(default_factory=list)  # about the hotel, in the traveller's words
    kinds: list[str] = field(default_factory=list)  # chosen in TASTE_TRIPS trips or more
    trips: list[dict] = field(default_factory=list)  # booked: {"chat_id", "name", "span", "from", "number"}
    seen: list[dict] = field(default_factory=list)  # looked at, not booked: {"chat_id", "text", "days"}

    def fact(self, key: str) -> Fact | None:
        return next((f for f in self.facts if f.key == key), None)

    def for_model(self) -> list[str]:
        return [f.for_model() for f in self.facts]

    def cards(self, slots: list[str]) -> dict:
        """What the question cards offer as «как в прошлый раз», for the slots they ask: one tap fills it."""
        offered: dict[str, dict] = {}
        if "travelers" in slots and self.party and (f := self.fact("party")):
            offered["travelers"] = {**self.party, "text": f.text, "source": f.source}
        if "budget" in slots and self.budget and (f := self.fact("budget")):
            offered["budget"] = {**_in_user_currency(self.budget), "text": f.text, "source": f.source}
        if "visa" in slots and self.visa_free_only is not None and (f := self.fact("visa")):
            offered["visa"] = {"visa_free_only": self.visa_free_only, "text": f.text, "source": f.source}
        return offered


def _brief(chat: dict) -> TripBrief | None:
    try:
        return TripBrief.model_validate(chat.get("brief") or {})
    except ValueError:
        return None


def _source(chat: dict, b: TripBrief) -> str:
    """The trip a fact comes from, as the traveller would call it: «Хургада · ноябрь», «Море · ноябрь»."""
    named = (b.booked or {}).get("name") or (b.plan or {}).get("name") or b.destination
    kinds = ", ".join(KIND_LABELS[k] for k in b.kinds or []).capitalize()
    name = named or kinds or chat.get("title") or "поездка"
    name = name if len(name) <= 40 else f"{name[:39]}…"
    return f"{name} · {MONTHS[b.month - 1]}" if b.month else name


def party_text(adults: int, ages: list[int], children: int, joiner: str = " + ") -> str:
    """«двое взрослых + ребёнок 6 лет», «вдвоём», «3 взрослых + дети 3 и 8 лет»."""
    if not children:
        return ALONE.get(adults, f"{adults} {plural(adults, ('взрослый', 'взрослых', 'взрослых'))}")
    grown = WITH_KIDS.get(adults, f"{adults} взрослых")
    if len(ages) < children:
        return f"{grown}{joiner}{children} {plural(children, ('ребёнок', 'ребёнка', 'детей'))}"
    years = plural(ages[-1], ("год", "года", "лет"))
    if len(ages) == 1:
        return f"{grown}{joiner}ребёнок {ages[0]} {years}"
    return f"{grown}{joiner}дети {', '.join(map(str, ages[:-1]))} и {ages[-1]} {years}"


def _budget_text(budget: dict) -> str:
    if "budget_total" in budget:
        return f"до {CURRENCIES[budget['budget_currency']].amount(budget['budget_total'])}"
    return BUDGET_LABELS[budget["budget_level"]].lower()


def _in_user_currency(budget: dict) -> dict:
    """A sum named in tenge offered to someone now counting in roubles, rounded the way people say it."""
    if "budget_total" not in budget:
        return budget
    here = current_currency.get()
    if budget["budget_currency"] == here.code:
        return budget
    rub = CURRENCIES[budget["budget_currency"]].to_rub(budget["budget_total"])
    amount = here.from_rub(rub)
    return {
        "budget_total": round(amount, -3) if amount >= 10_000 else round(amount),
        "budget_currency": here.code,
    }


def _seen(b: TripBrief) -> str | None:
    """What was looked at and left: the plan put together, else the first place on the last cards and how many
    more («Рас-эль-Хайма +2»), short enough for a chip."""
    if b.plan:
        return b.plan["name"]
    catalog = load_catalog()
    names = [p.name for i in b.shown if (p := catalog.find(i))]
    if not names:
        return None
    return f"{names[0]} +{len(names) - 1}" if len(names) > 1 else names[0]


def remember(chats: list[dict], today: date, forget: set[str] = frozenset()) -> Memory:
    """The traveller as their trips show them, newest trip first: `chats` are rows of the chats listing, with
    their briefs. The newest trip that says who travels decides the party; a taste needs a few trips."""
    memory = Memory()
    kinds: Counter[str] = Counter()

    def add(key: str, label: str, text: str, source: str, chat_id: str) -> bool:
        if key in forget or memory.fact(key):
            return False
        memory.facts.append(Fact(key, label, text, source, chat_id))
        return True

    for chat in chats[:MAX_CHATS]:
        b = _brief(chat)
        if b is None:
            continue
        said = datetime.fromisoformat(chat["updated_at"]).date()
        source, chat_id = _source(chat, b), chat["id"]
        if memory.party is None and b.adults and len(b.children_ages or []) >= (b.children or 0):
            grown = (today - said).days // 365  # a child of 5 last May is 6 this May
            ages = [age + grown for age in b.children_ages or []]
            text = party_text(b.adults, ages, b.children or 0)
            if add("party", "Кто едет", text, source, chat_id):
                memory.party = {"adults": b.adults, "children": b.children or 0, "children_ages": ages}
        recent = (today - said).days <= BUDGET_KEPT_DAYS
        if memory.budget is None and recent and (b.budget_total or b.budget_level is not None):
            if b.budget_total:
                budget = {"budget_total": b.budget_total, "budget_currency": b.budget_currency or "RUB"}
            else:
                budget = {"budget_level": b.budget_level}
            if add("budget", "Бюджет", _budget_text(budget), source, chat_id):
                memory.budget = budget
        if memory.visa_free_only is None and b.visa_free_only is not None:
            text = "только без визы" if b.visa_free_only else "визы не важны"
            if add("visa", "Визы", text, source, chat_id):
                memory.visa_free_only = b.visa_free_only
        if b.by_land and add("by_land", "Дорога", "поездом, а не самолётом", source, chat_id):
            memory.by_land = True
        if b.multi_country and add("multi_country", "Маршрут", "несколько стран за поездку", source, chat_id):
            memory.multi_country = True
        for wish in hotel_wishes(b.wishes):
            if len(memory.wishes) < MAX_WISHES and add(
                f"wish:{wish.casefold()}", "Важно", wish, source, chat_id
            ):
                memory.wishes.append(wish)
        kinds.update(set(b.kinds or []))
        if b.booked:
            label = "Едете" if date.fromisoformat(b.booked["from"]) >= today else "Были"
            if add(f"trip:{chat_id}", label, f"{b.booked['name']}, {b.booked['span']}", source, chat_id):
                memory.trips.append({**b.booked, "chat_id": chat_id})
        elif not memory.seen and (today - said).days <= SEEN_DAYS and (seen := _seen(b)):  # the latest one
            if add(f"seen:{chat_id}", "Смотрели", seen, source, chat_id):
                memory.seen.append({"chat_id": chat_id, "text": seen, "days": (today - said).days})
    tastes = [k for k, n in kinds.most_common() if n >= TASTE_TRIPS]
    if tastes and add("kinds", "Любите", ", ".join(KIND_LABELS[k] for k in tastes), "ваши поездки", ""):
        memory.kinds = tastes
    return memory


def nudge(memory: Memory, b: TripBrief) -> dict | None:
    """One quick reply from memory under the first cards or plan of a trip: a wish or a habit the traveller had
    last time and has not said this time. It suggests; sending it is the traveller's choice."""
    said = " ".join(b.wishes or []).casefold()
    for wish in memory.wishes:
        if wish.casefold() not in said:
            return {
                "text": f"Как в прошлый раз: {wish}",
                "source": memory.fact(f"wish:{wish.casefold()}").source,
            }
    if memory.by_land and b.by_land is None and (f := memory.fact("by_land")):
        return {"text": "Как в прошлый раз: поездом, где он ходит", "source": f.source}
    return None


def _days(n: int) -> str:
    return f"{n} {plural(n, ('день', 'дня', 'дней'))}"


def _company(party: dict | None) -> str:
    """«двое взрослых и ребёнок 6 лет», for a sentence the traveller would write."""
    if not party:
        return ""
    return party_text(party["adults"], party["children_ages"], party["children"], joiner=" и ")


def ideas(memory: Memory, today: date) -> list[dict]:
    """What the start screen suggests: a booked trip coming up, the trip left half-way, an idea for next month in
    the traveller's way of travelling, then ideas for anyone. Each has `why` when it comes from memory."""
    found: list[dict] = []
    for trip in memory.trips:
        days = (date.fromisoformat(trip["from"]) - today).days
        if 0 <= days <= SOON_DAYS:
            label = f"{trip['name']}: через {_days(days)}" if days else f"{trip['name']}: сегодня"
            question = "Что взять с собой и какая погода будет на мои даты?"
            found.append(
                {
                    "label": label,
                    "query": question,
                    "chat_id": trip["chat_id"],
                    "why": f"бронь {trip['number']}",
                }
            )
            break
    for seen in memory.seen[:1]:
        when = "сегодня" if not seen["days"] else f"{_days(seen['days'])} назад"
        found.append(
            {"label": f"Вернуться: {seen['text']}", "chat_id": seen["chat_id"], "why": f"смотрели {when}"}
        )
    month = today.month % 12 + 1  # next month: this one is mostly gone by the time a trip is planned
    taste = memory.kinds[0] if memory.kinds else None
    personal = bool(taste or memory.party or memory.by_land or memory.multi_country)
    if personal:
        title, wish = KIND_IDEAS[taste or "sea"]
        company = _company(memory.party)
        extra = [
            w
            for w in (
                company,
                "поездом" if memory.by_land else "",
                "несколько стран" if memory.multi_country else "",
            )
            if w
        ]
        kids = " с детьми" if memory.party and memory.party["children"] else ""
        why = [f.text for f in (memory.fact("party"), memory.fact("kinds"), memory.fact("by_land")) if f]
        found.append(
            {
                "label": f"{title} в {MONTHS_IN[month - 1]}{kids}",
                "query": f"Хочу {wish} в {MONTHS_IN[month - 1]}{', ' if extra else ''}{', '.join(extra)}",
                "why": "помню: " + ", ".join(why) if why else None,
            }
        )
    month_in = MONTHS_IN[month - 1]
    # ideas for anyone fill the rest, none repeating what the personal one already offers
    covered = (
        {taste or "sea", "multi"}
        if personal and memory.multi_country
        else {taste or "sea"}
        if personal
        else set()
    )
    for kind, title, query in (
        ("sea", f"Тёплое море в {month_in}", f"Хочу к тёплому морю в {month_in}, без долгих перелётов"),
        ("multi", "Несколько стран за 10 дней", f"Хочу посмотреть несколько стран за 10 дней в {month_in}"),
        ("city", "Выходные недалеко", f"Куда поехать на выходные недалеко в {month_in}?"),
    ):
        if len(found) < MAX_IDEAS and kind not in covered:
            found.append({"label": title, "query": query, "why": None})
    return found[:MAX_IDEAS]
