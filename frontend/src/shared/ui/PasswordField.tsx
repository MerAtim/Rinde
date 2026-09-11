import { useState } from "react";
import { useTranslation } from "react-i18next";

import { IconButton } from "./IconButton";
import { TextField, type TextFieldProps } from "./TextField";

export type PasswordFieldProps = Omit<TextFieldProps, "type" | "action">;

/** Contraseña con botón para mostrarla: ayuda a escribir frases largas sin errores. */
export function PasswordField(props: PasswordFieldProps) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  return (
    <TextField
      {...props}
      type={visible ? "text" : "password"}
      action={
        <IconButton
          icon={visible ? "visibility-off" : "visibility"}
          label={visible ? t("auth.hidePassword") : t("auth.showPassword")}
          onPress={() => {
            setVisible((current) => !current);
          }}
        />
      }
    />
  );
}
