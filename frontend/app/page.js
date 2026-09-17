'use client'
import { useState } from 'react'

export default function Home() {
  const [resultado, setResultado] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setCargando(true)
    setError(null)
    setResultado(null)
    const formData = new FormData(e.target)
    try {
      const res = await fetch('http://localhost:8000/api/serviu/analizar-presupuesto', {
        method: 'POST',
        body: formData
      })
      if (!res.ok) throw new Error('Error ' + res.status)
      const data = await res.json()
      setResultado(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <div style={{padding:20,fontFamily:'system-ui',background:'#111827',color:'white',minHeight:'100vh'}}>
      <h1 style={{color:'#60A5FA'}}>🏗️ DepaFix — SERVIU Presupuestos</h1>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:20,marginTop:20}}>
        <div style={{background:'#1F2937',padding:20,borderRadius:12}}>
          <h2>📤 Subir Presupuesto CSV</h2>
          <p style={{fontSize:12,color:'#9CA3AF'}}>Columnas: partida,monto,anticipo,retencion,garantia</p>
          <form onSubmit={handleSubmit}>
            <input type="file" name="archivo" accept=".csv" required style={{margin:'10px 0'}}/>
            <button type="submit" disabled={cargando} style={{padding:'10px 20px',background:cargando?'#4B5563':'#2563EB',color:'white',border:'none',borderRadius:8,cursor:'pointer'}}>
              {cargando ? '⏳ Analizando...' : '📊 Analizar'}
            </button>
          </form>
          {error && <p style={{color:'#FCA5A5',fontSize:14}}>❌ {error}</p>}
        </div>
        <div style={{background:'#1F2937',padding:20,borderRadius:12}}>
          <h2>📈 Resultados</h2>
          {!resultado && <p style={{color:'#6B7280'}}>Sube un archivo para ver resultados.</p>}
          {resultado && (
            <div>
              <p>Subtotal: <strong>${resultado.calculo_financiero?.subtotal_base?.toLocaleString('es-CL')}</strong></p>
              <p>Total IVA 19%: <strong style={{color:'#34D399'}}>${resultado.calculo_financiero?.total_cliente_iva?.toLocaleString('es-CL')}</strong></p>
              <p>Cascada 30/15/5: <strong style={{color:'#60A5FA'}}>${resultado.calculo_financiero?.total_interno_cascada?.toLocaleString('es-CL')}</strong></p>
              <p style={{fontSize:12,color:'#9CA3AF',marginTop:10}}>{resultado.analisis_normativo?.recomendacion}</p>
              {resultado.pdf_generado && <p style={{fontSize:12,color:'#93C5FD'}}>📄 {resultado.pdf_generado}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
