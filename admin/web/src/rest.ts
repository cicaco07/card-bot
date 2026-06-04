const API_BASE_URL = (import.meta.env.VITE_ADMIN_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://localhost:8000/api/v1";

type RequestOptions = RequestInit & {
  query?: Record<string, string | number | undefined>;
};

export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_BASE_URL}/${path.replace(/^\//, "")}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep the default detail when JSON parsing fails.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function adminApiUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\//, "")}`;
}
