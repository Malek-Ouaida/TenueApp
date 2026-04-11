import { useEffect, useMemo, useRef, useState } from "react";
import { router } from "expo-router";
import { Animated, Easing, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Image } from "expo-image";

import { authPalette } from "../../src/auth/ui";
import { supportsNativeAnimatedDriver } from "../../src/lib/runtime";
import splashLogo from "../../assets/auth/t_black.png";

export default function SplashScreen() {
  const [phase, setPhase] = useState<"enter" | "hold" | "exit">("enter");
  const fade = useRef(new Animated.Value(0)).current;
  const gradientDrift = useRef(new Animated.Value(0)).current;
  const gradientPulse = useRef(new Animated.Value(0)).current;
  const line = useRef(new Animated.Value(0)).current;
  const logoStyle = useMemo(
    () => ({
      opacity: phase === "enter" ? fade.interpolate({ inputRange: [0, 1], outputRange: [0, 1] }) : phase === "hold" ? 1 : fade.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
      transform: [
        {
          scale:
            phase === "enter"
              ? fade.interpolate({ inputRange: [0, 1], outputRange: [0.88, 1] })
              : phase === "hold"
                ? 1
                : fade.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] })
        },
        {
          translateY:
            phase === "enter"
              ? fade.interpolate({ inputRange: [0, 1], outputRange: [8, 0] })
              : phase === "hold"
                ? 0
                : fade.interpolate({ inputRange: [0, 1], outputRange: [0, -12] })
        }
      ]
    }),
    [fade, phase]
  );

  useEffect(() => {
    fade.setValue(0);
    line.setValue(0);
    Animated.timing(fade, {
      toValue: 1,
      duration: 800,
      easing: Easing.bezier(0.32, 0.72, 0, 1),
      useNativeDriver: supportsNativeAnimatedDriver
    }).start();
    const lineTimer = setTimeout(() => {
      setPhase("hold");
      Animated.timing(line, {
        toValue: 1,
        duration: 1200,
        easing: Easing.bezier(0.32, 0.72, 0, 1),
        useNativeDriver: supportsNativeAnimatedDriver
      }).start();
    }, 80);
    const exitTimer = setTimeout(() => {
      setPhase("exit");
      fade.setValue(0);
      Animated.timing(fade, {
        toValue: 1,
        duration: 500,
        easing: Easing.bezier(0.32, 0.72, 0, 1),
        useNativeDriver: supportsNativeAnimatedDriver
      }).start();
    }, 1400);
    const navTimer = setTimeout(() => {
      router.replace("/welcome");
    }, 1850);

    const loops = [
      Animated.loop(
        Animated.sequence([
          Animated.timing(gradientDrift, {
            toValue: 1,
            duration: 6000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: supportsNativeAnimatedDriver
          }),
          Animated.timing(gradientDrift, {
            toValue: 0,
            duration: 6000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: supportsNativeAnimatedDriver
          })
        ])
      ),
      Animated.loop(
        Animated.sequence([
          Animated.timing(gradientPulse, {
            toValue: 1,
            duration: 7000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: supportsNativeAnimatedDriver
          }),
          Animated.timing(gradientPulse, {
            toValue: 0,
            duration: 7000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: supportsNativeAnimatedDriver
          })
        ])
      )
    ];
    loops.forEach((loop) => loop.start());

    return () => {
      clearTimeout(lineTimer);
      clearTimeout(exitTimer);
      clearTimeout(navTimer);
      loops.forEach((loop) => loop.stop());
    };
  }, [fade, gradientDrift, gradientPulse, line]);

  return (
    <View style={styles.page}>
      <Animated.View
        style={[
          StyleSheet.absoluteFillObject,
          {
            opacity: phase === "exit" ? 1 : 0
          }
        ]}
      >
        <LinearGradient
          colors={[authPalette.background, authPalette.background]}
          end={{ x: 1, y: 1 }}
          start={{ x: 0, y: 0 }}
          style={StyleSheet.absoluteFillObject}
        />
      </Animated.View>
      <View pointerEvents="none" style={styles.gradientLayer}>
        <Animated.View
          style={[
            styles.gradientSheet,
            styles.gradientSheetPrimary,
            {
              opacity: 1,
              transform: [
                {
                  translateX: gradientDrift.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [-28, 16, -12]
                  })
                },
                {
                  translateY: gradientDrift.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [-12, 18, -6]
                  })
                },
                {
                  scale: gradientPulse.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [1.02, 1.08, 1.03]
                  })
                }
              ]
            }
          ]}>
          <LinearGradient
            colors={["#FFF8F6", "#FFEAE4", "#FFE0D8", "#F5E6FF", "#FFF8F0"]}
            end={{ x: 1, y: 1 }}
            start={{ x: 0, y: 0 }}
            style={styles.gradientFill}
          />
        </Animated.View>
        <Animated.View
          style={[
            styles.gradientSheet,
            styles.gradientSheetSecondary,
            {
              opacity: 0.78,
              transform: [
                {
                  translateX: gradientDrift.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [18, -26, 22]
                  })
                },
                {
                  translateY: gradientPulse.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [16, -22, 12]
                  })
                },
                {
                  scale: gradientDrift.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [1.12, 1.04, 1.1]
                  })
                }
              ]
            }
          ]}>
          <LinearGradient
            colors={["#FFEAE4", "#FFF8F6", "#F5E6FF", "#FFE0D8"]}
            end={{ x: 0.15, y: 1 }}
            start={{ x: 0.95, y: 0 }}
            style={styles.gradientFill}
          />
        </Animated.View>
        <Animated.View
          style={[
            styles.gradientSheet,
            styles.gradientSheetWarm,
            {
              opacity: 0.5,
              transform: [
                {
                  translateX: gradientPulse.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [-14, 24, -10]
                  })
                },
                {
                  translateY: gradientDrift.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [22, -12, 18]
                  })
                },
                {
                  scale: gradientPulse.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [1.06, 1.14, 1.08]
                  })
                }
              ]
            }
          ]}>
          <LinearGradient
            colors={["#FFF8F0", "#FFEAE4", "#FFF8F6"]}
            end={{ x: 1, y: 0.9 }}
            start={{ x: 0, y: 0.1 }}
            style={styles.gradientFill}
          />
        </Animated.View>
      </View>

      <Animated.View style={[styles.logoShell, logoStyle]}>
        <Image contentFit="contain" source={splashLogo} style={styles.logoImage} />
      </Animated.View>

      <Animated.View
        style={[
          styles.bottomLine,
          {
            opacity: phase === "exit" ? 0 : 1,
            transform: [
              {
                scaleX: line.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, 1]
                })
              }
            ]
          }
        ]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    backgroundColor: authPalette.background
  },
  gradientLayer: {
    ...StyleSheet.absoluteFillObject
  },
  gradientSheet: {
    position: "absolute",
    width: "150%",
    height: "150%"
  },
  gradientSheetPrimary: {
    top: "-22%",
    left: "-24%"
  },
  gradientSheetSecondary: {
    top: "-18%",
    right: "-30%"
  },
  gradientSheetWarm: {
    bottom: "-30%",
    left: "-18%"
  },
  gradientFill: {
    flex: 1
  },
  logoShell: {
    alignItems: "center",
    justifyContent: "center"
  },
  logoImage: {
    width: 56,
    height: 56
  },
  bottomLine: {
    position: "absolute",
    bottom: 0,
    width: "60%",
    height: 2,
    backgroundColor: "rgba(255, 107, 107, 0.28)"
  }
});
