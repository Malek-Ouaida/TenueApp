import { apiRequest } from "../lib/api";
import type { Profile, ProfileResponse, UpdateProfilePayload } from "./types";

export async function getMyProfile(accessToken: string): Promise<Profile> {
  const response = await apiRequest<ProfileResponse>("/profiles/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });

  return response.profile;
}

export async function updateMyProfile(
  accessToken: string,
  payload: UpdateProfilePayload
): Promise<Profile> {
  const response = await apiRequest<ProfileResponse>("/profiles/me", {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${accessToken}`
    },
    body: payload
  });

  return response.profile;
}
