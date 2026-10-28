/** Where each tool's data comes from: shown while it works, so the numbers on the cards have a name. */
export const TOOL_SOURCES: Record<string, string[]> = {
  search_destinations: ['авиабилеты', 'Open-Meteo', 'Passport Index', 'Wikidata'],
  get_destination: ['Open-Meteo', 'Wikivoyage'],
  search_routes: ['авиабилеты', 'Туту.ру', 'Яндекс.Расписания'],
  search_flights: ['авиабилеты'],
  plan_route: ['авиабилеты'],
  build_trip: ['OpenStreetMap', 'Wikidata', 'авиабилеты'],
  search_hotels: ['OpenStreetMap', 'Wikidata'],
  research: ['Веб-поиск'],
  read_page: ['Страница по ссылке'],
}
