import { Feather } from "@expo/vector-icons";
import { Image } from "expo-image";
import { router, type Href } from "expo-router";
import { useMemo, useState } from "react";
import {
  Pressable,
  StyleSheet,
  TextInput,
  View
} from "react-native";

import { fontFamilies } from "../theme";
import { AppText } from "../ui";
import { CLOSET_ITEMS } from "../lib/reference/wardrobe";
import { featurePalette, featureShadows } from "../theme/feature";
import {
  Chip,
  FeatureScreen,
  FeatureSwitch,
  SectionHeading,
  SurfaceIconButton
} from "../ui/feature-surfaces";

const SAVED_TABS = ["Products", "Outfits", "Inspiration"] as const;
const STYLE_SIZES = ["XS", "S", "M", "L", "XL", "XXL"] as const;
const FITS = ["Slim", "Regular", "Relaxed", "Oversized"] as const;
const VIBES = [
  "Minimalist",
  "Classic",
  "Streetwear",
  "Bohemian",
  "Editorial",
  "Athleisure",
  "Avant-garde"
] as const;
const BRANDS = ["COS", "Zara", "Uniqlo", "Massimo Dutti", "Arket", "& Other Stories", "Aritzia", "Everlane"] as const;
const OCCASIONS = ["Casual", "Work", "Evening", "Weekend", "Travel", "Active"] as const;
const NOTIFICATION_TOGGLES = [
  {
    id: "daily",
    label: "Daily outfit reminder",
    desc: "A gentle nudge to log your look",
    defaultValue: true
  },
  {
    id: "weekly",
    label: "Weekly style recap",
    desc: "Your wardrobe insights every Sunday",
    defaultValue: true
  },
  {
    id: "suggestions",
    label: "Style suggestions",
    desc: "Personalized outfit ideas",
    defaultValue: false
  },
  {
    id: "updates",
    label: "Product updates",
    desc: "New features and improvements",
    defaultValue: true
  }
] as const;
const PRIVACY_TOGGLES = [
  {
    id: "camera",
    label: "Camera access",
    desc: "Required for outfit logging and try-on",
    defaultValue: true
  },
  {
    id: "photos",
    label: "Photo library",
    desc: "Import items from your gallery",
    defaultValue: true
  },
  {
    id: "analytics",
    label: "Usage analytics",
    desc: "Help us improve the experience",
    defaultValue: false
  },
  {
    id: "recommendations",
    label: "Personalized recommendations",
    desc: "Use your closet data for better styling",
    defaultValue: true
  }
] as const;
const HELP_ITEMS = [
  { icon: "message-circle", label: "Contact us", desc: "Get in touch with our team" },
  { icon: "file-text", label: "Terms of service", desc: "Read our terms" },
  { icon: "file-text", label: "Privacy policy", desc: "How we handle your data" }
] as const;
const FAQ = [
  {
    q: "How does the AI Stylist work?",
    a: "Our AI analyzes your closet and personal style to create outfit recommendations tailored to your wardrobe, body, and preferences."
  },
  {
    q: "Is my wardrobe data private?",
    a: "Absolutely. Your data is encrypted and never shared. You control what's stored and can delete everything at any time."
  },
  {
    q: "How accurate is the try-on?",
    a: "Our try-on uses your body measurements to create a realistic visualization. Results improve as you use the feature more."
  }
] as const;

const SAVED_ITEMS = [
  { id: 1, type: "product", image: CLOSET_ITEMS[0]?.image, title: "Wool Blend Blazer", subtitle: "COS · $175" },
  { id: 2, type: "product", image: CLOSET_ITEMS[3]?.image, title: "Cashmere Sweater", subtitle: "Uniqlo · $89" },
  { id: 3, type: "outfit", image: CLOSET_ITEMS[4]?.image, title: "Date night look", subtitle: "Saved Apr 2" },
  { id: 4, type: "inspiration", image: CLOSET_ITEMS[6]?.image, title: "Parisian street style", subtitle: "Saved Mar 28" }
] as const;

