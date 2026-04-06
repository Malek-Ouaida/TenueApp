import { useFonts } from "expo-font";
import {
  Manrope_500Medium,
  Manrope_600SemiBold,
  Manrope_700Bold
} from "@expo-google-fonts/manrope";
import {
  Newsreader_500Medium,
  Newsreader_600SemiBold,
  Newsreader_700Bold
} from "@expo-google-fonts/newsreader";

export function useAppFonts() {
  return useFonts({
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Newsreader_500Medium,
    Newsreader_600SemiBold,
    Newsreader_700Bold
  });
}
