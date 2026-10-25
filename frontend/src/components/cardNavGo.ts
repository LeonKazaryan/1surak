import { createContext } from 'react'

export type CardNavGo = (href: string, state?: unknown) => void

/** Closes the menu, then goes to the page. Provided by CardNav to whatever it renders as its body. */
export const CardNavGoContext = createContext<CardNavGo>(() => {})
