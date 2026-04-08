import aiStylistPreview from "../../assets/home/ai-stylist-preview.jpg";
import lookCasual from "../../assets/home/look-casual.jpg";
import lookDateNight from "../../assets/home/look-date-night.jpg";
import lookOfficeChic from "../../assets/home/look-office-chic.jpg";
import lookWeekend from "../../assets/home/look-weekend.jpg";

export { aiStylistPreview };

export const homeFtueSteps = [
  {
    title: "Add your first item",
    description: "Snap a photo of something you wear. Tenue will route it through review before it becomes closet truth."
  },
  {
    title: "Log your first outfit",
    description: "Capture what you wore today so the lookbook and styling flows can build on real history."
  }
] as const;

export type HomeRecentLook = {
  id: string;
  image: number;
  label: string;
  background: string;
};

export const homeRecentLooks: HomeRecentLook[] = [
  {
    id: "date-night",
    image: lookDateNight,
    label: "Date Night",
    background: "#FFEAF2"
  },
  {
    id: "office-chic",
    image: lookOfficeChic,
    label: "Office Chic",
    background: "#DDF1E7"
  },
  {
    id: "casual-friday",
    image: lookCasual,
    label: "Casual Friday",
    background: "#E8DBFF"
  },
  {
    id: "weekend-vibes",
    image: lookWeekend,
    label: "Weekend Vibes",
    background: "#DCEAF7"
  }
];
