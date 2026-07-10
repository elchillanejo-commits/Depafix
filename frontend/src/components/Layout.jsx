import { Outlet, Link } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Drawer, List, ListItem, ListItemIcon, ListItemText, Box } from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import InventoryIcon from '@mui/icons-material/Inventory'
import PeopleIcon from '@mui/icons-material/People'
import ReceiptIcon from '@mui/icons-material/Receipt'

const drawerWidth = 240
const menu = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Inventario', icon: <InventoryIcon />, path: '/inventario' },
  { text: 'Proveedores', icon: <PeopleIcon />, path: '/proveedores' },
  { text: 'Presupuestos', icon: <ReceiptIcon />, path: '/presupuestos' },
]

export default function Layout() {
  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: 1201, background: '#0d1117' }}>
        <Toolbar><Typography variant="h6">🏗️ DepaFix</Typography></Toolbar>
      </AppBar>
      <Drawer variant="permanent" sx={{ width: drawerWidth, '& .MuiDrawer-paper': { width: drawerWidth, background: '#161b22', color: '#c9d1d9' } }}>
        <Toolbar />
        <List>{menu.map(item => (
          <ListItem button key={item.text} component={Link} to={item.path}>
            <ListItemIcon sx={{ color: '#58a6ff' }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.text} />
          </ListItem>
        ))}</List>
      </Drawer>
      <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}><Outlet /></Box>
    </Box>
  )
}
