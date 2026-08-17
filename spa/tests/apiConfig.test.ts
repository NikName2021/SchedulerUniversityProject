import assert from "node:assert/strict";
import test from "node:test";

import { apiFetch, setCsrfToken } from "../src/api/apiConfig.js";

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
