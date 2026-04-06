import { File } from "expo-file-system";
import * as ImagePicker from "expo-image-picker";

import type { ClosetDraftSnapshot } from "./types";
import {
  completeClosetUpload,
  createClosetDraft,
  createClosetUploadIntent
} from "./client";

const allowedMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxUploadSizeBytes = 15 * 1024 * 1024;

export type UploadIdempotencyPath = {
  logical_key: string;
  draft_key: string;
  complete_key: string;
  draft_id?: string;
};

export type PreparedUploadAsset = {
  file: File;
  uri: string;
  filename: string;
  file_size: number;
  mime_type: string;
  sha256: string;
};

type NativeCryptoHost = {
  randomUUID?: () => string;
  subtle?: {
    digest: (algorithm: string, data: BufferSource) => Promise<ArrayBuffer>;
  };
};

const sha256Constants = [
  0x428a2f98,
  0x71374491,
  0xb5c0fbcf,
  0xe9b5dba5,
  0x3956c25b,
  0x59f111f1,
  0x923f82a4,
  0xab1c5ed5,
  0xd807aa98,
  0x12835b01,
  0x243185be,
  0x550c7dc3,
  0x72be5d74,
  0x80deb1fe,
  0x9bdc06a7,
  0xc19bf174,
  0xe49b69c1,
  0xefbe4786,
  0x0fc19dc6,
  0x240ca1cc,
  0x2de92c6f,
  0x4a7484aa,
  0x5cb0a9dc,
  0x76f988da,
  0x983e5152,
  0xa831c66d,
  0xb00327c8,
  0xbf597fc7,
  0xc6e00bf3,
  0xd5a79147,
  0x06ca6351,
  0x14292967,
  0x27b70a85,
  0x2e1b2138,
  0x4d2c6dfc,
  0x53380d13,
  0x650a7354,
  0x766a0abb,
  0x81c2c92e,
  0x92722c85,
  0xa2bfe8a1,
  0xa81a664b,
  0xc24b8b70,
  0xc76c51a3,
  0xd192e819,
  0xd6990624,
  0xf40e3585,
  0x106aa070,
  0x19a4c116,
  0x1e376c08,
  0x2748774c,
  0x34b0bcb5,
  0x391c0cb3,
  0x4ed8aa4a,
  0x5b9cca4f,
  0x682e6ff3,
  0x748f82ee,
  0x78a5636f,
  0x84c87814,
  0x8cc70208,
  0x90befffa,
  0xa4506ceb,
  0xbef9a3f7,
  0xc67178f2
] as const;

function getNativeCryptoHost(): NativeCryptoHost | null {
  const cryptoHost = (globalThis as typeof globalThis & { crypto?: NativeCryptoHost }).crypto;
  if (!cryptoHost) {
    return null;
  }

  return cryptoHost;
}

function manualUuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    const value = character === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function generateUuid() {
  return getNativeCryptoHost()?.randomUUID?.() ?? manualUuid();
}

export function createUploadIdempotencyPath(logicalKey?: string): UploadIdempotencyPath {
  return {
    logical_key: logicalKey ?? generateUuid(),
    draft_key: generateUuid(),
    complete_key: generateUuid()
  };
}

export function buildLogicalRetryKey(asset: ImagePicker.ImagePickerAsset) {
  return [asset.assetId, asset.fileName, asset.fileSize, asset.uri].filter(Boolean).join(":");
}

function inferMimeType(asset: ImagePicker.ImagePickerAsset, filename: string) {
  const candidate = asset.mimeType?.toLowerCase();
  if (candidate && allowedMimeTypes.has(candidate)) {
    return candidate;
  }

  const extension = filename.split(".").pop()?.toLowerCase();
  if (extension === "jpg" || extension === "jpeg") {
    return "image/jpeg";
  }
  if (extension === "png") {
    return "image/png";
  }
  if (extension === "webp") {
    return "image/webp";
  }

  return null;
}

