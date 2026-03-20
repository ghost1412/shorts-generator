import { NextResponse } from 'next/server';

// This webhook is kept as a lightweight endpoint for backward compatibility.
// The Python runner now writes directly to Supabase via supabase-py.
// This can be used in the future for real-time UI push notifications (e.g., SSE/WebSockets).

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    console.log(`[Webhook] Received ping: video_id=${payload?.video_id}, status=${payload?.status}`);
    // No DB writes here — Python runner handles it directly.
    return NextResponse.json({ success: true, message: 'Acknowledged' });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
