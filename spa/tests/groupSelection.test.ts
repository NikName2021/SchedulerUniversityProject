import assert from "node:assert/strict";
import test from "node:test";

import {
  getStandaloneGroups,
  isStandaloneGroupName,
} from "../src/utils/groupSelection.js";

test("standalone group names do not contain subgroup or combined markers", () => {
  assert.equal(isStandaloneGroupName("К0409-25/1"), true);
  assert.equal(isStandaloneGroupName("К0409-25/1 (L1)"), false);
  assert.equal(isStandaloneGroupName("К0409-25/1, К0409-25/2"), false);
  assert.equal(isStandaloneGroupName("К0409-25/1 + К0409-25/2"), false);
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
