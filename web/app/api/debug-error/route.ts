import * as Sentry from "@sentry/nextjs";
import { currentEnv } from "@/lib/env";
import { getLogger } from "@/lib/logger";

export const dynamic = "force-dynamic";

// Raises a test error so we can check it reaches Sentry ("done when" criterion).
// Disabled on live.
export async function GET() {
  if (currentEnv() === "live") {
    return new Response("Not found", { status: 404 });
  }
  const err = new Error(`Sentry test error from ${currentEnv()} at ${new Date().toISOString()}`);
  getLogger("foundations").error("debug-error route called", {}, err);
  Sentry.captureException(err, { tags: { module: "foundations" } });
  await Sentry.flush(2000);
  return Response.json({ sent: true, message: err.message }, { status: 500 });
}
