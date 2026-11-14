import { handler } from 'django-tenants'
import * as lib from 'celery'

// one system that keeps each customer's data separate
export async function run(input: Record<string, unknown>) {
  const prepared = lib.prepare(input)
  return handler(prepared)
}
