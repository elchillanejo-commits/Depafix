import type { Metadata } from "next"

import { LoginForm } from "./login-form"

export const metadata: Metadata = {
  title: "Iniciar sesión",
}

interface LoginPageProps {
  searchParams: Promise<{ next?: string; error?: string }>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams
  const initialError =
    params.error === "auth_callback"
      ? "El enlace de confirmación no es válido o expiró. Intenta ingresar de nuevo."
      : null

  return (
    <main className="container flex min-h-[calc(100vh-4rem)] items-center justify-center py-10">
      <LoginForm
        next={params.next ?? "/presupuesto"}
        initialError={initialError}
      />
    </main>
  )
}
