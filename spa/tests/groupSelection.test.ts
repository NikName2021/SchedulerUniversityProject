import assert from "node:assert/strict";
import test from "node:test";

import {
  collectKnownSubgroups,
  getBaseGroupNames,
  getStandaloneGroups,
  groupLabelIncludesBase,
  groupLabelsOverlap,
  isStandaloneGroupName,
} from "../src/utils/groupSelection.js";

test("standalone group names do not contain subgroup or combined markers", () => {
  assert.equal(isStandaloneGroupName("К0409-25/1"), true);
  assert.equal(isStandaloneGroupName("К0409-25/1 (L1)"), false);
  assert.equal(isStandaloneGroupName("ИОП-ИТ-25/А"), false);
  assert.equal(isStandaloneGroupName("ИОП-ИТ-25/B"), false);
  assert.equal(isStandaloneGroupName("ИОП-ИТ-25/C"), false);
  assert.equal(isStandaloneGroupName("К0409-25/1, К0409-25/2"), false);
  assert.equal(isStandaloneGroupName("К0409-25/1 + К0409-25/2"), false);
});

test("joint and subgroup labels expose their base groups", () => {
  assert.deepEqual(getBaseGroupNames("К0109-23, К0609-23 (L2)"), [
    "К0109-23",
    "К0609-23",
  ]);
  assert.equal(
    groupLabelIncludesBase("К0109-23, К0609-23 (L2)", "К0609-23"),
    true,
  );
  assert.equal(
    groupLabelIncludesBase("К0109-23, К0609-23 (L2)", "К0209-23"),
    false,
  );
});

test("bulk selection keeps only standalone groups", () => {
  assert.deepEqual(
    getStandaloneGroups([
      "К0409-25/1",
      "К0409-25/1 (L1)",
      "К0409-25/1, К0409-25/2",
      "К0409-25/2",
    ]),
    ["К0409-25/1", "К0409-25/2"],
  );
});

test("three language subgroups can run in parallel and still overlap the whole group", () => {
  const labels = ["К0109-23", "К0109-23 (L1)", "К0109-23 (В)", "К0109-23 (С)"];
  const knownSubgroups = collectKnownSubgroups(labels);

  const [whole, first, second, third] = labels;
  assert.equal(groupLabelsOverlap(whole, first, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(whole, second, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(whole, third, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(first, second, knownSubgroups), false);
  assert.equal(groupLabelsOverlap(first, third, knownSubgroups), false);
  assert.equal(groupLabelsOverlap(second, third, knownSubgroups), false);
  assert.equal(
    groupLabelsOverlap(third, "К0109-23 (L3)", knownSubgroups),
    true,
  );
});

test("joint labels occupy every base group in the stream", () => {
  const labels = ["К0109-23", "К0609-23", "К0109-23, К0609-23 (L1)"];
  const knownSubgroups = collectKnownSubgroups(labels);

  assert.equal(
    groupLabelsOverlap("К0109-23, К0609-23 (L1)", "К0609-23", knownSubgroups),
    true,
  );
});

test("slash-separated three language subgroups can run in parallel", () => {
  const labels = ["ИОП-ИТ-25", "ИОП-ИТ-25/А", "ИОП-ИТ-25/B", "ИОП-ИТ-25/C"];
  const knownSubgroups = collectKnownSubgroups(labels);

  const [whole, first, second, third] = labels;
  assert.equal(groupLabelsOverlap(whole, first, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(whole, second, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(whole, third, knownSubgroups), true);
  assert.equal(groupLabelsOverlap(first, second, knownSubgroups), false);
  assert.equal(groupLabelsOverlap(first, third, knownSubgroups), false);
  assert.equal(groupLabelsOverlap(second, third, knownSubgroups), false);
});
