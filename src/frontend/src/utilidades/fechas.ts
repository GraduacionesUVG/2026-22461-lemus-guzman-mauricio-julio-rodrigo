export const ZONA_HORARIA_APLICACION = "America/Guatemala";

const formatoFechaHora = new Intl.DateTimeFormat("es-GT", {
  timeZone: ZONA_HORARIA_APLICACION,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  hour12: true
});

export function fechaHora(valor?: string | null) {
  if (!valor) {
    return "No disponible";
  }
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) {
    return "No disponible";
  }
  return formatoFechaHora.format(fecha).replace("a. m.", "a. m.").replace("p. m.", "p. m.");
}

export function etiquetaZonaHoraria() {
  return "Hora de Guatemala (UTC-06:00)";
}

const formatoFechaCompacta = new Intl.DateTimeFormat("es-GT", {
  timeZone: ZONA_HORARIA_APLICACION,
  day: "2-digit",
  month: "2-digit",
  year: "numeric"
});

const formatoHoraCompacta = new Intl.DateTimeFormat("es-GT", {
  timeZone: ZONA_HORARIA_APLICACION,
  hour: "numeric",
  minute: "2-digit",
  hour12: true
});

export function fechaCompacta(valor?: string | null) {
  if (!valor) {
    return { fecha: "No disponible", hora: "" };
  }
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) {
    return { fecha: "No disponible", hora: "" };
  }
  return { fecha: formatoFechaCompacta.format(fecha), hora: formatoHoraCompacta.format(fecha) };
}

export function duracionLegible(milisegundos?: number | null) {
  if (milisegundos === undefined || milisegundos === null) {
    return "—";
  }
  if (milisegundos < 1000) {
    return `${milisegundos} ms`;
  }
  const segundosTotales = milisegundos / 1000;
  if (segundosTotales < 60) {
    return `${segundosTotales.toFixed(1)} s`;
  }
  const minutos = Math.floor(segundosTotales / 60);
  const segundos = Math.round(segundosTotales % 60);
  if (minutos < 60) {
    return `${minutos} min ${String(segundos).padStart(2, "0")} s`;
  }
  const horas = Math.floor(minutos / 60);
  return `${horas} h ${String(minutos % 60).padStart(2, "0")} min`;
}
