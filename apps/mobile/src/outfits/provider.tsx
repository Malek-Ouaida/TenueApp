import type { PropsWithChildren } from "react";
import { createContext, useContext, useMemo, useState } from "react";
import type { ImagePickerAsset } from "expo-image-picker";

import type { ClosetItem, OutfitEntry } from "../lib/reference/wardrobe";
import { createSeededOutfits } from "../lib/reference/wardrobe";

type OutfitsContextValue = {
  consumeLogOutfitPhotoAsset: () => ImagePickerAsset | null;
  logOutfitPhotoAsset: ImagePickerAsset | null;
  outfits: Record<string, OutfitEntry>;
  setLogOutfitPhotoAsset: (asset: ImagePickerAsset | null) => void;
  upsertOutfit: (
    date: string,
    next: {
      image?: OutfitEntry["image"];
      imageUri?: string | null;
      items: ClosetItem[];
      note?: string;
      occasion?: string;
    }
  ) => void;
};

const OutfitsContext = createContext<OutfitsContextValue | null>(null);

export function OutfitsProvider({ children }: PropsWithChildren) {
  const [logOutfitPhotoAsset, setLogOutfitPhotoAssetState] = useState<ImagePickerAsset | null>(null);
  const [outfits, setOutfits] = useState<Record<string, OutfitEntry>>(() => createSeededOutfits());

  function setLogOutfitPhotoAsset(asset: ImagePickerAsset | null) {
    setLogOutfitPhotoAssetState(asset);
  }

  function consumeLogOutfitPhotoAsset() {
    const nextAsset = logOutfitPhotoAsset;
    setLogOutfitPhotoAssetState(null);
    return nextAsset;
  }

  function upsertOutfit(
    date: string,
    next: {
      image?: OutfitEntry["image"];
      imageUri?: string | null;
      items: ClosetItem[];
      note?: string;
      occasion?: string;
    }
  ) {
    setOutfits((current) => ({
      ...current,
      [date]: {
        image: next.image ?? current[date]?.image ?? null,
        imageUri: next.imageUri ?? current[date]?.imageUri ?? null,
        items: next.items,
        note: next.note,
        occasion: next.occasion
      }
    }));
  }

  const value = useMemo<OutfitsContextValue>(
    () => ({
      consumeLogOutfitPhotoAsset,
      logOutfitPhotoAsset,
      outfits,
      setLogOutfitPhotoAsset,
      upsertOutfit
    }),
    [logOutfitPhotoAsset, outfits]
  );

  return <OutfitsContext.Provider value={value}>{children}</OutfitsContext.Provider>;
}

export function useOutfits() {
  const value = useContext(OutfitsContext);

  if (!value) {
    throw new Error("useOutfits must be used within OutfitsProvider");
  }

  return value;
}
