import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider, App as AntApp } from "antd";
import { BrowserRouter } from "react-router-dom";
import { Refine } from "@refinedev/core";
import routerProvider from "@refinedev/react-router-v6";
import { dataProvider } from "./dataProvider";
import { authProvider } from "./authProvider";
import { AppRoutes } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#17594a",
          borderRadius: 18,
          colorBgLayout: "transparent",
          fontFamily: "\"Space Grotesk\", \"Segoe UI\", sans-serif",
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Refine
            dataProvider={dataProvider}
            authProvider={authProvider}
            routerProvider={routerProvider}
            resources={[
              { name: "dashboard", list: "/" },
              { name: "tournament-tables", list: "/tables", show: "/tables/show/:id" },
              { name: "player-stats", list: "/stats" },
            ]}
            options={{
              syncWithLocation: true,
            }}
          >
            <AppRoutes />
          </Refine>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
