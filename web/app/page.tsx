import { currentEnv } from "@/lib/env";

// Module 0: a deliberately blank page. Real pages arrive in Modules 7–9.
export default function Home() {
  const env = currentEnv();
  return (
    <main style={{ padding: "2rem 1rem", maxWidth: 640, margin: "0 auto" }}>
      <h1>Mauritius in numbers</h1>
      <p>Coming soon.</p>
      {env !== "live" && <p style={{ color: "#888" }}>Environment: {env}</p>}
    </main>
  );
}
