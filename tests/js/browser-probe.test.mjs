/* node --test tests/js/
 *
 * The probe's job is to be right or to say it does not know. These cases are
 * the ones incumbents get wrong: a chip inferred from core count, and memory
 * invented when the browser declined to report it.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// The module touches `document` at call time only, so a stub is enough.
globalThis.document = {
  createElement: () => ({
    getContext: () => globalThis.__renderer === null ? null : ({
      getExtension: (n) => n === "WEBGL_debug_renderer_info"
        ? { UNMASKED_RENDERER_WEBGL: 37446 } : null,
      getParameter: () => globalThis.__renderer,
    }),
  }),
};

const { probeBrowser, APPLE_CHIPS } = await import("../../web/browser-probe.js");

const M1_MAX = "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Max, Unspecified Version)";
const RTX_4090 = "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)";

test("reads the chip from the renderer string, not the core count", () => {
  globalThis.__renderer = M1_MAX;
  // Ten cores also fits an M1 Pro. The renderer says which; llmconfigurator.com
  // guesses from cores alone and reports this machine as a ~12 GB M1 Pro.
  const p = probeBrowser({ hardwareConcurrency: 10, deviceMemory: 32 });
  assert.equal(p.chip.value, "Apple M1 Max");
  assert.equal(p.chip.confidence, "high");
  assert.equal(p.backend, "metal");
});

test("never invents memory when the browser does not report it", () => {
  globalThis.__renderer = M1_MAX;
  const p = probeBrowser({ hardwareConcurrency: 10 });   // Safari, Firefox
  assert.equal(p.memoryBytes.value, null);
  assert.equal(p.memoryBytes.confidence, "none");
  assert.deepEqual(p.memoryBytes.candidates, APPLE_CHIPS["m1 max"].memory);
});

test("treats a reported 8 GB on a many-core machine as possibly the API ceiling", () => {
  globalThis.__renderer = M1_MAX;
  const p = probeBrowser({ hardwareConcurrency: 10, deviceMemory: 8 });
  assert.equal(p.memoryBytes.confidence, "low");
  assert.match(p.memoryBytes.note, /ceiling/);
});

test("the working set is always low confidence, never presented as measured", () => {
  globalThis.__renderer = M1_MAX;
  const p = probeBrowser({ hardwareConcurrency: 10, deviceMemory: 32 });
  assert.equal(p.workingSetBytes.confidence, "low");
  assert.equal(p.workingSetBytes.source, "estimated");
  // Fitted on one machine. Matching Metal there is not evidence it generalises.
  assert.ok(p.workingSetBytes.value < p.memoryBytes.value);
});

test("recognises NVIDIA and routes the backend", () => {
  globalThis.__renderer = RTX_4090;
  const p = probeBrowser({ hardwareConcurrency: 24, deviceMemory: 32 });
  assert.equal(p.backend, "cuda");
  assert.match(p.chip.value, /RTX 4090/);
});

test("says nothing rather than something when there is no GL context", () => {
  globalThis.__renderer = null;
  const p = probeBrowser({ hardwareConcurrency: 10 });
  assert.equal(p.chip.value, null);
  assert.equal(p.chip.confidence, "none");
  assert.equal(p.backend, null);
});

test("always lists what a browser cannot know", () => {
  globalThis.__renderer = M1_MAX;
  const p = probeBrowser({ hardwareConcurrency: 10, deviceMemory: 32 });
  assert.ok(p.limits.length >= 4);
  assert.ok(p.limits.some((l) => /free disk/i.test(l)));
});
