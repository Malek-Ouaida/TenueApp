import type { ImageSourcePropType } from "react-native";

import { referenceAssets } from "./assets";

export type ClosetItem = {
  id: number;
  title: string;
  category: string;
  image: ImageSourcePropType;
  tag: string | null;
  type: string;
  color: string;
  material: string;
  season: string;
  occasion: string;
  fit: string;
  brand: string;
  addedDaysAgo: number;
  timesWorn: number;
  lastWornDaysAgo: number | null;
};

export type OutfitEntry = {
  image: ImageSourcePropType | null;
  imageUri?: string | null;
  items: ClosetItem[];
  occasion?: string;
  note?: string;
};

export type PendingReviewField = {
  label: string;
  value: string;
  confidence: "high" | "medium" | "low";
  options: string[];
};

export type PendingReviewItem = {
  id: number;
  title: string;
  image: ImageSourcePropType | null;
  imageUri?: string | null;
  source: string;
  fields: PendingReviewField[];
};

export type LookbookEntry = {
  id: number;
  image: ImageSourcePropType;
  type: "outfit" | "inspiration";
  date: string;
  context: string;
  items: number;
};

export const CATEGORY_LABELS: Record<string, string> = {
  tops: "Tops",
  bottoms: "Bottoms",
  dresses: "Dresses",
  outerwear: "Outerwear",
  shoes: "Shoes",
  bags: "Bags",
  accessories: "Accessories"
};

export const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "tops", label: "Tops" },
  { id: "bottoms", label: "Bottoms" },
  { id: "dresses", label: "Dresses" },
  { id: "outerwear", label: "Outerwear" },
  { id: "shoes", label: "Shoes" },
  { id: "bags", label: "Bags" },
  { id: "accessories", label: "Accessories" }
] as const;

export const CLOSET_ITEMS: ClosetItem[] = [
  {
    id: 1,
    title: "Cream Knit Cardigan",
    category: "tops",
    image: referenceAssets.closet.creamCardigan,
    tag: "Most worn",
    type: "Cardigan",
    color: "Cream",
    material: "Knit",
    season: "Fall / Winter",
    occasion: "Casual",
    fit: "Relaxed",
    brand: "COS",
    addedDaysAgo: 45,
    timesWorn: 18,
    lastWornDaysAgo: 2
  },
  {
    id: 2,
    title: "Black Wide Trousers",
    category: "bottoms",
    image: referenceAssets.closet.blackTrousers,
    tag: null,
    type: "Trousers",
    color: "Black",
    material: "Wool Blend",
    season: "All Season",
    occasion: "Smart Casual",
    fit: "Wide",
    brand: "Zara",
    addedDaysAgo: 30,
    timesWorn: 12,
    lastWornDaysAgo: 5
  },
  {
    id: 3,
    title: "White Oversized Shirt",
    category: "tops",
    image: referenceAssets.closet.whiteShirt,
    tag: "Recently added",
    type: "Shirt",
    color: "White",
    material: "Cotton",
    season: "Spring / Summer",
    occasion: "Versatile",
    fit: "Oversized",
    brand: "Uniqlo",
    addedDaysAgo: 3,
    timesWorn: 1,
    lastWornDaysAgo: 1
  },
  {
    id: 4,
    title: "Camel Wool Coat",
    category: "outerwear",
    image: referenceAssets.closet.camelCoat,
    tag: null,
    type: "Coat",
    color: "Camel",
    material: "Wool",
    season: "Winter",
    occasion: "Formal",
    fit: "Tailored",
    brand: "Max Mara",
    addedDaysAgo: 90,
    timesWorn: 8,
    lastWornDaysAgo: 14
  },
  {
    id: 5,
    title: "Satin Slip Dress",
    category: "dresses",
    image: referenceAssets.closet.satinDress,
    tag: "Ready to style",
    type: "Slip Dress",
    color: "Champagne",
    material: "Satin",
    season: "All Season",
    occasion: "Evening",
    fit: "Slim",
    brand: "& Other Stories",
    addedDaysAgo: 20,
    timesWorn: 3,
    lastWornDaysAgo: 10
  },
  {
    id: 6,
    title: "Brown Leather Boots",
    category: "shoes",
    image: referenceAssets.closet.brownBoots,
    tag: null,
    type: "Boots",
    color: "Brown",
    material: "Leather",
    season: "Fall / Winter",
    occasion: "Everyday",
    fit: "True to Size",
    brand: "Dr. Martens",
    addedDaysAgo: 60,
    timesWorn: 22,
    lastWornDaysAgo: 3
  },
  {
    id: 7,
    title: "Navy Blazer",
    category: "outerwear",
    image: referenceAssets.closet.navyBlazer,
    tag: "Most worn",
    type: "Blazer",
    color: "Navy",
    material: "Wool Blend",
    season: "All Season",
    occasion: "Smart Casual",
    fit: "Tailored",
    brand: "Ralph Lauren",
    addedDaysAgo: 120,
    timesWorn: 30,
    lastWornDaysAgo: 1
  },
  {
    id: 8,
    title: "Linen Trousers",
    category: "bottoms",
    image: referenceAssets.closet.linenTrousers,
    tag: null,
    type: "Trousers",
    color: "Beige",
    material: "Linen",
    season: "Spring / Summer",
    occasion: "Casual",
    fit: "Relaxed",
    brand: "H&M",
    addedDaysAgo: 15,
    timesWorn: 5,
    lastWornDaysAgo: 7
  },
  {
    id: 9,
    title: "Silk Cami",
    category: "tops",
    image: referenceAssets.closet.silkCami,
    tag: null,
    type: "Camisole",
    color: "Ivory",
    material: "Silk",
    season: "Spring / Summer",
    occasion: "Evening",
    fit: "Slim",
    brand: "Massimo Dutti",
    addedDaysAgo: 40,
    timesWorn: 6,
    lastWornDaysAgo: 12
  },
  {
    id: 10,
    title: "Denim Jacket",
    category: "outerwear",
    image: referenceAssets.closet.denimJacket,
    tag: "Last worn 3d ago",
    type: "Jacket",
    color: "Indigo",
    material: "Denim",
    season: "Spring / Fall",
    occasion: "Casual",
    fit: "Regular",
    brand: "Levi's",
    addedDaysAgo: 200,
    timesWorn: 15,
    lastWornDaysAgo: 3
  }
];

