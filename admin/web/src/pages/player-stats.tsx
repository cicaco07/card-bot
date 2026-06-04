import { useCustom } from "@refinedev/core";
import { Card, Select, Space, Table, Typography } from "antd";
import { useState } from "react";

type PlayerStat = {
  user_id: number;
  display_name?: string | null;
  game_type: string;
  tournaments_played: number;
  tournaments_won: number;
  total_score: number;
  updated_at: string;
};

export function PlayerStatsPage() {
  const [gameType, setGameType] = useState<string | undefined>();
  const { data, isLoading } = useCustom<PlayerStat[]>({
    url: "player-stats",
    method: "get",
    config: {
      query: {
        game_type: gameType,
      },
    },
  });

  return (
    <Card className="admin-panel" bordered={false}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 0 }}>
            Player stats
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Rekap akumulasi tournament per user dari schema `cardbot`.
          </Typography.Paragraph>
        </div>
        <Select
          allowClear
          placeholder="Filter mode"
          style={{ width: 180 }}
          onChange={(value) => setGameType(value)}
          options={[
            { label: "Poker", value: "poker" },
            { label: "Rummy", value: "rummy" },
          ]}
        />
        <Table
          rowKey={(record) => `${record.game_type}-${record.user_id}`}
          loading={isLoading}
          dataSource={data?.data ?? []}
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
            { title: "Total Score", dataIndex: "total_score" },
            { title: "Updated", dataIndex: "updated_at", render: (value: string) => new Date(value).toLocaleString() },
          ]}
        />
      </Space>
    </Card>
  );
}
