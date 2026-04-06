import { Text, type TextProps, type TextStyle } from "react-native";

import { colors } from "../theme";
import { textStyles } from "../theme/typography";

type AppTextVariant = keyof typeof textStyles;

type AppTextProps = TextProps & {
  variant?: AppTextVariant;
  color?: string;
};

export function AppText({
  children,
  color = colors.text,
  style,
  variant = "body",
  ...props
}: AppTextProps) {
  return (
    <Text
      {...props}
      style={[textStyles[variant] as TextStyle, { color }, style]}
    >
      {children}
    </Text>
  );
}
