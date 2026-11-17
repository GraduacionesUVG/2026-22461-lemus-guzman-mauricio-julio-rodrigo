import { useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { CasoPrueba, Ejecucion, Entorno, Monitor, Pipeline, Proyecto, RespuestaLista } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

export function Pipelines() {
  const [proyectos, definirProyectos] = useState<Proyecto[]>([]);
  const [entornos, definirEntornos] = useState<Entorno[]>([]);
  const [monitores, definirMonitores] = useState<Monitor[]>([]);
  const [casos, definirCasos] = useState<CasoPrueba[]>([]);
  const [pipelines, definirPipelines] = useState<Pipeline[]>([]);
  const [proyectoId, definirProyectoId] = useState("");
  const [entornoId, definirEntornoId] = useState("");
  const avisos = useAvisos();

  async function cargarTodo() {
    const [respuestaProyectos, respuestaMonitores, respuestaCasos, respuestaPipelines] = await Promise.all([
      solicitar<RespuestaLista<Proyecto>>("/api/proyectos"),
      solicitar<RespuestaLista<Monitor>>("/api/monitores"),
      solicitar<RespuestaLista<CasoPrueba>>("/api/casos-prueba"),
      solicitar<RespuestaLista<Pipeline>>("/api/pipelines")
    ]);
    definirProyectos(respuestaProyectos.elementos);
    definirProyectoId(respuestaProyectos.elementos[0]?.id ?? "");
    definirMonitores(respuestaMonitores.elementos);
    definirCasos(respuestaCasos.elementos);
    definirPipelines(respuestaPipelines.elementos);
  }

  useEffect(() => {
    cargarTodo().catch((error: Error) => avisos.error(error.message));
  }, []);

  useEffect(() => {
    if (!proyectoId) {
      return;
    }
    solicitar<RespuestaLista<Entorno>>(`/api/proyectos/${proyectoId}/entornos`).then((respuesta) => {
      definirEntornos(respuesta.elementos);
      definirEntornoId(respuesta.elementos[0]?.id ?? "");
    });
  }, [proyectoId]);

  async function crearPipeline() {
    const monitor = monitores.find((elemento) => elemento.proyecto_id === proyectoId);
    const caso = casos.find((elemento) => elemento.proyecto_id === proyectoId);
    if (!monitor || !caso) {
      avisos.advertencia("Necesita al menos un monitor y un caso de prueba para crear el pipeline.");
      return;
    }
    await solicitar<Pipeline>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify({
        proyecto_id: proyectoId,
        nombre: "Validacion integral",
        detener_ante_fallo: false,
        pasos: [
          { orden: 1, tipo: "monitor", nombre: monitor.nombre, monitor_id: monitor.id, continuar_si_falla: true },
          { orden: 2, tipo: "caso_prueba", nombre: caso.nombre, caso_prueba_id: caso.id, continuar_si_falla: true }
        ]
      })
    });
    avisos.exito("Pipeline creado.");
    await cargarTodo();
  }

  async function ejecutarPipeline(pipelineId: string) {
    const ejecucion = await solicitar<Ejecucion>(`/api/pipelines/${pipelineId}/ejecutar`, {
      method: "POST",
      body: JSON.stringify({ entorno_id: entornoId, procesar_ahora: false })
    });
    avisos.exito(`Ejecución ${ejecucion.id.slice(0, 8)} encolada correctamente.`);
  }

  return (
    <MarcoModulo titulo="Pipelines" descripcion="Combine monitores y casos de prueba en una secuencia manual o programable.">
      <section className="formulario compacto">
        <label>Proyecto<select value={proyectoId} onChange={(evento) => definirProyectoId(evento.target.value)}>{proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}</select></label>
        <label>Entorno de ejecución<select value={entornoId} onChange={(evento) => definirEntornoId(evento.target.value)}>{entornos.map((entorno) => <option key={entorno.id} value={entorno.id}>{entorno.nombre}</option>)}</select></label>
        <button type="button" onClick={() => crearPipeline().catch((error: Error) => avisos.error(error.message))}>Crear pipeline guiado</button>
      </section>
      <section className="tabla-panel">
        <table><thead><tr><th>Pipeline</th><th>Pasos</th><th>Acción</th></tr></thead><tbody>{pipelines.map((pipeline) => <tr key={pipeline.id}><td>{pipeline.nombre}</td><td>{pipeline.pasos.length}</td><td><button onClick={() => ejecutarPipeline(pipeline.id).catch((error: Error) => avisos.error(error.message))}>Ejecutar</button></td></tr>)}</tbody></table>
      </section>
    </MarcoModulo>
  );
}
