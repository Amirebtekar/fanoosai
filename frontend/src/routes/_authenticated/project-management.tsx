import { createFileRoute } from '@tanstack/react-router'
import { ProjectManagementListPage } from '@/features/projects/project-management-list'

export const Route = createFileRoute('/_authenticated/project-management')({
  component: ProjectManagementListPage,
})