export function EditProfileSettingsScreen() {
  const [name, setName] = useState("Malek");
  const [username, setUsername] = useState("@malek");
  const [bio, setBio] = useState("Fashion enthusiast. Minimal wardrobe, maximum style.");
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => {
      router.back();
    }, 600);
  }

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow
        rightAction={
          <Pressable onPress={handleSave} style={({ pressed }) => [pressed ? styles.pressed : null]}>
            <AppText style={styles.saveButtonLabel}>{saved ? "Saved ✓" : "Save"}</AppText>
          </Pressable>
        }
      />

      <SectionHeading title="Edit profile" />

      <View style={styles.avatarWrap}>
        <Pressable style={({ pressed }) => [styles.avatarButton, pressed ? styles.pressed : null]}>
          <View style={styles.avatarCircle}>
            <Feather color={featurePalette.muted} name="user" size={38} />
          </View>
          <View style={styles.avatarBadge}>
            <Feather color="#FFFFFF" name="camera" size={14} />
          </View>
        </Pressable>
      </View>

      <View style={styles.formStack}>
        <LabeledField label="Display name" multiline={false} value={name} onChangeText={setName} />
        <LabeledField label="Username" multiline={false} value={username} onChangeText={setUsername} />
        <LabeledField label="Bio" multiline value={bio} onChangeText={setBio} />
      </View>
    </FeatureScreen>
  );
}

export function WishlistScreen() {
  const [activeTab, setActiveTab] = useState<(typeof SAVED_TABS)[number]>("Products");

  const filtered = useMemo(() => {
    if (activeTab === "Products") {
      return SAVED_ITEMS.filter((item) => item.type === "product");
    }

    if (activeTab === "Outfits") {
      return SAVED_ITEMS.filter((item) => item.type === "outfit");
    }

    return SAVED_ITEMS.filter((item) => item.type === "inspiration");
  }, [activeTab]);

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow />
      <SectionHeading subtitle="Your wishlist and inspiration" title="Saved" />

      <View style={styles.tabRow}>
        {SAVED_TABS.map((tab) => (
          <Chip key={tab} active={activeTab === tab} label={tab} onPress={() => setActiveTab(tab)} />
        ))}
      </View>

      {filtered.length ? (
        <View style={styles.savedGrid}>
          {filtered.map((item) => (
            <View key={item.id} style={styles.savedTile}>
              <View style={styles.savedImageFrame}>
                {item.image ? <Image contentFit="cover" source={item.image} style={styles.savedImage} /> : null}
                <Pressable style={styles.savedHeart}>
                  <Feather color="#F87171" name="heart" size={14} />
                </Pressable>
              </View>
              <AppText style={styles.savedTitle}>{item.title}</AppText>
              <AppText style={styles.savedSubtitle}>{item.subtitle}</AppText>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.emptyState}>
          <View style={styles.emptyStateIcon}>
            <Feather color={featurePalette.muted} name="heart" size={22} />
          </View>
          <AppText style={styles.emptyStateCopy}>Nothing saved yet</AppText>
        </View>
      )}
    </FeatureScreen>
  );
}

export function StylePreferencesScreen() {
  const [size, setSize] = useState("M");
  const [fit, setFit] = useState("Regular");
  const [vibes, setVibes] = useState<string[]>(["Minimalist", "Classic"]);
  const [brands, setBrands] = useState<string[]>(["COS", "Zara"]);
  const [occasions, setOccasions] = useState<string[]>(["Casual", "Work"]);
  const [budget, setBudget] = useState("$$");
  const [saved, setSaved] = useState(false);

  function toggleList(list: string[], value: string, setter: (next: string[]) => void) {
    setter(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => {
      router.back();
    }, 600);
  }

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow
        rightAction={
          <Pressable onPress={handleSave} style={({ pressed }) => [pressed ? styles.pressed : null]}>
            <AppText style={styles.saveButtonLabel}>{saved ? "Saved ✓" : "Save"}</AppText>
          </Pressable>
        }
      />

      <SectionHeading title="Style profile" />

      <PreferenceSection title="Your size">
        {STYLE_SIZES.map((item) => (
          <Chip key={item} active={size === item} label={item} onPress={() => setSize(item)} />
        ))}
      </PreferenceSection>

      <PreferenceSection title="Preferred fit">
        {FITS.map((item) => (
          <Chip key={item} active={fit === item} label={item} onPress={() => setFit(item)} />
        ))}
      </PreferenceSection>

      <PreferenceSection title="Style vibes">
        {VIBES.map((item) => (
          <Chip
            key={item}
            active={vibes.includes(item)}
            label={item}
            onPress={() => toggleList(vibes, item, setVibes)}
          />
        ))}
      </PreferenceSection>

      <PreferenceSection title="Favorite brands">
        {BRANDS.map((item) => (
          <Chip
            key={item}
            active={brands.includes(item)}
            label={item}
            onPress={() => toggleList(brands, item, setBrands)}
          />
        ))}
      </PreferenceSection>

      <PreferenceSection title="Occasions">
        {OCCASIONS.map((item) => (
          <Chip
            key={item}
            active={occasions.includes(item)}
            label={item}
            onPress={() => toggleList(occasions, item, setOccasions)}
          />
        ))}
      </PreferenceSection>

      <PreferenceSection title="Budget range">
        {["$", "$$", "$$$", "$$$$"].map((item) => (
          <Chip key={item} active={budget === item} label={item} onPress={() => setBudget(item)} />
        ))}
      </PreferenceSection>
    </FeatureScreen>
  );
}