export const HOME_RECENT_LOOKS = [
  { id: 1, image: referenceAssets.home.lookDateNight, label: "Date Night", background: "#FFEAF2" },
  { id: 2, image: referenceAssets.home.lookOfficeChic, label: "Office Chic", background: "#DDF1E7" },
  { id: 3, image: referenceAssets.home.lookCasual, label: "Casual Friday", background: "#E8DBFF" },
  { id: 4, image: referenceAssets.home.lookWeekend, label: "Weekend Vibes", background: "#DCEAF7" }
] as const;

export const LOOKBOOK_TABS = ["All", "Favorites", "Inspiration"] as const;

export const LOOKBOOK_ENTRIES: LookbookEntry[] = [
  { id: 1, image: CLOSET_ITEMS[0].image, type: "outfit", date: "Today", context: "Coffee with friends", items: 3 },
  { id: 2, image: CLOSET_ITEMS[4].image, type: "outfit", date: "Yesterday", context: "Office day", items: 4 },
  { id: 3, image: CLOSET_ITEMS[2].image, type: "inspiration", date: "Mar 28", context: "Spring mood", items: 0 },
  { id: 4, image: CLOSET_ITEMS[6].image, type: "outfit", date: "Mar 25", context: "Date night", items: 3 },
  { id: 5, image: CLOSET_ITEMS[3].image, type: "inspiration", date: "Mar 22", context: "Parisian chic", items: 0 },
  { id: 6, image: CLOSET_ITEMS[8].image, type: "outfit", date: "Mar 20", context: "Weekend brunch", items: 5 }
];

export const SORT_OPTIONS = [
  "Newest first",
  "Oldest first",
  "Most worn",
  "Least worn",
  "Recently worn"
] as const;

export const COLOR_FILTERS = [
  "All",
  "Black",
  "White",
  "Cream",
  "Camel",
  "Navy",
  "Brown",
  "Beige",
  "Ivory",
  "Indigo",
  "Champagne"
] as const;

export const SEASON_FILTERS = [
  "All",
  "Spring / Summer",
  "Fall / Winter",
  "All Season"
] as const;

export const OCCASIONS = [
  "Casual",
  "Work",
  "Dinner",
  "University",
  "Travel",
  "Date night",
  "Errands"
] as const;

