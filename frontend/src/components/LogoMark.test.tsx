import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LogoMark } from './LogoMark'

describe('LogoMark', () => {
  it('should show the mascot as a decorative image at the given size', () => {
    const { container } = render(<LogoMark className="h-14 w-14" />)

    const image = container.querySelector('img')
    expect(image).toHaveAttribute('src', '/logo.png')
    expect(image).toHaveAttribute('alt', '')
    expect(image).toHaveClass('h-14', 'w-14')
  })
})
