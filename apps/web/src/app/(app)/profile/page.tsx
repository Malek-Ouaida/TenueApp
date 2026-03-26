import { ProfilePage } from "../../../components/profile/ProfilePage";
import { requireSession } from "../../../lib/auth/session";
import { getCurrentProfile } from "../../../lib/profile";

type ProfileRoutePageProps = {
  searchParams?: Promise<{
    updated?: string;
  }>;
};

export default async function ProfileRoutePage({ searchParams }: ProfileRoutePageProps) {
  const session = await requireSession();
  const profile = await getCurrentProfile(session.session.access_token);
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <ProfilePage
      email={session.user.email}
      profile={profile}
      saved={resolvedSearchParams?.updated === "1"}
    />
  );
}
