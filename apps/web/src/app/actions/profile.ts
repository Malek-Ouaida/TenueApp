"use server";

import { redirect } from "next/navigation";

import { clearAuthCookies } from "../../lib/auth/cookies";
import { requireSession } from "../../lib/auth/session";
import { ApiError } from "../../lib/api";
import { updateCurrentProfile } from "../../lib/profile";

export type ProfileFormState = {
  error: string | null;
};

export const initialProfileFormState: ProfileFormState = {
  error: null
};

export async function updateProfileAction(
  _: ProfileFormState,
  formData: FormData
): Promise<ProfileFormState> {
  const session = await requireSession();

  try {
    await updateCurrentProfile(session.session.access_token, {
      username: normalizeOptionalField(formData.get("username")),
      display_name: normalizeOptionalField(formData.get("displayName")),
      bio: normalizeOptionalField(formData.get("bio"))
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      await clearAuthCookies();
      redirect("/signin");
    }

    return {
      error: error instanceof ApiError ? error.message : "Profile update failed."
    };
  }

  redirect("/profile?updated=1");
}

function normalizeOptionalField(value: FormDataEntryValue | null): string | null {
  const normalized = String(value ?? "").trim();
  return normalized ? normalized : null;
}
