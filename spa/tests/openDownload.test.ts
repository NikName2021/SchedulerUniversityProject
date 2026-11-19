import assert from "node:assert/strict";
import test from "node:test";

import { getDownloadFilename } from "../src/utils/openDownload.js";

test("download filenames cannot escape into a path", () => {
  assert.equal(
    getDownloadFilename('attachment; filename="../../schedule.xlsx"', "x"),
    ".._.._schedule.xlsx",
  );
});

test("malformed encoded filenames fall back to the provided name", () => {
  assert.equal(
    getDownloadFilename("attachment; filename*=UTF-8''%ZZ", "schedule.xlsx"),
    "schedule.xlsx",
  );
});
