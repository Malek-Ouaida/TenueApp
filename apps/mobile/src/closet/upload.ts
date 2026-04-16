import {
  EncodingType,
  getInfoAsync,
  readAsStringAsync,
  uploadAsync
} from "expo-file-system/legacy";
import * as ImagePicker from "expo-image-picker";
import { Platform } from "react-native";

import type { ClosetDraftSnapshot } from "./types";
import {
  completeConfirmedClosetItemUpload,
  completeClosetUpload,
  createConfirmedClosetItemUploadIntent,
  createClosetDraft,
  createClosetUploadIntent,
  getClosetExtractionSnapshot,
  getClosetProcessingSnapshot
} from "./client";

const allowedMimeTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxUploadSizeBytes = 15 * 1024 * 1024;
const processingPendingStatuses = new Set(["pending", "running"]);
const batchProcessingPollIntervalMs = 1500;
const batchProcessingTimeoutMs = 3 * 60 * 1000;

export type UploadIdempotencyPath = {
  logical_key: string;
  draft_key: string;
  complete_key: string;
  draft_id?: string;
};

export type PreparedUploadAsset = {
  uri: string;
  filename: string;
  file_size: number;
  mime_type: string;
  sha256: string;
  web_upload_body?: Uint8Array;
};

export type ClosetBatchUploadSnapshot = {
  completedCount: number;
  currentIndex: number | null;
  error: string | null;
  isRunning: boolean;
  queuedCount: number;
  stage: string | null;
  totalCount: number;
};

type ClosetBatchUploadListener = (snapshot: ClosetBatchUploadSnapshot) => void;

type QueuedClosetAsset = {
  accessToken: string;
  asset: ImagePicker.ImagePickerAsset;
  title?: string | null;
};

type NativeCryptoHost = {
  randomUUID?: () => string;
  subtle?: {
    digest: (algorithm: string, data: BufferSource) => Promise<ArrayBuffer>;
  };
};

const idleClosetBatchUploadSnapshot: ClosetBatchUploadSnapshot = {
  completedCount: 0,
  currentIndex: null,
  error: null,
  isRunning: false,
  queuedCount: 0,
  stage: null,
  totalCount: 0
};

const closetBatchUploadListeners = new Set<ClosetBatchUploadListener>();
const queuedClosetAssets: QueuedClosetAsset[] = [];
let closetBatchUploadSnapshot = { ...idleClosetBatchUploadSnapshot };
let queuedClosetAssetDrain: Promise<void> | null = null;

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

function inferFilenameFromUri(uri: string) {
  const sanitized = uri.split("?")[0]?.split("#")[0] ?? "";
  const rawName = sanitized.split("/").pop()?.trim() ?? "";

  if (!rawName) {
    return null;
  }

  try {
    return decodeURIComponent(rawName);
  } catch {
    return rawName;
  }
}

function decodeBase64(base64: string) {
  const normalized = base64.replace(/\s+/g, "");
  if (!normalized) {
    return new Uint8Array(0);
  }

  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const lookup = new Int16Array(256).fill(-1);
  for (let index = 0; index < alphabet.length; index += 1) {
    lookup[alphabet.charCodeAt(index)] = index;
  }
  lookup["=".charCodeAt(0)] = 0;

  const padding = normalized.endsWith("==") ? 2 : normalized.endsWith("=") ? 1 : 0;
  const outputLength = Math.floor((normalized.length * 3) / 4) - padding;
  const output = new Uint8Array(outputLength);

  let outputOffset = 0;
  for (let index = 0; index < normalized.length; index += 4) {
    const char0 = normalized.charCodeAt(index);
    const char1 = normalized.charCodeAt(index + 1);
    const char2 = normalized.charCodeAt(index + 2);
    const char3 = normalized.charCodeAt(index + 3);

    const value0 = lookup[char0] ?? -1;
    const value1 = lookup[char1] ?? -1;
    const value2 = lookup[char2] ?? -1;
    const value3 = lookup[char3] ?? -1;

    if (value0 < 0 || value1 < 0 || value2 < 0 || value3 < 0) {
      throw new Error("The selected image could not be decoded.");
    }

    const combined = (value0 << 18) | (value1 << 12) | (value2 << 6) | value3;

    output[outputOffset] = (combined >> 16) & 0xff;
    outputOffset += 1;

    if (normalized[index + 2] !== "=" && outputOffset < output.length) {
      output[outputOffset] = (combined >> 8) & 0xff;
      outputOffset += 1;
    }

    if (normalized[index + 3] !== "=" && outputOffset < output.length) {
      output[outputOffset] = combined & 0xff;
      outputOffset += 1;
    }
  }

  return output;
}

