import { router, type Href } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import { humanizeEnum } from "../lib/format";
import {
  triggerErrorHaptic,
  triggerSelectionHaptic,
  triggerSuccessHaptic
} from "../lib/haptics";
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

const palette = {
  background: "#FCFCFD",
  card: "#FFFFFF",
  foreground: "#111827",
  muted: "#6B7280",
  secondary: "#F3F4F6",
  lavender: "#EEE9FF",
  green: "#15803D"
} as const;

type RafCallback = () => void;
const webSansRegular = `${fontFamilies.sansRegular}, Manrope, sans-serif`;
const webSansSemiBold = `${fontFamilies.sansSemiBold}, Manrope, sans-serif`;
const webSansBold = `${fontFamilies.sansBold}, Manrope, sans-serif`;

const browser = globalThis as {
  innerWidth?: number;
  clearTimeout: typeof clearTimeout;
  setTimeout: typeof setTimeout;
  requestAnimationFrame?: (callback: RafCallback) => number;
  cancelAnimationFrame?: (handle: number) => void;
};

type ReviewDeckScreenProps = {
  attentionCount: number;
  itemId: string;
  processingCount: number;
  reviewableItems: ClosetDraftSnapshot[];
};

function iconStyle(size = 16): CSSProperties {
  return {
    display: "inline-flex",
    width: size,
    height: size,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0
  };
}

function IconArrowLeft() {
  return (
    <svg viewBox="0 0 24 24" style={iconStyle(20)} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </svg>
  );
}

function IconRotate() {
  return (
    <svg viewBox="0 0 24 24" style={iconStyle(20)} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 2v6h-6" />
      <path d="M3 11a9 9 0 0 1 15.55-6.36L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 13a9 9 0 0 1-15.55 6.36L3 16" />
    </svg>
  );
}

function IconSparkles() {
  return (
    <svg viewBox="0 0 24 24" style={iconStyle(12)} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.4L12 15l-1.9-4.6L5.5 9l4.6-1.4L12 3z" />
      <path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z" />
    </svg>
  );
}

