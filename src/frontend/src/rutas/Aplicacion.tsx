import { Activity, Bell, CalendarClock, ClipboardCheck, Gauge, GitBranch, HelpCircle, History, LayoutDashboard, LogOut, MessageSquareWarning, MonitorCheck, Settings, ShieldCheck, Users } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { solicitar } from "../api/cliente";
import { TourInicial } from "../componentes/TourInicial";
import { Usuarios } from "../modulos/administracion/Usuarios";
import { Alertas } from "../modulos/alertas/Alertas";
import { ConstructorPruebas } from "../modulos/casos-prueba/ConstructorPruebas";
import { Dashboard } from "../modulos/dashboard/Dashboard";
import { Ejecuciones } from "../modulos/ejecuciones/Ejecuciones";
import { Metricas } from "../modulos/metricas/Metricas";
import { Monitores } from "../modulos/monitores/Monitores";
import { Notificaciones } from "../modulos/notificaciones/Notificaciones";
import { Pipelines } from "../modulos/pipelines/Pipelines";
import { Programaciones } from "../modulos/programaciones/Programaciones";
import { Proyectos } from "../modulos/proyectos/Proyectos";
import { Yaml } from "../modulos/yaml/Yaml";
import { UsuarioSesion } from "../tipos/dominio";

type Sesion = {
  usuario: UsuarioSesion;
};

const navegacion = [
  { ruta: "/", etiqueta: "Dashboard", icono: LayoutDashboard },
  { ruta: "/proyectos", etiqueta: "Proyectos", icono: ShieldCheck },
  { ruta: "/pruebas", etiqueta: "Pruebas", icono: ClipboardCheck },
  { ruta: "/monitores", etiqueta: "Monitores", icono: MonitorCheck },
  { ruta: "/pipelines", etiqueta: "Pipelines", icono: GitBranch },
  { ruta: "/programaciones", etiqueta: "Programaciones", icono: CalendarClock },
  { ruta: "/ejecuciones", etiqueta: "Ejecuciones", icono: History },
  { ruta: "/alertas", etiqueta: "Alertas", icono: Bell },
  { ruta: "/notificaciones", etiqueta: "Notificaciones", icono: MessageSquareWarning, administrador: true },
  { ruta: "/metricas", etiqueta: "Métricas", icono: Gauge },
  { ruta: "/yaml", etiqueta: "YAML", icono: Settings },
  { ruta: "/administracion/usuarios", etiqueta: "Usuarios", icono: Users, administrador: true }
];

function InicioSesion({ alEntrar }: { alEntrar: (usuario: UsuarioSesion) => void }) {
  const [correo, definirCorreo] = useState("usuario@example.invalid");
  const [contrasena, definirContrasena] = useState("");
  const [error, definirError] = useState("");

  async function enviarFormulario(evento: FormEvent) {
    evento.preventDefault();
    definirError("");
    try {
      const respuesta = await solicitar<Sesion>("/api/autenticacion/iniciar-sesion", {
        method: "POST",
        body: JSON.stringify({ correo, contrasena })
      });
      alEntrar(respuesta.usuario);
    } catch (fallo) {
      definirError(fallo instanceof Error ? fallo.message : "No se pudo iniciar sesion.");
    }
  }

  return (
    <main className="pantalla-login">
      <section className="login-panel">
        <div className="marca">
          <Activity size={32} />
          <div>
            <h1>Sistema Integral de Calidad Web</h1>
            <p>Control operativo de pruebas, monitores y evidencias.</p>
          </div>
        </div>
        <form onSubmit={enviarFormulario} className="formulario">
          <label>
            Correo
            <input value={correo} onChange={(evento) => definirCorreo(evento.target.value)} type="email" required />
          </label>
          <label>
            Contraseña
            <input value={contrasena} onChange={(evento) => definirContrasena(evento.target.value)} type="password" required />
          </label>
          {error && <p className="mensaje-error">{error}</p>}
          <button type="submit">Iniciar sesión</button>
        </form>
      </section>
    </main>
  );
}

