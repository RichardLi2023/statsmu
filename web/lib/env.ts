// Which environment the site runs in (contract section 3).
export const ENVIRONMENTS = ["dev", "staging", "live"] as const;
export type AppEnv = (typeof ENVIRONMENTS)[number];

export function currentEnv(
  value: string | undefined = process.env.NEXT_PUBLIC_APP_ENV ?? process.env.APP_ENV,
): AppEnv {
  const env = (value ?? "dev").trim().toLowerCase();
  if (!(ENVIRONMENTS as readonly string[]).includes(env)) {
    throw new Error(`APP_ENV must be one of ${ENVIRONMENTS.join(", ")}; got "${env}"`);
  }
  return env as AppEnv;
}

export function releaseVersion(): string {
  return process.env.NEXT_PUBLIC_APP_VERSION?.trim() || "unreleased";
}

export function commitSha(): string {
  return (
    process.env.NEXT_PUBLIC_APP_COMMIT ??
    process.env.VERCEL_GIT_COMMIT_SHA ??
    process.env.APP_COMMIT ??
    "unknown"
  ).slice(0, 7);
}
