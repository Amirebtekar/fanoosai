import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ProjectSection } from './project-management'

describe('ProjectSection', () => {
  it('collapses optional sections and can keep the primary section open', () => {
    const collapsed = renderToStaticMarkup(
      <ProjectSection title="گزارش‌ها"><span>محتوا</span></ProjectSection>,
    )
    const open = renderToStaticMarkup(
      <ProjectSection title="پرامپت‌ها" defaultOpen><span>محتوا</span></ProjectSection>,
    )

    expect(collapsed).not.toContain(' open=""')
    expect(open).toContain(' open=""')
  })
})
