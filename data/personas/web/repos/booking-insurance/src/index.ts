import { handler } from 'express'
import * as lib from 'luxon'

// let clients book and reschedule appointments online
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
