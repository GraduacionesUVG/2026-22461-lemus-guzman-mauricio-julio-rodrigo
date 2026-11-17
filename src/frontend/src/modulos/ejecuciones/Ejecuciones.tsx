import { Download, FileText, RefreshCw, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { construirUrlApi, solicitar } from "../../api/cliente";
import { useAvisos } from "../../componentes/Avisos";
import { EstadoInsignia } from "../../componentes/EstadoInsignia";
import { EstadoVacio } from "../../componentes/EstadoVacio";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Mensaje } from "../../componentes/Mensaje";
import { TablaEjecuciones } from "../../componentes/TablaEjecuciones";
import { Ejecucion, InformeEjecucion, RespuestaLista } from "../../tipos/dominio";
import { resumenDiagnostico, tieneTrazaExtensa } from "../../utilidades/diagnostico";
import { etiquetaEstado, ESTADOS_EJECUCION } from "../../utilidades/estado";
import { duracionLegible, etiquetaZonaHoraria, fechaHora } from "../../utilidades/fechas";

type ResultadoEjecucion = Ejecucion["resultados"][number];

const REVISIONES_EJECUCION = [
  { valor: "confirmada", etiqueta: "Confirmada" },
  { valor: "falso_positivo", etiqueta: "Falso positivo" },
  { valor: "falso_negativo", etiqueta: "Falso negativo" },
  { valor: "requiere_analisis", etiqueta: "Requiere análisis" }
];

const REVISIONES_PASO = [
  { valor: "confirmado", etiqueta: "Confirmado" },
  { valor: "falso_positivo", etiqueta: "Falso positivo" },
  { valor: "falso_negativo", etiqueta: "Falso negativo" },
  { valor: "no_aplica", etiqueta: "No aplica" }
];

const MENSAJE_ERROR_REVISION = "No se pudo guardar la revisión. Inténtalo nuevamente.";

function DiagnosticoTexto({ texto }: { texto?: string | null }) {
  if (!texto) {
    return null;
  }
  const resumen = resumenDiagnostico(texto);
  if (!tieneTrazaExtensa(texto)) {
    return <p className="diagnostico-resumen">{texto}</p>;
  }
  return (
    <div className="diagnostico">
      {resumen && <p className="diagnostico-resumen">{resumen}</p>}
      <details>
        <summary>Ver traza técnica completa</summary>
        <pre>{texto}</pre>
      </details>
    </div>
  );
}

