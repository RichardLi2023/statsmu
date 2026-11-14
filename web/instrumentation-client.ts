import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_APP_ENV ?? "dev",
    release: process.env.NEXT_PUBLIC_APP_VERSION || "unreleased",
    tracesSampleRate: 0,
    initialScope: { tags: { module: "web" } },
  });
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
