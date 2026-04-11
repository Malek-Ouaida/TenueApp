import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  PanResponder,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions
} from "react-native";

import { humanizeEnum } from "../lib/format";
import {
  triggerErrorHaptic,
  triggerSelectionHaptic,
  triggerSuccessHaptic
} from "../lib/haptics";
import { supportsNativeAnimatedDriver } from "../lib/runtime";
import { useAuth } from "../auth/provider";
import { fontFamilies } from "../theme/typography";
import { prefetchClosetReviewItem, useClosetMetadataOptions, useClosetReviewItem } from "./hooks";
import {
  asString,
  asStringArray,
  buildAutoAcceptChanges,
  buildReviewFieldDescriptors,
  fieldIsMultiValue,
  formatFieldValue
} from "./reviewDeckShared";
import { getDraftPrimaryImage, getReviewItemPreview } from "./status";
import type {
  ClosetFieldCanonicalValue,
  ClosetDraftSnapshot,
  ClosetReviewFieldChange
} from "./types";

const SWIPE_THRESHOLD = 80;
const MAX_ROTATION = 12;

const CONFIDENCE_COLORS = {
  high: "#34D399",
  medium: "#FBBF24",
  low: "#F87171"
} as const;

type ReviewDeckScreenProps = {
  attentionCount: number;
  itemId: string;
  processingCount: number;
  reviewableItems: ClosetDraftSnapshot[];
};

function runAnimation(animation: Animated.CompositeAnimation) {
  return new Promise<void>((resolve) => {
    animation.start(() => resolve());
  });
}