export function NotificationsSettingsScreen() {
  return (
    <ToggleListScreen items={NOTIFICATION_TOGGLES} title="Notifications" />
  );
}

export function PrivacySettingsScreen() {
  return (
    <ToggleListScreen
      items={PRIVACY_TOGGLES}
      subtitle="Control how Tenue uses your data"
      title="Privacy & media"
    />
  );
}

export function AccountSecurityScreen() {
  const [showDelete, setShowDelete] = useState(false);

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow />
      <SectionHeading title="Account & security" />

      <View style={styles.cardStack}>
        <View style={[styles.infoCard, featureShadows.sm]}>
          <View style={styles.infoCardHeader}>
            <Feather color={featurePalette.muted} name="mail" size={18} />
            <AppText style={styles.infoEyebrow}>Email</AppText>
          </View>
          <AppText style={styles.infoValue}>malek@example.com</AppText>
        </View>

        <Pressable style={[styles.actionCard, featureShadows.sm]}>
          <Feather color={featurePalette.muted} name="lock" size={18} />
          <View>
            <AppText style={styles.actionTitle}>Change password</AppText>
            <AppText style={styles.actionSubtitle}>Update your password</AppText>
          </View>
        </Pressable>

        {!showDelete ? (
          <Pressable onPress={() => setShowDelete(true)} style={[styles.actionCard, featureShadows.sm]}>
            <Feather color={featurePalette.danger} name="trash-2" size={18} />
            <View>
              <AppText style={styles.deleteTitle}>Delete account</AppText>
              <AppText style={styles.actionSubtitle}>This action cannot be undone</AppText>
            </View>
          </Pressable>
        ) : (
          <View style={[styles.deleteCard, featureShadows.sm]}>
            <View style={styles.deleteCardHeader}>
              <Feather color={featurePalette.danger} name="alert-triangle" size={18} />
              <AppText style={styles.actionTitle}>Are you sure?</AppText>
            </View>
            <AppText style={styles.actionSubtitle}>
              All your data, closet items, and outfit history will be permanently removed.
            </AppText>
            <View style={styles.dualActions}>
              <PillButton label="Cancel" onPress={() => setShowDelete(false)} variant="secondary" />
              <PillButton label="Delete" onPress={() => router.replace("/welcome" as Href)} variant="danger" />
            </View>
          </View>
        )}
      </View>
    </FeatureScreen>
  );
}

