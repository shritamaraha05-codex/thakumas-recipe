-- Account-owned hand measurements. The API never accepts an owner id.
create table public.hand_profiles (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null unique references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

create table public.hand_weighings (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.hand_profiles(id) on delete cascade,
  unit text not null check (unit in ('muthi','chimti','cup','spoon','tsp','tbsp','bati','glass','poa','chhatak','ser')),
  ingredient text not null check (length(trim(ingredient)) between 1 and 120),
  amount numeric not null check (amount > 0),
  amount_unit text not null check (amount_unit in ('g','ml')),
  created_at timestamptz not null default now()
);

alter table public.hand_profiles enable row level security;
alter table public.hand_weighings enable row level security;
create policy hand_profiles_owner on public.hand_profiles for all to authenticated using (owner_user_id = auth.uid()) with check (owner_user_id = auth.uid());
create policy hand_weighings_owner on public.hand_weighings for all to authenticated using (exists (select 1 from public.hand_profiles p where p.id = profile_id and p.owner_user_id = auth.uid())) with check (exists (select 1 from public.hand_profiles p where p.id = profile_id and p.owner_user_id = auth.uid()));

create or replace function public.get_hand_calibration(p_owner_user_id uuid)
returns jsonb language plpgsql security invoker set search_path = public as $$
declare v_profile public.hand_profiles; v_result jsonb;
begin
  if p_owner_user_id is distinct from auth.uid() then raise exception 'owner mismatch' using errcode = '42501'; end if;
  insert into public.hand_profiles(owner_user_id) values (p_owner_user_id) on conflict(owner_user_id) do nothing;
  select * into v_profile from public.hand_profiles where owner_user_id = p_owner_user_id;
  select jsonb_build_object('profile_id', v_profile.id, 'weighings', coalesce(jsonb_agg(jsonb_build_object('id',w.id,'unit',w.unit,'ingredient',w.ingredient,'amount',w.amount,'amount_unit',w.amount_unit,'created_at',w.created_at) order by w.created_at desc) filter (where w.id is not null), '[]'::jsonb)) into v_result
  from public.hand_weighings w where w.profile_id = v_profile.id;
  return v_result;
end; $$;

create or replace function public.add_hand_weighing(p_owner_user_id uuid,p_unit text,p_ingredient text,p_amount numeric,p_amount_unit text)
returns jsonb language plpgsql security invoker set search_path = public as $$
declare v_profile public.hand_profiles; v_row public.hand_weighings;
begin
  if p_owner_user_id is distinct from auth.uid() then raise exception 'owner mismatch' using errcode = '42501'; end if;
  insert into public.hand_profiles(owner_user_id) values (p_owner_user_id) on conflict(owner_user_id) do nothing;
  select * into v_profile from public.hand_profiles where owner_user_id = p_owner_user_id;
  insert into public.hand_weighings(profile_id,unit,ingredient,amount,amount_unit) values(v_profile.id,p_unit,trim(p_ingredient),p_amount,p_amount_unit) returning * into v_row;
  return jsonb_build_object('id',v_row.id,'unit',v_row.unit,'ingredient',v_row.ingredient,'amount',v_row.amount,'amount_unit',v_row.amount_unit,'created_at',v_row.created_at);
end; $$;

create or replace function public.delete_hand_weighing(p_owner_user_id uuid,p_weighing_id uuid)
returns boolean language plpgsql security invoker set search_path = public as $$
declare v_deleted integer;
begin
  if p_owner_user_id is distinct from auth.uid() then raise exception 'owner mismatch' using errcode = '42501'; end if;
  delete from public.hand_weighings w using public.hand_profiles p where w.profile_id=p.id and p.owner_user_id=p_owner_user_id and w.id=p_weighing_id;
  get diagnostics v_deleted = row_count; return v_deleted > 0;
end; $$;

grant execute on function public.get_hand_calibration(uuid), public.add_hand_weighing(uuid,text,text,numeric,text), public.delete_hand_weighing(uuid,uuid) to authenticated;
