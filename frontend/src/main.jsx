import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ApolloClient, InMemoryCache, ApolloProvider } from '@apollo/client'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Inventario from './pages/Inventario'
import Proveedores from './pages/Proveedores'
import Presupuestos from './pages/Presupuestos'

const client = new ApolloClient({
  uri: '/graphql',
  cache: new InMemoryCache()
})

function App() {
  return (
    <ApolloProvider client={client}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="inventario" element={<Inventario />} />
            <Route path="proveedores" element={<Proveedores />} />
            <Route path="presupuestos" element={<Presupuestos />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ApolloProvider>
  )
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />)
