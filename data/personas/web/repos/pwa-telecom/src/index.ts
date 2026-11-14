import { handler } from 'workbox'
import * as lib from 'idb'

// an app that still works when the signal drops
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
