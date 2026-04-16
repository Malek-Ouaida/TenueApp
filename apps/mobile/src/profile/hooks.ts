import { useEffect, useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { getMyProfile, updateMyProfile } from "./client";
import type { Profile, UpdateProfilePayload } from "./types";

type UseProfileOptions = {
  accessToken?: string | null;
  onUnauthorized?: () => Promise<void> | void;
};

export function useProfile({ accessToken, onUnauthorized }: UseProfileOptions) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onUnauthorizedRef = useRef(onUnauthorized);

  useEffect(() => {
    onUnauthorizedRef.current = onUnauthorized;
  }, [onUnauthorized]);

  useEffect(() => {
    let active = true;

    async function loadProfile() {
      if (!accessToken) {
        setProfile(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const nextProfile = await getMyProfile(accessToken);
        if (!active) {
          return;
        }

        setProfile(nextProfile);
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 401) {
          await onUnauthorizedRef.current?.();
          return;
        }

        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Profile could not be loaded.");
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadProfile();

    return () => {
      active = false;
    };
  }, [accessToken]);

  async function saveProfile(payload: UpdateProfilePayload) {
    if (!accessToken) {
      return null;
    }

    setIsSaving(true);
    setError(null);

    try {
      const nextProfile = await updateMyProfile(accessToken, payload);
      setProfile(nextProfile);
      return nextProfile;
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 401) {
        await onUnauthorizedRef.current?.();
        return null;
      }

      setError(saveError instanceof Error ? saveError.message : "Profile update failed.");
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  return {
    error,
    isLoading,
    isSaving,
    profile,
    saveProfile,
    setProfile
  };
}
