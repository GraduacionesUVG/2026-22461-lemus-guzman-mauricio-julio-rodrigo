export function EstadoVacio({ titulo, descripcion }: { titulo: string; descripcion: string }) {
  return (
    <div className="estado-vacio">
      <h3>{titulo}</h3>
      <p>{descripcion}</p>
    </div>
  );
}
