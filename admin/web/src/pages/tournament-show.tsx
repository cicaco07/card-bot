import { useCustom } from "@refinedev/core";
import { Card, Col, Descriptions, Empty, Row, Skeleton, Table, Tag, Typography } from "antd";
import { useParams } from "react-router-dom";

type TableDetail = {
  table: {
    id: string;
    table_code: string;
    table_name?: string | null;
    guild_id: number;
    channel_id: number;
    owner_user_id: number;
    owner_display_name?: string | null;
    game_type: string;
    status: string;
    total_rounds_display: string;
    completed_rounds: number;
    created_at: string;
    updated_at: string;
  };
  settings: Record<string, unknown>;
  players: Array<{
    user_id: number;
    display_name: string;
    seat_order: number;
    cumulative_score: number;
  }>;
  rounds: Array<{
    round_number: number;
    summary: string;
    winner_ids: number[];
    loser_id?: number | null;
    ranking: number[];
    round_points: Record<number, number>;
    result_json: Record<string, unknown>;
  }>;
};

export function TournamentShowPage() {
  const { id = "" } = useParams();
  const { data, isLoading } = useCustom<TableDetail>({
    url: `tournament-tables/${id}`,
    method: "get",
  });

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 12 }} />;
  }

  const detail = data?.data;
  if (!detail) {
    return <Empty description="Table tidak ditemukan." />;
  }

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={10}>
        <Card className="admin-panel" bordered={false} title="Table Detail">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Code">{detail.table.table_code}</Descriptions.Item>
            <Descriptions.Item label="Name">{detail.table.table_name || "-"}</Descriptions.Item>
            <Descriptions.Item label="Mode"><Tag>{detail.table.game_type.toUpperCase()}</Tag></Descriptions.Item>
            <Descriptions.Item label="Status"><Tag>{detail.table.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="Rounds">{detail.table.total_rounds_display}</Descriptions.Item>
            <Descriptions.Item label="Completed">{detail.table.completed_rounds}</Descriptions.Item>
            <Descriptions.Item label="Guild">{detail.table.guild_id}</Descriptions.Item>
            <Descriptions.Item label="Channel">{detail.table.channel_id}</Descriptions.Item>
            <Descriptions.Item label="Owner">
              <div className="dashboard-player-cell">
                <span className="dashboard-player-name">{detail.table.owner_display_name || "Unknown Player"}</span>
                <span className="dashboard-user-id">{detail.table.owner_user_id}</span>
              </div>
            </Descriptions.Item>
            <Descriptions.Item label="Updated">{new Date(detail.table.updated_at).toLocaleString()}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card className="admin-panel" bordered={false} title="Settings" style={{ marginTop: 16 }}>
          <pre className="json-block">{JSON.stringify(detail.settings, null, 2)}</pre>
        </Card>
      </Col>
      <Col xs={24} xl={14}>
        <Card className="admin-panel" bordered={false} title="Players">
          <Table
            rowKey="user_id"
            pagination={false}
            dataSource={detail.players}
            columns={[
              { title: "Seat", dataIndex: "seat_order" },
              {
                title: "Player",
                key: "player",
                render: (_: unknown, record: TableDetail["players"][number]) => (
                  <div className="dashboard-player-cell">
                    <span className="dashboard-player-name">{record.display_name || "Unknown Player"}</span>
                    <span className="dashboard-user-id">{record.user_id}</span>
                  </div>
                ),
              },
              { title: "Score", dataIndex: "cumulative_score" },
            ]}
          />
        </Card>
        <Card className="admin-panel" bordered={false} title="Rounds" style={{ marginTop: 16 }}>
          {detail.rounds.length === 0 ? (
            <Empty description="Belum ada ronde tersimpan." />
          ) : (
            detail.rounds.map((round) => (
              <Card key={round.round_number} type="inner" title={`Ronde ${round.round_number}`} style={{ marginBottom: 12 }}>
                <Typography.Paragraph>{round.summary}</Typography.Paragraph>
                <pre className="json-block">{JSON.stringify(round.result_json, null, 2)}</pre>
              </Card>
            ))
          )}
        </Card>
      </Col>
    </Row>
  );
}
