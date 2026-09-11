import Check from "@material-symbols/svg-400/rounded/check.svg?react";
import CheckCircleFill from "@material-symbols/svg-400/rounded/check_circle-fill.svg?react";
import ContentCopy from "@material-symbols/svg-400/rounded/content_copy.svg?react";
import DarkMode from "@material-symbols/svg-400/rounded/dark_mode.svg?react";
import Download from "@material-symbols/svg-400/rounded/download.svg?react";
import ErrorFill from "@material-symbols/svg-400/rounded/error-fill.svg?react";
import LightMode from "@material-symbols/svg-400/rounded/light_mode.svg?react";
import Logout from "@material-symbols/svg-400/rounded/logout.svg?react";
import ScheduleFill from "@material-symbols/svg-400/rounded/schedule-fill.svg?react";
import Visibility from "@material-symbols/svg-400/rounded/visibility.svg?react";
import VisibilityOff from "@material-symbols/svg-400/rounded/visibility_off.svg?react";
import WarningFill from "@material-symbols/svg-400/rounded/warning-fill.svg?react";
import type { ComponentType, SVGProps } from "react";

// Material Symbols redondeados, peso 400. Solo se empaquetan los íconos importados acá.
const ICONS = {
  check: Check,
  "check-circle": CheckCircleFill,
  "content-copy": ContentCopy,
  "dark-mode": DarkMode,
  download: Download,
  error: ErrorFill,
  "light-mode": LightMode,
  logout: Logout,
  schedule: ScheduleFill,
  visibility: Visibility,
  "visibility-off": VisibilityOff,
  warning: WarningFill,
} satisfies Record<string, ComponentType<SVGProps<SVGSVGElement>>>;

export type IconName = keyof typeof ICONS;

interface IconProps {
  name: IconName;
  size?: number;
}

/** Ícono decorativo: siempre acompaña a un texto o a una etiqueta accesible. Toma el color del texto. */
export function Icon({ name, size = 20 }: IconProps) {
  const Svg = ICONS[name];
  return (
    <Svg aria-hidden="true" focusable="false" width={size} height={size} fill="currentColor" />
  );
}
