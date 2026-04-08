export type ClosetItem = {
  id: number;
  title: string;
  category: string;
  image: string;
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

export const COMPANION_ASSETS = {
  hero: "/companion/hero-fashion.jpg",
  logo: "/companion/tenue_black.png",
  recentLooks: [
    "/companion/recent-look-1.jpg",
    "/companion/recent-look-2.jpg",
    "/companion/recent-look-3.jpg"
  ]
} as const;

export const CLOSET_ITEMS: ClosetItem[] = [
  {
    id: 1,
    title: "Cream Knit Cardigan",
    category: "tops",
    image: "/companion/closet/cream-cardigan.jpg",
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
    image: "/companion/closet/black-trousers.jpg",
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
    image: "/companion/closet/white-shirt.jpg",
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
    image: "/companion/closet/camel-coat.jpg",
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
    image: "/companion/closet/satin-dress.jpg",
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
    image: "/companion/closet/brown-boots.jpg",
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
    image: "/companion/closet/navy-blazer.jpg",
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
    image: "/companion/closet/linen-trousers.jpg",
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
    image: "/companion/closet/silk-cami.jpg",
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
    image: "/companion/closet/denim-jacket.jpg",
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

export const CATEGORY_LABELS: Record<string, string> = {
  tops: "Tops",
  bottoms: "Bottoms",
  dresses: "Dresses",
  outerwear: "Outerwear",
  shoes: "Shoes",
  bags: "Bags",
  accessories: "Accessories"
};

export const DASHBOARD_RECENT_LOOKS = [
  {
    id: 1,
    image: COMPANION_ASSETS.recentLooks[0],
    context: "Coffee with friends",
    date: "Today"
  },
  {
    id: 2,
    image: COMPANION_ASSETS.recentLooks[1],
    context: "Office day",
    date: "Yesterday"
  },
  {
    id: 3,
    image: COMPANION_ASSETS.recentLooks[2],
    context: "Weekend brunch",
    date: "Mar 28"
  }
];

export const LOOKBOOK_ENTRIES = [
  {
    id: 1,
    image: CLOSET_ITEMS[0].image,
    type: "outfit",
    date: "Today",
    context: "Coffee with friends",
    items: 3
  },
  {
    id: 2,
    image: CLOSET_ITEMS[4].image,
    type: "outfit",
    date: "Yesterday",
    context: "Office day",
    items: 4
  },
  {
    id: 3,
    image: CLOSET_ITEMS[2].image,
    type: "inspiration",
    date: "Mar 28",
    context: "Spring mood",
    items: 0
  },
  {
    id: 4,
    image: CLOSET_ITEMS[6].image,
    type: "outfit",
    date: "Mar 25",
    context: "Date night",
    items: 3
  },
  {
    id: 5,
    image: CLOSET_ITEMS[3].image,
    type: "inspiration",
    date: "Mar 22",
    context: "Parisian chic",
    items: 0
  },
  {
    id: 6,
    image: CLOSET_ITEMS[8].image,
    type: "outfit",
    date: "Mar 20",
    context: "Weekend brunch",
    items: 5
  }
] as const;

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
