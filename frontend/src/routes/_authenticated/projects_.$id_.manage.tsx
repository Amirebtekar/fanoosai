import { createFileRoute } from '@tanstack/react-router'
import { ProjectManagementPage } from '@/features/projects/project-management'

export const Route = createFileRoute('/_authenticated/projects_/$id_/manage')({
  component: ProjectManagementPage,
})
