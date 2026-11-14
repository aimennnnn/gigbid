import { handler } from 'next'
import * as lib from 'stripe'

// an online shop where people can pay by card
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
