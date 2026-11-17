import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { UsuarioSesion } from "../tipos/dominio";

const pasosBase = [
  ["Dashboard", "Visualiza el estado general de ejecuciones, fallos, alertas y métricas recientes."],
  ["Proyectos", "Registra sistemas objetivo, entornos, URLs base y secretos protegidos."],
  ["Pruebas", "Diseña casos funcionales utilizando acciones de Selenium sin programar directamente."],
  ["Monitores", "Verifica automáticamente servicios HTTP, APIs, puertos TCP o bases de datos."],
  ["Pipelines", "Encadena pruebas y monitores para ejecutar flujos completos en orden definido."],
  ["Ejecuciones", "Consulta el historial, resultados por paso, evidencias y detalles técnicos."],
  ["Programaciones", "Define cuándo se ejecuta un pipeline con frecuencia, hora o intervalo."],
  ["Alertas", "Revisa fallos detectados, clasifica falsos positivos y navega hacia la evidencia."],
  ["Reportes", "Genera resúmenes y métricas para evaluar cobertura, fallos y trazabilidad."]
];

export function TourInicial({
  usuario,
  indice,
  alCambiarIndice,
  alFinalizar
}: {
  usuario: UsuarioSesion;
  indice: number;
  alCambiarIndice: (indice: number) => void;
  alFinalizar: () => void;
}) {
  const pasos = usuario.roles.includes("administrador") ? [...pasosBase, ["Administración", "Gestiona usuarios, roles, estado de acceso y contraseñas temporales."]] : pasosBase;
  const paso = pasos[indice] ?? pasos[0];
  const esPrimero = indice === 0;
  const esUltimo = indice === pasos.length - 1;

  return (
    <div className="tour-fondo" role="dialog" aria-modal="true" aria-label="Tour inicial">
      <section className="tour-panel">
        <button className="boton-icono tour-cerrar" onClick={alFinalizar} aria-label="Omitir tour"><X size={18} /></button>
        <span className="eyebrow">Guía inicial</span>
        <h2>{paso[0]}</h2>
        <p>{paso[1]}</p>
        <div className="tour-progreso">
          {pasos.map((item, posicion) => <span key={item[0]} className={posicion === indice ? "activo" : ""} />)}
        </div>
        <div className="botones-linea">
          <button type="button" className="secundario" onClick={() => alCambiarIndice(Math.max(0, indice - 1))} disabled={esPrimero}><ChevronLeft size={16} />Anterior</button>
          {esUltimo ? (
            <button type="button" onClick={alFinalizar}>Finalizar</button>
          ) : (
            <button type="button" onClick={() => alCambiarIndice(indice + 1)}>Siguiente<ChevronRight size={16} /></button>
          )}
        </div>
      </section>
    </div>
  );
}