export function ReviewDeckScreen({
  attentionCount,
  itemId,
  processingCount,
  reviewableItems
}: ReviewDeckScreenProps) {
  const { width: screenWidth } = useWindowDimensions();
  const cardWidth = Math.min(Math.max(screenWidth - 32, 280), 420);
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const reviewFlow = useClosetReviewItem(session?.access_token, itemId);

  const [flipped, setFlipped] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [optimisticValues, setOptimisticValues] = useState<Record<string, ClosetFieldCanonicalValue>>({});
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBrand, setDraftBrand] = useState("");
  const [pendingSaveCount, setPendingSaveCount] = useState(0);
  const hasPendingSaves = pendingSaveCount > 0;

  const translateX = useRef(new Animated.Value(0)).current;
  const rotateY = useRef(new Animated.Value(0)).current;
  const enterScale = useRef(new Animated.Value(0.96)).current;
  const enterTranslateY = useRef(new Animated.Value(18)).current;
  const enterOpacity = useRef(new Animated.Value(0)).current;
  const optimisticTokensRef = useRef<Record<string, number>>({});
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

  const currentIndex = useMemo(
    () => reviewableItems.findIndex((item) => item.id === itemId),
    [itemId, reviewableItems]
  );
  const currentDraft = currentIndex >= 0 ? reviewableItems[currentIndex] : null;
  const nextDraft = currentIndex + 1 < reviewableItems.length ? reviewableItems[currentIndex + 1] : null;
  const total = reviewableItems.length;

  const fields = useMemo(
    () => buildReviewFieldDescriptors(reviewFlow.review, metadata.data),
    [metadata.data, reviewFlow.review]
  );
  const displayedFields = useMemo(
    () =>
      fields.map((field) => {
        if (!(field.field.field_name in optimisticValues)) {
          return field;
        }

        const optimisticValue = optimisticValues[field.field.field_name];
        return {
          ...field,
          value: formatFieldValue(optimisticValue) ?? "Needs review",
          valueSelection: optimisticValue
        };
      }),
    [fields, optimisticValues]
  );

  const previewImage =
    (reviewFlow.review ? getReviewItemPreview(reviewFlow.review)?.url : undefined) ??
    (reviewFlow.processing ? getReviewItemPreview(reviewFlow.processing)?.url : undefined) ??
    (currentDraft ? getDraftPrimaryImage(currentDraft)?.url : undefined) ??
    undefined;
  const categoryField = displayedFields.find((field) => field.field.field_name === "category") ?? null;
  const titleField = displayedFields.find((field) => field.field.field_name === "title") ?? null;
  const brandField = displayedFields.find((field) => field.field.field_name === "brand") ?? null;
  const editableSelectionFields = displayedFields.filter(
    (field) => !["title", "brand", "category"].includes(field.field.field_name)
  );
  const itemTitle =
    currentDraft?.title ??
    asString(displayedFields.find((field) => field.field.field_name === "subcategory")?.valueSelection ?? null) ??
    "Review this item";
  const sourceLabel = "AI review";
  const nextRoute = nextDraft ? (`/review/${nextDraft.id}` as Href) : ("/review" as Href);

  useEffect(() => {
    if (!session?.access_token || !nextDraft) {
      return;
    }

    void prefetchClosetReviewItem(session.access_token, nextDraft.id);
  }, [nextDraft, session?.access_token]);

  useEffect(() => {
    setFlipped(false);
    setConfirming(false);
    setIsBusy(false);
    setNotice(null);
    setOptimisticValues({});
    setPendingSaveCount(0);
    optimisticTokensRef.current = {};
    saveQueueRef.current = Promise.resolve();
    rotateY.setValue(0);
    translateX.setValue(0);
    enterScale.setValue(0.96);
    enterTranslateY.setValue(18);
    enterOpacity.setValue(0);

    if (!currentDraft) {
      return;
    }

    const animation = Animated.parallel([
      Animated.timing(enterScale, {
        toValue: 1,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: supportsNativeAnimatedDriver
      }),
      Animated.timing(enterTranslateY, {
        toValue: 0,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: supportsNativeAnimatedDriver
      }),
      Animated.timing(enterOpacity, {
        toValue: 1,
        duration: 180,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: supportsNativeAnimatedDriver
      })
    ]);

    animation.start();
    return () => {
      animation.stop();
    };
  }, [
    currentDraft,
    enterOpacity,
    enterScale,
    enterTranslateY,
    itemId,
    rotateY,
    translateX
  ]);

  useEffect(() => {
    setDraftTitle(
      asString(
        reviewFlow.review?.review_fields.find((field) => field.field_name === "title")?.current_state.canonical_value ??
          null
      ) ?? ""
    );
    setDraftBrand(
      asString(
        reviewFlow.review?.review_fields.find((field) => field.field_name === "brand")?.current_state.canonical_value ??
          null
      ) ?? ""
    );
  }, [reviewFlow.review?.review_version]);

  const springToCenter = useCallback(async () => {
    await runAnimation(
      Animated.spring(translateX, {
        toValue: 0,
        tension: 95,
        friction: 11,
        useNativeDriver: supportsNativeAnimatedDriver
      })
    );
  }, [translateX]);

  const flipToEdit = useCallback(async () => {
    setFlipped(true);
    await runAnimation(
      Animated.timing(rotateY, {
        toValue: 180,
        duration: 320,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: supportsNativeAnimatedDriver
      })
    );
  }, [rotateY]);

  const flipToFront = useCallback(async () => {
    await runAnimation(
      Animated.timing(rotateY, {
        toValue: 0,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: supportsNativeAnimatedDriver
      })
    );
    setFlipped(false);
  }, [rotateY]);

  const animateExit = useCallback(async () => {
    await runAnimation(
      Animated.timing(translateX, {
        toValue: screenWidth,
        duration: 240,
        easing: Easing.bezier(0.32, 0.72, 0, 1),
        useNativeDriver: supportsNativeAnimatedDriver
      })
    );
  }, [screenWidth, translateX]);

  const applyFieldChange = useCallback(
    async (change: ClosetReviewFieldChange) => {
      setNotice(null);
      const result = await reviewFlow.applyChanges([change]);

      if (result.ok) {
        await triggerSelectionHaptic();
        return true;
      }

      if (result.stale) {
        setNotice("The review changed on the server, so Tenue refreshed the latest snapshot.");
        return false;
      }

      setNotice(reviewFlow.error ?? "The field update could not be saved.");
      return false;
    },
    [reviewFlow]
  );

  const queueFieldChange = useCallback(
    (fieldName: string, optimisticValue: ClosetFieldCanonicalValue, change: ClosetReviewFieldChange) => {
      const nextToken = (optimisticTokensRef.current[fieldName] ?? 0) + 1;
      optimisticTokensRef.current[fieldName] = nextToken;

      setOptimisticValues((current) => ({
        ...current,
        [fieldName]: optimisticValue
      }));
      setPendingSaveCount((current) => current + 1);

      saveQueueRef.current = saveQueueRef.current
        .catch(() => undefined)
        .then(async () => {
          const ok = await applyFieldChange(change);

          if (optimisticTokensRef.current[fieldName] === nextToken) {
            setOptimisticValues((current) => {
              if (!(fieldName in current)) {
                return current;
              }

              const next = { ...current };
              delete next[fieldName];
              return next;
            });
          }

          void ok;
        })
        .finally(() => {
          setPendingSaveCount((current) => Math.max(0, current - 1));
        });
    },
    [applyFieldChange]
  );

  const queueFieldAction = useCallback(
    (fieldName: string, change: ClosetReviewFieldChange) => {
      const nextToken = (optimisticTokensRef.current[fieldName] ?? 0) + 1;
      optimisticTokensRef.current[fieldName] = nextToken;
      setPendingSaveCount((current) => current + 1);

      saveQueueRef.current = saveQueueRef.current
        .catch(() => undefined)
        .then(async () => {
          await applyFieldChange(change);
        })
        .finally(() => {
          setPendingSaveCount((current) => Math.max(0, current - 1));
        });
    },
    [applyFieldChange]
  );

  const saveTextField = useCallback(
    (fieldName: "title" | "brand", value: string) => {
      const normalized = value.trim();
      queueFieldAction(
        fieldName,
        normalized
          ? {
              field_name: fieldName,
              operation: "set_value",
              canonical_value: normalized
            }
          : {
              field_name: fieldName,
              operation: "clear"
            }
      );
    },
    [queueFieldAction]
  );

  const prepareReviewForConfirm = useCallback(async () => {
    if (!reviewFlow.review) {
      setNotice("The latest review snapshot is still loading.");
      return false;
    }

    const changes = buildAutoAcceptChanges(reviewFlow.review);
    if (changes.length === 0) {
      return true;
    }

    const result = await reviewFlow.applyChanges(changes);
    if (result.ok) {
      return true;
    }

    if (result.stale) {
      setNotice("The review changed on the server, so Tenue refreshed the latest snapshot.");
      return false;
    }

    setNotice(reviewFlow.error ?? "Tenue could not accept the AI suggestions.");
    return false;
  }, [reviewFlow]);

  const confirmReviewOnServer = useCallback(async () => {
    const result = await reviewFlow.confirm();
    if (result.ok) {
      await triggerSuccessHaptic();
      return true;
    }

    if (result.stale) {
      setNotice("The review changed on the server. Tenue refreshed the latest state.");
      return false;
    }

    await triggerErrorHaptic();
    setNotice(reviewFlow.error ?? "Confirmation failed.");
    return false;
  }, [reviewFlow]);

  const confirmFromFront = useCallback(async () => {
    if (!currentDraft || flipped || isBusy || reviewFlow.isMutating || hasPendingSaves) {
      return;
    }

    setIsBusy(true);
    setNotice(null);
    await saveQueueRef.current;

    const prepared = await prepareReviewForConfirm();
    if (!prepared) {
      setIsBusy(false);
      await springToCenter();
      return;
    }

    const confirmPromise = confirmReviewOnServer();
    const exitPromise = animateExit();

    const confirmed = await confirmPromise;
    if (!confirmed) {
      setIsBusy(false);
      await springToCenter();
      return;
    }

    await exitPromise;
    router.replace(nextRoute);
  }, [
    animateExit,
    confirmReviewOnServer,
    currentDraft,
    flipped,
    hasPendingSaves,
    isBusy,
    nextRoute,
    prepareReviewForConfirm,
    reviewFlow.isMutating,
    springToCenter
  ]);

  const confirmFromEdit = useCallback(async () => {
    if (!currentDraft || !flipped || isBusy || reviewFlow.isMutating) {
      return;
    }

    setIsBusy(true);
    setNotice(null);
    await saveQueueRef.current;

    const prepared = await prepareReviewForConfirm();
    if (!prepared) {
      setIsBusy(false);
      return;
    }

    setConfirming(true);
    const confirmPromise = confirmReviewOnServer();
    await flipToFront();

    const confirmed = await confirmPromise;
    if (!confirmed) {
      setConfirming(false);
      setIsBusy(false);
      await flipToEdit();
      return;
    }

    await animateExit();
    router.replace(nextRoute);
  }, [
    animateExit,
    confirmReviewOnServer,
    currentDraft,
    flipped,
    flipToEdit,
    flipToFront,
    isBusy,
    nextRoute,
    prepareReviewForConfirm,
    reviewFlow.isMutating
  ]);

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gesture) => {
          if (flipped || isBusy || reviewFlow.isMutating || hasPendingSaves || !currentDraft) {
            return false;
          }

          return Math.abs(gesture.dx) > 8 && Math.abs(gesture.dx) > Math.abs(gesture.dy);
        },
        onPanResponderMove: (_, gesture) => {
          if (flipped || isBusy || reviewFlow.isMutating) {
            return;
          }
          translateX.setValue(gesture.dx);
        },
        onPanResponderRelease: (_, gesture) => {
          if (gesture.dx > SWIPE_THRESHOLD) {
            void confirmFromFront();
            return;
          }

          if (gesture.dx < -SWIPE_THRESHOLD) {
            Animated.spring(translateX, {
              toValue: 0,
              tension: 95,
              friction: 11,
              useNativeDriver: supportsNativeAnimatedDriver
            }).start(() => {
              void flipToEdit();
            });
            return;
          }

          Animated.spring(translateX, {
            toValue: 0,
            tension: 95,
            friction: 11,
            useNativeDriver: supportsNativeAnimatedDriver
          }).start();
        }
      }),
    [confirmFromFront, currentDraft, flipToEdit, flipped, hasPendingSaves, isBusy, reviewFlow.isMutating, translateX]
  );

  const overlayRightOpacity = translateX.interpolate({
    inputRange: [0, 30, 160],
    outputRange: [0, 0.2, 1],
    extrapolate: "clamp"
  });
  const overlayLeftOpacity = translateX.interpolate({
    inputRange: [-160, -30, 0],
    outputRange: [1, 0.2, 0],
    extrapolate: "clamp"
  });
  const rightLabelOpacity = translateX.interpolate({
    inputRange: [10, 30, 160],
    outputRange: [0, 0.15, 1],
    extrapolate: "clamp"
  });
  const leftLabelOpacity = translateX.interpolate({
    inputRange: [-160, -30, -10],
    outputRange: [1, 0.15, 0],
    extrapolate: "clamp"
  });
  const cardRotate = translateX.interpolate({
    inputRange: [-screenWidth, 0, screenWidth],
    outputRange: [`-${MAX_ROTATION}deg`, "0deg", `${MAX_ROTATION}deg`],
    extrapolate: "clamp"
  });
  const nextScale = translateX.interpolate({
    inputRange: [-160, 0, 160],
    outputRange: [1, 0.94, 1],
    extrapolate: "clamp"
  });
  const nextOpacity = translateX.interpolate({
    inputRange: [-160, 0, 160],
    outputRange: [1, 0.5, 1],
    extrapolate: "clamp"
  });

  const frontAnimatedStyle = {
    opacity: enterOpacity,
    transform: [
      { translateX },
      { translateY: enterTranslateY },
      { scale: enterScale },
      { rotate: cardRotate },
      { perspective: 1200 },
      {
        rotateY: rotateY.interpolate({
          inputRange: [0, 180],
          outputRange: ["0deg", "180deg"]
        })
      }
    ]
  } as const;

  const backAnimatedStyle = {
    opacity: enterOpacity,
    transform: [
      { translateY: enterTranslateY },
      { scale: enterScale },
      { perspective: 1200 },
      {
        rotateY: rotateY.interpolate({
          inputRange: [0, 180],
          outputRange: ["180deg", "360deg"]
        })
      }
    ]
  } as const;

  if (!currentDraft || (reviewFlow.isLoading && !reviewFlow.review)) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.emptyContainer}>
          <Text style={styles.headerTitle}>Loading review</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {!flipped ? (
          <>
            <Animated.View
              pointerEvents="none"
              style={[styles.overlay, styles.greenOverlay, { opacity: confirming ? 1 : overlayRightOpacity }]}
            />
            <Animated.View
              pointerEvents="none"
              style={[styles.overlay, styles.lavenderOverlay, { opacity: overlayLeftOpacity }]}
            />
          </>
        ) : null}

        {confirming && flipped ? (
          <View pointerEvents="none" style={[styles.overlay, styles.confirmOverlay]} />
        ) : null}

        <View style={styles.header}>
          <Pressable
            onPress={() => {
              if (flipped) {
                void flipToFront();
                return;
              }

              router.replace("/closet" as Href);
            }}
            style={styles.iconButton}
          >
            <Ionicons name={flipped ? "refresh" : "arrow-back"} size={20} color="#111827" />
          </Pressable>

          <View>
            <Text style={styles.headerTitle}>{flipped ? "Edit Details" : "Review Items"}</Text>
            <Text style={styles.headerSubTitle}>
              {currentIndex + 1} of {total} items
            </Text>
          </View>

          <View style={styles.headerGhost} />
        </View>

        <View style={styles.progressRow}>
          {reviewableItems.map((reviewItem, index) => (
            <View
              key={reviewItem.id}
              style={[
                styles.progressDot,
                { backgroundColor: index <= currentIndex ? "#111827" : "#E5E7EB" }
              ]}
            />
          ))}
        </View>

        {notice ? <Text style={styles.notice}>{notice}</Text> : null}

        {!flipped ? (
          <View style={styles.swipeLabelsRow}>
            <Animated.View style={[styles.swipeLabelLeft, { opacity: leftLabelOpacity }]}>
              <Ionicons name="create-outline" size={14} color="#6B7280" />
              <Text style={styles.swipeLabelLeftText}>EDIT</Text>
            </Animated.View>

            <Animated.View
              style={[styles.swipeLabelRight, { opacity: confirming ? 1 : rightLabelOpacity }]}
            >
              <Text style={styles.swipeLabelRightText}>ADD TO CLOSET</Text>
              <Ionicons name="checkmark" size={15} color="#15803D" />
            </Animated.View>
          </View>
        ) : (
          <View style={styles.swipeSpacer} />
        )}

        <View style={styles.cardStackWrap}>
          {nextDraft && !flipped ? (
            <Animated.View
              style={[
                styles.nextCard,
                {
                  opacity: nextOpacity,
                  left: "50%",
                  marginLeft: -cardWidth / 2,
                  transform: [{ scale: nextScale }],
                  width: cardWidth
                }
              ]}
            >
              <View style={styles.upNextPill}>
                <Text style={styles.upNextText}>Up next</Text>
              </View>
              {getDraftPrimaryImage(nextDraft)?.url ? (
                <Image
                  contentFit="cover"
                  source={{ uri: getDraftPrimaryImage(nextDraft)?.url }}
                  style={styles.nextImage}
                />
              ) : (
                <View style={styles.nextImageFallback} />
              )}
            </Animated.View>
          ) : null}

          <View style={[styles.flipWrap, { width: cardWidth }]}>
            <Animated.View
              pointerEvents={flipped ? "none" : "auto"}
              style={[styles.cardFace, frontAnimatedStyle]}
              {...panResponder.panHandlers}
            >
              <View style={styles.badgeRow}>
                <View style={styles.aiBadge}>
                  <Ionicons name="sparkles-outline" size={12} color="#111827" />
                  <Text style={styles.aiBadgeText}>AI identified · {sourceLabel}</Text>
                </View>
              </View>

              {previewImage ? (
                <Image contentFit="cover" source={{ uri: previewImage }} style={styles.heroImage} />
              ) : (
                <View style={styles.heroImageFallback} />
              )}

              <ScrollView
                contentContainerStyle={styles.fieldsScrollContent}
                nestedScrollEnabled
                showsVerticalScrollIndicator={false}
                style={styles.fieldsScroll}
              >
                {displayedFields.map((field) => (
                  <View key={field.field.field_name} style={styles.fieldRow}>
                    <Text style={styles.fieldLabel}>{field.label}</Text>
                    <View style={styles.fieldValueWrap}>
                      <Text style={styles.fieldValue}>{field.value}</Text>
                      <View
                        style={[
                          styles.confidenceDot,
                          { backgroundColor: CONFIDENCE_COLORS[field.confidence] }
                        ]}
                      />
                    </View>
                  </View>
                ))}
              </ScrollView>
            </Animated.View>

            <Animated.View
              pointerEvents={flipped ? "auto" : "none"}
              style={[styles.cardFace, styles.backCardFace, backAnimatedStyle]}
            >
              <View style={styles.backContent}>
                <ScrollView
                  contentContainerStyle={styles.backScrollContent}
                  nestedScrollEnabled
                  showsVerticalScrollIndicator={false}
                  style={styles.backScroll}
                >
                  <View style={styles.editHeader}>
                    {previewImage ? (
                      <Image contentFit="cover" source={{ uri: previewImage }} style={styles.editThumb} />
                    ) : (
                      <View style={styles.editThumbFallback} />
                    )}
                    <View style={styles.editHeaderCopy}>
                      <Text style={styles.editTitle}>{itemTitle}</Text>
                      <Text style={styles.editSubTitle}>{sourceLabel} · Tap to change</Text>
                    </View>
                  </View>

                  <View style={styles.editSections}>
                    {categoryField ? (
                      <View style={styles.derivedFieldCard}>
                        <Text style={styles.editFieldLabel}>Category</Text>
                        <Text style={styles.derivedFieldValue}>{categoryField.value}</Text>
                        <Text style={styles.derivedFieldHelper}>
                          Change subcategory to move this item into another category.
                        </Text>
                      </View>
                    ) : null}

                    {titleField ? (
                      <View style={styles.editFieldBlock}>
                        <Text style={styles.editFieldLabel}>Title</Text>
                        <TextInput
                          autoCapitalize="words"
                          placeholder="Closet item title"
                          placeholderTextColor="#9CA3AF"
                          style={styles.textField}
                          value={draftTitle}
                          onChangeText={setDraftTitle}
                        />
                        <View style={styles.actionPillRow}>
                          <Pressable
                            onPress={() => saveTextField("title", draftTitle)}
                            style={({ pressed }) => [
                              styles.actionPill,
                              styles.actionPillPrimary,
                              pressed ? styles.pressed : null
                            ]}
                          >
                            <Text style={[styles.actionPillLabel, styles.actionPillLabelPrimary]}>Save</Text>
                          </Pressable>
                          {titleField.field.suggested_state ? (
                            <Pressable
                              onPress={() =>
                                queueFieldAction("title", {
                                  field_name: "title",
                                  operation: "accept_suggestion"
                                })
                              }
                              style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                            >
                              <Text style={styles.actionPillLabel}>Use suggestion</Text>
                            </Pressable>
                          ) : null}
                          <Pressable
                            onPress={() =>
                              queueFieldAction("title", {
                                field_name: "title",
                                operation: "clear"
                              })
                            }
                            style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                          >
                            <Text style={styles.actionPillLabel}>Clear</Text>
                          </Pressable>
                        </View>
                      </View>
                    ) : null}

                    {brandField ? (
                      <View style={styles.editFieldBlock}>
                        <Text style={styles.editFieldLabel}>Brand</Text>
                        <TextInput
                          autoCapitalize="words"
                          placeholder="Brand"
                          placeholderTextColor="#9CA3AF"
                          style={styles.textField}
                          value={draftBrand}
                          onChangeText={setDraftBrand}
                        />
                        <View style={styles.actionPillRow}>
                          <Pressable
                            onPress={() => saveTextField("brand", draftBrand)}
                            style={({ pressed }) => [
                              styles.actionPill,
                              styles.actionPillPrimary,
                              pressed ? styles.pressed : null
                            ]}
                          >
                            <Text style={[styles.actionPillLabel, styles.actionPillLabelPrimary]}>Save</Text>
                          </Pressable>
                          {brandField.field.suggested_state ? (
                            <Pressable
                              onPress={() =>
                                queueFieldAction("brand", {
                                  field_name: "brand",
                                  operation: "accept_suggestion"
                                })
                              }
                              style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                            >
                              <Text style={styles.actionPillLabel}>Use suggestion</Text>
                            </Pressable>
                          ) : null}
                          <Pressable
                            onPress={() =>
                              queueFieldAction("brand", {
                                field_name: "brand",
                                operation: "mark_not_applicable"
                              })
                            }
                            style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                          >
                            <Text style={styles.actionPillLabel}>Not applicable</Text>
                          </Pressable>
                        </View>
                      </View>
                    ) : null}

                    {editableSelectionFields.map((field) => {
                      if (field.options.length === 0) {
                        return null;
                      }

                      const multi = fieldIsMultiValue(field.field.field_name);
                      const selectedValues = multi
                        ? asStringArray(field.valueSelection)
                        : [asString(field.valueSelection) ?? ""].filter(Boolean);

                      return (
                        <View key={field.field.field_name} style={styles.editFieldBlock}>
                          <Text style={styles.editFieldLabel}>{field.label}</Text>
                          <View style={styles.chipsWrap}>
                            {field.options.map((option) => {
                              const selected = selectedValues.includes(option);

                              return (
                                <Pressable
                                  key={option}
                                  onPress={() => {
                                    if (isBusy) {
                                      return;
                                    }

                                    const nextSelection = multi
                                      ? selected
                                        ? selectedValues.filter((value) => value !== option)
                                        : selectedValues.concat(option)
                                      : [option];

                                    queueFieldChange(
                                      field.field.field_name,
                                      multi ? nextSelection : nextSelection[0] ?? null,
                                      nextSelection.length === 0
                                        ? {
                                            field_name: field.field.field_name,
                                            operation: "clear"
                                          }
                                        : {
                                            field_name: field.field.field_name,
                                            operation: "set_value",
                                            canonical_value: multi ? nextSelection : nextSelection[0]
                                          }
                                    );
                                  }}
                                  style={[
                                    styles.chip,
                                    selected ? styles.chipSelected : styles.chipIdle
                                  ]}
                                >
                                  <Text
                                    style={[
                                      styles.chipText,
                                      selected ? styles.chipTextSelected : styles.chipTextIdle
                                    ]}
                                  >
                                    {humanizeEnum(option)}
                                  </Text>
                                </Pressable>
                              );
                            })}
                          </View>
                          <View style={styles.actionPillRow}>
                            {field.field.suggested_state ? (
                              <Pressable
                                onPress={() =>
                                  queueFieldAction(field.field.field_name, {
                                    field_name: field.field.field_name,
                                    operation: "accept_suggestion"
                                  })
                                }
                                style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                              >
                                <Text style={styles.actionPillLabel}>Use suggestion</Text>
                              </Pressable>
                          ) : null}
                          {!field.field.required ? (
                            <Pressable
                              onPress={() =>
                                queueFieldAction(field.field.field_name, {
                                  field_name: field.field.field_name,
                                  operation: "clear"
                                })
                              }
                              style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                            >
                              <Text style={styles.actionPillLabel}>Clear</Text>
                            </Pressable>
                          ) : null}
                            {!field.field.required ? (
                              <Pressable
                                onPress={() =>
                                  queueFieldAction(field.field.field_name, {
                                    field_name: field.field.field_name,
                                    operation: "mark_not_applicable"
                                  })
                                }
                                style={({ pressed }) => [styles.actionPill, pressed ? styles.pressed : null]}
                              >
                                <Text style={styles.actionPillLabel}>Not applicable</Text>
                              </Pressable>
                            ) : null}
                          </View>
                        </View>
                      );
                    })}
                  </View>
                </ScrollView>

                <View pointerEvents="none" style={styles.bottomFade} />

                <Pressable
                  onPress={() => void confirmFromEdit()}
                  style={[styles.primaryButton, styles.confirmButton]}
                >
                  <Ionicons name="checkmark" size={18} color="#FFFFFF" />
                  <Text style={styles.primaryButtonText}>Confirm & Add to Closet</Text>
                </Pressable>
              </View>
            </Animated.View>
          </View>
        </View>

        {!flipped ? (
          <View style={styles.actionsRow}>
            <Pressable onPress={() => void flipToEdit()} style={styles.secondaryButton}>
              <Ionicons name="create-outline" size={16} color="#111827" />
              <Text style={styles.secondaryButtonText}>Edit</Text>
            </Pressable>
            <Pressable onPress={() => void confirmFromFront()} style={styles.primaryButton}>
              <Ionicons name="checkmark" size={18} color="#FFFFFF" />
              <Text style={styles.primaryButtonText}>Add to Closet</Text>
            </Pressable>
          </View>
        ) : null}

        {processingCount > 0 || attentionCount > 0 ? (
          <View style={styles.queueMeta}>
            {processingCount > 0 ? (
              <Text style={styles.queueMetaText}>{processingCount} still processing</Text>
            ) : null}
            {attentionCount > 0 ? (
              <Text style={styles.queueMetaText}>{attentionCount} need attention</Text>
            ) : null}
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#FCFCFD"
  },
  container: {
    flex: 1,
    width: "100%",
    maxWidth: 460,
    alignSelf: "center",
    paddingHorizontal: 16,
    overflow: "hidden"
  },
  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24
  },
  overlay: {
    ...StyleSheet.absoluteFillObject
  },
  greenOverlay: {
    backgroundColor: "rgba(209, 250, 229, 0.55)"
  },
  lavenderOverlay: {
    backgroundColor: "rgba(229, 222, 255, 0.45)"
  },
  confirmOverlay: {
    backgroundColor: "rgba(209, 250, 229, 0.65)"
  },
  header: {
    paddingTop: 8,
    paddingBottom: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2
  },
  headerGhost: {
    width: 40,
    height: 40
  },
  headerTitle: {
    textAlign: "center",
    fontSize: 16,
    fontFamily: fontFamilies.sansSemiBold,
    color: "#111827"
  },
  headerSubTitle: {
    marginTop: 2,
    textAlign: "center",
    fontSize: 13,
    fontFamily: fontFamilies.sansRegular,
    color: "#6B7280"
  },
  progressRow: {
    marginTop: 8,
    marginBottom: 12,
    flexDirection: "row",
    gap: 8
  },
  progressDot: {
    flex: 1,
    height: 4,
    borderRadius: 999
  },
  notice: {
    marginBottom: 8,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    color: "#6B7280",
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18
  },
  swipeLabelsRow: {
    height: 28,
    marginBottom: 4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  swipeSpacer: {
    height: 28
  },
  swipeLabelLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6
  },
  swipeLabelLeftText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 13,
    letterSpacing: 1.8,
    color: "#6B7280"
  },
  swipeLabelRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5
  },
  swipeLabelRightText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 13,
    letterSpacing: 1.4,
    color: "#15803D"
  },
  cardStackWrap: {
    flex: 1,
    minHeight: 0,
    alignItems: "center"
  },
  nextCard: {
    position: "absolute",
    top: 0,
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 16,
    shadowColor: "#000000",
    shadowOpacity: 0.05,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2
  },
  upNextPill: {
    alignSelf: "flex-start",
    backgroundColor: "#EEE9FF",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    marginBottom: 12
  },
  upNextText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 11,
    color: "rgba(17, 24, 39, 0.6)",
    letterSpacing: 0.4
  },
  nextImage: {
    width: "100%",
    aspectRatio: 4 / 5,
    borderRadius: 18,
    opacity: 0.9
  },
  nextImageFallback: {
    width: "100%",
    aspectRatio: 4 / 5,
    borderRadius: 18,
    backgroundColor: "#F3F4F6"
  },
  flipWrap: {
    marginTop: 2
  },
  cardFace: {
    width: "100%",
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
    padding: 16,
    shadowColor: "#000000",
    shadowOpacity: 0.08,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 4,
    backfaceVisibility: "hidden"
  },
  backCardFace: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    padding: 0,
    overflow: "hidden"
  },
  badgeRow: {
    marginBottom: 12
  },
  aiBadge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#EEE9FF",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  aiBadgeText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 11,
    color: "#111827",
    letterSpacing: 0.3
  },
  heroImage: {
    width: "100%",
    aspectRatio: 4 / 5,
    borderRadius: 18,
    marginBottom: 14
  },
  heroImageFallback: {
    width: "100%",
    aspectRatio: 4 / 5,
    borderRadius: 18,
    marginBottom: 14,
    backgroundColor: "#F3F4F6"
  },
  fieldsScroll: {
    maxHeight: 200
  },
  fieldsScrollContent: {
    paddingBottom: 8
  },
  fieldRow: {
    paddingVertical: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  fieldLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    color: "#6B7280"
  },
  fieldValueWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    maxWidth: "55%"
  },
  fieldValue: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    color: "#111827",
    textAlign: "right",
    flexShrink: 1
  },
  confidenceDot: {
    width: 6,
    height: 6,
    borderRadius: 999
  },
  backContent: {
    flex: 1,
    minHeight: 0,
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 20
  },
  backScroll: {
    flex: 1
  },
  backScrollContent: {
    paddingBottom: 120
  },
  editSections: {
    gap: 18
  },
  derivedFieldCard: {
    gap: 6,
    padding: 16,
    borderRadius: 18,
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E5E7EB"
  },
  editHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 20
  },
  editHeaderCopy: {
    flex: 1
  },
  editThumb: {
    width: 56,
    height: 56,
    borderRadius: 18
  },
  editThumbFallback: {
    width: 56,
    height: 56,
    borderRadius: 18,
    backgroundColor: "#F3F4F6"
  },
  editTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    color: "#111827"
  },
  editSubTitle: {
    marginTop: 2,
    fontSize: 12,
    fontFamily: fontFamilies.sansRegular,
    color: "#6B7280"
  },
  editFieldBlock: {
    marginBottom: 18
  },
  editFieldLabel: {
    marginBottom: 10,
    fontFamily: fontFamilies.sansBold,
    fontSize: 11,
    color: "#6B7280",
    letterSpacing: 1.3,
    textTransform: "uppercase"
  },
  derivedFieldValue: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 16,
    lineHeight: 20,
    color: "#111827"
  },
  derivedFieldHelper: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 17,
    color: "#6B7280"
  },
  textField: {
    minHeight: 52,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#E5E7EB",
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: "#111827",
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 15
  },
  actionPillRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 10
  },
  actionPill: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#EEF0F3"
  },
  actionPillPrimary: {
    backgroundColor: "#111827"
  },
  actionPillLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    color: "#111827"
  },
  actionPillLabelPrimary: {
    color: "#FFFFFF"
  },
  pressed: {
    opacity: 0.78
  },
  chipsWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 10
  },
  chipIdle: {
    backgroundColor: "#F3F4F6"
  },
  chipSelected: {
    backgroundColor: "#111827"
  },
  chipText: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
  },
  chipTextIdle: {
    color: "#111827"
  },
  chipTextSelected: {
    color: "#FFFFFF"
  },
  bottomFade: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 84,
    height: 40,
    backgroundColor: "rgba(255,255,255,0.92)"
  },
  actionsRow: {
    paddingTop: 16,
    paddingBottom: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 12
  },
  secondaryButton: {
    height: 52,
    paddingHorizontal: 28,
    borderRadius: 999,
    backgroundColor: "#EEF0F3",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  secondaryButtonText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    color: "#111827"
  },
  primaryButton: {
    minHeight: 52,
    paddingHorizontal: 28,
    borderRadius: 999,
    backgroundColor: "#111827",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    shadowColor: "#000000",
    shadowOpacity: 0.14,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3
  },
  primaryButtonText: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    color: "#FFFFFF"
  },
  confirmButton: {
    position: "absolute",
    left: 20,
    right: 20,
    bottom: 20
  },
  queueMeta: {
    paddingBottom: 12,
    alignItems: "center",
    gap: 4
  },
  queueMetaText: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: "#6B7280"
  }
});

export default ReviewDeckScreen;
