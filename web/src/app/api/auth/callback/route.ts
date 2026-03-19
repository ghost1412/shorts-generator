import { NextResponse } from 'next/server'
import { createClient } from '@/utils/supabase/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  // if "next" is in search params, use it as the redirection URL
  const next = searchParams.get('next') ?? '/dashboard'

  if (code) {
    const supabase = await createClient()
    const { data: { user }, error } = await supabase.auth.exchangeCodeForSession(code)
    
    if (!error && user) {
      // Check if user_configs exists, if not create it (Free plan by default)
      const { data: config } = await supabase
        .from('user_configs')
        .select('*')
        .eq('user_id', user.id)
        .single()

      if (!config) {
        await supabase
          .from('user_configs')
          .insert({
            user_id: user.id,
            plan: 'free',
            max_videos: 3
          })
      }

      // Always redirect to the request origin for robustness
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // return the user to an error page with instructions
  return NextResponse.redirect(`${origin}/auth/auth-code-error`)
}
