import { apiRequest } from "./api";

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

export async function getCurrentProfile(accessToken: string): Promise<Profile> {
  const response = await apiRequest<ProfileResponse>("/profiles/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`
    },
    ttlSeconds: 10
  });

  return response.profile;
}

export async function updateCurrentProfile(
  accessToken: string,
  payload: UpdateProfilePayload
): Promise<Profile> {
  const response = await apiRequest<ProfileResponse>("/profiles/me", {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${accessToken}`
    },
    json: payload
  });

  return response.profile;
}
