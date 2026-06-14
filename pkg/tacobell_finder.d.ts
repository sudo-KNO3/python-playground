/* tslint:disable */
/* eslint-disable */

/**
 * How many Taco Bells are baked in (lets the JS side display the count
 * for fun: "powered by Rust over N locations").
 */
export function dataset_size(): number;

/**
 * Returns the three Taco Bells closest to (lat, lon), sorted ascending by
 * great-circle distance. JS receives an Array of `Hit` objects.
 *
 * Runs in O(n log n) over the baked array (~1900 entries), single-pass
 * haversine + partial sort. Bench: ~1ms on a low-end phone.
 */
export function find_nearest_three(lat: number, lon: number): any;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly dataset_size: () => number;
    readonly find_nearest_three: (a: number, b: number) => number;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
