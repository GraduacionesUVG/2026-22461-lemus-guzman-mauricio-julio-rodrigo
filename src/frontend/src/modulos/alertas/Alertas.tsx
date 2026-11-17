import { Fragment, useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { Mensaje } from "../../componentes/Mensaje";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Alerta, ResultadoPaso, RespuestaLista } from "../../tipos/dominio";
import { claseEstado } from "../../utilidades/estado";
import { useAvisos } from "../../componentes/Avisos";

function textoSelector(resultado?: ResultadoPaso) {
  const selector = resultado?.contexto?.selector;
  if (!selector) {
    return "No aplica";
  }
  const estrategia = selector.estrategia ? String(selector.estrategia) : "selector";
  const valor = selector.valor ? String(selector.valor) : "";
  return valor ? `${estrategia}: ${valor}` : estrategia;
}

function fecha(valor?: string) {
  return valor ? new Date(valor).toLocaleString("es-GT") : "No disponible";
}

export function Alertas() {
  const [alertas, definirAlertas] = useState<Alerta[]>([]);
  const avisos = useAvisos();
  const [alertaExpandida, definirAlertaExpandida] = useState("");

  async function cargarAlertas() {
    const respuesta = await solicitar<RespuestaLista<Alerta>>("/api/alertas");
    definirAlertas(respuesta.elementos);
  }

  useEffect(() => {
    cargarAlertas().catch((error: Error) => avisos.error(error.message));
  }, []);

  async function clasificar(alerta: Alerta, clasificacion: string) {
    await solicitar(`/api/alertas/${alerta.id}/revisar`, { method: "PATCH", body: JSON.stringify({ clasificacion_manual: clasificacion, observacion_revision: "Revisión manual desde frontend" }) });
    await cargarAlertas();
  }

  return (
    <MarcoModulo titulo="Alertas" descripcion="Reconozca el origen del fallo, revise logs y clasifique resultados.">
      <section className="tabla-panel">
        <table>
          <thead>
            <tr>
              <th>Proyecto</th>
              <th>Pipeline</th>
              <th>Prueba o monitor</th>
              <th>Paso</th>
              <th>Estado</th>
              <th>Severidad</th>
              <th>Clasificación</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            {alertas.map((alerta) => {
              const ejecucion = alerta.ejecucion;
              const resultado = alerta.resultado_principal;
              const contexto = resultado?.contexto;
              const expandida = alertaExpandida === alerta.id;
              return (
                <Fragment key={alerta.id}>
                  <tr>
                    <td><strong>{ejecucion?.proyecto_nombre ?? "No disponible"}</strong><small>{ejecucion?.entorno_nombre ?? "Entorno no disponible"}</small></td>
                    <td><strong>{ejecucion?.pipeline_nombre ?? "No disponible"}</strong><small>Ejecución {alerta.ejecucion_id.slice(0, 8)}</small></td>
                    <td>{contexto?.caso_prueba ?? contexto?.monitor ?? alerta.tipo}</td>
                    <td>{contexto?.paso_prueba ?? contexto?.paso_pipeline ?? "No disponible"}</td>
                    <td><span className={claseEstado(resultado?.estado ?? ejecucion?.estado ?? "pendiente")}>{resultado?.estado ?? ejecucion?.estado ?? "pendiente"}</span></td>
                    <td><span className={claseEstado(alerta.severidad)}>{alerta.severidad}</span></td>
                    <td>{alerta.clasificacion_manual}</td>
                    <td>
                      <div className="botones-linea">
                        <button className="secundario" onClick={() => definirAlertaExpandida(expandida ? "" : alerta.id)}>{expandida ? "Ocultar" : "Ver detalle"}</button>
                        <button className="secundario" onClick={() => clasificar(alerta, "confirmada")}>Confirmar</button>
                        <button className="secundario" onClick={() => clasificar(alerta, "falso_positivo")}>Falso positivo</button>
                      </div>
                    </td>
                  </tr>
                  {expandida && (
                    <tr>
                      <td colSpan={8}>
                        <div className="alerta-detalle">
                          <div className="contexto-grid">
                            <article><span>Fecha</span><strong>{fecha(alerta.fecha_deteccion)}</strong></article>
                            <article><span>Acción Selenium</span><strong>{contexto?.accion ?? resultado?.tipo ?? "No disponible"}</strong></article>
                            <article><span>Selector</span><strong>{textoSelector(resultado)}</strong></article>
                            <article><span>Duración</span><strong>{resultado?.duracion_milisegundos ?? ejecucion?.duracion_milisegundos ?? 0} ms</strong></article>
                          </div>
                          <div className="panel-doble">
                            <div>
                              <h3>Resultado automático</h3>
                              <p>{resultado?.mensaje || ejecucion?.error_tecnico || "Sin mensaje registrado."}</p>
                              <small>Esperado: {resultado?.esperado || "No registrado"}</small>
                              <small>Obtenido: {resultado?.obtenido || "No registrado"}</small>
                              <small>Revisión humana: {resultado?.revision_humana?.clasificacion ?? ejecucion?.revision_humana?.clasificacion ?? "Pendiente"}</small>
                            </div>
                            <div>
                              <h3>Evidencias</h3>
                              {(ejecucion?.evidencias ?? []).length === 0 && <p>No hay evidencias asociadas.</p>}
                              {(ejecucion?.evidencias ?? []).map((evidencia) => <a key={evidencia.id} href={`/api/evidencias/${evidencia.id}`}>{evidencia.nombre_archivo}</a>)}
                            </div>
                          </div>
                          <details open>
                            <summary>Logs y detalles técnicos</summary>
                            <pre>{JSON.stringify(resultado?.datos_tecnicos_sanitizados ?? ejecucion?.resultados?.map((item) => item.datos_tecnicos_sanitizados) ?? {}, null, 2)}</pre>
                          </details>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {alertas.length === 0 && <Mensaje variante="info">No hay alertas registradas.</Mensaje>}
      </section>
    </MarcoModulo>
  );
}
