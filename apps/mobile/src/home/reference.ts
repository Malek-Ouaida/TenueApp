import aiStylistPreview from "../../assets/home/ai-stylist-preview.jpg";
import lookCasual from "../../assets/home/look-casual.jpg";
import lookDateNight from "../../assets/home/look-date-night.jpg";
import lookOfficeChic from "../../assets/home/look-office-chic.jpg";
import lookWeekend from "../../assets/home/look-weekend.jpg";

export { aiStylistPreview };

export type HomeRecentLook = {
  id: string;
  image: number;
  label: string;
  tint: string;
};

export const homeRecentLooks: HomeRecentLook[] = [
  {
    id: "date-night",
    image: lookDateNight,
    label: "Date Night",
    tint: "#FFEAF2"
  },
  {
    id: "office-chic",
    image: lookOfficeChic,
    label: "Office Chic",
    tint: "#DDF1E7"
  },
  {
    id: "casual-friday",
    image: lookCasual,
    label: "Casual Friday",
    tint: "#E8DBFF"
  },
  {
    id: "weekend-vibes",
    image: lookWeekend,
    label: "Weekend Vibes",
    tint: "#DCEAF7"
  }
];
