import { router, type Href } from "expo-router";
import { useEffect, useMemo } from "react";

import { useAuth } from "../../../src/auth/provider";
import { useReviewQueue } from "../../../src/closet/hooks";
import { isReviewableDraft } from "../../../src/closet/status";
import { Screen, SkeletonBlock } from "../../../src/ui";

export default function ReviewQueueRoute() {
  const { session } = useAuth();
  const reviewQueue = useReviewQueue(session?.access_token, 50, { disableCache: true });
  const firstReviewableId = useMemo(
    () => reviewQueue.items.find(isReviewableDraft)?.id ?? null,
    [reviewQueue.items]
  );
  const hasProcessingBacklog = reviewQueue.sections.some((section) => section.key !== "needs_review");

  useEffect(() => {
    if (reviewQueue.isLoading) {
      return;
    }

    if (firstReviewableId) {
      router.replace(`/review/${firstReviewableId}` as Href);
      return;
    }

    if (hasProcessingBacklog) {
      router.replace("/closet?tab=processing" as Href);
      return;
    }

    router.replace("/closet" as Href);
  }, [firstReviewableId, hasProcessingBacklog, reviewQueue.isLoading]);

  return (
    <Screen>
      <SkeletonBlock height={120} />
      <SkeletonBlock height={420} />
    </Screen>
  );
}
