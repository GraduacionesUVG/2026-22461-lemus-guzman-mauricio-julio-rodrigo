import { ChevronRight } from "lucide-react";
import { Ejecucion } from "../tipos/dominio";
import { duracionLegible, fechaCompacta } from "../utilidades/fechas";
import { EstadoInsignia } from "./EstadoInsignia";

type PropiedadesTabla = {
  ejecuciones: Ejecucion[];
  seleccionadaId?: string;
  descripcion: string;
  alAbrir: (id: string) => void;
};

export function TablaEjecuciones({ ejecuciones, seleccionadaId, descripcion, alAbrir }: PropiedadesTabla) {
  return (
    <div className="tabla-desplazable">
      <table className="tabla-datos">
        <caption className="solo-lectores">{descripcion}</caption>
        <colgroup>
          <col className="col-id" />
          <col className="col-pipeline" />
          <col className="col-proyecto" />
          <col className="col-estado" />
          <col className="col-fecha" />
          <col className="col-duracion" />
          <col className="col-accion" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Pipeline</th>
            <th scope="col">Proyecto</th>
            <th scope="col">Estado</th>
            <th scope="col">Fecha</th>
            <th scope="col" className="numerica">Duración</th>
            <th scope="col"><span className="solo-lectores">Acción</span></th>
          </tr>
        </thead>
        <tbody>
          {ejecuciones.map((ejecucion) => {
            const identificador = ejecucion.id.slice(0, 8);
            const { fecha, hora } = fechaCompacta(ejecucion.fecha_inicio ?? ejecucion.fecha_encolado);
            const seleccionada = ejecucion.id === seleccionadaId;
            return (
              <tr key={ejecucion.id} className={seleccionada ? "fila-seleccionada" : undefined} onClick={() => alAbrir(ejecucion.id)}>
                <td><code className="identificador" title={ejecucion.id}>{identificador}</code></td>
                <td className="celda-texto" title={ejecucion.pipeline_nombre ?? ejecucion.pipeline_id}>{ejecucion.pipeline_nombre ?? ejecucion.pipeline_id.slice(0, 8)}</td>
                <td className="celda-texto secundaria" title={ejecucion.proyecto_nombre ?? undefined}>{ejecucion.proyecto_nombre ?? "No disponible"}</td>
                <td><EstadoInsignia estado={ejecucion.estado} /></td>
                <td className="celda-fecha"><time dateTime={ejecucion.fecha_inicio ?? ejecucion.fecha_encolado}>{fecha} <span className="secundaria">{hora}</span></time></td>
                <td className="numerica">{duracionLegible(ejecucion.duracion_milisegundos)}</td>
                <td className="celda-accion">
                  <button
                    type="button"
                    className="boton-tabla"
                    aria-label={`Ver detalle de la ejecución ${identificador}`}
                    aria-current={seleccionada ? "true" : undefined}
                    onClick={(evento) => {
                      evento.stopPropagation();
                      alAbrir(ejecucion.id);
                    }}
                  >
                    Ver detalle
                    <ChevronRight size={14} aria-hidden="true" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
