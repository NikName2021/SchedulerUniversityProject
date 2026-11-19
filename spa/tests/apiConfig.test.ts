import assert from "node:assert/strict";
import test from "node:test";

import {
  apiFetch,
  apiFetchJson,
  apiFetchNoContent,
  setCsrfToken,
} from "../src/api/apiConfig.js";

test("apiFetch sends credentials and CSRF token for mutating requests", async () => {
  const originalFetch = globalThis.fetch;
  let capturedInit: RequestInit | undefined;
  globalThis.fetch = async (_input, init) => {
    capturedInit = init;
    return new Response(null, { status: 204 });
  };

  try {
    setCsrfToken("csrf-value");
    await apiFetch("/api/v1/example", { method: "POST" });

    assert.equal(capturedInit?.credentials, "include");
    assert.equal(
      new Headers(capturedInit?.headers).get("X-CSRF-Token"),
      "csrf-value",
    );
  } finally {
    setCsrfToken(null);
    globalThis.fetch = originalFetch;
  }
});

test("apiFetch does not add CSRF token to safe requests", async () => {
  const originalFetch = globalThis.fetch;
  let capturedInit: RequestInit | undefined;
  globalThis.fetch = async (_input, init) => {
    capturedInit = init;
    return new Response(null, { status: 200 });
  };

  try {
    setCsrfToken("csrf-value");
    await apiFetch("/api/v1/example");

    assert.equal(new Headers(capturedInit?.headers).has("X-CSRF-Token"), false);
  } finally {
    setCsrfToken(null);
    globalThis.fetch = originalFetch;
  }
});

test("apiFetch discards a response from the previous account", async () => {
  const originalFetch = globalThis.fetch;
  let resolveResponse: (response: Response) => void = () => {};
  globalThis.fetch = () =>
    new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    });
  try {
    setCsrfToken("first-user");
    const pending = apiFetch("/api/v1/scheduler/tasks");
    setCsrfToken("second-user");
    resolveResponse(new Response("[]", { status: 200 }));
    await assert.rejects(pending, { name: "AbortError" });
  } finally {
    setCsrfToken(null);
    globalThis.fetch = originalFetch;
  }
});

test("apiFetchJson handles proxy errors and invalid JSON without exposing the body", async (t) => {
  const endpoint = "/api/v1/scheduler/tasks";
  const fallback = "Не удалось загрузить задачи";
  for (const status of [502, 504]) {
    const fetchMock = t.mock.method(
      globalThis,
      "fetch",
      async () =>
        new Response("<html>Gateway error</html>", {
          status,
          headers: { "Content-Type": "text/html" },
        }),
    );
    await assert.rejects(apiFetchJson(endpoint, fallback), {
      message: `${fallback} (HTTP ${status})`,
    });
    fetchMock.mock.restore();
  }

  for (const [body, mediaType] of [
    ["<html>Proxy</html>", "text/html"],
    ["{", "application/json"],
  ]) {
    const fetchMock = t.mock.method(
      globalThis,
      "fetch",
      async () =>
        new Response(body, { headers: { "Content-Type": mediaType } }),
    );
    await assert.rejects(apiFetchJson(endpoint, fallback), {
      message: `${fallback}. Некорректный ответ сервера`,
    });
    fetchMock.mock.restore();
  }
});

test("apiFetchJson preserves conflict messages and handles a rejected fetch", async (t) => {
  const endpoint = "/api/v1/scheduler/schedule/1";
  const fetchMock = t.mock.method(globalThis, "fetch", async () =>
    Response.json(
      { detail: { conflicts: ["Группа занята", "Аудитория занята"] } },
      { status: 409 },
    ),
  );
  await assert.rejects(apiFetchJson(endpoint, "Не удалось перенести занятие"), {
    message: "Группа занята\nАудитория занята",
  });
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(apiFetchJson(endpoint, "Не удалось перенести занятие"), {
    message: "Не удалось перенести занятие",
  });
});

test("apiFetchNoContent accepts a successful deletion with no body", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response(null, { status: 204 }),
  );
  await apiFetchNoContent(
    "/api/v1/scheduler/tasks/1",
    "Не удалось удалить расчёт",
    { method: "DELETE" },
  );
});
