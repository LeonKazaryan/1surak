import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HeroBackground } from './HeroBackground'

describe('HeroBackground', () => {
  it('should render the gradient fallback and no video when no source is set', () => {
    const { container, getByTestId } = render(<HeroBackground />)

    expect(container.querySelector('video')).toBeNull()
    expect(getByTestId('hero-fallback')).toBeInTheDocument()
  })

  it('should render a muted looping video when a source is set', () => {
    const { container, queryByTestId } = render(<HeroBackground videoSrc="/hero.webm" />)

    const video = container.querySelector('video')
    expect(video).toHaveAttribute('src', '/hero.webm')
    expect(video?.muted).toBe(true)
    expect(video?.loop).toBe(true)
    expect(queryByTestId('hero-fallback')).toBeNull()
  })
})
