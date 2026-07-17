import { createFileRoute, redirect } from '@tanstack/react-router'
import { LoginPage } from '@/features/auth/login-page'

export const Route = createFileRoute('/sign-in')({
  beforeLoad: () => {
    if (localStorage.getItem('access_token')) throw redirect({ to: '/' })
  },
  component: LoginPage,
})
