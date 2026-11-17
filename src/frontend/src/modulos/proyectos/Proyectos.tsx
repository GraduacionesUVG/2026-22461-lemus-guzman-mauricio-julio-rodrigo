import { useEffect, useState } from "react";
import { solicitar } from "../../api/cliente";
import { EstadoVacio } from "../../componentes/EstadoVacio";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Entorno, Proyecto, RespuestaLista, Secreto } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

export function Proyectos() {
  const [proyectos, definirProyectos] = useState<Proyecto[]>([]);
  const [entornos, definirEntornos] = useState<Entorno[]>([]);
  const [secretos, definirSecretos] = useState<Secreto[]>([]);
  const [proyectoActivo, definirProyectoActivo] = useState("");
  const [nombre, definirNombre] = useState("");
  const [urlBase, definirUrlBase] = useState("");
  const [nombreEntorno, definirNombreEntorno] = useState("");
  const [nombreSecreto, definirNombreSecreto] = useState("");
  const [valorSecreto, definirValorSecreto] = useState("");
  const avisos = useAvisos();

  async function cargarProyectos() {
    const respuesta = await solicitar<RespuestaLista<Proyecto>>("/api/proyectos");
    definirProyectos(respuesta.elementos);
    if (respuesta.elementos[0]) {
      definirProyectoActivo(respuesta.elementos[0].id);
    }
  }

  useEffect(() => {
    cargarProyectos().catch((error: Error) => avisos.error(error.message));
  }, []);

  useEffect(() => {
    if (!proyectoActivo) {
      definirEntornos([]);
      definirSecretos([]);
      return;
    }
    solicitar<RespuestaLista<Entorno>>(`/api/proyectos/${proyectoActivo}/entornos`)
      .then((respuesta) => definirEntornos(respuesta.elementos))
      .catch((error: Error) => avisos.error(error.message));
    cargarSecretos(proyectoActivo).catch((error: Error) => avisos.error(error.message));
  }, [proyectoActivo]);

  async function cargarSecretos(proyectoId = proyectoActivo) {
    if (!proyectoId) {
      definirSecretos([]);
      return;
    }
    const respuesta = await solicitar<RespuestaLista<Secreto>>(`/api/proyectos/${proyectoId}/secretos`);
    definirSecretos(respuesta.elementos);
  }

  async function crearProyecto() {
    const proyecto = await solicitar<Proyecto>("/api/proyectos", {
      method: "POST",
      body: JSON.stringify({ nombre, descripcion: "Proyecto creado desde asistente guiado", tecnologia_referencial: "Referencia opcional" })
    });
    definirNombre("");
    definirProyectoActivo(proyecto.id);
    await cargarProyectos();
  }

  async function crearEntorno() {
    if (!proyectoActivo) {
      return;
    }
    await solicitar<Entorno>(`/api/proyectos/${proyectoActivo}/entornos`, {
      method: "POST",
      body: JSON.stringify({ nombre: nombreEntorno.trim(), url_base: urlBase, zona_horaria: "America/Guatemala", tiempo_espera_segundos: 15 })
    });
    definirNombreEntorno("");
    definirUrlBase("");
    const respuesta = await solicitar<RespuestaLista<Entorno>>(`/api/proyectos/${proyectoActivo}/entornos`);
    definirEntornos(respuesta.elementos);
  }

  async function guardarSecreto() {
    if (!proyectoActivo) {
      return;
    }
    await solicitar(`/api/proyectos/${proyectoActivo}/secretos`, {
      method: "POST",
      body: JSON.stringify({ nombre: nombreSecreto.trim(), tipo: "password", valor: valorSecreto })
    });
    definirValorSecreto("");
    avisos.exito("Secreto guardado sin exponer su valor.");
    await cargarSecretos(proyectoActivo);
  }

  function nombreProyecto(proyectoId: string) {
    return proyectos.find((proyecto) => proyecto.id === proyectoId)?.nombre ?? "No disponible";
  }

  return (
    <MarcoModulo titulo="Proyectos" descripcion="Registre sistemas objetivo, entornos y secretos de forma guiada.">
      <section className="panel-doble">
        <form className="formulario compacto" onSubmit={(evento) => { evento.preventDefault(); crearProyecto().catch((error: Error) => avisos.error(error.message)); }}>
          <h3>Nuevo proyecto</h3>
          <label>
            Nombre del sistema
            <input value={nombre} onChange={(evento) => definirNombre(evento.target.value)} placeholder="Nombre del sistema evaluado" required />
          </label>
          <button type="submit">Crear proyecto</button>
        </form>
        <form className="formulario compacto" onSubmit={(evento) => { evento.preventDefault(); crearEntorno().catch((error: Error) => avisos.error(error.message)); }}>
          <h3>Entorno</h3>
          <label>
            Proyecto
            <select value={proyectoActivo} onChange={(evento) => definirProyectoActivo(evento.target.value)}>
              {proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}
            </select>
          </label>
          <label>
            Nombre del entorno
            <input value={nombreEntorno} onChange={(evento) => definirNombreEntorno(evento.target.value)} placeholder="Producción, pruebas o laboratorio" required />
          </label>
          <label>
            URL base
            <input value={urlBase} onChange={(evento) => definirUrlBase(evento.target.value)} placeholder="https://sistema.example.com" required />
          </label>
          <button type="submit">Guardar entorno</button>
        </form>
      </section>
      <section className="panel-doble">
        <form className="formulario compacto" onSubmit={(evento) => { evento.preventDefault(); guardarSecreto().catch((error: Error) => avisos.error(error.message)); }}>
          <h3>Secretos del proyecto</h3>
          <label>
            Proyecto
            <select value={proyectoActivo} onChange={(evento) => definirProyectoActivo(evento.target.value)} required>
              {proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}
            </select>
          </label>
          <label>
            Nombre del secreto
            <input value={nombreSecreto} onChange={(evento) => definirNombreSecreto(evento.target.value)} placeholder="Nombre interno del secreto" required />
          </label>
          <label>
            Valor
            <input type="password" value={valorSecreto} onChange={(evento) => definirValorSecreto(evento.target.value)} autoComplete="new-password" required />
          </label>
          <button type="submit">Guardar secreto</button>
        </form>
        <div className="tabla-panel">
          <h3>Secretos registrados</h3>
          {secretos.length === 0 ? <EstadoVacio titulo="Sin secretos" descripcion="Registre las credenciales requeridas por los pasos automatizados." /> : (
            <table>
              <thead><tr><th>Nombre</th><th>Proyecto</th><th>Actualizado</th></tr></thead>
              <tbody>{secretos.map((secreto) => (
                <tr key={secreto.id}>
                  <td>{secreto.nombre}</td>
                  <td>{nombreProyecto(secreto.proyecto_id)}</td>
                  <td>{secreto.actualizado_en ? new Date(secreto.actualizado_en).toLocaleString("es-GT") : "No disponible"}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </section>
      <section className="tabla-panel">
        {proyectos.length === 0 ? <EstadoVacio titulo="Sin proyectos" descripcion="Cree un proyecto para iniciar el flujo de calidad." /> : (
          <table>
            <thead><tr><th>Proyecto</th><th>Tecnología referencial</th><th>Estado</th></tr></thead>
            <tbody>{proyectos.map((proyecto) => <tr key={proyecto.id}><td>{proyecto.nombre}</td><td>{proyecto.tecnologia_referencial ?? "No indicada"}</td><td>{proyecto.activo ? "Activo" : "Inactivo"}</td></tr>)}</tbody>
          </table>
        )}
      </section>
      <section className="tabla-panel">
        <h3>Entornos del proyecto seleccionado</h3>
        <table>
          <tbody>{entornos.map((entorno) => <tr key={entorno.id}><td>{entorno.nombre}</td><td>{entorno.url_base}</td><td>{entorno.tiempo_espera_segundos}s</td></tr>)}</tbody>
        </table>
      </section>
    </MarcoModulo>
  );
}
