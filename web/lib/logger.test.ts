import { describe, expect, it } from "vitest";
import { currentEnv } from "./env";
import { formatLine, getLogger } from "./logger";

describe("currentEnv", () => {
  it("defaults to dev", () => expect(currentEnv(undefined)).toBe("dev"));
  it("accepts contract names", () => expect(currentEnv(" LIVE ")).toBe("live"));
  it("rejects others", () => expect(() => currentEnv("production")).toThrow());
});

describe("logger", () => {
  it("writes the contract fields", () => {
    const line = JSON.parse(
      formatLine("web", "info", "hello", { page: "/" }, undefined, new Date(0), "staging"),
    );
    expect(line).toEqual({
      ts: "1970-01-01T00:00:00.000Z",
      level: "info",
      module: "web",
      env: "staging",
      msg: "hello",
      page: "/",
    });
  });

  it("adds the error and protects reserved keys", () => {
    const line = JSON.parse(
      formatLine("web", "error", "boom", { module: "x" }, new TypeError("bad"), new Date(0), "dev"),
    );
    expect(line.error).toBe("TypeError: bad");
    expect(line.module).toBe("web");
  });

  it("rejects a bad slug", () => expect(() => getLogger("Bad Slug")).toThrow());

  it("writes one line per call", () => {
    const out: string[] = [];
    getLogger("web", (s) => out.push(s)).warning("careful");
    expect(out).toHaveLength(1);
    expect(JSON.parse(out[0]).level).toBe("warning");
  });
});
