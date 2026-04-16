import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { router, useFocusEffect, type Href } from "expo-router";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "../../../src/auth/provider";
import { useClosetInsights, useClosetItemUsageIndex } from "../../../src/closet/insights";
import { useInsightOverview } from "../../../src/home/overview";
import { useProfile } from "../../../src/profile/hooks";
import {
  buildProfileDescriptor,
  buildProfileDisplayName,
  buildProfileInitials
} from "../../../src/profile/selectors";
import { fontFamilies } from "../../../src/theme";
import { featurePalette, featureShadows, featureTypography } from "../../../src/theme/feature";
import { AppText, ModalSheet, Screen, SkeletonBlock } from "../../../src/ui";
import { formatLocalDate } from "../../../src/wear/dates";
import { useWearCalendarRange } from "../../../src/wear/hooks";

type ProfileViewMode = "calendar" | "timeline";

type ProfileCalendarCell =
  | {
      dateKey: string;
      dayNumber: number;
      eventCount: number;
      hasWearLog: boolean;
      imageUrl: string | null;
      isFuture: boolean;
      isToday: boolean;
      primaryEventId: string | null;
    }
  | null;

type ProfileTimelineEntry = {
  dateKey: string;
  eventCount: number;
  id: string;
  imageUrl: string | null;
  itemCount: number;
  title: string;
  wornAt: string;
};

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December"
] as const;
const MONTH_SHORT_NAMES = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec"
] as const;

function startOfMonth(date: Date) {
  const next = new Date(date);
  next.setDate(1);
  next.setHours(12, 0, 0, 0);
  return next;
}

function endOfMonth(date: Date) {
  const next = new Date(date.getFullYear(), date.getMonth() + 1, 0, 12, 0, 0, 0);
  return next;
}

function shiftMonth(date: Date, delta: number) {
  return startOfMonth(new Date(date.getFullYear(), date.getMonth() + delta, 1, 12, 0, 0, 0));
}

function isSameMonth(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth();
}

function chunkIntoWeeks<T>(items: T[], size = 7) {
  const chunks: T[][] = [];

  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }

  return chunks;
}

function buildMonthCells(
  monthDate: Date,
  days: Array<{
    date: string;
    event_count: number;
    events: Array<{
      id: string;
      item_count: number;
      worn_at: string;
      cover_image: { url: string } | null;
      title: string | null;
      context: string | null;
    }>;
    primary_event_id: string | null;
    primary_cover_image: { url: string } | null;
    has_wear_log: boolean;
  }>,
  todayKey: string
) {
  const start = startOfMonth(monthDate);
  const totalDays = endOfMonth(monthDate).getDate();
  const cells: ProfileCalendarCell[] = [];
  const dayMap = new Map(days.map((day) => [day.date, day]));
  const monthStartDay = start.getDay();
  const now = new Date();
  now.setHours(12, 0, 0, 0);

  for (let index = 0; index < monthStartDay; index += 1) {
    cells.push(null);
  }

  for (let dayNumber = 1; dayNumber <= totalDays; dayNumber += 1) {
    const date = new Date(monthDate.getFullYear(), monthDate.getMonth(), dayNumber, 12, 0, 0, 0);
    const dateKey = formatLocalDate(date);
    const snapshot = dayMap.get(dateKey) ?? null;

    cells.push({
      dateKey,
      dayNumber,
      eventCount: snapshot?.event_count ?? 0,
      hasWearLog: Boolean(snapshot?.has_wear_log && snapshot.primary_event_id),
      imageUrl: snapshot?.primary_cover_image?.url ?? null,
      isFuture: date.getTime() > now.getTime(),
      isToday: dateKey === todayKey,
      primaryEventId: snapshot?.primary_event_id ?? null
    });
  }

  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  return chunkIntoWeeks(cells, 7);
}

function formatMonthHeading(date: Date) {
  return `${MONTH_NAMES[date.getMonth()]} ${date.getFullYear()}`;
}

function buildMostWornLabel(item: { title: string | null; wear_count: number } | null) {
  if (!item || item.wear_count <= 0) {
    return "—";
  }

  const title = item.title?.trim();
  if (!title) {
    return `${item.wear_count} wears`;
  }

  return title.split(/\s+/).slice(0, 2).join(" ");
}

function formatTimelineLabel(dateKey: string) {
  const date = new Date(`${dateKey}T12:00:00`);
  return {
    dayName: DAY_LABELS[date.getDay()],
    monthDay: `${MONTH_SHORT_NAMES[date.getMonth()]} ${date.getDate()}`
  };
}

