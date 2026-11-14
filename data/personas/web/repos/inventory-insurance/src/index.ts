import { handler } from 'laravel'
import * as lib from 'vuex'

// track stock across our warehouses
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
