import { useState } from "react";
import { CheckCircle2, FileSearch, UploadCloud } from "lucide-react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";

const ejemplo = `version: 1
proyecto:
  nombre: Portal de demostracion
entornos:
  - nombre: demostracion
    url_base: http://localhost:5000/demo-objetivo
casos_prueba:
  - nombre: Login demo
    pasos:
      - orden: 1
        tipo: navegar
        nombre: Abrir login
        configuracion:
          ruta: /login`;

type DiferenciaNombres = {
  nuevos: string[];
  coincidentes: string[];
  sin_cambios: string[];
};

type PrevisualizacionYaml = {
  valido: boolean;
  proyecto: {
    nombre: string;
    descripcion?: string;
    tecnologia_referencial?: string;
    responsable?: string;
  };
  resumen: Record<string, number>;
  comparacion: {
    proyecto: {
      nombre: string;
      accion: "crear_nuevo" | "crear_copia";
      id_existente?: string | null;
    };
    modulos_objetivo: DiferenciaNombres;
    entornos: DiferenciaNombres;
    casos_prueba: DiferenciaNombres;
    monitores: DiferenciaNombres;
    pipelines: DiferenciaNombres;
    programaciones: DiferenciaNombres;
  };
  advertencias: string[];
};

const etiquetasResumen: Record<string, string> = {
  modulos_objetivo: "Módulos",
  entornos: "Entornos",
  casos_prueba: "Casos",
  monitores: "Monitores",
  pipelines: "Pipelines",
  programaciones: "Programaciones",
  pasos_casos_prueba: "Pasos de casos",
  pasos_pipelines: "Pasos de pipelines"
};

const seccionesComparacion: Array<[keyof PrevisualizacionYaml["comparacion"], string]> = [
  ["modulos_objetivo", "Módulos"],
  ["entornos", "Entornos"],
  ["casos_prueba", "Casos"],
  ["monitores", "Monitores"],
  ["pipelines", "Pipelines"],
  ["programaciones", "Programaciones"]
];

function listaCompacta(elementos: string[]) {
  if (elementos.length === 0) return "Ninguno";
  if (elementos.length <= 3) return elementos.join(", ");
  return `${elementos.slice(0, 3).join(", ")} y ${elementos.length - 3} más`;
}

export function Yaml() {
  const [contenido, definirContenido] = useState(ejemplo);
  const [resultado, definirResultado] = useState("");
  const [previsualizacion, definirPrevisualizacion] = useState<PrevisualizacionYaml | null>(null);

  async function validar() {
    const respuesta = await solicitar<{ valido: boolean; resumen: Record<string, number> }>("/api/configuraciones-yaml/validar", { method: "POST", body: JSON.stringify({ contenido }) });
    definirResultado(`Configuración válida con ${respuesta.resumen.entornos} entornos y ${respuesta.resumen.casos_prueba} casos.`);
  }

  async function previsualizar() {
    const respuesta = await solicitar<PrevisualizacionYaml>("/api/configuraciones-yaml/previsualizar", { method: "POST", body: JSON.stringify({ contenido }) });
    definirPrevisualizacion(respuesta);
    definirResultado("Previsualización lista para confirmar.");
  }

  async function importar() {
    const respuesta = await solicitar<{ aplicado: boolean; proyecto_id: string }>("/api/configuraciones-yaml/importar", { method: "POST", body: JSON.stringify({ contenido }) });
    definirResultado(`Configuración importada en el proyecto ${respuesta.proyecto_id.slice(0, 8)}.`);
    definirPrevisualizacion(null);
  }

  return (
    <MarcoModulo titulo="Configuración YAML" descripcion="Valide configuración avanzada sin exportar ni mostrar secretos.">
      <section className="formulario">
        <textarea
          value={contenido}
          onChange={(evento) => {
            definirContenido(evento.target.value);
            definirPrevisualizacion(null);
          }}
          rows={16}
        />
        <div className="botones-linea">
          <button type="button" className="secundario" onClick={() => validar().catch((error: Error) => definirResultado(error.message))}>
            <CheckCircle2 size={18} />
            Validar configuración
          </button>
          <button type="button" onClick={() => previsualizar().catch((error: Error) => definirResultado(error.message))}>
            <FileSearch size={18} />
            Previsualizar importación
          </button>
          {previsualizacion && (
            <button type="button" onClick={() => importar().catch((error: Error) => definirResultado(error.message))}>
              <UploadCloud size={18} />
              Confirmar importación
            </button>
          )}
        </div>
        {resultado && <p className="mensaje-info">{resultado}</p>}
      </section>
      {previsualizacion && (
        <section className="detalle yaml-preview">
          <div className="yaml-preview-cabecera">
            <div>
              <span className="eyebrow">Proyecto</span>
              <h3>{previsualizacion.proyecto.nombre}</h3>
            </div>
            <span className={previsualizacion.comparacion.proyecto.accion === "crear_nuevo" ? "estado estado-exito" : "estado estado-advertencia"}>
              {previsualizacion.comparacion.proyecto.accion === "crear_nuevo" ? "Nuevo" : "Copia"}
            </span>
          </div>
          {previsualizacion.advertencias.length > 0 && (
            <div className="yaml-advertencias">
              {previsualizacion.advertencias.map((advertencia) => <p key={advertencia}>{advertencia}</p>)}
            </div>
          )}
          <div className="yaml-resumen">
            {Object.entries(etiquetasResumen).map(([clave, etiqueta]) => (
              <article key={clave}>
                <span>{etiqueta}</span>
                <strong>{previsualizacion.resumen[clave] ?? 0}</strong>
              </article>
            ))}
          </div>
          <table>
            <thead>
              <tr>
                <th>Elemento</th>
                <th>Nuevos</th>
                <th>Coincidentes</th>
                <th>Existentes fuera del YAML</th>
              </tr>
            </thead>
            <tbody>
              {seccionesComparacion.map(([clave, etiqueta]) => {
                const diferencia = previsualizacion.comparacion[clave] as DiferenciaNombres;
                return (
                  <tr key={clave}>
                    <td>{etiqueta}</td>
                    <td>{listaCompacta(diferencia.nuevos)}</td>
                    <td>{listaCompacta(diferencia.coincidentes)}</td>
                    <td>{listaCompacta(diferencia.sin_cambios)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </MarcoModulo>
  );
}
