import type { RouteCard } from '@/types/api'

/** A real route from the backend (Astana → Almaty → Samarkand → Astana, May): both smart ways go through
 * Tashkent by train instead of flights with transfers. Photos left out. */
export const SMART_ROUTE: RouteCard = {
  "type": "route",
  "id": "almaty+samarkand",
  "name": "Алматы → Самарканд",
  "month_in": "мае",
  "month": "май",
  "stops": [
    {
      "id": "almaty",
      "name": "Алматы",
      "country": "Казахстан",
      "country_code": "KZ",
      "kinds": [
        "city",
        "mountains",
        "ski"
      ],
      "nights": 4,
      "day": 22,
      "sea": null,
      "visa": "без визы",
      "visa_easy": true,
      "highlights": [
        "горы в получасе от города",
        "Шымбулак и Медеу"
      ],
      "photo": null
    },
    {
      "id": "samarkand",
      "name": "Самарканд",
      "country": "Узбекистан",
      "country_code": "UZ",
      "kinds": [
        "city"
      ],
      "nights": 4,
      "day": 27,
      "sea": null,
      "visa": "без визы",
      "visa_easy": true,
      "highlights": [
        "Регистан и Шахи-Зинда",
        "плов"
      ],
      "photo": null
    }
  ],
  "legs": [
    {
      "from": "Астана",
      "to": "Алматы",
      "mode": "flight",
      "km": 971,
      "hours": 2.0,
      "from_stop": null,
      "to_stop": 0,
      "ticket": {
        "price_rub": 4297,
        "price": "4 297 ₽",
        "airline": "FS",
        "airline_name": "FlyArystan",
        "logo": "https://pics.avs.io/64/64/FS.png",
        "flight_number": "FS 7056",
        "transfers": 0,
        "hours": 2.0,
        "departure": "2027-05-12 19:15",
        "from_airport": "NQZ",
        "to_airport": "ALA",
        "link": "https://www.aviasales.ru/search/NQZ1205ALA1?t=FS18101493001810155600000105NQZALA_992c24b092df451363ca48f589156485_4297&search_date=22102026&expected_price_uuid=01a165f6-7cb8-8030-a024-fcd3c24753ce&static_fare_key=TY%7CP0%7CH1%7CL0%7CCH0%7CR0%7CTBC0&itinerary_key=dt1nzx-mTYZA4mreJ4VnjQ&expected_price_source=share&expected_price_currency=rub&expected_price=4297",
        "direct_available": true
      }
    },
    {
      "from": "Алматы",
      "to": "Самарканд",
      "mode": "flight",
      "km": 915,
      "hours": 3.5,
      "from_stop": 0,
      "to_stop": 1,
      "parts": [
        {
          "from": "Алматы",
          "to": "Ташкент",
          "mode": "flight",
          "km": 662,
          "hours": 1.5,
          "from_stop": null,
          "to_stop": null,
          "ticket": {
            "price_rub": 8224,
            "price": "8 224 ₽",
            "airline": "HY",
            "airline_name": "Uzbekistan Airways",
            "logo": "https://pics.avs.io/64/64/HY.png",
            "flight_number": "HY 762",
            "transfers": 0,
            "hours": 1.5,
            "departure": "2027-05-18 10:45",
            "from_airport": "ALA",
            "to_airport": "TAS",
            "link": "https://www.aviasales.ru/search/ALA1805TAS1?t=HY18106371001810642500000090ALATAS_e6c3cde31276367cd2e15b0a01c2aa8b_8224&search_date=19102026&expected_price_uuid=01a154e9-3819-8030-65b2-c0cd46f5367a&static_fare_key=TY%7CP1%7CH1%7CL0%7CCH0%7CR0%7CTBC0&itinerary_key=jd6my2dfSH0l6HAHA75uFw&expected_price_source=share&expected_price_currency=rub&expected_price=8224",
            "direct_available": true
          }
        },
        {
          "from": "Ташкент",
          "to": "Самарканд",
          "mode": "ground",
          "km": 267,
          "hours": 2.0,
          "from_stop": null,
          "to_stop": null,
          "ground": {
            "mode": "train",
            "source": "Туту.ру, расписание поездов",
            "name": "Поезд 776Ф",
            "departs": "13:56",
            "arrives": "16:09",
            "hours": 2.0,
            "price_rub": 3674,
            "fare": "сидячий",
            "link": "https://www.tutu.ru/poezda/rasp_d.php?nnst1=2900000&nnst2=2900700",
            "dated": false,
            "options": 10,
            "wait_hours": 1.0
          }
        }
      ],
      "via": "Ташкент",
      "price_rub": 11898,
      "instead": {
        "price_rub": 37089,
        "transfers": 1,
        "hours": 10.5,
        "airline": "Turkish Airlines"
      }
    },
    {
      "from": "Самарканд",
      "to": "Астана",
      "mode": "flight",
      "km": 1327,
      "hours": 6.0,
      "from_stop": 1,
      "to_stop": null,
      "parts": [
        {
          "from": "Самарканд",
          "to": "Ташкент",
          "mode": "ground",
          "km": 267,
          "hours": 4.0,
          "from_stop": null,
          "to_stop": null,
          "ground": {
            "mode": "train",
            "source": "Туту.ру, расписание поездов",
            "name": "Поезд 123Ф",
            "departs": "00:33",
            "arrives": "04:48",
            "hours": 4.0,
            "price_rub": 1387,
            "fare": "плацкарт",
            "link": "https://www.tutu.ru/poezda/rasp_d.php?nnst1=2900700&nnst2=2900000",
            "dated": false,
            "options": 10,
            "wait_hours": 7.5
          }
        },
        {
          "from": "Ташкент",
          "to": "Астана",
          "mode": "flight",
          "km": 1108,
          "hours": 2.0,
          "from_stop": null,
          "to_stop": null,
          "ticket": {
            "price_rub": 7471,
            "price": "7 471 ₽",
            "airline": "HY",
            "airline_name": "Uzbekistan Airways",
            "logo": "https://pics.avs.io/64/64/HY.png",
            "flight_number": "HY 721",
            "transfers": 0,
            "hours": 2.0,
            "departure": "2027-05-21 15:10",
            "from_airport": "TAS",
            "to_airport": "NQZ",
            "link": "https://www.aviasales.ru/search/TAS2105NQZ1?t=HY18109122001810919400000120TASNQZ_a2a7b60572738ba955b5a079693e2ff5_7471&search_date=23102026&expected_price_uuid=01a16aa4-a924-8031-2ae8-2e76cfc81469&static_fare_key=TY%7CP1%7CH1%7CL0%7CCH0%7CR0%7CTBC0&itinerary_key=XZeJA2j6JN6UAJFGpyKnSg&expected_price_source=share&expected_price_currency=rub&expected_price=7471",
            "direct_available": true
          }
        }
      ],
      "via": "Ташкент",
      "price_rub": 8858,
      "instead": {
        "price_rub": 46864,
        "transfers": 2,
        "hours": 9.5,
        "airline": "FLYONE Armenia"
      }
    }
  ],
  "total_rub": 25053,
  "total_complete": true,
  "dates_chained": true,
  "match": 94,
  "interests": [
    {
      "kind": "city",
      "label": "город",
      "covered": true,
      "wanted": false
    },
    {
      "kind": "mountains",
      "label": "горы",
      "covered": true,
      "wanted": false
    },
    {
      "kind": "ski",
      "label": "горные лыжи",
      "covered": true,
      "wanted": false
    }
  ],
  "kids": "можно с детьми",
  "why": "Алматы с горами и Самарканд с медресе: туда и обратно через Ташкент поездом, а не с пересадками.",
  "tradeoff": null
}
