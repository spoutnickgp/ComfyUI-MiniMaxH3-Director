// Nodes never move each other: a node that grows (on load or by its content) may cover what lies below or right of it,
// as any ComfyUI node may (user 2026-11-10: "just don't put things under the director").

// Cards, the Studio and the Storyboard are as tall as their content, and the user can drag them taller (user 2026-10-19:
// "the preview should grow when I make the node bigger"). When a drag stops, the height it left beyond the content goes to
// the node's growing part (a preview, the waveform, the canvas, the timeline) through `setGrow(px)`, which is kept in
// node.properties.ng_grow. Below the content's own height the node snaps back to it. The node reports its content without
// the grown part as its minimum (computeSize), so ComfyUI lets it be dragged smaller again; `fit` sizes it to minimum + grow.
// Waiting for the drag to end keeps the growth from fighting the pointer.
// Only the user's drag counts: ComfyUI marks it with resizing_node or the pointer's resize direction (frontend 1.55, measured
// 2026-10-19); a node sized by code (placing it, loading an image) is no drag. Without ComfyUI's canvas (tests) all count.
export function draggedByUser(node) {
  const canvas = globalThis.comfyAPI?.app?.app?.canvas;
  return !canvas || canvas.resizing_node === node || Boolean(canvas.pointer?.resizeDirection);
}

export function followDraggedHeight(node, setGrow, fit) {
  let settling = 0, target = 0;
  setGrow(node.properties.ng_grow || 0);
  const resized = node.onResize;
  node.onResize = function (...args) {
    const result = resized?.apply(this, args);
    // the node's own fit is no drag either
    if (!draggedByUser(node)) return result;
    if (Math.abs(node.size[1] - ((node.computeSize?.()[1] ?? node.size[1]) + (node.properties.ng_grow || 0))) < 3) return result;
    target = node.size[1];
    clearTimeout(settling);
    settling = setTimeout(adopt, 200);
    return result;
  };
  // One step: the growing parts grow by exactly what they are given (a preview's height, the waveform's, the timeline's).
  // Repeating it before `fit` had measured the grown content kept adding height (GUI test 2026-10-19: a 1872-high preview).
  function adopt() {
    const grow = Math.max(0, Math.round(target - (node.computeSize?.()[1] ?? target)));
    if (grow !== (node.properties.ng_grow || 0)) { node.properties.ng_grow = grow; setGrow(grow); }
    fit();
  }
}
