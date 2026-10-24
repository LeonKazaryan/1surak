export interface ExampleTrip {
  label: string
  query: string
}

export const EXAMPLE_TRIPS: ExampleTrip[] = [
  {
    label: 'Тёплое море в ноябре',
    query: 'Хочу к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов',
  },
  { label: 'Казань на выходные', query: 'Казань на выходные вдвоём, отель в центре до 8 000 ₽ за ночь' },
  { label: 'Новый год на поезде', query: 'Куда поехать на новогодние праздники на поезде из Москвы?' },
]
