import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchChats } from '@/api/client'
import { getMyChats } from '@/chat/chatStorage'
import type { ChatMeta } from '@/types/api'
import { CardNav } from '@/components/CardNav'
import { DepartureCityPicker } from '@/components/DepartureCityPicker'
import { CurrencyPicker } from '@/components/CurrencyPicker'
import { Footer } from '@/components/Footer'
import { HeroBackground } from '@/components/HeroBackground'
import { Reveal } from '@/components/Reveal'
import { TextType } from '@/components/TextType'
import { useSmoothScroll } from '@/hooks/use-smooth-scroll'
import { IdeaChips } from '@/chat/memory/IdeaChips'
import { useMemory } from '@/chat/memory/useMemory'
import type { Idea } from '@/types/api'
import { HERO_HIGHLIGHTS, HERO_PHRASES, HERO_TITLE, HERO_VIDEO_SRC } from './content'
import { TripPrompt } from './TripPrompt'
import { TripRoute } from './TripRoute'
import { TripsMenu } from './TripsMenu'

const MENU_TRIPS = 3

export default function LandingPage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [tripIds] = useState(() => getMyChats().slice(0, MENU_TRIPS))
  const [trips, setTrips] = useState<ChatMeta[]>([])

  useEffect(() => {
    if (!tripIds.length) return
    fetchChats(tripIds)
      .then(({ items }) => setTrips(tripIds.flatMap((id) => items.filter((trip) => trip.id === id))))
      .catch(() => setTrips([]))
  }, [tripIds])
  useSmoothScroll()

  const memory = useMemory()
  // an idea about an earlier trip opens it with the question ready, the traveller sends it
  const pickIdea = (idea: Idea) => {
    if (idea.chat_id) navigate(`/chat/${idea.chat_id}`, { state: idea.query ? { draft: idea.query } : null, viewTransition: true })
    else if (idea.query) startChat(idea.query)
  }
  const startChat = (query: string) => {
    const trimmed = query.trim()
    if (trimmed) navigate('/chat', { state: { query: trimmed }, viewTransition: true })
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <CardNav
        action={
          <span className="flex items-center gap-1.5">
            <DepartureCityPicker />
            <CurrencyPicker />
          </span>
        }
      >
        <TripsMenu hasTrips={tripIds.length > 0} trips={trips} />
      </CardNav>

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
              Напишите как есть, агент соберёт остальное.
            </p>
          </Reveal>

          <Reveal delay={150} className="relative z-30 w-full max-w-xl">
            <TripPrompt value={input} onChange={setInput} onSubmit={() => startChat(input)} />
          </Reveal>

          <Reveal delay={230} className="self-stretch">
            <IdeaChips ideas={memory.ideas} failed={memory.failed} onPick={pickIdea} className="-mx-4" surface="bg-card/70 backdrop-blur-sm" />
          </Reveal>
        </div>
      </section>

      <main className="flex-1">
        <TripRoute />
      </main>

      <Footer />
    </div>
  )
}
