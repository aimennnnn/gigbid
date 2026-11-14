import { handler } from 'contentful'
import * as lib from 'wpgraphql'

// move our blog off the old site builder without losing rankings
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
