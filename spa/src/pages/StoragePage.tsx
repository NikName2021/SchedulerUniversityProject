import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSpreadsheet,
  FileText,
  FileUp,
  FolderOpen,
  Trash2,
  Users,
} from "lucide-react";
import { API_BASE_URL, apiFetch, openDownload } from "../api/apiConfig";

type FolderName =
  | "Учебные планы и потоки"
  | "Аудитории"
  | "Доступность преподавателей";

interface FileItem {
  id: number;
  name: string;
  size: string;
  fileType: ImportFileType;
  status: string;
  date: string;
}

type ImportFileType = "streams" | "rooms";

const folders: Array<{
  title: FolderName;
  description: string;
  icon: typeof FileSpreadsheet;
  accent: "blue" | "slate" | "amber";
  note: string;
}> = [
  {
    title: "Учебные планы и потоки",
    description: "Учебные дисциплины, потоки и состав групп для расчёта.",
    icon: FileSpreadsheet,
    accent: "blue",
    note: "Импорт Excel и CSV",
  },
  {
    title: "Аудитории",
    description: "Помещения, вместимость и типы занятий для размещения пар.",
    icon: FolderOpen,
    accent: "slate",
    note: "Импорт справочника помещений",
  },
  {
    title: "Доступность преподавателей",
    description:
      "Индивидуальные окна доступности и ограничения преподавателей.",
    icon: Users,
    accent: "amber",
    note: "Шаблон доступности Excel",
  },
];