function profileDayHref(cell: Exclude<ProfileCalendarCell, null>): Href {
  if (!cell.hasWearLog || !cell.primaryEventId) {
    return "/log-outfit" as Href;
  }

  if (cell.eventCount > 1) {
    return ({
      pathname: "/wear",
      params: { date: cell.dateKey }
    } as unknown) as Href;
  }

  return `/wear/${cell.primaryEventId}` as Href;
}

function push(href: string | Href) {
  router.push(href as Href);
}

export default function ProfileScreen() {
  const { logoutCurrentUser, session, user } = useAuth();
  const profile = useProfile({
    accessToken: session?.access_token,
    onUnauthorized: async () => {
      await logoutCurrentUser();
      router.replace("/login");
    }
  });
  const overview = useInsightOverview(session?.access_token);
  const closetInsights = useClosetInsights(session?.access_token);
  const usageIndex = useClosetItemUsageIndex(session?.access_token);
  const [viewMode, setViewMode] = useState<ProfileViewMode>("calendar");
  const [showStats, setShowStats] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => startOfMonth(new Date()));

  const monthStart = formatLocalDate(startOfMonth(visibleMonth));
  const monthEnd = formatLocalDate(endOfMonth(visibleMonth));
  const monthCalendar = useWearCalendarRange(session?.access_token, {
    startDate: monthStart,
    endDate: monthEnd
  });

  useFocusEffect(
    useCallback(() => {
      void monthCalendar.refresh();
    }, [monthCalendar.refresh])
  );

  const todayKey = formatLocalDate(new Date());
  const monthWeeks = useMemo(
    () => buildMonthCells(visibleMonth, monthCalendar.days, todayKey),
    [monthCalendar.days, todayKey, visibleMonth]
  );
  const timelineEntries = useMemo<ProfileTimelineEntry[]>(
    () =>
      monthCalendar.days
        .flatMap((day) =>
          day.events.map((event) => ({
            dateKey: day.date,
            eventCount: day.event_count,
            id: event.id,
            imageUrl: event.cover_image?.url ?? day.primary_cover_image?.url ?? null,
            itemCount: event.item_count,
            title: event.title ?? event.context ?? day.outfit_title ?? "Outfit logged",
            wornAt: event.worn_at
          }))
        )
        .sort((left, right) => right.wornAt.localeCompare(left.wornAt)),
    [monthCalendar.days]
  );
  const displayTitle = buildProfileDisplayName(profile.profile, user?.email);
  const initials = buildProfileInitials(displayTitle);
  const descriptor = buildProfileDescriptor(profile.profile, closetInsights.insights);
  const totalOutfits = overview.data?.all_time.total_wear_logs ?? timelineEntries.length;
  const streak = overview.data?.streaks.current_streak_days ?? 0;
  const mostWornLabel = buildMostWornLabel(usageIndex.snapshot.items[0] ?? null);
  const isCurrentMonth = isSameMonth(visibleMonth, new Date());
  const hasMonthEntries = timelineEntries.length > 0;
  const shouldShowHeroSkeleton =
    !profile.profile &&
    profile.isLoading &&
    overview.isLoading &&
    closetInsights.isLoading &&
    usageIndex.isLoading;
  const statusMessages = [
    profile.error,
    overview.error,
    closetInsights.error,
    usageIndex.error
  ].filter((value): value is string => Boolean(value));

  return (
    <>
      <Screen backgroundColor={featurePalette.background} contentContainerStyle={styles.content} padded={false}>
        <View style={styles.page}>
          {shouldShowHeroSkeleton ? (
            <>
              <SkeletonBlock height={84} />
              <SkeletonBlock height={96} />
              <SkeletonBlock height={540} />
            </>
          ) : (
            <>
              <View style={styles.header}>
                <View style={styles.headerIdentity}>
                  <LinearGradient
                    colors={[featurePalette.lavender, featurePalette.blush]}
                    end={{ x: 1, y: 1 }}
                    start={{ x: 0, y: 0 }}
                    style={styles.avatarShell}
                  >
                    <AppText style={styles.avatarLabel}>{initials}</AppText>
                  </LinearGradient>

                  <View style={styles.headerCopy}>
                    <AppText style={styles.headerTitle}>{displayTitle}</AppText>
                    <AppText style={styles.headerSubtitle}>Your style story</AppText>
                  </View>
                </View>

                <Pressable
                  onPress={() => push("/settings")}
                  style={({ pressed }) => [styles.settingsButton, pressed ? styles.pressed : null]}
                >
                  <Feather color={featurePalette.warmGray} name="settings" size={18} />
                </Pressable>
              </View>

              <Pressable
                onPress={() => setShowStats(true)}
                style={({ pressed }) => [styles.statsRow, pressed ? styles.pressedWide : null]}
              >
                <ProfileStat
                  color="sage"
                  icon={<MaterialCommunityIcons color="#4C6B40" name="hanger" size={16} />}
                  label="Logged"
                  value={`${totalOutfits}`}
                />
                <ProfileStat
                  color="coral"
                  icon={<MaterialCommunityIcons color="#DE6D39" name="fire" size={16} />}
                  label="Streak"
                  value={`${streak}d`}
                />
                <ProfileStat
                  color="butter"
                  icon={<MaterialCommunityIcons color="#B88900" name="crown-outline" size={16} />}
                  label="Most worn"
                  value={mostWornLabel}
                />
                <Feather color="rgba(100, 116, 139, 0.5)" name="chevron-right" size={18} />
              </Pressable>

              <View style={styles.monthSection}>
                <View style={styles.monthHeader}>
                  <Pressable
                    onPress={() => setVisibleMonth((current) => shiftMonth(current, -1))}
                    style={({ pressed }) => [styles.monthArrow, pressed ? styles.pressed : null]}
                  >
                    <Feather color={featurePalette.foreground} name="chevron-left" size={18} />
                  </Pressable>

                  <View style={styles.monthHeaderCenter}>
                    <AppText style={styles.monthHeading}>{formatMonthHeading(visibleMonth)}</AppText>
                    <View style={styles.viewToggle}>
                      <Pressable
                        onPress={() => setViewMode("calendar")}
                        style={[
                          styles.viewToggleButton,
                          viewMode === "calendar" ? styles.viewToggleButtonActive : null
                        ]}
                      >
                        <Feather
                          color={viewMode === "calendar" ? featurePalette.foreground : featurePalette.muted}
                          name="calendar"
                          size={15}
                        />
                      </Pressable>
                      <Pressable
                        onPress={() => setViewMode("timeline")}
                        style={[
                          styles.viewToggleButton,
                          viewMode === "timeline" ? styles.viewToggleButtonActive : null
                        ]}
                      >
                        <Feather
                          color={viewMode === "timeline" ? featurePalette.foreground : featurePalette.muted}
                          name="list"
                          size={15}
                        />
                      </Pressable>
                    </View>
                  </View>

                  <Pressable
                    disabled={isCurrentMonth}
                    onPress={() => setVisibleMonth((current) => shiftMonth(current, 1))}
                    style={({ pressed }) => [
                      styles.monthArrow,
                      isCurrentMonth ? styles.monthArrowDisabled : null,
                      pressed && !isCurrentMonth ? styles.pressed : null
                    ]}
                  >
                    <Feather color={featurePalette.foreground} name="chevron-right" size={18} />
                  </Pressable>
                </View>

                <AppText style={styles.monthDescriptor}>
                  Tap a logged day to open it. Days with multiple OOTDs open that day&apos;s list.
                </AppText>

                {monthCalendar.error ? (
                  <View style={[styles.noticeCard, featureShadows.sm]}>
                    <AppText style={styles.noticeTitle}>Calendar unavailable</AppText>
                    <AppText style={styles.noticeBody}>{monthCalendar.error}</AppText>
                  </View>
                ) : monthCalendar.isLoading && monthCalendar.days.length === 0 ? (
                  <View style={styles.loadingStack}>
                    <SkeletonBlock height={18} />
                    <SkeletonBlock height={356} />
                  </View>
                ) : viewMode === "calendar" ? (
                  <View style={styles.calendarPanel}>
                    <View style={styles.calendarWeekdays}>
                      {DAY_LABELS.map((label) => (
                        <AppText key={label} style={styles.calendarWeekdayLabel}>
                          {label}
                        </AppText>
                      ))}
                    </View>

                    <View style={styles.calendarWeeks}>
                      {monthWeeks.map((week, weekIndex) => (
                        <View key={`week-${weekIndex}`} style={styles.calendarWeekRow}>
                          {week.map((cell, dayIndex) =>
                            cell ? (
                              <Pressable
                                key={cell.dateKey}
                                disabled={cell.isFuture}
                                onPress={() => push(profileDayHref(cell))}
                                style={({ pressed }) => [
                                  styles.calendarDay,
                                  cell.hasWearLog ? styles.calendarDayFilled : null,
                                  cell.isToday ? styles.calendarDayToday : null,
                                  cell.isFuture ? styles.calendarDayFuture : null,
                                  pressed && !cell.isFuture ? styles.pressed : null
                                ]}
                              >
                                {cell.imageUrl ? (
                                  <Image contentFit="cover" source={{ uri: cell.imageUrl }} style={styles.calendarImage} />
                                ) : null}
                                {cell.imageUrl ? <View style={styles.calendarImageOverlay} /> : null}
                                <AppText
                                  style={[
                                    styles.calendarDayNumber,
                                    cell.hasWearLog ? styles.calendarDayNumberFilled : null
                                  ]}
                                >
                                  {cell.dayNumber}
                                </AppText>
                                {cell.eventCount > 1 ? (
                                  <View style={styles.calendarEventBadge}>
                                    <AppText style={styles.calendarEventBadgeLabel}>
                                      +{cell.eventCount - 1}
                                    </AppText>
                                  </View>
                                ) : null}
                              </Pressable>
                            ) : (
                              <View key={`spacer-${weekIndex}-${dayIndex}`} style={styles.calendarSpacer} />
                            )
                          )}
                        </View>
                      ))}
                    </View>
                  </View>
                ) : hasMonthEntries ? (
                  <View style={styles.timelineList}>
                    {timelineEntries.map((entry, index) => {
                      const label = formatTimelineLabel(entry.dateKey);
                      return (
                        <Pressable
                          key={entry.id}
                          onPress={() => push(`/wear/${entry.id}`)}
                          style={({ pressed }) => [
                            styles.timelineCard,
                            featureShadows.sm,
                            pressed ? styles.pressedWide : null,
                            index === timelineEntries.length - 1 ? styles.timelineCardLast : null
                          ]}
                        >
                          <View style={styles.timelineDateColumn}>
                            <AppText style={styles.timelineDayName}>{label.dayName}</AppText>
                            <AppText style={styles.timelineDayNumber}>
                              {new Date(`${entry.dateKey}T12:00:00`).getDate()}
                            </AppText>
                          </View>

                          <View style={styles.timelineDivider} />

                          <View style={styles.timelineImageFrame}>
                            {entry.imageUrl ? (
                              <Image contentFit="cover" source={{ uri: entry.imageUrl }} style={styles.timelineImage} />
                            ) : (
                              <View style={styles.timelineImageFallback}>
                                <Feather color={featurePalette.muted} name="camera" size={18} />
                              </View>
                            )}
                          </View>

                          <View style={styles.timelineCopy}>
                            <AppText numberOfLines={1} style={styles.timelineTitle}>
                              {label.monthDay}
                            </AppText>
                            <AppText style={styles.timelineMeta}>Outfit logged</AppText>
                            <AppText numberOfLines={2} style={styles.timelineNote}>
                              {entry.title} · {entry.itemCount} items
                              {entry.eventCount > 1 ? ` · ${entry.eventCount} looks that day` : ""}
                            </AppText>
                          </View>

                          <Feather color="#CBD5E1" name="chevron-right" size={18} />
                        </Pressable>
                      );
                    })}
                  </View>
                ) : (
                  <View style={[styles.emptyCard, featureShadows.sm]}>
                    <View style={styles.emptyIcon}>
                      <Feather color={featurePalette.muted} name="calendar" size={20} />
                    </View>
                    <AppText style={styles.emptyTitle}>No outfits this month</AppText>
                    <AppText style={styles.emptyCopy}>
                      Start logging from the calendar and your month view will build here.
                    </AppText>
                    <Pressable
                      onPress={() => push("/log-outfit")}
                      style={({ pressed }) => [styles.emptyAction, pressed ? styles.pressed : null]}
                    >
                      <AppText style={styles.emptyActionLabel}>Log today’s outfit</AppText>
                    </Pressable>
                  </View>
                )}
              </View>

              <View style={styles.identityCard}>
                <AppText style={styles.identityEyebrow}>Profile</AppText>
                <AppText style={styles.identityDescriptor}>{descriptor}</AppText>
                <Pressable
                  onPress={() => push("/settings/edit-profile")}
                  style={({ pressed }) => [styles.identityAction, pressed ? styles.pressed : null]}
                >
                  <AppText style={styles.identityActionLabel}>Edit profile</AppText>
                </Pressable>
              </View>

              {statusMessages.map((message) => (
                <View key={message} style={[styles.noticeCard, featureShadows.sm]}>
                  <AppText style={styles.noticeTitle}>Data refresh issue</AppText>
                  <AppText style={styles.noticeBody}>{message}</AppText>
                </View>
              ))}
            </>
          )}
        </View>
      </Screen>

      <ModalSheet
        footer={
          <Pressable
            onPress={() => {
              setShowStats(false);
              push("/stats");
            }}
            style={({ pressed }) => [styles.modalAction, pressed ? styles.pressed : null]}
          >
            <AppText style={styles.modalActionLabel}>See All Stats</AppText>
            <Feather color="#FFFFFF" name="chevron-right" size={16} />
          </Pressable>
        }
        onClose={() => setShowStats(false)}
        visible={showStats}
      >
        <View style={styles.modalHeader}>
          <AppText style={styles.modalTitle}>Your Stats</AppText>
          <AppText style={styles.modalSubtitle}>Quick overview</AppText>
        </View>

        <ModalStatCard
          color="sage"
          icon={<MaterialCommunityIcons color="#4C6B40" name="hanger" size={18} />}
          label="Outfits logged"
          value={`${totalOutfits}`}
        />
        <ModalStatCard
          color="coral"
          icon={<MaterialCommunityIcons color="#DE6D39" name="fire" size={18} />}
          label="Current streak"
          value={`${streak} days`}
        />
        <ModalStatCard
          color="butter"
          icon={<MaterialCommunityIcons color="#B88900" name="crown-outline" size={18} />}
          label="Most worn"
          value={mostWornLabel}
        />
      </ModalSheet>
    </>
  );
}

