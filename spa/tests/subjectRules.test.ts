import assert from "node:assert/strict";
import test from "node:test";
import {
  applyRulePreset,
  ruleLessonCount,
  ruleValidationError,
  subjectRuleContextKey,
  type SubjectRuleConfig,
} from "../src/utils/subjectRules.js";

const config: SubjectRuleConfig = {
  lectures: 1,
  seminars: 2,
  laboratories: 0,
  days_per_week: 2,
  weekdays: [0, 3],
  days_hard: true,
  lecture_before_practice: true,
  time_preference: "morning",
};

test("three lessons may be distributed over two days", () => {
  assert.equal(ruleLessonCount(config), 3);
  assert.equal(ruleValidationError(config), null);
});

test("presets preserve day and time preferences and do not mutate saved settings", () => {
  const next = applyRulePreset(config, 1);
  assert.equal(next.seminars, 1);
  assert.equal(next.days_per_week, 2);
  assert.deepEqual(next.weekdays, [0, 3]);
  assert.equal(next.time_preference, "morning");
  assert.equal(config.seminars, 2);
});

test("invalid counts and impossible mandatory day selections block checking", () => {
  assert.ok(ruleValidationError({ ...config, days_per_week: 4 }));
  assert.ok(ruleValidationError({ ...config, seminars: -1 }));
  assert.ok(ruleValidationError({ ...config, seminars: 1.5 }));
  assert.ok(ruleValidationError({ ...config, weekdays: [0] }));
  assert.equal(
    ruleValidationError({ ...config, days_hard: false, weekdays: [0] }),
    null,
  );
  assert.ok(ruleValidationError({ ...config, weekdays: [6] }));
});

test("context identity is stable across selection order and changes with holidays", () => {
  const context = {
    groups: ["B", "A"],
    start_date: "2026-11-16",
    end_date: "2026-11-29",
    week_ids: [2, 1],
    enabled_types: ["Семинар", "Лекция"],
    holidays: [],
  };
  assert.equal(
    subjectRuleContextKey(context),
    subjectRuleContextKey({ ...context, groups: ["A", "B"], week_ids: [1, 2] }),
  );
  assert.notEqual(
    subjectRuleContextKey(context),
    subjectRuleContextKey({ ...context, holidays: ["2026-11-19"] }),
  );
});
