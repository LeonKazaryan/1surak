import type { TripPlanEvent } from '@/types/api'

/** A real plan from the backend (Antalya, a family of three), with a made-up guide, for the plan tests. */
export const PLAN: TripPlanEvent = {
  "type": "trip_plan",
  "id": "antalya",
  "name": "Анталья",
  "dates": {
    "from": "2026-11-06",
    "to": "2026-11-13",
    "nights": 7
  },
  "dates_fixed": true,
  "party": {
    "adults": 2,
    "children_ages": [
      5
    ]
  },
  "stops": [
    {
      "place_id": "antalya",
      "name": "Анталья",
      "country": "Турция",
      "country_code": "TR",
      "kinds": [
        "sea",
        "city"
      ],
      "check_in": "2026-11-06",
      "check_out": "2026-11-13",
      "nights": 7,
      "photo": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Kaleici.jpg/960px-Kaleici.jpg",
        "width": 960,
        "height": 640,
        "author": "Jane Doe",
        "license": "CC BY-SA 4.0",
        "file_url": "https://commons.wikimedia.org/wiki/File:Kaleici.jpg"
      },
      "source_url": "https://ru.wikivoyage.org/wiki/Анталья",
      "hotel": {
        "id": "antalya-h3",
        "name": "Морской бриз",
        "stars": 4,
        "rating": 8.1,
        "reviews": 2293,
        "area": "у моря",
        "beach_m": 179,
        "meal": "all_inclusive",
        "meal_label": "всё включено",
        "free_cancel_days": 7,
        "pay_at_hotel": false,
        "rooms": 1,
        "nights": 7,
        "night_rub": 15400,
        "total_rub": 107800,
        "check_in": "14:00",
        "check_out": "12:00",
        "reasons": [
          "детский клуб",
          "семейный номер",
          "всё включено",
          "бесплатная отмена"
        ],
        "misses": [],
        "demo": true
      },
      "alternatives": [
        {
          "id": "antalya-h0",
          "name": "Дом у маяка",
          "stars": 3,
          "rating": 9.0,
          "reviews": 638,
          "area": "на первой линии",
          "beach_m": 116,
          "meal": "breakfast",
          "meal_label": "завтраки",
          "free_cancel_days": 1,
          "pay_at_hotel": true,
          "rooms": 1,
          "nights": 7,
          "night_rub": 6100,
          "total_rub": 42700,
          "check_in": "14:00",
          "check_out": "12:00",
          "reasons": [
            "первая линия, до пляжа 116 м",
            "бесплатная отмена",
            "оценка гостей 9,0"
          ],
          "misses": [
            "нет детского клуба"
          ],
          "demo": true
        }
      ],
      "excluded": [
        {
          "name": "Солнечная терраса",
          "stars": 5,
          "reason": "только для взрослых, а с вами ребёнок"
        }
      ],
      "transfer_in": {
        "mode": "car",
        "km": 14,
        "minutes": 35,
        "price_rub": 800
      },
      "transfer_out": {
        "mode": "car",
        "km": 14,
        "minutes": 35,
        "price_rub": 800
      },
      "food_intro": "Турецкая кухня: мясо на углях, мезе и сладости.",
      "dishes": [
        {
          "name": "Пияз",
          "note": "салат из белой фасоли с тахини"
        },
        {
          "name": "Шиш-кебаб",
          "note": ""
        }
      ]
    }
  ],
  "legs": [
    {
      "from": "Москва",
      "to": "Анталья",
      "mode": "flight",
      "km": 2159,
      "hours": 4.0,
      "ticket": {
        "price_rub": 18000,
        "price": "18 000 ₽",
        "airline": "SU",
        "airline_name": "Аэрофлот",
        "logo": "https://pics.avs.io/64/64/SU.png",
        "flight_number": "SU 2134",
        "transfers": 0,
        "hours": 4.0,
        "departure": "2026-11-06 09:40",
        "from_airport": "XXX",
        "to_airport": "AYT",
        "link": "https://www.aviasales.ru/t",
        "direct_available": true
      },
      "departs": "2026-11-06T09:40",
      "arrives": "2026-11-06T13:40",
      "ground_rub": null
    },
    {
      "from": "Анталья",
      "to": "Москва",
      "mode": "flight",
      "km": 2159,
      "hours": 4.0,
      "ticket": {
        "price_rub": 17000,
        "price": "17 000 ₽",
        "airline": "SU",
        "airline_name": "Аэрофлот",
        "logo": "https://pics.avs.io/64/64/SU.png",
        "flight_number": "SU 2134",
        "transfers": 0,
        "hours": 4.0,
        "departure": "2026-11-13 15:00",
        "from_airport": "XXX",
        "to_airport": "MOW",
        "link": "https://www.aviasales.ru/t",
        "direct_available": true
      },
      "departs": "2026-11-13T15:00",
      "arrives": "2026-11-13T19:00",
      "ground_rub": null
    }
  ],
  "checks": [
    {
      "level": "ok",
      "title": "Прилёт 13:40, заселение с 14:00",
      "text": "В отеле около 14:15, как раз к заселению.",
      "fix": null,
      "kind": "timing"
    },
    {
      "level": "ok",
      "title": "Выезд до 12:00, вылет 15:00",
      "text": "После завтрака и выезда как раз время ехать в аэропорт, около 11:55.",
      "fix": null,
      "kind": "timing"
    },
    {
      "level": "warn",
      "title": "Прилёт 07:00, заселение с 14:00",
      "text": "Можно взять ранний заезд.",
      "fix": {
        "id": "early_check_in:antalya-h1",
        "type": "early_check_in",
        "label": "Ранний заезд в «Морской бриз»",
        "price_rub": 3200
      },
      "kind": "timing"
    }
  ],
  "days": [
    {
      "date": "2026-11-06",
      "title": "Прилёт и первый вечер",
      "place_id": "antalya",
      "items": [
        {
          "kind": "flight",
          "title": "Перелёт Москва → Анталья",
          "time": "09:40",
          "note": "SU 2134, прямой, 4 ч, прилёт в 13:40",
          "spot": null
        },
        {
          "kind": "transfer",
          "title": "Трансфер в отель",
          "time": "13:40",
          "note": "такси, около 35 мин, 800 ₽",
          "spot": null
        },
        {
          "kind": "hotel",
          "title": "Заселение: Морской бриз",
          "time": "14:15",
          "note": null,
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин в отеле",
          "time": "19:30",
          "note": "входит во «всё включено»",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-07",
      "title": "Калеичи",
      "place_id": "antalya",
      "items": [
        {
          "kind": "sight",
          "title": "Калеичи",
          "time": "10:00",
          "note": "Старый город с узкими улочками и гаванью.",
          "spot": {
            "id": "antalya-s1",
            "type": "see",
            "name": "Калеичи",
            "alt": null,
            "summary": "Старый город с узкими улочками и гаванью.",
            "hours": null,
            "price": null,
            "photo": {
              "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Kaleici.jpg/960px-Kaleici.jpg",
              "width": 960,
              "height": 640,
              "author": "Jane Doe",
              "license": "CC BY-SA 4.0",
              "file_url": "https://commons.wikimedia.org/wiki/File:Kaleici.jpg"
            },
            "lat": 36.884,
            "lon": 30.705,
            "source_url": null
          }
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин в отеле",
          "time": "19:30",
          "note": "входит во «всё включено»",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-08",
      "title": "Ворота Адриана",
      "place_id": "antalya",
      "items": [
        {
          "kind": "sight",
          "title": "Ворота Адриана",
          "time": "10:00",
          "note": "Римская арка II века.",
          "spot": {
            "id": "antalya-s2",
            "type": "see",
            "name": "Ворота Адриана",
            "alt": null,
            "summary": "Римская арка II века.",
            "hours": null,
            "price": null,
            "photo": null,
            "lat": 36.885,
            "lon": 30.708,
            "source_url": null
          }
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин: Piyazcı Sami",
          "time": "19:30",
          "note": "Знаменитый пияз и кюфте.",
          "spot": {
            "id": "antalya-f1",
            "type": "eat",
            "name": "Piyazcı Sami",
            "alt": null,
            "summary": "Знаменитый пияз и кюфте.",
            "hours": null,
            "price": null,
            "photo": null,
            "lat": 36.88,
            "lon": 30.7,
            "source_url": null
          }
        }
      ]
    },
    {
      "date": "2026-11-09",
      "title": "Водопад Дюден",
      "place_id": "antalya",
      "items": [
        {
          "kind": "sight",
          "title": "Водопад Дюден",
          "time": "10:00",
          "note": "Водопад, падающий прямо в море.",
          "spot": {
            "id": "antalya-s3",
            "type": "do",
            "name": "Водопад Дюден",
            "alt": null,
            "summary": "Водопад, падающий прямо в море.",
            "hours": null,
            "price": null,
            "photo": null,
            "lat": 36.85,
            "lon": 30.78,
            "source_url": null
          }
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин в отеле",
          "time": "19:30",
          "note": "входит во «всё включено»",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-10",
      "title": "Море и отдых",
      "place_id": "antalya",
      "items": [
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "10:00",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин в отеле",
          "time": "19:30",
          "note": "входит во «всё включено»",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-11",
      "title": "Море и отдых",
      "place_id": "antalya",
      "items": [
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "10:00",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин: попробуйте Пияз",
          "time": "19:30",
          "note": "салат из белой фасоли с тахини",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-12",
      "title": "Море и отдых",
      "place_id": "antalya",
      "items": [
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "10:00",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Обед в отеле",
          "time": "13:30",
          "note": "входит во «всё включено»",
          "spot": null
        },
        {
          "kind": "beach",
          "title": "Пляж и море",
          "time": "15:30",
          "note": "купаться и отдыхать",
          "spot": null
        },
        {
          "kind": "food",
          "title": "Ужин в отеле",
          "time": "19:30",
          "note": "входит во «всё включено»",
          "spot": null
        }
      ]
    },
    {
      "date": "2026-11-13",
      "title": "Дорога домой",
      "place_id": "antalya",
      "items": [
        {
          "kind": "hotel",
          "title": "Выезд из отеля",
          "time": "11:55",
          "note": null,
          "spot": null
        },
        {
          "kind": "transfer",
          "title": "Трансфер в аэропорт",
          "time": "11:55",
          "note": "такси, около 35 мин, 800 ₽",
          "spot": null
        },
        {
          "kind": "flight",
          "title": "Перелёт Анталья → Москва",
          "time": "15:00",
          "note": "SU 2134, прямой, 4 ч",
          "spot": null
        }
      ]
    }
  ],
  "costs": {
    "flights": 105000,
    "hotels": 107800,
    "transfers": 1600,
    "ground": 0,
    "total": 214400,
    "per_person": 71467,
    "guests": 3,
    "flights_complete": true,
    "budget": null,
    "over_by": null
  },
  "unmet": [],
  "changes": [],
  "summary": [
    "Анталья",
    "Ноябрь · 7 ночей",
    "2 взрослых + 1 ребёнок (5 лет)"
  ],
  "currency": {
    "code": "RUB",
    "sign": "₽",
    "glyph": "₽",
    "per_rub": 1
  }
}
