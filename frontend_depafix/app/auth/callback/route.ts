import { NextResponse } from "next/server"

import { createClient } from "@/lib/supabase/server"

function safeNext(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/presupuesto"
  }
  return value
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get("code")
  const next = safeNext(searchParams.get("next"))

  const forwardedHost = request.headers.get("x-forwarded-host")
  const forwardedProto = request.headers.get("x-forwarded-proto")
  const host = forwardedHost ?? request.headers.get("host")
  const protocol =
    forwardedProto ?? new URL(request.url).protocol.replace(":", "")
  const origin = host ? `${protocol}://${host}` : new URL(request.url).origin

  if (code) {
    const supabase = await createClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_callback`)
}
