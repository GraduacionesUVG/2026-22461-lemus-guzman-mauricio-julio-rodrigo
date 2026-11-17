import { ReactNode } from "react";

export function MarcoModulo({ titulo, descripcion, acciones, children }: { titulo: string; descripcion: string; acciones?: ReactNode; children: ReactNode }) {
  return (
    <main className="modulo">
      <div className="modulo-encabezado">
        <div>
          <h1>{titulo}</h1>
          <p>{descripcion}</p>
        </div>
        {acciones && <div className="acciones">{acciones}</div>}
      </div>
      {children}
    </main>
  );
}