function IconCheck({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" style={iconStyle(size)} fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function IconPencil() {
  return (
    <svg viewBox="0 0 24 24" style={iconStyle(15)} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  );
}

export function ReviewDeckScreen({
  attentionCount,
  itemId,
  processingCount,
  reviewableItems
}: ReviewDeckScreenProps) {
  const { session } = useAuth();
  const metadata = useClosetMetadataOptions(session?.access_token);
  const reviewFlow = useClosetReviewItem(session?.access_token, itemId);

  const [flipped, setFlipped] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [displayOffset, setDisplayOffset] = useState(0);
  const [phase, setPhase] = useState<"idle" | "entering" | "exiting">("entering");
  const [notice, setNotice] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [optimisticValues, setOptimisticValues] = useState<Record<string, ClosetFieldCanonicalValue>>({});
  const [pendingSaveCount, setPendingSaveCount] = useState(0);
  const hasPendingSaves = pendingSaveCount > 0;

  const dragX = useRef(0);
  const startX = useRef(0);
  const startY = useRef(0);
  const dragging = useRef(false);
  const locked = useRef<"horizontal" | "vertical" | null>(null);
  const rafId = useRef<number | ReturnType<typeof setTimeout>>(0);
  const enterTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const exitTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
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
    setPhase("entering");
    setFlipped(false);
    setConfirming(false);
    setDisplayOffset(0);
    setNotice(null);
    setIsBusy(false);
    setOptimisticValues({});
    setPendingSaveCount(0);
    optimisticTokensRef.current = {};
    saveQueueRef.current = Promise.resolve();
    dragX.current = 0;

    if (enterTimeout.current) {
      browser.clearTimeout(enterTimeout.current);
    }

    enterTimeout.current = browser.setTimeout(() => setPhase("idle"), 240);

    return () => {
      if (enterTimeout.current) {
        browser.clearTimeout(enterTimeout.current);
      }
      if (exitTimeout.current) {
        browser.clearTimeout(exitTimeout.current);
      }
      browser.cancelAnimationFrame?.(rafId.current as number);
    };
  }, [itemId]);

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

  const finishAdvance = useCallback(
    (delayMs: number) => {
      if (exitTimeout.current) {
        browser.clearTimeout(exitTimeout.current);
      }

      exitTimeout.current = browser.setTimeout(() => {
        router.replace(nextRoute);
      }, delayMs);
    },
    [nextRoute]
  );

  const confirmFromFront = useCallback(async () => {
    if (!currentDraft || flipped || isBusy || reviewFlow.isMutating || hasPendingSaves || phase !== "idle") {
      return;
    }

    setIsBusy(true);
    setNotice(null);
    await saveQueueRef.current;

    const prepared = await prepareReviewForConfirm();
    if (!prepared) {
      setIsBusy(false);
      setDisplayOffset(0);
      return;
    }

    const exitStartedAt = Date.now();
    const confirmPromise = confirmReviewOnServer();
    setPhase("exiting");
    setDisplayOffset(browser.innerWidth ?? 1200);

    const confirmed = await confirmPromise;
    if (!confirmed) {
      setPhase("idle");
      setIsBusy(false);
      setDisplayOffset(0);
      return;
    }

    finishAdvance(Math.max(0, 220 - (Date.now() - exitStartedAt)));
  }, [
    confirmReviewOnServer,
    currentDraft,
    finishAdvance,
    flipped,
    hasPendingSaves,
    isBusy,
    phase,
    prepareReviewForConfirm,
    reviewFlow.isMutating
  ]);

  const confirmFromEdit = useCallback(async () => {
    if (!currentDraft || !flipped || isBusy || reviewFlow.isMutating || phase !== "idle") {
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
    setFlipped(false);

    const flipStartedAt = Date.now();
    const confirmed = await confirmReviewOnServer();
    if (!confirmed) {
      setConfirming(false);
      setFlipped(true);
      setIsBusy(false);
      return;
    }

    if (exitTimeout.current) {
      browser.clearTimeout(exitTimeout.current);
    }

    exitTimeout.current = browser.setTimeout(() => {
      setPhase("exiting");
      setDisplayOffset(browser.innerWidth ?? 1200);
      finishAdvance(0);
    }, Math.max(0, 180 - (Date.now() - flipStartedAt)));
  }, [
    confirmReviewOnServer,
    currentDraft,
    finishAdvance,
    flipped,
    isBusy,
    phase,
    prepareReviewForConfirm,
    reviewFlow.isMutating
  ]);

  const onDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (flipped || phase !== "idle" || isBusy || reviewFlow.isMutating || hasPendingSaves) {
      return;
    }

    dragging.current = true;
    locked.current = null;
    startX.current = event.clientX;
    startY.current = event.clientY;
    dragX.current = 0;
    (event.currentTarget as HTMLDivElement & { setPointerCapture?: (pointerId: number) => void }).setPointerCapture?.(
      event.pointerId
    );
  };

  const onMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging.current) {
      return;
    }

    const dx = event.clientX - startX.current;
    const dy = event.clientY - startY.current;

    if (!locked.current) {
      if (Math.abs(dx) > 8 || Math.abs(dy) > 8) {
        locked.current = Math.abs(dx) > Math.abs(dy) ? "horizontal" : "vertical";
      }
      return;
    }

    if (locked.current === "vertical") {
      return;
    }

    dragX.current = dx;
    browser.cancelAnimationFrame?.(rafId.current as number);
    rafId.current = (browser.requestAnimationFrame ??
      ((callback: RafCallback) => browser.setTimeout(callback, 16)))(() =>
      setDisplayOffset(dx)
    );
  };

  const onUp = async () => {
    if (!dragging.current) {
      return;
    }

    dragging.current = false;
    locked.current = null;
    const dx = dragX.current;

    if (dx > SWIPE_THRESHOLD) {
      await confirmFromFront();
      return;
    }

    if (dx < -SWIPE_THRESHOLD) {
      setDisplayOffset(0);
      dragX.current = 0;
      setFlipped(true);
      return;
    }

    setDisplayOffset(0);
    dragX.current = 0;
  };

  const pct = Math.min(Math.abs(displayOffset) / 160, 1);
  const rotation = (displayOffset / Math.max(browser.innerWidth ?? 1, 1)) * MAX_ROTATION;
  const isRight = displayOffset > 30;
  const isLeft = displayOffset < -30;
  const nextScale = 0.94 + pct * 0.06;
  const nextOpacity = 0.5 + pct * 0.5;

  const containerTransform: CSSProperties =
    phase === "exiting"
      ? {
          transform: `translateX(110%) rotate(${MAX_ROTATION}deg)`,
          opacity: 0,
          transition: "transform 0.35s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.35s ease"
        }
      : phase === "entering"
        ? {
            transform: "scale(0.96) translateY(18px)",
            opacity: 0,
            animation: "reviewCardEnter 0.24s cubic-bezier(0.32, 0.72, 0, 1) forwards"
          }
        : {
            transform: flipped
              ? "rotateY(180deg)"
              : `translateX(${displayOffset}px) rotate(${rotation}deg)`,
            transition: flipped
              ? "transform 0.3s ease"
              : dragging.current
                ? "none"
                : "transform 0.22s cubic-bezier(0.32, 0.72, 0, 1)"
          };

  if (!currentDraft || (reviewFlow.isLoading && !reviewFlow.review)) {
    return (
      <div style={loadingScreenStyle}>
        <div style={{ height: 80, borderRadius: 24, background: "#FFFFFF" }} />
        <div style={{ height: 540, borderRadius: 24, background: "#FFFFFF" }} />
      </div>
    );
  }

  return (
    <div style={viewportStyle}>
      <div style={screenStyle}>
        {!flipped ? (
          <>
            <div
              style={{
                ...overlayStyle,
                background: "radial-gradient(ellipse at 70% 40%, hsl(152 76% 93% / 0.6), transparent 70%)",
                opacity: confirming ? 1 : isRight ? pct : 0,
                transition: "opacity 0.3s ease"
              }}
            />
            <div
              style={{
                ...overlayStyle,
                background: "radial-gradient(ellipse at 30% 40%, rgba(229,222,255,0.5), transparent 70%)",
                opacity: isLeft ? pct : 0,
                transition: "opacity 0.15s ease"
              }}
            />
          </>
        ) : null}

        {confirming && flipped ? (
          <div
            style={{
              ...overlayStyle,
              background: "radial-gradient(ellipse at center 40%, hsl(152 76% 93% / 0.7), transparent 80%)"
            }}
          />
        ) : null}

        <header style={headerStyle}>
          <button
            onClick={() => {
              if (flipped) {
                setFlipped(false);
                return;
              }

              router.replace("/closet" as Href);
            }}
            style={headerButtonStyle}
          >
            {flipped ? <IconRotate /> : <IconArrowLeft />}
          </button>

          <div style={{ textAlign: "center" }}>
            <h1 style={headerTitleStyle}>{flipped ? "Edit Details" : "Review Items"}</h1>
            <p style={headerSubtitleStyle}>
              {currentIndex + 1} of {total} items
            </p>
          </div>

          <div style={{ width: 40 }} />
        </header>

        <div style={progressRowStyle}>
          {reviewableItems.map((reviewItem, index) => (
            <div
              key={reviewItem.id}
              style={{
                flex: 1,
                height: 4,
                borderRadius: 999,
                backgroundColor: index <= currentIndex ? palette.foreground : "#E5E7EB",
                transition: "background-color 0.5s ease"
              }}
            />
          ))}
        </div>

        {notice ? <div style={noticeStyle}>{notice}</div> : null}

        {!flipped || confirming ? (
          <div style={hintRowStyle}>
            <div
              style={{
                ...hintBadgeStyle,
                opacity: isLeft ? pct : 0,
                transform: `translateX(${Math.min(displayOffset * 0.1, 0)}px)`
              }}
            >
              <IconPencil />
              <span>EDIT</span>
            </div>
            <div
              style={{
                ...hintBadgeStyle,
                color: palette.green,
                opacity: confirming ? 1 : isRight ? pct : 0,
                transform: `translateX(${Math.max(displayOffset * 0.1, 0)}px)`
              }}
            >
              <span>ADD TO CLOSET</span>
              <IconCheck size={16} />
            </div>
          </div>
        ) : (
          <div style={{ height: 28 }} />
        )}

        <div style={stackStyle}>
          {nextDraft && !flipped ? (
            <div
              style={{
                ...nextCardStyle,
                transform: `translateX(-50%) scale(${nextScale})`,
                opacity: nextOpacity
              }}
            >
              <div style={nextBadgeStyle}>Up next</div>
              <div style={imageShellStyle}>
                {getDraftPrimaryImage(nextDraft)?.url ? (
                  <img
                    alt={nextDraft.title ?? "Next item"}
                    draggable={false}
                    src={getDraftPrimaryImage(nextDraft)?.url}
                    style={{ ...imageStyle, filter: "blur(2px)" }}
                  />
                ) : (
                  <div style={{ ...imageStyle, border: `1px solid ${palette.secondary}` }} />
                )}
              </div>
            </div>
          ) : null}

          <div
            style={{
              ...cardShellStyle,
              ...containerTransform
            }}
          >
            <div
              onPointerCancel={() => void onUp()}
              onPointerDown={onDown}
              onPointerMove={onMove}
              onPointerUp={() => void onUp()}
              style={{
                ...frontFaceStyle,
                boxShadow: `0 ${10 + pct * 10}px ${30 + pct * 15}px rgba(0,0,0,${0.05 + pct * 0.05})`
              }}
            >
              <div style={badgeRowStyle}>
                <div style={aiBadgeStyle}>
                  <IconSparkles />
                  <span>AI identified · {sourceLabel}</span>
                </div>
              </div>

              <div style={{ ...imageShellStyle, marginBottom: 16 }}>
                {previewImage ? (
                  <img
                    alt={itemTitle}
                    draggable={false}
                    src={previewImage}
                    style={{
                      ...imageStyle,
                      transform: phase === "entering" ? "scale(1.06)" : "scale(1.02)",
                      transition: "transform 0.35s ease-out"
                    }}
                  />
                ) : (
                  <div style={{ ...imageStyle, border: `1px solid ${palette.secondary}` }} />
                )}
              </div>

              <div style={frontFieldsStyle}>
                {displayedFields.map((field, index) => (
                  <div
                    key={field.field.field_name}
                    style={{
                      ...frontFieldRowStyle,
                        animation:
                        phase === "entering" ? `reviewFieldFadeIn 0.18s ${index * 24}ms ease-out both` : undefined
                    }}
                  >
                    <span style={frontLabelStyle}>{field.label}</span>
                    <div style={frontValueWrapStyle}>
                      <span style={frontValueStyle}>{field.value}</span>
                      <div
                        style={{
                          width: 5,
                          height: 5,
                          borderRadius: 999,
                          background:
                            field.confidence === "high"
                              ? "#34D399"
                              : field.confidence === "medium"
                                ? "#FBBF24"
                                : "#F87171"
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={backFaceStyle}>
              <div style={backScrollStyle}>
                <div style={editHeaderStyle}>
                  <div style={editThumbStyle}>
                    {previewImage ? (
                      <img alt={itemTitle} draggable={false} src={previewImage} style={imageStyle} />
                    ) : (
                      <div style={{ ...imageStyle, border: `1px solid ${palette.secondary}` }} />
                    )}
                  </div>
                  <div>
                    <h3 style={editTitleStyle}>{itemTitle}</h3>
                    <p style={editSubtitleStyle}>{sourceLabel} · Tap to change</p>
                  </div>
                </div>

                <div style={editSectionsStyle}>
                  {displayedFields.map((field) => {
                    if (field.options.length === 0) {
                      return null;
                    }

                    const multi = fieldIsMultiValue(field.field.field_name);
                    const selectedValues = multi
                      ? asStringArray(field.valueSelection)
                      : [asString(field.valueSelection) ?? ""].filter(Boolean);

                    return (
                      <div key={field.field.field_name}>
                        <label style={chipLabelStyle}>{field.label}</label>
                        <div style={chipsWrapStyle}>
                          {field.options.map((option) => {
                            const selected = selectedValues.includes(option);

                            return (
                              <button
                                key={option}
                                onClick={() => {
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
                                style={selected ? chipButtonActiveStyle : chipButtonStyle}
                              >
                                {humanizeEnum(option)}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={bottomFadeStyle} />
              <div style={backFooterStyle}>
                <button onClick={() => void confirmFromEdit()} style={primaryButtonStyle}>
                  <span style={buttonInnerStyle}>
                    <IconCheck size={18} />
                    Confirm & Add to Closet
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {!flipped ? (
          <div style={actionRowStyle}>
            <button onClick={() => setFlipped(true)} style={secondaryButtonStyle}>
              <span style={buttonInnerStyle}>
                <IconPencil />
                Edit
              </span>
            </button>
            <button onClick={() => void confirmFromFront()} style={primaryButtonStyle}>
              <span style={buttonInnerStyle}>
                <IconCheck size={18} />
                Add to Closet
              </span>
            </button>
          </div>
        ) : null}

        {processingCount > 0 || attentionCount > 0 ? (
          <div style={queueMetaStyle}>
            {processingCount > 0 ? <div>{processingCount} still processing</div> : null}
            {attentionCount > 0 ? <div>{attentionCount} need attention</div> : null}
          </div>
        ) : null}

        <style>{`
          @keyframes reviewCardEnter {
            from { opacity: 0; transform: scale(0.94) translateY(24px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
          }
          @keyframes reviewFieldFadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    </div>
  );
}

const viewportStyle: CSSProperties = {
  height: "100vh",
  overflowY: "auto",
  overflowX: "hidden",
  background: palette.background,
  WebkitOverflowScrolling: "touch"
};

const screenStyle: CSSProperties = {
  minHeight: "100%",
  maxWidth: 460,
  width: "100%",
  margin: "0 auto",
  position: "relative",
  overflowX: "hidden",
  background: palette.background,
  padding: "0 16px 18px",
  boxSizing: "border-box",
  fontFamily: webSansRegular
};

const loadingScreenStyle: CSSProperties = {
  minHeight: "100vh",
  maxWidth: 460,
  margin: "0 auto",
  background: palette.background,
  padding: 24,
  display: "grid",
  gap: 20,
  boxSizing: "border-box"
};

const overlayStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  pointerEvents: "none"
};

const headerStyle: CSSProperties = {
  paddingTop: 12,
  paddingBottom: 8,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between"
};

const headerButtonStyle: CSSProperties = {
  width: 40,
  height: 40,
  border: "none",
  borderRadius: 20,
  background: "#FFFFFF",
  color: palette.foreground,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  boxShadow: "0 2px 8px rgba(0,0,0,0.06)"
};

const headerTitleStyle: CSSProperties = {
  margin: 0,
  textAlign: "center",
  fontSize: 16,
  lineHeight: "20px",
  fontFamily: webSansSemiBold,
  color: palette.foreground
};

const headerSubtitleStyle: CSSProperties = {
  margin: "2px 0 0",
  textAlign: "center",
  fontSize: 13,
  lineHeight: "18px",
  fontFamily: webSansRegular,
  color: palette.muted
};

const progressRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginTop: 8,
  marginBottom: 12
};

const noticeStyle: CSSProperties = {
  marginBottom: 8,
  borderRadius: 16,
  background: "#FFFFFF",
  color: palette.muted,
  padding: "12px 14px",
  fontFamily: webSansRegular,
  fontSize: 13,
  lineHeight: "18px"
};

const hintRowStyle: CSSProperties = {
  height: 28,
  marginBottom: 4,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  pointerEvents: "none"
};

const hintBadgeStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontFamily: webSansBold,
  fontSize: 13,
  lineHeight: "16px",
  letterSpacing: 1.4,
  color: palette.muted
};

const stackStyle: CSSProperties = {
  position: "relative",
  flex: 1,
  minHeight: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  perspective: "1200px"
};

const nextCardStyle: CSSProperties = {
  position: "absolute",
  top: 0,
  left: "50%",
  width: "100%",
  maxWidth: 420,
  borderRadius: 24,
  background: "#FFFFFF",
  padding: 16,
  pointerEvents: "none",
  boxShadow: "0 6px 20px rgba(0,0,0,0.04)",
  transition: "transform 0.18s ease, opacity 0.18s ease"
};

const nextBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  alignSelf: "flex-start",
  padding: "6px 12px",
  borderRadius: 999,
  background: palette.lavender,
  marginBottom: 12,
  fontSize: 11,
  lineHeight: "14px",
  fontWeight: 700,
  color: "rgba(17, 24, 39, 0.6)",
  letterSpacing: 0.4
};

const cardShellStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  maxWidth: 420,
  transformStyle: "preserve-3d",
  WebkitTransformStyle: "preserve-3d",
  willChange: "transform"
};

const frontFaceStyle: CSSProperties = {
  background: "#FFFFFF",
  borderRadius: 24,
  padding: 16,
  backfaceVisibility: "hidden",
  WebkitBackfaceVisibility: "hidden",
  userSelect: "none",
  touchAction: "pan-y"
};

const backFaceStyle: CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "#FFFFFF",
  borderRadius: 24,
  display: "flex",
  flexDirection: "column",
  transform: "rotateY(180deg)",
  WebkitTransform: "rotateY(180deg)",
  backfaceVisibility: "hidden",
  WebkitBackfaceVisibility: "hidden",
  boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
  overflow: "hidden"
};

const badgeRowStyle: CSSProperties = {
  marginBottom: 12
};

const aiBadgeStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "8px 12px",
  borderRadius: 999,
  background: palette.lavender,
  fontFamily: webSansBold,
  fontSize: 11,
  lineHeight: "14px",
  color: palette.foreground,
  letterSpacing: 0.3
};

const imageShellStyle: CSSProperties = {
  width: "100%",
  aspectRatio: "4 / 5",
  borderRadius: 18,
  overflow: "hidden",
  background: palette.secondary
};

const imageStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block"
};

const frontFieldsStyle: CSSProperties = {
  maxHeight: 200,
  overflowY: "auto",
  paddingBottom: 8
};

const frontFieldRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 0"
};

const frontLabelStyle: CSSProperties = {
  fontFamily: webSansRegular,
  fontSize: 13,
  lineHeight: "18px",
  color: palette.muted
};

const frontValueWrapStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  maxWidth: "55%"
};

const frontValueStyle: CSSProperties = {
  fontFamily: webSansSemiBold,
  fontSize: 14,
  lineHeight: "18px",
  color: palette.foreground,
  textAlign: "right"
};

const backScrollStyle: CSSProperties = {
  flex: 1,
  overflowY: "auto",
  padding: "20px 20px 0"
};

const editHeaderStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  marginBottom: 20
};

const editThumbStyle: CSSProperties = {
  width: 56,
  height: 56,
  borderRadius: 18,
  overflow: "hidden",
  background: palette.secondary,
  flexShrink: 0
};

const editTitleStyle: CSSProperties = {
  margin: 0,
  fontFamily: webSansSemiBold,
  fontSize: 16,
  lineHeight: "20px",
  color: palette.foreground
};

const editSubtitleStyle: CSSProperties = {
  margin: "2px 0 0",
  fontFamily: webSansRegular,
  fontSize: 12,
  lineHeight: "16px",
  color: palette.muted
};

const editSectionsStyle: CSSProperties = {
  display: "grid",
  gap: 18,
  paddingBottom: 120
};

const chipLabelStyle: CSSProperties = {
  display: "block",
  marginBottom: 10,
  fontFamily: webSansBold,
  fontSize: 11,
  lineHeight: "14px",
  color: palette.muted,
  letterSpacing: 1.3,
  textTransform: "uppercase"
};

const chipsWrapStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8
};

const chipButtonStyle: CSSProperties = {
  border: "none",
  borderRadius: 999,
  padding: "10px 14px",
  background: palette.secondary,
  color: palette.foreground,
  fontFamily: webSansSemiBold,
  fontSize: 13,
  lineHeight: "17px",
  cursor: "pointer"
};

const chipButtonActiveStyle: CSSProperties = {
  ...chipButtonStyle,
  background: palette.foreground,
  color: "#FFFFFF"
};

const bottomFadeStyle: CSSProperties = {
  position: "absolute",
  left: 0,
  right: 0,
  bottom: 84,
  height: 40,
  pointerEvents: "none",
  background: "rgba(255,255,255,0.92)"
};

const backFooterStyle: CSSProperties = {
  position: "absolute",
  left: 20,
  right: 20,
  bottom: 20
};

const actionRowStyle: CSSProperties = {
  paddingTop: 16,
  paddingBottom: 18,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 12
};

const buttonInnerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8
};

const secondaryButtonStyle: CSSProperties = {
  height: 52,
  border: "none",
  borderRadius: 999,
  background: "#EEF0F3",
  color: palette.foreground,
  fontFamily: webSansBold,
  padding: "0 28px",
  fontSize: 15,
  lineHeight: "20px",
  cursor: "pointer"
};

const primaryButtonStyle: CSSProperties = {
  minHeight: 52,
  border: "none",
  borderRadius: 999,
  background: palette.foreground,
  color: "#FFFFFF",
  fontFamily: webSansBold,
  padding: "0 28px",
  fontSize: 15,
  lineHeight: "20px",
  cursor: "pointer",
  boxShadow: "0 4px 14px rgba(0,0,0,0.12)"
};

const queueMetaStyle: CSSProperties = {
  paddingBottom: 12,
  textAlign: "center",
  fontFamily: webSansRegular,
  fontSize: 12,
  lineHeight: "16px",
  color: palette.muted
};

export default ReviewDeckScreen;
