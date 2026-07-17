import { createFileRoute } from '@tanstack/react-router'
import { ProjectDetailPage } from '@/features/projects/project-detail'

export const Route = createFileRoute('/_authenticated/projects_/$id')({
  component: ProjectDetailPage,
})
