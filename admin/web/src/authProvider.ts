import type { AuthBindings } from "@refinedev/core";
import { adminApiUrl, requestJson } from "./rest";

type AdminUser = {
  id: number;
  username: string;
  global_name?: string | null;
  avatar_url?: string | null;
};

export const authProvider: AuthBindings = {
  login: async () => {
    window.location.href = adminApiUrl("auth/discord/login");
    return {
      success: true,
    };
  },
  logout: async () => {
    await requestJson("auth/logout", { method: "POST", body: JSON.stringify({}) });
    return {
      success: true,
      redirectTo: "/login",
    };
  },
  check: async () => {
    try {
      await requestJson<AdminUser>("auth/me");
      return {
        authenticated: true,
      };
    } catch {
      return {
        authenticated: false,
        redirectTo: "/login",
      };
    }
  },
  getPermissions: async () => null,
  getIdentity: async () => {
    try {
      const user = await requestJson<AdminUser>("auth/me");
      return {
        id: user.id,
        name: user.global_name || user.username,
        avatar: user.avatar_url || undefined,
      };
    } catch {
      return null;
    }
  },
  onError: async () => {
    return { error: undefined };
  },
};
