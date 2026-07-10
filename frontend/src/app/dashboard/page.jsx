"use client";
import { useQuery, gql } from "@apollo/client";
import { Grid, Card, CardContent, Typography, CircularProgress } from "@mui/material";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const GET_METRICS = gql`
  {
    presupuestos { total activos }
    inventarioCritico { total }
    proveedores { total }
  }
`;

export default function DashboardPage() {
  const { loading, data } = useQuery(GET_METRICS);
  if (loading) return <CircularProgress />;
  return (
    <Grid container spacing={3}>
      <Grid item xs={4}><Card sx={{ background: "#161b22", color: "#3fb950" }}><CardContent><Typography variant="h3">{data?.presupuestos?.total || 0}</Typography>Presupuestos</CardContent></Card></Grid>
      <Grid item xs={4}><Card sx={{ background: "#161b22", color: "#f85149" }}><CardContent><Typography variant="h3">{data?.inventarioCritico?.total || 0}</Typography>Alertas Stock</CardContent></Card></Grid>
      <Grid item xs={4}><Card sx={{ background: "#161b22", color: "#58a6ff" }}><CardContent><Typography variant="h3">{data?.proveedores?.total || 0}</Typography>Proveedores</CardContent></Card></Grid>
      <Grid item xs={12}>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={[{name:"Ene",p:12},{name:"Feb",p:19},{name:"Mar",p:15}]}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar dataKey="p" fill="#58a6ff" />
          </BarChart>
        </ResponsiveContainer>
      </Grid>
    </Grid>
  );
}
