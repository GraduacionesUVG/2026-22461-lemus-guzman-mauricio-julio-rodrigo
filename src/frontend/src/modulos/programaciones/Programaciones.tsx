import { useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Entorno, Pipeline, Programacion, RespuestaLista } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

export function Programaciones() {
  const [pipelines, definirPipelines] = useState<Pipeline[]>([]);
  const [programaciones, definirProgramaciones] = useState<Programacion[]>([]);
  const [entornos, definirEntornos] = useState<Entorno[]>([]);
  const [pipelineId, definirPipelineId] = useState("");
  const [entornoId, definirEntornoId] = useState("");
  const [nombre, definirNombre] = useState("Programación guiada");
  const [tipoFrecuencia, definirTipoFrecuencia] = useState("minutos");
  const [cada, definirCada] = useState(15);
  const [hora, definirHora] = useState("06:00");
  const [editandoId, definirEditandoId] = useState("");
  const [siguientePreview, definirSiguientePreview] = useState("");
  const avisos = useAvisos();

  async function cargarProgramaciones() {
    const respuesta = await solicitar<RespuestaLista<Programacion>>("/api/programaciones");
    definirProgramaciones(respuesta.elementos);
  }

  useEffect(() => {
    solicitar<RespuestaLista<Pipeline>>("/api/pipelines").then((respuesta) => {
      definirPipelines(respuesta.elementos);
      definirPipelineId(respuesta.elementos[0]?.id ?? "");
    });
    cargarProgramaciones().catch((error: Error) => avisos.error(error.message));
  }, []);

  useEffect(() => {
    const pipeline = pipelines.find((elemento) => elemento.id === pipelineId);
    if (!pipeline) {
      return;
    }
    solicitar<RespuestaLista<Entorno>>(`/api/proyectos/${pipeline.proyecto_id}/entornos`).then((respuesta) => {
      definirEntornos(respuesta.elementos);
      definirEntornoId(respuesta.elementos[0]?.id ?? "");
    });
  }, [pipelineId, pipelines]);

  function construirConfiguracion() {
    return tipoFrecuencia === "diaria" ? { entorno_id: entornoId, hora } : { cada, entorno_id: entornoId };
  }

  async function previsualizarProgramacion() {
    if (!entornoId) {
      definirSiguientePreview("");
      return;
    }
    const respuesta = await solicitar<{ siguiente_ejecucion: string }>("/api/programaciones/previsualizar", {
      method: "POST",
      body: JSON.stringify({
        tipo_frecuencia: tipoFrecuencia,
        configuracion_frecuencia: construirConfiguracion()
      })
    });
    definirSiguientePreview(respuesta.siguiente_ejecucion);
  }

  useEffect(() => {
    previsualizarProgramacion().catch(() => definirSiguientePreview(""));
  }, [tipoFrecuencia, cada, hora, entornoId]);

  function cargarEdicion(programacion: Programacion) {
    definirEditandoId(programacion.id);
    definirNombre(programacion.nombre);
    definirPipelineId(programacion.pipeline_id);
    definirTipoFrecuencia(programacion.tipo_frecuencia);
    definirCada(Number(programacion.configuracion_frecuencia.cada ?? 15));
    definirHora(String(programacion.configuracion_frecuencia.hora ?? "06:00"));
    definirEntornoId(String(programacion.configuracion_frecuencia.entorno_id ?? ""));
  }

  function limpiarFormulario() {
    definirEditandoId("");
    definirNombre("Programación guiada");
    definirTipoFrecuencia("minutos");
    definirCada(15);
    definirHora("06:00");
  }

  async function crearProgramacion() {
    await solicitar<Programacion>("/api/programaciones", {
      method: "POST",
      body: JSON.stringify({
        pipeline_id: pipelineId,
        nombre,
        tipo_frecuencia: tipoFrecuencia,
        configuracion_frecuencia: construirConfiguracion(),
        zona_horaria: "America/Guatemala"
      })
    });
    avisos.exito("Programación creada con siguiente ejecución calculada.");
    limpiarFormulario();
    await cargarProgramaciones();
  }

  async function guardarProgramacion() {
    if (!editandoId) {
      await crearProgramacion();
      return;
    }
    await solicitar<Programacion>(`/api/programaciones/${editandoId}`, {
      method: "PATCH",
      body: JSON.stringify({
        nombre,
        tipo_frecuencia: tipoFrecuencia,
        configuracion_frecuencia: construirConfiguracion(),
        zona_horaria: "America/Guatemala"
      })
    });
    avisos.exito("Programación actualizada.");
    limpiarFormulario();
    await cargarProgramaciones();
  }

  async function alternarProgramacion(programacion: Programacion) {
    await solicitar<Programacion>(`/api/programaciones/${programacion.id}`, {
      method: "PATCH",
      body: JSON.stringify({ activo: !programacion.activo })
    });
    avisos.exito(programacion.activo ? "Programación pausada." : "Programación activada.");
    await cargarProgramaciones();
  }

  return (
    <MarcoModulo titulo="Programaciones" descripcion="Encole ejecuciones recurrentes sin exigir expresiones cron.">
      <section className="panel-doble">
        <form className="formulario compacto" onSubmit={(evento) => { evento.preventDefault(); guardarProgramacion().catch((error: Error) => avisos.error(error.message)); }}>
          <label>Nombre<input value={nombre} onChange={(evento) => definirNombre(evento.target.value)} required /></label>
          <label>Pipeline<select value={pipelineId} onChange={(evento) => definirPipelineId(evento.target.value)}>{pipelines.map((pipeline) => <option key={pipeline.id} value={pipeline.id}>{pipeline.nombre}</option>)}</select></label>
          <label>Entorno<select value={entornoId} onChange={(evento) => definirEntornoId(evento.target.value)}>{entornos.map((entorno) => <option key={entorno.id} value={entorno.id}>{entorno.nombre}</option>)}</select></label>
          <label>Frecuencia<select value={tipoFrecuencia} onChange={(evento) => definirTipoFrecuencia(evento.target.value)}><option value="minutos">Cada ciertos minutos</option><option value="horas">Cada ciertas horas</option><option value="diaria">Diaria</option></select></label>
          {tipoFrecuencia === "diaria" ? <label>Hora<input type="time" value={hora} onChange={(evento) => definirHora(evento.target.value)} /></label> : <label>Cada<input type="number" min={1} value={cada} onChange={(evento) => definirCada(Number(evento.target.value))} /></label>}
          {siguientePreview && <p className="mensaje-info">Siguiente ejecución estimada: {new Date(siguientePreview).toLocaleString()}</p>}
          <div className="botones-linea">
            <button type="submit">{editandoId ? "Actualizar programación" : "Guardar programación"}</button>
            {editandoId && <button type="button" className="secundario" onClick={limpiarFormulario}>Cancelar edición</button>}
          </div>
        </form>
        <section className="tabla-panel">
          <table><thead><tr><th>Nombre</th><th>Frecuencia</th><th>Siguiente</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{programaciones.map((programacion) => <tr key={programacion.id}><td>{programacion.nombre}</td><td>{programacion.tipo_frecuencia}</td><td>{programacion.siguiente_ejecucion ? new Date(programacion.siguiente_ejecucion).toLocaleString() : "Pendiente"}</td><td>{programacion.activo ? "Activa" : "Pausada"}</td><td><div className="botones-linea"><button type="button" className="secundario" onClick={() => cargarEdicion(programacion)}>Editar</button><button type="button" className="secundario" onClick={() => alternarProgramacion(programacion).catch((error: Error) => avisos.error(error.message))}>{programacion.activo ? "Pausar" : "Activar"}</button></div></td></tr>)}</tbody></table>
        </section>
      </section>
    </MarcoModulo>
  );
}
