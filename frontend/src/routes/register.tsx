import { createFileRoute, redirect } from '@tanstack/react-router'
import { RegisterPage } from '@/features/auth/register-page'

export const Route = createFileRoute('/register')({
  beforeLoad: () => {
    if (localStorage.getItem('access_token')) throw redirect({ to: '/' })
  },
  component: RegisterPage,
})
