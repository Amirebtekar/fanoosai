import { createFileRoute } from '@tanstack/react-router'
import { PromptAnalyticsPage } from '@/features/prompts/prompt-analytics'

export const Route = createFileRoute('/_authenticated/projects_/$projectId/prompts/$promptId')({
  component: PromptAnalyticsPage,
})
