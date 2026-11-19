import { X } from "lucide-react";
import type { StreamPreview as Stream } from "./types";

export function StreamPreview({
  group,
  streams,
  loading,
  onClose,
}: {
  group: string | null;
  streams: Stream[];
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <section className="app-panel">
      <div className="app-section app-section--header">
        <h2>{group ? `Состав группы ${group}` : "Состав группы"}</h2>
        {group && (
          <button
            className="button-icon"
            type="button"
            aria-label="Закрыть просмотр группы"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        )}
      </div>
      {loading ? (
        <p className="app-section" role="status">
          Загрузка потоков…
        </p>
      ) : group && streams.length ? (
        <div className="app-table-scroll generation-preview">
          <table className="app-table">
            <thead>
              <tr>
                <th scope="col">Дисциплина</th>
                <th scope="col">Тип</th>
                <th scope="col">Преподаватель</th>
              </tr>
            </thead>
            <tbody>
              {streams.map((stream) => (
                <tr key={stream.id}>
                  <td>{stream.event_name}</td>
                  <td>{stream.stream_type}</td>
                  <td>{stream.teacher || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="app-section text-text-secondary">
          {group
            ? "Нет пар, соответствующих фильтрам"
            : "Откройте состав группы, чтобы проверить её пары"}
        </p>
      )}
    </section>
  );
}