export const HOME_FTUE_STEPS = [
  {
    title: "Add your first item",
    description: "Snap a photo of something you wear — we'll handle the rest."
  },
  {
    title: "Log your first outfit",
    description: "Capture what you wore today. It only takes a few seconds."
  }
] as const;

export const PENDING_REVIEW_ITEMS: PendingReviewItem[] = [
  {
    id: 1,
    title: "Gray Hoodie",
    image: referenceAssets.closet.grayHoodie,
    source: "AI Scan",
    fields: [
      { label: "Category", value: "Tops", confidence: "high", options: ["Tops", "Outerwear", "Sweaters", "Hoodies", "Activewear", "Loungewear"] },
      { label: "Subcategory", value: "Hoodie", confidence: "high", options: ["Hoodie", "Sweatshirt", "Pullover", "Zip-Up"] },
      { label: "Color", value: "Gray", confidence: "high", options: ["Gray", "Slate", "Silver", "Charcoal", "Light Gray", "Heather"] },
      { label: "Material", value: "Cotton Blend", confidence: "medium", options: ["Cotton Blend", "Fleece", "French Terry", "Polyester", "Organic Cotton"] },
      { label: "Season", value: "Fall / Winter", confidence: "medium", options: ["Spring", "Summer", "Fall", "Winter", "Fall / Winter", "All Season"] },
      { label: "Occasion", value: "Casual", confidence: "high", options: ["Casual", "Athleisure", "Streetwear", "Loungewear", "Travel"] },
      { label: "Fit", value: "Regular", confidence: "medium", options: ["Slim", "Regular", "Oversized", "Relaxed", "Cropped"] },
      { label: "Brand", value: "Unknown", confidence: "low", options: ["Nike", "Zara", "H&M", "Uniqlo", "COS", "Unknown"] }
    ]
  },
  {
    id: 2,
    title: "Blue Sneakers",
    image: referenceAssets.closet.blueSneakers,
    source: "Photo",
    fields: [
      { label: "Category", value: "Shoes", confidence: "high", options: ["Shoes", "Sneakers", "Boots", "Sandals", "Loafers", "Athletic"] },
      { label: "Subcategory", value: "Sneakers", confidence: "high", options: ["Sneakers", "Trainers", "Running Shoes", "High-Tops", "Slip-Ons"] },
      { label: "Color", value: "Blue", confidence: "high", options: ["Blue", "Navy", "Royal Blue", "Cobalt", "Sky Blue", "Teal"] },
      { label: "Material", value: "Mesh & Synthetic", confidence: "low", options: ["Mesh & Synthetic", "Canvas", "Leather", "Knit", "Suede", "Nylon"] },
      { label: "Season", value: "All Season", confidence: "high", options: ["Spring", "Summer", "Fall", "Winter", "All Season"] },
      { label: "Occasion", value: "Casual", confidence: "high", options: ["Casual", "Athletic", "Streetwear", "Travel", "Everyday"] },
      { label: "Fit", value: "True to Size", confidence: "medium", options: ["True to Size", "Runs Small", "Runs Large", "Wide Fit"] },
      { label: "Brand", value: "Unknown", confidence: "low", options: ["Nike", "Adidas", "New Balance", "Puma", "Asics", "Unknown"] }
    ]
  },
  {
    id: 3,
    title: "Striped Shirt",
    image: referenceAssets.closet.stripedShirt,
    source: "Manual",
    fields: [
      { label: "Category", value: "Tops", confidence: "high", options: ["Tops", "Shirts", "Blouses", "T-Shirts", "Polos", "Tunics"] },
      { label: "Subcategory", value: "Button-Down", confidence: "high", options: ["Button-Down", "Oxford", "Dress Shirt", "Casual Shirt", "Flannel", "Linen Shirt"] },
      { label: "Color", value: "Blue & White", confidence: "high", options: ["Blue & White", "Striped Blue", "Light Blue", "Multi", "Navy & White"] },
      { label: "Pattern", value: "Vertical Stripes", confidence: "high", options: ["Vertical Stripes", "Horizontal Stripes", "Pinstripes", "Solid", "Check"] },
      { label: "Material", value: "Cotton", confidence: "medium", options: ["Cotton", "Linen", "Cotton Blend", "Poplin", "Oxford Cloth", "Chambray"] },
      { label: "Season", value: "Spring / Summer", confidence: "medium", options: ["Spring", "Summer", "Fall", "Spring / Summer", "All Season"] },
      { label: "Occasion", value: "Smart Casual", confidence: "high", options: ["Casual", "Smart Casual", "Business", "Formal", "Weekend"] },
      { label: "Fit", value: "Regular", confidence: "medium", options: ["Slim", "Regular", "Oversized", "Relaxed", "Tailored"] },
      { label: "Brand", value: "Unknown", confidence: "low", options: ["Zara", "Ralph Lauren", "COS", "Uniqlo", "J.Crew", "Unknown"] }
    ]
  }
];

