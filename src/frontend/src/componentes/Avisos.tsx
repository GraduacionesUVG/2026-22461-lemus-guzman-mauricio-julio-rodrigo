import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, KeyboardEvent, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

export type VarianteAviso = "exito" | "error" | "advertencia" | "info";

type Aviso = {
  id: number;
  variante: VarianteAviso;
  texto: string;
};

type ApiAvisos = {
  exito: (texto: string) => void;
  error: (texto: string) => void;
  advertencia: (texto: string) => void;
  info: (texto: string) => void;
};

const MAXIMO_AVISOS_VISIBLES = 4;

const DURACION_POR_VARIANTE: Record<VarianteAviso, number | null> = {
  exito: 4000,
  info: 4000,
  advertencia: 6000,
  error: null
};

const ICONOS = {
  exito: CheckCircle2,
  error: AlertCircle,
  advertencia: TriangleAlert,
  info: Info
};

const ETIQUETAS = {
  exito: "Éxito",
  error: "Error",
  advertencia: "Advertencia",
  info: "Información"
};

const ContextoAvisos = createContext<ApiAvisos | null>(null);

function TarjetaAviso({ aviso, alCerrar }: { aviso: Aviso; alCerrar: (id: number) => void }) {
  const [pausado, definirPausado] = useState(false);
  const Icono = ICONOS[aviso.variante];
  const duracion = DURACION_POR_VARIANTE[aviso.variante];

  useEffect(() => {
    if (duracion === null || pausado) {
      return;
    }
    const temporizador = window.setTimeout(() => alCerrar(aviso.id), duracion);
    return () => window.clearTimeout(temporizador);
  }, [aviso.id, duracion, pausado, alCerrar]);

  function cerrarConTeclado(evento: KeyboardEvent<HTMLDivElement>) {
    if (evento.key === "Escape") {
      alCerrar(aviso.id);
    }
  }

  return (
    <div
      className={`aviso aviso-${aviso.variante}`}
      role={aviso.variante === "error" ? "alert" : "status"}
      onMouseEnter={() => definirPausado(true)}
      onMouseLeave={() => definirPausado(false)}
      onFocus={() => definirPausado(true)}
      onBlur={() => definirPausado(false)}
      onKeyDown={cerrarConTeclado}
    >
      <Icono size={18} aria-hidden="true" className="aviso-icono" />
      <p className="aviso-texto">
        <span className="solo-lectores">{ETIQUETAS[aviso.variante]}: </span>
        {aviso.texto}
      </p>
      <button type="button" className="aviso-cerrar" onClick={() => alCerrar(aviso.id)} aria-label="Cerrar notificación">
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}

export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, definirAvisos] = useState<Aviso[]>([]);
  const siguienteId = useRef(0);

  const cerrar = useCallback((id: number) => {
    definirAvisos((actuales) => actuales.filter((aviso) => aviso.id !== id));
  }, []);

  const mostrar = useCallback((variante: VarianteAviso, texto: string) => {
    const contenido = texto.trim();
    if (!contenido) {
      return;
    }
    siguienteId.current += 1;
    const nuevo = { id: siguienteId.current, variante, texto: contenido };
    definirAvisos((actuales) => {
      const sinDuplicado = actuales.filter((aviso) => aviso.texto !== contenido || aviso.variante !== variante);
      return [...sinDuplicado, nuevo].slice(-MAXIMO_AVISOS_VISIBLES);
    });
  }, []);

  const api = useMemo<ApiAvisos>(() => ({
    exito: (texto) => mostrar("exito", texto),
    error: (texto) => mostrar("error", texto),
    advertencia: (texto) => mostrar("advertencia", texto),
    info: (texto) => mostrar("info", texto)
  }), [mostrar]);

  return (
    <ContextoAvisos.Provider value={api}>
      {children}
      <section className="avisos" aria-label="Notificaciones">
        {avisos.map((aviso) => <TarjetaAviso key={aviso.id} aviso={aviso} alCerrar={cerrar} />)}
      </section>
    </ContextoAvisos.Provider>
  );
}

export function useAvisos(): ApiAvisos {
  const contexto = useContext(ContextoAvisos);
  if (!contexto) {
    throw new Error("useAvisos debe utilizarse dentro de ProveedorAvisos.");
  }
  return contexto;
}
