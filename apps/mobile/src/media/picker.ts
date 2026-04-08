import * as ImagePicker from "expo-image-picker";

export async function launchCameraForSingleImage() {
  const result = await ImagePicker.launchCameraAsync({
    allowsEditing: false,
    cameraType: ImagePicker.CameraType.back,
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 1
  });

  if (result.canceled || !result.assets.length) {
    return null;
  }

  return result.assets[0]?.uri ?? null;
}

export async function launchLibraryForImages(options?: { multiple?: boolean }) {
  const result = await ImagePicker.launchImageLibraryAsync({
    allowsEditing: false,
    allowsMultipleSelection: options?.multiple ?? false,
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 1,
    selectionLimit: options?.multiple ? 10 : 1
  });

  if (result.canceled || !result.assets.length) {
    return [];
  }

  return result.assets.map((asset) => asset.uri).filter(Boolean);
}