export function HelpSupportScreen() {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow />
      <SectionHeading title="Help & support" />

      <View style={[styles.listCard, featureShadows.sm]}>
        {HELP_ITEMS.map((item, index) => (
          <Pressable
            key={item.label}
            style={[styles.listRow, index < HELP_ITEMS.length - 1 ? styles.rowBorder : null]}
          >
            <Feather color={featurePalette.muted} name={item.icon} size={18} />
            <View style={styles.listRowCopy}>
              <AppText style={styles.listRowTitle}>{item.label}</AppText>
              <AppText style={styles.listRowSubtitle}>{item.desc}</AppText>
            </View>
            <Feather color="rgba(100, 116, 139, 0.5)" name="chevron-right" size={16} />
          </Pressable>
        ))}
      </View>

      <View style={styles.faqSection}>
        <AppText style={styles.preferenceTitle}>Frequently asked</AppText>
        <View style={styles.faqStack}>
          {FAQ.map((item, index) => {
            const open = expanded === index;
            return (
              <Pressable
                key={item.q}
                onPress={() => setExpanded(open ? null : index)}
                style={[styles.faqCard, featureShadows.sm]}
              >
                <View style={styles.faqHeader}>
                  <AppText style={styles.faqQuestion}>{item.q}</AppText>
                  <Feather
                    color="rgba(100, 116, 139, 0.5)"
                    name="chevron-right"
                    size={16}
                    style={open ? styles.faqChevronOpen : undefined}
                  />
                </View>
                {open ? <AppText style={styles.faqAnswer}>{item.a}</AppText> : null}
              </Pressable>
            );
          })}
        </View>
      </View>

      <View style={styles.versionRow}>
        <AppText style={styles.versionLabel}>Tenue v1.0.0</AppText>
      </View>
    </FeatureScreen>
  );
}

function ToggleListScreen({
  items,
  subtitle,
  title
}: {
  items: ReadonlyArray<{ id: string; label: string; desc: string; defaultValue: boolean }>;
  subtitle?: string;
  title: string;
}) {
  const [settings, setSettings] = useState<Record<string, boolean>>(
    Object.fromEntries(items.map((item) => [item.id, item.defaultValue]))
  );

  return (
    <FeatureScreen contentContainerStyle={styles.settingsScreenContent}>
      <HeaderRow />
      <SectionHeading subtitle={subtitle} title={title} />

      <View style={[styles.listCard, featureShadows.sm]}>
        {items.map((item, index) => (
          <View key={item.id} style={[styles.toggleRow, index < items.length - 1 ? styles.rowBorder : null]}>
            <View style={styles.listRowCopy}>
              <AppText style={styles.listRowTitle}>{item.label}</AppText>
              <AppText style={styles.listRowSubtitle}>{item.desc}</AppText>
            </View>
            <FeatureSwitch
              onToggle={() =>
                setSettings((current) => ({
                  ...current,
                  [item.id]: !current[item.id]
                }))
              }
              value={settings[item.id] ?? false}
            />
          </View>
        ))}
      </View>
    </FeatureScreen>
  );
}

function HeaderRow({ rightAction }: { rightAction?: React.ReactNode }) {
  return (
    <View style={styles.headerRow}>
      <SurfaceIconButton
        icon={<Feather color={featurePalette.foreground} name="arrow-left" size={18} />}
        onPress={() => router.back()}
      />
      {rightAction ? <View>{rightAction}</View> : <View style={styles.headerSpacer} />}
    </View>
  );
}

function PreferenceSection({
  children,
  title
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <View style={styles.preferenceSection}>
      <AppText style={styles.preferenceTitle}>{title}</AppText>
      <View style={styles.preferenceWrap}>{children}</View>
    </View>
  );
}

function LabeledField({
  label,
  multiline,
  onChangeText,
  value
}: {
  label: string;
  multiline: boolean;
  onChangeText: (value: string) => void;
  value: string;
}) {
  return (
    <View>
      <AppText style={styles.fieldLabel}>{label}</AppText>
      <TextInput
        multiline={multiline}
        onChangeText={onChangeText}
        style={[styles.fieldInput, multiline ? styles.fieldInputMultiline : null]}
        textAlignVertical={multiline ? "top" : "center"}
        value={value}
      />
    </View>
  );
}

