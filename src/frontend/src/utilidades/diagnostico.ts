const MARCADORES_TRAZA = ["stacktrace:", "symbols not available", "backtrace", "traceback (most recent call last)", "\tat ", "#0 0x"];

export function resumenDiagnostico(texto?: string | null, limite = 220): string {
  if (!texto) {
    return "";
  }
  const minusculas = texto.toLowerCase();
  const corte = MARCADORES_TRAZA.map((marcador) => minusculas.indexOf(marcador)).filter((posicion) => posicion > 0).reduce((menor, posicion) => Math.min(menor, posicion), texto.length);
  const util = texto.slice(0, corte).replace(/^\s*message:\s*/i, "");
  const primeraLinea = util.split(/\r?\n/).map((linea) => linea.trim()).find((linea) => linea.length > 0) ?? "";
  const compacta = primeraLinea.replace(/\s+/g, " ").replace(/^message:\s*/i, "").trim();
  return compacta.length > limite ? `${compacta.slice(0, limite - 1).trimEnd()}…` : compacta;
}

export function tieneTrazaExtensa(texto?: string | null): boolean {
  if (!texto) {
    return false;
  }
  return texto.length > 240 || texto.split(/\r?\n/).length > 3;
}
