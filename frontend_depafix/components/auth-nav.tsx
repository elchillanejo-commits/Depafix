"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import type { User } from "@supabase/supabase-js"

import { createClient } from "@/lib/supabase/client"
import { Button, buttonVariants } from "@/components/ui/button"

export function AuthNav() {
  const router = useRouter()
  const [supabase] = useState(() => createClient())
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    supabase.auth.getUser().then(({ data }) => {
      if (!active) {
        return
      }
      setUser(data.user)
      setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [supabase])

  if (loading) {
    return null
  }

  if (!user) {
    return (
      <Link
        href="/login"
        className={buttonVariants({ variant: "outline", size: "sm" })}
      >
        Iniciar sesión
      </Link>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden max-w-40 truncate text-sm text-muted-foreground sm:inline">
        {user.email}
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={async () => {
          await supabase.auth.signOut()
          router.push("/login")
          router.refresh()
        }}
      >
        Salir
      </Button>
    </div>
  )
}
