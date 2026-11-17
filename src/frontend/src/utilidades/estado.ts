const ETIQUETAS_ESTADO: Record<string, string> = {
  exitosa: "Exitosa",
  exitoso: "Exitoso",
  fallida: "Fallida",
  error_tecnico: "Error técnico",
  pendiente: "Pendiente",
  en_cola: "Pendiente",
  en_ejecucion: "En ejecución",
  cancelada: "Cancelada",
  enviada: "Enviada",
  omitida: "Omitida",
  disponible: "Disponible",
  revisada: "Revisada",
  confirmada: "Confirmada",
  confirmado: "Confirmado",
  falso_positivo: "Falso positivo",
  falso_negativo: "Falso negativo",
  requiere_analisis: "Requiere análisis",
  no_aplica: "No aplica"
};

export const ESTADOS_EJECUCION = ["exitosa", "fallida", "error_tecnico", "en_cola", "en_ejecucion", "cancelada"];

export function etiquetaEstado(estado?: string | null): string {
  if (!estado) {
    return "No disponible";
  }
  const conocida = ETIQUETAS_ESTADO[estado];
  if (conocida) {
    return conocida;
  }
  const texto = estado.replaceAll("_", " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function tonoEstado(estado: string): "exito" | "error" | "tecnico" | "progreso" | "neutral" {
  if (["exitosa", "exitoso", "disponible", "enviada", "confirmada", "confirmado"].includes(estado)) {
    return "exito";
  }
  if (estado === "fallida") {
    return "error";
  }
  if (estado === "error_tecnico") {
    return "tecnico";
  }
  if (["en_ejecucion", "en_cola", "pendiente"].includes(estado)) {
    return "progreso";
  }
  return "neutral";
}

export function claseEstado(estado: string): string {
  if (["exitosa", "disponible", "enviada"].includes(estado)) {
    return "estado estado-exito";
  }
  if (estado === "fallida") {
    return "estado estado-error";
  }
  if (estado === "error_tecnico") {
    return "estado estado-tecnico";
  }
  if (["en_ejecucion", "en_cola"].includes(estado)) {
    return "estado estado-progreso";
  }
  return "estado estado-advertencia";
}
