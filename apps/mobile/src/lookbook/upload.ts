import type { ImagePickerAsset } from "expo-image-picker";

import { prepareUploadAsset, uploadFileToPresignedUrl } from "../closet/upload";
import { completeLookbookUpload, createLookbookUploadIntent } from "./client";

export async function uploadLookbookAsset(accessToken: string, asset: ImagePickerAsset) {
  const prepared = await prepareUploadAsset(asset);
  const uploadIntent = await createLookbookUploadIntent(accessToken, {
    filename: prepared.filename,
    mime_type: prepared.mime_type,
    file_size: prepared.file_size,
    sha256: prepared.sha256
  });

  await uploadFileToPresignedUrl(prepared, uploadIntent.upload);
  return completeLookbookUpload(accessToken, uploadIntent.upload_intent_id);
}
