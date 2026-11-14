import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs" || process.env.NEXT_RUNTIME === "edge") {
    const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) return; // error tracking off when no DSN (e.g. on a developer's computer)
    Sentry.init({
      dsn,
      environment: process.env.NEXT_PUBLIC_APP_ENV ?? process.env.APP_ENV ?? "dev",
      release: process.env.NEXT_PUBLIC_APP_VERSION || "unreleased",
      tracesSampleRate: 0,
      initialScope: { tags: { module: "web" } },
    });
  }
}

export const onRequestError = Sentry.captureRequestError;