async function readAssetBytes(uri: string) {
  const base64 = await readAsStringAsync(uri, { encoding: EncodingType.Base64 });
  return decodeBase64(base64);
}

async function readWebAssetData(asset: ImagePicker.ImagePickerAsset) {
  const file = asset.file;
  if (file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    return {
      bytes,
      fileSize: asset.fileSize ?? file.size
    };
  }

  const response = await fetch(asset.uri);
  if (!response.ok) {
    throw new Error("The selected image could not be read.");
  }

  const bytes = new Uint8Array(await response.arrayBuffer());
  return {
    bytes,
    fileSize: asset.fileSize ?? bytes.byteLength
  };
}

async function hashBytesSha256(bytes: Uint8Array) {
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
  if (!asset.uri) {
    throw new Error("The selected image is missing a readable file path.");
  }

  const filename =
    asset.fileName?.trim() || inferFilenameFromUri(asset.uri) || `closet-item-${Date.now()}.jpg`;
  const mimeType = inferMimeType(asset, filename);

  if (!mimeType) {
    throw new Error("Only JPEG, PNG, and WEBP images are supported.");
  }

  if (Platform.OS === "web") {
    const { bytes, fileSize } = await readWebAssetData(asset);

    if (!fileSize) {
      throw new Error("The selected image could not be read.");
    }

    if (fileSize > maxUploadSizeBytes) {
      throw new Error("The selected image exceeds the 15 MB mobile upload limit.");
    }

    return {
      uri: asset.uri,
      filename,
      file_size: fileSize,
      mime_type: mimeType,
      sha256: await hashBytesSha256(bytes),
      web_upload_body: bytes
    };
  }

  const fileInfo = await getInfoAsync(asset.uri);
  if (!fileInfo.exists || fileInfo.isDirectory) {
    throw new Error("The selected image could not be read.");
  }

  const fileSize = asset.fileSize ?? fileInfo.size;
  if (!fileSize) {
    throw new Error("The selected image could not be read.");
  }

  if (fileSize > maxUploadSizeBytes) {
    throw new Error("The selected image exceeds the 15 MB mobile upload limit.");
  }

  const bytes = await readAssetBytes(asset.uri);

  return {
    uri: asset.uri,
    filename,
    file_size: fileSize,
    mime_type: mimeType,
    sha256: await hashBytesSha256(bytes)
  };
}

