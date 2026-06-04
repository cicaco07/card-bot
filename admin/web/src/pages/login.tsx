import { LoginOutlined } from "@ant-design/icons";
import { Button, Card, Space, Typography } from "antd";
import { authProvider } from "../authProvider";

export function LoginPage() {
  return (
    <div className="admin-login">
      <Card className="admin-panel admin-login-card" bordered={false}>
        <Space direction="vertical" size="large">
          <Typography.Text className="admin-brand">CardBot Tournament Desk</Typography.Text>
          <Typography.Title level={1} style={{ margin: 0 }}>
            Masuk lewat Discord
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Admin panel ini membaca tournament table, ronde, checkpoint, dan player stats dari schema `cardbot`.
          </Typography.Paragraph>
          <Button
            type="primary"
            size="large"
            icon={<LoginOutlined />}
            onClick={() => authProvider.login?.({})}
          >
            Login dengan Discord
          </Button>
        </Space>
      </Card>
    </div>
  );
}
