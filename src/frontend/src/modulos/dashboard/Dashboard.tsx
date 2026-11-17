import { Activity, Database, ShieldQuestion, Timer } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { solicitar } from "../../api/cliente";
import { EstadoVacio } from "../../componentes/EstadoVacio";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { Mensaje } from "../../componentes/Mensaje";
import { TablaEjecuciones } from "../../componentes/TablaEjecuciones";
import { Ejecucion, RespuestaLista } from "../../tipos/dominio";
import { etiquetaEstado, ESTADOS_EJECUCION } from "../../utilidades/estado";
import { duracionLegible, etiquetaZonaHoraria } from "../../utilidades/fechas";

type ResumenMetricas = {
  ejecuciones: number;
  porcentaje_ejecuciones_tecnicamente_correctas: number;
  porcentaje_resultados_almacenados: number;
  porcentaje_fallos_con_evidencia: number;
  tasa_falsos_positivos: number;
  disponibilidad_notificaciones?: number;
  cobertura_modulos_criticos: number;
  tiempo_promedio_deteccion_milisegundos?: number;
};

const EJECUCIONES_RECIENTES = 8;

const COLORES_ESTADO: Record<string, string> = {
  exitosa: "#15803d",
  fallida: "#b42318",
  error_tecnico: "#b45309",
  en_cola: "#2563eb",
  en_ejecucion: "#0e7490",
  cancelada: "#64748b"
};

function porcentajeTexto(valor?: number | null) {
  if (valor === undefined || valor === null) {
    return "—";
  }
  return `${valor.toLocaleString("es-GT", { maximumFractionDigits: 1 })} %`;
}

function TarjetaIndicador({ etiqueta, valor, descripcion, icono, nota }: { etiqueta: string; valor: string; descripcion: string; icono: ReactNode; nota?: string }) {
  return (
    <article className="indicador">
      <div className="indicador-cabecera">
        <span className="indicador-etiqueta">{etiqueta}</span>
        <span className="indicador-icono" aria-hidden="true">{icono}</span>
      </div>
      <strong className="indicador-valor">{valor}</strong>
      <p className="indicador-descripcion">{descripcion}</p>
      {nota && <p className="indicador-nota">{nota}</p>}
    </article>
  );
}

function MedidorPorcentaje({ etiqueta, valor, descripcion }: { etiqueta: string; valor?: number; descripcion: string }) {
  const ancho = Math.max(0, Math.min(valor ?? 0, 100));
  return (
    <li className="medidor">
      <div className="medidor-cabecera">
        <span>{etiqueta}</span>
        <strong>{porcentajeTexto(valor)}</strong>
      </div>
      <div className="medidor-pista" aria-hidden="true">
        <div className="medidor-barra" style={{ width: `${ancho}%` }} />
      </div>
      <p>{descripcion}</p>
    </li>
  );
}

