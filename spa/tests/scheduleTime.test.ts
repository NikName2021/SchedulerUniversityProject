import assert from "node:assert/strict";
import test from "node:test";

import {
  getSlotsForInterval,
  minutesToTime,
  PAIR_TIMES,
  timeToMinutes,
} from "../src/utils/scheduleTime.js";

test("pair configuration covers all seven lessons", () => {
  assert.deepEqual(
    PAIR_TIMES.map((pair) => pair.num),
    [1, 2, 3, 4, 5, 6, 7],
  );
});

test("time conversion is reversible", () => {
  assert.equal(timeToMinutes("18:15"), 1095);
  assert.equal(minutesToTime(1095), "18:15");
});

test("interval maps only to overlapping lessons", () => {
  assert.deepEqual(getSlotsForInterval("10:00", "12:00"), [1, 2, 3]);
  assert.deepEqual(getSlotsForInterval("19:35", "20:00"), []);
});

test("invalid clock values are rejected", () => {
  assert.throws(() => timeToMinutes("25:00"), RangeError);
  assert.throws(() => minutesToTime(-1), RangeError);
});
