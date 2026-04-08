import type { PropsWithChildren } from "react";
import { createContext, useContext, useMemo, useState } from "react";

import type { ClosetItem, OutfitEntry } from "../lib/reference/wardrobe";
import { createSeededOutfits } from "../lib/reference/wardrobe";

type OutfitsContextValue = {
  consumeLogOutfitPhotoUri: () => string | null;
  logOutfitPhotoUri: string | null;
  outfits: Record<string, OutfitEntry>;
  setLogOutfitPhotoUri: (uri: string | null) => void;
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
  const [logOutfitPhotoUri, setLogOutfitPhotoUriState] = useState<string | null>(null);
  const [outfits, setOutfits] = useState<Record<string, OutfitEntry>>(() => createSeededOutfits());

  function setLogOutfitPhotoUri(uri: string | null) {
    setLogOutfitPhotoUriState(uri);
  }

  function consumeLogOutfitPhotoUri() {
    const nextUri = logOutfitPhotoUri;
    setLogOutfitPhotoUriState(null);
    return nextUri;
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
      consumeLogOutfitPhotoUri,
      logOutfitPhotoUri,
      outfits,
      setLogOutfitPhotoUri,
      upsertOutfit
    }),
    [logOutfitPhotoUri, outfits]
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