export const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
export const WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] as const;
export const MONTHS = [
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
export const MONTHS_SHORT = [
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

export function dateKey(date: Date) {
  return date.toISOString().split("T")[0] ?? "";
}

export function parseDateKey(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month ?? 1) - 1, day ?? 1);
}

export function formatFullDate(date: Date) {
  return `${MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

export function formatDayName(date: Date) {
  return WEEK[date.getDay()];
}

export function formatProfileReviewDate(date: Date) {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric"
  });
}

export function formatDaysAgo(days: number | null) {
  if (days === null) {
    return "Not worn yet";
  }

  if (days === 0) {
    return "Today";
  }

  if (days === 1) {
    return "Yesterday";
  }

  if (days < 7) {
    return `${days} days ago`;
  }

  if (days < 30) {
    return `${Math.floor(days / 7)} weeks ago`;
  }

  return `${Math.floor(days / 30)} months ago`;
}

export function createSeededOutfits() {
  const entries: Record<string, OutfitEntry> = {};
  const now = new Date();

  for (let monthOffset = -3; monthOffset <= 0; monthOffset += 1) {
    const month = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
    const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();

    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = new Date(month.getFullYear(), month.getMonth(), day);
      if (date > now) {
        continue;
      }

      const seed = (date.getFullYear() * 1000 + date.getMonth() * 40 + day) % 100;
      if (seed >= 60) {
        continue;
      }

      const first = CLOSET_ITEMS[seed % CLOSET_ITEMS.length];
      const second = CLOSET_ITEMS[(seed + 3) % CLOSET_ITEMS.length];
      const third = CLOSET_ITEMS[(seed + 7) % CLOSET_ITEMS.length];
      const items = [first, second, third].filter(
        (candidate, index, all) => all.findIndex((item) => item.id === candidate.id) === index
      );

      entries[dateKey(date)] = {
        image: items[0]?.image ?? null,
        items,
        occasion: seed % 3 === 0 ? OCCASIONS[seed % OCCASIONS.length] : undefined,
        note: seed % 5 === 0 ? "Felt great in this" : undefined
      };
    }
  }

  return entries;
}

export function buildTimeline(totalDays = 120) {
  const now = new Date();
  const dates: string[] = [];

  for (let offset = totalDays; offset >= 0; offset -= 1) {
    const date = new Date(now);
    date.setDate(date.getDate() - offset);
    dates.push(dateKey(date));
  }

  return dates;
}

export function getStreak(outfits: Record<string, OutfitEntry>) {
  let streak = 0;
  const cursor = new Date();

  while (true) {
    const key = dateKey(cursor);
    if (!outfits[key]) {
      break;
    }

    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }

  return streak;
}

export function getCategoryCounts() {
  return CLOSET_ITEMS.reduce<Record<string, number>>((counts, item) => {
    counts[item.category] = (counts[item.category] ?? 0) + 1;
    return counts;
  }, {});
}

export function getColorCounts() {
  return CLOSET_ITEMS.reduce<Record<string, number>>((counts, item) => {
    counts[item.color] = (counts[item.color] ?? 0) + 1;
    return counts;
  }, {});
}

export function getBrandCounts() {
  return CLOSET_ITEMS.reduce<Record<string, number>>((counts, item) => {
    counts[item.brand] = (counts[item.brand] ?? 0) + 1;
    return counts;
  }, {});
}

export function getClosetItemById(id: number) {
  return CLOSET_ITEMS.find((item) => item.id === id) ?? null;
}

export function getClosetItemsByIds(ids: number[]) {
  return ids
    .map((id) => getClosetItemById(id))
    .filter((item): item is ClosetItem => item !== null);
}
