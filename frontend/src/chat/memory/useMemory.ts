import { useEffect, useState } from 'react'
import { fetchMemory } from '@/api/client'
import type { MemoryResponse } from '@/types/api'
import { getMyChats } from '../chatStorage'
import { forgetFact, getForgotten } from './forgotten'

// the last answer, shown at once on the next screen while it is asked again: a trip may have been booked since
let last: MemoryResponse | null = null

/** What the browser's trips say about the traveller and the ideas from it; `forget` hides one fact for good. */
export function useMemory() {
  const [version, setVersion] = useState(0)
  const [data, setData] = useState<MemoryResponse | null>(last)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchMemory(getMyChats(), getForgotten(), controller.signal).then(
      (found) => {
        last = found
        setData(found)
        setFailed(false)
      },
      () => !controller.signal.aborted && setFailed(true),
    )
    return () => controller.abort()
  }, [version])

  return {
    facts: data?.facts ?? [],
    /** null while the first answer loads */
    ideas: data?.ideas ?? null,
    failed,
    forget: (key: string) => {
      forgetFact(key)
      setData((prev) => prev && { ...prev, facts: prev.facts.filter((f) => f.key !== key) })
      setVersion((v) => v + 1) // the ideas built on it change too
    },
  }
}
