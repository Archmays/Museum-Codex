import assert from "node:assert/strict";
import test from "node:test";

import { selectAffectedSpecs } from "../scripts/run-e2e.mjs";

test("path changes select the path suite plus the candidate closure", () => {
  assert.deepEqual(
    selectAffectedSpecs('["paths"]'),
    ["e2e/museum-06.spec.ts", "e2e/museum-08.spec.ts"],
  );
});

test("shared shell changes select every phase route suite exactly once", () => {
  assert.deepEqual(
    selectAffectedSpecs('["shell","paths","search"]'),
    [
      "e2e/museum-05a.spec.ts",
      "e2e/museum-05b.spec.ts",
      "e2e/museum-06.spec.ts",
      "e2e/museum-07.spec.ts",
      "e2e/museum-08.spec.ts",
      "e2e/online.spec.ts",
    ],
  );
});

test("online test changes select online checks plus the candidate closure", () => {
  assert.deepEqual(
    selectAffectedSpecs('["online"]'),
    ["e2e/museum-08.spec.ts", "e2e/online.spec.ts"],
  );
});

test("full runs remain unscoped and unknown suites fail closed", () => {
  assert.deepEqual(selectAffectedSpecs(undefined), []);
  assert.throws(
    () => selectAffectedSpecs('["invented-suite"]'),
    /Unknown browser suite/,
  );
});
