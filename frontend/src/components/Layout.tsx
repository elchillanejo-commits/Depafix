import { Box, Drawer, List, ListItem, ListItemText } from '@mui/material';
export const Layout = ({ children }: any) => (
  <Box sx={{display: 'flex'}}><Drawer variant="permanent" sx={{width:240}}><List>{['Dashboard','Inventario','OC'].map(t => <ListItem key={t}><ListItemText primary={t}/></ListItem>)}</List></Drawer><Box p={3}>{children}</Box></Box>
);
