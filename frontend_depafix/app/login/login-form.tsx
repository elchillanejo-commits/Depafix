"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { createClient } from "@/lib/supabase/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"

interface LoginFormProps {
  next: string
  initialError?: string | null
}

function normalizeRedirect(next: string) {
  if (!next.startsWith("/") || next.startsWith("//")) {
    return "/presupuesto"
  }
  return next
}

function translateAuthError(message: string) {
  const errors: Record<string, string> = {
    "Invalid login credentials": "Correo o contraseña incorrectos.",
    "Email not confirmed": "Debes confirmar tu correo antes de iniciar sesión.",
    "User already registered": "Ya existe una cuenta con este correo.",
    "Password should be at least 6 characters":
      "La contraseña debe tener al menos 6 caracteres.",
  }
  return errors[message] ?? message
}

export function LoginForm({ next, initialError = null }: LoginFormProps) {
  const router = useRouter()
  const [supabase] = useState(() => createClient())
  const [mode, setMode] = useState<"login" | "signup">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(initialError)
  const [message, setMessage] = useState<string | null>(null)

  const redirectTo = normalizeRedirect(next)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    setMessage(null)

    try {
      if (mode === "login") {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        })

        if (signInError) {
          setError(translateAuthError(signInError.message))
          return
        }

        router.push(redirectTo)
        router.refresh()
        return
      }

      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(redirectTo)}`,
        },
      })

      if (signUpError) {
        setError(translateAuthError(signUpError.message))
        return
      }

      if (data.session) {
        router.push(redirectTo)
        router.refresh()
        return
      }

      setMessage(
        "Cuenta creada. Revisa tu correo para confirmar el registro."
      )
    } catch (cause) {
      setError(
        cause instanceof Error
          ? `No pudimos conectar con Supabase: ${cause.message}`
          : "Error inesperado al autenticar."
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>
          {mode === "login" ? "Ingresar a DepaFix" : "Crear cuenta"}
        </CardTitle>
        <CardDescription>
          {mode === "login"
            ? "Usa tu correo y contraseña de Supabase."
            : "Regístrate para generar presupuestos protegidos."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Correo
            </label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="tu@correo.cl"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">
              Contraseña
            </label>
            <Input
              id="password"
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              required
              minLength={6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Mínimo 6 caracteres"
            />
          </div>

          {error ? (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          ) : null}

          {message ? (
            <p role="status" className="text-sm text-muted-foreground">
              {message}
            </p>
          ) : null}

          <Button type="submit" disabled={loading} className="w-full">
            {loading
              ? "Procesando..."
              : mode === "login"
                ? "Ingresar"
                : "Crear cuenta"}
          </Button>

          <Button
            type="button"
            variant="link"
            className="w-full"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login")
              setError(null)
              setMessage(null)
            }}
          >
            {mode === "login"
              ? "¿No tienes cuenta? Regístrate"
              : "Ya tengo cuenta. Ingresar"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
