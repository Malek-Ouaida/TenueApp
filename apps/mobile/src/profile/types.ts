export type Profile = {
  id: string;
  username: string | null;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ProfileResponse = {
  profile: Profile;
};

export type UpdateProfilePayload = {
  username?: string | null;
  display_name?: string | null;
  bio?: string | null;
  avatar_path?: string | null;
};
