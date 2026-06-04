import { useCustom } from "@refinedev/core";
import { Card, Col, Empty, Row, Skeleton, Statistic, Table, Typography } from "antd";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type PlayerStat = {
  user_id: number;
  display_name?: string | null;
  game_type: string;
  tournaments_played: number;
  tournaments_won: number;
  total_score: number;
  updated_at: string;
};

type DashboardSummary = {
  active_tables: number;
  archived_tables: number;
  finished_tables: number;
  total_rounds_saved: number;
  top_player_stats: PlayerStat[];
};

export function DashboardPage() {
  const { data, isLoading } = useCustom<DashboardSummary>({
    url: "dashboard/summary",
    method: "get",
  });

  const summary = data?.data;
  const chartData = summary?.top_player_stats.map((item) => ({
    label: item.display_name || `User ${item.user_id}`,
    total_score: item.total_score,
  })) ?? [];

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  if (!summary) {
    return <Empty description="Dashboard belum punya data." />;
  }

  return (
    <div className="dashboard-page">
      <Row gutter={[16, 16]} className="dashboard-stats-row">
        <Col xs={24} md={12} xl={6}>
          <Card className="admin-panel stat-card" bordered={false}>
            <Statistic title="Table Aktif" value={summary.active_tables} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="admin-panel stat-card" bordered={false}>
            <Statistic title="Table Finished" value={summary.finished_tables} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="admin-panel stat-card" bordered={false}>
            <Statistic title="Table Archived" value={summary.archived_tables} />
          </Card>
        </Col>
        <Col xs={24} md={12} xl={6}>
          <Card className="admin-panel stat-card" bordered={false}>
            <Statistic title="Rounds Tersimpan" value={summary.total_rounds_saved} />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={15}>
          <Card className="admin-panel dashboard-chart-card" bordered={false} title="Top Player Scores">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={chartData}>
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="total_score" fill="#17594a" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card className="admin-panel dashboard-table-card" bordered={false} title="Player Stats Snapshot">
            <Table
              rowKey={(record) => `${record.game_type}-${record.user_id}`}
              pagination={false}
              size="small"
              dataSource={summary.top_player_stats}
              scroll={{ x: 540 }}
              columns={[
                {
                  title: "Player",
                  key: "player",
                  render: (_: unknown, record: PlayerStat) => (
                    <div className="dashboard-player-cell">
                      <span className="dashboard-player-name">{record.display_name || "Unknown Player"}</span>
                      <span className="dashboard-user-id">{record.user_id}</span>
                    </div>
                  ),
                },
                { title: "Mode", dataIndex: "game_type" },
                { title: "Played", dataIndex: "tournaments_played" },
                { title: "Won", dataIndex: "tournaments_won" },
                { title: "Score", dataIndex: "total_score" },
              ]}
            />
            <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
              Snapshot ini diambil langsung dari `cardbot.tournament_player_stats`.
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
