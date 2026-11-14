// The shared logger: one JSON object per line, tagged with module and environment
// (contract section 5). Same fields as the Python logger.
import { currentEnv } from "./env";

export type Level = "debug" | "info" | "warning" | "error" | "critical";
export type Context = Record<string, unknown>;

export interface Logger {
  debug(msg: string, ctx?: Context): void;
  info(msg: string, ctx?: Context): void;
  warning(msg: string, ctx?: Context): void;
  error(msg: string, ctx?: Context, err?: unknown): void;
  critical(msg: string, ctx?: Context, err?: unknown): void;
}

const RESERVED = new Set(["ts", "level", "module", "env", "msg", "error"]);

export function formatLine(
  module: string,
  level: Level,
  msg: string,
  ctx: Context = {},
  err?: unknown,
  now: Date = new Date(),
  env: string = currentEnv(),
): string {
  const line: Record<string, unknown> = { ts: now.toISOString(), level, module, env, msg };
  if (err !== undefined) {
    line.error = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
  }
  for (const [k, v] of Object.entries(ctx)) {
    if (!RESERVED.has(k)) line[k] = v;
  }
  return JSON.stringify(line);
}

export function getLogger(module: string, write: (s: string) => void = console.log): Logger {
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(module)) {
    throw new Error("module must be the module slug, such as 'ingestion'");
  }
  const at =
    (level: Level) =>
    (msg: string, ctx?: Context, err?: unknown): void =>
      write(formatLine(module, level, msg, ctx, err));
  return {
    debug: at("debug"),
    info: at("info"),
    warning: at("warning"),
    error: at("error"),
    critical: at("critical"),
  };
}
