import { createFileRoute } from '@tanstack/react-router'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Card, CardContent } from '@/components/ui/card'

function AnalyticsDisabledPage() {
  return (
    <div className='min-h-full bg-bg font-vazirmatn' dir='rtl'>
      <Header fixed className='bg-bg'>
        <h1 className='text-lg font-black'>آنالیتیکس</h1>
      </Header>
      <Main fixed>
        <Card className='border-border shadow-[6px_6px_0_var(--color-shadow)]'>
          <CardContent className='py-10 text-center'>
            <h2 className='text-xl font-black'>این بخش موقتاً غیرفعال است</h2>
            <p className='mt-2 text-sm font-medium text-muted-text'>آنالیتیکس پس از رفع مشکل دوباره فعال می‌شود.</p>
          </CardContent>
        </Card>
      </Main>
    </div>
  )
}

export const Route = createFileRoute('/_authenticated/analytics')({
  component: AnalyticsDisabledPage,
})
