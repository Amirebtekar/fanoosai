import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ModelPerformanceTableContent } from './project-management'

describe('ModelPerformanceTableContent', () => {
  it('shows provider-routed successes as direct without an AvalAI column', () => {
    const html = renderToStaticMarkup(
      <ModelPerformanceTableContent
        models={[{
          ai_model: 'openai/gpt-5.1-chat',
          total_runs: 9,
          successful_runs: 8,
          direct_successful_runs: 8,
          failed_runs: 1,
          success_rate: 88.9,
        }]}
      />,
    )

    expect(html).toContain('موفق مستقیم')
    expect(html).not.toContain('AvalAI')
    expect(html).toContain('ناموفق نهایی')
    expect(html).toContain('۸')
    expect(html).toContain('۸۸٫۹٪')
  })
})
