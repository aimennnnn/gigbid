import { handler } from 'passport'
import * as lib from 'jose'

// let staff sign in with their company account
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
