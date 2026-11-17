import { useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { CanalNotificacion, Proyecto, RespuestaLista } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

export function Notificaciones() {
  const [proyectos, definirProyectos] = useState<Proyecto[]>([]);
  const [canales, definirCanales] = useState<CanalNotificacion[]>([]);
  const [proyectoId, definirProyectoId] = useState("");
  const [tipo, definirTipo] = useState<"webhook" | "correo">("webhook");
  const [nombre, definirNombre] = useState("");
  const [destino, definirDestino] = useState("");
  const avisos = useAvisos();

  async function cargarCanales(proyecto: string) {
    if (!proyecto) {
      definirCanales([]);
      return;
    }
    const respuesta = await solicitar<RespuestaLista<CanalNotificacion>>(`/api/proyectos/${proyecto}/canales-notificacion`);
    definirCanales(respuesta.elementos);
  }

  useEffect(() => {
    solicitar<RespuestaLista<Proyecto>>("/api/proyectos").then((respuesta) => {
      definirProyectos(respuesta.elementos);
      const primerProyecto = respuesta.elementos[0]?.id ?? "";
      definirProyectoId(primerProyecto);
      cargarCanales(primerProyecto).catch((error: Error) => avisos.error(error.message));
    });
  }, []);

  useEffect(() => {
    cargarCanales(proyectoId).catch((error: Error) => avisos.error(error.message));
  }, [proyectoId]);

  async function crearCanal() {
    const configuracion = tipo === "webhook"
      ? { url: destino, metodo: "POST" }
      : { destinatarios: destino.split(",").map((valor) => valor.trim()).filter(Boolean), tls: false };
    await solicitar<CanalNotificacion>(`/api/proyectos/${proyectoId}/canales-notificacion`, {
      method: "POST",
      body: JSON.stringify({ nombre, tipo, configuracion })
    });
    avisos.exito("Canal registrado con configuración cifrada.");
    await cargarCanales(proyectoId);
  }

  async function probarCanal(canalId: string) {
    const respuesta = await solicitar<{ estado: string; codigo_estado?: number }>(`/api/canales-notificacion/${canalId}/probar`, { method: "POST" });
    avisos.info(`Prueba finalizada: ${respuesta.estado}${respuesta.codigo_estado ? ` HTTP ${respuesta.codigo_estado}` : ""}`);
  }

  return (
    <MarcoModulo titulo="Notificaciones" descripcion="Configure correo o webhook sin exponer secretos ni encabezados sensibles.">
      <section className="panel-doble">
        <form className="formulario compacto" onSubmit={(evento) => { evento.preventDefault(); crearCanal().catch((error: Error) => avisos.error(error.message)); }}>
          <label>Proyecto<select value={proyectoId} onChange={(evento) => definirProyectoId(evento.target.value)}>{proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}</select></label>
          <label>Nombre<input value={nombre} onChange={(evento) => definirNombre(evento.target.value)} placeholder="Nombre del canal" /></label>
          <label>Tipo<select value={tipo} onChange={(evento) => definirTipo(evento.target.value as "webhook" | "correo")}><option value="webhook">Webhook</option><option value="correo">Correo</option></select></label>
          <label>{tipo === "webhook" ? "URL del webhook" : "Destinatarios separados por coma"}<input value={destino} onChange={(evento) => definirDestino(evento.target.value)} placeholder={tipo === "webhook" ? "https://..." : "qa@example.com"} /></label>
          <button type="submit">Guardar canal</button>
        </form>
        <section className="tabla-panel">
          <table><thead><tr><th>Canal</th><th>Tipo</th><th>Acción</th></tr></thead><tbody>{canales.map((canal) => <tr key={canal.id}><td>{canal.nombre}</td><td>{canal.tipo}</td><td><button className="secundario" onClick={() => probarCanal(canal.id).catch((error: Error) => avisos.error(error.message))}>Enviar prueba</button></td></tr>)}</tbody></table>
        </section>
      </section>
    </MarcoModulo>
  );
}
