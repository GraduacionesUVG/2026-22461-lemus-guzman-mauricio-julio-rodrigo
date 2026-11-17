import { useEffect, useState } from "react";
import { construirUrlApi, solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";

type MetricasResumen = Record<string, number>;

export function Metricas() {
  const [metricas, definirMetricas] = useState<MetricasResumen>({});

  useEffect(() => {
    solicitar<MetricasResumen>("/api/metricas/resumen").then(definirMetricas);
  }, []);

  function descargarReporte() {
    window.open(construirUrlApi("/api/metricas/reporte-evaluacion.csv"), "_blank");
  }

  return (
    <MarcoModulo titulo="Métricas" descripcion="Indicadores evaluables para la comparación académica del proceso.">
      <section className="botones-linea">
        <button type="button" onClick={descargarReporte}>Descargar reporte CSV</button>
      </section>
      <section className="metricas-grid">
        {Object.entries(metricas).map(([nombre, valor]) => <article key={nombre}><span>{nombre.replaceAll("_", " ")}</span><strong>{valor}</strong></article>)}
      </section>
    </MarcoModulo>
  );
}