export async function uploadFileToPresignedUrl(
  preparedAsset: PreparedUploadAsset,
  descriptor: { method: string; url: string; headers: Record<string, string> }
) {
  const method = descriptor.method.toUpperCase();
  if (method !== "POST" && method !== "PUT" && method !== "PATCH") {
    throw new Error("Tenue returned an unsupported upload method.");
  }

  if (Platform.OS === "web") {
    const response = await fetch(descriptor.url, {
      method,
      headers: descriptor.headers,
      body: preparedAsset.web_upload_body
    });

    if (!response.ok) {
      throw new Error("Image upload failed before Tenue could process it.");
    }

    return;
  }

  const response = await uploadAsync(descriptor.url, preparedAsset.uri, {
    headers: descriptor.headers,
    httpMethod: method
  });

  if (response.status < 200 || response.status >= 300) {
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

export async function selectImagesFromLibrary(options?: {
  multiple?: boolean;
  selectionLimit?: number;
}) {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    throw new Error("Photo Library access is required to choose a closet item image.");
  }

  const multiple = options?.multiple ?? false;
  const result = await ImagePicker.launchImageLibraryAsync({
    allowsEditing: false,
    allowsMultipleSelection: multiple,
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 1,
    selectionLimit: multiple ? (options?.selectionLimit ?? 10) : 1
  });

  return result.canceled ? [] : result.assets;
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

export async function uploadClosetAssets(params: {
  accessToken: string;
  assets: ImagePicker.ImagePickerAsset[];
  onStageChange?: (stage: string, progress: { index: number; total: number }) => void;
  title?: string | null;
}) {
  const drafts: ClosetDraftSnapshot[] = [];

  for (const [index, asset] of params.assets.entries()) {
    const total = params.assets.length;
    const progress = { index: index + 1, total };
    const logicalKey = buildLogicalRetryKey(asset);

    const result = await uploadClosetAsset({
      accessToken: params.accessToken,
      asset,
      path: createUploadIdempotencyPath(logicalKey),
      title: params.title,
      onStageChange: (stage) => {
        params.onStageChange?.(stage, progress);
      }
    });

    drafts.push(result.draft);
  }

  return drafts;
}

function cloneClosetBatchUploadSnapshot() {
  return { ...closetBatchUploadSnapshot };
}

function emitClosetBatchUploadSnapshot() {
  const nextSnapshot = cloneClosetBatchUploadSnapshot();
  for (const listener of closetBatchUploadListeners) {
    listener(nextSnapshot);
  }
}

function updateClosetBatchUploadSnapshot(
  updater: (current: ClosetBatchUploadSnapshot) => ClosetBatchUploadSnapshot
) {
  closetBatchUploadSnapshot = updater(closetBatchUploadSnapshot);
  emitClosetBatchUploadSnapshot();
}

function formatBatchStage(stage: string, currentIndex: number, totalCount: number) {
  return `${stage} (${currentIndex}/${totalCount})`;
}

function sleep(delayMs: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}

function isClosetItemPipelineActive(params: {
  extraction: Awaited<ReturnType<typeof getClosetExtractionSnapshot>> | null;
  processing: Awaited<ReturnType<typeof getClosetProcessingSnapshot>>;
}) {
  if (
    params.processing.lifecycle_status === "processing" ||
    processingPendingStatuses.has(params.processing.processing_status)
  ) {
    return true;
  }

  if (!params.extraction) {
    return false;
  }

  return (
    processingPendingStatuses.has(params.extraction.extraction_status) ||
    processingPendingStatuses.has(params.extraction.normalization_status)
  );
}

async function waitForClosetItemPipelineToSettle(params: {
  accessToken: string;
  currentIndex: number;
  itemId: string;
}) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < batchProcessingTimeoutMs) {
    updateClosetBatchUploadSnapshot((current) => ({
      ...current,
      currentIndex: params.currentIndex,
      isRunning: true,
      queuedCount: queuedClosetAssets.length,
      stage: formatBatchStage("Processing image", params.currentIndex, current.totalCount)
    }));

    const [processing, extraction] = await Promise.all([
      getClosetProcessingSnapshot(params.accessToken, params.itemId),
      getClosetExtractionSnapshot(params.accessToken, params.itemId).catch(() => null)
    ]);

    if (!isClosetItemPipelineActive({ extraction, processing })) {
      return;
    }

    await sleep(batchProcessingPollIntervalMs);
  }

  throw new Error(
    "Tenue paused the queue because one photo is taking too long to finish processing."
  );
}

