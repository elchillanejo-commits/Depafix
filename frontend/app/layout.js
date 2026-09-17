import './globals.css'

export const metadata = {
  title: 'DepaFix - Dashboard',
  description: 'Gestión de mantención y proyectos',
}

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  )
}
