// The Studio is the H3 Director node's face in the graph; "Full screen" lifts the same Studio over the window and back.
import assert from "node:assert/strict";
import { installStudioDom, fixture } from "../regressions/studio_fixture.mjs";
import { openStudio, closeStudio } from "../../../js/ng/h3s_studio.js";

installStudioDom();
// The overlay fixture only ever removed from <body>; here the Studio also sits in a node.
Object.getPrototypeOf(document.body).remove = function () { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((entry) => entry !== this); this.parentNode = null; };
const f = fixture(), host = document.createElement("div");
const studio = openStudio(f.node, f.app, f.api, host);
assert.equal(studio.root.parentNode, host, "the Studio lives in the node, not over the window");
assert.ok(!studio.root.classList.contains("full"));
assert.equal(studio.root.button("Back to graph"), undefined, "in the graph there is nothing to go back to");
assert.equal(studio.root.byClass("h3s-title").length, 0, "the node's own title names it");
assert.ok(studio.root.byClass("h3s-shot").length, "the timeline is there right away");
assert.equal(openStudio(f.node, f.app, f.api, host), studio, "one Studio per node");

// Delete or Backspace on a Studio button must not reach ComfyUI, which would delete the selected node; Ctrl+S may.
const key = (init) => { const event = { ...init, stopped: false, stopPropagation() { this.stopped = true; } }; studio.root.fire("keydown", event); return event.stopped; };
assert.ok(key({ key: "Delete" }) && key({ key: "Backspace" }), "graph shortcuts stay out of the Studio");
assert.ok(!key({ key: "s", ctrlKey: true }), "Ctrl+S still saves the workflow");

studio.root.button("Full screen").onclick();
assert.equal(studio.root.parentNode, document.body, "Full screen moves the same Studio over the window");
assert.ok(studio.root.classList.contains("full"));
assert.equal(studio.root.byClass("h3s-title")[0].innerText, "H3 Director");
let stopped = false;
studio.root.onkeydown({ key: "Escape", target: studio.root, stopPropagation() { stopped = true; } });
assert.ok(stopped && studio.root.parentNode === host && !studio.root.classList.contains("full"), "Esc puts it back into the node");
stopped = false;
studio.root.onkeydown({ key: "Escape", target: studio.root, stopPropagation() { stopped = true; } });
assert.ok(!stopped && studio.root.parentNode === host, "in the graph Esc is left to ComfyUI");

closeStudio(f.node);
assert.equal(host.children.length, 0, "removing the node removes its Studio");
// A split sends the user's own dialogue along: inline lines and spoken lines, by the speaker's name.
{
  const { ownLines } = await import("../../../js/ng/h3s_ai.js");
  const S = { byId: new Map([["mage", { name: "Mage" }]]), shots: [
    { text: "The mage looks up.\n@Mage says: Welcome back.", spoken: [] },
    { text: "Wide shot.", spoken: [{ speaker_id: "mage", text: "Stay." }, { speaker_id: "", text: "Night falls." }, { speaker_id: "mage", text: " " }] }] };
  assert.equal(ownLines(S), "@Mage says: Welcome back.\n@Mage says: Stay.\nNarrator says: Night falls.");
}
// Dragged taller, a content-high node gives the extra height to its growing part (user 2026-10-19); dragged below its
// content it goes back to it; its own fit to the content is not taken for a drag; the growth is kept with the node.
{
  const { followDraggedHeight } = await import("../../../js/ng/ng_layout.js");
  globalThis.requestAnimationFrame ||= (callback) => setTimeout(callback, 0);
  const BASE = 1000, calls = [];
  let grow = 0, fits = 0;
  // computeSize is the minimum (the content without the grown part); fit sizes the node to minimum + grow
  const node = { properties: { ng_grow: 0 }, size: [800, BASE], computeSize: () => [800, BASE], onResize: () => calls.push("own") };
  followDraggedHeight(node, (px) => { grow = px; }, () => { fits += 1; node.size = [800, BASE + grow]; });
  const settle = () => new Promise((resolve) => setTimeout(resolve, 400));
  node.size = [800, BASE]; node.onResize(node.size); await settle();
  assert.equal(node.properties.ng_grow, 0, "the node's own fit is no drag");
  node.size = [800, 1300]; node.onResize(node.size); node.size = [800, 1400]; node.onResize(node.size);
  assert.equal(grow, 0, "nothing grows while the drag goes on");
  await settle();
  assert.deepEqual([grow, node.properties.ng_grow, node.size[1]], [400, 400, 1400], "the extra 400 go to the growing part");
  node.size = [800, 600]; node.onResize(node.size); await settle(); await settle();
  assert.deepEqual([grow, node.size[1]], [0, BASE], "below the content: back to the content");
  assert.ok(fits >= 1 && calls.length >= 4, "the earlier onResize keeps working");
  // with ComfyUI's canvas present, only its resize drag counts: code that sizes the node (placing it, an image loading) does not
  const canvas = { resizing_node: null, pointer: { resizeDirection: null } };
  globalThis.comfyAPI = { app: { app: { canvas } } };
  node.size = [800, 1600]; node.onResize(node.size); await settle();
  assert.equal(grow, 0, "a size set by code is no drag");
  canvas.pointer.resizeDirection = "SE";
  node.size = [800, 1300]; node.onResize(node.size); await settle();
  assert.equal(grow, 300, "the pointer's resize is one");
  delete globalThis.comfyAPI;
  const saved = { properties: { ng_grow: 250 }, size: [800, 1250], computeSize: () => [800, 1000] };
  let restored = -1;
  followDraggedHeight(saved, (px) => { restored = px; }, () => {});
  assert.equal(restored, 250, "a saved workflow comes back at its grown size");
}
console.log("h3s embedded ok");
