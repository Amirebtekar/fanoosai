import { createFileRoute } from '@tanstack/react-router'
import { SharedReportPage } from '@/features/projects/shared-report'

export const Route = createFileRoute('/shared/$token')({
  component: SharedReportPage,
})
