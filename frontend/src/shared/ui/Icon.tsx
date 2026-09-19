import AccountBalance from "@material-symbols/svg-400/rounded/account_balance.svg?react";
import AccountBalanceWallet from "@material-symbols/svg-400/rounded/account_balance_wallet.svg?react";
import AccountBalanceWalletFill from "@material-symbols/svg-400/rounded/account_balance_wallet-fill.svg?react";
import Add from "@material-symbols/svg-400/rounded/add.svg?react";
import ArrowBack from "@material-symbols/svg-400/rounded/arrow_back.svg?react";
import Check from "@material-symbols/svg-400/rounded/check.svg?react";
import CheckCircleFill from "@material-symbols/svg-400/rounded/check_circle-fill.svg?react";
import ChevronRight from "@material-symbols/svg-400/rounded/chevron_right.svg?react";
import ContentCopy from "@material-symbols/svg-400/rounded/content_copy.svg?react";
import CreditCard from "@material-symbols/svg-400/rounded/credit_card.svg?react";
import CurrencyBitcoin from "@material-symbols/svg-400/rounded/currency_bitcoin.svg?react";
import DarkMode from "@material-symbols/svg-400/rounded/dark_mode.svg?react";
import Download from "@material-symbols/svg-400/rounded/download.svg?react";
import ErrorFill from "@material-symbols/svg-400/rounded/error-fill.svg?react";
import Home from "@material-symbols/svg-400/rounded/home.svg?react";
import HomeFill from "@material-symbols/svg-400/rounded/home-fill.svg?react";
import Inventory2 from "@material-symbols/svg-400/rounded/inventory_2.svg?react";
import LightMode from "@material-symbols/svg-400/rounded/light_mode.svg?react";
import Logout from "@material-symbols/svg-400/rounded/logout.svg?react";
import Close from "@material-symbols/svg-400/rounded/close.svg?react";
import Delete from "@material-symbols/svg-400/rounded/delete.svg?react";
import Edit from "@material-symbols/svg-400/rounded/edit.svg?react";
import NorthEast from "@material-symbols/svg-400/rounded/north_east.svg?react";
import ReceiptLong from "@material-symbols/svg-400/rounded/receipt_long.svg?react";
import ReceiptLongFill from "@material-symbols/svg-400/rounded/receipt_long-fill.svg?react";
import SouthWest from "@material-symbols/svg-400/rounded/south_west.svg?react";
import SwapHoriz from "@material-symbols/svg-400/rounded/swap_horiz.svg?react";
import Undo from "@material-symbols/svg-400/rounded/undo.svg?react";
import Payments from "@material-symbols/svg-400/rounded/payments.svg?react";
import ScheduleFill from "@material-symbols/svg-400/rounded/schedule-fill.svg?react";
import Visibility from "@material-symbols/svg-400/rounded/visibility.svg?react";
import VisibilityOff from "@material-symbols/svg-400/rounded/visibility_off.svg?react";
import WarningFill from "@material-symbols/svg-400/rounded/warning-fill.svg?react";
import type { ComponentType, SVGProps } from "react";

// Material Symbols redondeados, peso 400. Solo se empaquetan los íconos importados acá.
const ICONS = {
  add: Add,
  archive: Inventory2,
  "arrow-back": ArrowBack,
  bank: AccountBalance,
  bitcoin: CurrencyBitcoin,
  cash: Payments,
  check: Check,
  close: Close,
  "check-circle": CheckCircleFill,
  "chevron-right": ChevronRight,
  "content-copy": ContentCopy,
  "credit-card": CreditCard,
  delete: Delete,
  "dark-mode": DarkMode,
  download: Download,
  edit: Edit,
  error: ErrorFill,
  home: Home,
  "home-fill": HomeFill,
  "light-mode": LightMode,
  logout: Logout,
  "movement-in": NorthEast,
  "movement-out": SouthWest,
  movements: ReceiptLong,
  "movements-fill": ReceiptLongFill,
  schedule: ScheduleFill,
  swap: SwapHoriz,
  visibility: Visibility,
  "visibility-off": VisibilityOff,
  undo: Undo,
  wallet: AccountBalanceWallet,
  "wallet-fill": AccountBalanceWalletFill,
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
