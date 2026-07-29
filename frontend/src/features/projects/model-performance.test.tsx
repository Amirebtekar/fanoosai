import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ModelPerformanceTableContent } from './project-management'

describe('ModelPerformanceTableContent', () => {
  it('separates direct and AvalAI fallback successes', () => {
    const html = renderToStaticMarkup(
      <ModelPerformanceTableContent
        models={[{
          ai_model: 'openai/gpt-5.1-chat',
          total_runs: 9,
          successful_runs: 8,
          direct_successful_runs: 6,
          fallback_successful_runs: 2,
          failed_runs: 1,
          success_rate: 88.9,
        }]}
      />,
    )

    expect(html).toContain('موفق مستقیم')
    expect(html).toContain('موفق با AvalAI')
    expect(html).toContain('ناموفق نهایی')
    expect(html).toContain('۸۸٫۹٪')
  })
})