async function hashFileSha256(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const nativeDigest = await getNativeCryptoHost()?.subtle?.digest("SHA-256", bytes);

  return Array.from(new Uint8Array(nativeDigest ?? sha256ArrayBuffer(bytes)))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function rightRotate(value: number, amount: number) {
  return (value >>> amount) | (value << (32 - amount));
}

function addUnsigned(...values: number[]) {
  return values.reduce((sum, value) => (sum + value) >>> 0, 0);
}

function sha256ArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const words: number[] = [];
  const bitLength = bytes.length * 8;

  for (let index = 0; index < bytes.length; index += 1) {
    words[index >> 2] = (words[index >> 2] ?? 0) | (bytes[index] << (24 - (index % 4) * 8));
  }

  words[bytes.length >> 2] = (words[bytes.length >> 2] ?? 0) | (0x80 << (24 - (bytes.length % 4) * 8));
  words[(((bytes.length + 8) >> 6) + 1) * 16 - 2] = Math.floor(bitLength / 0x100000000);
  words[(((bytes.length + 8) >> 6) + 1) * 16 - 1] = bitLength >>> 0;

  const hash = [
    0x6a09e667,
    0xbb67ae85,
    0x3c6ef372,
    0xa54ff53a,
    0x510e527f,
    0x9b05688c,
    0x1f83d9ab,
    0x5be0cd19
  ];

  const messageSchedule = new Array<number>(64);

  for (let chunkIndex = 0; chunkIndex < words.length; chunkIndex += 16) {
    for (let scheduleIndex = 0; scheduleIndex < 16; scheduleIndex += 1) {
      messageSchedule[scheduleIndex] = words[chunkIndex + scheduleIndex] ?? 0;
    }

    for (let scheduleIndex = 16; scheduleIndex < 64; scheduleIndex += 1) {
      const s0 =
        rightRotate(messageSchedule[scheduleIndex - 15], 7) ^
        rightRotate(messageSchedule[scheduleIndex - 15], 18) ^
        (messageSchedule[scheduleIndex - 15] >>> 3);
      const s1 =
        rightRotate(messageSchedule[scheduleIndex - 2], 17) ^
        rightRotate(messageSchedule[scheduleIndex - 2], 19) ^
        (messageSchedule[scheduleIndex - 2] >>> 10);

      messageSchedule[scheduleIndex] = addUnsigned(
        messageSchedule[scheduleIndex - 16],
        s0,
        messageSchedule[scheduleIndex - 7],
        s1
      );
    }

    let [a, b, c, d, e, f, g, h] = hash;

    for (let round = 0; round < 64; round += 1) {
      const s1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = addUnsigned(h, s1, choice, sha256Constants[round], messageSchedule[round]);
      const s0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = addUnsigned(s0, majority);

      h = g;
      g = f;
      f = e;
      e = addUnsigned(d, temp1);
      d = c;
      c = b;
      b = a;
      a = addUnsigned(temp1, temp2);
    }

    hash[0] = addUnsigned(hash[0], a);
    hash[1] = addUnsigned(hash[1], b);
    hash[2] = addUnsigned(hash[2], c);
    hash[3] = addUnsigned(hash[3], d);
    hash[4] = addUnsigned(hash[4], e);
    hash[5] = addUnsigned(hash[5], f);
    hash[6] = addUnsigned(hash[6], g);
    hash[7] = addUnsigned(hash[7], h);
  }

  const result = new Uint8Array(32);
  for (let index = 0; index < hash.length; index += 1) {
    result[index * 4] = (hash[index] >>> 24) & 0xff;
    result[index * 4 + 1] = (hash[index] >>> 16) & 0xff;
    result[index * 4 + 2] = (hash[index] >>> 8) & 0xff;
    result[index * 4 + 3] = hash[index] & 0xff;
  }

  return result.buffer;
}

export async function prepareUploadAsset(asset: ImagePicker.ImagePickerAsset): Promise<PreparedUploadAsset> {
  const file = new File(asset.uri);
  const filename = asset.fileName?.trim() || file.name || `closet-item-${Date.now()}.jpg`;
  const mimeType = inferMimeType(asset, filename);

  if (!mimeType) {
    throw new Error("Only JPEG, PNG, and WEBP images are supported.");
  }

  const fileSize = asset.fileSize ?? file.size;
  if (!fileSize) {
    throw new Error("The selected image could not be read.");
  }

  if (fileSize > maxUploadSizeBytes) {
    throw new Error("The selected image exceeds the 15 MB mobile upload limit.");
  }

  return {
    file,
    uri: asset.uri,
    filename,
    file_size: fileSize,
    mime_type: mimeType,
    sha256: await hashFileSha256(file)
  };
}

export async function uploadFileToPresignedUrl(
  preparedAsset: PreparedUploadAsset,
  descriptor: { method: string; url: string; headers: Record<string, string> }
) {
  const response = await fetch(descriptor.url, {
    method: descriptor.method,
    headers: descriptor.headers,
    body: preparedAsset.file
  });

  if (!response.ok) {
    throw new Error("Image upload failed before Tenue could process it.");
  }
}

export async function selectSingleImage(source: "camera" | "library") {
  if (source === "camera") {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      throw new Error("Camera access is required to capture a closet item.");
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 1
    });
    return result.canceled ? null : result.assets[0] ?? null;
  }

  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    throw new Error("Photo Library access is required to choose a closet item image.");
  }

  const result = await ImagePicker.launchImageLibraryAsync({
    allowsEditing: false,
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 1,
    selectionLimit: 1
  });
  return result.canceled ? null : result.assets[0] ?? null;
}

export async function uploadClosetAsset(params: {
  accessToken: string;
  asset: ImagePicker.ImagePickerAsset;
  path: UploadIdempotencyPath;
  title?: string | null;
  onStageChange?: (stage: string) => void;
}): Promise<{ draft: ClosetDraftSnapshot; path: UploadIdempotencyPath; prepared: PreparedUploadAsset }> {
  params.onStageChange?.("Preparing image");
  const prepared = await prepareUploadAsset(params.asset);
  const nextPath = { ...params.path };

  if (!nextPath.draft_id) {
    params.onStageChange?.("Creating draft");
    const draft = await createClosetDraft(params.accessToken, params.title ?? null, nextPath.draft_key);
    nextPath.draft_id = draft.id;
  }

  params.onStageChange?.("Requesting upload");
  const uploadIntent = await createClosetUploadIntent(
    params.accessToken,
    nextPath.draft_id,
    {
      filename: prepared.filename,
      mime_type: prepared.mime_type,
      file_size: prepared.file_size,
      sha256: prepared.sha256
    }
  );

  params.onStageChange?.("Uploading image");
  await uploadFileToPresignedUrl(prepared, uploadIntent.upload);

  params.onStageChange?.("Completing upload");
  const completedDraft = await completeClosetUpload(
    params.accessToken,
    nextPath.draft_id,
    uploadIntent.upload_intent_id,
    nextPath.complete_key
  );

  return {
    draft: completedDraft,
    path: nextPath,
    prepared
  };
}
