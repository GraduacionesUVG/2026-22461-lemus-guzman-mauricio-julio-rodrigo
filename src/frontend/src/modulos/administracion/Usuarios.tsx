import { KeyRound, Save, Search } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { solicitar } from "../../api/cliente";
import { Mensaje } from "../../componentes/Mensaje";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { RespuestaLista, Rol, UsuarioSesion } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

type FormularioUsuario = {
  nombre: string;
  correo: string;
  contrasena: string;
  rol: string;
  activo: boolean;
};

const formularioInicial: FormularioUsuario = {
  nombre: "",
  correo: "",
  contrasena: "",
  rol: "qa",
  activo: true
};

function formatearFecha(valor?: string) {
  if (!valor) {
    return "No disponible";
  }
  return new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeStyle: "short" }).format(new Date(valor));
}

export function Usuarios() {
  const [usuarios, definirUsuarios] = useState<UsuarioSesion[]>([]);
  const [roles, definirRoles] = useState<Rol[]>([]);
  const [busqueda, definirBusqueda] = useState("");
  const [formulario, definirFormulario] = useState<FormularioUsuario>(formularioInicial);
  const [usuarioSeleccionado, definirUsuarioSeleccionado] = useState<UsuarioSesion | null>(null);
  const [nuevaContrasena, definirNuevaContrasena] = useState("");
  const avisos = useAvisos();

  async function cargarDatos() {
    const [respuestaUsuarios, respuestaRoles] = await Promise.all([
      solicitar<RespuestaLista<UsuarioSesion>>("/api/usuarios"),
      solicitar<RespuestaLista<Rol>>("/api/usuarios/roles")
    ]);
    definirUsuarios(respuestaUsuarios.elementos);
    definirRoles(respuestaRoles.elementos);
  }

  useEffect(() => {
    cargarDatos().catch((error: Error) => avisos.error(error.message));
  }, []);

  const usuariosFiltrados = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    if (!termino) {
      return usuarios;
    }
    return usuarios.filter((usuario) => `${usuario.nombre} ${usuario.correo} ${usuario.roles.join(" ")}`.toLowerCase().includes(termino));
  }, [busqueda, usuarios]);

  function seleccionarUsuario(usuario: UsuarioSesion) {
    definirUsuarioSeleccionado(usuario);
    definirFormulario({
      nombre: usuario.nombre,
      correo: usuario.correo,
      contrasena: "",
      rol: usuario.roles[0] ?? "qa",
      activo: Boolean(usuario.activo)
    });
    definirNuevaContrasena("");
  }

  function limpiarFormulario() {
    definirUsuarioSeleccionado(null);
    definirFormulario(formularioInicial);
    definirNuevaContrasena("");
  }

  async function guardarUsuario(evento: FormEvent) {
    evento.preventDefault();
    const cuerpo = {
      nombre: formulario.nombre,
      correo: formulario.correo,
      contrasena: formulario.contrasena,
      roles: [formulario.rol],
      activo: formulario.activo
    };
    if (usuarioSeleccionado) {
      await solicitar(`/api/usuarios/${usuarioSeleccionado.id}`, {
        method: "PATCH",
        body: JSON.stringify({ nombre: formulario.nombre, roles: [formulario.rol], activo: formulario.activo })
      });
      avisos.exito("Usuario actualizado correctamente.");
    } else {
      await solicitar("/api/usuarios", { method: "POST", body: JSON.stringify(cuerpo) });
      avisos.exito("Usuario creado correctamente.");
    }
    limpiarFormulario();
    await cargarDatos();
  }

  async function restablecerContrasena() {
    if (!usuarioSeleccionado || !nuevaContrasena.trim()) {
      avisos.advertencia("Ingrese una contraseña temporal para restablecerla.");
      return;
    }
    await solicitar(`/api/usuarios/${usuarioSeleccionado.id}/restablecer-contrasena`, {
      method: "POST",
      body: JSON.stringify({ contrasena: nuevaContrasena })
    });
    definirNuevaContrasena("");
    avisos.exito("Contraseña restablecida correctamente.");
  }

  return (
    <MarcoModulo titulo="Usuarios" descripcion="Administre accesos, roles y estado de usuarios de la plataforma.">
      <section className="panel-doble">
        <form className="formulario compacto" onSubmit={(evento) => guardarUsuario(evento).catch((error: Error) => avisos.error(error.message))}>
          <h3>{usuarioSeleccionado ? "Editar usuario" : "Crear usuario"}</h3>
          <label>Nombre<input value={formulario.nombre} onChange={(evento) => definirFormulario({ ...formulario, nombre: evento.target.value })} required /></label>
          <label>Correo<input value={formulario.correo} onChange={(evento) => definirFormulario({ ...formulario, correo: evento.target.value })} type="email" required disabled={Boolean(usuarioSeleccionado)} /></label>
          {!usuarioSeleccionado && <label>Contraseña temporal<input value={formulario.contrasena} onChange={(evento) => definirFormulario({ ...formulario, contrasena: evento.target.value })} type="password" required /></label>}
          <label>
            Rol
            <select value={formulario.rol} onChange={(evento) => definirFormulario({ ...formulario, rol: evento.target.value })}>
              {roles.map((rol) => <option key={rol.id} value={rol.nombre}>{rol.nombre}</option>)}
            </select>
          </label>
          <label className="checkbox-linea">
            <input type="checkbox" checked={formulario.activo} onChange={(evento) => definirFormulario({ ...formulario, activo: evento.target.checked })} />
            Usuario activo
          </label>
          <div className="botones-linea">
            <button type="submit"><Save size={16} />Guardar</button>
            <button type="button" className="secundario" onClick={limpiarFormulario}>Nuevo</button>
          </div>
          {usuarioSeleccionado && (
            <div className="restablecer-clave">
              <label>Nueva contraseña temporal<input value={nuevaContrasena} onChange={(evento) => definirNuevaContrasena(evento.target.value)} type="password" /></label>
              <button type="button" className="secundario" onClick={() => restablecerContrasena().catch((error: Error) => avisos.error(error.message))}><KeyRound size={16} />Restablecer</button>
            </div>
          )}
        </form>
        <div className="tabla-panel">
          <label className="busqueda">
            <Search size={16} />
            <input value={busqueda} onChange={(evento) => definirBusqueda(evento.target.value)} placeholder="Buscar por nombre, correo o rol" />
          </label>
          <table>
            <thead><tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Último acceso</th><th>Creación</th></tr></thead>
            <tbody>
              {usuariosFiltrados.map((usuario) => (
                <tr key={usuario.id} onClick={() => seleccionarUsuario(usuario)}>
                  <td><strong>{usuario.nombre}</strong><small>{usuario.correo}</small></td>
                  <td>{usuario.roles.join(", ")}</td>
                  <td>{usuario.activo ? "Activo" : "Inactivo"}</td>
                  <td>{formatearFecha(usuario.ultimo_acceso)}</td>
                  <td>{formatearFecha(usuario.creado_en)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {usuariosFiltrados.length === 0 && <Mensaje variante="info">No hay usuarios para la búsqueda actual.</Mensaje>}
        </div>
      </section>
    </MarcoModulo>
  );
}
