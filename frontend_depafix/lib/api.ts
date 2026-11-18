import { createClient } from "@/lib/supabase/client"

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const supabase = createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session) {
    throw new ApiError("Tu sesión expiró. Vuelve a iniciar sesión.", 401)
  }

  const headers = new Headers(init.headers)
  headers.set("Authorization", `Bearer ${session.access_token}`)

  const response = await fetch(`${API_URL}${path}`, { ...init, headers })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `Error ${response.status}`
    throw new ApiError(detail, response.status)
  }

  return response
}
