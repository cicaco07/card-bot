import { useCustom, useCustomMutation } from "@refinedev/core";
import { App, Button, Card, Input, Select, Space, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";

type TournamentTable = {
  id: string;
  table_code: string;
  table_name?: string | null;
  guild_id: number;
  channel_id: number;
  owner_user_id: number;
  owner_display_name?: string | null;
  game_type: string;
  status: string;
  total_rounds: number;
  total_rounds_display: string;
  completed_rounds: number;
  updated_at: string;
};

export function TournamentListPage() {
  const { message } = App.useApp();
  const [status, setStatus] = useState<string | undefined>();
  const [gameType, setGameType] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const { data, isLoading, refetch } = useCustom<TournamentTable[]>({
    url: "tournament-tables",
    method: "get",
    config: {
      query: {
        status,
        game_type: gameType,
        search: search || undefined,
      },
    },
  });
  const { mutateAsync } = useCustomMutation();

  const rows = data?.data ?? [];
  const columns = [
    {
      title: "Code",
      dataIndex: "table_code",
      render: (value: string, record: TournamentTable) => <Link to={`/tables/show/${record.id}`}>{value}</Link>,
    },
    { title: "Name", dataIndex: "table_name", render: (value: string | null) => value || "-" },
    { title: "Mode", dataIndex: "game_type", render: (value: string) => <Tag>{value.toUpperCase()}</Tag> },
    { title: "Status", dataIndex: "status", render: (value: string) => <Tag color={value === "between_rounds" ? "green" : value === "finished" ? "gold" : "default"}>{value}</Tag> },
    { title: "Rounds", dataIndex: "total_rounds_display" },
    { title: "Completed", dataIndex: "completed_rounds" },
    {
      title: "Owner",
      key: "owner",
      render: (_: unknown, record: TournamentTable) => (
        <div className="dashboard-player-cell">
          <span className="dashboard-player-name">{record.owner_display_name || "Unknown Player"}</span>
          <span className="dashboard-user-id">{record.owner_user_id}</span>
        </div>
      ),
    },
    { title: "Guild", dataIndex: "guild_id" },
    { title: "Updated", dataIndex: "updated_at", render: (value: string) => new Date(value).toLocaleString() },
    {
      title: "Action",
      key: "action",
      render: (_: unknown, record: TournamentTable) => (
        <Button
          danger
          disabled={record.status === "archived"}
          onClick={async () => {
            await mutateAsync({
              url: `tournament-tables/${record.id}/archive`,
              method: "post",
              values: {},
            });
            message.success(`Table ${record.table_code} di-archive.`);
            refetch();
          }}
        >
          Archive
        </Button>
      ),
    },
  ];

  return (
    <Card className="admin-panel" bordered={false}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <div>
          <Typography.Title level={3} style={{ marginBottom: 0 }}>
            Tournament tables
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            Filter table aktif, finished, archived, dan cari kode atau nama meja.
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Select
            allowClear
            placeholder="Status"
            style={{ width: 180 }}
            onChange={(value) => setStatus(value)}
            options={[
              { label: "Between Rounds", value: "between_rounds" },
              { label: "Finished", value: "finished" },
              { label: "Archived", value: "archived" },
            ]}
          />
          <Select
            allowClear
            placeholder="Mode"
            style={{ width: 160 }}
            onChange={(value) => setGameType(value)}
            options={[
              { label: "Poker", value: "poker" },
              { label: "Rummy", value: "rummy" },
            ]}
          />
          <Input.Search
            placeholder="Cari code atau name"
            allowClear
            style={{ width: 280 }}
            onSearch={(value) => setSearch(value)}
          />
        </Space>
        <Table<TournamentTable> rowKey="id" loading={isLoading} dataSource={rows} columns={columns} scroll={{ x: 960 }} />
      </Space>
    </Card>
  );
}
