import { createFileRoute } from '@tanstack/react-router'
import { ProjectsPage } from '@/features/projects/projects-list'

export const Route = createFileRoute('/_authenticated/projects')({
  component: ProjectsPage,
})
