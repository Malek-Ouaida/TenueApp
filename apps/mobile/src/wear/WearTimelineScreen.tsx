import { Feather, MaterialCommunityIcons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, useLocalSearchParams, type Href } from "expo-router";
import type { ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useAuth } from "../auth/provider";
import { useInsightOverview } from "../home/overview";
import { humanizeEnum } from "../lib/format";
import { AppText } from "../ui";
import { GlassIconButton, PrimaryActionButton } from "../ui/feature-components";
import { featurePalette, featureShadows, featureTypography } from "../theme/feature";
import { formatLocalDate } from "./dates";
import { useWearCalendar, useWearTimeline } from "./hooks";

function push(href: string) {
  router.push(href as Href);
}

function getCoverUri(log: {
  cover_image?: { url: string } | null;
  primary_cover_image?: { url: string } | null;
}) {
  return log.cover_image?.url ?? log.primary_cover_image?.url ?? null;
}

function formatWearDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric"
  }).format(new Date(`${value}T12:00:00`));
}

function formatWearDayHeading(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "long",
    day: "numeric"
  }).format(new Date(`${value}T12:00:00`));
}

export default function WearTimelineScreen() {
  const params = useLocalSearchParams<{ date?: string | string[] }>();
  const selectedDate = Array.isArray(params.date) ? params.date[0] : params.date;
  const isDayView = Boolean(selectedDate);
  const { session } = useAuth();
  const overview = useInsightOverview(session?.access_token);
  const timeline = useWearTimeline(
    session?.access_token,
    selectedDate ? { wear_date: selectedDate } : {},
    40
  );
  const calendar = useWearCalendar(session?.access_token, 14);
  const todayKey = formatLocalDate(new Date());
  const todayLog = calendar.days.find((day) => day.date === todayKey) ?? null;
  const heading = selectedDate ? formatWearDayHeading(selectedDate) : "Wear History";

  return (
    <ScrollView
      bounces={false}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      style={styles.screen}
    >
      <View style={styles.header}>
        <GlassIconButton
          icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
          onPress={() => router.back()}
        />
        <AppText style={styles.headerTitle}>{heading}</AppText>
        <View style={styles.headerSpacer} />
      </View>

      {isDayView ? (
        <View style={[styles.heroCard, featureShadows.md]}>
          <View style={styles.heroGlowTop} />
          <View style={styles.heroGlowBottom} />
          <View style={styles.heroHeader}>
            <View>
              <AppText style={styles.heroTitle}>All outfits from this day</AppText>
              <AppText style={styles.heroSubtitle}>
                Tenue keeps multiple OOTDs as separate wear logs, not one merged memory.
              </AppText>
            </View>
          </View>

          <PrimaryActionButton
            label="Log another OOTD"
            onPress={() => push("/log-outfit")}
          />
        </View>
      ) : (
        <>
          <View style={[styles.heroCard, featureShadows.md]}>
            <View style={styles.heroGlowTop} />
            <View style={styles.heroGlowBottom} />
            <View style={styles.heroHeader}>
              <View>
                <AppText style={styles.heroTitle}>Your real wear timeline</AppText>
                <AppText style={styles.heroSubtitle}>
                  Logged outfits, current streaks, and the last two weeks at a glance.
                </AppText>
              </View>
              <View style={styles.heroBadge}>
                <MaterialCommunityIcons color="#DE6D39" name="fire" size={16} />
                <AppText style={styles.heroBadgeLabel}>
                  {overview.data?.streaks.current_streak_days ?? 0} day streak
                </AppText>
              </View>
            </View>

            <View style={styles.metricRow}>
              <MetricCard
                icon={<Feather color="#4C6B40" name="calendar" size={16} />}
                label="Wear logs"
                tone="#F0FDF4"
                value={`${overview.data?.all_time.total_wear_logs ?? timeline.items.length}`}
              />
              <MetricCard
                icon={<Feather color="#7658C3" name="layers" size={16} />}
                label="Unique worn"
                tone="rgba(232, 219, 255, 0.35)"
                value={`${overview.data?.all_time.unique_items_worn ?? 0}`}
              />
              <MetricCard
                icon={<Feather color="#577B9A" name="activity" size={16} />}
                label="This month"
                tone="rgba(220, 234, 247, 0.35)"
                value={`${overview.data?.current_month.total_wear_logs ?? 0}`}
              />
            </View>

            <PrimaryActionButton
              label={todayLog?.primary_event_id ? "Open today’s wear log" : "Log today’s outfit"}
              onPress={() => push(todayLog?.primary_event_id ? `/wear/${todayLog.primary_event_id}` : "/log-outfit")}
            />
          </View>

          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <AppText style={styles.sectionTitle}>Last 14 days</AppText>
              <AppText style={styles.sectionMeta}>Tap a day to open it</AppText>
            </View>

            <View style={[styles.calendarCard, featureShadows.sm]}>
              <View style={styles.calendarGrid}>
                {calendar.days.map((day) => {
                  const filled = day.has_wear_log;
                  const isToday = day.date === todayKey;
                  return (
                    <Pressable
                      key={day.date}
                      onPress={() => push(day.primary_event_id ? `/wear/${day.primary_event_id}` : "/log-outfit")}
                      style={[
                        styles.calendarDay,
                        filled ? styles.calendarDayFilled : null,
                        isToday ? styles.calendarDayToday : null
                      ]}
                    >
                      <AppText style={[styles.calendarDayLabel, filled ? styles.calendarDayLabelFilled : null]}>
                        {new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 3)}
                      </AppText>
                      <AppText style={[styles.calendarDayNumber, filled ? styles.calendarDayLabelFilled : null]}>
                        {new Date(`${day.date}T12:00:00`).getDate()}
                      </AppText>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          </View>
        </>
      )}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <AppText style={styles.sectionTitle}>{isDayView ? `${heading} OOTDs` : "Recent wear logs"}</AppText>
          <AppText style={styles.sectionMeta}>
            {timeline.items.length} {timeline.items.length === 1 ? "entry" : "entries"}
          </AppText>
        </View>

        {timeline.error ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>Wear history could not refresh</AppText>
            <AppText style={styles.noticeBody}>{timeline.error}</AppText>
          </View>
        ) : null}

        {timeline.isLoading ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>Loading wear logs</AppText>
            <AppText style={styles.noticeBody}>Fetching your confirmed outfit history.</AppText>
          </View>
        ) : timeline.items.length === 0 ? (
          <View style={styles.noticeCard}>
            <AppText style={styles.noticeTitle}>
              {isDayView ? "No outfits logged on this day" : "No wear logs yet"}
            </AppText>
            <AppText style={styles.noticeBody}>
              {isDayView
                ? "Log one or more OOTDs and Tenue will keep each look separate here."
                : "Start with a closet-based or photo-based wear log and it will appear here."}
            </AppText>
          </View>
        ) : (
          <View style={styles.timelineList}>
            {timeline.items.map((item) => {
              const coverUri = getCoverUri(item);
              return (
                <Pressable
                  key={item.id}
                  onPress={() => push(`/wear/${item.id}`)}
                  style={({ pressed }) => [
                    styles.timelineCard,
                    featureShadows.sm,
                    pressed ? styles.pressed : null
                  ]}
                >
                  <View style={styles.timelineImageFrame}>
                    {coverUri ? (
                      <Image contentFit="cover" source={{ uri: coverUri }} style={styles.timelineImage} />
                    ) : (
                      <View style={styles.timelineImagePlaceholder}>
                        <Feather color={featurePalette.muted} name="camera" size={18} />
                      </View>
                    )}
                  </View>

                  <View style={styles.timelineCopy}>
                    <View style={styles.timelineMetaRow}>
                      <View style={styles.timelinePill}>
                        <AppText style={styles.timelinePillLabel}>{formatWearDate(item.wear_date)}</AppText>
                      </View>
                      <View style={[styles.timelinePill, styles.timelineStatusPill]}>
                        <AppText style={styles.timelineStatusLabel}>{humanizeEnum(item.status)}</AppText>
                      </View>
                    </View>
                    <AppText style={styles.timelineTitle}>
                      {item.outfit_title || item.context
                        ? humanizeEnum(item.outfit_title ?? item.context)
                        : "Wear log"}
                    </AppText>
                    <AppText style={styles.timelineSubtitle}>
                      {item.item_count} items · {item.is_confirmed ? "Confirmed" : humanizeEnum(item.source)}
                    </AppText>
                  </View>

                  <Feather color={featurePalette.muted} name="chevron-right" size={18} />
                </Pressable>
              );
            })}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

function MetricCard({
  icon,
  label,
  tone,
  value
}: {
  icon: ReactNode;
  label: string;
  tone: string;
  value: string;
}) {
  return (
    <View style={[styles.metricCard, { backgroundColor: tone }]}>
      <View style={styles.metricIcon}>{icon}</View>
      <AppText style={styles.metricValue}>{value}</AppText>
      <AppText style={styles.metricLabel}>{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: featurePalette.background
  },
  content: {
    paddingTop: 56,
    paddingHorizontal: 20,
    paddingBottom: 40,
    gap: 24
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  headerTitle: {
    ...featureTypography.title
  },
  headerSpacer: {
    width: 40
  },
  heroCard: {
    borderRadius: 28,
    backgroundColor: "#FFFFFF",
    padding: 20,
    overflow: "hidden",
    gap: 18
  },
  heroGlowTop: {
    position: "absolute",
    top: -50,
    right: -40,
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: "rgba(232, 219, 255, 0.35)"
  },
  heroGlowBottom: {
    position: "absolute",
    bottom: -60,
    left: -50,
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: "rgba(216, 235, 207, 0.28)"
  },
  heroHeader: {
    gap: 12
  },
  heroTitle: {
    ...featureTypography.display,
    fontSize: 28,
    lineHeight: 30
  },
  heroSubtitle: {
    ...featureTypography.body
  },
  heroBadge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderRadius: 999,
    backgroundColor: "rgba(255, 210, 194, 0.35)",
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  heroBadgeLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.foreground
  },
  metricRow: {
    flexDirection: "row",
    gap: 10
  },
  metricCard: {
    flex: 1,
    borderRadius: 18,
    paddingHorizontal: 12,
    paddingVertical: 14,
    gap: 6
  },
  metricIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF"
  },
  metricValue: {
    fontFamily: "Manrope_700Bold",
    fontSize: 18,
    lineHeight: 22,
    color: featurePalette.foreground
  },
  metricLabel: {
    ...featureTypography.label,
    fontSize: 12
  },
  section: {
    gap: 12
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  sectionTitle: {
    ...featureTypography.microUpper
  },
  sectionMeta: {
    ...featureTypography.label,
    fontSize: 12
  },
  calendarCard: {
    borderRadius: 22,
    backgroundColor: "#FFFFFF",
    padding: 16
  },
  calendarGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  calendarDay: {
    width: "13.5%",
    minWidth: 40,
    borderRadius: 14,
    backgroundColor: featurePalette.secondary,
    paddingVertical: 10,
    alignItems: "center",
    justifyContent: "center",
    gap: 2
  },
  calendarDayFilled: {
    backgroundColor: featurePalette.foreground
  },
  calendarDayToday: {
    borderWidth: 1.5,
    borderColor: featurePalette.coral
  },
  calendarDayLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.muted
  },
  calendarDayNumber: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  calendarDayLabelFilled: {
    color: "#FFFFFF"
  },
  noticeCard: {
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 14
  },
  noticeTitle: {
    fontFamily: "Manrope_700Bold",
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.darkText,
    marginBottom: 4
  },
  noticeBody: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  },
  timelineList: {
    gap: 12
  },
  timelineCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    borderRadius: 20,
    backgroundColor: "#FFFFFF",
    padding: 12
  },
  timelineImageFrame: {
    width: 76,
    height: 96,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary
  },
  timelineImage: {
    width: "100%",
    height: "100%"
  },
  timelineImagePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center"
  },
  timelineCopy: {
    flex: 1,
    gap: 8
  },
  timelineMetaRow: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap"
  },
  timelinePill: {
    borderRadius: 999,
    backgroundColor: featurePalette.secondary,
    paddingHorizontal: 10,
    paddingVertical: 4
  },
  timelineStatusPill: {
    backgroundColor: "rgba(255, 210, 194, 0.35)"
  },
  timelinePillLabel: {
    fontFamily: "Manrope_600SemiBold",
    fontSize: 11,
    lineHeight: 14,
    color: featurePalette.foreground
  },
  timelineStatusLabel: {
    fontFamily: "Manrope_700Bold",
    fontSize: 11,
    lineHeight: 14,
    color: "#A34E1C"
  },
  timelineTitle: {
    ...featureTypography.bodyStrong
  },
  timelineSubtitle: {
    ...featureTypography.label,
    fontSize: 13,
    lineHeight: 18
  },
  pressed: {
    transform: [{ scale: 0.99 }]
  }
});
