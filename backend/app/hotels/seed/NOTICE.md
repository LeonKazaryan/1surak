# Licence notice for hotels.json

`hotels.json` lists real hotels around the catalogue places. Rebuild it with
`cd backend && .venv/bin/python -m scripts.build_hotels_seed` (add `--osm` for OpenStreetMap).

- **Wikidata** (names, coordinates, the photo link): CC0, https://www.wikidata.org
- **OpenStreetMap** (names, coordinates, stars, websites): © OpenStreetMap contributors, available under the
  Open Database License (ODbL 1.0), https://www.openstreetmap.org/copyright. Rows with an `osm` id come from it;
  this file as a whole is offered under the ODbL.
- **Photos**: Wikimedia Commons, each under its own free licence; the author and licence are stored per photo
  and shown with it.

No prices, ratings, room types or amenities are stored here: prices are estimated offers (`app/hotels/offers.py`)
and are labelled as estimates wherever they are shown.
