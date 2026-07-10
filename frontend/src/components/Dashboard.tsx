import { useQuery, gql } from '@apollo/client';
import { Card, Grid, Typography } from '@mui/material';
const GET_DATA = gql`query { presupuestos }`;
export const Dashboard = () => {
  const { data } = useQuery(GET_DATA, { pollInterval: 30000 });
  return <Grid container spacing={2}><Card sx={{p:2}}><Typography variant="h4">{data?.presupuestos?.length || 0}</Typography></Card></Grid>;
};
