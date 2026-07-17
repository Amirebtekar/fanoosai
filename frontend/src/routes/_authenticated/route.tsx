import { createFileRoute, redirect } from '@tanstack/react-router'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'
import { getCurrentUser } from '@/lib/api'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async () => {
    try {
      await getCurrentUser()
    } catch {
      throw redirect({ to: '/sign-in' })
    }
  },
  component: AuthenticatedLayout,
})
