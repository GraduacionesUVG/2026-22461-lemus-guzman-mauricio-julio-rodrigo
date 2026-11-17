import { claseEstado, etiquetaEstado } from "../utilidades/estado";

export function EstadoInsignia({ estado }: { estado: string }) {
  return (
    <span className={claseEstado(estado)}>
      <span className="estado-punto" aria-hidden="true" />
      {etiquetaEstado(estado)}
    </span>
  );
}