async function drainQueuedClosetAssets() {
  try {
    while (queuedClosetAssets.length > 0) {
      const queuedAsset = queuedClosetAssets.shift();
      if (!queuedAsset) {
        continue;
      }

      const currentIndex = closetBatchUploadSnapshot.completedCount + 1;

      updateClosetBatchUploadSnapshot((current) => ({
        ...current,
        currentIndex,
        error: null,
        isRunning: true,
        queuedCount: queuedClosetAssets.length
      }));

      const result = await uploadClosetAsset({
        accessToken: queuedAsset.accessToken,
        asset: queuedAsset.asset,
        path: createUploadIdempotencyPath(buildLogicalRetryKey(queuedAsset.asset)),
        title: queuedAsset.title,
        onStageChange: (stage) => {
          updateClosetBatchUploadSnapshot((current) => ({
            ...current,
            currentIndex,
            isRunning: true,
            queuedCount: queuedClosetAssets.length,
            stage: formatBatchStage(stage, currentIndex, current.totalCount)
          }));
        }
      });

      await waitForClosetItemPipelineToSettle({
        accessToken: queuedAsset.accessToken,
        currentIndex,
        itemId: result.draft.id
      });

      updateClosetBatchUploadSnapshot((current) => {
        const completedCount = current.completedCount + 1;
        const hasMoreQueuedAssets = queuedClosetAssets.length > 0;

        return hasMoreQueuedAssets
          ? {
              ...current,
              completedCount,
              currentIndex: completedCount + 1,
              isRunning: true,
              queuedCount: queuedClosetAssets.length,
              stage: formatBatchStage("Starting next photo", completedCount + 1, current.totalCount)
            }
          : { ...idleClosetBatchUploadSnapshot };
      });
    }
  } catch (error) {
    queuedClosetAssets.length = 0;
    updateClosetBatchUploadSnapshot((current) => ({
      ...current,
      currentIndex: null,
      error: error instanceof Error ? error.message : "Upload failed.",
      isRunning: false,
      queuedCount: 0,
      stage: null
    }));
  } finally {
    queuedClosetAssetDrain = null;
    if (queuedClosetAssets.length > 0) {
      queuedClosetAssetDrain = drainQueuedClosetAssets();
    }
  }
}

export function getClosetBatchUploadSnapshot() {
  return cloneClosetBatchUploadSnapshot();
}

export function subscribeToClosetBatchUpload(listener: ClosetBatchUploadListener) {
  closetBatchUploadListeners.add(listener);
  listener(getClosetBatchUploadSnapshot());

  return () => {
    closetBatchUploadListeners.delete(listener);
  };
}

export function queueClosetAssetsForUpload(params: {
  accessToken: string;
  assets: ImagePicker.ImagePickerAsset[];
  title?: string | null;
}) {
  if (!params.assets.length) {
    return getClosetBatchUploadSnapshot();
  }

  const isFreshQueue = !closetBatchUploadSnapshot.isRunning && queuedClosetAssets.length === 0;
  queuedClosetAssets.push(
    ...params.assets.map((asset) => ({
      accessToken: params.accessToken,
      asset,
      title: params.title
    }))
  );

  updateClosetBatchUploadSnapshot((current) => ({
    completedCount: isFreshQueue ? 0 : current.completedCount,
    currentIndex: isFreshQueue ? null : current.currentIndex,
    error: null,
    isRunning: true,
    queuedCount: queuedClosetAssets.length,
    stage:
      current.stage ??
      `Queued ${queuedClosetAssets.length} photo${queuedClosetAssets.length === 1 ? "" : "s"}`,
    totalCount: (isFreshQueue ? 0 : current.totalCount) + params.assets.length
  }));

  if (!queuedClosetAssetDrain) {
    queuedClosetAssetDrain = drainQueuedClosetAssets();
  }

  return getClosetBatchUploadSnapshot();
}

export async function uploadConfirmedClosetItemImage(params: {
  accessToken: string;
  asset: ImagePicker.ImagePickerAsset;
  itemId: string;
  onStageChange?: (stage: string) => void;
}) {
  params.onStageChange?.("Preparing image");
  const prepared = await prepareUploadAsset(params.asset);

  params.onStageChange?.("Requesting upload");
  const uploadIntent = await createConfirmedClosetItemUploadIntent(params.accessToken, params.itemId, {
    filename: prepared.filename,
    mime_type: prepared.mime_type,
    file_size: prepared.file_size,
    sha256: prepared.sha256
  });

  params.onStageChange?.("Uploading image");
  await uploadFileToPresignedUrl(prepared, uploadIntent.upload);

  params.onStageChange?.("Completing upload");
  const detail = await completeConfirmedClosetItemUpload(
    params.accessToken,
    params.itemId,
    uploadIntent.upload_intent_id
  );

  return {
    detail,
    prepared
  };
}
