import { useNavigate } from '@tanstack/react-router'
import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'

export function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-full bg-bg font-vazirmatn" dir="rtl">
      <Header fixed className="bg-bg">
        <h1 className="text-lg font-black">FanoosAI</h1>
      </Header>
      <Main>
        <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
          <Card className="w-full max-w-lg border-border text-center shadow-[6px_6px_0_var(--color-shadow)]">
            <CardContent className="flex flex-col items-center gap-6 py-16">
              <Sparkles className="size-16 text-accent-neon" />
              <h1 className="text-5xl font-black tracking-tight sm:text-6xl lg:text-7xl">FanoosAI</h1>
              <p className="max-w-sm text-base font-medium text-muted-text">مدیریت پرامپت و آنالیز برند با هوش مصنوعی</p>
              <div className="flex flex-wrap justify-center gap-3">
                <Button onClick={() => navigate({ to: '/dashboard' })} className="border-border bg-accent-neon text-fg shadow-[5px_5px_0_var(--color-shadow)] hover:bg-accent-neon/90 font-bold text-base px-6 py-5">
                  ورود به داشبورد
                </Button>
                <Button variant="outline" onClick={() => navigate({ to: '/projects' })} className="border-border bg-card text-fg shadow-[5px_5px_0_var(--color-shadow)] hover:shadow-[3px_3px_0_var(--color-shadow)] font-bold text-base px-6 py-5">
                  مشاهده پروژه‌ها
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </Main>
    </div>
  )
}
