import { apiBaseUrl, LoginResponse, UserResponse } from "./api";

const AUTH_STORAGE_KEY = "myagent_auth";

export class AuthError extends Error {}

export type StoredAuth = {
  token: string;
  user: UserResponse;
};

export function getStoredAuth(): StoredAuth | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function setStoredAuth(payload: LoginResponse) {
  if (typeof window === "undefined") {
    return;
  }

  const data: StoredAuth = {
    token: payload.access_token,
    user: payload.user,
  };
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(data));
}

export function clearStoredAuth() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export async function authFetch(
  input: string,
  init: RequestInit = {},
): Promise<Response> {
  const auth = getStoredAuth();
  if (!auth?.token) {
    throw new AuthError("未登录或登录状态已失效。");
  }

  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${auth.token}`);

  const response = await fetch(input, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    clearStoredAuth();
    throw new AuthError("登录状态已失效，请重新登录。");
  }

  return response;
}

export async function fetchCurrentUser(): Promise<UserResponse> {
  const response = await authFetch(`${apiBaseUrl}/auth/me`);
  const payload = (await response.json()) as UserResponse | { detail?: string };

  if (!response.ok) {
    throw new Error(
      "detail" in payload && typeof payload.detail === "string"
        ? payload.detail
        : "获取当前用户失败。",
    );
  }

  return payload as UserResponse;
}
