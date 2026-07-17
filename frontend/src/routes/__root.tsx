import { type QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Toaster } from '@/components/ui/sonner'
import { NavigationProgress } from '@/components/navigation-progress'

export function GeneralError() {
  return <div className="flex items-center justify-center min-h-screen p-8"><div className="text-center"><h1 className="text-2xl font-bold mb-2">خطایی رخ داد</h1><p className="text-muted-foreground">لطفاً دوباره تلاش کنید</p></div></div>
}

export function NotFoundError() {
  return <div className="flex items-center justify-center min-h-screen p-8"><div className="text-center"><h1 className="text-2xl font-bold mb-2">صفحه پیدا نشد</h1><p className="text-muted-foreground">آدرس وارد شده معتبر نیست</p></div></div>
}

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({
  component: () => {
    return (
      <>
        <NavigationProgress />
        <Outlet />
        <Toaster duration={5000} />
        {import.meta.env.MODE === 'development' && (
          <>
            <ReactQueryDevtools buttonPosition='bottom-left' />
            <TanStackRouterDevtools position='bottom-right' />
          </>
        )}
      </>
    )
  },
  notFoundComponent: NotFoundError,
  errorComponent: GeneralError,
})
