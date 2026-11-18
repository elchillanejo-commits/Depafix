"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";

type Item = { desc: string; precio: number };

export default function PresupuestoPage() {
  const router = useRouter();
  const [direccion, setDireccion] = useState("");
  const [items, setItems] = useState<Item[]>([
    { desc: "", precio: 0 },
    { desc: "", precio: 0 },
    { desc: "", precio: 0 },
    { desc: "", precio: 0 },
  ]);
  const [generando, setGenerando] = useState(false);

  // Total calculado en tiempo real, siempre sincronizado
  const calcularTotal = () => items.reduce((sum, item) => sum + (item.precio || 0), 0);

  const actualizarItem = (idx: number, campo: keyof Item, valor: string | number) => {
    const nuevos = [...items];
    nuevos[idx] = { ...nuevos[idx], [campo]: valor };
    setItems(nuevos);
  };

  const handleGenerarPDF = async () => {
    if (!direccion.trim()) {
      alert("Ingresá la dirección.");
      return;
    }
    // Solo exigimos descripción no vacía. Precio 0 permitido.
    if (items.some((item) => !item.desc.trim())) {
      alert("Todos los ítems deben tener descripción.");
      return;
    }
    setGenerando(true);
    try {
      const res = await apiFetch("/api/v1/presupuesto/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          direccion,
          items: items.filter((i) => i.desc.trim() !== ""),
          total_neto: calcularTotal(),
        }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `presupuesto-${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        router.push("/login?next=/presupuesto");
        return;
      }
      alert(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setGenerando(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-gray-50 flex justify-center">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Generar Presupuesto PDF</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Dirección</label>
            <Input
              value={direccion}
              onChange={(e) => setDireccion(e.target.value)}
              placeholder="Santo Domingo 1890, Depto 405B"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Ítems</label>
            {items.map((item, idx) => (
              <div key={idx} className="flex gap-2">
                <Input
                  placeholder={`Descripción ítem ${idx + 1}`}
                  value={item.desc}
                  onChange={(e) => actualizarItem(idx, "desc", e.target.value)}
                />
                <Input
                  type="number"
                  min={0}
                  placeholder="Precio"
                  value={item.precio || ""}
                  onChange={(e) => actualizarItem(idx, "precio", Number(e.target.value))}
                  className="w-32"
                />
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center pt-2 border-t">
            <span className="font-semibold">Total Neto</span>
            <span className="text-lg font-bold">
              ${calcularTotal().toLocaleString("es-CL")}
            </span>
          </div>

          <Button
            type="button"
            onClick={handleGenerarPDF}
            disabled={generando}
            className="w-full"
          >
            {generando ? "Generando..." : "Generar PDF"}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
