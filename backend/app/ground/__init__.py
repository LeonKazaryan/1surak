"""Trains and buses between cities: real timetables and fares where an open source has them.

Three sources, all free:
- Tutu.ru trains through Travelpayouts (suggest.travelpayouts.com, service=tutu_trains): the timetable between
  two stations with a fare per class. It covers the former Soviet railways: Russia, Kazakhstan, Uzbekistan,
  Kyrgyzstan, Belarus, Azerbaijan. Fares are the timetable's typical ones, not a live seat search.
- FlixBus (the JSON API its own website uses, undocumented): rides on a given day with the fare, for Europe and
  Turkey (Kamil Koç). Unofficial, so it is easy to turn off (FLIXBUS=false) and every failure is «no data».
- Yandex.Rasp (official, a free key in YANDEX_RASP_KEY): trains, suburban trains and buses on a given day in
  local times, with fares for much of Russia. Its terms require a credit line next to its data.

Nothing here raises: a source that is down or blocked means the leg falls back to an estimate by distance.
"""

from app.ground.model import Ground, GroundOption, GroundRoute, NoGround
from app.ground.service import GroundTransport, configure, transport

__all__ = ["Ground", "GroundOption", "GroundRoute", "GroundTransport", "NoGround", "configure", "transport"]
