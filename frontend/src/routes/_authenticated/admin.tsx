import { createFileRoute, redirect } from '@tanstack/react-router'
import { getCurrentUser } from '@/lib/api'
import { AdminPanelPage } from '@/features/admin/admin-panel'

export const Route = createFileRoute('/_authenticated/admin')({
  beforeLoad: async () => {
    try {
      const user = await getCurrentUser()
      if (!user.is_superuser) throw redirect({ to: '/' })
    } catch (error) {
      if (error && typeof error === 'object' && 'to' in (error as Record<string, unknown>)) throw error
      throw redirect({ to: '/sign-in' })
    }
  },
  component: AdminPanelPage,
})
