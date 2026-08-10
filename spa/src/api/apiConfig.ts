import { downloadResponse, openDownload } from "../utils/openDownload.js";

const runtimeEnv = import.meta.env as ImportMetaEnv | undefined;

export const API_BASE_URL = runtimeEnv?.VITE_API_BASE_URL || "";
export const AUTH_UNAUTHORIZED_EVENT = "scheduler:unauthorized";

let csrfToken: string | null = null;

export const setCsrfToken = (token: string | null): void => {
  csrfToken = token;
};

const isUnsafeMethod = (method: string): boolean =>
  !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());

export const apiFetch = async (
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> => {
  const method =
    init.method ?? (input instanceof Request ? input.method : "GET");
  const headers = new Headers(init.headers);

  if (isUnsafeMethod(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(input, {
    ...init,
    headers,
    credentials: "include",
  });

  const requestUrl = String(input);
  if (
    response.status === 401 &&
    !requestUrl.includes("/auth/login") &&
    !requestUrl.includes("/auth/me") &&
    typeof window !== "undefined"
  ) {
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
  }

  return response;
};

export { downloadResponse, openDownload };
