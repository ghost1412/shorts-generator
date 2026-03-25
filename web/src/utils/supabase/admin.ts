import { createClient } from '@supabase/supabase-js';

// Singleton instance of the Supabase Admin client
// This prevents "Too Many Connections" (429) errors by reusing the same client across serverless invocations
let supabaseAdminInstance: any = null;

export const getSupabaseAdmin = () => {
  if (supabaseAdminInstance) return supabaseAdminInstance;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !supabaseServiceRoleKey) {
    throw new Error('Supabase URL or Service Role Key is missing in environment variables');
  }

  supabaseAdminInstance = createClient(supabaseUrl, supabaseServiceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });

  return supabaseAdminInstance;
};
