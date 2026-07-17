import {
  LayoutDashboard,
  Home,
  Command,
} from 'lucide-react'
import {
  IconFolder,
  IconChartBar,
} from '@tabler/icons-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  user: {
    name: 'کاربر',
    email: '',
    avatar: '/avatars/shadcn.jpg',
  },
  teams: [
    {
      name: 'FanoosAI',
      logo: Command,
      plan: 'مدیریت پرامپت',
    },
  ],
  navGroups: [
    {
      title: 'عمومی',
      items: [
        {
          title: 'خانه',
          url: '/',
          icon: Home,
        },
        {
          title: 'داشبورد',
          url: '/dashboard',
          icon: LayoutDashboard,
        },
        {
          title: 'پروژه‌ها',
          url: '/projects',
          icon: IconFolder,
        },
        {
          title: 'آنالیتیکس',
          url: '/analytics',
          icon: IconChartBar,
        },
      ],
    },
  ],
}
