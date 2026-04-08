/* eslint-disable @typescript-eslint/no-require-imports */
import type { ImageSourcePropType } from "react-native";

export const referenceAssets = {
  home: {
    lookCasual: require("../../assets/home/look-casual.jpg"),
    lookDateNight: require("../../assets/home/look-date-night.jpg"),
    lookOfficeChic: require("../../assets/home/look-office-chic.jpg"),
    lookWeekend: require("../../assets/home/look-weekend.jpg")
  },
  closet: {
    blackTrousers: require("../../assets/closet/mock/black-trousers.jpg"),
    blueSneakers: require("../../assets/closet/mock/blue-sneakers.jpg"),
    brownBoots: require("../../assets/closet/mock/brown-boots.jpg"),
    camelCoat: require("../../assets/closet/mock/camel-coat.jpg"),
    creamCardigan: require("../../assets/closet/mock/cream-cardigan.jpg"),
    denimJacket: require("../../assets/closet/mock/denim-jacket.jpg"),
    grayHoodie: require("../../assets/closet/mock/gray-hoodie.jpg"),
    linenTrousers: require("../../assets/closet/mock/linen-trousers.jpg"),
    navyBlazer: require("../../assets/closet/mock/navy-blazer.jpg"),
    satinDress: require("../../assets/closet/mock/satin-dress.jpg"),
    silkCami: require("../../assets/closet/mock/silk-cami.jpg"),
    stripedShirt: require("../../assets/closet/mock/striped-shirt.jpg"),
    whiteShirt: require("../../assets/closet/mock/white-shirt.jpg")
  }
} as const satisfies Record<string, ImageSourcePropType | Record<string, ImageSourcePropType>>;
