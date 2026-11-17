import { useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Entorno, Monitor, Proyecto, RespuestaLista, Secreto } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

export function Monitores() {
  const [proyectos, definirProyectos] = useState<Proyecto[]>([]);
  const [entornos, definirEntornos] = useState<Entorno[]>([]);
  const [secretos, definirSecretos] = useState<Secreto[]>([]);
  const [monitores, definirMonitores] = useState<Monitor[]>([]);
  const [proyectoId, definirProyectoId] = useState("");
  const [entornoId, definirEntornoId] = useState("");
  const [nombre, definirNombre] = useState("");
  const [tipo, definirTipo] = useState("http");
  const [ruta, definirRuta] = useState("/health");
  const [urlApi, definirUrlApi] = useState("");
  const [hostTcp, definirHostTcp] = useState("localhost");
  const [puertoTcp, definirPuertoTcp] = useState(5000);
  const [consulta, definirConsulta] = useState("SELECT 1");
  const [cadenaConexion, definirCadenaConexion] = useState("sqlite://");
  const [secretoId, definirSecretoId] = useState("");
  const avisos = useAvisos();

  async function cargarMonitores() {
    const respuesta = await solicitar<RespuestaLista<Monitor>>("/api/monitores");
    definirMonitores(respuesta.elementos);
  }

  useEffect(() => {
    solicitar<RespuestaLista<Proyecto>>("/api/proyectos").then((respuesta) => {
      definirProyectos(respuesta.elementos);
      definirProyectoId(respuesta.elementos[0]?.id ?? "");
    });
    cargarMonitores().catch((error: Error) => avisos.error(error.message));
  }, []);

  useEffect(() => {
    if (!proyectoId) {
      return;
    }
    solicitar<RespuestaLista<Entorno>>(`/api/proyectos/${proyectoId}/entornos`).then((respuesta) => {
      definirEntornos(respuesta.elementos);
      definirEntornoId(respuesta.elementos[0]?.id ?? "");
    });
    solicitar<RespuestaLista<Secreto>>(`/api/proyectos/${proyectoId}/secretos`).then((respuesta) => {
      definirSecretos(respuesta.elementos);
      definirSecretoId(respuesta.elementos[0]?.id ?? "");
    }).catch(() => {
      definirSecretos([]);
      definirSecretoId("");
    });
  }, [proyectoId]);

  function construirConfiguracion() {
    if (tipo === "api") {
      return { url: urlApi, metodo: "GET", estados_esperados: [200] };
    }
    if (tipo === "tcp") {
      return { host: hostTcp, puerto: puertoTcp, tiempo_espera: 5 };
    }
    if (tipo === "base_datos") {
      return secretoId ? { consulta, secreto_cadena_conexion_id: secretoId } : { consulta, cadena_conexion: cadenaConexion };
    }
    return { ruta, metodo: "GET", estados_esperados: [200], tiempo_maximo_milisegundos: 2000 };
  }

  async function crearMonitor() {
    await solicitar<Monitor>("/api/monitores", {
      method: "POST",
      body: JSON.stringify({
        proyecto_id: proyectoId,
        entorno_id: entornoId,
        nombre,
        tipo,
        configuracion: construirConfiguracion()
      })
    });
    avisos.exito("Monitor creado.");
    await cargarMonitores();
  }

  async function ejecutarMonitor(monitorId: string) {
    const resultado = await solicitar<{ estado: string; mensaje: string }>(`/api/monitores/${monitorId}/ejecutar`, { method: "POST", body: JSON.stringify({ entorno_id: entornoId }) });
    avisos.info(`${resultado.mensaje}: ${resultado.estado}`);
  }

  return (
    <MarcoModulo titulo="Monitores" descripcion="Valide disponibilidad HTTP, API y TCP desde fuera del sistema objetivo.">
      <section className="formulario compacto">
        <label>Proyecto<select value={proyectoId} onChange={(evento) => definirProyectoId(evento.target.value)}>{proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}</select></label>
        <label>Entorno<select value={entornoId} onChange={(evento) => definirEntornoId(evento.target.value)}>{entornos.map((entorno) => <option key={entorno.id} value={entorno.id}>{entorno.nombre}</option>)}</select></label>
        <label>Nombre<input value={nombre} onChange={(evento) => definirNombre(evento.target.value)} placeholder="Nombre del monitor" /></label>
        <label>Tipo<select value={tipo} onChange={(evento) => definirTipo(evento.target.value)}><option value="http">HTTP</option><option value="api">API</option><option value="tcp">TCP</option><option value="base_datos">Base de datos</option></select></label>
        {tipo === "http" && <label>Ruta<input value={ruta} onChange={(evento) => definirRuta(evento.target.value)} /></label>}
        {tipo === "api" && <label>URL API<input value={urlApi} onChange={(evento) => definirUrlApi(evento.target.value)} placeholder="https://api.example.com/estado" /></label>}
        {tipo === "tcp" && <section className="panel-doble"><label>Host<input value={hostTcp} onChange={(evento) => definirHostTcp(evento.target.value)} /></label><label>Puerto<input type="number" min={1} value={puertoTcp} onChange={(evento) => definirPuertoTcp(Number(evento.target.value))} /></label></section>}
        {tipo === "base_datos" && <><label>Consulta<input value={consulta} onChange={(evento) => definirConsulta(evento.target.value)} /></label><label>Secreto de conexión<select value={secretoId} onChange={(evento) => definirSecretoId(evento.target.value)}><option value="">Usar cadena directa</option>{secretos.map((secreto) => <option key={secreto.id} value={secreto.id}>{secreto.nombre}</option>)}</select></label>{!secretoId && <label>Cadena directa<input value={cadenaConexion} onChange={(evento) => definirCadenaConexion(evento.target.value)} /></label>}</>}
        <button type="button" onClick={() => crearMonitor().catch((error: Error) => avisos.error(error.message))}>Crear monitor</button>
      </section>
      <section className="tabla-panel">
        <table><thead><tr><th>Monitor</th><th>Tipo</th><th>Acción</th></tr></thead><tbody>{monitores.map((monitor) => <tr key={monitor.id}><td>{monitor.nombre}</td><td>{monitor.tipo}</td><td><button className="secundario" onClick={() => ejecutarMonitor(monitor.id).catch((error: Error) => avisos.error(error.message))}>Probar conexión</button></td></tr>)}</tbody></table>
      </section>
    </MarcoModulo>
  );
}