export function Dashboard() {
  const [metricas, definirMetricas] = useState<ResumenMetricas | null>(null);
  const [ejecuciones, definirEjecuciones] = useState<Ejecucion[]>([]);
  const [cargando, definirCargando] = useState(true);
  const [errorCarga, definirErrorCarga] = useState(false);
  const navegar = useNavigate();

  useEffect(() => {
    function actualizar() {
      Promise.all([
        solicitar<ResumenMetricas>("/api/metricas/resumen").then(definirMetricas),
        solicitar<RespuestaLista<Ejecucion>>("/api/ejecuciones").then((respuesta) => definirEjecuciones(respuesta.elementos))
      ])
        .then(() => definirErrorCarga(false))
        .catch(() => definirErrorCarga(true))
        .finally(() => definirCargando(false));
    }
    actualizar();
    window.addEventListener("focus", actualizar);
    const intervalo = window.setInterval(actualizar, 15000);
    return () => {
      window.removeEventListener("focus", actualizar);
      window.clearInterval(intervalo);
    };
  }, []);

  const distribucionEstados = useMemo(() => {
    const conteo = new Map<string, number>();
    ejecuciones.forEach((ejecucion) => conteo.set(ejecucion.estado, (conteo.get(ejecucion.estado) ?? 0) + 1));
    const orden = [...ESTADOS_EJECUCION, ...[...conteo.keys()].filter((estado) => !ESTADOS_EJECUCION.includes(estado))];
    return orden
      .filter((estado) => (conteo.get(estado) ?? 0) > 0)
      .map((estado) => ({ estado, etiqueta: etiquetaEstado(estado), cantidad: conteo.get(estado) ?? 0 }));
  }, [ejecuciones]);

  const resumenDistribucion = distribucionEstados.map((dato) => `${dato.etiqueta}: ${dato.cantidad}`).join(", ");
  const recientes = ejecuciones.slice(0, EJECUCIONES_RECIENTES);
  const sinDato = cargando && !metricas;

  return (
    <MarcoModulo titulo="Dashboard" descripcion="Estado general de la plataforma, indicadores de calidad y ejecuciones recientes.">
      {errorCarga && <Mensaje variante="advertencia" titulo="Datos sin actualizar">No se pudo actualizar el panel. Se reintentará automáticamente.</Mensaje>}

      <section className="indicadores-grid" aria-label="Indicadores principales" aria-busy={sinDato}>
        <TarjetaIndicador
          etiqueta="Ejecuciones registradas"
          valor={sinDato ? "—" : (metricas?.ejecuciones ?? 0).toLocaleString("es-GT")}
          descripcion="Total histórico de ejecuciones de pipelines."
          icono={<Activity size={16} />}
        />
        <TarjetaIndicador
          etiqueta="Resultados almacenados"
          valor={sinDato ? "—" : porcentajeTexto(metricas?.porcentaje_resultados_almacenados)}
          descripcion="Pasos ejecutados con resultado persistido."
          icono={<Database size={16} />}
        />
        <TarjetaIndicador
          etiqueta="Tiempo promedio de detección"
          valor={sinDato ? "—" : duracionLegible(metricas?.tiempo_promedio_deteccion_milisegundos ? Math.round(metricas.tiempo_promedio_deteccion_milisegundos) : metricas?.tiempo_promedio_deteccion_milisegundos)}
          descripcion="Duración media de ejecuciones con al menos un fallo detectado."
          icono={<Timer size={16} />}
        />
        <TarjetaIndicador
          etiqueta="Falsos positivos"
          valor={sinDato ? "—" : porcentajeTexto(metricas?.tasa_falsos_positivos)}
          descripcion="Proporción sobre revisiones humanas concluyentes."
          nota="Indicador referencial: depende de clasificaciones manuales no validadas experimentalmente."
          icono={<ShieldQuestion size={16} />}
        />
      </section>

      <section className="paneles-analiticos">
        <article className="panel">
          <header className="panel-cabecera">
            <div>
              <h2>Indicadores de calidad</h2>
              <p>Porcentajes calculados sobre los registros históricos. Escala de 0 a 100 %.</p>
            </div>
          </header>
          <ul className="medidores">
            <MedidorPorcentaje
              etiqueta="Ejecución técnicamente correcta"
              valor={metricas?.porcentaje_ejecuciones_tecnicamente_correctas}
              descripcion="Ejecuciones que concluyeron como exitosas o fallidas, sin error técnico."
            />
            <MedidorPorcentaje
              etiqueta="Fallos con evidencia"
              valor={metricas?.porcentaje_fallos_con_evidencia}
              descripcion="Evidencias almacenadas respecto de pasos fallidos o con error técnico. Puede superar 100 % cuando un fallo conserva varias capturas."
            />
            <MedidorPorcentaje
              etiqueta="Cobertura de módulos críticos"
              valor={metricas?.cobertura_modulos_criticos}
              descripcion="Módulos críticos activos con al menos un caso de prueba activo."
            />
            <MedidorPorcentaje
              etiqueta="Notificaciones entregadas"
              valor={metricas?.disponibilidad_notificaciones}
              descripcion="Notificaciones con estado enviada respecto del total registrado."
            />
          </ul>
        </article>

        <article className="panel">
          <header className="panel-cabecera">
            <div>
              <h2>Ejecuciones por estado</h2>
              <p>Cantidad de ejecuciones entre las {ejecuciones.length} más recientes consultadas.</p>
            </div>
          </header>
          {distribucionEstados.length > 0 ? (
            <figure className="figura-grafica" aria-label={`Ejecuciones por estado. ${resumenDistribucion}.`}>
              <ResponsiveContainer width="100%" height={Math.max(150, distribucionEstados.length * 44 + 40)}>
                <BarChart data={distribucionEstados} layout="vertical" margin={{ top: 4, right: 36, bottom: 18, left: 8 }}>
                  <CartesianGrid horizontal={false} stroke="#e7edf3" />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: "#516275", fontSize: 12 }} label={{ value: "Cantidad de ejecuciones", position: "insideBottom", offset: -10, fill: "#516275", fontSize: 12 }} />
                  <YAxis type="category" dataKey="etiqueta" width={104} tick={{ fill: "#14213d", fontSize: 12 }} />
                  <Tooltip cursor={{ fill: "#f1f5f9" }} formatter={(valor: number) => [`${valor} ejecuciones`, "Cantidad"]} />
                  <Bar dataKey="cantidad" barSize={18} radius={[0, 3, 3, 0]} isAnimationActive={false}>
                    {distribucionEstados.map((dato) => <Cell key={dato.estado} fill={COLORES_ESTADO[dato.estado] ?? "#64748b"} />)}
                    <LabelList dataKey="cantidad" position="right" fill="#14213d" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <figcaption className="solo-lectores">{resumenDistribucion}</figcaption>
            </figure>
          ) : (
            <EstadoVacio titulo={cargando ? "Cargando ejecuciones" : "Sin ejecuciones"} descripcion={cargando ? "Consultando el historial." : "Aún no hay ejecuciones registradas."} />
          )}
        </article>
      </section>

      <section className="panel">
        <header className="panel-cabecera">
          <div>
            <h2>Ejecuciones recientes</h2>
            <p>{etiquetaZonaHoraria()}</p>
          </div>
          <button type="button" className="secundario compacto" onClick={() => navegar("/ejecuciones")}>Ver historial completo</button>
        </header>
        {recientes.length > 0 ? (
          <TablaEjecuciones
            ejecuciones={recientes}
            descripcion="Ejecuciones recientes"
            alAbrir={(id) => navegar(`/ejecuciones?id=${id}`)}
          />
        ) : (
          <EstadoVacio titulo={cargando ? "Cargando ejecuciones" : "Sin ejecuciones"} descripcion={cargando ? "Consultando el historial." : "Las ejecuciones aparecerán aquí al ejecutar un pipeline."} />
        )}
      </section>
    </MarcoModulo>
  );
}
