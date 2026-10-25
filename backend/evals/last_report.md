# Eval: 27/28 сценариев пройдено

Модель `gpt-5.4-mini`, запуск 2026-10-25 14:34, кейсы из `evals/cases.json`.

| Метрика | Значение |
|---|---|
| Сценарии пройдены | 27 из 28 (96%) |
| Уточняющих вопросов в среднем | 0.4 |
| До первого ответа, медиана | 2.7 с |
| Числа не из инструментов | 0 |
| Ошибки стыковок | проверим, когда появятся билеты и отели |
| Поиск информации (research) | 11 вызовов: из базы знаний 3, из интернета 8, остальное без ответа |

| Кейс | Тип | Итог | Инструменты | Вопросов | Первый ответ | Всего | Что не так |
|---|---|---|---|---|---|---|---|
| golden | inspiration | ✅ | search_destinations | 1 | 3.3 с | 4.5 с |  |
| golden_why_not_turkey | replan | ✅ | search_destinations | 2 | 3.8 с | 9.5 с |  |
| golden_source | robustness | ✅ | search_destinations | 2 | 3.2 с | 11.9 с |  |
| quiet_nature_no_plane | inspiration | ✅ | search_destinations | 1 | 3.0 с | 4.5 с |  |
| ski_january | inspiration | ✅ | search_destinations | 0 | 2.2 с | 3.8 с |  |
| new_year_couple | inspiration | ✅ | search_destinations | 1 | 2.3 с | 5.1 с |  |
| winter_two_kids | inspiration | ✅ | search_destinations | 0 | 2.7 с | 4.5 с |  |
| food_and_walks | inspiration | ✅ | search_destinations | 1 | 2.5 с | 3.2 с |  |
| from_kazan_sea_december | constraints | ✅ | search_destinations | 0 | 2.7 с | 5.0 с |  |
| europe_warm_no_visa | impossible | ✅ | search_destinations | 0 | 2.6 с | 4.0 с |  |
| maldives_cheap | impossible | ✅ | search_destinations | 0 | 2.7 с | 4.4 с |  |
| paris_weekend | impossible | ✅ | get_destination | 1 | 2.4 с | 2.9 с |  |
| kazan_concrete_hotel | concrete | ✅ | get_destination | 0 | 2.2 с | 3.4 с |  |
| typos | robustness | ✅ | search_destinations | 1 | 2.7 с | 5.0 с |  |
| english | robustness | ✅ | search_destinations | 1 | 2.5 с | 4.1 с |  |
| prompt_injection | robustness | ✅ | – | 0 | 1.0 с | 1.8 с |  |
| off_topic_code | robustness | ✅ | – | 0 | 1.0 с | 1.5 с |  |
| tdac_phuket_kid | research | ✅ | research (интернет) | 0 | 7.5 с | 10.3 с |  |
| china_visa_free_hainan | research | ✅ | research, search_destinations (интернет) | 0 | 13.1 с | 15.3 с |  |
| uae_medicines | research | ✅ | get_destination, research (интернет) | 0 | 16.2 с | 20.7 с |  |
| hurghada_snorkel_area | research | ❌ | get_destination | 0 | 2.4 с | 4.4 с | did not call research; no source link or site named in the answer |
| anapa_airport_open | research | ✅ | get_destination, research (интернет) | 1 | 10.7 с | 12.3 с |  |
| istanbul_events_dates | research | ✅ | research (интернет) | 0 | 13.4 с | 19.3 с |  |
| kazan_food_weekend | research | ✅ | get_destination, research (база знаний) | 0 | 4.4 с | 6.6 с |  |
| dog_train_sochi | research | ✅ | research (интернет) | 0 | 17.6 с | 18.9 с |  |
| georgia_internal_passport | research | ✅ | research (интернет) | 0 | 10.1 с | 10.9 с |  |
| family_january_full | combined | ✅ | search_destinations, research (интернет) | 0 | 15.5 с | 18.1 с |  |
| tdac_then_kid | research | ✅ | research (база знаний, база знаний) | 0 | 2.5 с | 8.8 с |  |
