import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';

dotenv.config({ path: 'web/.env.local' });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('Missing Supabase credentials');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function seedData() {
  const { data: { user } } = await supabase.auth.admin.listUsers(); // This won't work with anon key
  // We need a user ID. Let's assume the user is already logged in and we can get their ID or just prompt.
  console.log('Please run this script with a valid user ID as an argument.');
  const userId = process.argv[2];
  if (!userId) {
    console.log('Usage: node seed.js <user_id>');
    return;
  }

  const logs = [
    {
      user_id: userId,
      title: '10 Mind-Blowing Space Facts',
      mode: 'FACTS',
      status: 'Published',
      views: 1250,
      download_url: 'https://example.com/video1.mp4'
    },
    {
      user_id: userId,
      title: 'The Mystery of the Ghost Ship',
      mode: 'STORY',
      status: 'Published',
      views: 3400,
      download_url: 'https://example.com/video2.mp4'
    },
    {
      user_id: userId,
      title: 'Can you Find the Hidden Cat?',
      mode: 'FIND_IT',
      status: 'Published',
      views: 890,
      download_url: 'https://example.com/video3.mp4'
    }
  ];

  const { error } = await supabase.from('video_logs').insert(logs);
  if (error) console.error('Error seeding data:', error);
  else console.log('Successfully seeded 3 video logs!');
}

seedData();
