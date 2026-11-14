import { commitSha, currentEnv, releaseVersion } from "@/lib/env";

export const dynamic = "force-dynamic";

// Contract section 3: the smoke test after every deployment calls this.
export function GET() {
  return Response.json(
    { status: "ok", env: currentEnv(), version: releaseVersion(), commit: commitSha() },
    { headers: { "Cache-Control": "no-store" } },
  );
}
