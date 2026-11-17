import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";

type VarianteMensaje = "error" | "exito" | "advertencia" | "info";

const iconos = {
  error: AlertCircle,
  exito: CheckCircle2,
  advertencia: TriangleAlert,
  info: Info
};

const titulos = {
  error: "Error",
  exito: "Listo",
  advertencia: "Atención",
  info: "Información"
};

export function Mensaje({ variante = "info", titulo, children }: { variante?: VarianteMensaje; titulo?: string; children: string }) {
  const Icono = iconos[variante];
  return (
    <div className={`mensaje mensaje-${variante}`} role={variante === "error" ? "alert" : "status"}>
      <Icono size={18} />
      <div>
        <strong>{titulo ?? titulos[variante]}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}
