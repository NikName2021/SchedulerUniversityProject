import { downloadResponse, openDownload } from "../utils/openDownload.js";

const runtimeEnv = import.meta.env as ImportMetaEnv | undefined;

export const API_BASE_URL = runtimeEnv?.VITE_API_BASE_URL || "";
export const AUTH_UNAUTHORIZED_EVENT = "scheduler:unauthorized";

let csrfToken: string | null = null;
let sessionVersion = 0;

export const setCsrfToken = (token: string | null): void => {
  if (csrfToken !== token) sessionVersion += 1;
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

  const requestSession = sessionVersion;
  const response = await fetch(input, {
    ...init,
    headers,
    credentials: "include",
  });

  if (requestSession !== sessionVersion) {
    throw new DOMException("Session changed", "AbortError");
  }

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

const hasJsonContentType = (response: Response): boolean => {
  const mediaType = response.headers
    .get("Content-Type")
    ?.split(";", 1)[0]
    ?.trim()
    .toLowerCase();
  return (
    mediaType === "application/json" || mediaType?.endsWith("+json") === true
  );
};

const getResponseErrorDetail = async (response: Response) => {
  if (!hasJsonContentType(response)) return undefined;
  const payload: unknown = await response.json().catch(() => null);
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return;

  const { detail } = payload;
  if (typeof detail === "string") return detail.trim() || undefined;
  if (!detail || typeof detail !== "object") return;

  if ("conflicts" in detail && Array.isArray(detail.conflicts)) {
    const conflicts = detail.conflicts.filter(
      (conflict): conflict is string =>
        typeof conflict === "string" && Boolean(conflict.trim()),
    );
    if (conflicts.length) return conflicts.join("\n");
  }
  if ("message" in detail && typeof detail.message === "string") {
    return detail.message.trim() || undefined;
  }
};

const apiFetchChecked = async (
  input: RequestInfo | URL,
  errorMessage: string,
  init?: RequestInit,
): Promise<Response> => {
  let response: Response;
  try {
    response = await apiFetch(input, init);
  } catch (error) {
    throw new Error(errorMessage, { cause: error });
  }

  if (!response.ok) {
    const detail = await getResponseErrorDetail(response);
    throw new Error(detail || `${errorMessage} (HTTP ${response.status})`);
  }
  return response;
};

export const apiFetchJson = async <T = unknown>(
  input: RequestInfo | URL,
  errorMessage: string,
  init?: RequestInit,
): Promise<T> => {
  const response = await apiFetchChecked(input, errorMessage, init);
  const invalidResponse = `${errorMessage}. Некорректный ответ сервера`;
  if (!hasJsonContentType(response)) throw new Error(invalidResponse);
  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new Error(invalidResponse, { cause: error });
  }
};

export const apiFetchNoContent = async (
  input: RequestInfo | URL,
  errorMessage: string,
  init?: RequestInit,
): Promise<void> => {
  const response = await apiFetchChecked(input, errorMessage, init);
  if (response.status !== 204) {
    throw new Error(`${errorMessage}. Некорректный ответ сервера`);
  }
};

export { downloadResponse, openDownload };