const DragDropZone: React.FC<{
  onDrop: (files: FileList) => void;
  isDragging: boolean;
  setIsDragging: (value: boolean) => void;
}> = ({ onDrop, isDragging, setIsDragging }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      className={`upload-zone ${isDragging ? "upload-zone--active" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        if (event.dataTransfer.files.length > 0)
          onDrop(event.dataTransfer.files);
      }}
    >
      <div className="upload-zone__icon">
        <FileUp size={24} strokeWidth={1.8} />
      </div>
      <div>
        <h3>Загрузите файл</h3>
        <p>
          Перетащите Excel или CSV в эту область либо выберите его на
          компьютере.
        </p>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        hidden
        accept=".xls,.xlsx,.csv"
        onChange={(event) => {
          if (event.target.files?.length) onDrop(event.target.files);
        }}
      />
      <button
        type="button"
        className="btn-secondary"
        onClick={() => fileInputRef.current?.click()}
      >
        Выбрать файл
      </button>
      <span className="upload-zone__formats">
        Поддерживаются: XLS, XLSX, CSV
      </span>
    </div>
  );
};

const FileListItem: React.FC<{
  file: FileItem;
  onDownload: () => void;
  onRemove: () => void;
}> = ({ file, onDownload, onRemove }) => (
  <div className="import-file-row">
    <div className="import-file-row__icon">
      <FileText size={19} />
    </div>
    <div className="import-file-row__main">
      <strong>{file.name}</strong>
      <span>
        {file.size}
        {file.date
          ? ` · ${new Date(file.date).toLocaleDateString("ru-RU")}`
          : ""}
      </span>
    </div>
    <span className="status-badge status-badge--success">
      <CheckCircle2 size={13} /> Загружен
    </span>
    <button
      type="button"
      onClick={onDownload}
      className="button-icon import-file-row__download"
      title="Скачать файл"
      aria-label={`Скачать ${file.name}`}
    >
      <Download size={16} />
    </button>
    <button
      type="button"
      onClick={onRemove}
      className="button-icon import-file-row__delete"
      title="Удалить файл"
      aria-label={`Удалить ${file.name}`}
    >
      <Trash2 size={16} />
    </button>
  </div>
);

export const StoragePage: React.FC = () => {
  const [selectedFolder, setSelectedFolder] = useState<FolderName | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);

  const fetchHistory = useCallback(async (fileType: ImportFileType) => {
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/import/history?file_type=${fileType}`,
      );
      if (!response.ok) return;
      const data = await response.json();
      setFiles(
        data.map(
          (item: {
            id: number;
            filename: string;
            file_type: ImportFileType;
            created_date: string;
          }) => ({
            id: item.id,
            name: item.filename,
            size: item.file_type === "rooms" ? "Аудитории" : "Потоки",
            fileType: item.file_type,
            status: "ready",
            date: item.created_date,
          }),
        ),
      );
    } catch (requestError) {
      console.error(requestError);
    }
  }, []);

  const uploadFile = useCallback(
    async (file: File) => {
      if (!selectedFolder) return;
      setIsUploading(true);
      setError(null);
      setSuccessMsg(null);
      const formData = new FormData();
      formData.append("file", file);
      const isTeacherImport = selectedFolder === "Доступность преподавателей";
      const isRoomImport = selectedFolder === "Аудитории";
      const endpoint = isTeacherImport
        ? `${API_BASE_URL}/api/v1/scheduler/teachers/import`
        : isRoomImport
          ? `${API_BASE_URL}/api/v1/reference/rooms/import`
          : `${API_BASE_URL}/api/v1/scheduler/import/streams`;

      try {
        const response = await apiFetch(endpoint, {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const payload = await response.json();
          throw new Error(payload.detail || "Не удалось загрузить файл");
        }
        const payload = await response.json();
        setSuccessMsg(
          isTeacherImport
            ? `Доступность обновлена: преподавателей — ${payload.updated_teachers}.`
            : isRoomImport
              ? `Аудитории загружены: распознано — ${payload.rooms_found}, добавлено — ${payload.rooms_created}, обновлено — ${payload.rooms_updated}.`
              : `Файл загружен: потоков — ${payload.streams_added}, групп — ${payload.groups_added}.`,
        );
        if (!isTeacherImport) {
          await fetchHistory(isRoomImport ? "rooms" : "streams");
        }
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить файл",
        );
      } finally {
        setIsUploading(false);
      }
    },
    [fetchHistory, selectedFolder],
  );

  useEffect(() => {
    if (selectedFolder === "Учебные планы и потоки") {
      void fetchHistory("streams");
    } else if (selectedFolder === "Аудитории") {
      void fetchHistory("rooms");
    } else {
      setFiles([]);
    }
  }, [fetchHistory, selectedFolder]);

  const removeFile = async (file: FileItem) => {
    try {
      const response = await apiFetch(
        `${API_BASE_URL}/api/v1/scheduler/import/history/${file.id}`,
        { method: "DELETE" },
      );
      if (!response.ok) return;
      setSuccessMsg(
        file.fileType === "streams"
          ? "Файл и связанные данные удалены."
          : "Файл удалён из истории импорта.",
      );
      await fetchHistory(file.fileType);
    } catch (requestError) {
      console.error(requestError);
    }
  };

  const handleExportTeachers = () => {
    openDownload(`${API_BASE_URL}/api/v1/scheduler/teachers/export`);
  };

  if (!selectedFolder) {
    return (
      <div className="enterprise-page animate-fade-in">
        <section className="data-overview">
          <div>
            <span className="data-overview__eyebrow">КАТАЛОГ ДАННЫХ</span>
            <h2>Подготовьте исходные данные</h2>
            <p>
              Загрузите и проверьте наборы данных перед распределением нагрузки
              и расчётом расписания.
            </p>
          </div>
          <div className="data-overview__summary">
            <strong>3</strong>
            <span>раздела данных</span>
          </div>
        </section>
        <section className="data-source-grid" aria-label="Разделы хранилища">
          {folders.map((folder) => {
            const Icon = folder.icon;
            return (
              <button
                key={folder.title}
                type="button"
                className="data-source-card"
                onClick={() => setSelectedFolder(folder.title)}
              >
                <div
                  className={`data-source-card__icon data-source-card__icon--${folder.accent}`}
                >
                  <Icon size={23} strokeWidth={1.8} />
                </div>
                <div className="data-source-card__content">
                  <h3>{folder.title}</h3>
                  <p>{folder.description}</p>
                </div>
                <div className="data-source-card__footer">
                  <span>{folder.note}</span>
                  <ChevronRight size={17} />
                </div>
              </button>
            );
          })}
        </section>
      </div>
    );
  }

  const isTeacherFolder = selectedFolder === "Доступность преподавателей";
  const isRoomFolder = selectedFolder === "Аудитории";
  const isSingleImportFolder = isTeacherFolder;
  return (
    <div className="enterprise-page animate-fade-in">
      <section className="enterprise-page__header">
        <div>
          <button
            type="button"
            className="page-back"
            onClick={() => setSelectedFolder(null)}
          >
            <ArrowLeft size={16} /> Все разделы данных
          </button>
          <h2 className="enterprise-page__heading">{selectedFolder}</h2>
          <p className="enterprise-page__description">
            Загружайте актуальные файлы и контролируйте историю импорта.
          </p>
        </div>
        {isUploading && (
          <span className="status-badge status-badge--warning">
            Выполняется загрузка
          </span>
        )}
      </section>

      {error && <div className="notice notice--danger">{error}</div>}
      {successMsg && <div className="notice notice--success">{successMsg}</div>}

      <div
        className={`import-workspace ${isSingleImportFolder ? "import-workspace--single" : ""}`}
      >
        <div className="app-panel import-workspace__upload">
          {isRoomFolder && (
            <div className="availability-note availability-note--rooms">
              <div className="availability-note__icon">
                <FolderOpen size={20} />
              </div>
              <div>
                <h3>Импорт аудиторий</h3>
                <p>
                  Файл должен содержать название аудитории, вместимость и, при
                  наличии, тип учебного помещения.
                </p>
              </div>
            </div>
          )}
          {isTeacherFolder && (
            <div className="availability-note">
              <div className="availability-note__icon">
                <Users size={20} />
              </div>
              <div>
                <h3>Управление доступностью</h3>
                <p>
                  Скачайте текущий список, укажите окна в формате «день_пара»
                  или «ГГГГ-ММ-ДД_пара», затем загрузите файл обратно.
                </p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleExportTeachers}
              >
                <Download size={16} /> Скачать шаблон
              </button>
            </div>
          )}
          <DragDropZone
            onDrop={(uploadedFiles) => void uploadFile(uploadedFiles[0])}
            isDragging={isDragging}
            setIsDragging={setIsDragging}
          />
        </div>

        {!isSingleImportFolder && (
          <section className="app-panel import-history">
            <div className="import-history__header">
              <div>
                <h3>История импорта</h3>
                <p>Файлы, на основе которых сформированы данные.</p>
              </div>
              <span className="status-badge status-badge--neutral">
                {files.length}
              </span>
            </div>
            <div className="import-history__list">
              {files.map((file) => (
                <FileListItem
                  key={file.id}
                  file={file}
                  onDownload={() =>
                    openDownload(
                      `${API_BASE_URL}/api/v1/scheduler/import/history/${file.id}/download`,
                    )
                  }
                  onRemove={() => void removeFile(file)}
                />
              ))}
              {files.length === 0 && (
                <div className="import-empty">
                  <FileSpreadsheet size={26} />
                  <strong>Нет загруженных файлов</strong>
                  <span>После импорта файлы появятся в этом списке.</span>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};
