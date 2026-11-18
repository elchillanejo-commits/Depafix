"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { ApiError, apiFetch } from "@/lib/api"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

interface MeResponse {
  user_id: string
  email: string | null
  role: string | null
}

export default function CuentaPage() {
  const router = useRouter()
  const [me, setMe] = useState<MeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch("/api/v1/me")
      .then((response) => response.json())
      .then((data: MeResponse) => setMe(data))
      .catch((cause) => {
        if (
          cause instanceof ApiError &&
          (cause.status === 401 || cause.status === 403)
        ) {
          router.push("/login?next=/cuenta")
          return
        }
        setError(
          cause instanceof Error ? cause.message : "Error inesperado al cargar."
        )
      })
  }, [router])

  return (
    <main className="container flex min-h-[calc(100vh-4rem)] items-center justify-center py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Mi cuenta</CardTitle>
          <CardDescription>
            Datos entregados por el backend al validar el JWT de Supabase.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {error ? <p className="text-destructive">{error}</p> : null}
          {!error && !me ? (
            <p className="text-muted-foreground">Cargando...</p>
          ) : null}
          {me ? (
            <dl className="space-y-2">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="truncate font-medium">{me.email ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Rol</dt>
                <dd className="font-medium">{me.role ?? "-"}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">User ID</dt>
                <dd className="truncate font-mono text-xs">{me.user_id}</dd>
              </div>
            </dl>
          ) : null}
        </CardContent>
      </Card>
    </main>
  )
}
