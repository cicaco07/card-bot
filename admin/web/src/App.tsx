import {
  BarChartOutlined,
  LoginOutlined,
  OrderedListOutlined,
  TableOutlined,
} from "@ant-design/icons";
import { Authenticated } from "@refinedev/core";
import { Button, Layout, Menu, Typography } from "antd";
import { Link, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { authProvider } from "./authProvider";
import { DashboardPage } from "./pages/dashboard";
import { LoginPage } from "./pages/login";
import { PlayerStatsPage } from "./pages/player-stats";
import { TournamentListPage } from "./pages/tournament-list";
import { TournamentShowPage } from "./pages/tournament-show";

const { Content, Sider } = Layout;

function ShellLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const selectedKey = location.pathname.startsWith("/stats")
    ? "/stats"
    : location.pathname.startsWith("/tables")
      ? "/tables"
      : "/";

  return (
    <Layout className="admin-shell">
      <Sider theme="light" width={240} breakpoint="lg" collapsedWidth="0" style={{ background: "transparent", padding: 16 }}>
        <div className="admin-panel admin-sidebar">
          <Typography.Title level={4} className="admin-brand" style={{ marginTop: 0 }}>
            CardBot Admin
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Tournament data, checkpoint, dan statistik Supabase dalam satu panel.
          </Typography.Paragraph>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            style={{ borderInlineEnd: "none", background: "transparent" }}
            items={[
              { key: "/", icon: <BarChartOutlined />, label: <Link to="/">Dashboard</Link> },
              { key: "/tables", icon: <TableOutlined />, label: <Link to="/tables">Tournament Tables</Link> },
              { key: "/stats", icon: <OrderedListOutlined />, label: <Link to="/stats">Player Stats</Link> },
            ]}
          />
        </div>
      </Sider>
      <Layout className="admin-main">
        <Content className="admin-content">
          <div className="admin-panel admin-hero">
            <div className="admin-hero-bar">
              <div>
                <Typography.Title level={2} className="admin-hero-title">
                  Control room tournament
                </Typography.Title>
                <Typography.Paragraph type="secondary" className="admin-hero-copy">
                  Lihat state table, inspeksi checkpoint ronde, dan archive meja yang perlu dirapikan.
                </Typography.Paragraph>
              </div>
              <Button
                icon={<LoginOutlined />}
                onClick={async () => {
                  await authProvider.logout?.({});
                  navigate("/login");
                }}
              >
                Logout
              </Button>
            </div>
          </div>
          <div className="admin-page-body">
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <Authenticated key="admin-shell" fallback={<LoginPage />}>
            <ShellLayout />
          </Authenticated>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="/tables" element={<TournamentListPage />} />
        <Route path="/tables/show/:id" element={<TournamentShowPage />} />
        <Route path="/stats" element={<PlayerStatsPage />} />
      </Route>
    </Routes>
  );
}
