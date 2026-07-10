'use client'
import { useUser, SignInButton, SignOutButton } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

export default function Home() {
  const { isSignedIn, user } = useUser()
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isSignedIn) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL}/obras/`)
        .then(res => res.json())
        .then(setData)
        .catch(console.error)
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [isSignedIn])

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
      <h1>🏗️ DepaFix Dashboard</h1>
      {!isSignedIn ? (
        <SignInButton mode="modal">
          <button style={{ padding: '10px 20px', background: '#1E3A8A', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Iniciar sesión
          </button>
        </SignInButton>
      ) : (
        <div>
          <p>👋 Bienvenido, {user?.firstName || 'usuario'}</p>
          <SignOutButton>
            <button style={{ padding: '8px 16px', background: '#dc2626', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
              Cerrar sesión
            </button>
          </SignOutButton>
          <h2>📊 Obras recientes</h2>
          {loading ? (
            <p>Cargando...</p>
          ) : (
            <ul>
              {Array.isArray(data) && data.slice(0, 5).map((item, i) => (
                <li key={i}>{item.descripcion || 'Sin nombre'} - ${item.total?.toFixed(0) || 0}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
