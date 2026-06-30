// Vercel serverless function: POST /api/run-scan
// Triggers the AlphaHunter Daily Scan GitHub Actions workflow (workflow_dispatch).
//
// Requires a repo-scoped token in the Vercel project env var GITHUB_DISPATCH_TOKEN
// (a fine-grained PAT with "Actions: read and write" on this repo). Without it,
// responds {configured:false, actionsUrl} so the UI links to the Actions page.
//
// Optional env: GITHUB_REPO (default "Amit33-design/Amit33-network-design").

const DEFAULT_REPO = "Amit33-design/Amit33-network-design";
const WORKFLOW = "alphahunter-scan.yml";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const repo = process.env.GITHUB_REPO || DEFAULT_REPO;
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  const actionsUrl = `https://github.com/${repo}/actions/workflows/${WORKFLOW}`;

  if (!token) {
    return res.status(200).json({ configured: false, actionsUrl });
  }

  try {
    const r = await fetch(
      `https://api.github.com/repos/${repo}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main", inputs: { loose: "true" } }),
      }
    );
    if (r.status === 204) {
      return res.status(200).json({ triggered: true });
    }
    const body = await r.text();
    return res.status(502).json({ error: `GitHub returned ${r.status}`, detail: body, actionsUrl });
  } catch (e) {
    return res.status(500).json({ error: String(e), actionsUrl });
  }
}