function ProfileStat({
  color,
  icon,
  label,
  value
}: {
  color: "butter" | "coral" | "sage";
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.statBlock}>
      <View
        style={[
          styles.statIcon,
          color === "sage"
            ? styles.statIconSage
            : color === "coral"
              ? styles.statIconCoral
              : styles.statIconButter
        ]}
      >
        {icon}
      </View>
      <View style={styles.statCopy}>
        <AppText style={styles.statLabel}>{label}</AppText>
        <AppText numberOfLines={1} style={styles.statValue}>
          {value}
        </AppText>
      </View>
    </View>
  );
}

function ModalStatCard({
  color,
  icon,
  label,
  value
}: {
  color: "butter" | "coral" | "sage";
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <View
      style={[
        styles.modalStatCard,
        color === "sage"
          ? styles.modalStatSage
          : color === "coral"
            ? styles.modalStatCoral
            : styles.modalStatButter
      ]}
    >
      <View style={styles.modalStatIcon}>{icon}</View>
      <View style={styles.modalStatCopy}>
        <AppText style={styles.modalStatLabel}>{label}</AppText>
        <AppText numberOfLines={1} style={styles.modalStatValue}>
          {value}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingBottom: 132
  },
  page: {
    paddingHorizontal: 24,
    paddingTop: 18,
    gap: 22
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerIdentity: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14
  },
  avatarShell: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center"
  },
  avatarLabel: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 19,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  headerCopy: {
    gap: 2
  },
  headerTitle: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 26,
    color: featurePalette.foreground
  },
  headerSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  settingsButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  statBlock: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 10
  },
  statIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center"
  },
  statIconSage: {
    backgroundColor: "rgba(216, 235, 207, 0.9)"
  },
  statIconCoral: {
    backgroundColor: "rgba(255, 210, 194, 0.45)"
  },
  statIconButter: {
    backgroundColor: "rgba(255, 239, 161, 0.48)"
  },
  statCopy: {
    flex: 1,
    gap: 2
  },
  statLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 10,
    lineHeight: 12,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  statValue: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  monthSection: {
    gap: 12
  },
  monthHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  monthHeaderCenter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  monthHeading: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  monthArrow: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  monthArrowDisabled: {
    opacity: 0.3
  },
  viewToggle: {
    flexDirection: "row",
    borderRadius: 999,
    backgroundColor: "#F1F0EE",
    padding: 2
  },
  viewToggleButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: "center",
    justifyContent: "center"
  },
  viewToggleButtonActive: {
    backgroundColor: "#FFFFFF"
  },
  monthDescriptor: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  loadingStack: {
    gap: 12
  },
  calendarPanel: {
    gap: 10
  },
  calendarWeekdays: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 2
  },
  calendarWeekdayLabel: {
    flex: 1,
    textAlign: "center",
    fontFamily: fontFamilies.serifMediumItalic,
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.muted
  },
  calendarWeeks: {
    gap: 6
  },
  calendarWeekRow: {
    flexDirection: "row",
    gap: 6
  },
  calendarDay: {
    flex: 1,
    aspectRatio: 0.74,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    justifyContent: "flex-start",
    paddingHorizontal: 6,
    paddingVertical: 4
  },
  calendarDayFilled: {
    backgroundColor: featurePalette.foreground
  },
  calendarDayToday: {
    borderWidth: 2,
    borderColor: featurePalette.coral
  },
  calendarDayFuture: {
    opacity: 0.28
  },
  calendarImage: {
    ...StyleSheet.absoluteFillObject
  },
  calendarImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15, 23, 42, 0.18)"
  },
  calendarDayNumber: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 10,
    lineHeight: 12,
    color: featurePalette.muted
  },
  calendarDayNumberFilled: {
    color: "#FFFFFF"
  },
  calendarEventBadge: {
    marginTop: "auto",
    alignSelf: "flex-start",
    borderRadius: 999,
    backgroundColor: "rgba(255, 255, 255, 0.18)",
    paddingHorizontal: 6,
    paddingVertical: 3
  },
  calendarEventBadgeLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 10,
    lineHeight: 12,
    color: "#FFFFFF"
  },
  calendarSpacer: {
    flex: 1,
    aspectRatio: 0.74
  },
  timelineList: {
    gap: 12
  },
  timelineCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    padding: 14
  },
  timelineCardLast: {
    marginBottom: 4
  },
  timelineDateColumn: {
    width: 40,
    alignItems: "center",
    justifyContent: "center"
  },
  timelineDayName: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.muted,
    textTransform: "uppercase"
  },
  timelineDayNumber: {
    fontFamily: fontFamilies.serifSemiBold,
    fontSize: 22,
    lineHeight: 24,
    color: featurePalette.foreground
  },
  timelineDivider: {
    width: 2,
    alignSelf: "stretch",
    borderRadius: 999,
    backgroundColor: "#F1F0EE"
  },
  timelineImageFrame: {
    width: 64,
    height: 80,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  timelineImage: {
    width: "100%",
    height: "100%"
  },
  timelineImageFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  timelineCopy: {
    flex: 1,
    gap: 2
  },
  timelineTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  timelineMeta: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  timelineNote: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.warmGray
  },
  emptyCard: {
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    padding: 20,
    alignItems: "flex-start",
    gap: 10
  },
  emptyIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: featurePalette.secondary
  },
  emptyTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  emptyCopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 20,
    color: featurePalette.warmGray
  },
  emptyAction: {
    height: 40,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: featurePalette.foreground,
    alignItems: "center",
    justifyContent: "center"
  },
  emptyActionLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 13,
    lineHeight: 16,
    color: "#FFFFFF"
  },
  identityCard: {
    borderRadius: 22,
    backgroundColor: "#FFFFFF",
    padding: 20,
    gap: 10
  },
  identityEyebrow: {
    ...featureTypography.microUpper
  },
  identityDescriptor: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  identityAction: {
    alignSelf: "flex-start",
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  identityActionLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  noticeCard: {
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  noticeTitle: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  noticeBody: {
    marginTop: 4,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.warmGray
  },
  modalHeader: {
    gap: 2
  },
  modalTitle: {
    ...featureTypography.title,
    fontSize: 22,
    lineHeight: 26
  },
  modalSubtitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 13,
    lineHeight: 18,
    color: featurePalette.muted
  },
  modalStatCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderRadius: 18,
    padding: 16
  },
  modalStatSage: {
    backgroundColor: "rgba(216, 235, 207, 0.6)"
  },
  modalStatCoral: {
    backgroundColor: "rgba(255, 234, 242, 0.74)"
  },
  modalStatButter: {
    backgroundColor: "rgba(255, 239, 161, 0.45)"
  },
  modalStatIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.55)"
  },
  modalStatCopy: {
    flex: 1,
    gap: 2
  },
  modalStatLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    textTransform: "uppercase",
    color: featurePalette.warmGray
  },
  modalStatValue: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 17,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  modalAction: {
    height: 48,
    borderRadius: 18,
    backgroundColor: featurePalette.foreground,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  modalActionLabel: {
    fontFamily: fontFamilies.sansBold,
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  pressed: {
    transform: [{ scale: 0.96 }]
  },
  pressedWide: {
    transform: [{ scale: 0.98 }]
  }
});
