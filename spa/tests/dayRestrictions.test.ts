import assert from "node:assert/strict";
import test from "node:test";

import {
  getDayRestrictionKeys,
  toggleDayRestrictions,
} from "../src/utils/dayRestrictions.js";

test("selecting a whole date blocks all seven lessons", () => {
  assert.deepEqual(toggleDayRestrictions([], "2026-11-17", "specific"), [
    "2026-11-17-1",
    "2026-11-17-2",
    "2026-11-17-3",
    "2026-11-17-4",
    "2026-11-17-5",
    "2026-11-17-6",
    "2026-11-17-7",
  ]);
});

test("selecting a partially marked day fills it without inverting existing marks", () => {
  const current = ["2026-11-17-2", "2026-11-18-1"];
  const selected = toggleDayRestrictions(current, "2026-11-17", "specific");
  assert.equal(selected.length, 8);
  assert.equal(new Set(selected).size, 8);
  assert.ok(selected.includes("2026-11-18-1"));
  assert.deepEqual(current, ["2026-11-17-2", "2026-11-18-1"]);
  assert.deepEqual(toggleDayRestrictions(selected, "2026-11-17", "specific"), [
    "2026-11-18-1",
  ]);
});

test("weekly selection uses the weekday and applies to subsequent weeks", () => {
  const selected = toggleDayRestrictions(["3-1"], "2026-11-17", "recurring");
  assert.deepEqual(selected, [
    "3-1",
    "2-1",
    "2-2",
    "2-3",
    "2-4",
    "2-5",
    "2-6",
    "2-7",
  ]);
  assert.deepEqual(toggleDayRestrictions(selected, "2026-11-24", "recurring"), [
    "3-1",
  ]);
});

test("specific and weekly marks stay separate", () => {
  assert.deepEqual(getDayRestrictionKeys("2026-11-21", "recurring"), [
    "6-1",
    "6-2",
    "6-3",
    "6-4",
    "6-5",
    "6-6",
    "6-7",
  ]);
  const marks = ["6-1", "2026-11-21-1"];
  const selected = toggleDayRestrictions(marks, "2026-11-21", "specific");
  assert.ok(selected.includes("6-1"));
  assert.deepEqual(toggleDayRestrictions(selected, "2026-11-21", "specific"), [
    "6-1",
  ]);
});
