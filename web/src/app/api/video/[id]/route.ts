import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: videoId } = await params;
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }


    // Delete the video log entry. 
    // RLS will ensure the user can only delete their own video.
    const { error } = await supabase
      .from('video_logs')
      .delete()
      .eq('id', videoId)
      .eq('user_id', user.id); // Redundant if RLS is on, but safer

    if (error) {
      console.error('Error deleting video:', error);
      return NextResponse.json({ error: 'Failed to delete video' }, { status: 500 });
    }

    return NextResponse.json({ message: 'Video deleted successfully' });
  } catch (error: any) {
    console.error('Error in delete route:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