export function Aplicacion() {
  const [usuario, definirUsuario] = useState<UsuarioSesion | null>(null);
  const [cargando, definirCargando] = useState(true);
  const [tourVisible, definirTourVisible] = useState(false);
  const [pasoTour, definirPasoTour] = useState(0);
  const navegar = useNavigate();

  useEffect(() => {
    solicitar<Sesion>("/api/autenticacion/sesion-actual")
      .then((respuesta) => {
        definirUsuario(respuesta.usuario);
        definirTourVisible(!respuesta.usuario.tour_completado);
      })
      .catch(() => definirUsuario(null))
      .finally(() => definirCargando(false));
  }, []);

  const iniciales = useMemo(() => usuario?.nombre.split(" ").map((parte) => parte[0]).join("").slice(0, 2) ?? "QA", [usuario]);
  const esAdministrador = usuario?.roles.includes("administrador") ?? false;
  const navegacionPermitida = useMemo(() => navegacion.filter((elemento) => !elemento.administrador || esAdministrador), [esAdministrador]);

  async function cerrarSesion() {
    await solicitar("/api/autenticacion/cerrar-sesion", { method: "POST" });
    definirUsuario(null);
    navegar("/");
  }

  async function finalizarTour() {
    definirTourVisible(false);
    definirPasoTour(0);
    const respuesta = await solicitar<Sesion>("/api/autenticacion/preferencias", {
      method: "PATCH",
      body: JSON.stringify({ tour_completado: true })
    });
    definirUsuario(respuesta.usuario);
  }

  if (cargando) {
    return <main className="estado-inicial">Cargando plataforma</main>;
  }

  if (!usuario) {
    return <InicioSesion alEntrar={definirUsuario} />;
  }

  return (
    <div className="aplicacion">
      <aside className="barra-lateral">
        <div className="identidad">
          <Activity />
          <strong>Calidad Web</strong>
        </div>
        <nav>
          {navegacionPermitida.map((elemento) => {
            const Icono = elemento.icono;
            return (
              <NavLink key={elemento.ruta} to={elemento.ruta} end={elemento.ruta === "/"}>
                <Icono size={18} />
                <span>{elemento.etiqueta}</span>
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <div className="contenido">
        <header className="cabecera">
          <div>
            <h2>Centro de calidad y monitoreo</h2>
          </div>
          <div className="usuario">
            <span>{iniciales}</span>
            <div>
              <strong>{usuario.nombre}</strong>
              <small>{usuario.roles.join(", ")}</small>
            </div>
            <button className="boton-icono" onClick={cerrarSesion} aria-label="Cerrar sesión">
              <LogOut size={18} />
            </button>
            <button className="boton-icono" onClick={() => definirTourVisible(true)} aria-label="Ver tour nuevamente">
              <HelpCircle size={18} />
            </button>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/proyectos" element={<Proyectos />} />
          <Route path="/pruebas" element={<ConstructorPruebas />} />
          <Route path="/monitores" element={<Monitores />} />
          <Route path="/pipelines" element={<Pipelines />} />
          <Route path="/programaciones" element={<Programaciones />} />
          <Route path="/ejecuciones" element={<Ejecuciones />} />
          <Route path="/alertas" element={<Alertas />} />
          <Route path="/notificaciones" element={<Notificaciones />} />
          <Route path="/metricas" element={<Metricas />} />
          <Route path="/yaml" element={<Yaml />} />
          <Route path="/administracion/usuarios" element={esAdministrador ? <Usuarios /> : <Dashboard />} />
        </Routes>
      </div>
      {tourVisible && <TourInicial usuario={usuario} indice={pasoTour} alCambiarIndice={definirPasoTour} alFinalizar={() => finalizarTour().catch(() => definirTourVisible(false))} />}
    </div>
  );
}
