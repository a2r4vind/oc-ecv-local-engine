// Day 45: shared WebGL context disposal, used by MapView (MapLibre +
// deck.gl overlay canvases) and any Plotly component using a WebGL trace
// (currently only ScatterChart's scattergl). Browsers cap concurrent
// contexts (~16); relying on GC after unmount isn't fast/reliable enough
// under rapid mount/unmount cycles — confirmed via Day 44's stress
// session. Forces release deterministically instead.
export function forceLoseWebGLContext(canvas: HTMLCanvasElement | null | undefined) {
  if (!canvas) return;
  const gl = (canvas.getContext("webgl2") || canvas.getContext("webgl")) as
    | WebGLRenderingContext
    | WebGL2RenderingContext
    | null;
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
}

// Scans a container for every <canvas> and forces context loss on each.
// Used for both MapView's container (MapLibre canvas + deck.gl overlay
// canvas) and a Plotly graphDiv (which may contain a WebGL <canvas>
// alongside SVG layers, depending on trace type).
export function loseAllWebGLContextsIn(container: HTMLElement, exclude?: HTMLCanvasElement | null) {
  container.querySelectorAll("canvas").forEach((canvas) => {
    if (canvas === exclude) return;
    forceLoseWebGLContext(canvas as HTMLCanvasElement);
  });
}