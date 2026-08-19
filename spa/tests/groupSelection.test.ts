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

test("whole groups overlap language subgroups but L1 and L2 can run together", () => {
  const labels = ["К0109-23", "К0109-23 (L1)", "К0109-23 (L2)"];
  const knownSubgroups = collectKnownSubgroups(labels);

  assert.equal(
    groupLabelsOverlap("К0109-23", "К0109-23 (L1)", knownSubgroups),
    true,
  );
  assert.equal(
    groupLabelsOverlap("К0109-23", "К0109-23 (L2)", knownSubgroups),
    true,
  );
  assert.equal(
    groupLabelsOverlap("К0109-23 (L1)", "К0109-23 (L2)", knownSubgroups),
    false,
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
