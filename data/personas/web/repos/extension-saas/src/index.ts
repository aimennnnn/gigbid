import { handler } from 'webextension-polyfill'
import * as lib from 'vite'

// a browser add-on that saves our team clicks
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
