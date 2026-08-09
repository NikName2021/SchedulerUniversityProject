import assert from "node:assert/strict";
import test from "node:test";

import {
  getDownloadFilename,
  openDownload,
} from "../src/utils/openDownload.js";

test("downloads open without exposing window.opener", () => {
  const calls: unknown[][] = [];
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      open: (...args: unknown[]) => {
        calls.push(args);
        return null;
      },
    },
  });

  openDownload("/api/export");

  assert.deepEqual(calls, [["/api/export", "_blank", "noopener,noreferrer"]]);
  Reflect.deleteProperty(globalThis, "window");
});

test("download filenames cannot escape into a path", () => {
  assert.equal(
    getDownloadFilename(
      'attachment; filename="../../result.scheduler-result"',
      "x",
    ),
    ".._.._result.scheduler-result",
  );
});
