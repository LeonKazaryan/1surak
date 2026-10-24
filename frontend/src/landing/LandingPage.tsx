import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRightIcon } from '@heroicons/react/20/solid'
import { CardNav, type CardNavItem } from '@/components/CardNav'
import { Footer } from '@/components/Footer'
import { HeroBackground } from '@/components/HeroBackground'
import { Reveal } from '@/components/Reveal'
import { TextType } from '@/components/TextType'
import { ScrollStack, ScrollStackItem } from '@/components/ui/ScrollStack'
import { EXAMPLE_TRIPS } from '@/lib/exampleTrips'
import {
  HERO_HIGHLIGHTS,
  HERO_PHRASES,
  HERO_TITLE,
  HERO_VIDEO_SRC,
  STEPS,
  TRACK_TASKS,
} from './content'
import { TripPrompt } from './TripPrompt'

const NAV_ITEMS: CardNavItem[] = [
  {
    label: 'Агент',
    bgColor: 'var(--accent)',
    textColor: 'var(--foreground)',
    links: [
      { label: 'Новый чат', href: '/chat' },
      { label: 'Как это работает', href: '#how' },
    ],
  },
  {
    label: 'Трек',
    bgColor: 'var(--secondary)',
    textColor: 'var(--foreground)',
    links: [{ label: 'Задачи трека', href: '#tasks' }],
  },
]

export default function LandingPage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')

  const startChat = (query: string) => {
    const trimmed = query.trim()
    if (trimmed) navigate('/chat', { state: { query: trimmed } })
  }

  const startButton = (
    <button
      type="button"
      onClick={() => navigate('/chat')}
      className="hidden h-9 items-center gap-1.5 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-hover sm:inline-flex"
    >
      Начать
      <ArrowRightIcon className="h-4 w-4" />
    </button>
  )

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <CardNav items={NAV_ITEMS} action={startButton} />

      <section id="hero" className="relative isolate flex min-h-svh flex-col overflow-hidden">
        <HeroBackground videoSrc={HERO_VIDEO_SRC} />
        <div className="relative z-20 mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-[clamp(1.25rem,4vh,2.75rem)] px-4 py-8 text-center">
          <Reveal>
            <h1 className="flex min-h-[2.3em] max-w-[24ch] items-start justify-center text-balance text-[clamp(2.1rem,5.4vw,4.5rem)] font-semibold leading-[1.1] tracking-tight text-foreground">
              <span className="sr-only">{HERO_TITLE}</span>
              <span aria-hidden>
                <TextType
                  text={HERO_PHRASES}
                  highlightWords={HERO_HIGHLIGHTS}
                  highlightClassName="text-highlight"
                  typingSpeed={55}
                  deletingSpeed={32}
                  pauseDuration={3600}
                  cursorClassName="font-normal text-highlight"
                />
              </span>
            </h1>
            <p className="mx-auto mt-[clamp(0.75rem,2vh,1.5rem)] max-w-xl text-[clamp(1rem,1.6vw,1.375rem)] leading-relaxed text-muted-foreground">
              Напишите как есть. Агент уточнит главное, подберёт направление, дорогу, отель и трансфер и соберёт
              поездку.
            </p>
          </Reveal>

          <Reveal delay={150} className="relative z-30 w-full max-w-xl">
            <TripPrompt value={input} onChange={setInput} onSubmit={() => startChat(input)} />
          </Reveal>

          <Reveal delay={230}>
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLE_TRIPS.map((trip) => (
                <button
                  key={trip.label}
                  type="button"
                  onClick={() => startChat(trip.query)}
                  className="min-h-[36px] rounded-full border border-border bg-card/70 px-4 py-1.5 text-sm text-muted-foreground backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:border-primary hover:bg-accent hover:text-foreground"
                >
                  {trip.label}
                </button>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      <main className="flex-1 pb-20">
        <section id="how" className="mx-auto w-full max-w-3xl scroll-mt-24 px-4">
          <ScrollStack useWindowScroll rotationAmount={0.6} blurAmount={1.2}>
            {STEPS.map(({ title, desc }, i) => (
              <ScrollStackItem key={title}>
                <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-2xl font-semibold text-highlight tabular-nums">
                  {i + 1}
                </span>
                <div className="mt-6 text-3xl font-semibold tracking-tight text-foreground">{title}</div>
                <div className="mt-2 text-lg text-muted-foreground">{desc}</div>
              </ScrollStackItem>
            ))}
          </ScrollStack>
        </section>

        <section id="tasks" className="mx-auto w-full max-w-5xl scroll-mt-24 px-4 pt-8">
          <div className="text-center">
            <span className="inline-block rounded-full bg-accent px-3 py-1 text-xs font-semibold uppercase tracking-wider text-foreground">
              Трек «О!дин запрос»
            </span>
            <h2 className="mt-3 text-[clamp(1.6rem,3vw,2.25rem)] font-semibold tracking-tight text-foreground">
              Шесть задач, которые решает агент
            </h2>
            <p className="mx-auto mt-2 max-w-xl text-muted-foreground">
              От размытого «хочу к морю» до собранной поездки с имитацией оплаты.
            </p>
          </div>
          <ol className="mt-8 grid list-none gap-3 p-0 sm:grid-cols-2">
            {TRACK_TASKS.map((task, i) => (
              <li
                key={task}
                data-testid="brief-task"
                className="flex gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground tabular-nums">
                  {i + 1}
                </span>
                <span className="text-[15px] leading-relaxed text-foreground">{task}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <Footer />
    </div>
  )
}
