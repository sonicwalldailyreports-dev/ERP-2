const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const devUserId = import.meta.env.VITE_DEV_USER_ID;
let accessToken: string | null = null;
let refreshHandler: (() => Promise<string | null>) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setRefreshHandler(handler: (() => Promise<string | null>) | null) {
  refreshHandler = handler;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

export async function apiClient<T>(path: string, options: RequestInit = {}): Promise<T> {
  const request = () => fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(devUserId ? { "X-Dev-User-ID": devUserId } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
  });
  let response = await request();
  if (response.status === 401 && refreshHandler && !path.includes("/auth/")) {
    const token = await refreshHandler();
    if (token) {
      response = await request();
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body?.error?.message ?? "Something went wrong.", response.status, body?.error?.code);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
