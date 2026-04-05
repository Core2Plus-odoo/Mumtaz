import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ZAKI — CFO AI',
  description: 'Your AI-powered CFO for smarter financial decisions',
  icons: { icon: '/favicon.svg' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
