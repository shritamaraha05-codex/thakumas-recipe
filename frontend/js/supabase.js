// supabase.js - Supabase client initialization
import { createClient } from '@supabase/supabase-js'
import { config } from './config.js'

export const supabaseConfigured = Boolean(config.supabaseUrl && config.supabaseKey)

export const supabase = supabaseConfigured
  ? createClient(config.supabaseUrl, config.supabaseKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null

