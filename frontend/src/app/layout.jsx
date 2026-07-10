"use client";
import { ClerkProvider, SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import { ApolloWrapper } from "@/lib/apollo";
import { AppBar, Toolbar, Typography, Drawer, List, ListItem, ListItemIcon, ListItemText, Box, CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import InventoryIcon from "@mui/icons-material/Inventory";
import PeopleIcon from "@mui/icons-material/People";
import Link from "next/link";

const darkTheme = createTheme({ palette: { mode: "dark" } });
const drawerWidth = 240;
const menu = [
  { text: "Dashboard", icon: <DashboardIcon />, path: "/dashboard" },
  { text: "Inventario", icon: <InventoryIcon />, path: "/inventario" },
  { text: "Proveedores", icon: <PeopleIcon />, path: "/proveedores" },
];

export default function RootLayout({ children }) {
  return (
    <ClerkProvider>
      <html lang="es">
        <body>
          <ThemeProvider theme={darkTheme}>
            <CssBaseline />
            <ApolloWrapper>
              <Box sx={{ display: "flex" }}>
                <AppBar position="fixed" sx={{ zIndex: 1201, background: "#0d1117" }}>
                  <Toolbar>
                    <Typography variant="h6" sx={{ flexGrow: 1 }}>🏗️ DepaFix</Typography>
                    <SignedOut><SignInButton /></SignedOut>
                    <SignedIn><UserButton /></SignedIn>
                  </Toolbar>
                </AppBar>
                <Drawer variant="permanent" sx={{ width: drawerWidth, "& .MuiDrawer-paper": { width: drawerWidth, background: "#161b22", color: "#c9d1d9" } }}>
                  <Toolbar />
                  <List>
                    {menu.map(item => (
                      <ListItem key={item.text} component={Link} href={item.path}>
                        <ListItemIcon sx={{ color: "#58a6ff" }}>{item.icon}</ListItemIcon>
                        <ListItemText primary={item.text} />
                      </ListItem>
                    ))}
                  </List>
                </Drawer>
                <Box sx={{ flexGrow: 1, p: 3, mt: 8 }}>{children}</Box>
              </Box>
            </ApolloWrapper>
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
