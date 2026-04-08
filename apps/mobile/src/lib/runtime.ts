import { NativeModules, Platform } from "react-native";

type TenueRuntimeModule = {
  isSimulator?: boolean;
};

const nativeModules = NativeModules as {
  TenueRuntime?: TenueRuntimeModule;
};

export const isIosSimulator =
  Platform.OS === "ios" && nativeModules.TenueRuntime?.isSimulator === true;