export function Ejecuciones() {
  const [ejecuciones, definirEjecuciones] = useState<Ejecucion[]>([]);
  const [cargandoLista, definirCargandoLista] = useState(true);
  const [seleccionada, definirSeleccionada] = useState<Ejecucion | null>(null);
  const [cargandoDetalle, definirCargandoDetalle] = useState(false);
  const [comentarioGeneral, definirComentarioGeneral] = useState("");
  const [informe, definirInforme] = useState<InformeEjecucion | null>(null);
  const [generandoInforme, definirGenerandoInforme] = useState(false);
  const [visorAbierto, definirVisorAbierto] = useState(false);
  const [busqueda, definirBusqueda] = useState("");
  const [filtroEstado, definirFiltroEstado] = useState("");
  const [parametros, definirParametros] = useSearchParams();
  const encabezadoDetalle = useRef<HTMLHeadingElement>(null);
  const avisos = useAvisos();

  useEffect(() => {
    solicitar<RespuestaLista<Ejecucion>>("/api/ejecuciones")
      .then((respuesta) => definirEjecuciones(respuesta.elementos))
      .catch((error: Error) => avisos.error(error.message))
      .finally(() => definirCargandoLista(false));
  }, [avisos]);

  const idSolicitado = parametros.get("id");

  useEffect(() => {
    if (idSolicitado && idSolicitado !== seleccionada?.id) {
      cargarDetalle(idSolicitado, true).catch((error: Error) => avisos.error(error.message));
    }
  }, [idSolicitado]);

  const ejecucionesFiltradas = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    return ejecuciones.filter((ejecucion) => {
      if (filtroEstado && ejecucion.estado !== filtroEstado) {
        return false;
      }
      if (!termino) {
        return true;
      }
      return [ejecucion.id, ejecucion.pipeline_nombre, ejecucion.proyecto_nombre, ejecucion.origen]
        .filter(Boolean)
        .some((valor) => String(valor).toLowerCase().includes(termino));
    });
  }, [ejecuciones, busqueda, filtroEstado]);

  const estadosDisponibles = useMemo(() => {
    const presentes = new Set(ejecuciones.map((ejecucion) => ejecucion.estado));
    return [...ESTADOS_EJECUCION, ...[...presentes].filter((estado) => !ESTADOS_EJECUCION.includes(estado))].filter((estado) => presentes.has(estado));
  }, [ejecuciones]);

  async function cargarDetalle(id: string, enfocar = false) {
    definirCargandoDetalle(true);
    try {
      const ejecucion = await solicitar<Ejecucion>(`/api/ejecuciones/${id}`);
      definirSeleccionada(ejecucion);
      definirInforme(null);
      definirVisorAbierto(false);
      if (enfocar) {
        window.requestAnimationFrame(() => encabezadoDetalle.current?.focus());
      }
    } finally {
      definirCargandoDetalle(false);
    }
  }

  function abrirEjecucion(id: string) {
    if (id === idSolicitado) {
      cargarDetalle(id, true).catch((error: Error) => avisos.error(error.message));
      return;
    }
    definirParametros({ id }, { replace: true });
  }

  function cerrarDetalle() {
    definirSeleccionada(null);
    definirVisorAbierto(false);
    definirParametros({}, { replace: true });
  }

  async function revisarEjecucion(clasificacion: string) {
    if (!seleccionada) {
      return;
    }
    await solicitar(`/api/ejecuciones/${seleccionada.id}/revision`, {
      method: "POST",
      body: JSON.stringify({ clasificacion, comentario: comentarioGeneral })
    });
    await cargarDetalle(seleccionada.id);
    avisos.exito("Revisión general guardada correctamente.");
  }

  async function revisarPaso(resultadoId: string, clasificacion: string) {
    await solicitar(`/api/resultados-paso/${resultadoId}/revision`, {
      method: "POST",
      body: JSON.stringify({ clasificacion })
    });
    if (seleccionada) {
      await cargarDetalle(seleccionada.id);
    }
    avisos.exito("Revisión guardada correctamente.");
  }

  function selectorTexto(resultado: ResultadoEjecucion) {
    const selector = resultado.contexto?.selector;
    if (!selector) {
      return "No aplica";
    }
    const estrategia = selector.estrategia ? String(selector.estrategia) : "selector";
    const valor = selector.valor ? String(selector.valor) : "";
    return valor ? `${estrategia}: ${valor}` : estrategia;
  }

  async function generarInforme(regenerar = false) {
    if (!seleccionada) {
      return;
    }
    definirGenerandoInforme(true);
    try {
      const respuesta = await solicitar<InformeEjecucion>(`/api/ejecuciones/${seleccionada.id}/informe`, {
        method: "POST",
        body: JSON.stringify({ regenerar })
      });
      definirInforme(respuesta);
      definirVisorAbierto(true);
      avisos.exito(regenerar ? "Informe regenerado correctamente." : "Informe listo para consulta.");
    } finally {
      definirGenerandoInforme(false);
    }
  }

  function urlInforme(descargar = false) {
    if (!seleccionada) {
      return "";
    }
    const parametrosInforme = new URLSearchParams();
    if (descargar) parametrosInforme.set("descargar", "1");
    if (informe) parametrosInforme.set("version", String(informe.version));
    const consulta = parametrosInforme.toString();
    return construirUrlApi(`/api/ejecuciones/${seleccionada.id}/informe/pdf${consulta ? `?${consulta}` : ""}`);
  }

  function etiquetaTecnica(resultado: ResultadoEjecucion) {
    if (resultado.tipo.startsWith("monitor")) {
      return "Monitor";
    }
    if (resultado.tipo === "caso_prueba") {
      return "Selenium";
    }
    return "Detalle técnico";
  }

  function paresTecnicos(datos: Record<string, unknown> = {}) {
    return Object.entries(datos).filter(([, valor]) => valor !== undefined && valor !== null && valor !== "");
  }

  function nombrePaso(resultado: ResultadoEjecucion) {
    return resultado.contexto?.paso_prueba ?? resultado.contexto?.paso_pipeline ?? resultado.tipo;
  }

  const conteoPasos = seleccionada
    ? {
        exitosos: seleccionada.resultados.filter((resultado) => resultado.estado === "exitosa").length,
        fallidos: seleccionada.resultados.filter((resultado) => resultado.estado === "fallida").length,
        errores: seleccionada.resultados.filter((resultado) => resultado.estado === "error_tecnico").length
      }
    : null;

  return (
    <MarcoModulo titulo="Historial de ejecuciones" descripcion="Consulte ejecuciones, resultados por paso, evidencias y diagnóstico sanitizado.">
      <section className="panel">
        <header className="panel-cabecera">
          <div>
            <h2>Ejecuciones</h2>
            <p>{etiquetaZonaHoraria()}</p>
          </div>
          <div className="filtros" role="search">
            <label className="campo-busqueda">
              <span className="solo-lectores">Buscar ejecución</span>
              <Search size={15} aria-hidden="true" />
              <input type="search" value={busqueda} onChange={(evento) => definirBusqueda(evento.target.value)} placeholder="Buscar por ID, pipeline o proyecto" />
            </label>
            <label>
              <span className="solo-lectores">Filtrar por estado</span>
              <select value={filtroEstado} onChange={(evento) => definirFiltroEstado(evento.target.value)}>
                <option value="">Todos los estados</option>
                {estadosDisponibles.map((estado) => <option key={estado} value={estado}>{etiquetaEstado(estado)}</option>)}
              </select>
            </label>
          </div>
        </header>
        <p className="conteo-resultados" aria-live="polite">
          {cargandoLista ? "Cargando ejecuciones…" : `Mostrando ${ejecucionesFiltradas.length} de ${ejecuciones.length} ejecuciones`}
        </p>
        {ejecucionesFiltradas.length > 0 ? (
          <TablaEjecuciones ejecuciones={ejecucionesFiltradas} seleccionadaId={seleccionada?.id} descripcion="Historial de ejecuciones" alAbrir={abrirEjecucion} />
        ) : (
          !cargandoLista && <EstadoVacio titulo="Sin coincidencias" descripcion={ejecuciones.length ? "Ajuste la búsqueda o el filtro de estado." : "Aún no hay ejecuciones registradas."} />
        )}
      </section>

      {cargandoDetalle && !seleccionada && <p className="estado-carga" role="status">Cargando detalle de la ejecución…</p>}

      {seleccionada && (
        <section className="panel detalle-ejecucion" aria-busy={cargandoDetalle}>
          <header className="panel-cabecera">
            <div className="titulo-detalle">
              <h2 ref={encabezadoDetalle} tabIndex={-1}>Ejecución <code className="identificador">{seleccionada.id.slice(0, 8)}</code></h2>
              <EstadoInsignia estado={seleccionada.estado} />
            </div>
            <button type="button" className="boton-icono" onClick={cerrarDetalle} aria-label="Cerrar detalle de la ejecución"><X size={18} aria-hidden="true" /></button>
          </header>

          <dl className="contexto-grid">
            <div><dt>Proyecto</dt><dd>{seleccionada.proyecto_nombre ?? "No disponible"}</dd></div>
            <div><dt>Pipeline</dt><dd>{seleccionada.pipeline_nombre ?? "No disponible"}</dd></div>
            <div><dt>Entorno</dt><dd>{seleccionada.entorno_nombre ?? "No disponible"}</dd></div>
            <div><dt>Origen</dt><dd>{seleccionada.origen}</dd></div>
            <div><dt>Solicitud</dt><dd>{fechaHora(seleccionada.fecha_encolado)}</dd></div>
            <div><dt>Inicio</dt><dd>{fechaHora(seleccionada.fecha_inicio)}</dd></div>
            <div><dt>Finalización</dt><dd>{fechaHora(seleccionada.fecha_fin)}</dd></div>
            <div><dt>Duración</dt><dd>{duracionLegible(seleccionada.duracion_milisegundos)}</dd></div>
          </dl>

          {conteoPasos && (
            <ul className="resumen-pasos" aria-label="Resumen de pasos">
              <li><strong>{seleccionada.resultados.length}</strong> pasos</li>
              <li className="tono-exito"><strong>{conteoPasos.exitosos}</strong> exitosos</li>
              <li className="tono-error"><strong>{conteoPasos.fallidos}</strong> fallidos</li>
              <li className="tono-tecnico"><strong>{conteoPasos.errores}</strong> errores técnicos</li>
              <li><strong>{(seleccionada.evidencias ?? []).length}</strong> evidencias</li>
              <li><strong>{(seleccionada.alertas ?? []).length}</strong> alertas</li>
            </ul>
          )}

          <div className="acciones-informe">
            <button type="button" onClick={() => generarInforme(false).catch((error: Error) => avisos.error(error.message))} disabled={generandoInforme}>
              <FileText size={16} aria-hidden="true" />
              {generandoInforme ? "Generando…" : "Ver informe PDF"}
            </button>
            <a className="boton-enlace secundario" href={urlInforme(true)}>
              <Download size={16} aria-hidden="true" />
              Descargar PDF
            </a>
            <button type="button" className="secundario" onClick={() => generarInforme(true).catch((error: Error) => avisos.error(error.message))} disabled={generandoInforme}>
              <RefreshCw size={16} aria-hidden="true" />
              Regenerar informe
            </button>
          </div>

          {visorAbierto && (
            <section className="visor-pdf" aria-label="Visor del informe PDF">
              <div className="botones-linea separados">
                <strong>{informe?.nombre_archivo ?? "Informe PDF"}</strong>
                <button type="button" className="boton-icono" onClick={() => definirVisorAbierto(false)} aria-label="Cerrar visor"><X size={18} aria-hidden="true" /></button>
              </div>
              <iframe title="Informe PDF de ejecución" src={urlInforme(false)} />
            </section>
          )}

          {seleccionada.error_tecnico && (
            <article className="bloque-diagnostico" aria-label="Diagnóstico técnico de la ejecución">
              <div className="bloque-diagnostico-cabecera">
                <strong>Diagnóstico técnico</strong>
                <EstadoInsignia estado="error_tecnico" />
              </div>
              <DiagnosticoTexto texto={seleccionada.error_tecnico} />
            </article>
          )}

          <section className="revision-general" aria-labelledby="titulo-revision-general">
            <div className="revision-general-cabecera">
              <h3 id="titulo-revision-general">Revisión humana</h3>
              <span>Resultado automático: <EstadoInsignia estado={seleccionada.estado} /></span>
              <span>Revisión: <strong>{seleccionada.revision_humana ? etiquetaEstado(seleccionada.revision_humana.clasificacion) : (seleccionada.requiere_revision_humana ? "Pendiente" : "No requerida")}</strong></span>
            </div>
            <label>
              <span className="solo-lectores">Comentario del revisor</span>
              <textarea value={comentarioGeneral} onChange={(evento) => definirComentarioGeneral(evento.target.value)} placeholder="Comentario del revisor" rows={2} />
            </label>
            <div className="grupo-segmentado" role="group" aria-label="Clasificar la ejecución">
              {REVISIONES_EJECUCION.map((opcion) => (
                <button
                  key={opcion.valor}
                  type="button"
                  className="secundario"
                  aria-pressed={seleccionada.revision_humana?.clasificacion === opcion.valor}
                  onClick={() => revisarEjecucion(opcion.valor).catch(() => avisos.error(MENSAJE_ERROR_REVISION))}
                >
                  {opcion.etiqueta}
                </button>
              ))}
            </div>
          </section>

          {(seleccionada.alertas ?? []).length > 0 && (
            <section className="subseccion">
              <h3>Alertas de la ejecución</h3>
              <div className="tabla-desplazable">
                <table className="tabla-datos">
                  <thead><tr><th scope="col">Detección</th><th scope="col">Tipo</th><th scope="col">Severidad</th><th scope="col">Clasificación</th></tr></thead>
                  <tbody>
                    {(seleccionada.alertas ?? []).map((alerta) => (
                      <tr key={alerta.id}>
                        <td className="celda-fecha">{fechaHora(alerta.fecha_deteccion)}</td>
                        <td>{etiquetaEstado(alerta.tipo)}</td>
                        <td>{etiquetaEstado(alerta.severidad)}</td>
                        <td>{etiquetaEstado(alerta.clasificacion_manual)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="subseccion">
            <h3>Resultados por paso</h3>
            {seleccionada.resultados.length === 0 && (
              <Mensaje variante="advertencia">La ejecución terminó sin resultados de pasos. Revise el diagnóstico técnico y el log del trabajador.</Mensaje>
            )}
            <ol className="lista-pasos">
              {seleccionada.resultados.map((resultado, indice) => (
                <li className={`paso-resultado paso-${resultado.estado}`} key={resultado.id}>
                  <div className="paso-resultado-cabecera">
                    <span className="paso-numero" aria-hidden="true">{indice + 1}</span>
                    <strong className="paso-titulo"><span className="solo-lectores">Paso {indice + 1}: </span>{nombrePaso(resultado)}</strong>
                    <EstadoInsignia estado={resultado.estado} />
                    <span className="paso-duracion">{duracionLegible(resultado.duracion_milisegundos)}</span>
                  </div>
                  <dl className="paso-meta">
                    <div><dt>Prueba</dt><dd>{resultado.contexto?.caso_prueba ?? resultado.contexto?.monitor ?? "No disponible"}</dd></div>
                    <div><dt>Acción</dt><dd>{resultado.contexto?.accion ?? resultado.tipo}</dd></div>
                    <div><dt>Selector</dt><dd>{selectorTexto(resultado)}</dd></div>
                    <div><dt>Esperado</dt><dd>{resultado.esperado || "No disponible"}</dd></div>
                    <div><dt>Obtenido</dt><dd>{resultado.obtenido || "No disponible"}</dd></div>
                    <div><dt>Horario</dt><dd>{fechaHora(resultado.fecha_inicio)} – {fechaHora(resultado.fecha_fin)}</dd></div>
                  </dl>
                  <DiagnosticoTexto texto={resultado.mensaje} />
                  <div className="paso-revision">
                    <span>Revisión: <strong>{resultado.revision_humana ? etiquetaEstado(resultado.revision_humana.clasificacion) : "Pendiente"}</strong></span>
                    <div className="grupo-segmentado" role="group" aria-label={`Clasificar el paso ${indice + 1}`}>
                      {REVISIONES_PASO.map((opcion) => (
                        <button
                          key={opcion.valor}
                          type="button"
                          className="secundario"
                          aria-pressed={resultado.revision_humana?.clasificacion === opcion.valor}
                          onClick={() => revisarPaso(resultado.id, opcion.valor).catch(() => avisos.error(MENSAJE_ERROR_REVISION))}
                        >
                          {opcion.etiqueta}
                        </button>
                      ))}
                    </div>
                  </div>
                  <details className="detalle-tecnico" open={resultado.estado !== "exitosa" && paresTecnicos(resultado.datos_tecnicos_sanitizados).length > 0}>
                    <summary>Logs y detalles técnicos · {etiquetaTecnica(resultado)}</summary>
                    {paresTecnicos(resultado.datos_tecnicos_sanitizados).length > 0 ? (
                      <dl className="detalles-tecnicos">
                        {paresTecnicos(resultado.datos_tecnicos_sanitizados).map(([clave, valor]) => (
                          <div key={clave}><dt>{clave.replaceAll("_", " ")}</dt><dd>{typeof valor === "object" ? JSON.stringify(valor) : String(valor)}</dd></div>
                        ))}
                      </dl>
                    ) : <p className="texto-secundario">No hay metadatos técnicos adicionales registrados para este paso.</p>}
                    <details>
                      <summary>JSON sanitizado</summary>
                      <pre>{JSON.stringify(resultado.datos_tecnicos_sanitizados ?? {}, null, 2)}</pre>
                    </details>
                  </details>
                </li>
              ))}
            </ol>
          </section>

          {(seleccionada.evidencias ?? []).length > 0 && (
            <section className="subseccion">
              <h3>Evidencias</h3>
              <ul className="lista-evidencias">
                {(seleccionada.evidencias ?? []).map((evidencia) => (
                  <li key={evidencia.id}>
                    <span className="celda-texto">{evidencia.nombre_archivo}</span>
                    <small>{evidencia.tipo_contenido}</small>
                    <a href={`/api/evidencias/${evidencia.id}`}>Descargar evidencia<span className="solo-lectores"> {evidencia.nombre_archivo}</span></a>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </section>
      )}

      {!seleccionada && !cargandoDetalle && ejecuciones.length > 0 && (
        <p className="texto-secundario">Seleccione una ejecución para consultar su línea de tiempo, diagnóstico e informe.</p>
      )}
    </MarcoModulo>
  );
}
