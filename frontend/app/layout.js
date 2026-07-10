import { ClerkProvider } from '@clerk/nextjs'
import './globals.css'

export const metadata = {
  title: 'DepaFix - Dashboard',
  description: 'Gestión de mantención y proyectos',
}

export default function RootLayout({ children }) {
  return (
    <ClerkProvider>
      <html lang="es">
        <body>{children}</body>
      </html>
    </ClerkProvider>
  )
}
