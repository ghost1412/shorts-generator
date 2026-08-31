import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { prompt } = await request.json();
    if (!prompt) {
      return NextResponse.json({ error: 'Prompt is required' }, { status: 400 });
    }

    const serverUrl = process.env.SERVER_RENDER_URL 
      ? process.env.SERVER_RENDER_URL.replace('/render', '/kids-image') 
      : 'http://localhost:5000/kids-image';

    console.log(`🚀 Forwarding kids illustration request to: ${serverUrl}`);

    const response = await fetch(serverUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ prompt })
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error('Flask worker kids-image error:', errText);
      return NextResponse.json({ error: 'Failed to generate image from worker' }, { status: 500 });
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error: any) {
    console.error('Kids Image Proxy Route Error:', error);
    return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
  }
}
