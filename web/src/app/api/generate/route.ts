import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { mode, category, customScript, vibe } = await request.json();

    const GITHUB_TOKEN = process.env.GITHUB_SERVICE_TOKEN;
    const REPO_OWNER = process.env.GITHUB_REPO_OWNER;
    const REPO_NAME = process.env.GITHUB_REPO_NAME;

    if (!GITHUB_TOKEN || !REPO_OWNER || !REPO_NAME) {
      return NextResponse.json({ error: 'GitHub configuration missing' }, { status: 500 });
    }

    const response = await fetch(
      `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/daily_generate.yml/dispatches`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            mode: mode || 'AUTO',
            category: category || 'random',
            custom_script: customScript || '',
            vibe: vibe || 'suspense',
          },
        }),
      }
    );

    if (response.ok) {
      return NextResponse.json({ message: 'Workflow triggered successfully' });
    } else {
      const error = await response.text();
      return NextResponse.json({ error }, { status: response.status });
    }
  } catch (err) {
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
