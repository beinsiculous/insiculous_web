/**
 * The WebGPU gate every embed runs before it downloads a wasm bundle.
 *
 * An adapter alone is not proof: the engine asks for a device at the default
 * limits, and an adapter that exposes the API without them fails there with a
 * generic 'Failed to start'. So the probe asks for the same device — default
 * limits, no features — and releases it before the wasm asks for its own.
 */

export type WebGpuFailureReason = 'no-api' | 'no-adapter' | 'no-device';

export type WebGpuProbeResult = { ok: true } | { ok: false; reason: WebGpuFailureReason };

export async function probeWebGpu(): Promise<WebGpuProbeResult> {
  const gpu = 'gpu' in navigator ? (navigator as any).gpu : null;
  if (!gpu) return { ok: false, reason: 'no-api' };

  const adapter = await gpu.requestAdapter().catch(() => null);
  if (!adapter) return { ok: false, reason: 'no-adapter' };

  const device = await adapter.requestDevice().catch(() => null);
  device?.destroy();
  if (!device) return { ok: false, reason: 'no-device' };

  return { ok: true };
}

export function describeWebGpuFailure(reason: WebGpuFailureReason): string {
  switch (reason) {
    case 'no-api':
      return 'This browser has no WebGPU at all.';
    case 'no-adapter':
      return 'This browser knows WebGPU but found no graphics adapter it can use.';
    case 'no-device':
      return 'This browser found an adapter, but it would not hand out a graphics device at the limits the engine needs.';
  }
}