function PillButton({
  label,
  onPress,
  variant
}: {
  label: string;
  onPress: () => void;
  variant: "danger" | "secondary";
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.dualActionButton,
        variant === "danger" ? styles.dualActionDanger : styles.dualActionSecondary,
        pressed ? styles.pressed : null
      ]}
    >
      <AppText style={variant === "danger" ? styles.dualActionDangerLabel : styles.dualActionSecondaryLabel}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  settingsScreenContent: {
    paddingTop: 56,
    paddingHorizontal: 24,
    paddingBottom: 40
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16
  },
  headerSpacer: {
    width: 40
  },
  pressed: {
    opacity: 0.88,
    transform: [{ scale: 0.97 }]
  },
  saveButtonLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  avatarWrap: {
    alignItems: "center",
    marginBottom: 32
  },
  avatarButton: {
    position: "relative"
  },
  avatarCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center"
  },
  avatarBadge: {
    position: "absolute",
    right: -2,
    bottom: -2,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: featurePalette.coral,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4
  },
  formStack: {
    gap: 16
  },
  fieldLabel: {
    marginBottom: 6,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  fieldInput: {
    minHeight: 48,
    borderRadius: 16,
    paddingHorizontal: 16,
    backgroundColor: "#FFFFFF",
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 12,
    elevation: 2
  },
  fieldInputMultiline: {
    minHeight: 110,
    paddingTop: 14,
    paddingBottom: 14
  },
  tabRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 24
  },
  savedGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12
  },
  savedTile: {
    width: "47%"
  },
  savedImageFrame: {
    aspectRatio: 3 / 4,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: featurePalette.secondary,
    marginBottom: 8
  },
  savedImage: {
    width: "100%",
    height: "100%"
  },
  savedHeart: {
    position: "absolute",
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.82)",
    alignItems: "center",
    justifyContent: "center"
  },
  savedTitle: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  savedSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  emptyState: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 48
  },
  emptyStateIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: featurePalette.secondary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16
  },
  emptyStateCopy: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.muted
  },
  preferenceSection: {
    marginBottom: 28
  },
  preferenceTitle: {
    marginBottom: 12,
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  preferenceWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8
  },
  listCard: {
    borderRadius: 24,
    overflow: "hidden",
    backgroundColor: "#FFFFFF"
  },
  listRow: {
    minHeight: 62,
    paddingHorizontal: 20,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  toggleRow: {
    minHeight: 76,
    paddingHorizontal: 20,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  rowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: "rgba(226, 232, 240, 0.7)"
  },
  listRowCopy: {
    flex: 1
  },
  listRowTitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  listRowSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  cardStack: {
    gap: 16
  },
  infoCard: {
    borderRadius: 24,
    padding: 20,
    backgroundColor: "#FFFFFF"
  },
  infoCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 6
  },
  infoEyebrow: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 13,
    lineHeight: 16,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: featurePalette.muted
  },
  infoValue: {
    marginLeft: 30,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  actionCard: {
    borderRadius: 24,
    padding: 20,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    gap: 12
  },
  actionTitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  actionSubtitle: {
    marginTop: 2,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: featurePalette.muted
  },
  deleteTitle: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.danger
  },
  deleteCard: {
    borderRadius: 24,
    padding: 20,
    backgroundColor: "#FFFFFF"
  },
  deleteCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 8
  },
  dualActions: {
    flexDirection: "row",
    gap: 12,
    marginTop: 16
  },
  dualActionButton: {
    flex: 1,
    height: 44,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center"
  },
  dualActionSecondary: {
    backgroundColor: featurePalette.secondary
  },
  dualActionDanger: {
    backgroundColor: featurePalette.danger
  },
  dualActionSecondaryLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: featurePalette.foreground
  },
  dualActionDangerLabel: {
    fontFamily: fontFamilies.sansSemiBold,
    fontSize: 14,
    lineHeight: 18,
    color: "#FFFFFF"
  },
  faqSection: {
    marginTop: 28
  },
  faqStack: {
    gap: 12
  },
  faqCard: {
    borderRadius: 20,
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: "#FFFFFF"
  },
  faqHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12
  },
  faqQuestion: {
    flex: 1,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 15,
    lineHeight: 20,
    color: featurePalette.foreground
  },
  faqChevronOpen: {
    transform: [{ rotate: "90deg" }]
  },
  faqAnswer: {
    marginTop: 12,
    fontFamily: fontFamilies.sansRegular,
    fontSize: 14,
    lineHeight: 22,
    color: featurePalette.muted
  },
  versionRow: {
    marginTop: 40,
    alignItems: "center"
  },
  versionLabel: {
    fontFamily: fontFamilies.sansRegular,
    fontSize: 12,
    lineHeight: 16,
    color: "rgba(100, 116, 139, 0.5)"
  }
});
